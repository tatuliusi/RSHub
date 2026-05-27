"""
Hybrid search over Qdrant using dense + sparse vectors with RRF fusion.
RRF (Reciprocal Rank Fusion) is rank-based and does not take an alpha weight;
see config.py — hybrid_alpha was removed as it had no effect.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Prefetch,
    FusionQuery,
    Fusion,
    Filter,
    FieldCondition,
    MatchValue,
    SparseVector,
)

from src.config import get_settings
from src.ingestion.embedder import embed_query
from src.ingestion.indexer import DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME

log = logging.getLogger(__name__)

# Source hint values that map to the "source" payload field
_VALID_SOURCE_HINTS = {"tax_code", "circular", "form", "guidance"}


@dataclass
class SearchResult:
    chunk_id: str
    parent_id: str
    text: str
    score: float
    source: str
    language: str
    article_number: str
    title: str
    last_modified: str
    url: str
    status: str


@lru_cache(maxsize=1)
def _get_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url)


def _payload_to_result(point) -> SearchResult:
    p = point.payload
    return SearchResult(
        chunk_id=str(point.id),
        parent_id=p.get("parent_id", ""),
        text=p.get("text", ""),
        score=point.score if hasattr(point, "score") else 0.0,
        source=p.get("source", ""),
        language=p.get("language", "ka"),
        article_number=p.get("article_number", ""),
        title=p.get("title", ""),
        last_modified=p.get("last_modified", ""),
        url=p.get("url", ""),
        status=p.get("status", "active"),
    )


def hybrid_search(
    query: str,
    top_k: int | None = None,
    language_filter: str | None = None,
    source_hint: str | None = None,
) -> list[SearchResult]:
    """
    Runs hybrid search using Qdrant's native RRF fusion over dense and sparse vectors.
    Only returns active (non-superseded) child chunks.
    source_hint filters by document type when set to a value other than "any".
    """
    settings = get_settings()
    client = _get_client()
    limit = top_k or settings.top_k_retrieval

    embedding = embed_query(query)

    sparse_vec = SparseVector(
        indices=list(embedding["sparse"].keys()),
        values=list(embedding["sparse"].values()),
    )

    must_conditions = [
        FieldCondition(key="status", match=MatchValue(value="active")),
        FieldCondition(key="is_parent", match=MatchValue(value=False)),
    ]
    if language_filter:
        must_conditions.append(
            FieldCondition(key="language", match=MatchValue(value=language_filter))
        )
    if source_hint and source_hint in _VALID_SOURCE_HINTS:
        must_conditions.append(
            FieldCondition(key="source", match=MatchValue(value=source_hint))
        )

    query_filter = Filter(must=must_conditions)

    results = client.query_points(
        collection_name=settings.qdrant_collection,
        prefetch=[
            Prefetch(
                query=embedding["dense"],
                using=DENSE_VECTOR_NAME,
                limit=limit,
                filter=query_filter,
            ),
            Prefetch(
                query=sparse_vec,
                using=SPARSE_VECTOR_NAME,
                limit=limit,
                filter=query_filter,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=limit,
        with_payload=True,
    )

    return [_payload_to_result(p) for p in results.points]


def get_parent_texts_batch(parent_ids: list[str]) -> dict[str, str]:
    """
    Fetches multiple parent chunk texts in a single Qdrant call.
    Returns a mapping of parent_id -> text.
    """
    if not parent_ids:
        return {}
    settings = get_settings()
    client = _get_client()
    points = client.retrieve(
        collection_name=settings.qdrant_collection,
        ids=parent_ids,
        with_payload=True,
    )
    return {str(p.id): p.payload.get("text", "") for p in points}


def get_parent_text(parent_id: str) -> str:
    """Fetches a single parent chunk text. Prefer get_parent_texts_batch for bulk lookups."""
    result = get_parent_texts_batch([parent_id])
    return result.get(parent_id, "")
