#!/usr/bin/env python3
"""Master ingestion pipeline: parse → chunk → SQLite → FTS5 → FAISS → metrics.

Reads data/raw/aapl_10k.json and produces:
  - data/processed/app.db      (SQLite with chunks, FTS5, metrics tables)
  - data/processed/chunks.jsonl (one chunk per line for reference)
  - data/processed/faiss/       (FAISS index + chunk_ids.json)
"""

import json
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Support both local (python-service/app) and Docker (/app/python-service/app) layouts
for p in [str(PROJECT_ROOT / "python-service"), str(PROJECT_ROOT), str(SCRIPT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from app.config import Settings
from app import embedding

from scripts.chunker import chunk_sections
from scripts.extract_metrics import extract_all_metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

import os

DATA_ROOT = Path(os.environ.get("DATA_ROOT", str(PROJECT_ROOT / "data")))
RAW_PATH = DATA_ROOT / "raw" / "aapl_10k.json"
PROCESSED_DIR = DATA_ROOT / "processed"
DB_PATH = PROCESSED_DIR / "app.db"
CHUNKS_PATH = PROCESSED_DIR / "chunks.jsonl"
FAISS_DIR = PROCESSED_DIR / "faiss"


def load_raw_data() -> list[dict]:
    """Parse the aapl_10k.json file."""
    logger.info("Loading raw data from %s", RAW_PATH)
    with open(RAW_PATH) as f:
        data = json.load(f)

    key = list(data.keys())[0]
    sections = data[key]
    logger.info("Loaded %d section records", len(sections))
    return sections


def init_db(conn: sqlite3.Connection) -> None:
    """Create SQLite tables."""
    conn.executescript("""
        DROP TABLE IF EXISTS chunks;
        DROP TABLE IF EXISTS chunks_fts;
        DROP TABLE IF EXISTS metrics;

        CREATE TABLE chunks (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            fiscal_year INTEGER NOT NULL,
            form_type TEXT NOT NULL,
            section_id INTEGER NOT NULL,
            section_title TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            token_count INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            id,
            content,
            section_title,
            tokenize='porter'
        );

        CREATE TABLE metrics (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            fiscal_year INTEGER NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            metric_unit TEXT,
            source_section TEXT,
            source_ref TEXT
        );

        CREATE INDEX idx_chunks_year ON chunks(fiscal_year);
        CREATE INDEX idx_chunks_section ON chunks(section_id);
        CREATE INDEX idx_metrics_symbol_name ON metrics(symbol, metric_name);
        CREATE INDEX idx_metrics_year ON metrics(fiscal_year);
    """)


def insert_chunks(conn: sqlite3.Connection, chunks: list[dict]) -> None:
    """Insert chunks into SQLite and FTS5 index."""
    for chunk in chunks:
        conn.execute(
            "INSERT INTO chunks (id, symbol, fiscal_year, form_type, section_id, section_title, chunk_index, content, token_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                chunk["id"], chunk["symbol"], chunk["fiscal_year"],
                chunk["form_type"], chunk["section_id"], chunk["section_title"],
                chunk["chunk_index"], chunk["content"], chunk.get("token_count", 0),
            ),
        )
        conn.execute(
            "INSERT INTO chunks_fts (id, content, section_title) VALUES (?, ?, ?)",
            (chunk["id"], chunk["content"], chunk["section_title"]),
        )
    conn.commit()
    logger.info("Inserted %d chunks into SQLite + FTS5", len(chunks))


def insert_metrics(conn: sqlite3.Connection, metrics: list[dict]) -> None:
    """Insert structured financial metrics into SQLite."""
    for m in metrics:
        conn.execute(
            "INSERT OR REPLACE INTO metrics (id, symbol, fiscal_year, metric_name, metric_value, metric_unit, source_section, source_ref) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                m["id"], m["symbol"], m["fiscal_year"], m["metric_name"],
                m["metric_value"], m.get("metric_unit", ""), m.get("source_section", ""),
                m.get("source_ref", ""),
            ),
        )
    conn.commit()
    logger.info("Inserted %d metrics into SQLite", len(metrics))


def save_chunks_jsonl(chunks: list[dict]) -> None:
    """Save chunks as JSONL for reference."""
    with open(CHUNKS_PATH, "w") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    logger.info("Saved %d chunks to %s", len(chunks), CHUNKS_PATH)


def build_faiss_index(chunks: list[dict], model_name: str) -> None:
    """Build FAISS index from chunk embeddings."""
    import faiss

    embedding.load_model(model_name)
    texts = [c["content"] for c in chunks]

    logger.info("Encoding %d chunks...", len(texts))
    batch_size = 32
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        vecs = embedding.encode(batch)
        all_embeddings.extend(vecs)
        if (i // batch_size) % 10 == 0:
            logger.info("  encoded %d / %d", min(i + batch_size, len(texts)), len(texts))

    matrix = np.array(all_embeddings, dtype=np.float32)
    dim = matrix.shape[1]

    index = faiss.IndexFlatIP(dim)
    index.add(matrix)

    FAISS_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(FAISS_DIR / "index.faiss"))

    chunk_ids = [c["id"] for c in chunks]
    with open(FAISS_DIR / "chunk_ids.json", "w") as f:
        json.dump(chunk_ids, f)

    logger.info("FAISS index built: %d vectors, dim=%d, saved to %s", index.ntotal, dim, FAISS_DIR)


def validate_data(conn: sqlite3.Connection) -> None:
    """Basic data integrity validation."""
    chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    metric_count = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    years = conn.execute("SELECT DISTINCT fiscal_year FROM chunks ORDER BY fiscal_year").fetchall()
    years_list = [r[0] for r in years]

    logger.info("=== Data Validation ===")
    logger.info("  Chunks: %d", chunk_count)
    logger.info("  Metrics: %d", metric_count)
    logger.info("  Fiscal years: %s", years_list)

    expected_years = {2020, 2021, 2022, 2023, 2024, 2025}
    actual_years = set(years_list)
    missing = expected_years - actual_years
    if missing:
        logger.warning("  MISSING fiscal years: %s", missing)
    else:
        logger.info("  All expected fiscal years present")

    for year in sorted(actual_years):
        count = conn.execute("SELECT COUNT(*) FROM chunks WHERE fiscal_year=?", (year,)).fetchone()[0]
        m_count = conn.execute("SELECT COUNT(*) FROM metrics WHERE fiscal_year=?", (year,)).fetchone()[0]
        logger.info("  FY%d: %d chunks, %d metrics", year, count, m_count)


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    sections = load_raw_data()

    logger.info("--- Step 1: Chunking ---")
    chunks = chunk_sections(sections)

    logger.info("--- Step 2: SQLite + FTS5 ---")
    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)
    insert_chunks(conn, chunks)

    logger.info("--- Step 3: Extract Metrics ---")
    metrics = extract_all_metrics(sections)
    insert_metrics(conn, metrics)

    logger.info("--- Step 4: Validate Data ---")
    validate_data(conn)
    conn.close()

    logger.info("--- Step 5: Save JSONL ---")
    save_chunks_jsonl(chunks)

    logger.info("--- Step 6: Build FAISS Index ---")
    settings = Settings()
    build_faiss_index(chunks, settings.embedding_model)

    logger.info("=== Ingestion complete ===")


if __name__ == "__main__":
    main()
