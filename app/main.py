import asyncio
import ipaddress
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.config import ROOT_DIR, get_settings
from app.database import SessionLocal, engine, ensure_schema, get_db
from app.models import Article, ProcessingRun, Source, Topic
from app.schemas import ArticleListOut, ArticleOut, SourceOut, TopicCreate, TopicOut, TranslationOut, TranslationRequest
from app.services.pipeline import collect_news, process_pending_articles, sync_topics
from app.services.ollama import translate_to_language
from app.services.cloudflare_access import verify_access_token

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="UTC")
_rate_windows: dict[tuple[str, str], list[float]] = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_schema(engine)
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
    scheduler.add_job(
        process_pending_articles,
        "interval",
        minutes=5,
        id="pending_ai_retry",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    if get_settings().collect_on_start:
        asyncio.create_task(collect_news())
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="NewsRadar", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=get_settings().allowed_host_list)
app.mount("/static", StaticFiles(directory=ROOT_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=ROOT_DIR / "app" / "templates")


@app.middleware("http")
async def harden_response(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > get_settings().max_request_body_bytes:
        return JSONResponse({"detail": "request body is too large"}, status_code=413)
    settings = get_settings()
    # Access validation is optional until the owner supplies their team domain and app audience.
    if (settings.cf_access_audience or settings.cf_access_team_domain) and request.url.path != "/health":
        token = request.headers.get("cf-access-jwt-assertion", "")
        if not token or len(token) > 16_384:
            return JSONResponse({"detail": "Cloudflare Access assertion required"}, status_code=401)
        try:
            if not await verify_access_token(token):
                return JSONResponse({"detail": "invalid Cloudflare Access assertion"}, status_code=401)
        except Exception:
            logger.exception("Could not verify Cloudflare Access assertion")
            return JSONResponse({"detail": "identity verification is temporarily unavailable"}, status_code=503)
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https: data:; "
        "connect-src 'self'; form-action 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def protect_write(request: Request, action: str, limit: int, window_seconds: int) -> None:
    host = request.headers.get("host", "").lower()
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(status_code=403, detail="cross-site writes are not allowed")
    source = origin or referer
    if source and urlsplit(source).netloc.lower() != host:
        raise HTTPException(status_code=403, detail="cross-origin writes are not allowed")

    # A única worker mantém esta cota local efetiva sem adicionar Redis.
    client_host = request.client.host if request.client else "unknown"
    key = (client_host, action)
    now = time.monotonic()
    recent = [timestamp for timestamp in _rate_windows.get(key, []) if now - timestamp < window_seconds]
    if len(recent) >= limit:
        raise HTTPException(status_code=429, detail="too many requests")
    recent.append(now)
    _rate_windows[key] = recent
    if len(_rate_windows) > 2_048:
        _rate_windows.clear()


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
        "article_type": article.article_type,
        "translation_pt": article.translation_pt,
        "translation_en": article.translation_en,
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
    article_type: str | None = None,
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
    if article_type:
        query = query.where(Article.article_type == article_type)
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
    kind: str | None = Query(default=None, pattern="^(news|research)$"),
    sort: str = Query(default="date", pattern="^(date|relevance)$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
):
    query = article_query(session, topic, hours, source, search, article_type=kind)
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
    return session.scalars(select(Topic).where(Topic.enabled.is_(True)).order_by(Topic.name)).all()


@app.post("/api/topics", response_model=TopicOut, status_code=201)
def create_topic(payload: TopicCreate, request: Request, session: Session = Depends(get_db)):
    protect_write(request, "topics", limit=10, window_seconds=3_600)
    name = payload.name.strip()
    existing = session.scalar(select(Topic).where(func.lower(Topic.name) == name.lower()))
    if existing:
        if existing.enabled:
            raise HTTPException(status_code=409, detail="topic already exists")
        existing.enabled = True
        existing.queries = payload.normalized_queries()
        session.commit()
        session.refresh(existing)
        return existing
    topic = Topic(name=name, queries=payload.normalized_queries(), origin="ui", enabled=True)
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


@app.delete("/api/topics/{topic_id}", status_code=204)
def disable_topic(topic_id: int, request: Request, session: Session = Depends(get_db)):
    protect_write(request, "topics", limit=10, window_seconds=3_600)
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="topic not found")
    topic.enabled = False
    session.commit()


@app.post("/api/translate", response_model=TranslationOut)
async def translate_text(payload: TranslationRequest, request: Request):
    protect_write(request, "translate", limit=10, window_seconds=60)
    target = payload.target or get_settings().translation_default_target
    try:
        return {"translation": await translate_to_language(payload.text, target), "target": target}
    except Exception as error:
        logger.warning("Translation unavailable: %s", error)
        raise HTTPException(status_code=503, detail="translation is temporarily unavailable") from error


@app.post("/api/articles/{article_id}/translate", response_model=TranslationOut)
async def translate_article(
    article_id: int,
    request: Request,
    target: str | None = Query(default=None, pattern="^(pt-BR|en)$"),
    session: Session = Depends(get_db),
):
    protect_write(request, "translate", limit=10, window_seconds=60)
    article = session.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    target = target or get_settings().translation_default_target
    translation_field = "translation_pt" if target == "pt-BR" else "translation_en"
    if not getattr(article, translation_field):
        source = f"{article.title}\n\n{article.summary or article.description or ''}".strip()
        if not source:
            raise HTTPException(status_code=422, detail="article has no text to translate")
        try:
            setattr(article, translation_field, await translate_to_language(source[:12_000], target))
            session.commit()
        except Exception as error:
            session.rollback()
            logger.warning("Article translation unavailable for %s: %s", article_id, error)
            raise HTTPException(status_code=503, detail="translation is temporarily unavailable") from error
    return {"translation": getattr(article, translation_field), "target": target}


@app.get("/api/sources", response_model=list[SourceOut])
def list_sources(session: Session = Depends(get_db)):
    return session.scalars(select(Source).order_by(Source.name)).all()


@app.post("/api/collect")
async def run_collection(request: Request):
    protect_write(request, "collect", limit=2, window_seconds=600)
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
        "last_collection": session.scalar(
            select(ProcessingRun.finished_at)
            .where(ProcessingRun.status.not_in(["ai_processing", "ai_completed", "ai_failed"]))
            .order_by(ProcessingRun.started_at.desc())
            .limit(1)
        ),
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
    kind: str = Query(default="news", pattern="^(news|research)$"),
    session: Session = Depends(get_db),
):
    selected_query = article_query(
        session, topic, hours, source, search, events_only=view == "events", article_type=kind
    )
    if sort == "relevance":
        selected_query = selected_query.order_by(Article.relevance_score.desc(), Article.discovered_at.desc())
    else:
        selected_query = selected_query.order_by(Article.published_at.desc().nullslast(), Article.discovered_at.desc())
    latest = session.scalars(selected_query.limit(60)).unique().all()
    highlights = session.scalars(
        article_query(session, topic, hours, source, search, article_type=kind)
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
            "selected_kind": kind,
            "translation_default_target": get_settings().translation_default_target,
            "selected_hours": hours,
            "selected_source": source,
            "search": search or "",
            "sort": sort,
            "view": view,
            "total_articles": session.scalar(select(func.count(Article.id))) or 0,
            "pending_ai": session.scalar(select(func.count(Article.id)).where(Article.processing_status == "pending_ai")) or 0,
        },
    )