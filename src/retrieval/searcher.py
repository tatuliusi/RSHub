"""
Hybrid search over Qdrant using dense + sparse vectors with RRF fusion.
"""

import logging
from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Prefetch,
    FusionQuery,
    Fusion,
    Filter,
    FieldCondition,
    MatchValue,
    SparseVector,
    NamedSparseVector,
    NamedVector,
    SearchRequest,
    QueryRequest,
)

from src.config import get_settings
from src.ingestion.embedder import embed_query
from src.ingestion.indexer import DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME

log = logging.getLogger(__name__)


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
) -> list[SearchResult]:
    """
    Runs hybrid search using Qdrant's native RRF fusion over dense and sparse vectors.
    Only returns active (non-superseded) child chunks.
    """
    settings = get_settings()
    client = _get_client()
    limit = top_k or settings.top_k_retrieval

    # Embed the query (dense + sparse)
    embedding = embed_query(query)

    sparse_vec = SparseVector(
        indices=list(embedding["sparse"].keys()),
        values=list(embedding["sparse"].values()),
    )

    # Build metadata filter: active child chunks only
    must_conditions = [
        FieldCondition(key="status", match=MatchValue(value="active")),
        FieldCondition(key="is_parent", match=MatchValue(value=False)),
    ]
    if language_filter:
        must_conditions.append(
            FieldCondition(key="language", match=MatchValue(value=language_filter))
        )

    query_filter = Filter(must=must_conditions)

    # Hybrid search with RRF fusion
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


def get_parent_text(parent_id: str) -> str:
    """Fetches the parent chunk text for context enrichment."""
    settings = get_settings()
    client = _get_client()
    points = client.retrieve(
        collection_name=settings.qdrant_collection,
        ids=[parent_id],
        with_payload=True,
    )
    if points:
        return points[0].payload.get("text", "")
    return ""
