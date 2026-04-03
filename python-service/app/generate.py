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


def _build_system_prompt(query_type: str, lang: str = "en") -> str:
    if lang == "zh":
        base = (
            "你是一名专业的金融研究分析师助手，专注于 Apple Inc.（AAPL）的 SEC 10-K 年报分析。"
            "你基于提供的 10-K 年报证据给出有据可查的回答。\n\n"
            "规则：\n"
            "- 每个论点都必须基于提供的证据，绝不编造数据。\n"
            "- 使用精确的金融术语（净营收、稀释每股收益、毛利率等）。\n"
            "- 引用数字时，标明对应的财年和来源章节。\n"
            "- 如果证据不足，请明确说明而非猜测。\n"
            "- 回答须简明专业。\n"
            "- 使用 Markdown 格式组织回答（标题、列表、加粗等）。\n"
            "- **必须使用中文回答。**\n"
        )
    else:
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
            "- Use Markdown formatting to structure your answer (headings, lists, bold, etc.).\n"
        )

    if query_type == "metric":
        if lang == "zh":
            base += (
                "\n针对财务指标类问题：\n"
                "- 清晰展示数字，使用合适的格式。\n"
                "- 在数据可用时进行同比对比。\n"
                "- 解释该指标在上下文中的意义。\n"
            )
        else:
            base += (
                "\nFor financial metrics questions:\n"
                "- Present numbers clearly with proper formatting.\n"
                "- Include year-over-year comparisons when data is available.\n"
                "- Explain the significance of the metric in context.\n"
            )
    elif query_type in ("comparative", "report"):
        if lang == "zh":
            base += (
                "\n针对比较/报告类问题：\n"
                "- 使用清晰的章节结构组织回答。\n"
                "- 重点突出不同年份之间的关键差异。\n"
                "- 识别趋势和模式。\n"
                "- 用年报中的具体证据支撑每个观点。\n"
            )
        else:
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


def _build_messages(system_prompt: str, user_prompt: str, history: list | None = None) -> list[dict]:
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for h in history[-6:]:
            role = h.role if hasattr(h, 'role') else h.get('role', 'user')
            content = h.content if hasattr(h, 'content') else h.get('content', '')
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_prompt})
    return messages


async def generate(question: str, context: list[dict], query_type: str = "narrative", lang: str = "en", history: list | None = None) -> dict:
    """Generate a grounded answer using LLM."""
    if _client is None:
        init_client()

    model = _get_model()
    settings = get_settings()
    system_prompt = _build_system_prompt(query_type, lang)
    user_prompt = _build_user_prompt(question, context)

    response = await _client.chat.completions.create(
        model=model,
        messages=_build_messages(system_prompt, user_prompt, history),
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


async def generate_stream(question: str, context: list[dict], query_type: str = "narrative", lang: str = "en", history: list | None = None) -> AsyncGenerator[str, None]:
    """Stream-generate a grounded answer using LLM via SSE."""
    if _client is None:
        init_client()

    model = _get_model()
    settings = get_settings()
    system_prompt = _build_system_prompt(query_type, lang)
    user_prompt = _build_user_prompt(question, context)

    stream = await _client.chat.completions.create(
        model=model,
        messages=_build_messages(system_prompt, user_prompt, history),
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
