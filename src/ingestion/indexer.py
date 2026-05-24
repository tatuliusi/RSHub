"""
Qdrant indexing.
Creates the collection if it doesn't exist, then upserts chunks with
both dense and sparse vectors plus metadata payload.
"""

import logging
from typing import Any

from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    PointStruct,
    SparseVector,
    PayloadSchemaType,
)

from src.config import get_settings
from src.ingestion.chunker import Chunk

log = logging.getLogger(__name__)

DENSE_DIM = 1024  # BGE-M3 dense output dimension
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"


def _get_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection() -> None:
    """Creates the Qdrant collection with named dense + sparse vectors if it doesn't exist."""
    settings = get_settings()
    client = _get_client()

    existing = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection in existing:
        log.info("Collection '%s' already exists", settings.qdrant_collection)
        return

    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config={
            DENSE_VECTOR_NAME: VectorParams(
                size=DENSE_DIM,
                distance=Distance.COSINE,
            )
        },
        sparse_vectors_config={
            SPARSE_VECTOR_NAME: SparseVectorParams(
                index=SparseIndexParams(on_disk=False)
            )
        },
    )

    # Payload index for fast metadata filtering
    for field_name in ("status", "language", "source", "article_number", "is_parent"):
        client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name=field_name,
            field_schema=PayloadSchemaType.KEYWORD,
        )

    log.info("Created collection '%s'", settings.qdrant_collection)


def _chunk_to_point(chunk: Chunk, embedding: dict[str, Any]) -> PointStruct:
    sparse_vec = SparseVector(
        indices=list(embedding["sparse"].keys()),
        values=list(embedding["sparse"].values()),
    )
    return PointStruct(
        id=chunk.chunk_id,
        vector={
            DENSE_VECTOR_NAME: embedding["dense"],
            SPARSE_VECTOR_NAME: sparse_vec,
        },
        payload={
            "text": chunk.text,
            "is_parent": chunk.is_parent,
            "parent_id": chunk.parent_id,
            "source": chunk.source,
            "language": chunk.language,
            "article_number": chunk.article_number,
            "title": chunk.title,
            "last_modified": chunk.last_modified,
            "url": chunk.url,
            "status": chunk.status,
            "doc_hash": chunk.doc_hash,
        },
    )


def upsert_chunks(chunks: list[Chunk], embeddings: list[dict[str, Any]], batch_size: int = 64) -> None:
    """Upserts chunks with their embeddings into Qdrant in batches."""
    settings = get_settings()
    client = _get_client()

    points = [_chunk_to_point(c, e) for c, e in zip(chunks, embeddings)]

    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        client.upsert(collection_name=settings.qdrant_collection, points=batch)
        log.debug("Upserted batch %d-%d", i, i + len(batch))

    log.info("Upserted %d points to '%s'", len(points), settings.qdrant_collection)


def mark_superseded(chunk_ids: list[str]) -> None:
    """Marks chunks as superseded (when source document is replaced)."""
    settings = get_settings()
    client = _get_client()
    from qdrant_client.models import SetPayload

    client.set_payload(
        collection_name=settings.qdrant_collection,
        payload={"status": "superseded"},
        points=chunk_ids,
    )


def get_parent_chunk(parent_id: str) -> dict | None:
    """Fetches a parent chunk by its ID."""
    settings = get_settings()
    client = _get_client()
    results = client.retrieve(
        collection_name=settings.qdrant_collection,
        ids=[parent_id],
        with_payload=True,
    )
    if results:
        return results[0].payload
    return None
