import asyncio
import logging
from urllib.parse import urlsplit

import feedparser

from app.config import get_settings
from app.services.http import get_public_response
from app.services.source_policy import is_excluded_domain

logger = logging.getLogger(__name__)


async def _check_feed(feed: dict, semaphore: asyncio.Semaphore) -> tuple[str, str, int]:
    name = str(feed.get("name", "Unnamed feed"))
    async with semaphore:
        domain = (urlsplit(feed.get("url", "")).hostname or "").lower()
        if is_excluded_domain(domain, get_settings().excluded_domain_list):
            return name, "excluded by EXCLUDED_DOMAINS", 0
        try:
            response = await get_public_response(feed["url"], attempts=1)
            parsed = feedparser.parse(response.content)
            if parsed.entries:
                return name, "ok", len(parsed.entries)
            return name, "empty or invalid feed", 0
        except Exception as error:
            logger.debug("Feed audit failed for %s: %s", name, error)
            return name, f"unavailable ({type(error).__name__})", 0


async def audit_feeds(concurrency: int = 8) -> list[tuple[str, str, int]]:
    settings = get_settings()
    semaphore = asyncio.Semaphore(concurrency)
    feeds = [feed for feed in settings.feeds() if feed.get("enabled", True)]
    return await asyncio.gather(*(_check_feed(feed, semaphore) for feed in feeds))


def main() -> None:
    results = asyncio.run(audit_feeds())
    failures = [result for result in results if result[1] != "ok"]
    for name, status, count in results:
        print(f"{status:32} {count:4} entries  {name}")
    print(f"\n{len(results) - len(failures)}/{len(results)} feeds returned readable entries")


if __name__ == "__main__":
    main()
