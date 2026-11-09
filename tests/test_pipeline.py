from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Article, ProcessingRun, Topic
from app.services import pipeline


@pytest.fixture
def engine(tmp_path):
    target = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(target)
    yield target
    target.dispose()


def add_article(session, index=0, **fields):
    article = Article(url=f'https://example.org/{index}', canonical_url=f'https://example.org/{index}',
                      title=fields.pop('title', f'Article {index}'), **fields)
    session.add(article)
    session.commit()
    return article.id


@pytest.mark.asyncio
async def test_url_duplicate_topic_survives_session_close(engine):
    with Session(engine) as session:
        article_id = add_article(session)
        topic = Topic(name='Linux', queries=['linux'], origin='ui')
        session.add(topic)
        session.commit()
        counters = {'duplicates': 0}
        await pipeline._ingest(session, {'url': 'https://example.org/0', 'topic_names': ['Linux']},
                               ProcessingRun(), {'Linux': topic}, counters)
    with Session(engine) as session:
        assert [topic.name for topic in session.get(Article, article_id).topics] == ['Linux']
    assert counters['duplicates'] == 1


@pytest.mark.asyncio
async def test_title_duplicate_matches_same_type_and_commits(engine, monkeypatch):
    async def unexpected_extract(_url):
        pytest.fail('A matching news article already exists')
    monkeypatch.setattr(pipeline, 'extract_article', unexpected_extract)
    with Session(engine) as session:
        title = 'Linux kernel release has important security fixes'
        news_id = add_article(session, 0, title=title, article_type='news')
        add_article(session, 1, title=title, article_type='research')
        counters = {'duplicates': 0, 'discovered': 0, 'errors': 0}
        await pipeline._ingest(session, {'url': 'https://example.org/2', 'title': title},
                               ProcessingRun(), {}, counters)
    with Session(engine) as session:
        article = session.get(Article, news_id)
        assert len(article.related_sources) == 2
        assert article.processing_status == 'pending_ai'


@pytest.mark.asyncio
async def test_pending_queue_loads_only_one_article_at_a_time(engine, monkeypatch):
    with Session(engine, expire_on_commit=False) as session:
        for index in range(5):
            add_article(session, index, content='x'*100_000)
        session.expunge_all()
        async def fake_process(_article, _topics):
            assert sum(isinstance(value, Article) for value in session.identity_map.values()) == 1
            return {'relevance_score': 80, 'topics': [], 'article_type': 'news'}, 'Summary', None
        monkeypatch.setattr(pipeline, 'process_article', fake_process)
        assert await pipeline._process_pending(session, {}, limit=3) == 3
        assert len(session.scalars(select(Article.id).where(Article.processing_status == 'pending_ai')).all()) == 2


@pytest.mark.asyncio
async def test_inference_failure_stops_batch_without_losing_pending(engine, monkeypatch):
    calls = 0
    async def unavailable(_article, _topics):
        nonlocal calls
        calls += 1
        raise TimeoutError('backend offline')
    monkeypatch.setattr(pipeline, 'process_article', unavailable)
    with Session(engine, expire_on_commit=False) as session:
        for index in range(3):
            add_article(session, index)
        assert await pipeline._process_pending(session, {}, limit=3) == 0
        assert calls == 1
        assert len(session.scalars(select(Article.id).where(Article.processing_status == 'pending_ai')).all()) == 3


@pytest.mark.asyncio
async def test_invalid_model_result_does_not_block_other_articles(engine, monkeypatch):
    calls = 0
    async def process(_article, _topics):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError('malformed model JSON')
        return {'relevance_score': 50, 'topics': []}, 'New summary', None
    monkeypatch.setattr(pipeline, 'process_article', process)
    with Session(engine, expire_on_commit=False) as session:
        add_article(session, 0, translation_pt='Stale translation')
        add_article(session, 1)
        assert await pipeline._process_pending(session, {}, limit=2) == 1
        assert calls == 2
        article = session.scalar(select(Article).where(Article.processing_status == 'processed'))
        assert article.translation_pt is None
