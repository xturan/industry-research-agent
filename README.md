# Industry Research Agent

生产导向的中文产业调研 Agent：把一个产业问题转换为可执行的研究计划，完成来源发现、网页抓取、证据构建、质量审查和多章节报告生成。

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Workflow-LangGraph-6B46C1)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-2ea44f)](LICENSE)

> 本项目定位为行业情报、产业研究和内容生产辅助系统，不构成证券投资建议。

## 这个项目解决什么问题

普通搜索通常只能返回一组网页，难以回答产业研究真正关心的几个问题：

- 当前结论对应哪些一手来源？
- 政策是否已经转化为项目、采购、企业披露或统计变化？
- 哪些维度已有证据，哪些维度仍然缺失？
- 来源质量、证据强度和报告表述是否匹配？

Industry Research Agent 将研究过程拆成可审计的链路：

    研究问题
      -> 意图识别与维度规划
      -> 多路来源发现与抓取
      -> 文档解析、切块与来源评级
      -> Evidence Bundle 与 Claim 构建
      -> 报告撰写、对手审查、逐条验证
      -> 质量门禁与最终报告

每条重要判断都尽量关联到 Claim、Evidence、Source 和引用定位；证据不足时降低结论强度，并将缺口显式保留在报告中。

## 生成结果

仓库内提供了可直接打开的示例报告：

| 主题 | 示例 | 内容规模 |
|---|---|---:|
| 低空经济 | [中标公告深度研究报告](examples/reports/低空经济中标公告深度研究报告.html) | 约 3 万字 / 142 条证据 |
| 动力电池 | [动力电池产业链调研](examples/reports/动力电池产业链调研.html) | 约 3 万字 / 69 条证据 |
| 智能网联汽车 | [智能网联汽车产业链调研](examples/reports/智能网联汽车产业链调研.html) | 约 1.9 万字 / 44 条证据 |
| 合肥低空经济 | [市级产业调研](examples/reports/合肥低空经济产业调研.html) | 约 2.5 万字 / 93 条证据 |

报告包含执行摘要、研究口径、分维度分析、风险与不确定性、证据引用和来源说明，而不是只输出搜索结果或结论列表。

## 核心能力

### 研究框架

- 固定的产业研究维度框架，覆盖政策、市场、产业链、供需、技术、项目、企业、资本、区域、风险和趋势等维度。
- Query 分解为多个研究维度和证据义务，避免用一个搜索词覆盖所有问题。
- 对地方问题保留省、市、县级粒度，并显式记录上级来源兜底和本级证据缺口。

### 来源与检索

- AnySearch 作为当前搜索发现主 provider，Tavily 可作为 fallback。
- DeepSeek 参与复杂 Query 的意图识别、检索规划和报告生成。
- Crawl4AI 负责网页正文、Markdown、附件和出链抽取。
- 对政策、项目/招采、统计/财政、上市公司披露、环评/土地等来源族进行分类、路由和质量评级。
- 对结构化披露、统计和查询平台保留专用 adapter，不把所有来源退化为通用网页搜索。

### 证据与报告

- Source Quality 与 Evidence Strength 分离但联动：来源权威性不能直接替代证据对具体 Claim 的支撑强度。
- Evidence Bundle 保留 Source、时间、地域、Source Family、Citation、限制条件和支持类型。
- Editor1 生成可读报告，Editor2 进行对手审查，Evidence Judge 验证 Claim 支持关系。
- Chief Gate 根据覆盖度、引用完整性、来源多样性、风险和证据缺口决定通过、补证据、重写或人工审核。

### 运行可靠性

- Capability Gateway 为搜索和 LLM provider 提供路由、fallback、并发预算、电路熔断和遥测。
- 每次 provider attempt 可记录 run 归因、延迟、token/result 用量和 fallback 状态。
- LangGraph checkpoint、运行 dossier 和报告 artifact 支持中断恢复与过程审计。

## 架构

![系统架构图](docs/assets/architecture.png)

    FastAPI / Async Tasks
            |
            v
    LangGraph Research Workflow
      Planner -> Source Hunter -> Parser -> Source Quality
          -> Evidence Builder -> Claim Builder
          -> Editor1 -> Editor2 -> Verifier -> Chief Gate
            |
            +--> add evidence / revise / human review
            |
            v
    Final Report + Dossier + Checkpoint + Telemetry

主要模块：

| 模块 | 职责 |
|---|---|
| apps/api | FastAPI API 入口 |
| apps/worker | 异步任务执行与重试 |
| packages/research_harness | LangGraph 研究流程、证据链和报告生成 |
| packages/sources | 来源 taxonomy、路由、搜索、抓取和国内来源适配 |
| packages/providers | DeepSeek、搜索 provider 和统一调用抽象 |
| packages/rag | Chunk 检索、粗排和精排接口 |
| packages/capability_gateway | provider 路由、预算、熔断和遥测 |
| packages/content | 将研究结果转成多平台内容资产 |
| packages/memory | 运行记忆、主题记忆和反馈记忆 |
| packages/evals | 研究、来源和策略评测 |
| docs | 技术路线、来源协议、工作流和评测文档 |

## 快速开始

### 1. 安装依赖

    make install

### 2. 配置 provider

    Copy-Item .env.example .env

按需填写：

    # 报告与规划模型
    DEEPSEEK_API_KEY=your_deepseek_api_key_here
    DEEPSEEK_RESEARCH_MODEL=deepseek-chat

    # 搜索发现：AnySearch 主 provider，Tavily fallback
    SEARCH_DISCOVERY_PROVIDER=anysearch
    SEARCH_DISCOVERY_FALLBACK_PROVIDER=tavily
    ANYSEARCH_API_KEY=your_anysearch_api_key_here
    TAVILY_API_KEY=your_tavily_api_key_here

    # 本地精排，可选；未启用时使用确定性精排
    RERANK_ENDPOINT=http://localhost:11434/v1/chat/completions
    RERANK_MODEL=invest-rerank-v6

安全默认值是 LLM_PROVIDER=mock。只有明确配置 key 并选择 live/LLM 模式时，才会调用外部模型。

### 3. 启动本地服务

    make up
    make dev-api

如需启用本地 Ollama 精排：

    ollama pull qwen2.5:3b-instruct
    cd data/rerank_cloud_train/output/ollama_rerank_v6_qwen25_3b
    ollama create invest-rerank-v6 -f Modelfile

### 4. 发起一次研究

    $body = @{
      query = "安徽低空经济的政策、项目落地与产业链发展如何"
      top_k = 6
      mode = "llm"
      provider = "deepseek"
      enable_thinking = $false
    } | ConvertTo-Json

    Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/research/analyze" -ContentType "application/json" -Body $body

查看完整嵌套返回时使用：

    $response | ConvertTo-Json -Depth 100

## 关键 API

| Endpoint | 用途 |
|---|---|
| POST /research/analyze | 执行研究分析和报告生成 |
| GET /research/runs/{run_id} | 查看运行状态和步骤输出 |
| POST /ingest/url | 抓取并入库网页来源 |
| POST /search/chunks | 按 Chunk 检索来源内容 |
| POST /search/evidence-bundle | 构建可审计 Evidence Bundle |
| POST /tasks/research/analyze | 异步提交研究任务 |
| GET /tasks/{task_id} | 查看异步任务状态 |
| GET /gateway/health | 查看 provider 网关健康度 |
| GET /gateway/providers | 查看 provider 成功率、延迟、限流和 fallback |
| GET /ops/sources/performance | 查看来源性能和路由表现 |

## Provider 网关

需要统一治理搜索和 LLM 请求时，在 .env 中启用：

    CAPABILITY_GATEWAY_ENABLED=true
    CAPABILITY_GATEWAY_SEARCH_MODE=gateway
    CAPABILITY_GATEWAY_LLM_MODE=gateway

网关负责：

- provider 路由和 fallback；
- 并发预算与跨进程 lease；
- 连续失败熔断与恢复探测；
- attempt 级遥测、token/result 用量和 run 归因；
- PostgreSQL、Redis、SQLite/InProcess 三类运行环境的状态存储适配。

## 验证

常用验证命令：

    make test
    make lint
    make compose-config
    make research-demo
    make evals-smoke-demo

来源层专项验证：

    pytest -q tests/test_sources_layer.py
    pytest -q tests/test_sources_live_fetch.py tests/test_sources_profile_adapter.py tests/test_sources_router_domestic.py
    pytest -q tests/test_sources_pdf_step43.py

需要真实 DeepSeek 时：

    make research-live-deepseek

运行过程中的报告、dossier、checkpoint 和 provider 遥测会根据配置写入 data/，用于复核来源、证据、路由和质量门禁。

## 文档入口

- [项目现状总览](docs/current-project-overview.md)
- [Technical Roadmap Evolution](docs/technical-roadmap-evolution.md)
- [Source Query Decomposition](docs/source-query-decomposition-rules.md)
- [Source Taxonomy Inventory](docs/source-taxonomy-inventory.md)
- [Source Quality Scoring v2](docs/source-quality-scoring-v2.md)
- [50 Query 覆盖评测](docs/evals/report_coverage_50_queries_v1.md)
- [Agent Workflow](docs/workflows/review-gated-agent-workflow.md)
- [Skill Contracts](docs/workflows/skill-contracts.md)
- [项目 PRD](docs/prd/deep_research_readable_report_prd_v0_1.md)
- [Architecture Decision Records](docs/adr/)

实现过程中的阶段性记录、方案讨论和历史 remediation 不再作为 README 主体；它们保留在 .agent/PLANS/、.agent/STATUS.md 和 docs/，便于开发者追溯而不干扰项目展示。

## 当前边界

- 国内来源仍然依赖站点结构稳定性，深分页、反爬、登录态和复杂交互页面需要专用适配。
- 扫描型 PDF 的 OCR、复杂表格和图表理解尚未作为默认路径启用。
- 市县级来源采用通用域名模式、白名单和上级来源兜底，不能宣称覆盖所有地区。
- Provider 质量、来源命中率和报告完整性必须通过真实 query 与 evidence gate 持续评估。
- 外部 provider 的密钥只应放在本地 .env 或部署密钥系统中，不要提交到 Git。

## License

MIT
