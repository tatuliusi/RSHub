"""
Redis sliding window rate limiter middleware.
"""

import time
import logging

import redis.asyncio as aioredis
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import get_settings

log = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str, limit: int, window_seconds: int = 60):
        super().__init__(app)
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self.limit = limit
        self.window = window_seconds

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and static files
        if request.url.path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)

        # X-Forwarded-For is set by reverse proxies and Docker NAT — prefer it over
        # request.client.host, which is the gateway IP for all containerized traffic.
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.headers.get("X-Real-IP") or (
                request.client.host if request.client else "unknown"
            )
        key = f"rshub:rate:{ip}"
        now = time.time()
        window_start = now - self.window

        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, self.window)
        _, _, count, _ = await pipe.execute()

        if count > self.limit:
            log.warning("Rate limit exceeded for IP: %s (%d requests)", ip, count)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {self.limit} requests per minute.",
            )

        return await call_next(request)
