from functools import lru_cache
from pathlib import Path

import yaml
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "NewsRadar"
    app_port: int = 8000
    database_url: str = "sqlite:///./data/newsradar.db"
    searxng_url: str = "http://localhost:8080"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    collection_interval_minutes: int = Field(default=30, ge=5)
    max_results_per_query: int = Field(default=10, ge=1, le=50)
    max_results_per_feed: int = Field(default=20, ge=1, le=100)
    article_max_age_hours: int = Field(default=48, ge=1)
    request_timeout_seconds: float = Field(default=15, gt=0, le=120)
    http_user_agent: str = "NewsRadar/0.1 (+self-hosted news aggregator)"
    config_file: str = "config.yaml"
    sources_file: str = "sources.yaml"
    max_queries_per_topic: int = Field(default=4, ge=1, le=10)
    max_research_results_per_topic: int = Field(default=5, ge=1, le=20)
    ai_articles_per_run: int = Field(default=200, ge=1, le=500)
    max_http_response_bytes: int = Field(default=8_000_000, ge=100_000, le=25_000_000)
    allowed_hosts: str = "localhost,127.0.0.1,host.docker.internal"
    max_request_body_bytes: int = Field(default=64_000, ge=1_024, le=1_000_000)
    cf_access_team_domain: str | None = None
    cf_access_audience: str | None = None
    translation_default_target: Literal["pt-BR", "en"] = "pt-BR"
    collect_on_start: bool = True
    respect_robots_txt: bool = True

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def config_path(self) -> Path:
        path = Path(self.config_file)
        return path if path.is_absolute() else ROOT_DIR / path

    @property
    def sources_path(self) -> Path:
        path = Path(self.sources_file)
        return path if path.is_absolute() else ROOT_DIR / path

    def read_yaml(self, path: Path) -> dict:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as stream:
            return yaml.safe_load(stream) or {}

    def topics(self) -> list[dict]:
        return self.read_yaml(self.config_path).get("topics", [])

    def languages(self) -> list[str]:
        return self.read_yaml(self.config_path).get("languages", ["pt", "en"])

    def feeds(self) -> list[dict]:
        return self.read_yaml(self.sources_path).get("feeds", [])


@lru_cache

def get_settings() -> Settings:
    return Settings()
