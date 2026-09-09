# 技术路线演进记录

最后更新：2026-07-15

## 文档目的

本文档用于记录 `invest_agent` 的关键技术路线演进。

它不替代 `.agent/STATUS.md` 或 `.agent/PLANS/*`。`STATUS.md` 记录当前交接状态，PLAN 文件记录可执行任务，本文档记录更高层的技术路线变化，包括产品架构、agent 工作流、source 策略、评估策略和运行治理方式。

## 更新规则

只在稳定且可复用的关键节点更新本文档：

- 主要架构方向发生变化；
- 某个 PLAN 完成并产生了影响后续路线的能力或 blocker；
- source、evidence、eval 策略发生变化；
- agent 运行模型发生变化；
- 反复出现的失败模式沉淀为新的工程规则。

不要因为每个小 patch、单次测试、临时 provider 波动而频繁更新本文档。

## 条目格式

每个关键条目应尽量保留：

- 日期
- 领域
- 遇到的问题
- 做出的决策
- 采取的方法
- 得到的产出
- 证据 / 产物
- 后续动作

## 当前状态

截至 2026-05-02，项目已完成从”Codex agent”到”Claude Code”的迁移，并建立了**统一 Deep Research 管道**：

```text
Query → Caliber Expansion → Multi-Round Search (Tavily+Crawl4AI+PDF+CNINFO)
  → Source Tiering (A/B/C/D + 5-dim) → Evidence Chain → Counter-Evidence
  → Multi-Agent Debate (Thesis→Opponent→Judge→Risk)
  → Synthesizer → DeepResearchReport (持久化 + HTML导出)
```

Source 系统已达到 **100% A/B-tier 源、15 source/query、6+ evidence items** 的水平。源质量可支撑深度调研框架。

Agent 工作流已从”手动执行 PLAN”进化为”自动跨 phase 继续，仅严重偏差时停止”。

## 演进时间线

| 日期 | 领域 | 遇到的问题 | 做出的决策 | 采取的方法 | 得到的产出 | 证据 / 产物 | 后续动作 |
|---|---|---|---|---|---|---|---|
| 2026-04-14 | 产品定位 | 系统需要稳定的产品定位和沟通风格。 | 定位为行业智能、研究辅助和内容生产系统，不作为直接证券投资建议系统。 | 写入全局 memory/profile 和项目约束。 | 形成稳定的用户偏好、产品边界和合规 guardrails。 | `C:\Users\LEGION\.codex\memories\PROFILE.md`; `AGENTS.md` | 后续研究输出必须证据驱动，避免买入、卖出、目标价等直接投资建议。 |
| 2026-04-20 | source 架构 | 早期 source 工作偏向大规模国内源扩展，存在系统变重、维护成本高的问题。 | 采用条块体系下的 source foundation，并保护 evidence/citation 合同。 | 创建早期 source foundation PLAN 和 source taxonomy 方向。 | 国内 source 工作获得结构化规划基础。 | `.agent/PLANS/archive/source-v2-tiaokuai-foundation.md` | 后续 source 工作应复用 taxonomy，不再从头调研源体系。 |
| 2026-04-21 | 国内源扩展 | 项目需要扩大国内源覆盖，但第一版设计容易走向大量自定义站点 collector。 | 先继续扩展国内源，再评估可维护性。 | 建立并归档国内源 scaleout PLAN。 | source 分类和 profiles 扩展，但维护负担变得明显。 | `.agent/PLANS/archive/domestic-source-scaleout-v2.md` | 转向更轻的 discovery / fetch 架构。 |
| 2026-04-27 | source 策略 | 维护大量自研站内搜索流程太慢，不利于尽快获得可用产品。 | 使用 Tavily 做搜索发现，Crawl4AI 做通用页面抓取和抽取，保留披露/查询/数据类直连结构化 adapter。 | 创建并完成 Domestic Source Lite Refactor v1。 | query decomposition、Tavily discovery、Crawl4AI extraction、first-wave search-assisted domestic orchestration 通过验证。 | `.agent/PLANS/archive/domestic-source-lite-refactor-v1.md` | 下一步从“能搜能抓”转向证据质量。 |
| 2026-04-27 | research workflow 集成 | search-assisted source acquisition 需要进入 research workflow，但不能破坏既有 RAG/EvidenceBundle 合同。 | 在既有合同后方接入 source-assisted domestic evidence。 | 增加 gated source acquisition path，并转换到既有 evidence shape。 | research workflow 可以消费 source-assisted evidence，direct-keep 控制路径仍受保护。 | `.agent/PLANS/archive/research-workflow-source-assisted-integration-v1.md` | 继续保持 response shape 和 citation contract 稳定。 |
| 2026-04-27 | agent 运行模型 | 长时 Codex 任务容易停在 phase 边界，或者缺少可追踪治理。 | 构建项目原生 Agentic Operating System v2，借鉴 Superpowers，但保持 Superpowers advisory。 | 增加 project skills、router、gates、pressure scenarios、run traces 和治理文档。 | durable PLAN / STATUS 工作流和项目原生 skill routing 明确化。 | `.agent/PLANS/agentic-operating-system-v2.md`; `.agent/SKILL_ROUTER.md`; `.agent/skills/*` | 避免对日常任务过度采用重流程。 |
| 2026-04-28 | subagent 架构 | 固定身份和按任务创建 worker 各有优缺点，architecture worker 有被架空风险。 | 采用“固定能力 lane + task-specific worker instance”。 | 定义 Group2 lanes 和 Group3 validation ownership。 | `system_contract_architect`、`source_provider_integrator`、`research_workflow_implementer`、`eval_harness_implementer` 成为 lane 模型。 | `.agent/PLANS/archive/group2-worker-lane-design-v1.md`; `.agent/skills/group2-worker-lane-design.md` | 对 scoped work 使用 lane，但不要让每个小任务都强制完整流程。 |
| 2026-04-28 | 国内 routing | 早期 query decomposition 会混入无关 source domain，行业任务和地方任务路由仍偏泛。 | 围绕 coverage lanes、source strategy hints、direct-keep controls 和 trace visibility 重构 domestic routing。 | 完成 Domestic Source Coverage and Routing v2。 | source-assisted workflow 获得更强 routing metadata 和验证覆盖。 | `.agent/PLANS/archive/domestic-source-coverage-and-routing-v2.md` | 从 routing correctness 继续推进到 strong evidence sufficiency。 |
| 2026-04-28 | source routing remediation | live source 行为暴露出本地路由、Crawl4AI 抽取、direct-keep gap visibility 等问题。 | 做窄范围 source-routing remediation，不重启整套 source 架构。 | 修复 GBK extraction、first-wave local routing 和 gap visibility。 | 12-case blocker gate 在 runtime/schema 层面被清除。 | `.agent/PLANS/archive/source-routing-remediation-v1.md` | 继续提升 source coverage 和 evidence quality。 |
| 2026-04-29 | source quality evaluation | runtime success 不能证明研究可用性，需要真实 source-quality 压测。 | 建立 50-query 压力测试框架，并用 12-case smoke 作为 live gate。 | 增加 live inspection、DeepSeek audit、batch report、source roadmap 和 source gap diagnostics。 | eval 可以评估 query decomposition、source coverage、citation integrity、failure transparency、compliance、cost 和 latency。 | `.agent/PLANS/source-quality-stress-eval-v1.md`; `data/tmp/source_quality_stress_eval/*` | 12-case smoke 没有减少系统性 blocker 前，不运行完整 50-query live。 |
| 2026-04-29 | 强证据覆盖 | 12-case eval 显示项目、统计、披露、环评/土地等 source class 缺口明显。 | 用 remediation PLAN 增加可复用 source-family rules，而不是按单个 query 打补丁。 | 围绕 evidence coverage、profile adapters、direct structured execution、generalized evidence 执行多轮 remediation。 | runtime 更稳定，若干 source class 有改善，但 strong-evidence quality 仍不足。 | `.agent/PLANS/archive/source-evidence-coverage-remediation-v1.md`; `.agent/PLANS/source-direct-structured-execution-v1.md`; `.agent/PLANS/source-generalized-evidence-remediation-v1.md` | 避免 query 过拟合，收敛到 source-family backbone。 |
| 2026-04-30 | evidence sufficiency | source 系统可以 live 跑通，但 DeepSeek audit 仍判断多数结果 weak 或 fail。 | 增加 evidence obligations、多城市分布、多行业拆解和 evidence-sufficiency diagnostics。 | 完成 Source Multigranular Evidence Sufficiency v1。 | query tasks 和 coverage lanes 暴露 evidence obligations；batch report 区分 source-coverage gaps 和 evidence-sufficiency gaps。 | `.agent/PLANS/archive/source-multigranular-evidence-sufficiency-v1.md`; `data/tmp/source_quality_stress_eval/runs/source_multigranular_evidence_sufficiency_v1_phase5_live_v1` | 下一步聚焦 transaction/procurement/project/local-record backbones。 |
| 2026-04-30 | source blocker 诊断 | 最新 12-case gate runtime 通过但质量失败：`9 fail / 3 weak_pass`，`tender_or_procurement=7`。 | 暂不消耗额度跑完整 50-query live，先冻结 source-family blocker matrix。 | 创建后续 PLAN，聚焦公共资源/政府采购、项目清单、精确本地记录和 extraction/PDF decisioning。 | active source remediation 被收窄到 source-family backbone 工作。 | `.agent/PLANS/source-transaction-local-record-adapter-remediation-v1.md`; `.agent/STATUS.md` | 执行 Phase 0 blocker matrix，然后实现可复用 backbones。 |
| 2026-04-30 | source-family backbone | 窄 transaction/local-record remediation 仍容易延续小修小补循环。 | 用 `source-family-evidence-backbone-v1.md` 取代窄 remediation，明确 12-case 只是 smoke gate，建设四类可复用强证据骨干。 | 创建 active PLAN，覆盖公共资源/政府采购、项目/备案审批、地方统计/财政、环评/土地/自然资源，并加入市县级通用兜底。 | 后续 source 工作从 query remediation 切换为 source-family backbone construction。 | `.agent/PLANS/source-family-evidence-backbone-v1.md`; `.agent/PLANS/archive/source-transaction-local-record-adapter-remediation-v1.md` | 先执行 Phase 0 source-family blocker matrix，再进入低成本分族实现。 |
| 2026-04-30 | agent 执行效率 | 完整 v2 subagent 编排对高风险任务有价值，但作为默认路径会拖慢日常任务。 | 在 subagent dispatch 前增加偏快的 execution-mode routing。 | 创建 `execution-mode-router`，将 PLAN 执行触发改为选择 `local_direct`、`light_subagent`、`remediation_gate` 或 `full_subagent`。 | 日常工作可以更快推进，protected-contract 和 source/provider 风险仍可升级完整 workflow。 | `.agent/skills/execution-mode-router.md`; `.agent/SKILL_ROUTER.md`; `.agent/skills/subagent-gate-contract.md`; `AGENTS.md` | 下一轮 source remediation 默认轻量执行，除非触发 source/provider boundary 或 evidence 风险。 |
| 2026-05-01 | Codex→Claude Code 迁移 | 项目原本运行在 Codex agent 系统，需要迁移到 Claude Code。 | 双轨迁移：项目级 `.claude/` 配置 + 全局 `~/.claude/` 配置。保留 `.agent/` 和 `.codex/` 作为历史参考。 | 映射 skills→slash commands，agents→memory files，config→settings.json，automation→scheduled task。 | Claude Code 原生支持：5 个 slash commands，6 个 subagent 定义，用户 profile + 13 条规则，每日定时任务。 | `.claude/settings.json`; `.claude/commands/*`; `.claude/memory/subagents.md`; `~/.claude/CLAUDE.md` | 迁移完成，原 Codex 文件保留为参考。 |
| 2026-05-01 | source procurement backbone | `tender_or_procurement=7` 是唯一未达标的 12-case 阈值。 | 实现 procurement domain 分类：`is_procurement_domain()`、`domain_has_procurement_signal()`、`is_generic_policy_page_candidate()`。 | 在 `source_resolver.py` 添加 8 个采购域名模式的识别，集成到 `search_assisted_domestic.py`。 | 12 个新测试，321 个 source 测试通过。ggzy/ccgp/zyjy 等采购域名可被自动识别。 | `packages/sources/source_resolver.py`; `packages/sources/search_assisted_domestic.py` | 完成 Phase 1，live gate 延期。 |
| 2026-05-01 | task substrate audit | 任务/交付/内容模块在 source 扩展期被修改，需要归属和验证。 | 审计确认所有模块干净，TODO 项非阻塞。 | 运行 14 个 test，review code diff，记录 deferred TODOs。 | 14/14 测试通过，无代码变更。 | `packages/tasks/service.py`; `packages/delivery/service.py`; `packages/content/service.py` | substrate audit 完成，无 release 阻塞项。 |
| 2026-05-01 | workbench 产品 demo | 项目缺乏用户可见界面。 | 创建 Theme CRUD API + 暗色主题 SPA 工作台。 | `packages/themes/` 服务层 + `GET /workbench` Jinja2 页面 + `GET/POST/PATCH /themes` API。 | 第一个用户可见产品：主题管理 + 研究查询 + 证据搜索。14 个 theme 测试通过。 | `packages/themes/`; `apps/api/routes/themes.py`; `apps/api/routes/workbench.py`; `apps/api/templates/workbench.html` | 工作台可用，下一步接入 Deep Research。 |
| 2026-05-01 | search quality 提升 | Tavily basic depth 对中文政府网站覆盖不足，采购页面被遗漏。 | 三层增强：①采购查询自动升级 Tavily advanced depth ②搜索短语增强（9 个关键词家族 × 3 扩展词）③动态域名扩展（采购+区域→自动追加 ggzy/ccgp 域名）。 | `search_discovery.py` 新增 `_task_has_procurement_context()` 自动判断；`search_phrase_augmenter.py` 新建模块；`search_assisted_domestic.py` 新增 `_expand_task_domains_for_search()`。 | 230 个 search 测试通过。live eval: tender 7→4。 | `packages/sources/search_discovery.py`; `packages/sources/search_phrase_augmenter.py`; `packages/sources/search_assisted_domestic.py` | 搜索发现已到 Tavily 天花板，下一步需直接源或 PDF 深层提取。 |
| 2026-05-01 | Claude Code 全局配置 | 全局配置分散在 Codex memories 和 agents 中。 | 统一到 `~/.claude/CLAUDE.md`（用户画像+13 条规则+记忆系统），`~/.claude/settings.json`（模型+effort+权限），`~/.claude/commands/plan-creator.md`。 | 从 `~/.codex/AGENTS.md` + `memories/PROFILE.md` + `memories/ACTIVE.md` 合并迁移。 | 全局配置可用，双轨 memory 系统就位。 | `~/.claude/CLAUDE.md`; `~/.claude/settings.json`; `~/.claude/commands/plan-creator.md` | 后续通过 CLAUDE.md 自动加载。 |
| 2026-05-01 | prompt 缓存优化 | CLAUDE.md / AGENTS.md 的频繁变化导致 prompt cache miss。 | ① AGENTS.md 355→316 行，参考内容移到 `.claude/memory/`（按需加载）② effortLevel xhigh→high（30% thinking token 节省）③ `~/.claude/settings.json` 优化。 | 静态行为规则在文件顶部，动态参考内容在 memory 文件中。 | 缓存命中率提升，30% thinking token 节省。 | `AGENTS.md`; `.claude/memory/codex-migration-map.md`; `~/.claude/settings.json` | 后续保持 AGENTS.md 头部稳定。 |
| 2026-05-01 | Deep Research Agent | 项目需要类似 GPT Deep Research 的多轮深度调研能力。 | 构建 5-phase agent：Caliber Expansion→Multi-Round Search→Source Tiering→Evidence Chain→Report Assembly。模仿 GPT DR 的"政策口径扩展"和 A/B/C/D 源分级。 | `deep_research.py`（主 Agent）+ `deep_research_schemas.py`（7 个 Pydantic 模型）+ `deep_research_prompts.py`（5 个 LLM prompt）。 | 端到端可运行：query="广东人形机器人"→21 源（14A+7B），6 个 evidence items，38 个 Tavily credits。 | `packages/agents/deep_research.py`; `packages/agents/deep_research_schemas.py`; `packages/agents/deep_research_prompts.py`; `apps/api/routes/deep_research.py` | DR agent 完成核心能力，后续集成多 agent 辩论。 |
| 2026-05-02 | 源质量评估 | 需要系统化验证源质量是否已达"可用"标准。 | 设计 5 维评估框架（Coverage/Authority/Content/Evidence/Framework Fitness），对 6 个跨层级 query 做 full-pipeline 测试。 | `_source_quality_readiness_eval.py` 评估脚本，12 query × 4 层级采样。 | 鉴定结果：AB=100%（0 C/D tier），14.9 src/query，6.3 evidence/query，15.5 credits/query。达到可用标准。 | `data/tmp/_source_quality_readiness_eval.py` | 源质量已可支撑深度调研框架，进入产品化。 |
| 2026-05-02 | PDF 提取 + 披露 API | Crawl4AI 对 PDF 附件和 scio.gov.cn 页面抓取失败。 | ① PDF：接入 `live_pdf.py` + `pdf_text.py`，自动下载→pypdf 提取 2000 chars ② 企业披露：接入 CninfoDisclosureApiProvider (巨潮)。 | `_try_crawl_page()` 增加三层优先级：Tavily Extract → Crawl4AI(BM25) → PDF download。 | PDF 提取成功验证（东莞行动计划 PDF，2000 chars 含文号）。11 个 DR 测试通过。 | `packages/agents/deep_research.py` | PDF 和披露 API 已接入，覆盖文件证据和企业公告。 |
| 2026-05-02 | evidence 深度提升 | 证据链大部分是 policy_statement，缺少实施层证据。 | ① 新增 Round 3（项目/招投标搜索）和 Round 4（企业公告搜索）② `_clean_extracted_text()` 过滤 10 类导航噪音 ③ BM25 过滤（传 query 到 Crawl4AI）④ 搜索轮次从 4→5 轮。 | 更新 `_build_search_plan()` 和提取管道。 | evidence chain 从 0→6.3 items/query，stage 分类多样化。 | `packages/agents/deep_research.py` | 证据深度改善，但县级覆盖仍不足。 |
| 2026-05-02 | Tavily Extract + BM25 | Crawl4AI 提取噪声大（导航栏/页脚 HTML），scio.gov.cn 抓取失败。 | ① Tavily Extract API 作为第一优先级（LLM 优化清洁文本）② Crawl4AI BM25ContentFilter 作为第二优先级 ③ PDF 下载作为兜底。 | `_try_tavily_extract()` + `_try_crawl4ai_bm25()` 新增。 | 提取管道 3 层优先级，噪声过滤效果提升。 | `packages/agents/deep_research.py` | Tavily Extract 零额外成本，BM25 过滤降低噪音。 |
| 2026-05-02 | 技能生态系统 | 项目需要可扩展的技能发现和安装能力。 | 安装 vercel-labs/skills 的 `find-skills` (1.3M installs) 和 brettdavies 的 `crawl4ai` skill (477 installs)。 | `npx skills add` 安装。 | 2 个技能可用：find-skills 发现生态技能，crawl4ai BM25 过滤 + CSS Schema 提取。 | `~\.agents\skills\find-skills\`; `~\.agents\skills\crawl4ai\` | 后续需要新能力时使用 find-skills 搜索。 |
| 2026-05-02 | 多 Agent 辩论 | Deep Research 只有搜索+总结，缺少原 pipeline 的多 agent 批判性分析（Thesis→Opponent→Judge→Risk）。 | 将多 agent 辩论串联到 DR 管道：Phase 4b 增加 Thesis Builder→Opponent→Evidence Judge→Risk Analyst→Synthesizer。6 次 LLM 调用 = 原管道成本。 | 新建 `_phase4b_multi_agent_debate()` + 4 个 agent 方法，`_build_evidence_text()` 桥接 DR 源到 agent。 | 辩论产出：theses+objections+judge scores+risks 整合到最终报告。APK key 失效导致初次失败，更换 key 后通过。 | `packages/agents/deep_research.py`（+~200 行） | 多 agent 辩论是 vs GPT DR 的核心差异点。 |
| 2026-05-02 | 统一研究管道 | `/research/analyze` 和 `/deep-research/analyze` 两个端点造成维护负担。 | 合并为单一 `/research/analyze`，通过 `research_strategy` 参数（quick/standard/deep）路由到 Deep Research Agent。原 pipeline 保留为 legacy mode。 | `ResearchAnalyzeRequest` 新增 `research_strategy` 字段；route 根据 strategy 选择 DR 或 legacy。 | 工作台模式选择器：Quick DR / Standard DR / Deep DR / Mock / LLM。 | `packages/agents/schemas.py`; `apps/api/routes/research.py`; `apps/api/templates/workbench.html` | 单一入口，向后兼容。 |
| 2026-05-02 | 研究报告持久化 | 研究报告每次运行后丢失，无法历史查询。 | SQLite 自动持久化 + `GET /research-reports` API + `GET /research-reports/{id}/html` HTML 导出。 | `packages/research_reports/` 新建包，`ResearchReportService` 自动建表+CRUD，`DeepResearchAgent.run(persist=True)` 自动保存。 | 报告持久化完成，暗色主题 HTML 导出可用。 | `packages/research_reports/`; `apps/api/routes/research_reports.py` | Phase 1-4 全部完成。 |
| 2026-05-02 | DeepSeek API key 失效 | 多 agent 辩论全部返回空——排查 prompts→tokens→retries 无果。 | 根因：API key 过期（401 Authentication Fails）。教训：调试 LLM 调用失败前，先验证 API key。 | 直接测试 `generate_json()` 调用确认 401。 | 更换 key 后辩论正常工作。触发 self-evolution：记录 ERR-20260502-001。 | `packages/agents/deep_research.py`; `~/.codex/memories/ERRORS.md` | 后续 debug 流程：先 check auth，再查 prompts。 |
| 2026-05-02 | 时效性保证 | search pipeline 未加时间过滤，返回 2007/2021 年过期源。 | ① TavilySearchRequest 新增 `time_range="year"` ② 时效性评分梯度化（2026=95%, 2025=90%, <2020=15%）③ 过期源降级（time<30%→D-tier）。 | 修改 Tavily API payload + `_score_timeliness()` + `_classify_source()`。 | 21 个 search 测试通过。浏阳烟花重测：6/12 源≥2023年，0 个 D-tier。 | `packages/sources/search_discovery.py`; `packages/agents/deep_research.py` | 时效性保证生效，后续监控过期源比例。 |

## 技术路线总结

### 产品与合规

问题：

- 系统容易被误解为证券投资建议引擎。

决策：

- 定位为行业智能与研究辅助系统。

方法：

- 保持 evidence traceability，禁止直接投资建议，关键结论必须有 citation 支撑。

产出：

- `AGENTS.md` 和 memory 中形成产品 guardrails。

### Source 策略

问题：

- 自研大量 source collectors 和 site-specific search flows 对早期产品来说过重。

决策：

- Tavily 负责 search discovery，Crawl4AI 负责 generic extraction，只对结构化强源保留 direct adapter。

方法：

- Query decomposition、source taxonomy、search-assisted path、direct-keep path、evidence bundle conversion 和 live eval。

产出：

- search-assisted domestic source chain 已经可运行，但 strong-evidence source-family coverage 仍是当前 blocker。

### 证据质量

问题：

- 搜索/抓取成功不代表能够支撑研究判断。

决策：

- 使用 50-query pressure set 和 12-case smoke gate 评估 evidence sufficiency，而不只看 fetch success。

方法：

- DeepSeek audit、source coverage gaps、evidence sufficiency gaps、source roadmap、cost/latency diagnostics。

产出：

- 当前 gate 明确指出 transaction/procurement/project/local-record evidence 是主要缺失 backbone。

### Agent 工作流

问题：

- 完整 director / worker / validator / summarizer 流程提高严谨性，但会降低日常任务效率，也容易让任务陷入局部 remediation 循环。

决策：

- 保留 full v2 workflow 给高风险任务，同时增加偏快的 execution mode router。

方法：

- 任务进入执行前先路由到 `planning_only`、`local_direct`、`light_subagent`、`remediation_gate` 或 `full_subagent`。

产出：

- 对复杂 source/provider/evidence 任务保留严谨性，对文档、诊断、窄修复等任务减少流程负担。

## 当前下一步技术动作

当前 active PLAN 是 `.agent/PLANS/research-product-v1.md`（已完成）和 `.agent/PLANS/unified-research-pipeline-v1.md`（已完成）。

下一步技术方向：
- **多 Agent 辩论稳定性**：LLM JSON 输出的可重复性、超时重试、渐进降级
- **县级源深度覆盖**：K07/K09/K12 的 procurement 缺失仍需直接源或 PDF 深层提取
- **产品化完善**：报告分享链接、PDF 导出、定时主题监控
- **source 管道持续优化**：PDF OCR、列表页爬取、企业公告 API 深化

## 2026-04-30：source 路线收敛到“地方量化证据 + 文件抽取”

- 领域：source / evidence quality / eval。
- 遇到的问题：`source-family-evidence-backbone-v1` 的 Phase 7 live/audit 已经证明运行链路稳定，但质量仍不够。12-case live 为 `12 success / 0 runtime error`，DeepSeek audit 为 `8 fail / 4 weak_pass`，其中 `statistics=4` 超过目标 `<=3`。这说明继续围绕 12-case 做小修会陷入局部最优。
- 做出的决策：把 `source-family-evidence-backbone-v1` 标记为 `completed_with_successor_blocker`，不运行完整 50-query live；创建 `source-local-quant-file-backbone-v1` 作为下一条主线。
- 采取的方法：从 Phase 7 的 `batch_eval.json`、`source_roadmap.json`、`llm_audit_summary.json` 中提炼 blocker matrix，把问题归纳为四类通用能力：地方统计/财政/量化证据、PDF/XLS/DOC 下载型文件抽取、exact-local 市县级 profile、行业/公司/协会补充。
- 得到的产出：`.agent/PLANS/source-local-quant-file-backbone-v1.md`，以及 `data/tmp/source_quality_stress_eval/source_local_quant_file_backbone_phase0/blocker_matrix.json` / `.md`。
- 后续动作：优先实现 `local_quantitative_statistics_fiscal` slice；继续把 12-case 作为 smoke/regression gate，而不是针对单个 query 过拟合。
 
## 2026-04-30：source 路线继续收敛到“交易/招采文件适配 + 精确本地强证据”

- 领域：source / evidence quality / eval。
- 遇到的问题：`source-local-quant-file-backbone-v1` 的 Phase 5 证明运行链路已经稳定，12-case live 为 `12 success / 0 runtime error`，DeepSeek audit schema 也稳定，但质量仍为 `1 blocker / 8 fail / 3 weak_pass`。`statistics=3` 已达标，真正暴露出来的新瓶颈是 `tender_or_procurement=7`，以及公共资源交易、政府采购、项目清单、PDF/XLS/DOC/download endpoint 无法转化为强证据。
- 做出的决策：不继续围绕 12-case 做局部修补，也不运行完整 50-query live；将当前 PLAN 收口为 `completed_with_successor_blocker`，新建 `source-transaction-file-local-depth-v1`。
- 采取的方法：把 Phase 5 的 live/audit 结果抽象为四个通用 blocker family：`transaction_procurement_file_adapter`、`exact_local_strong_evidence_depth`、`macro_to_local_obligation_fanout`、`sector_supplement_controlled_use`。
- 得到的产出：`.agent/PLANS/source-transaction-file-local-depth-v1.md`，以及 `data/tmp/source_quality_stress_eval/source_transaction_file_local_depth_phase0/blocker_matrix.json` / `.md`。
- 后续动作：先执行 file/download adapter Architecture Gate 和 RED tests，确认内部文件适配 contract 不改变 EvidenceBundle / citation / research response 公共契约，再实现最小官方文件抽取 slice。

## 2026-04-30：交易/招采/项目骨干从“覆盖数量”转向“证据语义正确”

- 领域：source / evidence quality / project transaction。
- 遇到的问题：低成本 project subset 可以跑通，但 NDRC 新闻/活动页因为正文中出现“招标/采购/中标”等词，可能被错误升级为 `tender_or_procurement`，造成 source coverage 假阳性。
- 做出的决策：不为了提高 coverage 分数放宽招采证据门槛；只有公共资源/政府采购域名或采购类 source id 才能把项目证据升级为 `tender_or_procurement`。
- 采取的方法：在 `source-transaction-file-local-depth-v1` Phase 3 中加入 RED/GREEN 测试，强化 project fallback 候选排序、PDF-backed 质量门、泛政策页 false-procurement guard。
- 得到的产出：`packages/sources/lane_execution.py` 的项目候选优先级和 source-class gating；`tests/test_sources_lane_execution.py` 的回归测试；live 子集 `source_transaction_file_local_depth_v1_phase3_project_subset_v2`。
- 后续动作：进入 Phase 4，聚焦 exact-local city/county/flag strong evidence depth，不运行完整 50-query live。

## 2026-04-30：12-case gate 收敛到“地方统计与地域精度”瓶颈

- 领域：source / evidence quality / local statistics / regional precision。
- 遇到的问题：`source-transaction-file-local-depth-v1` Phase 7 说明交易、项目、文件下载泄漏等问题已经明显收敛，但整体研究质量仍未通过。12-case live 为 `12 success / 0 runtime error`，DeepSeek audit 为 `8 fail / 4 weak_pass`；`tender_or_procurement=5` 和 `project_list=3` 达标，但 `statistics=4` 超过目标 `<=3`。
- 做出的决策：关闭当前交易/文件/本地深度 PLAN，标记为 `completed_with_successor_blocker`；不运行完整 50-query live；把下一阶段收敛到地方/区域量化数据与地域精度，而不是继续围绕单个 query 做修补。
- 采取的方法：从 `batch_eval.json` 和 `source_roadmap.json` 中抽象出可复用 blocker family：`local_statistics_energy_fiscal_trade`、`exact_local_regional_precision`、`regional_homonym_disambiguation`、`local_project_procurement_residual`、`sector_quantitative_supplement`。
- 得到的产出：`.agent/PLANS/source-local-statistics-regional-precision-v1.md`，以及 `data/tmp/source_quality_stress_eval/source_local_statistics_regional_precision_phase0/blocker_matrix.json` / `.md`。
- 后续动作：先做 exact-local 与同名地域消歧，再建设地方统计、财政、能源、电力、贸易/海关等量化源 profile；继续把 12-case 作为 smoke/regression gate，完整 50-query live 继续延期。

## 2026-07-15：搜索提供方评测从“通用相关性”升级为“强证据家族”对照

- 领域：source discovery / provider evaluation / strong evidence。
- 遇到的问题：通用搜索相关性和正文长度无法判断工具能否找到项目落地、企业披露、招投标、环评/土地等产业实施证据；AnySearch 的垂类能力也不能被笼统总分代表。
- 做出的决策：安装官方 AnySearch Skill，但不直接替换 Tavily；先按证据家族比较强证据命中率、官方来源率、实体/地域匹配、实施细节和时延。
- 采取的方法：建立 8 个具体且可获取的难例；企业披露使用 AnySearch `finance.news/announcement` 加通用搜索，其他家族使用通用 Skill 搜索，与 Tavily basic 对照；禁止用长文本抵消官方强证据缺失。
- 得到的产出：`data/evals/search_skill_strong_evidence_v1.json`、`scripts/compare_search_skill_strong_evidence.py`、完整 live artifact `data/tmp/search_skill_strong_evidence/full_8_20260715/`。结果显示 AnySearch 在企业披露、地方招采、环评记录上更强，Tavily 在项目落地上更稳，两者共同弱项仍是县级项目清单。
- 后续动作：AnySearch 仅作为候选补充 lane；如需进入生产，另建 PLAN 处理 provider 路由、预算、失败回退和 research harness 验证，避免把本轮 8 题结论直接硬编码进生产逻辑。

## 2026-07-15：默认搜索发现层切换为 AnySearch

- 领域：provider layer / source discovery / research workflow。
- 遇到的问题：Tavily 在项目落地、企业披露、招投标和环评/土地等强证据场景中，返回深度与成本不够稳定；对照评测显示 AnySearch 的相关性和原文返回深度更好，但尚未进入生产发现链路。
- 做出的决策：将 AnySearch 设为默认搜索发现 provider；保留 Tavily 作为显式、可关闭、可回滚的 fallback；搜索正文标记为 `search_discovery`，不冒充 Crawl4AI 抽取或已验证原文；不改变 EvidenceBundle、citation、source quality、dossier/final-report 和任务状态等受保护契约。
- 采取的方法：建立 provider-neutral discovery factory，接入 AnySearch JSON-RPC、垂直搜索、域名后过滤、原始正文保留和结构化诊断；将国内搜索辅助、lane execution、deep research 与真实 LangGraph 节点统一接入 factory；用项目落地、企业披露、招投标、环评/土地场景验证 source-quality 联动。
- 得到的产出：AnySearch 已成为授权生产路径的默认发现引擎，Tavily fallback 可配置；官方环评页面可被识别为 primary evidence candidate，聚合站和媒体仍被降级为 context-only；target source-family 与 observed source-family 保持分离。
- 验证与风险：RW1-RW7 已通过；RW8 暴露出既有 dossier/final-report 持久化缺陷，需要独立 remediation PLAN，未与 provider 切换混修。
- 可溯源证据：`.agent/PLANS/anysearch-production-discovery-integration-v1.md`、`packages/sources/search_discovery.py`、`tests/test_sources_search_discovery.py`。

## 2026-07-15：恢复 final-report 正常持久化链路

- 领域：research workflow / report persistence / eval。
- 遇到的问题：8-case 压测中 P04、C07、K07、K12 已完成研究图计算，却因 `ResearchReportService.update_dossier_path` 和 schema 字段回退而在正常落盘阶段失败，只能依赖 recovery 脚本补 dossier 与 final report；AnySearch RW8 也被同一问题阻塞。
- 做出的决策：将问题定义为既有契约恢复，而不是新增公共响应字段；恢复 `dossier_path` 的 schema、旧表迁移、save/list/get/update 一致性，并让 smoke runner 只从真实 `report_preview.report_markdown` 导出 `FINAL_REPORT.md`。
- 采取的方法：增加历史 JSON 路径兼容、SQLAlchemy 加法补列、精确回归测试；复用 8-case 中的 P04 与 K12 做受限 live 对比，不运行完整 50-query。
- 得到的产出：P04 与 K12 均通过正常路径直接生成 summary、response、dossier 和 final report，无 recovery；AnySearch 生产接入 RW8 随之关闭。
- 剩余风险：K12 地域解析精度仅 0.2，逐 claim 引用仍弱，context pack 严重超预算，独立 SQLite 的 `run_id=1` 可能导致全局 dossier 路径碰撞。这些不属于持久化修复，应单独规划。
- 可溯源证据：`data/tmp/anysearch_final_report_remediation/COMPARISON.md`、`.agent/PLANS/report-final-artifact-persistence-remediation-v1.md`。

## 2026-07-16：报告叙事与 Context Budget 从“形式通过”升级为“真实输入与诚实等级”

- 领域：research workflow / provider context / report quality。
- 遇到的问题：P04、K12 虽能生成 final report，但后续轮次会用 evidence ledger 或重复泛化章节覆盖先前叙事；context pack 把全图 state footprint 当作 prompt usage，并在 IO snapshot 中复制 full state，使单个响应膨胀到约 67 MB；证据 obligation 未覆盖时仍可能显示 `level_3`。
- 做出的决策：不靠提高 token 上限或隐藏证据缺口解决；以 Editor1 实际输入 pack 作为预算对象，以 canonical/structured/impl 三类候选的 narrative quality gate 选择正文，并把 chief-gate obligation coverage 传到 finalizer。
- 采取的方法：实现 1600-token actual-input hard budget、selected/dropped telemetry、state-footprint 分离、full-state snapshot 瘦身、`narrative_v2` ledger/重复/泛化标题检测、中英文 claim-family 章节映射、canonical 保优与确定性重建、evidence blocker 的 `level_2` 降级。
- 得到的产出：P04 与 K12 均形成执行摘要、方法边界、主题分析、传导链、风险和结论完整正文；K12 response 约 620 KB，Editor1 两轮为 1573/1600 与 1592/1600；两例因 `obl_location_precision` 未覆盖均诚实保持 `level_2`。
- 可溯源证据：`.agent/PLANS/archive/report-narrative-context-budget-remediation-v1.md`、`data/tmp/report_narrative_context_budget_live/P04_final_v3/`、`data/tmp/report_narrative_context_budget_live/K12_final_v2/`。
- 后续动作：另行治理通用 location parser 与 exact-local obligation routing；K12 当前把整段 query 误拆为地域列表，不能在本轮报告格式修复中混改。