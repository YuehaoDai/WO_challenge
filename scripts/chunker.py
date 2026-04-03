"""Intelligent chunking for 10-K section texts.

Strategy:
- Short sections (<1500 chars): keep as single chunk
- Long sections: split by paragraph boundaries, target 300-700 tokens (~1200-2800 chars)
  with 100-token (~400 char) overlap
- Financial statement sections: keep tables intact as single chunks
- Each chunk carries full metadata for traceability
"""

import re
import logging

logger = logging.getLogger(__name__)

TARGET_CHUNK_SIZE = 2000
MAX_CHUNK_SIZE = 3000
OVERLAP_SIZE = 400
MIN_CHUNK_SIZE = 200

FINANCIAL_SECTIONS = {
    "Balance Sheet Balance Sheet",
    "Income Statement Income Statement",
    "Cash Flow Statement Cash Flow Statement",
}


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _split_by_paragraphs(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def _merge_small_paragraphs(paragraphs: list[str], target_size: int) -> list[str]:
    """Merge consecutive small paragraphs to approach target size."""
    merged = []
    current = ""

    for para in paragraphs:
        if not current:
            current = para
        elif len(current) + len(para) + 2 <= target_size:
            current = current + "\n\n" + para
        else:
            merged.append(current)
            current = para

    if current:
        merged.append(current)

    return merged


def _create_overlapping_chunks(segments: list[str], overlap_size: int) -> list[str]:
    """Create chunks with overlap from merged segments."""
    if len(segments) <= 1:
        return segments

    chunks = []
    for i, segment in enumerate(segments):
        if i > 0:
            prev = segments[i - 1]
            overlap = prev[-overlap_size:] if len(prev) > overlap_size else prev
            segment = overlap + "\n\n" + segment
        chunks.append(segment)

    return chunks


def chunk_section(section: dict) -> list[dict]:
    """Chunk a single section into one or more chunks with metadata."""
    symbol = section["symbol"]
    fy = section["file_fiscal_year"]
    form_type = section["form_type"]
    section_title = section["section_title"]
    section_id = section["section_id"]
    text = section["section_text"].strip()

    if not text:
        return []

    base_id = f"{symbol}_{fy}_{section_id}"

    if section_title in FINANCIAL_SECTIONS:
        return [{
            "id": f"{base_id}_0",
            "symbol": symbol,
            "fiscal_year": fy,
            "form_type": form_type,
            "section_id": section_id,
            "section_title": section_title,
            "chunk_index": 0,
            "content": text,
            "token_count": _estimate_tokens(text),
        }]

    if len(text) <= TARGET_CHUNK_SIZE:
        return [{
            "id": f"{base_id}_0",
            "symbol": symbol,
            "fiscal_year": fy,
            "form_type": form_type,
            "section_id": section_id,
            "section_title": section_title,
            "chunk_index": 0,
            "content": text,
            "token_count": _estimate_tokens(text),
        }]

    paragraphs = _split_by_paragraphs(text)
    merged = _merge_small_paragraphs(paragraphs, TARGET_CHUNK_SIZE)
    overlapped = _create_overlapping_chunks(merged, OVERLAP_SIZE)

    chunks = []
    for i, chunk_text in enumerate(overlapped):
        if len(chunk_text) < MIN_CHUNK_SIZE and i > 0:
            continue
        chunks.append({
            "id": f"{base_id}_{i}",
            "symbol": symbol,
            "fiscal_year": fy,
            "form_type": form_type,
            "section_id": section_id,
            "section_title": section_title,
            "chunk_index": i,
            "content": chunk_text,
            "token_count": _estimate_tokens(chunk_text),
        })

    return chunks


def chunk_sections(sections: list[dict]) -> list[dict]:
    """Chunk all sections and return flat list of chunks."""
    all_chunks = []
    for section in sections:
        chunks = chunk_section(section)
        all_chunks.extend(chunks)

    logger.info(
        "Chunked %d sections into %d chunks (avg %.0f chars/chunk)",
        len(sections),
        len(all_chunks),
        sum(len(c["content"]) for c in all_chunks) / max(len(all_chunks), 1),
    )

    return all_chunks
