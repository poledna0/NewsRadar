from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    queries: list[str]
    enabled: bool


class TopicCreate(BaseModel):
    name: str = Field(min_length=2, max_length=60, pattern=r"^[\wÀ-ÿ][\w À-ÿ+.#-]*$")
    queries: list[str] = Field(default_factory=list, max_length=8)

    def normalized_queries(self) -> list[str]:
        queries = [query.strip()[:160] for query in self.queries if query.strip()]
        return list(dict.fromkeys(queries)) or [self.name.strip()]


class TranslationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12_000)


class TranslationOut(BaseModel):
    translation: str


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
    article_type: str
    translation_pt: str | None
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