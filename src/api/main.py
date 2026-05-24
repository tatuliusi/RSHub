"""
FastAPI application entry point.
"""

import logging

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

settings = get_settings()

app = FastAPI(
    title="RSHub Tax RAG API",
    description="Multi-agent RAG system for Georgian tax consultation",
    version="0.1.0",
)

# CORS - allow frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.add_middleware(
    RateLimitMiddleware,
    redis_url=settings.redis_url,
    limit=settings.rate_limit_per_minute,
    window_seconds=60,
)

app.include_router(health_router)
app.include_router(chat_router)


@app.on_event("startup")
async def startup():
    logging.getLogger(__name__).info("RSHub API starting up")
