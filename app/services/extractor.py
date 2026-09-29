import logging
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import trafilatura
from trafilatura.metadata import extract_metadata

from app.config import get_settings
from app.services.http import get_public_response, make_client

logger = logging.getLogger(__name__)
_robots_cache: dict[str, RobotFileParser | None] = {}


async def _robots_allowed(client: httpx.AsyncClient, url: str) -> bool:
    settings = get_settings()
    if not settings.respect_robots_txt:
        return True
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in _robots_cache:
        parser = RobotFileParser()
        parser.set_url(f"{origin}/robots.txt")
        try:
            response = await get_public_response(client, parser.url)
            parser.parse(response.text.splitlines())
            _robots_cache[origin] = parser
        except (httpx.HTTPError, ValueError):
            _robots_cache[origin] = None
    parser = _robots_cache[origin]
    return parser is None or parser.can_fetch(settings.http_user_agent, url)


async def extract_article(url: str) -> dict:
    try:
        async with make_client() as client:
            if not await _robots_allowed(client, url):
                logger.info("robots.txt disallows article extraction: %s", url)
                return {}
            response = await get_public_response(client, url)
        downloaded = response.text
        content = trafilatura.extract(downloaded, url=url, include_comments=False, include_tables=False)
        metadata = extract_metadata(downloaded, url=url)
        return {
            "title": metadata.title if metadata else None,
            "author": metadata.author if metadata else None,
            "published_at": metadata.date if metadata else None,
            "content": content,
            "description": metadata.description if metadata else None,
            "image_url": metadata.image if metadata else None,
        }
    except Exception as error:
        logger.warning("Article extraction failed for %s: %s", url, error)
        return {}