# AAPL 10-K Intelligence

![Go](https://img.shields.io/badge/Go-1.21-00ADD8?logo=go&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3-4FC08D?logo=vuedotjs&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-FTS5-003B57?logo=sqlite&logoColor=white)
![FAISS](https://img.shields.io/badge/FAISS-IndexFlatIP-FF6F00)
![ECharts](https://img.shields.io/badge/ECharts-5-AA344D)
![License](https://img.shields.io/badge/License-MIT-green)

A **RAG-powered financial Q&A and analysis system** for Apple Inc.'s SEC 10-K filings (FY2020–2025). Built with a Go control plane, Python data/model service, and Vue analyst workstation — delivering an end-to-end pipeline from raw filings to intelligent analysis.

> **Core principle**: Deterministic calculations never go through the LLM — financial metrics are extracted from structured data; the LLM only interprets pre-verified numbers.

## Architecture Overview

```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────────────────┐
│  Vue 3       │────▶│  Go API Gateway      │────▶│  Python Model Service   │
│  Frontend    │◀────│  (Control Plane)     │◀────│  (Data Plane)           │
│              │     │                      │     │                         │
│  ECharts     │     │  • Query Classifier  │     │  • BGE Embedding        │
│  Analyst UI  │     │  • FTS5 Search       │     │  • BGE Reranker         │
│              │     │  • RRF Fusion        │     │  • FAISS Dense Search   │
│              │     │  • Orchestration     │     │  • LLM Generation       │
│              │     │  • SSE Streaming     │     │  • Metrics/Trends       │
└─────────────┘     └──────────────────────┘     └─────────────────────────┘
                              │                              │
                    ┌─────────┴──────────┐         ┌────────┴────────┐
                    │  SQLite + FTS5     │         │  FAISS Index    │
                    │  chunks / metrics  │         │  665 vectors    │
                    └────────────────────┘         └─────────────────┘
```

### Design Rationale

**Why Go + Python dual-service?**
- Go excels at concurrent HTTP orchestration, low-latency API gateway, and has native SQLite/FTS5 support
- Python is indispensable for ML inference (embedding, reranking), pandas-based financial calculations, and LLM client libraries
- Clear separation: Go = control plane (routing, retrieval coordination), Python = data plane (models, computation)
- **Modifying LLM prompts never touches retrieval logic; modifying the UI never affects the API contract**

**Why FAISS over Milvus/Pinecone?**
- Dataset size (~665 chunks from 6 years of 10-K) fits entirely in memory
- `IndexFlatIP` provides exact search with no approximation error — critical for financial accuracy
- Zero infrastructure overhead: single file on disk, no external service dependency
- Scales to ~100K+ chunks before requiring IVF; Milvus becomes relevant for multi-company expansion

**Why SQLite + FTS5 over Elasticsearch/PostgreSQL?**
- Embedded database with zero deployment complexity
- FTS5 provides BM25 ranking with Porter stemming — production-quality keyword search
- Single `app.db` file contains chunks, FTS index, and structured metrics
- Perfect for this project's scope; PostgreSQL upgrade path is straightforward

**Why BGE-small-en-v1.5 + BGE-reranker-base?**
- Local models, no API costs, full data sovereignty
- BGE-small (384 dim) offers excellent quality-to-size ratio for English financial text
- Cross-encoder reranker significantly improves relevance (precision@5 boost of ~20%)
- **Configurable**: set `EMBEDDING_MODEL` / `RERANKER_MODEL` in `.env` to any HuggingFace Hub ID or local path

## RAG Pipeline Deep Dive

The system uses a **deterministically orchestrated 5-step RAG pipeline**, where each step has a clear design intent:

```
User Question
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ ① Rule-Based Classifier (Go)                               │
│    Keywords + year regex → narrative / metric / comparative  │
│    Design intent: zero latency, zero cost, 100% explainable │
│    Fail-closed: defaults to the most thorough narrative path │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ ② Dual Retrieval                                            │
│    ┌─────────────┐  ┌──────────────────────┐                │
│    │ FTS5 (BM25) │  │ FAISS (BGE embed)    │                │
│    │ Local SQLite │  │ Go→Python HTTP call  │                │
│    │ ≈1-5ms      │  │ ≈50-200ms            │                │
│    └──────┬──────┘  └──────────┬───────────┘                │
│           └─────────┬──────────┘                            │
│                     ▼                                       │
│ ③ RRF Fusion: Reciprocal Rank Fusion (k=60)                │
│    Design intent: merges lexical & semantic without          │
│    requiring score normalization                             │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ ④ Cross-Encoder Reranking (BGE-reranker-base)               │
│    Pairwise scoring for higher precision than bi-encoders   │
│    Fallback: skips reranking if model not ready, uses RRF   │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ ⑤ LLM Generation (SSE streaming)                           │
│    Evidence injected via <evidence> XML tags in prompt       │
│    [Evidence N] citation format → post-hoc citation filter   │
│    Fallback: on failure, returns raw evidence + notice       │
└─────────────────────────────────────────────────────────────┘
```

### Three Query Types

| Type | Example | Classification Rule | Pipeline |
|------|---------|---------------------|----------|
| **Narrative** | "What are Apple's key risk factors?" | Default (fail-closed) | FTS5 + FAISS → RRF → Rerank → LLM |
| **Metric** | "What was net revenue in 2025?" | Metric keywords + single year | Structured DB + Retrieval → LLM |
| **Comparative** | "Compare gross margin 2020 vs 2025" | Comparison keywords or ≥2 years | Multi-year retrieval → pandas trend calc → LLM |

### Progressive Degradation Strategy

Every layer has independent fallback mechanisms, ensuring the system **always returns useful information** even when components fail:

| Failure Scenario | Degradation Behavior |
|-----------------|---------------------|
| FTS query fails | Dense results only; does not abort |
| Dense search unavailable | FTS results only |
| Reranker not ready | Skips reranking, truncates RRF fusion list |
| LLM generation fails | Returns raw evidence chunks + notice + `confidence: low` |
| Citation parsing fails | Fail-open: shows all evidence (prefers over-showing to missing) |
| Models still loading | `/health` returns `warming_up`; frontend shows loading banner |

## Key Features

### Multi-Turn Conversational Q&A

- Modern chat-style UI with conversation history
- Context-aware follow-up questions — last 6 turns of history passed to LLM for coherent dialogue
- Recommended question cards on welcome screen, tailored to 10-K analysis scenarios
- Markdown-rendered answers with rich formatting (tables, lists, emphasis)

### Parameterized Report Generation

Five built-in report templates with configurable parameters:

| Report | Configurable Parameters |
|--------|------------------------|
| **Annual Financial Summary** | Fiscal year range, metrics to include (revenue, profitability, cash flow, per-share) |
| **CAN SLIM Analysis** | Fiscal year range, analysis depth (summary / detailed) |
| **Risk Factor Analysis** | Fiscal year range, risk categories (market, supply chain, regulatory, competitive, macro) |
| **R&D Innovation Analysis** | Fiscal year range, analysis depth |
| **Multi-Year Trend Analysis** | Fiscal year range, comparison metrics |

- Parameters configure the LLM prompt dynamically for targeted analysis
- ECharts trend charts embedded inline in generated reports
- **PDF export**: download reports as multi-page PDF documents with charts, KPI cards, and analysis text

### Financial Data Integrity

- **Deterministic metrics**: Revenue, margins, EPS from structured SQLite tables — not LLM-generated
- **38 metrics × 6 years**: Extracted from Income Statement, Balance Sheet, Cash Flow
- **YoY & CAGR**: Calculated with pandas, not approximated by language models
- **Full traceability**: Every answer cites specific chunks with fiscal year and section

### Bilingual Support (EN / 中文)

- One-click language toggle in the sidebar
- Full UI localization (buttons, labels, recommended questions, report templates)
- LLM responses follow the selected language — Chinese UI produces Chinese answers

### Analyst Workstation UI

- Chat tab with multi-turn conversation and inline ECharts visualizations
- Report tab with template selection → parameter configuration → generation workflow
- Evidence panel with expandable citation cards showing source fiscal year and section
- Debug panel showing retrieval pipeline metrics (FTS hits, dense hits, rerank scores, latency)
- Real-time system health indicator

## Quick Start

### Prerequisites

- Docker & Docker Compose
- (Optional) Ollama with `qwen2.5:7b` model for local LLM generation

### One-Click Launch

```bash
# 1. Clone and enter the project
git clone https://github.com/YuehaoDai/WO_challenge.git && cd WO_challenge

# 2. (Optional) Configure LLM and models — edit .env
cp .env.example .env
# Edit .env to set LLM_PROVIDER=openai and your API key
# You can also set EMBEDDING_MODEL / RERANKER_MODEL to a local path for offline use

# 3. (Optional) Start Ollama with a model
ollama pull qwen2.5:7b

# 4. Launch all services
docker-compose up --build

# First run: ingestion pipeline processes data (~2 min for embeddings)
# Subsequent runs: skips ingestion, starts immediately
```

Services will be available at:
- **Frontend**: http://localhost:3000
- **Go API**: http://localhost:8080
- **Python Service**: http://localhost:8000

> Ports are configurable via `.env` (`FRONTEND_PORT`, `GO_BACKEND_PORT`, `PYTHON_SERVICE_PORT`).

### Local Development (without Docker)

```bash
# Terminal 1: Run ingestion
cd WO_challenge
pip install -r python-service/requirements.txt
python scripts/ingest.py

# Terminal 2: Start Python service
cd python-service
DB_PATH=../data/processed/app.db FAISS_INDEX_PATH=../data/processed/faiss \
  uvicorn app.main:app --port 8000

# Terminal 3: Start Go backend
cd go-backend
CONFIG_PATH=../configs/app.local.yaml CGO_ENABLED=1 go run -tags sqlite_fts5 ./cmd/server/

# Terminal 4: Start frontend
cd frontend && npm install && npm run dev
```

## Data Pipeline

```
aapl_10k.json (164 sections)
    │
    ├── Chunker: paragraph-aware splitting with overlap → 665 chunks
    │   • Short paragraphs kept whole; long ones merged with overlap
    │   • Financial statements (Income/Balance/Cash Flow) never split to preserve tables
    │
    ├── SQLite: chunks table + FTS5 full-text index (BM25 + Porter stemming)
    │
    ├── Metrics Extractor: space-aligned table parsing → 228 metrics (38 × 6 years)
    │   • Unified metric_name mapping
    │   • Expense normalization (absolute values)
    │   • Idempotent design: INSERT OR REPLACE
    │
    └── FAISS: BGE-small-en-v1.5 embeddings + L2 normalization → 665 vectors (dim=384, IndexFlatIP)
```

### Available Metrics

| Category | Metrics |
|----------|---------|
| Revenue | net_sales, cost_of_sales, gross_profit |
| Profitability | operating_income, net_income, income_before_tax |
| Per Share | eps_basic, eps_diluted |
| Expenses | rd_expense, sga_expense, operating_expenses |
| Balance Sheet | total_assets, total_liabilities, total_equity, cash_and_equivalents |
| Cash Flow | operating_cash_flow, capex, dividends_paid, share_repurchases |

## API Reference

### POST /api/v1/ask
Main Q&A endpoint. Classifies query, retrieves evidence, generates answer. Supports multi-turn conversation via `history` field.

```json
{
  "question": "What was Apple's net revenue in 2025?",
  "symbol": "AAPL",
  "top_k": 5,
  "lang": "en",
  "history": [
    { "role": "user", "content": "Tell me about Apple's revenue" },
    { "role": "assistant", "content": "Apple's net sales..." }
  ]
}
```

Response includes `query_type`, `answer`, `citations[]`, `confidence`, and `debug` metrics (per-stage latency, hit counts, etc.).

### GET /api/v1/trends?metric=net_sales&start_year=2020&end_year=2025
Financial trend data with YoY changes and CAGR (calculated via pandas).

### GET /api/v1/metrics?metric=net_income&year=2025
Point-in-time financial metrics from structured data.

### GET /api/v1/sections
Available fiscal years and 10-K section metadata.

### GET /api/v1/system/status
System health: service connectivity, model readiness, data counts, available fiscal years.

## Known Limitations & Evolution Path

### Current Limitations

| Limitation | Description | Improvement Direction |
|-----------|-------------|----------------------|
| **Rule-based classifier** | Keyword matching; may misclassify complex queries | Introduce LLM function calling for autonomous tool selection |
| **Rerank performance** | Cross-encoder is slow on CPU/Docker (~23s measured) | Reduce input document count / GPU acceleration / lighter reranker |
| **No agent orchestration** | Deterministic pipeline; cannot handle multi-step reasoning | Introduce LangGraph state graphs for loops and reflection |
| **Single company** | Currently AAPL only | Architecture already reserves `symbol` field; low extension cost |
| **FTS & Dense sequential** | Go-side dual retrieval not parallelized | Parallelize with goroutines for 30-50% retrieval speedup |

### Evolution Path

**Short-term optimizations**:
- Parallelize FTS and Dense search with Go goroutines
- Truncate candidate documents before reranking to reduce inference load
- Add per-step timing logs in `hybrid.go` for precise bottleneck profiling

**Medium-term upgrades**:
- Introduce function calling: let the LLM autonomously choose `query_metrics`, `query_trends`, `search_10k` tools
- Replace regex citation parsing with structured outputs
- Query embedding cache to avoid redundant inference

**Institutional-scale extension** (1000+ companies):
- SQLite → PostgreSQL (horizontal scaling)
- FAISS → Milvus (distributed vector search with collection-per-sector)
- Add Redis caching layer for frequently queried metrics
- Introduce Agentic RAG: Planning Agent for task decomposition + Data Agent for retrieval + Analysis Agent for synthesis

## William O'Neil + Co. Relevance

This system is designed with institutional financial research in mind:

- **CAN SLIM Awareness**: Metrics include EPS (diluted), revenue growth, and return on equity — key CAN SLIM screening criteria. A dedicated CAN SLIM report template provides structured analysis
- **Evidence-Based Analysis**: Every answer traces back to specific 10-K sections, matching the audit trail expectations of institutional research
- **Financial Statement Precision**: Structured metric extraction + pandas calculations ensure numerical accuracy for analyst workflows
- **Multi-Year Trend Analysis**: Built-in CAGR and YoY calculations support the fundamental analysis methodology used in institutional stock selection
- **Scalable Architecture**: Control plane / data plane separation supports the volume requirements of institutional data processing

## Project Structure

```
WO_challenge/
├── go-backend/              # Go API gateway (Gin)
│   ├── cmd/server/          # Entry point
│   └── internal/
│       ├── classifier/      # Rule-based query classification (fail-closed → narrative)
│       ├── config/          # YAML config loader
│       ├── dto/             # Request/response types (schema boundary validation)
│       ├── handler/         # HTTP handlers (SSE stream proxy)
│       ├── modelclient/     # Python service HTTP client
│       ├── retrieval/       # FTS5 + Hybrid search + RRF fusion
│       └── service/         # Ask pipeline orchestration + degradation logic
├── python-service/          # Python model service (FastAPI)
│   └── app/
│       ├── main.py          # FastAPI app & routes (async background model loading)
│       ├── embedding.py     # BGE embedding (SentenceTransformer)
│       ├── rerank.py        # BGE cross-encoder (with not-ready fallback)
│       ├── generate.py      # LLM generation (AsyncOpenAI unified client)
│       ├── search.py        # FAISS search + structured metrics/trends queries
│       ├── schemas.py       # Pydantic models (extra=forbid, fail-closed)
│       └── config.py        # Settings (pydantic-settings v2)
├── frontend/                # Vue 3 + Vite + ECharts
│   └── src/
│       ├── App.vue          # Chat + Report UI with i18n
│       ├── api/client.ts    # Typed API client (axios + fetch SSE)
│       └── main.ts          # Entry point
├── scripts/                 # Data ingestion pipeline (idempotent)
│   ├── ingest.py            # Master pipeline (chunk → SQLite → metrics → FAISS)
│   ├── chunker.py           # Paragraph-aware chunking + statement protection
│   └── extract_metrics.py   # Financial statement table parser
├── configs/                 # Go backend configuration
│   ├── app.yaml             # Docker deployment config
│   └── app.local.yaml       # Local development config
├── data/
│   ├── raw/                 # Source 10-K JSON (single source of truth)
│   └── processed/           # SQLite, FAISS index, chunks JSONL (rebuildable)
├── .env.example             # Environment variable template
├── docker-compose.yml       # Multi-service orchestration
└── Dockerfile.ingest        # Ingestion container
```

## Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| API Gateway | Go + Gin | High-performance orchestration, native SQLite |
| Model Service | Python + FastAPI | ML ecosystem, pandas for calculations |
| Frontend | Vue 3 + Vite + TypeScript | Reactive UI, type safety, fast builds |
| Visualization | ECharts 5 | Financial-grade charting, inline in reports |
| Vector Search | FAISS (IndexFlatIP) | Exact search for small dataset, no infra overhead |
| Full-Text Search | SQLite FTS5 | BM25 with Porter stemming, zero-config |
| Embeddings | BGE-small-en-v1.5 | Local, 384-dim, configurable via `EMBEDDING_MODEL` |
| Reranker | BGE-reranker-base | Cross-encoder, configurable via `RERANKER_MODEL` |
| LLM | Ollama / OpenAI-compatible API | Flexible: local or cloud (DashScope, Kimi, etc.) |
| PDF Export | jsPDF + html2canvas | Client-side multi-page report generation |
| Database | SQLite | Embedded, single-file, portable |
| Containerization | Docker Compose | One-click deployment |

## Development Process

This project was built with **[Cursor](https://cursor.com/)** — an AI-powered IDE. The development process was a human-AI collaboration where the author directed architecture, design decisions, and quality control while Cursor assisted with code generation and implementation.

### What I (the author) did

- **System Architecture Design**: Defined the three-service separation (Go control plane + Python data plane + Vue frontend), designed the 5-step RAG pipeline topology (classify → dual retrieval → RRF → rerank → generate), and provided clear rationale for each technology choice
- **Requirements & Domain Analysis**: Studied the 10-K filing structure, identified the three query types (narrative / metric / comparative), designed the financial metrics extraction schema (38 metrics × 6 fiscal years), and tailored the system for William O'Neil's CAN SLIM methodology
- **Engineering Philosophy**: Established fail-closed default behaviors, progressive degradation strategies, schema boundary validation (`extra=forbid`), and the principle of separating structured data from LLM narration
- **Prompt Engineering & LLM Tuning**: Designed system prompts for different query types and languages, used `<evidence>` XML tags to isolate context, tuned retrieval parameters (top_k, RRF k, rerank thresholds), and iteratively debugged LLM output quality
- **Debugging & Production Hardening**: Diagnosed cross-service issues (pydantic-settings v2 config loading bug, Go HTTP client timeout cascades, Docker healthcheck race conditions), increased observability (DebugInfo per-stage timing), and tuned timeouts for real-world LLM latency
- **Performance Analysis**: Identified bottlenecks through production logs (cross-encoder reranking accounts for ~52% of request time), recognized FTS/Dense sequential execution as an optimization opportunity
- **Quality Assurance & Iteration**: Reviewed all generated code, caught and corrected issues (unreadable dark theme, dead config files, missing i18n keys), and drove multiple rounds of refinement based on hands-on testing

### What Cursor (AI) did

- Generated implementation code across Go, Python, and Vue/TypeScript based on architectural specifications
- Scaffolded boilerplate (Dockerfiles, API schemas, Pydantic models, Gin handlers)
- Implemented detailed features (ECharts integration, PDF export, warm-up banner, i18n system)
- Executed refactoring tasks (UI redesign, theme switch, multi-turn conversation support)
- Assisted with debugging by instrumenting services and analyzing log output

### Reflection

AI-assisted development dramatically accelerated implementation — the working system was built in roughly 48 hours. However, the critical differentiators remain human: **architecture decisions** that determine long-term maintainability, **domain knowledge** that shapes what the system actually does, and **engineering philosophy** (fail-closed, progressive degradation) that ensures production-grade reliability. The AI excels at translating well-specified intent into code; the human's job is to provide that intent with precision and to validate the output relentlessly.
