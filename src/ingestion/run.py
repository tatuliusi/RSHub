"""
Ingestion orchestrator.
Called by the scheduler or manually to process scraped documents
through chunking -> embedding -> indexing.
"""

import asyncio
import logging

from src.ingestion.chunker import chunk_documents, Chunk
from src.ingestion.embedder import embed_texts
from src.ingestion.indexer import ensure_collection, upsert_chunks
from src.scraper.models import RawDocument

log = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 16


async def ingest_documents(docs: list[RawDocument]) -> None:
    """Full pipeline: chunk -> embed -> upsert into Qdrant."""
    if not docs:
        log.info("No documents to ingest")
        return

    log.info("Ingesting %d documents", len(docs))

    # 1. Chunk
    all_chunks = chunk_documents(docs)
    # Only embed child chunks (parents are stored but not searched directly)
    child_chunks = [c for c in all_chunks if not c.is_parent]
    parent_chunks = [c for c in all_chunks if c.is_parent]

    log.info(
        "Created %d parent + %d child chunks from %d documents",
        len(parent_chunks),
        len(child_chunks),
        len(docs),
    )

    # 2. Ensure collection exists
    ensure_collection()

    # 3. Upsert parent chunks without embeddings (stored for context retrieval)
    # Parents need dummy vectors - we insert them with zero vectors and rely on ID retrieval
    # Actually: parents also get embeddings for potential full-article search
    # Embed parents in small batches to avoid OOM
    log.info("Embedding %d parent chunks...", len(parent_chunks))
    parent_embeddings = _embed_in_batches([c.text for c in parent_chunks])
    upsert_chunks(parent_chunks, parent_embeddings)

    # 4. Embed and upsert child chunks
    log.info("Embedding %d child chunks...", len(child_chunks))
    child_embeddings = _embed_in_batches([c.text for c in child_chunks])
    upsert_chunks(child_chunks, child_embeddings)

    log.info("Ingestion complete: %d total chunks indexed", len(all_chunks))


def _embed_in_batches(texts: list[str]) -> list[dict]:
    all_embeddings = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        embeddings = embed_texts(batch)
        all_embeddings.extend(embeddings)
        log.debug("Embedded batch %d-%d", i, i + len(batch))
    return all_embeddings


async def run_full_ingestion() -> None:
    """Runs a complete ingestion from scratch (both Tax Code and rs.ge)."""
    from src.scraper.matsne import scrape_all_tax_code
    from src.scraper.rs_ge import scrape_all_rs_ge

    log.info("Starting full ingestion from all sources...")

    tax_code_docs = await scrape_all_tax_code()
    log.info("Scraped %d Tax Code articles", len(tax_code_docs))
    await ingest_documents(tax_code_docs)

    await asyncio.sleep(2)

    rs_ge_docs = await scrape_all_rs_ge()
    log.info("Scraped %d rs.ge documents", len(rs_ge_docs))
    await ingest_documents(rs_ge_docs)

    log.info("Full ingestion complete")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run_full_ingestion())
