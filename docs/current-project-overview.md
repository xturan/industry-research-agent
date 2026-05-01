# 当前项目说明

## 项目定位

`invest_agent` 是一个生产导向的行业智能与研究辅助系统，核心目标是围绕行业报告、政策/公告/数据源、证据链、研究工作流、多 agent 协作和多渠道内容生成，搭建一套可审计、可扩展、可验证的 AI 应用基础设施。

项目定位是：

- 行业情报系统
- 证据驱动研究助手
- 多 agent 研究与内容生产工作台
- 国内外来源采集、解析、归一化、证据构建和下游内容生产的工程骨架

项目明确不定位为直接证券投资建议系统。所有结论都应能追溯到证据来源。

## 当前技术栈

主要技术选择：

- 后端语言：Python
- API 框架：FastAPI
- 数据库：PostgreSQL 优先，测试/本地路径兼容 SQLite
- 向量检索方向：pgvector
- 缓存/任务状态方向：Redis
- 任务执行：异步 task queue + worker
- ORM / migration：SQLAlchemy + Alembic
- LLM provider：当前支持 mock 和 DeepSeek provider 路径
- 本地运行：Makefile + Docker Compose
- 测试：pytest
- 代码质量：ruff

## 单仓结构

主要目录：

| 路径 | 作用 |
| --- | --- |
| `apps/api` | FastAPI API 服务 |
| `apps/worker` | 异步任务 worker |
| `packages/core` | 配置、日志、运行日志等基础设施 |
| `packages/db` | SQLAlchemy 模型、会话、迁移 |
| `packages/ingestion` | 文件/URL 摄取、解析、切块、持久化 |
| `packages/rag` | 检索与 evidence bundle 构建 |
| `packages/agents` | deterministic multi-agent research workflow |
| `packages/providers` | LLM provider 抽象与 DeepSeek client |
| `packages/sources` | source contracts、routing、profiles、collectors、domestic source 能力 |
| `packages/content` | 多平台内容生成层 |
| `packages/delivery` | 内容交付、审批、导出、dispatch |
| `packages/tasks` | 任务队列、worker claim/execute/retry/idempotency |
| `packages/memory` | 记忆抽取、搜索、反馈 |
| `packages/evals` | deterministic eval 与 smoke runner |
| `packages/policy` | 研究/内容/交付 policy guardrails |
| `packages/registry` | 模板、策略、style pack 注册 |
| `packages/ops` | readiness、recent failures、ops visibility |
| `tests` | API、服务、source、task、eval 等测试 |
| `.agent/PLANS` | 长任务 PLAN |
| `.agent/STATUS.md` | 当前项目状态和 handoff |
| `.codex/agents` | 当前 6 个项目 subagents |
| `docs` | 项目文档 |

## 核心工作流

### 1. 摄取与检索

典型路径：

```text
文件/URL
  -> ingestion parser
  -> document/chunk 持久化
  -> chunk retrieval
  -> evidence bundle
```

目标是保证每个研究结论都能追溯到 document、chunk、citation 和证据引用。

### 2. Source-Assisted Research

source-assisted path 负责在研究前先进行来源路由、检索、详情抓取、证据抽取和 evidence bundle 构建。

典型路径：

```text
ResearchAnalyzeRequest
  -> source route
  -> source search
  -> fetch detail
  -> extract evidence
  -> build source evidence bundle
  -> convert to RAG evidence bundle
  -> multi-agent research workflow
```

当前国内源方向正在从“大量站点内搜索/列表维护”收敛为更轻的混合架构：

```text
User Query
  -> Query Decomposer
  -> Tiaokuai Router / Source Strategy
     -> Search-Assisted Path
        -> Tavily Search Discovery
        -> Crawl4AI Page Fetch and Extraction
        -> Normalizer
     -> Direct Structured Path
        -> disclosure/query/data adapters
        -> Normalizer
  -> Evidence Bundle
  -> Research Workflow
```

### 3. Multi-Agent Research

研究工作流位于 `packages/agents`，当前核心阶段包括：

- supervisor intake
- thesis builder
- opponent
- evidence judge
- risk analyst
- synthesize memo

研究输出会持久化为 `Run` 和 `RunStep`，用于审计和问题定位。

### 4. 内容生产与交付

研究结果可以进入内容工厂：

```text
research run / research memo
  -> content factory
  -> platform-specific content assets
  -> delivery job
  -> review / approve
  -> dispatch / export
```

支持的内容方向包括文章、小红书、短视频脚本等多平台资产形态。

### 5. 异步任务

当前任务系统支持：

- research analyze task
- content generate task
- delivery dispatch task

任务路径包括：

```text
enqueue
  -> task persistence
  -> worker claim
  -> handler execute
  -> succeeded / retry / dead_letter
```

任务系统强调 idempotency、retry、failure structure 和可审计状态。

## 当前 active PLAN

当前 active PLAN：

```text
.agent/PLANS/domestic-source-lite-refactor-v1.md
```

当前阶段：

```text
Phase 5: Query-Based Usability Eval and Cost Review
```

当前焦点：

- 国内源轻量化重构已经完成 query decomposition、Tavily search discovery、Crawl4AI extraction、search-assisted domestic orchestration 的核心合同验证。
- Phase 4 已完成。
- Phase 5 关注查询级可用性评估和 Tavily credit/cost review。
- 当前要求 Phase 5 限定在 scripts、artifacts、tests、docs 范围内。
- 如果需要修改 `packages/sources/**` 或其他生产代码，应视为 blocker 并重新打开 PLAN。

Phase 5 重点验证维度：

- coverage
- evidence sufficiency
- source relevance
- failure transparency
- latency
- estimated Tavily credits

## 当前运行日志能力

系统已经加入 compact runtime log：

```text
SYSTEM_RUN_LOG_ENABLED=true
SYSTEM_RUN_LOG_DIR=data/run_logs
SYSTEM_RUN_LOG_MAX_VALUE_CHARS=240
SYSTEM_RUN_LOG_MAX_ITEMS=8
```

日志文件按 UTC 时间和任务名命名，例如：

```text
20260426T010203Z_research-analyze_run-42.jsonl
```

日志记录：

- input 摘要
- decision 摘要
- output 摘要
- error 摘要

日志会屏蔽 secret/token/password/api_key/reasoning 字段，并把重文本字段压缩为 `{chars, preview}`，避免 token 和存储膨胀。

## 当前质量状态

最近已通过的关键检查包括：

- source-layer focused tests
- domestic source focused tests
- search-assisted domestic tests
- query decomposition tests
- Crawl4AI extraction tests
- task/content/delivery/research 相关回归测试
- compact runtime log tests

已知限制：

- `python -m ruff check .` 目前仍会被既有 `data/tmp` scratch/demo scripts 的 import ordering、UP009、E501 等问题阻断。
- 这些 `data/tmp` 问题被记录为 repo-wide limitation，不属于当前核心生产代码路径。

## 项目约束

重要保护对象：

- EvidenceBundle schema
- EvidenceItem citation fields
- `source_quality_summary`
- research analyze response shape
- task/job status semantics
- run/run_steps meaning
- content asset metadata contract
- delivery state transition behavior

除非 PLAN 明确授权，否则不能静默修改这些契约。

## 推荐工作方式

当前项目遵循 PLAN-driven 执行方式：

1. 选择或创建 active PLAN。
2. `invest_project_director` 先把真实场景验证计划写入 PLAN。
3. Group 2 执行架构或代码任务。
4. Group 3 做代码质量和真实功能验证。
5. PLAN 完成后由 `invest_project_summarizer` 总结，并评估是否需要更新 worker 能力。

当用户说“开始实施PLAN”或等价表达时，应自动触发该 v2 subagent 工作流。
