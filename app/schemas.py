from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    queries: list[str]
    enabled: bool


class TopicCreate(BaseModel):
    name: str = Field(min_length=2, max_length=60, pattern=r"^[\wÀ-ÿ][\w À-ÿ+.#-]*$")
    queries: list[Annotated[str, StringConstraints(max_length=160)]] = Field(default_factory=list, max_length=8)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    def normalized_queries(self) -> list[str]:
        queries = [query.strip()[:160] for query in self.queries if query.strip()]
        return list(dict.fromkeys(queries)) or [self.name.strip()]


class TopicUpdate(TopicCreate):
    """Fields editable for a saved topic in the navigation bar."""


class TranslationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12_000)
    target: Literal["pt-BR", "en"] | None = None

    @field_validator("text")
    @classmethod
    def reject_blank(cls, value):
        if not value.strip():
            raise ValueError("Informe um texto para traduzir")
        return value


class TranslationOut(BaseModel):
    translation: str
    target: Literal["pt-BR", "en"]


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
    translation_en: str | None
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
