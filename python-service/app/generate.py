"""LLM generation service. Supports Ollama (local) and OpenAI-compatible APIs."""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

import httpx
from openai import AsyncOpenAI

from .config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def init_client() -> None:
    global _client
    settings = get_settings()

    if settings.llm_provider == "openai":
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    else:
        _client = AsyncOpenAI(
            api_key="ollama",
            base_url=f"{settings.ollama_base_url}/v1",
        )
    logger.info("LLM client initialized: provider=%s", settings.llm_provider)


def _get_model() -> str:
    settings = get_settings()
    if settings.llm_provider == "openai":
        return settings.openai_model
    return settings.ollama_model


def _build_system_prompt(query_type: str) -> str:
    base = (
        "You are a financial research analyst assistant specializing in SEC 10-K filings analysis "
        "for Apple Inc. (AAPL). You provide grounded, evidence-based answers using ONLY the "
        "provided context from 10-K filings.\n\n"
        "Rules:\n"
        "- Base every claim on the provided evidence. Never fabricate data.\n"
        "- Use precise financial terminology (net sales, diluted EPS, gross margin, etc.).\n"
        "- When citing numbers, specify the fiscal year and source section.\n"
        "- If the context is insufficient, say so explicitly rather than guessing.\n"
        "- Keep answers concise and professional.\n"
    )

    if query_type == "metric":
        base += (
            "\nFor financial metrics questions:\n"
            "- Present numbers clearly with proper formatting.\n"
            "- Include year-over-year comparisons when data is available.\n"
            "- Explain the significance of the metric in context.\n"
        )
    elif query_type in ("comparative", "report"):
        base += (
            "\nFor comparative/report questions:\n"
            "- Structure your answer with clear sections.\n"
            "- Highlight key differences across years.\n"
            "- Identify trends and patterns.\n"
            "- Support each point with specific evidence from the filings.\n"
        )

    return base


def _build_user_prompt(question: str, context: list[dict]) -> str:
    evidence_parts = []
    for i, chunk in enumerate(context, 1):
        fy = chunk.get("fiscal_year", "N/A")
        section = chunk.get("section_title", "N/A")
        text = chunk.get("text", "")
        evidence_parts.append(
            f"[Evidence {i}] FY{fy} | {section}\n{text}"
        )

    evidence_block = "\n\n---\n\n".join(evidence_parts)

    return (
        f"Based on the following evidence from Apple's 10-K filings, answer the question.\n\n"
        f"<evidence>\n{evidence_block}\n</evidence>\n\n"
        f"Question: {question}"
    )


async def generate(question: str, context: list[dict], query_type: str = "narrative") -> dict:
    """Generate a grounded answer using LLM."""
    if _client is None:
        init_client()

    model = _get_model()
    settings = get_settings()
    system_prompt = _build_system_prompt(query_type)
    user_prompt = _build_user_prompt(question, context)

    response = await _client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )

    answer = response.choices[0].message.content or ""

    citations = []
    for chunk in context:
        snippet = chunk.get("text", "")[:200]
        citations.append({
            "chunk_id": chunk.get("id", ""),
            "fiscal_year": chunk.get("fiscal_year", 0),
            "section_title": chunk.get("section_title", ""),
            "snippet": snippet,
        })

    return {
        "answer": answer,
        "citations": citations,
        "model": model,
    }


async def generate_stream(question: str, context: list[dict], query_type: str = "narrative") -> AsyncGenerator[str, None]:
    """Stream-generate a grounded answer using LLM via SSE."""
    if _client is None:
        init_client()

    model = _get_model()
    settings = get_settings()
    system_prompt = _build_system_prompt(query_type)
    user_prompt = _build_user_prompt(question, context)

    stream = await _client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        stream=True,
    )

    citations = []
    for chunk in context:
        snippet = chunk.get("text", "")[:200]
        citations.append({
            "chunk_id": chunk.get("id", ""),
            "fiscal_year": chunk.get("fiscal_year", 0),
            "section_title": chunk.get("section_title", ""),
            "snippet": snippet,
        })

    yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield f"data: {json.dumps({'type': 'token', 'content': delta.content})}\n\n"

    yield f"data: {json.dumps({'type': 'done', 'model': model})}\n\n"
