"""Python Model & Data Service — embedding, rerank, generation, dense search, metrics."""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import get_settings
from .schemas import (
    EmbedRequest, EmbedResponse,
    RerankRequest, RerankResponse,
    DenseSearchRequest, DenseSearchResponse,
    GenerateRequest, GenerateResponse,
    MetricsRequest, MetricsResponse,
    TrendsRequest, TrendsResponse,
    HealthResponse,
)
from . import embedding, rerank, generate, search

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AAPL 10-K Model Service",
    description="Embedding, reranking, generation, dense search, and financial metrics for AAPL 10-K filings.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    import threading

    settings = get_settings()
    logger.info("Starting Python model service (non-blocking)...")

    try:
        generate.init_client()
    except Exception as e:
        logger.error("Failed to init LLM client: %s", e)

    try:
        search.load_faiss_index()
    except Exception as e:
        logger.error("Failed to load FAISS index: %s", e)

    def _load_models():
        try:
            embedding.load_model(settings.embedding_model)
        except Exception as e:
            logger.error("Failed to load embedding model: %s", e)

        try:
            rerank.load_model(settings.reranker_model)
        except Exception as e:
            logger.error("Failed to load reranker model: %s", e)

        logger.info("All ML models loaded. Service fully ready.")

    thread = threading.Thread(target=_load_models, daemon=True)
    thread.start()

    logger.info("Server listening. ML models loading in background...")


@app.get("/health")
async def health():
    settings = get_settings()
    from . import embedding as _emb, rerank as _rr
    models_ready = _emb._model is not None and _rr._model is not None
    return {
        "status": "ok" if models_ready else "warming_up",
        "embedding_model": settings.embedding_model,
        "embedding_ready": _emb._model is not None,
        "reranker_model": settings.reranker_model,
        "reranker_ready": _rr._model is not None,
        "llm_provider": settings.llm_provider,
        "faiss_index_size": search.get_index_size(),
        "db_chunks_count": search.get_db_chunks_count(),
    }


@app.post("/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest):
    try:
        vectors = embedding.encode(req.texts)
        return EmbedResponse(
            embeddings=vectors,
            model=get_settings().embedding_model,
            dimension=embedding.get_dimension(),
        )
    except Exception as e:
        logger.error("Embedding failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rerank", response_model=RerankResponse)
async def rerank_endpoint(req: RerankRequest):
    try:
        results = rerank.rerank(req.query, req.documents, req.top_k)
        return RerankResponse(results=results)
    except Exception as e:
        logger.error("Reranking failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/dense", response_model=DenseSearchResponse)
async def dense_search(req: DenseSearchRequest):
    try:
        results = search.dense_search(req.query, req.top_k, req.filters)
        return DenseSearchResponse(results=results)
    except Exception as e:
        logger.error("Dense search failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate", response_model=GenerateResponse)
async def generate_answer(req: GenerateRequest):
    if req.stream:
        return StreamingResponse(
            generate.generate_stream(req.question, req.context, req.query_type),
            media_type="text/event-stream",
        )
    try:
        result = await generate.generate(req.question, req.context, req.query_type)
        return GenerateResponse(**result)
    except Exception as e:
        logger.error("Generation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/stream")
async def generate_stream(req: GenerateRequest):
    return StreamingResponse(
        generate.generate_stream(req.question, req.context, req.query_type),
        media_type="text/event-stream",
    )


@app.post("/metrics", response_model=MetricsResponse)
async def get_metrics(req: MetricsRequest):
    data = search.query_metrics(req.symbol, req.metric, req.fiscal_year)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {req.symbol}/{req.metric}")
    return MetricsResponse(symbol=req.symbol, metric=req.metric, data=data)


@app.post("/trends", response_model=TrendsResponse)
async def get_trends(req: TrendsRequest):
    result = search.query_trends(req.symbol, req.metric, req.start_year, req.end_year)
    if not result["data"]:
        raise HTTPException(status_code=404, detail=f"No trend data for {req.symbol}/{req.metric}")
    return TrendsResponse(**result)


@app.get("/metrics/available")
async def available_metrics(symbol: str = "AAPL"):
    metrics = search.list_available_metrics(symbol)
    return {"symbol": symbol, "metrics": metrics}
