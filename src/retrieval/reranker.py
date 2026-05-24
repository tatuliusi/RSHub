"""
Cross-encoder reranking using bge-reranker-v2-m3.
Takes the top-K candidates from hybrid search and rescores them.
Model is loaded once at module import time.
"""

import logging
from functools import lru_cache

from src.config import get_settings
from src.retrieval.searcher import SearchResult

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_reranker():
    from FlagEmbedding import FlagReranker

    settings = get_settings()
    log.info("Loading reranker: %s", settings.bge_reranker_model)
    reranker = FlagReranker(
        settings.bge_reranker_model,
        use_fp16=(settings.bge_m3_device != "cpu"),
        device=settings.bge_m3_device,
    )
    log.info("Reranker loaded")
    return reranker


def rerank(query: str, results: list[SearchResult], top_k: int | None = None) -> list[SearchResult]:
    """
    Reranks search results using the cross-encoder.
    Returns top_k results sorted by reranker score descending.
    """
    if not results:
        return []

    settings = get_settings()
    final_k = top_k or settings.top_k_final

    reranker = _load_reranker()

    # Build (query, passage) pairs
    pairs = [[query, r.text] for r in results]
    scores = reranker.compute_score(pairs, normalize=True)

    # Attach scores and sort
    scored = sorted(zip(scores, results), key=lambda x: x[0], reverse=True)

    top = scored[:final_k]
    reranked = []
    for score, result in top:
        result.score = float(score)
        reranked.append(result)

    return reranked
