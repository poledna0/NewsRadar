from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    enabled: bool


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    domain: str | None
    feed_url: str | None
    enabled: bool
    last_checked_at: datetime | None
    last_error: str | None


class ArticleOut(BaseModel):
    id: int
    url: str
    canonical_url: str
    title: str
    source_name: str | None
    source_domain: str | None
    author: str | None
    published_at: datetime | None
    discovered_at: datetime
    description: str | None
    summary: str | None
    category: str | None
    relevance_score: int
    language: str | None
    image_url: str | None
    processing_status: str
    related_sources: list[dict]
    topics: list[str]


class ArticleListOut(BaseModel):
    items: list[ArticleOut]
    total: int
    limit: int
    offset: int