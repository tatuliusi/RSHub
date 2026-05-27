"""
Redis-based semantic query cache.

Design:
- Cache is GLOBAL (cross-session): only critic-APPROVED answers are stored, so serving
  the same verified tax answer to different users is correct and safe.
- Embeddings are stored as raw numpy float32 bytes, NOT serialised into the index JSON.
  This keeps the index small (~30 bytes/entry) and makes the similarity scan fast.
- Cosine similarity is computed with numpy (vectorised, ~100x faster than pure Python).
- Invalidation scans all rshub:cache:*, rshub:emb:*, and the index key.
"""

import asyncio
import hashlib
import json
import logging

import numpy as np
import redis.asyncio as aioredis

from src.config import get_settings

log = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "rshub:cache:"
EMB_KEY_PREFIX = "rshub:emb:"
INDEX_KEY = "rshub:idx"

_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=False)
    return _redis_client


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / norm) if norm > 0 else 0.0


async def get_cached_response(query: str) -> dict | None:
    """
    Returns a cached response for a semantically similar query, or None.
    Cross-session: any user's approved answer can be returned to any other user.
    """
    settings = get_settings()
    r = _get_redis()

    index_data = await r.get(INDEX_KEY)
    if not index_data:
        return None

    index: list[dict] = json.loads(index_data)
    if not index:
        return None

    from src.ingestion.embedder import embed_query
    current_embedding = await asyncio.to_thread(embed_query, query)
    current_vec = np.array(current_embedding["dense"], dtype=np.float32)

    # Batch-fetch all cached embeddings in one round-trip
    emb_keys = [f"{EMB_KEY_PREFIX}{e['key']}" for e in index]
    raw_embs = await r.mget(*emb_keys)

    best_score = 0.0
    best_key: str | None = None

    for entry, raw_emb in zip(index, raw_embs):
        if raw_emb is None:
            continue
        cached_vec = np.frombuffer(raw_emb, dtype=np.float32)
        sim = _cosine_sim(current_vec, cached_vec)
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
    """Stores a critic-approved query-response pair in the global semantic cache."""
    settings = get_settings()
    r = _get_redis()

    from src.ingestion.embedder import embed_query
    embedding = await asyncio.to_thread(embed_query, query)
    vec = np.array(embedding["dense"], dtype=np.float32)

    cache_key = hashlib.sha256(query.encode()).hexdigest()[:16]

    pipe = r.pipeline()
    # Store embedding as compact binary (float32, 4 bytes × 1024 dims = 4 KB)
    pipe.setex(f"{EMB_KEY_PREFIX}{cache_key}", settings.cache_ttl_seconds, vec.tobytes())
    # Store response JSON
    pipe.setex(f"{CACHE_KEY_PREFIX}{cache_key}", settings.cache_ttl_seconds, json.dumps(response))
    await pipe.execute()

    # Update compact index (no embeddings, just {key, preview})
    index_data = await r.get(INDEX_KEY)
    index: list[dict] = json.loads(index_data) if index_data else []
    index = [e for e in index if e["key"] != cache_key]
    index.append({"key": cache_key, "q": query[:100]})

    if len(index) > 1000:
        index = index[-1000:]

    await r.setex(INDEX_KEY, settings.cache_ttl_seconds, json.dumps(index))
    log.debug("Cached response for query: %s", query[:60])


async def invalidate_cache() -> int:
    """Flushes all cached entries. Called when source documents change."""
    r = _get_redis()
    keys: list = []
    async for key in r.scan_iter(f"{CACHE_KEY_PREFIX}*"):
        keys.append(key)
    async for key in r.scan_iter(f"{EMB_KEY_PREFIX}*"):
        keys.append(key)
    if keys:
        await r.delete(*keys)
    await r.delete(INDEX_KEY)
    log.info("Cache invalidated: %d entries removed", len(keys))
    return len(keys)


# Keep old name as alias so scheduler/ingestion code doesn't break
async def invalidate_by_source(source_type: str) -> int:
    return await invalidate_cache()
