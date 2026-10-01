from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app import main
from app.main import app
from app.config import get_settings
from app.models import Article


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def override_get_db():
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(get_settings(), "collect_on_start", False)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, base_url="http://127.0.0.1") as test_client:
        test_client.app.state.test_engine = engine
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_articles_api_returns_empty_page(client):
    response = client.get("/api/articles")
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert client.get("/api/articles?kind=research").json()["items"] == []


def test_daily_archive_paginates_all_articles_for_a_day(client):
    with Session(client.app.state.test_engine) as session:
        for index in range(35):
            session.add(
                Article(
                    url=f"https://example.org/archive/{index}",
                    canonical_url=f"https://example.org/archive/{index}",
                    title=f"Daily article {index}",
                    published_at=datetime(2026, 9, 28, 12, index, tzinfo=timezone.utc),
                )
            )
        session.commit()

    second_page = client.get("/?day=2026-09-28&page=2&kind=news")
    assert second_page.status_code == 200
    assert "Página 2 / 2 · 35 resultados" in second_page.text
    assert second_page.text.count('class="news-item"') == 5
    filtered_api = client.get("/api/articles?day=2026-09-28&kind=news&limit=100")
    assert filtered_api.json()["total"] == 35


def test_subscription_domains_are_hidden_without_deleting_rows(client):
    with Session(client.app.state.test_engine) as session:
        articles = [
            Article(
                url="https://www.forbes.com/paywalled",
                canonical_url="https://www.forbes.com/paywalled",
                title="Subscription article",
                source_domain="www.forbes.com",
            ),
            Article(
                url="https://www.theregister.com/open",
                canonical_url="https://www.theregister.com/open",
                title="Open access article",
                source_domain="www.theregister.com",
            ),
        ]
        session.add_all(articles)
        session.commit()
        paywalled_id = articles[0].id
        assert session.get(Article, paywalled_id) is not None

    listing = client.get("/api/articles")
    titles = [article["title"] for article in listing.json()["items"]]
    assert "Subscription article" not in titles
    assert "Open access article" in titles
    assert client.get(f"/api/articles/{paywalled_id}").status_code == 404


def test_topic_can_be_added_with_search_terms(client):
    response = client.post(
        "/api/topics",
        json={"name": "Computação quântica", "queries": ["quantum computing", "computação quântica"]},
    )
    assert response.status_code == 201
    assert response.json()["queries"] == ["quantum computing", "computação quântica"]
    assert response.json()["name"] == "Computação quântica"


def test_disabled_topic_can_be_reenabled_from_the_form(client):
    created = client.post("/api/topics", json={"name": "Sistemas distribuídos"})
    topic_id = created.json()["id"]
    assert client.delete(f"/api/topics/{topic_id}").status_code == 204
    recreated = client.post("/api/topics", json={"name": "Sistemas distribuídos", "queries": ["distributed systems"]})
    assert recreated.status_code == 201
    assert recreated.json()["enabled"] is True
    assert recreated.json()["queries"] == ["distributed systems"]


def test_cross_site_write_is_rejected(client):
    response = client.post("/api/topics", headers={"Origin": "https://attacker.example"}, json={"name": "tema invasor"})
    assert response.status_code == 403


def test_translation_endpoint_uses_local_translation_service(client, monkeypatch):
    async def fake_translation(_text, target):
        assert target == "pt-BR"
        return "Tradução segura"

    monkeypatch.setattr(main, "translate_to_language", fake_translation)
    response = client.post("/api/translate", json={"text": "A short English paragraph."})
    assert response.status_code == 200
    assert response.json() == {"translation": "Tradução segura", "target": "pt-BR"}


def test_translation_endpoint_accepts_english_target(client, monkeypatch):
    async def fake_translation(_text, target):
        assert target == "en"
        return "Translated into English"

    monkeypatch.setattr(main, "translate_to_language", fake_translation)
    response = client.post("/api/translate", json={"text": "Um parágrafo curto.", "target": "en"})
    assert response.status_code == 200
    assert response.json() == {"translation": "Translated into English", "target": "en"}


def test_article_translation_is_cached_separately_per_target(client, monkeypatch):
    with Session(client.app.state.test_engine) as session:
        article = Article(
            url="https://example.org/translation-test",
            canonical_url="https://example.org/translation-test",
            title="A short article",
            summary="The story is ready.",
        )
        session.add(article)
        session.commit()
        article_id = article.id

    calls = []

    async def fake_translation(_text, target):
        calls.append(target)
        return f"translation-{target}"

    monkeypatch.setattr(main, "translate_to_language", fake_translation)
    english = client.post(f"/api/articles/{article_id}/translate?target=en")
    english_again = client.post(f"/api/articles/{article_id}/translate?target=en")
    portuguese = client.post(f"/api/articles/{article_id}/translate?target=pt-BR")
    assert english.json() == {"translation": "translation-en", "target": "en"}
    assert english_again.json() == english.json()
    assert portuguese.json() == {"translation": "translation-pt-BR", "target": "pt-BR"}
    assert calls == ["en", "pt-BR"]


def test_security_headers_are_present(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_cloudflare_jwt_is_required_when_access_is_configured(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "cf_access_audience", "test-audience")
    response = client.get("/")
    assert response.status_code == 401


def test_unknown_host_is_rejected(client):
    response = client.get("/", headers={"Host": "attacker.example"})
    assert response.status_code == 400