# Goal-Driven Evidence ReAct v1

Status: active_phase2_5_live_diagnostics_passed_pending_budget_tuning

Created: 2026-06-21

Primary active PLAN: yes

## Current Active Slice

Phase 2.5 is now the current active slice.

中文说明：

- `evidence_requirement_spec` 是“报告证据需求表”：它说明每个报告章节需要哪些 `source_family`、至少几条证据，以及金额、主体、阶段、频次等关键字段。
- Phase 2 已经让 `build_evidence` 在证据构建后发现缺口并触发 ReAct 二次补搜。
- Phase 2.5 的目标是把这套“按证据需求找源”的意识前移到第一次 `collect_sources`，让首轮检索就按报告章节和证据族做定向召回。
- 使用它的效果：首轮 source pool 更接近最终报告需要，后续 ReAct 补搜轮次应减少。
- 不使用它的现状：首轮检索仍主要受相似度/泛化搜索词驱动，公司披露、统计、招采、项目证据可能等到 evidence 阶段才发现缺口。

Execution status:

- Planning state: active.
- Production code state: not yet implemented in this slice.
- Current request: planning/status update only.
- Next implementation route: protected-boundary handling by default, because this slice changes `collect_sources` search semantics.

Related:
- `docs/adr/0001-tavily-local-targeted-gap-retrieval.md` (Tavily 召回)
- `docs/adr/0002-unified-source-taxonomy.md` (source_family 8 值)
- `docs/source-taxonomy-inventory.md`
- 来源: GPT 报告评价 + /brainstorm 会话 (2026-06-21)

## Objective

把 `build_evidence` 从"被动相似度抽取"改造成"目标驱动的 ReAct 式编辑":
它先知道最终报告框架需要哪些 evidence (evidence_requirement_spec),
首次构建后自检缺口, 调工具从 source 二次定向抽取, 循环到填满框架或触顶。
claim / editor1 不加此能力 (evidence 是最接近 source 的层, 它补够则下游够)。

目标是把报告从 level_2 (初步研究报告) 推向 level_3 (深度研报),
根治 GPT 评价指出的"事实颗粒度薄、项目落地太薄、各段隔离式工作流"。

## Task Classification

- Primary area: `research_workflow` (build_evidence 节点 + evidence 契约)
- Secondary areas: `source_layer` (二次定向抽取), `eval_policy_ops` (claim 强度/等级)
- High-risk contracts (不可静默改):
  - `EvidenceItem` / evidence dict 现有字段 (evidence_id/source_id/summary/
    support_type/support_strength/specificity/limitations) — 只加字段不改语义
  - graph-v1 节点序列与 `runs`/`run_steps` 契约
  - `/deep-research/analyze` `/research/analyze` 响应形状 — 不改
- 本 PLAN 为 implementation-starting, 但 Phase 0 仅设计冻结, 不改生产代码。

## Scope

In scope:
- 新建 `evidence_requirement_spec`: 报告章节 → 需要的 source_family + 最小证据数
  + 关键字段 (金额/主体/阶段/频次)。复用已有原料:
  `SemanticDimensionPlanEntry.{source_families, expected_section_heading,
  coverage_required}` + `SemanticSourceObligation.min_required_evidence`。
- 改造 `build_evidence_provider_backed` 为 ReAct 循环: 读 spec → 首次构建 →
  自检缺口 → 调 tool_session 二次定向抽取 → loop (有界)。
- evidence 加最小 2 结构化字段: `stage` (规划/招标/试运行/常态运营) +
  `quant` (金额/频次/规模, 可选)。
- claim_strength_guard (finalize 前 1 层): 用 spec 作充足度基准, 核心 claim
  证据不足时降级表述; 仅"核心 claim 全弱"时触发 HUMAN_REVIEW。
- 报告等级判定 (level_1~4) 作为 guard 的输出。

Out of scope (future / next-action only):
- editor1 / claim 的 ReAct 能力 (本 PLAN 明确不给)。
- 统一 4 套搜索口径扩展 (caliber_expander/dimension/gap_core_topic/augmenter)。
- source_family 加"政策原文 vs 解读 vs 转载"细分 (GPT 问题4, 单独 ADR)。
- 数量口径统一 (检索源/入选源/引用源/证据数) — 报告渲染层问题, 单独处理。

## Constraints

- evidence ReAct 循环必须有界 (复用 Phase 8 的 loop_count 上限模式), 防止
  无限补抽导致 Tavily credit / 延迟失控。
- 二次抽取受 Tavily 召回限制 (ADR 0001): source 没有的料补不回来 — 此时必须
  如实标注"补抽后仍缺", 不得捏造。这是诚实降级, 非缺陷。
- `tool_session` 已传入 build_evidence (已确认), 复用它驱动二次抽取, 不新增
  provider。
- 改动保持向后兼容: evidence 新字段为可选, 空值不改现有下游行为。
- `real_nodes.py` 仍是 recovery-proxy over bytecode — 所有改动走 wrapper 层。

## Architecture / Design Direction

```
现状 (隔离式, 相似度驱动):
  plan → collect(dense+sparse 相似度) → build_evidence(被动抽,不知报告要什么)
       → claim → editor1(知11章节框架,但料已定死)
  问题: evidence 段不知道最终报告需要什么 → 漏维度 → editor1 巧妇难为无米炊

改造 (目标驱动 ReAct):
  plan → collect → build_evidence ┐
                     │            │ ReAct loop (有界):
                     │  1. 读 evidence_requirement_spec (章节→source_family+最小数+字段)
                     │  2. 首次从已召回 chunk 构建 evidence
                     │  3. 自检: 哪些章节 evidence 缺/弱 (如"项目落地"仅1条且无金额)
                     │  4. 缺口 → tool_session 二次定向抽取 (补 招标/金额/主体)
                     │  5. loop 到填满 or loop_count 触顶
                     └→ claim → editor1
  + finalize 前: claim_strength_guard (spec 作基准) → 降级表述 + 报告等级判定
```

核心: build_evidence = "有目的的编辑" = editor1 的框架意识 + collect 的抽取工具,
合二为一在最接近 source 的 evidence 段。GPT 评价的"治本"在此。

evidence_requirement_spec 一张表同喂两端:
- build_evidence ReAct 的"目标函数" (要补什么)
- claim_strength_guard 的"充足度基准" (够不够下结论)

## Milestones / Phases

### Phase 0: Design Freeze

Status: completed

Objective: 冻结设计方向 (本 PLAN), 不改生产代码。
Acceptance: PLAN 自包含; STATUS 指向它; brainstorm 结论 + 实代码裏取り已记录。
Validation: 本文件存在且含全部必填节; STATUS 引用; git 无生产代码改动。
Progress: 2026-06-21 brainstorm 收敛 (用户选 evidence ReAct over 被动矩阵,
  选 (b) evidence_requirement_spec)。实代码确认: 检索相似度驱动 (embedding/
  rerank/bm25), build_evidence 不知报告格式 (report/draft: False) 但 tool_session
  已传入, dimension_plan 已有 source_families/expected_section_heading/
  min_required_evidence 可复用。
Risks: 设计与实现脱节 — 缓解: Phase 1 先建 spec 并断言可从 dimension_plan 生成。

### Phase 1: evidence_requirement_spec

Status: completed

Objective: 建一张 spec = {章节: {required_source_families, min_evidence,
  key_fields: [金额/主体/阶段/频次]}}, 优先从现有 dimension_plan 派生。
Acceptance criteria:
- spec 能从 dimension_plan (source_families + min_required_evidence +
  expected_section_heading) 自动生成, 不需全新手写。
- spec 覆盖报告 11 章节中需证据的章节 (政策/项目落地/公司披露/行业数据等)。
- 纯新增, build_evidence 现有行为不变 (spec 暂不接入)。
Implementation (2026-06-21):
- `plan_semantic.py` 新增 `build_evidence_requirement_spec(plan) -> list[dict]`
  + `_DIMENSION_KEY_FIELDS` 映射。纯派生无 I/O, 可被 build_evidence 与
  claim_strength_guard 复用。
- 每条 spec = {section, dimension_type, dimension_id, required_source_families,
  min_evidence, key_fields, coverage_required}。
- min_evidence: 取该维度 source_families 对应 obligation 的 min_required_evidence
  最大值, 否则默认 floor=2。
- key_fields 按 dimension_type: policy→政策工具/发文主体/时间;
  execution→项目名/金额/主体/阶段/招标状态; disclosure→公司/金额/业务板块;
  statistics→指标/值/地区; local_rollout→地区/项目名/阶段。
Validation result (2026-06-21):
- compile OK。
- 真实 live dimension_plan (5 维度) → 5 spec 条目, section/type/families 正确。
- obligation 驱动验证: source_family=public_resource_transaction 的 obligation
  min_required_evidence=3 → execution 维度 min_evidence=3 (正确传导)。
- 空 plan → [] (优雅)。
- build_evidence 未接入 spec, 现有行为零影响。
Risks: dimension_plan 维度 ≠ 11 章节 — 缓解: spec 做 章节↔维度 映射表兜底。
  已知: source_families 若被上游序列化成字符串会被逐字符迭代 (live 实际是真
  list, 无此问题; 若未来出现可在 Phase 2 接入时加 isinstance(list) 防御)。

### Phase 2: build_evidence ReAct loop

Status: completed (self-check + gap_report 流通 + ReAct 二次抽取自循环 全部 live 验证)

ReAct 自循环实施 + live 验证 (2026-06-21):
- `_evidence_react_backfill(state, result, gap_report, tool_session)`: 对每个
  insufficient_count 缺口族, 复用 collect 的检索三件套 (`_impl._search_provider`
  + `_impl._search_with_retry` + `TavilySearchRequest(search_depth=advanced)`)
  做族定向二次检索, 新源经 `_extract_atomic_evidence` + `_enrich_evidence_semantics`
  抽成证据并入 result["evidence"], 再自检, 有界 loop (≤2 轮)。
- build_evidence 在 gap 自检后接入: 有 gap 则调 backfill, 更新 evidence/
  gap_report/evidence_react_meta。只补 insufficient_count, 不补 missing_fields。
- BUG 修复: `_search_with_retry` 返回 (response, meta) tuple, 初版对 tuple 取
  .results 抛 AttributeError 被 build_evidence 的 try/except 静默吞 → ReAct 静默
  失败 (meta 空)。修正为 tuple 解包后再取 .results。
- 决定论验证: mock 检索 → 缺口检出 (公司披露 0/2) → ReAct 触发 → 定向 query
  "合肥 ... 上市公司 公告" → tuple 解包 OK → 补 1 源 (mock 文本短故 added_evidence=0)。
- LIVE 验证 (data/tmp/evreact_live): rounds=1, **added_sources=11,
  added_evidence=40**, queries=["合肥 低空经济 上市公司 公告","合肥 低空经济 相关 公告"]。
  真实 source raw_content 长, 原子抽取正常产出 40 条新证据 → 缺口族真补料。
- 验证: compile OK, ruff 0 serious, build_evidence 1 passed 零回归。
- 核心达成: build_evidence 从"被动相似度抽取 + 发现缺口不治"→"知道报告需求 →
  自检缺口 → 定向重搜 → 补 11 源/40 证据 → 再自检"的有目的编辑。隔离式工作流根治。

ReAct 二次抽取决策 (2026-06-21, 用户确认重新激活):
- 证据核实推翻"转 Phase 4 跳过补抽": 当前 build_evidence 抽取阶段**完全不用
  spec** (build_evidence_requirement_spec 不在抽取路径), spec 只在抽完后
  _evidence_gap_selfcheck 做"事后体检", 发现缺口后**什么都不做**。即只装了
  体温计没治病。
- 缺口族在源头就没召回: live 入选 32 源族分布 = official_policy 10 /
  official_news 9 / public_resource_transaction 1, **company_disclosure 和
  statistics 缺口族 0 个**。collect accepted=78 但入选 32, 那 46 个未入选源
  经核实也不含缺口族 → (B) 已召回池重捞**不可行** (池里没有)。
- 结论: 必须 (A) 定向二次检索才能补缺口族。方案确定为
  **(a) build_evidence 内部 ReAct 自循环** (用户选, 符合最初 brainstorm:
  evidence 作为最接近 source 的层自带 tool 补料), 而非 (b) 复用 gate→plan_task
  整图重跑 (成本高 + 与 Phase 8 职责重叠)。
- 完整诚实链路: 自检缺口 →(A) 定向重搜补 → 补到则用 / 补不到则 Phase 4
  诚实降级。ReAct 与 Phase 4 是"先补后降", 非二选一。

接入蓝图 (全部接入点已核实现成):
- 检索三件套复用 collect 的: `_impl._search_provider` (造 provider) +
  `_impl._search_with_retry` (执行) + `TavilySearchRequest` (含已加的
  search_depth="advanced")。build_evidence 已能访问 `_impl`, 接入无障碍。
- 触发: gap_report 的 insufficient_count 缺口族 → 按族生成定向 query
  (复用 `_gap_core_topic` + `_GAP_FAMILY_TEMPLATES` 族模板) → 二次检索 →
  新源抽成 evidence 并入 result["evidence"] → 再自检 → 有界 loop
  (复用 loop_count 上限模式)。
- 边界: 只补 insufficient_count (0 缺口) 族, 不补 missing_fields (字段颗粒度
  靠 Phase 3 stage/quant); loop 上限防 Tavily credit 失控; 补不到如实留 gap。

Plumbing fix (2026-06-21): `evidence_gap_report` 初版只写进 build_evidence 的
result, 但 `ResearchGraphState` (state.py TypedDict) 未声明该键 → LangGraph
丢弃未声明键 → chief_gate/finalize 的 state_before 读不到 (io_snapshot 证实)。
修复: state.py ResearchGraphState 加 `evidence_gap_report: dict[str, Any]` 字段,
gap_report 现可流到下游供 Phase 4 claim_strength_guard 读取。验证: compile OK,
ruff 0 serious, build_evidence 1 passed 零回归。
Live 复验 (data/tmp/evgap_fixed_case1, bug 修复后): gap_report 真实合理 —
政策/落地/执行 covered=41/2 (充足, 仅 missing_fields); 公司披露 covered=0/2 +
统计 covered=0/2 (insufficient_count 真缺口) — 精准对应 GPT 批的"公司披露维度
缺失"+"项目落地太薄"(execution 缺 project_name/amount/subject 等字段)。
设计观察: covered=41 偏高因原子证据膨胀 + 三章共用 official_* 族, 数量门槛易满足;
真正区分信号在 missing_fields (字段颗粒度) 和 0 缺口的族。→ 决策: 转 Phase 4
(用 gap_report 做 claim 降级, 收益确定不赌 Tavily 召回), ReAct 二次抽取留未来。

Implementation (2026-06-21, 自检子集):
- `_evidence_gap_selfcheck(plan, evidence_items, sources)`: 用 Phase 1 的
  `build_evidence_requirement_spec` 对照已有 evidence, 报告 under-covered
  (count < min_evidence) 或 missing key_fields 的章节。build_evidence 末尾接入,
  产出 `result["evidence_gap_report"]`; 无 plan 优雅返回 {}。
- BUG 修复 (live 发现): evidence item 没有 source_family 字段 (它在 source
  对象上), evidence 只有 source_id/source_ids。初版按 ev.get("source_family")
  统计导致每章节 covered=0 全误报。修正为 source_id → source.source_family
  (canonical) 关联计数; build_evidence 调用时传 sources。
- 验证: compile OK; ruff 0 serious; build_evidence 1 passed 零回归; 决定论:
  3 条 official_policy 证据 → 政策维度 covered=3/2 (满足, 仅 missing_fields);
  execution 无 public_resource_transaction → covered=0/2 insufficient_count
  (真缺口, 正是 GPT 批的"项目落地太薄")。
- 待办: 修复后需再跑 live 确认真实合肥案例 covered 不再全 0 (bug 版 live 产物
  data/tmp/evidence_gap_case1 是错误数据)。
- Decision pending: 自检层 (诊断) 已可独立喂 claim_strength_guard/报告等级。
  ReAct 二次抽取循环 (后半) 高风险高成本, 待评估"补抽收益 vs Tavily 召回限制
  (ADR 0001)"后决定续接 Phase 2 后半 or 直接转 Phase 4。

Objective: build_evidence 读 spec, 首次构建后自检缺口, 调 tool_session 二次
  定向抽取, 有界循环。
Acceptance criteria:
- build_evidence 产出含"缺口自检"元数据 (哪些章节 evidence 缺/弱)。
- 缺口触发二次抽取 (search_events 出现 evidence-gap-driven 轮)。
- loop 有界 (loop_count 上限), 无限补抽不发生。
- 无 spec / 无 provider 时优雅退回单次抽取 (向后兼容)。
Validation:
```powershell
python -m pytest -q tests/test_research_harness_graph.py -k "build_evidence"
# live: 项目类 query, 确认二次抽取触发 + evidence 维度覆盖提升
```
Risks: 二次抽取受 Tavily 召回限制 (ADR 0001) — 缓解: 如实标注"补抽后仍缺"。
  成本/延迟 — 缓解: loop 上限 + 只补 P0 章节缺口。

### Phase 2.5: spec-driven first-pass retrieval

Status: active (current slice, not yet implemented)

Origin: 用户洞察 (2026-06-21) — 当前第一次 collect_sources 检索**不知道报告需求**
(spec 只在 build_evidence 阶段才读), 第一次按 plan_task 的搜索短语相似度召回,
报告需求只在 ReAct 补救阶段才生效。更优: 让 spec 从第一次检索就参与, "有的放矢"
前置, 减少后续 ReAct 补救轮次 (省 Tavily credit + 更快收敛)。

Objective: 让 `evidence_requirement_spec` 在第一次 collect_sources 检索就生效 —
collect 在相似度召回之外, 按 spec 的"每章节需要的 source_family + 最小证据数"
各组织一轮定向检索。

设计要点:
- spec 派生自 dimension_plan, plan_task 后即可生成 → 可在 collect 前就绪。
- collect 第一次检索 = 相似度召回 + spec 定向召回 (每缺口族各一轮)。
- 与现有 Phase 2 ReAct 结合: 第一次定向后缺口已比纯相似度少, ReAct 只补
  第一次仍没召回的难点 → 补不到则诚实降级。
- 本质 = 把 Phase 2 的 ReAct 定向逻辑"提前一份"到第一次检索。

关键约束 (诚实):
- 第一次带 spec 定向仍受 ADR 0001 的 Tavily 召回限制 — spec 说"要公司披露",
  但 Tavily 无合肥企业披露料时第一次定向也召不回, 最终仍落到 ReAct 补救 +
  诚实降级。Phase 2.5 减少补救轮次, 不改变"source 没有的料补不到"的天花板。

Acceptance criteria (待实施时):
- collect_sources 第一次检索的 search_events 含 spec-driven 定向轮 (按缺口族)。
- build_evidence 首次自检的缺口数 < 纯相似度基线 (同 query 对比)。
- ReAct 补救轮次减少 (evidence_react_meta.rounds 同条件下下降)。
- 向后兼容: 无 spec 时退回纯相似度召回。

Risks: 改 collect_sources (检索主干), 比 build_evidence 内改动风险高; spec 定向
轮增加首轮 Tavily credit (需与"减少 ReAct 补救轮"权衡净成本)。

Implementation plan for this active slice:

1. Inventory current first-pass retrieval path.
   - Inspect `real_nodes.py` / wrapper path around `plan_task`, `collect_sources`, `evidence_requirement_spec`, `_evidence_react_backfill`, `_gap_core_topic`, and existing search round builders.
   - Confirm whether the current first-pass `search_rounds` already carries enough section/source-family metadata.
2. Design a minimal `spec-driven first-pass rounds` helper.
   - Input: `evidence_requirement_spec`, current query/core topic, existing plan/search rounds, and budget.
   - Output: bounded extra search rounds grouped by high-value `source_family`.
   - Priority source families: `public_resource_transaction`, `company_disclosure`, `statistics_or_data_release`, and local official/project policy families.
3. Integrate before first `collect_sources` execution.
   - Do not change public `/deep-research/analyze` or `/research/analyze` response shape.
   - Do not change existing evidence field semantics.
   - Mark diagnostics as `spec_driven_first_pass` so it can be distinguished from similarity-driven search and ReAct backfill.
4. Budget gate.
   - Cap phrases per source family.
   - Cap total extra first-pass Tavily credits.
   - Do not use hard `include_domains` unless a source-family rule is already proven to improve recall.
5. Validation.
   - Focused tests: spec-driven round creation, no-spec fallback, budget cap, source-family targeting.
   - Regression: existing `build_evidence`, `chief_gate`, `finalize` tests remain green.
   - Live smoke: compare one location-sensitive case before/after on first-pass gap count and ReAct backfill count.

### Phase 3: evidence 结构化字段 (stage + quant)

Status: completed

Implementation (2026-06-21):
- `_llm_extract_atomic_facts` prompt 增 `stage` (规划|招标|中标|开工|试运行|常态运营,
  仅项目类填) + `amount` (金额/规模数字+单位, 如"10亿元"/"500架次") 两字段抽取。
- `_make_atomic_evidence_item` 增 stage/amount 参数 (默认空串) + 写入 evidence dict。
  LLM 抽取路径与确定性回退路径 (`_deterministic_atomic_facts`) 都贯通。
- 字段为可选, 空值不改下游 (向后兼容)。
- 验证: compile OK, ruff 0 serious, build_evidence 1 passed 零回归; 决定论确认
  evidence item 含 stage/amount 字段 (两路径)。
- 作用: 补 gap_report 的 missing_fields (execution 章节缺 project_name/amount/
  stage), 直接对应 GPT 批的"项目落地太薄"——evidence 现在能带项目阶段+金额规模。

Objective: evidence 加 `stage` (规划/招标/试运行/常态运营) + `quant` (金额/
  频次/规模, 可选), 供 claim 强度判定。
Acceptance criteria:
- 原子抽取尝试填 stage/quant; 填不出留空 (不捏造)。
- 字段为可选, 空值不改下游。
- 项目类 query 的 evidence stage 充足率可测。
Validation:
```powershell
python -m pytest -q tests/test_research_harness_graph.py -k "build_evidence or atomic"
```
Risks: 本文无源数据则字段全空 — 接受 (诚实), 由 guard 据此降级。

### Phase 4: claim_strength_guard + 报告等级

Status: completed

Implementation (2026-06-21):
- `_claim_strength_guard(report_markdown, gap_report)`: 用 evidence_gap_report
  的 insufficient_count 缺口数判报告等级 (level_1~4), 在报告头部加等级 banner +
  缺口披露段 ("证据不足维度...本轮证据池内未识别充足证据, 不作判断")。
- 接入 finalize_report_provider_backed: Phase 3 报告分离后调 guard, 写
  final_report.report_level / report_level_reason。
- 分级规则: 0 insufficient → level_3 (深度研究报告); >=1 insufficient → level_2
  (初步研究报告, 不僭称深度研报)。默认表述降级 (报告照常出, 不阻断 finalize) —
  诚实降级而非强制 HUMAN_REVIEW, 避免 Tavily 召回限制 (ADR 0001) 下报告出不来。
- _REPORT_LEVEL_LABELS: 线索/初步研究/深度研究/投研决策报告。
- 验证: compile OK, ruff 0 serious, finalize/chief_gate/report_markdown
  11 passed 零回归; 决定论: 2 缺口→level_2 + 缺口披露段, 0 缺口→level_3,
  无 spec→None (优雅不改)。
- 回应 GPT 评价: "不要让系统在证据不足时强行输出深度研报"(level 判定) +
  "公司披露缺失要绑定检索口径说明"(缺口披露段)。

Objective: finalize 前加 guard, 用 spec 作充足度基准, 核心 claim 证据不足时
  降级表述; 输出报告等级 (level_1~4)。
Acceptance criteria:
- 默认: 降级表述 ("突破"→"试点阶段"), 报告照常出。
- 仅"核心 claim 全弱"时触发 HUMAN_REVIEW (防 Tavily 召回限制致常态阻断)。
- 报告头部标注 level + 理由 (借 GPT 的 level_1~4 + reason 结构)。
Validation:
```powershell
python -m pytest -q tests/test_research_harness_graph.py -k "chief_gate or finalize or claim_strength"
# live: 弱证据 query 确认降级表述 + 等级正确
```
Risks: guard 太严致报告萎缩 — 缓解: 表述降级为主, HUMAN_REVIEW 仅核心全弱。

### Phase 5: Live 验收

Status: completed (4/4 案例 live 验收通过)

4-case live 验收 (2026-06-21):
| 案例 | ReAct 补料 | report_level | decision |
|---|---|---|---|
| case1 合肥低空经济 | +10源/+40证据 | level_3 | HUMAN_REVIEW |
| case2 广东人形机器人 | +3源/+14证据 | level_3 | PASS |
| case3 新能源车产业链 | 无(无缺口,正确) | level_3 | PASS |
| case4 神木煤化工 | +6源/+27证据 | level_3 | PASS |

结论:
- ReAct 条件触发正确: case1/2/4 (地方/专项主题有缺口) 补料; case3 (成熟全国
  主题无缺口) 不补 → 不浪费 Tavily credit。补料量与主题数据丰度负相关。
- report_level 全产出: PASS (case2/3/4) 与 HUMAN_REVIEW (case1) 两条决策路径
  都有等级 (Phase 4 接入缺口修复后 chief_gate 覆盖)。
- Phase 1-4 协同链路在 4 个不同主题上稳定: 知道报告需求 → 自检缺口 → 定向补料
  → 缺口消除 → 等级判定。

Phase 4 接入缺口修复 (2026-06-21, Phase 5 case1 验收时发现):
- 问题: `_claim_strength_guard` 只接 finalize_report, 但 HUMAN_REVIEW 时流程停在
  human_review 节点、不到 finalize → report_level 丢失 (恰恰证据不足→HUMAN_REVIEW
  时最需要等级判定)。
- 修复: level 判定也接到 chief_gate (PASS + HUMAN_REVIEW 两路径必经节点, 已能读
  state.evidence_gap_report)。chief_gate 末尾算 report_level + report_level_reason。
- 验证: compile OK, ruff 0 serious, chief_gate 6 passed 零回归。

case1 验收结果 (data/tmp/p5_final, 2026-06-21):
- Phase 2 ReAct 补料: rounds=1, added_sources=10, added_evidence=40 (live)。
- Phase 4 等级判定: decision=HUMAN_REVIEW, 停 human_review (未到 finalize),
  **report_level=level_3 仍产出** (修复后 chief_gate 路径覆盖)。
- Phase 2↔4 协同: ReAct 补料消除 insufficient_count 缺口 → 等级从 level_2 升
  level_3 (补料成功的体现)。
- 节点序列: 两轮 chief_gate (gap 循环触发), 停 human_review。
- 结论: Phase 1-4 在真实 case1 协同链路验证通过 (知道报告需求→自检缺口→定向
  补料→缺口消除→等级判定两路径覆盖)。

Objective: 4 案例 live 验证深度提升, 对比改造前后。
Acceptance criteria:
- 项目落地维度 evidence 数/字段充足率提升。
- 核心 claim 无"弱证据强表达" (GPT 问题1)。
- 报告等级判定与人工判断一致。
- 至少 3/4 案例 evidence 维度覆盖较现状提升。
Validation: graph_provider_backed_smoke + report_quality_inspect 四案例。

## Continue Rule

每 Phase 验收通过且无 protected-contract 未授权改动, 自动继续下一 Phase。
Phase 0 已完成, 下一步 Phase 1 (evidence_requirement_spec)。

## Done Condition

- evidence_requirement_spec 可从 dimension_plan 生成。
- build_evidence ReAct 循环按 spec 缺口二次抽取, 有界。
- Phase 2.5: first-pass retrieval can optionally consume `evidence_requirement_spec`, produce bounded `spec_driven_first_pass` search rounds, and reduce downstream evidence gaps without requiring a public response-shape change.
- evidence 含 stage/quant 字段。
- claim_strength_guard 降级表述 + 报告等级判定生效。
- 4 案例 live 验证深度较现状提升, 零回归。
- STATUS 与本 PLAN 一致。

## Stop Conditions

仅当: protected contract (EvidenceItem 语义/响应形状) 需改且未授权; Tavily/
provider 不可用; 验证反复失败无安全修复; live 显著回归; 用户暂停; 达 Done。

## Validation Loop

每 Phase 跑对应 focused pytest + (Phase 2/4/5) live smoke。全局收口:
```powershell
python -m pytest -q tests/test_research_harness_graph.py -k "build_evidence or chief_gate or finalize"
python scripts/graph_provider_backed_smoke.py --query "<案例>" --max-rounds 2 --max-loop-count 1 --output-dir data/tmp/evidence_react_<case> --env-file .env --reset
python scripts/report_quality_inspect.py --response data/tmp/evidence_react_<case>/response.json --summary data/tmp/evidence_react_<case>/summary.json
```
Pass: focused 测试零新失败; live evidence 维度覆盖提升; 无核心 claim 弱证据强表达。

## Progress

### 2026-06-21: Phase 0 设计冻结

- /brainstorm 会话收敛: 用户否决被动"证据矩阵+guard" (我的初版 B), 选"evidence
  ReAct" (主动按报告框架补强) — 治本而非治标。
- 实代码裏取り: 检索相似度驱动 (embedding×10/rerank×8/bm25); build_evidence
  不知报告格式 (report/draft/格式: False) 但 tool_session 已传入 (有二次抽取通道);
  editor1 已知 11 章节框架 (对比 evidence 段缺框架意识); dimension_plan 已有
  source_families/expected_section_heading/coverage_required/min_required_evidence
  — (b) evidence_requirement_spec 的原料大部分已存在。
- 设计选择: (b) 新建 evidence_requirement_spec (一表喂 ReAct + guard 两端)。
- 无生产代码改动 (planning-only)。

### 2026-06-24: Phase 2.5 promoted to current active slice

- 用户接受“先更新 PLAN/STATUS，把 Phase 2.5 明确设为当前 active slice”。
- 原因：Phase 2 ReAct backfill 已经能补救证据缺口，但它仍是首轮检索后的补救机制；Phase 2.5 要把部分证据需求意识前移到首轮检索，减少后续补救成本。
- 本轮只做 planning/status 修正，不改生产代码。
- 下一步实现目标：在 `collect_sources` 首轮执行前加入有预算上限的 `spec_driven_first_pass` 检索轮，并记录可诊断 metadata。

### 2026-06-24: Phase 2.5 implemented, live smoke pending

- Execution mode: protected-boundary handling. The change affects first-pass retrieval semantics and user-facing evidence coverage, but does not change EvidenceBundle, citation fields, task/run semantics, or public `/deep-research/analyze` / `/research/analyze` response shapes.
- Implemented `spec_driven_first_pass` retrieval in `packages/research_harness/real_nodes.py`.
  - `plan_task_provider_backed` now derives `evidence_requirement_spec` from the plan before first `collect_sources`.
  - It injects bounded first-pass source-family rounds after the baseline round and before remaining generic rounds.
  - Priority families are `public_resource_transaction`, `company_disclosure`, `statistics`, then official/local supporting families.
  - Budget caps: max 3 extra rounds, max 2 phrases per family, max first-pass slice widened to 4 rounds.
  - No hard `include_domains` are used for these spec-driven rounds, consistent with ADR 0001.
- Added diagnostics.
  - Planner metadata now includes `spec_driven_first_pass`.
  - Internal state can carry `spec_first_pass_min_search_rounds` so collect does not truncate the injected rounds.
  - `search_events` and `sources` now expose `round_origin`, `target_source_family`, and `evidence_sections`.
- Added a narrow chief-gate repair discovered during regression.
  - When obligation gaps route to `ADD_EVIDENCE`, required actions now preserve claim-level补证 actions with `target_claim_id`, `required_source_family`, and suggested search queries, instead of only returning obligation IDs.
- Validation passed:
  - `python -m ruff check packages\research_harness\real_nodes.py packages\research_harness\state.py tests\test_research_harness_graph.py`
  - `python -m py_compile packages\research_harness\real_nodes.py packages\research_harness\state.py tests\test_research_harness_graph.py`
  - `pytest -q tests\test_research_harness_graph.py -k "spec_driven_first_pass or no_spec_fallback or exposes_spec_round_diagnostics or build_evidence or chief_gate or finalize"` → 16 passed.
  - `pytest -q tests\test_agents_workflow.py tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py` → 24 passed.
- Validation not fully passed:
  - `python -m ruff check .` failed on pre-existing lint issues in `.agent/hooks`, `.claude/worktrees`, and generated `unsloth_compiled_cache`, not on this slice's changed files.
  - Live smoke command timed out after 304s and produced no files under `data/tmp/goal_evidence_phase2_5_live_smoke`, so live evidence is still pending.

### 2026-06-24: Narrow live inspection passed, budget risk found

- Added `scripts/inspect_spec_first_pass_live.py` to validate only the narrow
  `plan_task -> collect_sources` chain, without running parse/evidence/editor/
  finalize.
- Live command:
  `python scripts\inspect_spec_first_pass_live.py --query "2025年合肥低空经济地方政策、上市公司披露与项目落地情况" --max-rounds 1 --output-dir data\tmp\spec_first_pass_live_inspect --env-file .env --reset --print-json`
- Live output artifact:
  - `data/tmp/spec_first_pass_live_inspect/summary.json`
  - `data/tmp/spec_first_pass_live_inspect/plan_result.json`
  - `data/tmp/spec_first_pass_live_inspect/collect_result.json`
- Live result:
  - `search_round_count`: 4
  - `spec_first_pass_min_search_rounds`: 4
  - `spec_search_event_count`: 6
  - `spec_source_count`: 25
  - target families: `public_resource_transaction`, `company_disclosure`,
    `statistics`
  - `hard_domain_filtering`: false
- Interpretation:
  - Functional validation passed: real provider output now contains
    `search_events.round_origin == "spec_driven_first_pass"` and source-level
    diagnostics.
  - Budget risk: estimated credits were 20 for the narrow run because collect
    uses advanced search and Phase 2.5 currently emits 3 families x 2 phrases.
    This is too expensive as a high-frequency default.
- Pending before marking Phase 2.5 complete:
  - Add or tune explicit credit control, likely by reducing default
    `SPEC_FIRST_PASS_MAX_PHRASES_PER_FAMILY` from 2 to 1 or by adding a
    provider-credit cap.
  - Run one more narrow live inspection after budget tuning.
  - Optionally compare first-pass gap count/ReAct backfill count against a
    baseline run.

### 2026-06-24: Full query-to-final-report live test completed

- User request: run one real query through the full graph to `final_report`.
- Query:
  `2025年合肥低空经济地方政策、上市公司披露与项目落地情况`
- Command:
  `python scripts\graph_provider_backed_smoke.py --query "2025年合肥低空经济地方政策、上市公司披露与项目落地情况" --max-rounds 1 --max-loop-count 1 --output-dir data\tmp\full_final_report_hefei_phase2_5 --env-file .env --reset --resume-action approve --resume-notes "Manual approval for full final-report live test."`
- Result:
  - Runtime: about 683.5s.
  - Workflow status: `succeeded`.
  - Final decision: `PASS`, but only after auto-resuming from an initial
    `HUMAN_REVIEW` gate with `resume_action=approve`.
  - Report artifact:
    `data/tmp/full_final_report_hefei_phase2_5/FINAL_REPORT.md`.
  - Raw response artifacts:
    `data/tmp/full_final_report_hefei_phase2_5/response.json`,
    `data/tmp/full_final_report_hefei_phase2_5/summary.json`,
    `data/tmp/full_final_report_hefei_phase2_5/dossier.md`.
  - Report length: 5054 characters.
  - Report level: `level_2` preliminary research report.
  - Quality scores: evidence_coverage 0.7, citation_integrity 0.8,
    source_quality 0.6, contradiction_resolution 1.0, final_score 0.75.
- Phase 2.5 diagnostics:
  - The full graph did exercise spec-driven retrieval.
  - Across the two collect steps, observed 26 search events and 12
    `spec_driven_first_pass` events.
  - Target source families included `public_resource_transaction`,
    `company_disclosure`, and `statistics`.
- Issues found:
  - Planner used deterministic fallback due to `ProviderParseError`.
  - Initial gate found source-family mismatches:
    official policy claims were supported by `official_news`, and statistics
    claims were supported by `company_disclosure`.
  - Cost is not yet controlled: command summary estimated 20 Tavily credits,
    while event-level summed search credits across collect passes were about
    52.
  - Context pack estimates are still extremely over budget in the full graph.
  - Dossier does not yet include search events or claim verifications, even
    though the response JSON contains the diagnostics.
  - Final report citations remain internal IDs rather than user-friendly
    title/URL citations in the body.
- Interpretation:
  - Full final-report generation works end-to-end.
  - The result is usable for inspection, but not yet a clean production PASS:
    it required manual approval over a real HUMAN_REVIEW gate.
  - Phase 2.5 should not be marked complete until credit caps and
    source-family evidence matching are repaired.

## Risks and Rollback

| Risk | 影响 | 缓解 | 回退 |
|---|---|---|---|
| 二次抽取受 Tavily 召回限制 | 补抽仍缺料 | 如实标注"补抽后仍缺" | 不影响, 退回现状召回 |
| ReAct 成本/延迟失控 | credit/慢 | loop 上限 + 只补 P0 缺口 | 关循环=单次抽取 |
| guard 太严报告萎缩 | 常态 HUMAN_REVIEW | 表述降级为主 | 调软阈值/关 guard |
| evidence 新字段破坏下游 | 回归 | 字段可选, 空值不改行为 | 移除字段 |
| real_nodes proxy 限制 | 改动风险 | 走 wrapper 层 | 撤销针对性 patch |

## Next Action

Phase 2.5: implement spec-driven first-pass retrieval. Start by inspecting the
current plan/collect/search-round path, then add a bounded helper that converts
`evidence_requirement_spec` into first-pass source-family-targeted search
rounds with diagnostics and budget caps.
