# 项目进度汇总（截至 2026-04-19）

## 1. 里程碑进度

- Step 1：完成 monorepo 基础脚手架（FastAPI + worker + core/db/agents/rag/memory + infra）。
- Step 2：完成业务核心数据库模型与 Alembic 迁移（documents/chunks/citations/themes/theses/runs/memory/content 等）。
- Step 3：完成 ingestion 解析流水线（file/url -> document/chunk/citation + run/run_steps 审计）。
- Step 4：完成 RAG v1（chunk 检索、过滤、重排、evidence bundle 组装）。
- Step 5：完成多 Agent 研究工作流（Supervisor/Thesis/Opponent/EvidenceJudge/Risk + 结构化 memo）。
- Step 6：完成内容生成层（wechat_article/xiaohongshu_post/douyin_script 落库 content_assets）。
- Step 7：完成 memory + feedback 闭环（memory_records + content feedback + 提取/检索 API）。
- Step 8：完成交付层（delivery job、审核流、mock dispatch/export）。
- Step 9：完成异步任务层（task_jobs/task_attempts、worker claim/retry/idempotency、metrics/readyz）。
- Step 10：完成评测/策略/运营可观测层（evals、policy checks、registry、ops 路由）。
- Step 11：完成 DeepSeek 研究侧 provider 集成（mock/llm 双模式、严格 JSON 校验、错误修复路径）。
- Step 3.x（source-intelligence）：完成 source contracts -> 可用 adapters -> source-assisted research 集成 -> hardening -> source-evals/router scoring。
- Step 4.1~4.4（国内源专项）：
  - 完成 profile-driven domestic foundation（GenericProfileSourceAdapter / LiveHtmlFetchService / CollectorFactory）。
  - 完成两个真实国内源的 list-detail-attachment 采集闭环。
  - 完成 PDF 附件下载/提取/证据化最小链路。
  - 完成 PDF 能力作为 research/source-assisted/async 的显式可配置能力（含 summary 与审计信息）。

## 2. 当前系统可用能力（业务视角）

- 研究输入：支持传统检索路径与 source-assisted 路径（可选启用）。
- 证据构建：支持 chunk-level 证据、citation/locator、evidence bundle 汇总。
- 研究输出：输出结构化研究 memo（theses、objections、risks、confidence、gaps）。
- 内容工厂：从 research run 生成多平台内容资产并落库。
- 记忆闭环：从 run/content/feedback 提取 memory，支持检索与策略沉淀。
- 交付执行：内容资产 -> delivery jobs -> 审核 -> mock connector/export。
- 异步执行：research/content/delivery 可走任务队列执行并可审计追踪。
- 质量治理：evals + policy guardrails + readiness/ops 接口。
- 源采集：
  - 国际 API 型 source（user_input/world_bank/eia/sec_edgar）可用。
  - 国内 profile-driven source 支持真实站点最小可用采集。
  - PDF 附件可做受限下载/提取/证据项生成。

## 3. 核心调用链（高层）

- API 层：`apps/api/routes/*`
- 服务层：`packages/*/service.py`
- 工作流层：`packages/agents/workflow.py`（研究编排）
- 数据层：`packages/db/models.py` + 各模块 repository
- 异步层：`packages/tasks/*`（enqueue/claim/execute/retry）
- 源采集层：`packages/sources/*`（router/registry/adapters/collectors/live_fetch/pdf）

典型 research（source-assisted + PDF）路径：
1. `POST /research/analyze`
2. `ResearchWorkflowService`
3. （可选）`SourceIntelligenceService.build_bundle_for_query`
4. adapters/collectors 采集 + 证据归一化 + PDF 处理
5. 进入多 agent 研究工作流
6. 输出结构化 memo，并写入 `runs` / `run_steps`

## 4. 当前工程状态

- 主分支存在一批未提交改动（source、evals、tests、README 等），已具备进一步封版条件。
- 已形成“可运行 + 可审计 + 可回放”的主链路。
- 当前阶段重点从“功能可用”进入“稳定性/质量/可运维增强”。

## 5. 下一步建议（建议顺序）

1. Step 4.5：国内源鲁棒性增强（反爬/结构漂移监控/选择器健康检测）。
2. PDF 增强：分页抽样策略、文本质量评分、失败重试策略细化。
3. Source Evals 深化：源质量统计长期化、路由分数在线校准。
4. 生产化：凭证管理、部署编排、告警与 SLO、回归测试矩阵扩展。

## 6. 提交说明

本次提交目标：沉淀“当前项目进度汇总”并与现有改动一起入库，便于后续继续迭代与交接。
