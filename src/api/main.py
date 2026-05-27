"""
FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.chat import router as chat_router
from src.api.routes.health import router as health_router
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log = logging.getLogger(__name__)
    log.info("RSHub API starting up (allowed origins: %s)", settings.allowed_origins)
    from src.observability import init_langfuse
    init_langfuse()
    yield
    log.info("RSHub API shutting down")


settings = get_settings()

app = FastAPI(
    title="RSHub Tax RAG API",
    description="Multi-agent RAG system for Georgian tax consultation",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    RateLimitMiddleware,
    redis_url=settings.redis_url,
    limit=settings.rate_limit_per_minute,
    window_seconds=60,
)

app.include_router(health_router)
app.include_router(chat_router)
