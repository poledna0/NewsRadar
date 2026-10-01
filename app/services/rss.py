import logging

import feedparser
from dateutil import parser as date_parser

from app.config import get_settings
from app.services.http import get_public_response

logger = logging.getLogger(__name__)


async def read_feed(feed: dict) -> list[dict]:
    try:
        response = await get_public_response(feed["url"])
        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            raise ValueError(str(parsed.bozo_exception))
        items = []
        entries = parsed.entries[: get_settings().max_results_per_feed]
        if len(parsed.entries) > len(entries):
            logger.info(
                "RSS feed '%s' capped at %s entries",
                feed.get("name", feed.get("url")),
                len(entries),
            )
        configured_type = str(feed.get("article_type", "news")).strip().lower()
        article_type = "research" if configured_type == "research" else "news"
        category_hint = feed.get("category_hint")
        if configured_type not in {"news", "research"}:
            category_hint = category_hint or configured_type
        for entry in entries:
            link = entry.get("link")
            title = entry.get("title")
            if not link or not title:
                continue
            published = entry.get("published") or entry.get("updated")
            try:
                published = date_parser.parse(published).isoformat() if published else None
            except (TypeError, ValueError, OverflowError):
                published = None
            items.append(
                {
                    "url": link,
                    "title": title,
                    "description": entry.get("summary", ""),
                    "source_name": feed.get("name", "RSS"),
                    "published_at": published,
                    "image_url": None,
                    "topic_names": [],
                    "article_type": article_type,
                    "category_hint": category_hint,
                }
            )
        return items
    except Exception as error:
        logger.warning("RSS feed '%s' failed: %s", feed.get("name", feed.get("url")), error)
        return []