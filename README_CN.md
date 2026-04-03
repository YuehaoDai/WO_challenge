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
- **可配置**：在 `.env` 中设置 `EMBEDDING_MODEL` / `RERANKER_MODEL`，支持 HuggingFace Hub ID 或本地路径，适用于离线部署或自定义模型（参见 `.env.example`）

## 核心特性

### 多轮对话问答

- 现代聊天式 UI，完整对话历史
- 上下文感知的追问 —— 对话历史传递给 LLM，实现连贯的多轮对话
- 新对话欢迎页展示推荐问题卡片，涵盖 10-K 常见分析场景
- Markdown 渲染答案，支持表格、列表、强调等富文本格式

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
- **同比增长 & 复合年增长率**：使用 pandas 精确计算，非语言模型近似
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

- **CAN SLIM 感知**：指标覆盖稀释后 EPS、营收增长、股东权益回报率 —— CAN SLIM 筛选核心指标。内置 CAN SLIM 专项报告模板
- **循证分析**：每个答案追溯至具体 10-K 章节，满足机构研究的审计追踪要求
- **报表精度**：结构化指标提取确保分析师工作流的数值准确性
- **多年趋势分析**：内置 CAGR 和同比计算，支持机构选股的基本面分析方法论
- **可扩展架构**：控制面/数据面分离支撑机构级数据处理量
- **报告生成**：参数化报告模板（年度摘要、CAN SLIM、风险因素、研发、趋势）支持 PDF 导出，满足分析师交付需求

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
│       └── config.py        # 配置管理（pydantic-settings v2）
├── frontend/                # Vue 3 + Vite + ECharts
│   └── src/
│       ├── App.vue          # 对话 + 报告 UI（含 i18n）
│       ├── api/client.ts    # 类型化 API 客户端
│       └── main.ts          # 入口
├── scripts/                 # 数据管线
│   ├── ingest.py            # 主管线
│   ├── chunker.py           # 智能分块
│   └── extract_metrics.py   # 财报解析器
├── configs/                 # Go 后端配置
│   ├── app.yaml             # Docker 部署配置
│   └── app.local.yaml       # 本地开发配置
├── .cursor/rules/           # Cursor AI 编码规范
├── data/
│   ├── raw/                 # 原始 10-K JSON
│   └── processed/           # SQLite、FAISS 索引、chunks JSONL
├── .env.example             # 环境变量模板
├── docker-compose.yml       # 多服务编排
├── Dockerfile.ingest        # 数据管线容器
├── README.md                # English documentation
└── README_CN.md             # 中文文档
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

- **系统架构设计**：定义三服务分离架构（Go 控制面 + Python 数据面 + Vue 前端），选择 RAG 管线拓扑，并为每个技术选型提供明确理由（FAISS 而非 Milvus、SQLite FTS5 而非 Elasticsearch 等）
- **需求与领域分析**：研究 10-K 年报结构，识别三种查询类型（叙述型 / 数值型 / 比较型），设计财务指标提取 schema（38 项指标 × 6 个财年），并针对 William O'Neil + Co. 的 CAN SLIM 方法论进行定制
- **提示词工程与 LLM 调优**：为不同查询类型和语言设计 system prompt，调整检索参数（top_k、RRF k、rerank 阈值），迭代调试 LLM 输出质量（如通过增加上下文 chunk 数量解决"数据缺失"问题）
- **UI/UX 方向把控**：定义聊天式交互模式，设计参数化报告模板系统，选择浅色主题以保证可读性，指导 OpenClaw 风格的设计美学
- **调试与生产加固**：诊断跨服务问题（pydantic-settings v2 配置加载 bug、Go HTTP 客户端超时级联、Docker 健康检查竞态条件），增强可观测性，根据真实 LLM 延迟调整超时配置
- **质量保障与迭代**：审查所有生成代码，发现并纠正问题（深色主题不可读、死配置文件、缺失的 i18n 键），基于实际测试推动多轮改进
- **DevOps 与交付**：使用 conventional commits 管理 git 历史，构建 Docker Compose 部署方案，维护中英文文档同步

### Cursor（AI）做了什么

- 根据架构规格生成 Go、Python、Vue/TypeScript 的实现代码
- 搭建脚手架代码（Dockerfile、API schema、Pydantic 模型、Gin handler）
- 实现具体功能（ECharts 集成、PDF 导出、warm-up 横幅、i18n 系统）
- 执行重构任务（UI 重设计、主题切换、多轮对话支持）
- 协助调试：为服务添加观测日志并分析输出

### 反思

AI 辅助开发极大地加速了实现过程 —— 整个可运行系统在约 48 小时内完成。然而，关键的差异化因素仍然在人：**架构决策**决定了长期可维护性，**领域知识**塑造了系统的实际功能，**审美判断**能捕捉到"看起来不对"或"用起来不好"的问题。AI 擅长将清晰的意图转化为代码；人的职责是精准地提供这种意图，并不懈地验证输出结果。
