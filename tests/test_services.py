from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Article
from app.services import ollama, rss
from app.services.deduplicator import find_title_duplicate, normalize_title, normalize_url, title_similarity
from app.services.http import PublicResolver, validate_public_url


def test_url_normalization_removes_tracking_and_fragment():
    assert normalize_url("HTTPS://WWW.Example.com/story/?utm_source=feed&id=7#part") == "https://example.com/story?id=7"


def test_url_normalization_preserves_valid_ipv6_authority():
    assert normalize_url("http://[2001:4860:4860::8888]:8080/story") == "http://[2001:4860:4860::8888]:8080/story"


def test_url_normalization_rejects_non_http_scheme():
    with pytest.raises(ValueError):
        normalize_url("file:///etc/passwd")


def test_url_normalization_rejects_embedded_credentials():
    with pytest.raises(ValueError):
        normalize_url("https://user:secret@example.org/article")


def test_title_similarity_groups_small_variations():
    first = "New critical flaw found in Linux kernel"
    second = "New critical flaw found in the Linux kernel"
    assert normalize_title(first) == "new critical flaw found in linux kernel"
    assert title_similarity(first, second) >= 0.88
    assert find_title_duplicate(first, [SimpleNamespace(title=second)]) is not None


def test_private_article_urls_are_rejected():
    assert not __import__("asyncio").run(validate_public_url("http://127.0.0.1/article"))
    assert not __import__("asyncio").run(validate_public_url("file:///tmp/article"))


@pytest.mark.asyncio
async def test_scraper_dns_resolver_rejects_private_answers(monkeypatch):
    class FakeLoop:
        async def getaddrinfo(self, _host, port, **_kwargs):
            return [(2, 1, 6, "", ("10.0.0.8", port))]

    monkeypatch.setattr("app.services.http.asyncio.get_running_loop", lambda: FakeLoop())
    with pytest.raises(OSError, match="not globally routable"):
        await PublicResolver().resolve("attacker.example", 443)


def test_article_storage_round_trip():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        article = Article(url="https://example.org/a", canonical_url="https://example.org/a", title="News")
        session.add(article)
        session.commit()
        stored = session.scalar(select(Article).where(Article.canonical_url == "https://example.org/a"))
        assert stored is not None
        assert stored.title == "News"
        assert stored.processing_status == "pending_ai"
    engine.dispose()


@pytest.mark.asyncio
async def test_ollama_generation_disables_thinking(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": '{"ok": true}'}

    class FakeClient:
        payload = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, json):
            self.payload = json
            return FakeResponse()

    fake_client = FakeClient()
    monkeypatch.setattr(ollama.httpx, "AsyncClient", lambda **_kwargs: fake_client)
    assert await ollama._generate("prompt") == '{"ok": true}'
    assert fake_client.payload["think"] is False


@pytest.mark.asyncio
async def test_classification_limits_topics_and_score(monkeypatch):
    async def fake_generate(_prompt):
        return '{"relevance_score": 120, "category": "linux", "topics": ["Linux", "fora"], "important": true}'

    monkeypatch.setattr(ollama, "_generate", fake_generate)
    result = await ollama.classify({"title": "Linux"}, ["Linux"])
    assert result["relevance_score"] == 100
    assert result["topics"] == ["Linux"]
    assert result["article_type"] == "news"


@pytest.mark.asyncio
async def test_research_sources_remain_classified_as_research(monkeypatch):
    async def fake_generate(_prompt):
        return '{"relevance_score": 80, "category": "ai", "article_type": "news", "topics": ["AI"]}'

    monkeypatch.setattr(ollama, "_generate", fake_generate)
    result = await ollama.classify({"title": "A new paper", "article_type": "research"}, ["AI"])
    assert result["article_type"] == "research"


@pytest.mark.asyncio
async def test_translation_returns_only_translated_text(monkeypatch):
    async def fake_generate(_prompt):
        return '{"translation": "O sistema protege a conta."}'

    monkeypatch.setattr(ollama, "_generate", fake_generate)
    assert await ollama.translate_to_pt_br("The system protects the account.") == "O sistema protege a conta."


@pytest.mark.asyncio
async def test_event_consolidation_returns_title_and_summary(monkeypatch):
    async def fake_generate(_prompt):
        return '{"title": "Falha afeta sistemas Linux", "summary": "Duas fontes relataram a falha."}'

    monkeypatch.setattr(ollama, "_generate", fake_generate)
    title, summary = await ollama.consolidate_event(
        {"related_sources": [{"name": "Fonte A", "title": "Falha no Linux", "description": "Detalhes"}]}
    )
    assert title == "Falha afeta sistemas Linux"
    assert summary == "Duas fontes relataram a falha."


@pytest.mark.asyncio
async def test_rss_parser_returns_entries(monkeypatch):
    monkeypatch.setattr(rss, "get_public_response", lambda *_args: _fake_response())
    monkeypatch.setattr(
        rss.feedparser,
        "parse",
        lambda _content: SimpleNamespace(
            bozo=False,
            entries=[{"title": "Uma notícia", "link": "https://example.org/a", "summary": "Descrição"}],
        ),
    )
    result = await rss.read_feed({"name": "Teste", "url": "https://example.org/rss"})
    assert result[0]["title"] == "Uma notícia"
    assert result[0]["source_name"] == "Teste"


async def _fake_response():
    return SimpleNamespace(content=b"<rss />")


@pytest.mark.asyncio
async def test_broken_rss_returns_empty_list(monkeypatch):
    async def broken_request(*_args):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(rss, "get_public_response", broken_request)
    assert await rss.read_feed({"name": "Offline", "url": "https://example.org/rss"}) == []