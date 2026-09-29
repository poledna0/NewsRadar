import asyncio
import logging
from urllib.parse import urlsplit

import httpx

from app.config import get_settings
from app.services.http import make_client

logger = logging.getLogger(__name__)


async def search_topic(topic: dict) -> list[dict]:
    settings = get_settings()
    configured_queries = topic.get("queries") or []
    queries = list(configured_queries[: settings.max_queries_per_topic])
    if not queries:
        queries = [topic["name"], f"{topic['name']} news"]
    results = []
    async with make_client() as client:
        for query in queries:
            try:
                for attempt in range(2):
                    try:
                        response = await client.get(
                            f"{settings.searxng_url.rstrip('/')}/search",
                            params={"q": query, "format": "json", "categories": "news"},
                        )
                        response.raise_for_status()
                        break
                    except httpx.HTTPError:
                        if attempt == 1:
                            raise
                        await asyncio.sleep(0.4)
                entries = response.json().get("results", [])[: settings.max_results_per_query]
                for item in entries:
                    if not item.get("url") or not item.get("title"):
                        continue
                    results.append(
                        {
                            "url": item["url"],
                            "title": item["title"],
                            "description": item.get("content") or "",
                            "source_name": urlsplit(item["url"]).hostname or "Busca na web",
                            "published_at": item.get("publishedDate"),
                            "image_url": item.get("thumbnail"),
                            "topic_names": [topic["name"]],
                        }
                    )
                logger.info("Topic '%s': %s results for query '%s'", topic["name"], len(entries), query)
            except Exception as error:
                logger.warning("SearXNG query failed for '%s': %s", query, error)
    return results