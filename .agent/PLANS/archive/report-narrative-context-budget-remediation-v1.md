# Report Narrative And Context Budget Remediation v1

Status: completed

## Objective

修复 provider-backed research graph 在深度报告阶段退化为“结论 + 证据条目账本”的问题，并把 context-pack 预算从事后、全状态估算改为对真实 Editor1 LLM 输入生效的可观测预算。最终报告必须保留分析叙事、跨来源综合、传导链条、对比、证据局限和后续跟踪，而不能仅因 claim 都有证据就被授予 `level_3`。

## Task Classification

- Primary area: `research_workflow`
- Secondary areas: `provider_layer`, `eval_policy_ops`
- Execution mode: `local_direct`（用户明确要求本轮不再启动 subagent）
- Request type: `implementation_and_validation`
- Impacted modules (planned write scope for later implementation only):
  - `packages/research_harness/**`
  - `tests/test_research_harness_graph.py`
  - `tests/test_report_quality_inspect.py`
  - `tests/test_graph_provider_backed_smoke_matrix.py`
- Protected contracts that must not change silently:
  - `EvidenceBundle` schema
  - `EvidenceItem` citation fields
  - `source_quality_summary` shape
  - public research API request/response schema
  - task/run status semantics

## Confirmed Root Cause

已确认根因，不再把 P04/K12 个例现象误判为 resume 覆盖或单查询特例：

1. P04 与 K12 的 `initial` / `resume` 最终报告内容一致，因此退化不是 resume 覆盖导致。
2. 首轮 Editor1 已经生成叙事型草稿；补证后的后续轮次生成了 evidence-ledger 风格草稿并替换了原始叙事草稿。
3. 退化轮次草稿缺少稳定的 `llm_synthesized` 成功元数据，符合异常或低质量输出后静默 fallback 的行为特征。
4. finalizer 没有进行“旧草稿 vs 新草稿”的质量比较，只按 evidence gap 和形式化 coverage 定级。
5. 当前 `context_pack_summary` 统计的是重复的全状态 footprint，而不是实际送入 Editor1 prompt 的输入集。

结论：问题属于通用的“输入预算失真 + 草稿晋升缺少质量护栏 + 最终定级未验证报告形态”，不是 P04/K12 专属逻辑缺陷。

## Scope

### In Scope

- Editor1 实际输入 pack 的排序、去重、截断、预算上限与 telemetry。
- LLM 成功、失败、fallback 的显式 metadata。
- 多轮草稿的 deterministic narrative-quality assessment 与“保优晋级”。
- finalizer 仅消费 canonical / best draft，而不是盲目消费最新 draft。
- report level 同时考察 evidence coverage 与 report-form synthesis quality。
- 区分 actual prompt usage 与 full-state footprint。
- 面向通用报告质量的回归测试与受限 live 验证，不为 P04/K12 写特化规则。

### Out Of Scope

- 新增 provider、search lane、source family 或外部数据源。
- 为 P04/K12、行业、地区、公司、关键词、URL 写 query-specific 规则。
- 修改 `EvidenceBundle` / citation / public API schema。
- 完整 50-query live 压测。
- 调整任务编排语义、run 状态机或持久化 schema。

## Explicit Prohibitions

实施阶段明确禁止：

- 通过硬编码 section 标题、行业词、区域词、公司名来“修好” P04/K12。
- 以删除关键 claim、source-family coverage 或 region coverage 的方式换取预算通过。
- 仅靠拉高 token 上限掩盖 context-pack 选择失真。
- 在没有质量比较的情况下用最新 draft 覆盖历史合格 draft。
- 把 evidence 列表排版得更像报告，却不增加 synthesis、comparison、transmission chain、limitations 等叙事结构。
- 在本 PLAN 中顺带修正无关生产问题或做广泛重构。

## General Report Quality Standard

以下标准是通用报告质量标准，不得针对 P04/K12 定制：

### Minimum Narrative Standard

一份可晋级的报告正文至少应具备：

- 明确研究对象、时间范围与结论边界。
- 不少于一个跨来源综合段，而不是逐条证据罗列。
- 不少于一个对比或分层说明，例如政策 vs 企业披露、现状 vs 预期、区域差异、供需链条差异。
- 不少于一个传导链条或机制解释段，说明“信息如何影响行业/公司/项目”。
- 明确的风险、不确定性、证据缺口或反例说明。
- 来源说明不能只以原始 ledger 充当正文主体。

### Ledger Rejection Standard

以下任一成立，草稿不得被视为 `level_3` 候选：

- 正文主体主要由 claim/evidence 条目堆叠组成。
- 章节存在英文占位或模板残留。
- 缺少综合、对比、传导链条、局限性中的两项及以上。
- 虽有大量证据，但正文没有把证据组织成结论链和解释链。

### Level Gate Standard

- `level_3` 必须同时满足 evidence gate 与 report-form gate。
- `level_2` 允许证据较充分但综合叙事不足、对比不足、机制解释不足或局限性不足。
- 若 evidence 足够但报告形态退化为 ledger，只能停留在 `level_2` 或触发保留旧草稿。

## Design Direction

### Budgeted Editor Input Pack

- 以 claim coverage、evidence/source quality、source-family diversity、region match、time relevance 为主排序因子。
- 对实际送入 Editor1 的 evidence / source 摘要做去重与硬预算控制。
- 同时记录：
  - `prompt_selected_ids`
  - `prompt_dropped_ids`
  - `drop_reasons`
  - `prompt_estimated_tokens`
  - `prompt_budget_limit`
  - `prompt_budget_status`
- `state_footprint_estimated_tokens` 单列保存，不得再冒充实际 prompt usage。

### Preserve-Best Draft Promotion

- 为每轮 draft 生成 deterministic quality summary。
- 至少检查：章节完整性、分析段密度、ledger 占比、跨来源综合、对比、传导链条、风险/局限、来源说明。
- 新 draft 只有在“达到最低 narrative 标准且不弱于 canonical best draft”时才能晋级。
- 若 LLM 失败、新稿退化或预算降级导致正文劣化：
  - 保留上一版 canonical narrative body；
  - 记录 `retained_previous_draft=true`；
  - fallback 仅在没有历史合格稿时允许进入正文路径。

### Finalizer And Report-Level Gate

- finalizer 只消费 canonical / best draft，而不是盲目消费最新 draft。
- 若最新 draft 退化，则 finalizer 保留 canonical narrative body，仅追加 level/audit 说明。
- report level 必须把 evidence sufficiency 与 narrative form 一起纳入判断。
- level 判定 metadata 需要能解释：为什么给到该等级、为什么保留旧稿或拒绝新稿。

## Real-World Validation Plan

本节是当前 phase 的真实验收蓝图，未完成前不得开始生产实现。

### Validation Goal

证明修复后的机制能通用地阻止“后续轮次低质量 ledger 草稿覆盖先前合格叙事草稿”，并且能让 prompt budget 度量真实反映 Editor1 输入，而不是状态总量。

### Acceptance Cases

1. Synthetic narrative-preservation fixture
- 构造“首轮 narrative 合格、次轮 ledger 退化”的固定输入。
- 期望：系统保留首轮 canonical draft，不因次轮 evidence 更多而降级正文。

2. Synthetic budget-trim fixture
- 构造超预算输入 pack。
- 期望：只裁剪重复/低优先项，claim/source-family/region 的必要覆盖仍保留。
- 输出 telemetry 必须展示 selected/dropped IDs 与原因。

3. P04 limited live case
- 不要求把 P04 调成 `level_3`，只要求报告正文不再退化为 ledger，且 budget telemetry 与 draft promotion 行为可解释。

4. K12 limited live case
- 与 P04 相同，验证通用机制，而不是特化行业逻辑。

### Real-World Pass Criteria

同时满足以下条件才算本 PLAN 的 live gate 通过：

- P04 与 K12 都能稳定产出 dossier 和 `FINAL_REPORT.md`。
- 两个 live case 的最终正文都不是 ledger 主体，不含英文占位章节。
- 若某轮新稿退化，最终正文会保留先前合格 narrative draft，而不是被低质量新稿覆盖。
- telemetry 能明确区分 `prompt_estimated_tokens` 与 `state_footprint_estimated_tokens`。
- prompt budget 若超限，必须可见选择/丢弃明细，且不以删除关键 coverage 为代价。
- `level_3` 不会授予明显 ledger 化正文；如 evidence 足够但叙事不足，应降为 `level_2` 或保留旧稿。

### Failure Classification

live 或测试失败时必须归类，不得笼统写“质量不达标”：

- `prompt_budget_accounting_regression`
- `draft_promotion_regression`
- `narrative_quality_regression`
- `report_level_gate_regression`
- `fallback_visibility_regression`
- `research_contract_regression`

## Agent Execution Contract

- `invest_project_director`
  - 只负责 PLAN、验收口径、分工、phase gate、风险记录。
  - 本阶段不改生产代码。
- `invest_agent_architecture_builder`
  - 负责内部契约设计：input-pack、draft quality rubric、promotion state machine、report-level gate。
  - 写入范围仅限 PLAN 允许的设计/接口说明与必要测试设计，不改 public contract。
- `invest_feature_programmer`
  - 负责后续实现 `packages/research_harness/**` 与对应测试。
  - 不得修改 protected contracts，不得引入 query-specific 规则。
- `invest_code_quality_checker`
  - 负责 ruff、compile、focused pytest、研究工作流 contract checklist。
  - 先判是否为既有噪音，再判是否为本次回归。
- `invest_functional_validator`
  - 负责 narrative quality、draft promotion、budget telemetry、P04/K12 limited live 验证。
  - 重点验证“通用机制是否成立”，不是“个案是否看起来更好”。
- `invest_project_summarizer`
  - 仅在 Done Condition 达成后执行，评估是否需要沉淀成更通用的质量 gate 资产。

## Group 2 Assignments

### Group 2A - Architecture Builder

Owner: `invest_agent_architecture_builder`

Write scope for next implementation turn:
- `.agent/PLANS/report-narrative-context-budget-remediation-v1.md`（必要时仅补设计细节）
- 设计说明中涉及的内部 contract notes

Responsibilities:
- 定义 Editor1 actual-input pack contract。
- 定义 draft quality rubric 与 promotion state machine。
- 定义 finalizer canonical-draft consumption contract。
- 定义 level gate 的通用 narrative criteria。

Deliverables:
- 一份可直接指导编码的内部设计清单。
- 每项设计与现有 protected contract 的边界说明。

### Group 2B - Feature Programmer

Owner: `invest_feature_programmer`

Planned module ownership for later implementation:
- `packages/research_harness/**`
- `tests/test_research_harness_graph.py`
- `tests/test_report_quality_inspect.py`
- `tests/test_graph_provider_backed_smoke_matrix.py`

Responsibilities:
- 实现 actual-input budget telemetry。
- 实现 preserve-best draft promotion。
- 实现 finalizer canonical-draft protection。
- 增加 narrative vs ledger 的 focused regression fixtures。

Non-goals:
- 不扩展 provider/source/router。
- 不动 public schema。
- 不为 P04/K12 添加特化逻辑。

## Group 3 Validation Assignments

### Group 3A - Code Quality Checker

Owner: `invest_code_quality_checker`

Validation scope:
- `python -m ruff check packages/research_harness tests`
- `python -m compileall -q packages/research_harness`
- `pytest -q tests/test_research_harness_graph.py -k "editor1 or finalize or report_level or context_pack"`
- `pytest -q tests/test_report_quality_inspect.py`
- `pytest -q tests/test_agents_workflow.py`
- `pytest -q tests/test_research_api.py`
- `pytest -q tests/test_research_provider_integration.py`
- `pytest -q tests/test_deepseek_provider.py`

Required judgment:
- 明确区分本次改动引入的 regression 与仓库既有噪音。
- 若 research contract 需要变化，必须退回 Director Gate，不得由验证角色默许。

### Group 3B - Functional Validator

Owner: `invest_functional_validator`

Validation scope:
- narrative-preservation fixture
- budget-trim fixture
- P04 limited live gate
- K12 limited live gate

Required artifacts:
- 每个 case 的 final report 结论摘要
- canonical draft / latest draft 的比较说明
- prompt budget telemetry 摘要
- level decision rationale

## Milestones And Phase Gates

### Phase 0 - Freeze Baseline And Acceptance Fixtures

Objective:
- 固化 narrative-vs-ledger 退化基线与通用验收 fixture。

Acceptance:
- 测试能识别 ledger 不是深度报告。
- fixture 不依赖 P04/K12 专属关键词、行业、公司或 URL。
- 有“首稿更优、次稿退化”的稳定样本。

Completion gate:
- Director 确认验收标准与 fixture 口径稳定。
- 才能进入 Phase 1。

### Phase 1 - Implement Budgeted Input Pack

Objective:
- 让 Editor1 的实际 prompt 输入可预算、可解释、可回归。

Acceptance:
- actual prompt pack 不超过预算上限。
- telemetry 清晰区分 prompt usage 与 state footprint。
- 裁剪不破坏必要 claim/source-family/region coverage。

Completion gate:
- Group 3A focused tests 通过。
- Group 3B synthetic budget-trim fixture 通过。

### Phase 2 - Implement Preserve-Best Draft Promotion

Objective:
- 阻止低质量新稿覆盖历史合格叙事稿。

Acceptance:
- 新稿退化时保留 canonical best draft。
- ledger 输出不能晋级覆盖 narrative draft。
- fallback 行为可见、可解释。

Completion gate:
- Group 3A focused tests 通过。
- Group 3B narrative-preservation fixture 通过。

### Phase 3 - Strengthen Finalizer And Report-Level Gate

Objective:
- 让 finalizer 与等级系统真正感知报告形态质量。

Acceptance:
- `level_3` 同时要求 evidence gate 与 report-form gate。
- finalizer 不降级 canonical narrative body。
- metadata 能解释等级与草稿选择原因。

Completion gate:
- Group 3A research contract checks 通过。
- Group 3B level decision validation 通过。

### Phase 4 - Regression And Limited Live Validation

Objective:
- 在真实 provider-backed 流程中证明机制通用有效。

Acceptance:
- P04/K12 都能产出完整 dossier/final report。
- 正文具备执行摘要、方法/边界、综合分析、比较或机制链、风险与不确定性、结论与来源说明。
- ledger 不再主导正文，英文占位章节消失。
- budget 超限时表现为可解释降级，不覆盖历史合格 narrative draft。

Completion gate:
- Group 3A 与 Group 3B 全部通过。
- Director 复核无 protected-contract 外溢。

## Validation Loop

```powershell
python -m ruff check packages/research_harness tests
python -m compileall -q packages/research_harness
pytest -q tests/test_research_harness_graph.py -k "editor1 or finalize or report_level or context_pack"
pytest -q tests/test_report_quality_inspect.py
pytest -q tests/test_graph_provider_backed_smoke_matrix.py
pytest -q tests/test_agents_workflow.py
pytest -q tests/test_research_api.py
pytest -q tests/test_research_provider_integration.py
pytest -q tests/test_deepseek_provider.py
```

Limited live gate 只运行现有 smoke runner 的 P04/K12，不扩展到 50-query。

## Continue Rule

每个 phase 在以下条件同时满足时自动进入下一 phase：

- 当前 phase 的 acceptance criteria 达成；
- Group 3 required validation 通过；
- 没有权限、依赖、credential、网络或 provider blocker；
- 没有触发未授权 protected-contract 变更；
- 没有出现无法安全修复的回归。

本 PLAN 为实施蓝图；除 stop condition 外，不以“阶段总结”作为默认停点。

## Stop Conditions

- 需要未授权的 protected-contract 变更。
- live credential、额度、provider 连通性缺失。
- 连续两轮修复仍导致历史正确报告或 focused tests 退化。
- 输入预算只能通过删除关键 claim/source-family/region coverage 才能满足。
- 用户明确要求暂停，或明确要求保持 planning-only。

## Done Condition

- 低质量 fallback / ledger 草稿不再覆盖历史合格 narrative 草稿。
- Editor1 actual prompt pack 具备硬预算与准确 telemetry。
- `state_footprint_estimated_tokens` 不再冒充 prompt usage。
- `level_3` 不会授予 ledger 化正文。
- focused tests、research contract checks、P04/K12 limited live gate 全部通过。
- PLAN、STATUS、必要技术路线节点已按实施结果更新。

## Progress

- [x] 根因复核完成，并确认不是 resume 覆盖或个例问题。
- [x] Director Gate 已补充真实验收、Group2/3 分工、禁止范围与通用质量标准。
- [x] Phase 0 acceptance fixtures implemented.
- [x] Phase 1 budgeted input pack implemented.
- [x] Phase 2 preserve-best promotion implemented.
- [x] Phase 3 finalizer/report-level gate implemented.
- [x] Phase 4 regression and limited live validation completed.

## Risks And Rollback

- 形态质量 gate 可能误伤简洁但有效的报告：采用多指标组合，而不是仅看篇幅。
- 输入裁剪可能损失长尾 recall：必须记录 dropped IDs 与原因，且优先删除重复或低优先项。
- 保留旧稿可能漏掉后续补证：允许新稿在质量不退化前提下晋级，并把补证信息保留在 audit metadata。
- 本 PLAN 的回滚不涉及持久化 schema，只回滚 draft promotion、budget accounting、finalizer 选择逻辑。

## Phase 4 Validation Record

### Focused And Contract Regression

- `pytest -q tests/test_research_harness_graph.py -k "context_pack or narrative or editor1 or finalize or report_level or claim_strength_guard"` -> `17 passed`.
- `pytest -q tests/test_report_quality_inspect.py tests/test_graph_provider_backed_smoke_matrix.py tests/test_agents_workflow.py tests/test_research_api.py tests/test_research_provider_integration.py tests/test_deepseek_provider.py` -> `42 passed`.
- `python -m compileall -q packages/research_harness` -> passed.
- 本轮修改文件 Ruff 通过。
- 全目录 `python -m ruff check packages/research_harness tests` 仍有 8 个既有 lint 项，位于本轮未修改的 `plan_semantic.py`、`retrieval_bridge.py`、`schemas.py` 和 `tooling/*`，未判作本轮回归。

### Limited Live Gate

- P04 live: `data/tmp/report_narrative_context_budget_live/P04_final_v3/`。
  - 10/10 search events success；32 个来源、48 条证据。
  - Editor1 actual prompt 在 1600 token 上限内；无 over-budget context pack。
  - 最终报告为 `level_2`，理由为 `obl_location_precision` 未覆盖。
  - finalizer replay 后章节唯一且语义化：政策、整车、电池、零部件、综合评估、传导链、风险和结论。
- K12 live: `data/tmp/report_narrative_context_budget_live/K12_final_v2/`。
  - 10/10 search events success；最终报告正文基于真实 live checkpoint 重放。
  - Editor1 两轮分别为 `1573/1600`、`1592/1600`，均 within budget。
  - response payload 从旧基线约 67 MB 降至约 620 KB；`io_snapshot` 不再包含 `state_before_full/state_after_full`。
  - 最终报告为 `level_2`，章节覆盖环评、企业投资、产业化、资源、交通与基础设施、传导链、风险和结论。

### Functional Quality Classification

`report_quality_inspect.py` 对两例均通过正文长度、正文占比、章节完整性、source-family mismatch、P0 issue、limitations 和 context budget 检查；整体仍标记 `workflow_pass_product_fail`，唯一失败项是 `obl_location_precision` 未覆盖。该缺口已被 final report 的 `level_2` 和等级理由显式暴露，属于后续 source routing / location parsing remediation，不属于本 PLAN 的叙事与 context budget 范围。

## PLAN Completion Report

### What Was Done

- 实现 Editor1 真实输入 pack 的去重、选择、硬预算和 selected/dropped telemetry。
- 将实际 prompt token 与 graph state footprint 分离，未实测 prompt 的节点标为 `unbudgeted`。
- 移除公开 context-pack IO snapshot 中的 full-state 副本，保留 keys 与摘要。
- 引入 `narrative_v2` 报告质量门，识别 ledger、占位标题、重复标题和泛化标题。
- 实现 canonical draft 保优，以及无 canonical 时对重复/泛化章节的确定性重建。
- 将 chief-gate 权威 obligation coverage 传递到 LangGraph state 和 finalizer。
- 报告等级同时依赖 report form 和 evidence obligation；人工批准不再自动消除证据 blocker。
- 扩展中英文 claim-family 到中文研究章节的通用映射。

### Implemented Capability

系统现在能够在 provider-backed 多轮研究中保留或重建结构化研究叙事，避免低质量 evidence ledger 覆盖正文；context budget 反映真实 Editor1 输入；证据义务未覆盖时报告仍可生成，但会诚实降为 `level_2` 并说明原因。

### Before And After Examples

1. P04 安徽新能源汽车：
   - 改动前：报告呈结论/证据条目罗列，重复或英文模板标题，证据缺口仍可能显示 `level_3`。
   - 改动后：报告按政策、整车、电池、零部件、综合判断、传导链和风险组织；`obl_location_precision` 未覆盖时固定为 `level_2`。
2. K12 若羌盐湖锂钾：
   - 改动前：多个“专题证据分析”重复章节，来源类别可误显示为 0，response context pack 约 67 MB。
   - 改动后：章节语义化为环评、企业投资、产业化、资源、交通与基础设施；source-family 元数据缺失时如实说明；response 降至约 620 KB，实际 prompt 保持在 1600 token 内。

### Files Created Or Modified

- `packages/research_harness/context.py`
- `packages/research_harness/real_nodes.py`
- `packages/research_harness/runner.py`
- `packages/research_harness/state.py`
- `tests/test_research_harness_graph.py`
- `data/tmp/report_narrative_context_budget_live/P04_final_v3/`
- `data/tmp/report_narrative_context_budget_live/K12_final_v2/`
- `.agent/PLANS/archive/report-narrative-context-budget-remediation-v1.md`
- `.agent/STATUS.md`
- `docs/technical-roadmap-evolution.md`

### Remaining Risks And TODOs

- K12 query requirement/location parser 将整段问题拆成地域列表，`target_location` 明显异常；需独立 source-routing/location-parsing PLAN。
- P04/K12 的 location obligation 均未覆盖，不能视为完整深度研究证据闭环。
- live graph 单次耗时约 6-10 分钟，应继续使用 fast fixture gate + 少量 live acceptance，而非每次改动重跑全图。
- DeepSeek planner 仍出现 `ProviderParseError` 后 deterministic fallback；不影响本 PLAN 通过，但需单独治理 provider JSON 稳定性。
- 全目录仍有 8 个既有 Ruff lint 项。

## Next Action

本 PLAN 已完成并归档。若继续处理最重要的产品风险，下一 PLAN 应聚焦通用 location parser 与 exact-local obligation routing，不应为 P04/K12 写 query-specific 规则。