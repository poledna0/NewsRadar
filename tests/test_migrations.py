from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.database import ensure_schema
from app.models import Article, Topic


def test_additive_migration_preserves_existing_article_data():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """CREATE TABLE articles (
                id INTEGER PRIMARY KEY, url TEXT NOT NULL, canonical_url TEXT NOT NULL,
                title TEXT NOT NULL, source_name VARCHAR(255), source_domain VARCHAR(255),
                author VARCHAR(255), published_at DATETIME, discovered_at DATETIME NOT NULL,
                content TEXT, description TEXT, summary TEXT, category VARCHAR(120),
                relevance_score INTEGER NOT NULL, language VARCHAR(12), image_url TEXT,
                processing_status VARCHAR(32) NOT NULL, related_sources JSON NOT NULL,
                event_key VARCHAR(64), created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
            )"""
        )
        connection.exec_driver_sql(
            """CREATE TABLE topics (
                id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL UNIQUE,
                enabled BOOLEAN NOT NULL
            )"""
        )
        connection.execute(
            text("""INSERT INTO articles
                (id, url, canonical_url, title, discovered_at, relevance_score,
                 processing_status, related_sources, created_at, updated_at)
                VALUES (1, 'https://example.org/a', 'https://example.org/a', 'Artigo antigo',
                CURRENT_TIMESTAMP, 0, 'pending_ai', '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""")
        )
        connection.execute(text("INSERT INTO topics (id, name, enabled) VALUES (1, 'Linux', 1)"))

    ensure_schema(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("articles")}
    assert {"article_type", "translation_pt", "translation_en"}.issubset(columns)
    topic_columns = {column["name"] for column in inspect(engine).get_columns("topics")}
    assert {"queries", "origin"}.issubset(topic_columns)
    with Session(engine) as session:
        article = session.get(Article, 1)
        topic = session.get(Topic, 1)
        assert article.title == "Artigo antigo"
        assert article.article_type == "news"
        assert article.translation_pt is None
        assert article.translation_en is None
        assert topic.queries == []
        assert topic.origin == "yaml"
    engine.dispose()
