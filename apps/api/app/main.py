"""TasteOS FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app import __version__
from app.api.routes import router
from app.core.config import get_settings
from app.core.database import init_db
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)
settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_per_minute}/minute"],
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "Starting TasteOS mode=%s qloo_configured=%s",
        settings.tasteos_mode,
        settings.qloo_configured,
    )
    await init_db()
    yield


app = FastAPI(
    title="TasteOS API",
    description=(
        "Cultural Intelligence Layer for AI Agents.\n\n"
        "**Live mode** calls Qloo `GET /search` and `GET /v2/insights` "
        "(header `X-Api-Key`). **Demo mode** uses a labeled sample dataset.\n\n"
        "`qloo_affinity` is only set when Qloo returns it. "
        "`app_rank_score` is TasteOS negotiation logic — not a Qloo score."
    ),
    version=__version__,
    lifespan=lifespan,
)
app.state.limiter = limiter
register_exception_handlers(app)
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(
        status_code=429,
        content={"error": {"code": "rate_limited", "message": "Rate limit exceeded"}},
    ),
)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Accept",
        "X-TasteOS-Key",
        "X-Requested-With",
    ],
)
app.include_router(router)


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 1_000_000:
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "payload_too_large",
                    "message": "Request body too large",
                }
            },
        )
    return await call_next(request)
