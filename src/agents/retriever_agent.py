"""
Retriever node: runs hybrid search + reranking for all sub-queries in parallel.
This is a pure Python function, not an LLM agent.
Uses a thread pool so CPU-bound embedding work doesn't block the event loop.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from src.agents.state import AgentState, RetrievedChunk, SubQuery
from src.retrieval.searcher import hybrid_search, get_parent_text
from src.retrieval.reranker import rerank
from src.config import get_settings

log = logging.getLogger(__name__)

# Shared executor for embedding work (CPU-bound, not I/O-bound)
_executor = ThreadPoolExecutor(max_workers=4)


def _retrieve_for_subquery(sub_query: SubQuery) -> list[RetrievedChunk]:
    """Sync retrieval for a single sub-query. Runs in thread pool."""
    settings = get_settings()

    results = hybrid_search(
        query=sub_query.query,
        top_k=settings.top_k_retrieval,
    )
    reranked = rerank(sub_query.query, results, top_k=settings.top_k_final)

    chunks = []
    for r in reranked:
        parent_text = get_parent_text(r.parent_id) if r.parent_id != r.chunk_id else ""
        chunks.append(
            RetrievedChunk(
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
                sub_query=sub_query.query,
            )
        )
    return chunks


async def retriever_node_async(state: AgentState) -> dict:
    """
    Async version: dispatches all sub-query retrievals to the thread pool in parallel.
    Used when the graph is run with ainvoke/astream.
    """
    import asyncio

    sub_queries: list[SubQuery] = state.get("sub_queries", [])
    if not sub_queries:
        log.warning("Retriever called with no sub-queries")
        return {"retrieved_chunks": [], "status": "synthesizing"}

    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(_executor, _retrieve_for_subquery, sq)
        for sq in sub_queries
    ]
    all_results = await asyncio.gather(*tasks)

    # Merge and deduplicate by chunk_id, keeping best score
    seen: dict[str, RetrievedChunk] = {}
    for results in all_results:
        for chunk in results:
            if chunk.chunk_id not in seen or chunk.score > seen[chunk.chunk_id].score:
                seen[chunk.chunk_id] = chunk

    merged = sorted(seen.values(), key=lambda c: c.score, reverse=True)

    log.info(
        "Retriever: %d unique chunks from %d sub-queries",
        len(merged),
        len(sub_queries),
    )

    return {"retrieved_chunks": merged, "status": "synthesizing"}


def retriever_node(state: AgentState) -> dict:
    """
    Sync wrapper for use in synchronous graph invocations.
    Falls back to running each sub-query sequentially.
    """
    sub_queries: list[SubQuery] = state.get("sub_queries", [])
    if not sub_queries:
        return {"retrieved_chunks": [], "status": "synthesizing"}

    seen: dict[str, RetrievedChunk] = {}
    for sq in sub_queries:
        for chunk in _retrieve_for_subquery(sq):
            if chunk.chunk_id not in seen or chunk.score > seen[chunk.chunk_id].score:
                seen[chunk.chunk_id] = chunk

    merged = sorted(seen.values(), key=lambda c: c.score, reverse=True)
    log.info("Retriever: %d unique chunks from %d sub-queries", len(merged), len(sub_queries))
    return {"retrieved_chunks": merged, "status": "synthesizing"}
