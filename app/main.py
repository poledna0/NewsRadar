import asyncio
import ipaddress
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.config import ROOT_DIR, get_settings
from app.database import Base, SessionLocal, engine, get_db
from app.models import Article, ProcessingRun, Source, Topic
from app.schemas import ArticleListOut, ArticleOut, SourceOut, TopicOut
from app.services.pipeline import collect_news, sync_topics

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="UTC")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        sync_topics(session)
    scheduler.add_job(
        collect_news,
        "interval",
        minutes=get_settings().collection_interval_minutes,
        id="newsradar_collection",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    if get_settings().collect_on_start:
        asyncio.create_task(collect_news())
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="NewsRadar", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=ROOT_DIR / "app" / "templates")


def article_dict(article: Article) -> dict:
    return {
        "id": article.id,
        "url": article.url,
        "canonical_url": article.canonical_url,
        "title": article.title,
        "source_name": article.source_name,
        "source_domain": article.source_domain,
        "author": article.author,
        "published_at": article.published_at,
        "discovered_at": article.discovered_at,
        "description": article.description,
        "summary": article.summary,
        "category": article.category,
        "relevance_score": article.relevance_score,
        "language": article.language,
        "image_url": article.image_url,
        "processing_status": article.processing_status,
        "related_sources": article.related_sources or [],
        "topics": [topic.name for topic in article.topics],
    }


def article_query(
    session: Session,
    topic: str | None,
    hours: int | None,
    source: str | None,
    search: str | None,
    events_only: bool = False,
):
    query = select(Article).options(selectinload(Article.topics))
    if topic:
        query = query.join(Article.topics).where(Topic.name == topic)
    if hours:
        query = query.where(Article.discovered_at >= datetime.now(timezone.utc) - timedelta(hours=hours))
    if source:
        query = query.where(Article.source_domain == source)
    if search:
        term = f"%{search.strip()}%"
        query = query.where((Article.title.ilike(term)) | (Article.description.ilike(term)) | (Article.summary.ilike(term)))
    if events_only:
        query = query.where(Article.related_sources.is_not(None)).where(Article.related_sources != [])
    return query


@app.get("/health")
def health(session: Session = Depends(get_db)):
    try:
        session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}
    except Exception as error:
        logger.exception("Health check failed")
        raise HTTPException(status_code=503, detail="database unavailable") from error


@app.get("/api/articles", response_model=ArticleListOut)
def list_articles(
    topic: str | None = None,
    hours: int | None = Query(default=None, ge=1, le=720),
    source: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    sort: str = Query(default="date", pattern="^(date|relevance)$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
):
    query = article_query(session, topic, hours, source, search)
    total = session.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    if sort == "relevance":
        query = query.order_by(Article.relevance_score.desc(), Article.discovered_at.desc())
    else:
        query = query.order_by(Article.published_at.desc().nullslast(), Article.discovered_at.desc())
    articles = session.scalars(query.offset(offset).limit(limit)).unique().all()
    return {"items": [article_dict(item) for item in articles], "total": total, "limit": limit, "offset": offset}


@app.get("/api/articles/{article_id}", response_model=ArticleOut)
def get_article(article_id: int, session: Session = Depends(get_db)):
    article = session.scalar(select(Article).options(selectinload(Article.topics)).where(Article.id == article_id))
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    return article_dict(article)


@app.get("/api/topics", response_model=list[TopicOut])
def list_topics(session: Session = Depends(get_db)):
    return session.scalars(select(Topic).order_by(Topic.name)).all()


@app.get("/api/sources", response_model=list[SourceOut])
def list_sources(session: Session = Depends(get_db)):
    return session.scalars(select(Source).order_by(Source.name)).all()


@app.post("/api/collect")
async def run_collection(request: Request):
    client_host = request.client.host if request.client else ""
    try:
        client_address = ipaddress.ip_address(client_host)
    except ValueError as error:
        raise HTTPException(status_code=403, detail="manual collection is limited to private networks") from error
    if not (client_address.is_private or client_address.is_loopback):
        raise HTTPException(status_code=403, detail="manual collection is limited to private networks")
    result = await collect_news()
    if result["status"] == "already_running":
        raise HTTPException(status_code=409, detail="collection already running")
    return result


@app.get("/api/stats")
def stats(session: Session = Depends(get_db)):
    return {
        "articles": session.scalar(select(func.count(Article.id))) or 0,
        "pending_ai": session.scalar(select(func.count(Article.id)).where(Article.processing_status == "pending_ai")) or 0,
        "sources": session.scalar(select(func.count(Source.id)).where(Source.enabled.is_(True))) or 0,
        "topics": session.scalar(select(func.count(Topic.id)).where(Topic.enabled.is_(True))) or 0,
        "last_collection": session.scalar(select(ProcessingRun.finished_at).order_by(ProcessingRun.started_at.desc()).limit(1)),
    }


@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    topic: str | None = None,
    hours: int | None = Query(default=None, ge=1, le=720),
    source: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    sort: str = Query(default="date", pattern="^(date|relevance)$"),
    view: str = Query(default="latest", pattern="^(latest|events)$"),
    session: Session = Depends(get_db),
):
    selected_query = article_query(session, topic, hours, source, search, events_only=view == "events")
    if sort == "relevance":
        selected_query = selected_query.order_by(Article.relevance_score.desc(), Article.discovered_at.desc())
    else:
        selected_query = selected_query.order_by(Article.published_at.desc().nullslast(), Article.discovered_at.desc())
    latest = session.scalars(selected_query.limit(60)).unique().all()
    highlights = session.scalars(
        article_query(session, topic, hours, source, search)
        .where(Article.relevance_score >= 60)
        .order_by(Article.relevance_score.desc(), Article.discovered_at.desc())
        .limit(4)
    ).unique().all()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "articles": latest,
            "highlights": highlights,
            "topics": session.scalars(select(Topic).where(Topic.enabled.is_(True)).order_by(Topic.name)).all(),
            "sources": session.scalars(select(Source.domain).where(Source.domain.is_not(None)).distinct().order_by(Source.domain)).all(),
            "selected_topic": topic,
            "selected_hours": hours,
            "selected_source": source,
            "search": search or "",
            "sort": sort,
            "view": view,
            "total_articles": session.scalar(select(func.count(Article.id))) or 0,
            "pending_ai": session.scalar(select(func.count(Article.id)).where(Article.processing_status == "pending_ai")) or 0,
        },
    )