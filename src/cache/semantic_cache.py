"""
Redis-based semantic query cache.
Before hitting the agent pipeline, checks if a similar query was answered recently.
Similarity is measured by cosine distance between BGE-M3 dense embeddings.
"""

import hashlib
import json
import logging
import math
from typing import Any

import redis as redis_lib

from src.config import get_settings

log = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "rshub:cache:"
INDEX_KEY = "rshub:cache:index"


def _get_redis() -> redis_lib.Redis:
    settings = get_settings()
    return redis_lib.from_url(settings.redis_url, decode_responses=False)


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def get_cached_response(query: str) -> dict | None:
    """
    Returns cached response if a semantically similar query was cached.
    Returns None if no match above threshold.
    """
    settings = get_settings()
    r = _get_redis()

    # Get all cached query embeddings
    index_data = r.get(INDEX_KEY)
    if not index_data:
        return None

    index: list[dict] = json.loads(index_data)
    if not index:
        return None

    # Embed current query
    from src.ingestion.embedder import embed_query
    current_embedding = embed_query(query)["dense"]

    best_score = 0.0
    best_key = None

    for entry in index:
        sim = _cosine_sim(current_embedding, entry["embedding"])
        if sim > best_score:
            best_score = sim
            best_key = entry["key"]

    if best_score >= settings.semantic_cache_threshold and best_key:
        cached_raw = r.get(f"{CACHE_KEY_PREFIX}{best_key}")
        if cached_raw:
            log.info("Cache hit: similarity=%.3f for query: %s", best_score, query[:60])
            return json.loads(cached_raw)

    return None


def set_cached_response(query: str, response: dict) -> None:
    """Stores a query-response pair in the semantic cache."""
    settings = get_settings()
    r = _get_redis()

    from src.ingestion.embedder import embed_query
    embedding = embed_query(query)["dense"]

    cache_key = hashlib.sha256(query.encode()).hexdigest()[:16]

    # Store the response
    r.setex(
        f"{CACHE_KEY_PREFIX}{cache_key}",
        settings.cache_ttl_seconds,
        json.dumps(response),
    )

    # Update the index
    index_data = r.get(INDEX_KEY)
    index: list[dict] = json.loads(index_data) if index_data else []

    # Remove old entry for this key if it exists
    index = [e for e in index if e["key"] != cache_key]
    index.append({"key": cache_key, "query": query[:100], "embedding": embedding})

    # Keep index manageable (max 500 entries)
    if len(index) > 500:
        index = index[-500:]

    r.setex(INDEX_KEY, settings.cache_ttl_seconds, json.dumps(index))
    log.debug("Cached response for: %s", query[:60])


def invalidate_by_source(source_type: str) -> int:
    """Flushes all cached entries (called when source documents change)."""
    r = _get_redis()
    keys = list(r.scan_iter(f"{CACHE_KEY_PREFIX}*"))
    if keys:
        r.delete(*keys)
    r.delete(INDEX_KEY)
    log.info("Cache invalidated: %d entries removed (source: %s)", len(keys), source_type)
    return len(keys)
