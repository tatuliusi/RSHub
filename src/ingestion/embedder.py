"""
BGE-M3 embedding generation.
Produces both dense and sparse vectors in a single forward pass.
Model is loaded once at module import time (singleton pattern).
"""

import logging
from functools import lru_cache
from typing import Any

from src.config import get_settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_model():
    from FlagEmbedding import BGEM3FlagModel

    settings = get_settings()
    log.info("Loading BGE-M3 model: %s on device: %s", settings.bge_m3_model, settings.bge_m3_device)
    model = BGEM3FlagModel(
        settings.bge_m3_model,
        use_fp16=(settings.bge_m3_device != "cpu"),
        device=settings.bge_m3_device,
    )
    log.info("BGE-M3 model loaded")
    return model


def embed_texts(
    texts: list[str],
    batch_size: int = 16,
    max_length: int = 8192,
) -> list[dict[str, Any]]:
    """
    Embeds a list of texts.
    Returns a list of dicts, each with:
      - "dense": list[float] - 1024-dim dense vector
      - "sparse": dict[int, float] - sparse vector (token_id -> weight)
    """
    model = _load_model()
    outputs = model.encode(
        texts,
        batch_size=batch_size,
        max_length=max_length,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )

    results = []
    for i in range(len(texts)):
        dense = outputs["dense_vecs"][i].tolist()
        # BGE-M3 sparse output is a dict {token_id: weight} per sample
        sparse_raw = outputs["lexical_weights"][i]
        sparse = {int(k): float(v) for k, v in sparse_raw.items()}
        results.append({"dense": dense, "sparse": sparse})

    return results


def embed_query(text: str) -> dict[str, Any]:
    """Embed a single query text. Returns same format as embed_texts."""
    return embed_texts([text])[0]
