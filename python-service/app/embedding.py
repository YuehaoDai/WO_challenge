"""Embedding service using sentence-transformers BGE model."""

from __future__ import annotations

import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None
_model_name: str = ""


def load_model(model_name: str) -> None:
    global _model, _model_name
    if _model is not None and _model_name == model_name:
        return
    logger.info("Loading embedding model: %s", model_name)
    try:
        _model = SentenceTransformer(model_name)
    except Exception as e:
        logger.warning("Online load failed (%s), retrying from local cache...", type(e).__name__)
        import os
        os.environ["HF_HUB_OFFLINE"] = "1"
        _model = SentenceTransformer(model_name)
    _model_name = model_name
    logger.info("Embedding model loaded. Dimension: %d", _model.get_sentence_embedding_dimension())


def get_dimension() -> int:
    if _model is None:
        raise RuntimeError("Embedding model not loaded")
    return _model.get_sentence_embedding_dimension()


def encode(texts: list[str]) -> list[list[float]]:
    if _model is None:
        raise RuntimeError("Embedding model not loaded")
    embeddings = _model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()
