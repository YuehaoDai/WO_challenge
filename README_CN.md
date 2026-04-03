# AAPL 10-K 智能分析系统

基于 Apple Inc. 2020–2025 财年 SEC 10-K 年报的智能金融问答与分析系统。采用 Go 控制面 + Python 数据/模型服务 + Vue 分析师工作台的三服务架构。

## 架构总览

```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────────────────┐
│  Vue 3       │────▶│  Go API 网关         │────▶│  Python 模型服务        │
│  前端        │◀────│ （控制面）            │◀────│ （数据面）              │
│              │     │                      │     │                         │
│  ECharts     │     │  • 查询分类器         │     │  • BGE 向量化           │
│  分析师 UI   │     │  • FTS5 全文检索      │     │  • BGE 重排序           │
│              │     │  • RRF 融合           │     │  • FAISS 稠密检索       │
│              │     │  • 流程编排           │     │  • LLM 生成             │
│              │     │  • SSE 流式推送       │     │  • 指标/趋势查询        │
└─────────────┘     └──────────────────────┘     └─────────────────────────┘
                              │                              │
                    ┌─────────┴──────────┐         ┌────────┴────────┐
                    │  SQLite + FTS5     │         │  FAISS 索引     │
                    │  chunks / metrics  │         │  665 向量       │
                    └────────────────────┘         └─────────────────┘
```

### 设计决策

**为什么采用 Go + Python 双服务？**
- Go 擅长高并发 HTTP 编排、低延迟 API 网关，且原生支持 SQLite/FTS5
- Python 在 ML 推理（embedding、reranking）、pandas 金融计算和 LLM 客户端方面不可替代
- 职责清晰：Go = 控制面（路由、检索协调），Python = 数据面（模型、计算）

**为什么用 FAISS 而非 Milvus/Pinecone？**
- 数据规模（约 665 个 chunk，6 年 10-K）完全可放入内存
- `IndexFlatIP` 提供精确搜索，无近似误差 —— 对金融准确性至关重要
- 零基础设施开销：单文件落盘，无需外部服务依赖
- 扩展至约 10 万 chunk 前无需 IVF；多公司扩展时再考虑 Milvus

**为什么用 SQLite + FTS5 而非 Elasticsearch/PostgreSQL？**
- 嵌入式数据库，零部署复杂度
- FTS5 提供 BM25 排序 + Porter 词干提取 —— 生产级关键词搜索
- 单个 `app.db` 文件包含 chunk、全文索引和结构化指标
- 项目规模适用；PostgreSQL 升级路径清晰

**为什么用 BGE-small-en-v1.5 + BGE-reranker-base？**
- 本地模型，无 API 费用，数据完全可控
- BGE-small（384 维）在英文金融文本上性价比优秀
- 交叉编码器重排序显著提升相关性（precision@5 提升约 20%）
- 首次运行时通过 HuggingFace 自动下载

## 核心特性

### 三种查询类型

| 类型 | 示例 | 处理管线 |
|------|------|----------|
| **叙述型** | "Apple 的主要风险因素有哪些？" | FTS5 + FAISS → RRF → 重排序 → LLM |
| **数值型** | "2025 年净营收是多少？" | 结构化数据库 + 检索 → LLM |
| **比较型** | "对比 2020 和 2025 的毛利率" | 多年检索 → 趋势计算 → LLM |

### 混合检索管线

1. **查询分类**：基于规则的分类器识别查询类型，提取财年和章节提示
2. **双路检索**：BM25（FTS5）+ 稠密检索（FAISS/BGE）并行执行
3. **RRF 融合**：倒数排名融合合并两路排序结果（k=60）
4. **交叉编码器重排序**：BGE-reranker-base 对候选文档重新打分
5. **LLM 生成**：基于上下文的答案生成，附带引用来源

### 金融数据准确性保障

- **确定性指标**：营收、利润率、EPS 来自结构化 SQLite 表 —— 非 LLM 生成
- **38 项指标 × 6 个财年**：从利润表、资产负债表、现金流量表中提取
- **同比增长 & 复合年增长率**：使用 pandas 精确计算，非语言模型近似
- **完整可追溯性**：每个答案引用具体 chunk，标注财年和章节来源

### 分析师工作台 UI

- 预置分析场景（业务概览、风险因素、营收分析、研发等）
- 证据面板，展示可展开的引用卡片（标注来源财年和章节）
- ECharts 交互式金融趋势图，显示同比变化和 CAGR
- 调试面板，展示检索管线指标（FTS 命中数、稠密命中数、重排分数、延迟）

## 快速开始

### 前置条件

- Docker & Docker Compose
- （可选）Ollama 并拉取 `qwen2.5:7b` 模型用于 LLM 生成

### 一键启动

```bash
# 1. 克隆并进入项目
git clone https://github.com/YuehaoDai/WO_challenge.git && cd WO_challenge

# 2.（可选）配置 LLM —— 编辑 .env 设置 OpenAI API
cp .env.example .env

# 3.（可选）启动 Ollama 并拉取模型
ollama pull qwen2.5:7b

# 4. 启动所有服务
docker-compose up --build

# 首次运行：数据管线处理数据（embedding 约需 2 分钟）
# 后续运行：跳过数据处理，直接启动
```

服务地址：
- **前端界面**：http://localhost:3000
- **Go API 网关**：http://localhost:8080
- **Python 模型服务**：http://localhost:8000

### 本地开发（不使用 Docker）

```bash
# 终端 1：运行数据管线
cd WO_challenge
pip install -r python-service/requirements.txt
python scripts/ingest.py

# 终端 2：启动 Python 服务
cd python-service
DB_PATH=../data/processed/app.db FAISS_INDEX_PATH=../data/processed/faiss \
  uvicorn app.main:app --port 8000

# 终端 3：启动 Go 后端
cd go-backend
CONFIG_PATH=../configs/app.local.yaml CGO_ENABLED=1 go run -tags sqlite_fts5 ./cmd/server/

# 终端 4：启动前端
cd frontend && npm install && npm run dev
```

## API 接口

### POST /api/v1/ask
主问答接口。自动分类查询、检索证据、生成答案。

```json
{
  "question": "What was Apple's net revenue in 2025?",
  "symbol": "AAPL",
  "top_k": 5
}
```

返回包含 `query_type`、`answer`、`citations[]`、`confidence` 和 `debug` 指标。

### GET /api/v1/trends?metric=net_sales&start_year=2020&end_year=2025
金融趋势数据，含同比变化和 CAGR。

### GET /api/v1/metrics?metric=net_income&year=2025
结构化财务指标的时间点查询。

### GET /api/v1/sections
可用财年及 10-K 章节元数据。

### GET /api/v1/system/status
系统健康状态：服务连通性、数据统计、可用财年。

## 数据管线

```
aapl_10k.json（164 个章节）
    │
    ├── 分块器：段落感知切分 + 重叠 → 665 个 chunk
    │
    ├── SQLite：chunks 表 + FTS5 全文索引
    │
    ├── 指标提取：利润表/资产负债表/现金流量表 → 228 项指标（38 × 6 年）
    │
    └── FAISS：BGE-small-en-v1.5 向量化 → 665 个向量（dim=384）
```

### 可用指标

从 10-K 财务报表中结构化提取的指标：

| 类别 | 指标 |
|------|------|
| 营收 | net_sales, cost_of_sales, gross_profit |
| 盈利能力 | operating_income, net_income, income_before_tax |
| 每股收益 | eps_basic, eps_diluted |
| 费用 | rd_expense, sga_expense, operating_expenses |
| 资产负债表 | total_assets, total_liabilities, total_equity, cash_and_equivalents |
| 现金流 | operating_cash_flow, capex, dividends_paid, share_repurchases |

## 多公司扩展

架构设计支持从 AAPL 扩展到多公司：

1. **数据管线**：向 `data/raw/` 添加新 JSON 文件，管线原生支持 `symbol` 字段
2. **SQLite 模式**：所有表包含 `symbol` 列，支持多公司查询
3. **FAISS 索引**：元数据过滤支持按公司检索
4. **API 层**：所有端点支持 `symbol` 参数（默认 AAPL）
5. **前端**：侧边栏可添加公司选择器

机构级部署（1000+ 家公司）升级路径：
- SQLite → PostgreSQL（水平扩展）
- FAISS → Milvus（分布式向量检索，按行业分 collection）
- 增加 Redis 缓存层应对高频指标查询

## William O'Neil + Co. 适配

本系统针对机构级金融研究设计：

- **CAN SLIM 感知**：指标覆盖稀释后 EPS、营收增长、股东权益回报率 —— CAN SLIM 筛选的核心指标
- **循证分析**：每个答案追溯至具体 10-K 章节，满足机构研究的审计追踪要求
- **报表精度**：结构化指标提取确保分析师工作流的数值准确性
- **多年趋势分析**：内置 CAGR 和同比计算，支持机构选股的基本面分析方法论
- **可扩展架构**：控制面/数据面分离支撑机构级数据处理量

## 项目结构

```
WO_challenge/
├── go-backend/              # Go API 网关（Gin）
│   ├── cmd/server/          # 入口
│   └── internal/
│       ├── classifier/      # 基于规则的查询路由
│       ├── config/          # YAML 配置加载
│       ├── dto/             # 请求/响应类型
│       ├── handler/         # HTTP 处理器
│       ├── modelclient/     # Python 服务客户端
│       ├── retrieval/       # FTS5 + 混合检索 + RRF
│       └── service/         # Ask 编排
├── python-service/          # Python 模型服务（FastAPI）
│   └── app/
│       ├── main.py          # FastAPI 应用 & 端点
│       ├── embedding.py     # BGE 向量化
│       ├── rerank.py        # BGE 交叉编码器
│       ├── generate.py      # LLM 生成（Ollama/OpenAI）
│       ├── search.py        # FAISS 检索 + 指标查询
│       ├── schemas.py       # Pydantic 模型
│       └── config.py        # 配置管理
├── frontend/                # Vue 3 + Vite + ECharts
│   └── src/
│       ├── App.vue          # 分析师工作台 UI
│       ├── api/client.ts    # API 客户端
│       └── main.ts          # 入口
├── scripts/                 # 数据管线
│   ├── ingest.py            # 主管线
│   ├── chunker.py           # 智能分块
│   └── extract_metrics.py   # 财报解析器
├── configs/                 # 服务配置
├── data/
│   ├── raw/                 # 原始 10-K JSON
│   └── processed/           # SQLite、FAISS 索引、chunks JSONL
├── docker-compose.yml       # 多服务编排
├── Dockerfile.ingest        # 数据管线容器
└── README.md
```

## 技术栈

| 组件 | 技术 | 选型理由 |
|------|------|----------|
| API 网关 | Go + Gin | 高性能编排，原生 SQLite 支持 |
| 模型服务 | Python + FastAPI | ML 生态，pandas 金融计算 |
| 前端 | Vue 3 + Vite | 响应式 UI，快速构建 |
| 可视化 | ECharts | 金融级图表 |
| 向量检索 | FAISS (IndexFlatIP) | 小数据集精确搜索，零基础设施开销 |
| 全文检索 | SQLite FTS5 | BM25 + Porter 词干，零配置 |
| 向量化 | BGE-small-en-v1.5 | 本地模型，384 维，英文表现优异 |
| 重排序 | BGE-reranker-base | 交叉编码器提升精度 |
| LLM | Ollama / OpenAI API | 灵活切换：本地或云端 |
| 数据库 | SQLite | 嵌入式，单文件，可移植 |
| 容器化 | Docker Compose | 一键部署 |
