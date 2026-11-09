import asyncio
import logging
import time
from collections import OrderedDict
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import trafilatura
from trafilatura.metadata import extract_metadata

from app.config import get_settings
from app.services.http import get_public_response

logger = logging.getLogger(__name__)
# Entries expire and oldest entries are evicted; failed lookups retry sooner.
_ROBOTS_MAX_ENTRIES = 256
_robots_cache: OrderedDict[str, tuple[float, RobotFileParser | None]] = OrderedDict()


async def _robots_allowed(url: str) -> bool:
    settings = get_settings()
    if not settings.respect_robots_txt:
        return True
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    now = time.monotonic()
    cached = _robots_cache.get(origin)
    if cached is None or cached[0] <= now:
        parser = RobotFileParser()
        parser.set_url(f"{origin}/robots.txt")
        try:
            response = await get_public_response(parser.url)
            parser.parse(response.text.splitlines())
            _robots_cache[origin] = (now + 3600, parser)
        except Exception:
            _robots_cache[origin] = (now + 60, None)
    _robots_cache.move_to_end(origin)
    while len(_robots_cache) > _ROBOTS_MAX_ENTRIES:
        _robots_cache.popitem(last=False)
    parser = _robots_cache[origin][1]
    return parser is None or parser.can_fetch(settings.http_user_agent, url)


def _extract_document(downloaded: str, url: str) -> dict:
    content = trafilatura.extract(downloaded, url=url, include_comments=False, include_tables=False)
    metadata = extract_metadata(downloaded, default_url=url)
    return {
        "title": metadata.title if metadata else None,
        "author": metadata.author if metadata else None,
        "published_at": metadata.date if metadata else None,
        "content": content,
        "description": metadata.description if metadata else None,
        "image_url": metadata.image if metadata else None,
    }


async def extract_article(url: str) -> dict:
    try:
        if not await _robots_allowed(url):
            logger.info("robots.txt disallows article extraction: %s", url)
            return {}
        response = await get_public_response(url)
        # Parsing HTML is CPU-bound; keep the event loop responsive.
        return await asyncio.to_thread(_extract_document, response.text, url)
    except Exception as error:
        logger.warning("Article extraction failed for %s: %s", url, error)
        return {}