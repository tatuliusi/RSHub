"""
Retriever node: runs hybrid search + reranking for all sub-queries in parallel.
This is a pure Python function, not an LLM agent.
Uses a thread pool so CPU-bound embedding work doesn't block the event loop.
"""

import asyncio
import atexit
import logging
from concurrent.futures import ThreadPoolExecutor

from src.agents.state import AgentState, RetrievedChunk, SubQuery
from src.retrieval.searcher import hybrid_search, get_parent_texts_batch
from src.retrieval.reranker import rerank
from src.config import get_settings

log = logging.getLogger(__name__)

# Shared executor; worker count matched to typical sub-query concurrency (2-6 sub-queries)
_executor = ThreadPoolExecutor(max_workers=8)
atexit.register(_executor.shutdown, wait=False)


def _retrieve_for_subquery(sub_query: SubQuery) -> list[tuple]:
    """
    Sync retrieval for a single sub-query. Runs in thread pool.
    Returns list of (SearchResult, sub_query_text) pairs — parent text is fetched
    in a single batch after all sub-queries complete.
    """
    settings = get_settings()

    results = hybrid_search(
        query=sub_query.query,
        top_k=settings.top_k_retrieval,
        source_hint=sub_query.source_hint,
    )
    reranked = rerank(sub_query.query, results, top_k=settings.top_k_final)
    return [(r, sub_query.query) for r in reranked]


def _batch_fetch_parents(result_pairs: list[tuple]) -> dict[str, str]:
    """
    Collects all unique parent IDs from result pairs and fetches them in one Qdrant call.
    """
    parent_ids = list({
        r.parent_id
        for r, _ in result_pairs
        if r.parent_id and r.parent_id != r.chunk_id
    })
    return get_parent_texts_batch(parent_ids)


async def retriever_node_async(state: AgentState) -> dict:
    """
    Dispatches all sub-query retrievals to the thread pool in parallel, then
    fetches all parent texts in a single batch call.
    On critic retries, accumulates chunks from previous iterations (capped at
    max_context_chunks to prevent context window overflow).
    """
    settings = get_settings()
    sub_queries: list[SubQuery] = state.get("sub_queries", [])
    if not sub_queries:
        log.warning("Retriever called with no sub-queries")
        return {"retrieved_chunks": [], "status": "synthesizing"}

    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(_executor, _retrieve_for_subquery, sq)
        for sq in sub_queries
    ]
    all_batches = await asyncio.gather(*tasks)

    # Flatten all (result, sub_query_text) pairs from this iteration
    new_pairs: list[tuple] = [pair for batch in all_batches for pair in batch]

    # Batch-fetch all parent texts in one Qdrant call
    parent_texts = await loop.run_in_executor(_executor, _batch_fetch_parents, new_pairs)

    # Start from previously accumulated chunks
    accumulated: dict[str, RetrievedChunk] = {
        c.chunk_id: c for c in state.get("retrieved_chunks", [])
    }

    for r, sq_text in new_pairs:
        parent_text = parent_texts.get(r.parent_id, "") if r.parent_id != r.chunk_id else ""
        chunk = RetrievedChunk(
            chunk_id=r.chunk_id,
            parent_id=r.parent_id,
            text=r.text,
            parent_text=parent_text,
            source=r.source,
            language=r.language,
            article_number=r.article_number,
            title=r.title,
            last_modified=r.last_modified,
            url=r.url,
            score=r.score,
            sub_query=sq_text,
            status=r.status,
        )
        if chunk.chunk_id not in accumulated or r.score > accumulated[chunk.chunk_id].score:
            accumulated[chunk.chunk_id] = chunk

    merged = sorted(accumulated.values(), key=lambda c: c.score, reverse=True)

    # Cap total chunks to prevent synthesizer context overflow
    if len(merged) > settings.max_context_chunks:
        log.warning(
            "Capping retrieved chunks at %d (had %d)",
            settings.max_context_chunks,
            len(merged),
        )
        merged = merged[: settings.max_context_chunks]

    log.info(
        "Retriever: %d unique chunks total (%d new sub-queries, iteration %d)",
        len(merged),
        len(sub_queries),
        state.get("iteration_count", 0),
    )

    return {"retrieved_chunks": merged, "status": "synthesizing"}


def retriever_node(state: AgentState) -> dict:
    """Sync wrapper for use in synchronous graph invocations."""
    settings = get_settings()
    sub_queries: list[SubQuery] = state.get("sub_queries", [])
    if not sub_queries:
        return {"retrieved_chunks": [], "status": "synthesizing"}

    all_pairs: list[tuple] = []
    for sq in sub_queries:
        all_pairs.extend(_retrieve_for_subquery(sq))

    parent_texts = _batch_fetch_parents(all_pairs)

    seen: dict[str, RetrievedChunk] = {}
    for r, sq_text in all_pairs:
        parent_text = parent_texts.get(r.parent_id, "") if r.parent_id != r.chunk_id else ""
        chunk = RetrievedChunk(
            chunk_id=r.chunk_id,
            parent_id=r.parent_id,
            text=r.text,
            parent_text=parent_text,
            source=r.source,
            language=r.language,
            article_number=r.article_number,
            title=r.title,
            last_modified=r.last_modified,
            url=r.url,
            score=r.score,
            sub_query=sq_text,
            status=r.status,
        )
        if chunk.chunk_id not in seen or r.score > seen[chunk.chunk_id].score:
            seen[chunk.chunk_id] = chunk

    merged = sorted(seen.values(), key=lambda c: c.score, reverse=True)
    if len(merged) > settings.max_context_chunks:
        merged = merged[: settings.max_context_chunks]

    log.info("Retriever: %d unique chunks from %d sub-queries", len(merged), len(sub_queries))
    return {"retrieved_chunks": merged, "status": "synthesizing"}
