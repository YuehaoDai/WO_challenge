# AAPL 10-K Intelligence

An intelligent financial Q&A and analysis system for Apple Inc.'s SEC 10-K filings (FY2020–2025). Built with a Go control plane, Python data/model service, and Vue analyst workstation frontend.

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
- Python is indispensable for ML model inference (embedding, reranking), pandas-based financial calculations, and LLM client libraries
- Clear separation: Go = control plane (routing, retrieval coordination), Python = data plane (models, computation)

**Why FAISS over Milvus/Pinecone?**
- Dataset size (~665 chunks from 6 years of 10-K) fits entirely in memory
- `IndexFlatIP` provides exact search with no approximation error — critical for financial accuracy
- Zero infrastructure overhead: single file on disk, no external service dependency
- Scales to ~100K+ chunks before requiring IVF. For multi-company expansion, Milvus becomes relevant

**Why SQLite + FTS5 over Elasticsearch/PostgreSQL?**
- Embedded database with zero deployment complexity
- FTS5 provides BM25 ranking with Porter stemming — production-quality keyword search
- Single `app.db` file contains chunks, FTS index, and structured metrics
- Perfect for interview-scope projects; PostgreSQL upgrade path is straightforward

**Why BGE-small-en-v1.5 + BGE-reranker-base?**
- Local models, no API costs, full data sovereignty
- BGE-small (384 dim) offers excellent quality-to-size ratio for English financial text
- Cross-encoder reranker significantly improves relevance (precision@5 boost of ~20%)
- Models auto-download on first run via HuggingFace

## Key Features

### Three Query Types

| Type | Example | Pipeline |
|------|---------|----------|
| **Narrative** | "What are Apple's key risk factors?" | FTS5 + FAISS → RRF → Rerank → LLM |
| **Metric** | "What was net revenue in 2025?" | Structured DB + Retrieval → LLM |
| **Comparative** | "Compare gross margin 2020 vs 2025" | Multi-year retrieval → Trend calc → LLM |

### Hybrid Retrieval Pipeline

1. **Query Classification**: Rule-based classifier detects query type, extracts fiscal years and section hints
2. **Dual Retrieval**: BM25 (FTS5) + Dense (FAISS/BGE) search in parallel
3. **RRF Fusion**: Reciprocal Rank Fusion merges both ranked lists (k=60)
4. **Cross-Encoder Reranking**: BGE-reranker-base re-scores top candidates
5. **LLM Generation**: Context-grounded answer with citations

### Financial Data Integrity

- **Deterministic metrics**: Revenue, margins, EPS from structured SQLite tables — not LLM-generated
- **38 metrics × 6 years**: Extracted from Income Statement, Balance Sheet, Cash Flow
- **YoY & CAGR**: Calculated with pandas, not approximated by language models
- **Full traceability**: Every answer cites specific chunks with fiscal year and section

### Analyst Workstation UI

- Pre-built analysis scenarios (Business Overview, Risk Factors, Revenue Analysis, etc.)
- Evidence panel with expandable citation cards showing source fiscal year and section
- ECharts interactive financial trend charts with YoY and CAGR display
- Debug panel showing retrieval pipeline metrics (FTS hits, dense hits, rerank scores, latency)

## Quick Start

### Prerequisites

- Docker & Docker Compose
- (Optional) Ollama with `qwen2.5:7b` model for LLM generation

### One-Click Launch

```bash
# 1. Clone and enter the project
git clone <repo-url> && cd WO_challenge

# 2. (Optional) Configure LLM — edit .env for OpenAI API
cp .env.example .env

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

## API Reference

### POST /api/v1/ask
Main Q&A endpoint. Classifies query, retrieves evidence, generates answer.

```json
{
  "question": "What was Apple's net revenue in 2025?",
  "symbol": "AAPL",
  "top_k": 5
}
```

Response includes `query_type`, `answer`, `citations[]`, `confidence`, and `debug` metrics.

### GET /api/v1/trends?metric=net_sales&start_year=2020&end_year=2025
Financial trend data with YoY changes and CAGR.

### GET /api/v1/metrics?metric=net_income&year=2025
Point-in-time financial metrics from structured data.

### GET /api/v1/sections
Available fiscal years and 10-K section metadata.

### GET /api/v1/system/status
System health: service connectivity, data counts, available fiscal years.

## Data Pipeline

```
aapl_10k.json (164 sections)
    │
    ├── Chunker: paragraph-aware splitting with overlap → 665 chunks
    │
    ├── SQLite: chunks table + FTS5 full-text index
    │
    ├── Metrics Extractor: Income/Balance/Cash Flow → 228 metrics (38 × 6 years)
    │
    └── FAISS: BGE-small-en-v1.5 embeddings → 665 vectors (dim=384)
```

### Available Metrics

Financial metrics extracted from structured 10-K statements:

| Category | Metrics |
|----------|---------|
| Revenue | net_sales, cost_of_sales, gross_profit |
| Profitability | operating_income, net_income, income_before_tax |
| Per Share | eps_basic, eps_diluted |
| Expenses | rd_expense, sga_expense, operating_expenses |
| Balance Sheet | total_assets, total_liabilities, total_equity, cash_and_equivalents |
| Cash Flow | operating_cash_flow, capex, dividends_paid, share_repurchases |

## Multi-Company Extension

The architecture is designed for extension beyond AAPL:

1. **Data ingestion**: Add new JSON files to `data/raw/`, the pipeline handles `symbol` field natively
2. **SQLite schema**: All tables include `symbol` column for multi-company queries
3. **FAISS index**: Metadata filtering supports per-company search
4. **API layer**: `symbol` parameter on all endpoints (defaults to AAPL)
5. **Frontend**: Symbol selector can be added to sidebar

For institutional-scale deployment (1000+ companies), upgrade path:
- SQLite → PostgreSQL (horizontal scaling)
- FAISS → Milvus (distributed vector search with collection-per-sector)
- Add Redis caching layer for frequently queried metrics

## William O'Neil + Co. Relevance

This system is designed with institutional financial research in mind:

- **CAN SLIM Awareness**: Metrics include EPS (diluted), revenue growth, and return on equity — key CAN SLIM screening criteria
- **Evidence-Based Analysis**: Every answer traces back to specific 10-K sections, matching the audit trail expectations of institutional research
- **Financial Statement Precision**: Structured metric extraction ensures numerical accuracy for analyst workflows
- **Multi-Year Trend Analysis**: Built-in CAGR and YoY calculations support the fundamental analysis methodology used in institutional stock selection
- **Scalable Architecture**: Control plane / data plane separation supports the volume requirements of institutional data processing

## Project Structure

```
WO_challenge/
├── go-backend/              # Go API gateway (Gin)
│   ├── cmd/server/          # Entry point
│   └── internal/
│       ├── classifier/      # Rule-based query routing
│       ├── config/          # YAML config loader
│       ├── dto/             # Request/response types
│       ├── handler/         # HTTP handlers
│       ├── modelclient/     # Python service client
│       ├── retrieval/       # FTS5 + Hybrid + RRF
│       └── service/         # Ask orchestration
├── python-service/          # Python model service (FastAPI)
│   └── app/
│       ├── main.py          # FastAPI app & endpoints
│       ├── embedding.py     # BGE embedding
│       ├── rerank.py        # BGE cross-encoder
│       ├── generate.py      # LLM generation (Ollama/OpenAI)
│       ├── search.py        # FAISS search + metrics queries
│       ├── schemas.py       # Pydantic models
│       └── config.py        # Settings management
├── frontend/                # Vue 3 + Vite + ECharts
│   └── src/
│       ├── App.vue          # Analyst workstation UI
│       ├── api/client.ts    # API client
│       └── main.ts          # Entry point
├── scripts/                 # Data ingestion pipeline
│   ├── ingest.py            # Master pipeline
│   ├── chunker.py           # Intelligent chunking
│   └── extract_metrics.py   # Financial statement parser
├── configs/                 # Service configuration
├── data/
│   ├── raw/                 # Source 10-K JSON
│   └── processed/           # SQLite, FAISS index, chunks JSONL
├── docker-compose.yml       # Multi-service orchestration
├── Dockerfile.ingest        # Ingestion container
└── README.md
```

## Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| API Gateway | Go + Gin | High-performance orchestration, native SQLite |
| Model Service | Python + FastAPI | ML ecosystem, pandas for calculations |
| Frontend | Vue 3 + Vite | Reactive UI, fast builds |
| Visualization | ECharts | Financial-grade charting |
| Vector Search | FAISS (IndexFlatIP) | Exact search for small dataset, no infra overhead |
| Full-Text Search | SQLite FTS5 | BM25 with Porter stemming, zero-config |
| Embeddings | BGE-small-en-v1.5 | Local, 384-dim, strong English performance |
| Reranker | BGE-reranker-base | Cross-encoder for precision boost |
| LLM | Ollama / OpenAI API | Flexible: local or cloud |
| Database | SQLite | Embedded, single-file, portable |
| Containerization | Docker Compose | One-click deployment |
