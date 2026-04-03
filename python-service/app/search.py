"""FAISS dense vector search and SQLite metrics query service."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

import faiss
import numpy as np
import pandas as pd

from . import embedding
from .config import get_settings

logger = logging.getLogger(__name__)

_faiss_index: faiss.Index | None = None
_chunk_ids: list[str] = []
_chunk_metadata: dict[str, dict] = {}
_db_path: str = ""


def load_faiss_index() -> None:
    """Load FAISS index and chunk ID mapping from disk."""
    global _faiss_index, _chunk_ids, _chunk_metadata, _db_path

    settings = get_settings()
    index_dir = Path(settings.faiss_index_path)
    _db_path = settings.db_path

    index_file = index_dir / "index.faiss"
    ids_file = index_dir / "chunk_ids.json"

    if not index_file.exists():
        logger.warning("FAISS index not found at %s — dense search disabled", index_file)
        return

    _faiss_index = faiss.read_index(str(index_file))
    logger.info("FAISS index loaded: %d vectors", _faiss_index.ntotal)

    if ids_file.exists():
        with open(ids_file) as f:
            _chunk_ids = json.load(f)

    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, fiscal_year, section_id, section_title, content FROM chunks").fetchall()
    for row in rows:
        _chunk_metadata[row["id"]] = dict(row)
    conn.close()
    logger.info("Loaded metadata for %d chunks", len(_chunk_metadata))


def get_index_size() -> int:
    if _faiss_index is None:
        return 0
    return _faiss_index.ntotal


def dense_search(query: str, top_k: int = 20, filters: dict | None = None) -> list[dict]:
    """Search FAISS index using dense embedding similarity."""
    if _faiss_index is None or not _chunk_ids:
        return []

    query_vec = np.array(embedding.encode([query]), dtype=np.float32)
    scores, indices = _faiss_index.search(query_vec, min(top_k * 3, _faiss_index.ntotal))

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(_chunk_ids):
            continue
        chunk_id = _chunk_ids[idx]
        meta = _chunk_metadata.get(chunk_id)
        if meta is None:
            continue

        if filters:
            if "fiscal_year" in filters and meta["fiscal_year"] != filters["fiscal_year"]:
                continue
            if "section_id" in filters and meta["section_id"] != filters["section_id"]:
                continue

        results.append({
            "chunk_id": chunk_id,
            "score": float(score),
            "fiscal_year": meta["fiscal_year"],
            "section_id": meta["section_id"],
            "section_title": meta["section_title"],
            "content": meta["content"],
        })

        if len(results) >= top_k:
            break

    return results


def get_db_chunks_count() -> int:
    try:
        conn = sqlite3.connect(_db_path)
        count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def query_metrics(symbol: str, metric: str, fiscal_year: int | None = None) -> list[dict]:
    """Query structured financial metrics from SQLite."""
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row

    if fiscal_year:
        rows = conn.execute(
            "SELECT * FROM metrics WHERE symbol=? AND metric_name=? AND fiscal_year=? ORDER BY fiscal_year",
            (symbol, metric, fiscal_year),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM metrics WHERE symbol=? AND metric_name=? ORDER BY fiscal_year",
            (symbol, metric),
        ).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def query_trends(symbol: str, metric: str, start_year: int, end_year: int) -> dict:
    """Query metric trends with YoY and CAGR calculations using pandas."""
    conn = sqlite3.connect(_db_path)
    df = pd.read_sql_query(
        "SELECT fiscal_year, metric_value, metric_unit FROM metrics "
        "WHERE symbol=? AND metric_name=? AND fiscal_year BETWEEN ? AND ? "
        "ORDER BY fiscal_year",
        conn,
        params=(symbol, metric, start_year, end_year),
    )
    conn.close()

    if df.empty:
        return {"symbol": symbol, "metric": metric, "unit": "", "data": [], "cagr": None}

    df["yoy_change"] = df["metric_value"].diff()
    df["yoy_pct"] = df["metric_value"].pct_change() * 100

    unit = df["metric_unit"].iloc[0] if "metric_unit" in df.columns else ""

    cagr = None
    if len(df) >= 2:
        first_val = df["metric_value"].iloc[0]
        last_val = df["metric_value"].iloc[-1]
        n_years = df["fiscal_year"].iloc[-1] - df["fiscal_year"].iloc[0]
        if first_val > 0 and n_years > 0:
            cagr = round(((last_val / first_val) ** (1 / n_years) - 1) * 100, 2)

    data = []
    for _, row in df.iterrows():
        data.append({
            "fiscal_year": int(row["fiscal_year"]),
            "value": float(row["metric_value"]),
            "yoy_change": round(float(row["yoy_change"]), 2) if pd.notna(row["yoy_change"]) else None,
            "yoy_pct": round(float(row["yoy_pct"]), 2) if pd.notna(row["yoy_pct"]) else None,
        })

    return {
        "symbol": symbol,
        "metric": metric,
        "unit": unit,
        "data": data,
        "cagr": cagr,
    }


def list_available_metrics(symbol: str = "AAPL") -> list[str]:
    """List all available metric names for a symbol."""
    try:
        conn = sqlite3.connect(_db_path)
        rows = conn.execute(
            "SELECT DISTINCT metric_name FROM metrics WHERE symbol=? ORDER BY metric_name",
            (symbol,),
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []
