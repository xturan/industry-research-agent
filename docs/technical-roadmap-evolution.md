# 技术路线演进记录

最后更新：2026-04-30

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

截至 2026-04-30，项目定位是生产导向的行业智能与研究辅助系统，而不是直接证券投资建议系统。核心技术方向是证据驱动研究：

```text
source acquisition
  -> evidence bundle
  -> research workflow
  -> content/workflow outputs
  -> validation and traceability
```

当前 source 系统已经越过“能否搜索和抓取网页”的基础阶段。主要 blocker 变成了强证据充分性：交易、招采、项目清单、精确本地记录、统计、环评、土地等证据是否足以支撑产业研究判断。

agent 工作流已经加入偏快的 execution router。完整 v2 subagent 编排仍保留给高风险任务；日常任务优先使用 `local_direct` 或 `light_subagent`。

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

当前 active PLAN 是 `.agent/PLANS/source-transaction-file-local-depth-v1.md`。下一步 source-layer 工作不应再做泛化 routing remediation，而应继续建设可复用 source-family backbones：

- public-resource / government-procurement；
- project-list / filing / approval / key-project records；
- exact-local city/county government records；
- statistics / fiscal / environmental / land records；
- extraction/PDF failure classification and strong-evidence gating。

12-case smoke set 应继续作为 regression gate。完整 50-query set 应继续延后，直到 source-family gaps 缩小到值得消耗成本的程度。

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
