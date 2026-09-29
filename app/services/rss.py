import logging

import feedparser
from dateutil import parser as date_parser

from app.services.http import make_client, get_public_response

logger = logging.getLogger(__name__)


async def read_feed(feed: dict) -> list[dict]:
    try:
        async with make_client() as client:
            response = await get_public_response(client, feed["url"])
        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            raise ValueError(str(parsed.bozo_exception))
        items = []
        for entry in parsed.entries:
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
                }
            )
        return items
    except Exception as error:
        logger.warning("RSS feed '%s' failed: %s", feed.get("name", feed.get("url")), error)
        return []