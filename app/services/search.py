import asyncio
import logging
from urllib.parse import urlsplit

import httpx

from app.config import get_settings
from app.services.http import make_client

logger = logging.getLogger(__name__)


async def _search(client: httpx.AsyncClient, query: str, category: str, limit: int) -> list[dict]:
    settings = get_settings()
    for attempt in range(2):
        try:
            response = await client.get(
                f"{settings.searxng_url.rstrip('/')}/search",
                params={"q": query, "format": "json", "categories": category},
            )
            response.raise_for_status()
            return response.json().get("results", [])[:limit]
        except httpx.HTTPError:
            if attempt == 1:
                raise
            await asyncio.sleep(0.4)
    return []


def _map_result(item: dict, topic_name: str, article_type: str) -> dict | None:
    url = item.get("url")
    if not url or not item.get("title"):
        return None
    return {
        "url": url,
        "title": item["title"],
        "description": item.get("content") or "",
        "source_name": urlsplit(url).hostname or "Busca na web",
        "published_at": item.get("publishedDate"),
        "image_url": item.get("thumbnail"),
        "topic_names": [topic_name],
        "article_type": article_type,
    }


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
                entries = await _search(client, query, "news", settings.max_results_per_query)
                results.extend(
                    mapped for item in entries if (mapped := _map_result(item, topic["name"], "news"))
                )
                logger.info("Topic '%s': %s news results for query '%s'", topic["name"], len(entries), query)
            except Exception as error:
                logger.warning("SearXNG news query failed for '%s': %s", query, error)
        research_query = f"{topic['name']} research study paper"
        try:
            entries = await _search(
                client, research_query, "science", settings.max_research_results_per_topic
            )
            results.extend(
                mapped for item in entries if (mapped := _map_result(item, topic["name"], "research"))
            )
            logger.info("Topic '%s': %s research results", topic["name"], len(entries))
        except Exception as error:
            logger.warning("SearXNG research query failed for '%s': %s", research_query, error)
    return results