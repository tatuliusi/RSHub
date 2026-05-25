"""
Redis-based semantic query cache.
Before hitting the agent pipeline, checks if a similar query was answered recently.
Similarity is measured by cosine distance between BGE-M3 dense embeddings.
"""

import asyncio
import hashlib
import json
import logging
import math
from typing import Any

import redis.asyncio as aioredis

from src.config import get_settings

log = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "rshub:cache:"
INDEX_KEY = "rshub:cache:index"

_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=False)
    return _redis_client


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def get_cached_response(query: str) -> dict | None:
    """
    Returns cached response if a semantically similar query was cached.
    Returns None if no match above threshold.
    """
    settings = get_settings()
    r = _get_redis()

    index_data = await r.get(INDEX_KEY)
    if not index_data:
        return None

    index: list[dict] = json.loads(index_data)
    if not index:
        return None

    # Embed in thread pool — BGE-M3 inference blocks the event loop if run inline
    from src.ingestion.embedder import embed_query
    current_embedding = await asyncio.to_thread(embed_query, query)
    current_embedding = current_embedding["dense"]

    best_score = 0.0
    best_key = None

    for entry in index:
        sim = _cosine_sim(current_embedding, entry["embedding"])
        if sim > best_score:
            best_score = sim
            best_key = entry["key"]

    if best_score >= settings.semantic_cache_threshold and best_key:
        cached_raw = await r.get(f"{CACHE_KEY_PREFIX}{best_key}")
        if cached_raw:
            log.info("Cache hit: similarity=%.3f for query: %s", best_score, query[:60])
            return json.loads(cached_raw)

    return None


async def set_cached_response(query: str, response: dict) -> None:
    """Stores a query-response pair in the semantic cache."""
    settings = get_settings()
    r = _get_redis()

    from src.ingestion.embedder import embed_query
    embedding = await asyncio.to_thread(embed_query, query)
    embedding = embedding["dense"]

    cache_key = hashlib.sha256(query.encode()).hexdigest()[:16]

    await r.setex(
        f"{CACHE_KEY_PREFIX}{cache_key}",
        settings.cache_ttl_seconds,
        json.dumps(response),
    )

    index_data = await r.get(INDEX_KEY)
    index: list[dict] = json.loads(index_data) if index_data else []

    index = [e for e in index if e["key"] != cache_key]
    index.append({"key": cache_key, "query": query[:100], "embedding": embedding})

    if len(index) > 500:
        index = index[-500:]

    await r.setex(INDEX_KEY, settings.cache_ttl_seconds, json.dumps(index))
    log.debug("Cached response for: %s", query[:60])


async def invalidate_by_source(source_type: str) -> int:
    """Flushes all cached entries (called when source documents change)."""
    r = _get_redis()
    keys = [key async for key in r.scan_iter(f"{CACHE_KEY_PREFIX}*")]
    if keys:
        await r.delete(*keys)
    await r.delete(INDEX_KEY)
    log.info("Cache invalidated: %d entries removed (source: %s)", len(keys), source_type)
    return len(keys)
