import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from dateutil import parser as date_parser
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import Article, ProcessingRun, Source, Topic, utc_now
from app.services.deduplicator import event_key, find_title_duplicate, normalize_url
from app.services.extractor import extract_article
from app.services.ollama import process_article
from app.services.rss import read_feed
from app.services.search import search_topic

logger = logging.getLogger(__name__)
_collection_lock = asyncio.Lock()


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = value if isinstance(value, datetime) else date_parser.parse(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def sync_topics(session: Session) -> list[Topic]:
    configured = get_settings().topics()
    found = []
    for item in configured:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        topic = session.scalar(select(Topic).where(Topic.name == name))
        if topic is None:
            topic = Topic(name=name, enabled=bool(item.get("enabled", True)))
            session.add(topic)
        else:
            topic.enabled = bool(item.get("enabled", True))
        found.append(topic)
    session.commit()
    return found


def _sync_sources(session: Session, feeds: list[dict]) -> None:
    for feed in feeds:
        name = feed.get("name", "RSS")
        source = session.scalar(select(Source).where(Source.name == name))
        domain = urlsplit(feed.get("url", "")).hostname
        if source is None:
            source = Source(name=name, domain=domain)
            session.add(source)
        source.domain = domain
        source.feed_url = feed.get("url")
        source.enabled = bool(feed.get("enabled", True))
    session.commit()


def _record_discovered_source(session: Session, name: str, domain: str | None) -> None:
    if not name:
        return
    source = session.scalar(select(Source).where(Source.name == name))
    if source is None:
        source = Source(name=name, domain=domain, enabled=True)
        session.add(source)
    else:
        source.domain = source.domain or domain
    source.last_checked_at = utc_now()


def _attach_topics(article: Article, names: list[str], topic_by_name: dict[str, Topic]) -> None:
    existing = {topic.name for topic in article.topics}
    for name in names:
        topic = topic_by_name.get(name)
        if topic and name not in existing:
            article.topics.append(topic)
            existing.add(name)


async def _ingest(session: Session, item: dict, run: ProcessingRun, topic_by_name: dict[str, Topic], counters: dict):
    url = item.get("url", "")
    try:
        canonical_url = normalize_url(url)
    except ValueError:
        counters["errors"] += 1
        return
    domain = urlsplit(canonical_url).hostname
    _record_discovered_source(session, item.get("source_name") or domain or "Fonte desconhecida", domain)
    existing = session.scalar(select(Article).where(Article.canonical_url == canonical_url))
    if existing:
        _attach_topics(existing, item.get("topic_names", []), topic_by_name)
        counters["duplicates"] += 1
        return

    published_at = _parse_datetime(item.get("published_at"))
    cutoff = utc_now() - timedelta(hours=get_settings().article_max_age_hours)
    if published_at and published_at < cutoff:
        return
    counters["discovered"] += 1
    candidates = session.scalars(
        select(Article).where(Article.discovered_at >= utc_now() - timedelta(days=3)).order_by(Article.discovered_at.desc())
    ).all()
    duplicate = find_title_duplicate(item.get("title", ""), candidates)
    if duplicate:
        sources = list(duplicate.related_sources or [])
        known_urls = {source.get("url") for source in sources}
        original = {
            "name": duplicate.source_name or duplicate.source_domain,
            "url": duplicate.url,
            "title": duplicate.title,
            "description": duplicate.description or "",
        }
        if duplicate.url not in known_urls:
            sources.append(original)
        incoming = {
            "name": item.get("source_name") or domain,
            "url": url,
            "title": item.get("title", ""),
            "description": item.get("description", ""),
        }
        if url not in {source.get("url") for source in sources}:
            sources.append(incoming)
        duplicate.related_sources = sources
        duplicate.processing_status = "pending_ai"
        _attach_topics(duplicate, item.get("topic_names", []), topic_by_name)
        counters["duplicates"] += 1
        logger.info("Grouped similar headline from %s under article %s", domain, duplicate.id)
        return

    extracted = await extract_article(url)
    article = Article(
        url=url,
        canonical_url=canonical_url,
        title=(extracted.get("title") or item.get("title") or "").strip(),
        source_name=item.get("source_name") or domain,
        source_domain=domain,
        published_at=_parse_datetime(extracted.get("published_at")) or published_at,
        discovered_at=utc_now(),
        content=extracted.get("content"),
        description=extracted.get("description") or item.get("description"),
        image_url=extracted.get("image_url") or item.get("image_url"),
        processing_status="pending_ai",
        event_key=event_key(item.get("title", "")),
    )
    _attach_topics(article, item.get("topic_names", []), topic_by_name)
    session.add(article)
    session.commit()
    counters["new"] += 1


async def _process_pending(session: Session, topic_by_name: dict[str, Topic], limit: int | None = None) -> int:
    limit = limit or get_settings().ai_articles_per_run
    pending = session.scalars(
        select(Article).where(Article.processing_status == "pending_ai").order_by(Article.discovered_at.desc()).limit(limit)
    ).all()
    topic_names = list(topic_by_name)
    processed = 0
    for article in pending:
        payload = {
            "title": article.title,
            "source_name": article.source_name,
            "description": article.description or "",
            "content": article.content or "",
            "related_sources": article.related_sources or [],
        }
        try:
            classification, summary, consolidated_title = await process_article(payload, topic_names)
            article.relevance_score = classification["relevance_score"]
            article.category = classification.get("category") or "Geral"
            article.summary = summary
            if consolidated_title:
                article.title = consolidated_title
            article.processing_status = "processed"
            _attach_topics(article, classification.get("topics", []), topic_by_name)
            session.commit()
            processed += 1
        except Exception as error:
            session.rollback()
            article = session.get(Article, article.id)
            if article:
                article.processing_status = "pending_ai"
                session.commit()
            logger.warning("AI processing unavailable for article %s: %s", article.id, error)
    return processed


async def collect_news() -> dict:
    if _collection_lock.locked():
        return {"status": "already_running"}
    async with _collection_lock:
        settings = get_settings()
        logger.info("Starting collection")
        session = SessionLocal()
        run = ProcessingRun(status="running")
        session.add(run)
        session.commit()
        counters = {"discovered": 0, "new": 0, "duplicates": 0, "errors": 0}
        try:
            topics = sync_topics(session)
            topic_by_name = {topic.name: topic for topic in topics if topic.enabled}
            feeds = [feed for feed in settings.feeds() if feed.get("enabled", True)]
            _sync_sources(session, settings.feeds())
            for topic in settings.topics():
                if topic.get("enabled", True):
                    results = await search_topic(topic)
                    for item in results:
                        try:
                            await _ingest(session, item, run, topic_by_name, counters)
                        except Exception:
                            session.rollback()
                            counters["errors"] += 1
                            logger.exception("Could not ingest search result: %s", item.get("url"))
            for feed in feeds:
                results = await read_feed(feed)
                for item in results:
                    try:
                        await _ingest(session, item, run, topic_by_name, counters)
                    except Exception:
                        session.rollback()
                        counters["errors"] += 1
                        logger.exception("Could not ingest RSS item from %s", feed.get("name"))
            processed_count = await _process_pending(session, topic_by_name)
            run.discovered_count = counters["discovered"]
            run.new_count = counters["new"]
            run.duplicate_count = counters["duplicates"]
            run.error_count = counters["errors"]
            run.status = "completed_with_errors" if counters["errors"] else "completed"
            run.details = json.dumps({**counters, "ai_processed": processed_count})
            logger.info(
                "Collection finished: %s discovered, %s new, %s duplicates, %s sent to Ollama",
                counters["discovered"], counters["new"], processed_count, counters["duplicates"],
            )
        except Exception as error:
            session.rollback()
            run = session.get(ProcessingRun, run.id)
            if run:
                run.status = "failed"
                run.error_count += 1
                run.details = str(error)
            logger.exception("Collection failed")
        finally:
            run = session.get(ProcessingRun, run.id)
            if run:
                run.finished_at = utc_now()
                session.commit()
            result = {
                "status": run.status if run else "failed",
                "discovered": counters["discovered"],
                "new": counters["new"],
                "duplicates": counters["duplicates"],
                "errors": counters["errors"],
            }
            session.close()
        return result