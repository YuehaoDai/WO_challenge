"""Pydantic models for request/response validation.

Strict mode: extra fields raise errors (fail-closed at system boundary).
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class EmbedRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    texts: list[str] = Field(..., min_length=1, max_length=128, description="Texts to embed")


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    model: str
    dimension: int


class RerankRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    query: str = Field(..., min_length=1)
    documents: list[dict] = Field(..., min_length=1, description="List of {id, text} dicts")
    top_k: int = Field(default=8, ge=1, le=50)


class RankedDocument(BaseModel):
    id: str
    text: str
    score: float
    rank: int


class RerankResponse(BaseModel):
    results: list[RankedDocument]


class DenseSearchRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=20, ge=1, le=100)
    filters: Optional[dict] = Field(default=None, description="Optional metadata filters: {fiscal_year, section_id}")


class SearchResult(BaseModel):
    chunk_id: str
    score: float
    fiscal_year: int
    section_id: int
    section_title: str
    content: str


class DenseSearchResponse(BaseModel):
    results: list[SearchResult]


class HistoryMessage(BaseModel):
    role: str
    content: str

class GenerateRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    question: str = Field(..., min_length=1)
    context: list[dict] = Field(..., description="List of {id, fiscal_year, section_title, text} evidence chunks")
    query_type: str = Field(default="narrative", description="narrative | metric | comparative | report")
    stream: bool = Field(default=False)
    lang: str = Field(default="en", description="Response language: en | zh")
    history: list[HistoryMessage] = Field(default_factory=list, description="Conversation history for multi-turn")


class Citation(BaseModel):
    chunk_id: str
    fiscal_year: int
    section_title: str
    snippet: str


class GenerateResponse(BaseModel):
    answer: str
    citations: list[Citation]
    model: str


class MetricsRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    symbol: str = Field(default="AAPL")
    metric: str = Field(..., description="Metric name: net_sales, net_income, gross_profit, etc.")
    fiscal_year: Optional[int] = Field(default=None)


class MetricsResponse(BaseModel):
    symbol: str
    metric: str
    data: list[dict]


class TrendsRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    symbol: str = Field(default="AAPL")
    metric: str
    start_year: int = Field(default=2020)
    end_year: int = Field(default=2025)


class TrendPoint(BaseModel):
    fiscal_year: int
    value: float
    yoy_change: Optional[float] = None
    yoy_pct: Optional[float] = None


class TrendsResponse(BaseModel):
    symbol: str
    metric: str
    unit: str
    data: list[TrendPoint]
    cagr: Optional[float] = None


class HealthResponse(BaseModel):
    status: str
    embedding_model: str
    reranker_model: str
    llm_provider: str
    faiss_index_size: int
    db_chunks_count: int
