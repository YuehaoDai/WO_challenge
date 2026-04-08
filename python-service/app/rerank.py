"""Reranking service using BGE cross-encoder model."""

from __future__ import annotations

import logging
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

_model: CrossEncoder | None = None
_model_name: str = ""


def load_model(model_name: str) -> None:
    global _model, _model_name
    if _model is not None and _model_name == model_name:
        return
    logger.info("Loading reranker model: %s", model_name)
    try:
        _model = CrossEncoder(model_name)
    except Exception as e:
        logger.warning("Online load failed (%s), retrying from local cache...", type(e).__name__)
        import os
        os.environ["HF_HUB_OFFLINE"] = "1"
        _model = CrossEncoder(model_name)
    _model_name = model_name
    logger.info("Reranker model loaded")


def rerank(query: str, documents: list[dict], top_k: int = 8) -> list[dict]:
    """Rerank documents by relevance to query. Returns sorted list with scores."""
    if _model is None:
        logger.warning("Reranker not loaded — returning documents in original order")
        return [{"id": d["id"], "text": d["text"], "score": 1.0 / (i + 1), "rank": i + 1} for i, d in enumerate(documents[:top_k])]

    pairs = [(query, doc["text"]) for doc in documents]
    scores = _model.predict(pairs)

    scored_docs = []
    for i, doc in enumerate(documents):
        scored_docs.append({
            "id": doc["id"],
            "text": doc["text"],
            "score": float(scores[i]),
            "rank": 0,
        })

    scored_docs.sort(key=lambda x: x["score"], reverse=True)
    for rank, doc in enumerate(scored_docs[:top_k]):
        doc["rank"] = rank + 1

    return scored_docs[:top_k]
