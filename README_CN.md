# AAPL 10-K 智能分析系统

![Go](https://img.shields.io/badge/Go-1.21-00ADD8?logo=go&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3-4FC08D?logo=vuedotjs&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-FTS5-003B57?logo=sqlite&logoColor=white)
![FAISS](https://img.shields.io/badge/FAISS-IndexFlatIP-FF6F00)
![ECharts](https://img.shields.io/badge/ECharts-5-AA344D)
![License](https://img.shields.io/badge/License-MIT-green)

基于 Apple Inc. 2020–2025 财年 SEC 10-K 年报的 **RAG 金融问答与分析系统**。采用 Go 控制面 + Python 数据/模型服务 + Vue 分析师工作台的三服务架构，实现从原始年报到智能分析的端到端管线。

> **核心理念**：确定性计算绝不交给 LLM —— 财务指标从结构化数据中提取，LLM 只负责基于已确认数值的分析解读。

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
- **修改 LLM 提示词不触碰检索逻辑；修改前端 UI 不影响 API 契约**

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
- **可配置**：在 `.env` 中设置 `EMBEDDING_MODEL` / `RERANKER_MODEL`，支持 HuggingFace Hub ID 或本地路径

## RAG 管线深度解析

系统采用 **确定性编排的五步 RAG 管线**，每一步都有明确的设计意图：

```
用户问题
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ ① 规则分类器（Go）                                          │
│    关键词 + 年份正则 → narrative / metric / comparative      │
│    设计意图：零延迟、零成本、100% 可解释                      │
│    Fail-closed：不确定时默认走最完整的 narrative 管线         │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ ② 双路并行检索                                              │
│    ┌─────────────┐  ┌──────────────────────┐                │
│    │ FTS5 (BM25) │  │ FAISS (BGE 向量化)   │                │
│    │ 本地 SQLite  │  │ Go→Python HTTP 调用   │                │
│    │ ≈1-5ms      │  │ ≈50-200ms            │                │
│    └──────┬──────┘  └──────────┬───────────┘                │
│           └─────────┬──────────┘                            │
│                     ▼                                       │
│ ③ RRF 融合：倒数排名融合（k=60）                             │
│    设计意图：不依赖分数可比性，合并 lexical 与 semantic 两路   │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ ④ 交叉编码器重排序（BGE-reranker-base）                      │
│    对候选文档逐对精排，比双编码器精度更高                      │
│    降级策略：模型未就绪时跳过重排，直接用 RRF 结果截断        │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ ⑤ LLM 生成（SSE 流式输出）                                  │
│    证据以 <evidence> XML 标签注入 prompt                     │
│    要求 [Evidence N] 格式标注引用 → 后验过滤 citations        │
│    降级策略：生成失败 → 返回检索证据 + 固定提示，而非空白     │
└─────────────────────────────────────────────────────────────┘
```

### 三种查询类型

| 类型 | 示例 | 分类依据 | 处理管线 |
|------|------|----------|----------|
| **叙述型** | "Apple 的主要风险因素有哪些？" | 默认（fail-closed） | FTS5 + FAISS → RRF → 重排序 → LLM |
| **数值型** | "2025 年净营收是多少？" | 包含指标关键词 + 单一年份 | 结构化数据 + 检索 → LLM |
| **比较型** | "对比 2020 和 2025 的毛利率" | 包含对比关键词 或 ≥2 个年份 | 多年检索 → pandas 趋势计算 → LLM |

### 渐进式降级策略

系统在每一层都有独立的降级机制，确保 **即使部分组件失败也能返回有价值的信息**：

| 故障场景 | 降级行为 |
|---------|---------|
| FTS 查询失败 | 仅靠向量检索结果，不整体失败 |
| 向量检索不可用 | 仅靠 FTS 结果 |
| Reranker 未就绪 | 跳过重排，用 RRF 融合列表截断返回 |
| LLM 生成失败 | 返回检索到的原始证据 + 说明文案 + `confidence: low` |
| 引用格式解析失败 | fail-open：展示全部证据（宁可多展示也不漏掉） |
| 模型加载中 | `/health` 返回 `warming_up`，前端显示加载横幅 |

## 核心特性

### 多轮对话问答

- 现代聊天式 UI，完整对话历史
- 上下文感知的追问 —— 对话历史（最近 6 轮）传递给 LLM，实现连贯的多轮对话
- 新对话欢迎页展示推荐问题卡片，涵盖 10-K 常见分析场景
- Markdown 渲染答案，支持表格、列表、强调等富文本格式

### 参数化报告生成

五种内置报告模板，支持可配置参数：

| 报告类型 | 可配置参数 |
|---------|-----------|
| **年度财务摘要** | 财年范围、包含指标（营收、盈利、现金流、每股指标） |
| **CAN SLIM 分析** | 财年范围、分析深度（摘要 / 详细） |
| **风险因素分析** | 财年范围、风险类别（市场、供应链、监管、竞争、宏观） |
| **研发创新分析** | 财年范围、分析深度 |
| **多年趋势分析** | 财年范围、对比指标 |

- 参数动态配置 LLM 提示词，实现定向分析
- ECharts 趋势图内嵌到生成的报告中
- **PDF 导出**：将报告下载为多页 PDF 文档，包含图表、KPI 卡片和分析文本

### 金融数据准确性保障

- **确定性指标**：营收、利润率、EPS 来自结构化 SQLite 表 —— 非 LLM 生成
- **38 项指标 × 6 个财年**：从利润表、资产负债表、现金流量表中提取
- **同比增长 & CAGR**：使用 pandas 精确计算，非语言模型近似
- **完整可追溯性**：每个答案引用具体 chunk，标注财年和章节来源

### 双语支持（EN / 中文）

- 侧边栏一键切换语言
- 完整 UI 本地化（按钮、标签、推荐问题、报告模板）
- LLM 回复跟随所选语言 —— 中文界面自动产出中文答案

### 分析师工作台 UI

- 对话标签页：多轮对话 + 内嵌 ECharts 可视化
- 报告标签页：模板选择 → 参数配置 → 生成报告的完整工作流
- 证据面板：可展开的引用卡片（标注来源财年和章节）
- 调试面板：展示检索管线指标（FTS 命中数、稠密命中数、重排分数、延迟）
- 实时系统健康状态指示器

## 快速开始

### 前置条件

- Docker & Docker Compose
- （可选）Ollama 并拉取 `qwen2.5:7b` 模型用于本地 LLM 生成

### 一键启动

```bash
# 1. 克隆并进入项目
git clone https://github.com/YuehaoDai/WO_challenge.git && cd WO_challenge

# 2.（可选）配置 LLM 和模型 —— 编辑 .env
cp .env.example .env
# 编辑 .env 设置 LLM_PROVIDER=openai 和 API 密钥
# 也可设置 EMBEDDING_MODEL / RERANKER_MODEL 为本地路径以支持离线使用

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

> 端口可通过 `.env` 配置（`FRONTEND_PORT`、`GO_BACKEND_PORT`、`PYTHON_SERVICE_PORT`）。

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

## 数据管线

```
aapl_10k.json（164 个章节）
    │
    ├── 分块器：段落感知切分 + 重叠 → 665 个 chunk
    │   • 短段落整块保留；长段落按段合并 + 重叠
    │   • 三大报表（利润表/资产负债表/现金流量表）整段不拆，避免表格断裂
    │
    ├── SQLite：chunks 表 + FTS5 全文索引（BM25 + Porter 词干）
    │
    ├── 指标提取：解析空格对齐表格 → 228 项指标（38 × 6 年）
    │   • 统一 metric_name 映射
    │   • 费用类取绝对值归一化
    │   • 幂等设计：INSERT OR REPLACE
    │
    └── FAISS：BGE-small-en-v1.5 向量化 + L2 归一化 → 665 个向量（dim=384, IndexFlatIP）
```

### 可用指标

| 类别 | 指标 |
|------|------|
| 营收 | net_sales, cost_of_sales, gross_profit |
| 盈利能力 | operating_income, net_income, income_before_tax |
| 每股收益 | eps_basic, eps_diluted |
| 费用 | rd_expense, sga_expense, operating_expenses |
| 资产负债表 | total_assets, total_liabilities, total_equity, cash_and_equivalents |
| 现金流 | operating_cash_flow, capex, dividends_paid, share_repurchases |

## API 接口

### POST /api/v1/ask
主问答接口。自动分类查询、检索证据、生成答案。支持通过 `history` 字段传入多轮对话历史。

```json
{
  "question": "What was Apple's net revenue in 2025?",
  "symbol": "AAPL",
  "top_k": 5,
  "lang": "zh",
  "history": [
    { "role": "user", "content": "告诉我 Apple 的营收情况" },
    { "role": "assistant", "content": "Apple 的净销售额..." }
  ]
}
```

返回包含 `query_type`、`answer`、`citations[]`、`confidence` 和 `debug` 指标（各阶段耗时、命中数等）。

### GET /api/v1/trends?metric=net_sales&start_year=2020&end_year=2025
金融趋势数据，含同比变化和 CAGR（pandas 精确计算）。

### GET /api/v1/metrics?metric=net_income&year=2025
结构化财务指标的时间点查询。

### GET /api/v1/sections
可用财年及 10-K 章节元数据。

### GET /api/v1/system/status
系统健康状态：服务连通性、模型就绪状态、数据统计、可用财年。

## 已知局限与演进路径

### 当前局限

| 局限 | 说明 | 改进方向 |
|------|------|----------|
| **规则分类器** | 基于关键词匹配，复杂查询可能误判 | 引入 LLM function calling 让模型自主选择工具 |
| **Rerank 性能** | 交叉编码器在 CPU/Docker 下较慢（实测 ~23s） | 减少传入文档数 / GPU 加速 / 轻量 reranker |
| **无 Agent 编排** | 确定性管线，无法处理多步推理 | 引入 LangGraph 状态图支持循环与反思 |
| **单公司** | 当前仅支持 AAPL | 架构已预留 `symbol` 字段，扩展成本低 |
| **FTS 与 Dense 串行** | Go 侧两路检索未并行执行 | 用 goroutine 并行化，检索阶段可减少 30-50% |

### 演进路径

**短期优化**：
- FTS 与 Dense 并行化（Go goroutine）
- Rerank 前截断候选文档数量，减少推理量
- 给 `hybrid.go` 各子步骤加计时日志，精确定位瓶颈

**中期升级**：
- 引入 function calling：让 LLM 自主选择 `query_metrics`、`query_trends`、`search_10k` 工具
- 用 structured outputs 替代正则解析引用索引
- 查询 embedding 缓存，减少重复推理

**机构级扩展**（1000+ 家公司）：
- SQLite → PostgreSQL（水平扩展）
- FAISS → Milvus（分布式向量检索，按行业分 collection）
- 增加 Redis 缓存层应对高频指标查询
- 引入 Agentic RAG：Planning Agent 分解任务 + Data Agent 检索 + Analysis Agent 综合分析

## William O'Neil + Co. 适配

本系统针对机构级金融研究设计：

- **CAN SLIM 感知**：指标覆盖稀释后 EPS、营收增长、股东权益回报率 —— CAN SLIM 筛选核心指标。内置 CAN SLIM 专项报告模板
- **循证分析**：每个答案追溯至具体 10-K 章节，满足机构研究的审计追踪要求
- **报表精度**：结构化指标提取 + pandas 精确计算，确保分析师工作流的数值准确性
- **多年趋势分析**：内置 CAGR 和同比计算，支持机构选股的基本面分析方法论
- **可扩展架构**：控制面/数据面分离支撑机构级数据处理量

## 项目结构

```
WO_challenge/
├── go-backend/              # Go API 网关（Gin）
│   ├── cmd/server/          # 入口
│   └── internal/
│       ├── classifier/      # 基于规则的查询分类（fail-closed → narrative）
│       ├── config/          # YAML 配置加载
│       ├── dto/             # 请求/响应类型（Schema 边界校验）
│       ├── handler/         # HTTP 处理器（SSE 流式代理）
│       ├── modelclient/     # Python 服务 HTTP 客户端
│       ├── retrieval/       # FTS5 + 混合检索 + RRF 融合
│       └── service/         # Ask 管线编排 + 降级逻辑
├── python-service/          # Python 模型服务（FastAPI）
│   └── app/
│       ├── main.py          # FastAPI 应用 & 路由（模型异步后台加载）
│       ├── embedding.py     # BGE 向量化（SentenceTransformer）
│       ├── rerank.py        # BGE 交叉编码器（含未加载时降级）
│       ├── generate.py      # LLM 生成（AsyncOpenAI 统一客户端）
│       ├── search.py        # FAISS 检索 + 结构化指标/趋势查询
│       ├── schemas.py       # Pydantic 模型（extra=forbid, fail-closed）
│       └── config.py        # 配置管理（pydantic-settings v2）
├── frontend/                # Vue 3 + Vite + ECharts
│   └── src/
│       ├── App.vue          # 对话 + 报告 UI（含 i18n）
│       ├── api/client.ts    # 类型化 API 客户端（axios + fetch SSE）
│       └── main.ts          # 入口
├── scripts/                 # 数据管线（幂等设计）
│   ├── ingest.py            # 主管线（分块 → SQLite → 指标提取 → FAISS）
│   ├── chunker.py           # 段落感知分块 + 报表保护
│   └── extract_metrics.py   # 财报表格解析器
├── configs/                 # Go 后端配置
│   ├── app.yaml             # Docker 部署配置
│   └── app.local.yaml       # 本地开发配置
├── data/
│   ├── raw/                 # 原始 10-K JSON（single source of truth）
│   └── processed/           # SQLite、FAISS 索引、chunks JSONL（可重建）
├── .env.example             # 环境变量模板
├── docker-compose.yml       # 多服务编排
└── Dockerfile.ingest        # 数据管线容器
```

## 技术栈

| 组件 | 技术 | 选型理由 |
|------|------|----------|
| API 网关 | Go + Gin | 高性能编排，原生 SQLite 支持 |
| 模型服务 | Python + FastAPI | ML 生态，pandas 金融计算 |
| 前端 | Vue 3 + Vite + TypeScript | 响应式 UI，类型安全，快速构建 |
| 可视化 | ECharts 5 | 金融级图表，可内嵌到报告 |
| 向量检索 | FAISS (IndexFlatIP) | 小数据集精确搜索，零基础设施开销 |
| 全文检索 | SQLite FTS5 | BM25 + Porter 词干，零配置 |
| 向量化 | BGE-small-en-v1.5 | 本地模型，384 维，通过 `EMBEDDING_MODEL` 可配置 |
| 重排序 | BGE-reranker-base | 交叉编码器，通过 `RERANKER_MODEL` 可配置 |
| LLM | Ollama / OpenAI 兼容 API | 灵活切换：本地或云端（DashScope、Kimi 等） |
| PDF 导出 | jsPDF + html2canvas | 客户端多页报告生成 |
| 数据库 | SQLite | 嵌入式，单文件，可移植 |
| 容器化 | Docker Compose | 一键部署 |

## 开发过程

本项目使用 **[Cursor](https://cursor.com/)** — 一款 AI 驱动的 IDE 完成开发。整个开发过程是人机协作：作者主导架构设计、技术决策和质量把控，Cursor 辅助代码生成和实现。

### 本人（作者）做了什么

- **系统架构设计**：定义三服务分离架构（Go 控制面 + Python 数据面 + Vue 前端），设计五步 RAG 管线拓扑（分类 → 双路检索 → RRF → 重排 → 生成），为每个技术选型提供明确理由
- **需求与领域分析**：研究 10-K 年报结构，识别三种查询类型（叙述型 / 数值型 / 比较型），设计财务指标提取 schema（38 项指标 × 6 个财年），针对 William O'Neil 的 CAN SLIM 方法论进行定制
- **工程哲学建立**：确立 fail-closed 默认行为、渐进式降级策略、Schema 边界校验（`extra=forbid`）、结构化数据与 LLM 叙述分离等核心原则
- **提示词工程与 LLM 调优**：为不同查询类型和语言设计 system prompt，用 `<evidence>` XML 标签隔离上下文，调整检索参数（top_k、RRF k、rerank 阈值），迭代调试 LLM 输出质量
- **调试与生产加固**：诊断跨服务问题（pydantic-settings v2 配置加载 bug、Go HTTP 客户端超时级联、Docker 健康检查竞态条件），增强可观测性（DebugInfo 各阶段耗时），根据真实 LLM 延迟调整超时配置
- **性能分析**：通过实际运行日志定位瓶颈（交叉编码器 rerank 占请求总时间 ~52%），识别 FTS/Dense 串行执行等优化空间
- **质量保障与迭代**：审查所有生成代码，发现并纠正问题（深色主题不可读、死配置文件、缺失的 i18n 键），基于实际测试推动多轮改进

### Cursor（AI）做了什么

- 根据架构规格生成 Go、Python、Vue/TypeScript 的实现代码
- 搭建脚手架代码（Dockerfile、API schema、Pydantic 模型、Gin handler）
- 实现具体功能（ECharts 集成、PDF 导出、warm-up 横幅、i18n 系统）
- 执行重构任务（UI 重设计、主题切换、多轮对话支持）
- 协助调试：为服务添加观测日志并分析输出

### 反思

AI 辅助开发极大地加速了实现过程 —— 整个可运行系统在约 48 小时内完成。然而，关键的差异化因素仍然在人：**架构决策**决定了长期可维护性，**领域知识**塑造了系统的实际功能，**工程哲学**（fail-closed、渐进式降级）保障了生产级可靠性。AI 擅长将清晰的意图转化为代码；人的职责是精准地提供这种意图，并不懈地验证输出结果。
