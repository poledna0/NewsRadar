from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    url = get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    if url.startswith("sqlite:///") and ":memory:" not in url:
        database_path = url.removeprefix("sqlite:///").split("?", 1)[0]
        if not database_path.startswith("/"):
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def ensure_schema(target_engine=engine) -> None:
    """Create missing tables and additive columns without discarding the existing SQLite data."""
    Base.metadata.create_all(bind=target_engine)
    additions = {
        "articles": {
            "article_type": "VARCHAR(20) NOT NULL DEFAULT 'news'",
            "translation_pt": "TEXT",
        },
        "topics": {
            "queries": "JSON NOT NULL DEFAULT '[]'",
            "origin": "VARCHAR(16) NOT NULL DEFAULT 'yaml'",
        },
    }
    inspector = inspect(target_engine)
    with target_engine.begin() as connection:
        for table_name, columns in additions.items():
            present = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, declaration in columns.items():
                if column_name not in present:
                    connection.exec_driver_sql(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {declaration}"
                    )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_articles_article_type ON articles(article_type)"
        )


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()