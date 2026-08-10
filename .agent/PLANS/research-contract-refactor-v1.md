# Research Contract Refactor v1

Status: active_phaseA_core_schema_formalize

Created: 2026-06-23

Primary active PLAN: yes

Parent of: `.agent/PLANS/goal-driven-evidence-react-v1.md` (evidence 层前置工作, 已完成)

Related:
- 方案源: `C:\Users\LEGION\Downloads\invest_agent_prompt_pipeline_refactor.md` (Codex 重构方案)
- 用户评审: 调整阶段顺序 + 5 项硬要求 (2026-06-23)
- 现有基础: `packages/research_harness/real_nodes.py` (recovery proxy), `plan_semantic.py`, `tooling/llm_agents.py`, `state.py`, `retrieval_bridge.py`

## Objective

将当前"多套 Planner、两套 Editor1、Prompt 中英混杂、上下文截断、证据与报告脱节"的实现，重构为一条**可审计、可回归、可逐步迁移**的研究流水线。终态：

```text
Research Contract 驱动检索
Claim Slot 约束 Evidence
Sufficiency Gate 决定是否进入写作
Claim Card 约束 Editor1
Draft Gap 触发补充研究
```

核心原则（用户评审确认）：
- **增量演进，不建第二套系统**——把现有 evidence_requirement_spec / atomic evidence / gap self-check / claim_strength_guard / backfill / structured sections / prompt trace **formalize 成契约**，而非并行重写
- **Planner 最后收敛**——上游改动影响所有下游，先稳定下游契约和评价方式
- **additive schema / dual-write / shadow compare / feature flag**——禁止直接破坏旧路径

## Task Classification

- Primary area: `research_workflow`
- Secondary: `provider_layer`, `eval_policy_ops`, `source_layer`, `task_substrate`
- Protected contracts (不可静默改): `/deep-research/analyze`、`/research/analyze` 响应形状; `EvidenceItem`/`SourceAssessment` 公共 schema; `runs`/`run_steps` 语义
- Execution mode: `light_subagent` for 单节点契约 formalize; `remediation_gate` if gate 回归; `full_subagent` 仅 protected-contract 变更

## Scope

In scope:
- 核心契约 formalize (EvidenceUnit/ClaimCard/ResearchContract/StructuredDraft)
- 基础来源聚类 (content_cluster_id, 独立来源计数)
- Sufficiency Gate 精确化 (critical 硬门禁)
- 全量分层审查 (确定性全文 + Section LLM + 高风险 Claim LLM)
- Prompt Registry 最低版本 (name/version/hash 落盘)
- Claim Expander 从"<8 条"改 slot-driven
- Planner 收敛 (intent/blueprint/retrieval 职责分离)

Out of scope (Phase E 或后续):
- 高级来源溯源 (origin_source_id 高置信、转载链、传播路径)
- Prompt Registry UI / 完整服务
- 跨任务 Evidence 复用
- 复杂 discovery_policy / advanced_argument_posture / 跨报告 Claim lineage

## Constraints

- **Additive 优先**: 新字段可为空、双写、shadow compare，稳定后再切读路径；禁止一次改坏旧路径
- **Critical slot 硬门禁**: `weighted_slot_coverage` 只作可视化/排序/评分，**不能**补偿 critical slot 缺失
- **Prompt 版本必传**: 每个 Provider 调用必须带 prompt_name/version/hash，否则回归无法归因
- **来源独立性先于 Gate**: 基础聚类必须在 Sufficiency Gate 之前，否则 Gate 误算独立来源
- **确定性优先**: ID 校验、数字校验、citation integrity、聚类、覆盖率用代码，LLM 只做语义判断
- **不以数量判断充分**: 删除 `len(claims) < 8` 触发逻辑，改 slot-driven
- `real_nodes.py` 是 recovery proxy over bytecode — 改动走 wrapper 层

## Phases

### Phase 0: 基线冻结与可观测性

Status: completed

Implementation (2026-06-23):
- Prompt trace 补字段: `_persist_llm_trace` 增加 system_prompt_hash / user_prompt_hash
  (sha256 前16) / git_commit (git rev-parse --short) / temperature (getattr 兜底 0.1)
  / schema_version (trace_v1)。`call_tooling_json` 调用时传入。验证: 决定论 trace
  含全部新字段 (run_999/test/attempt_1.json)。
- 评测集冻结: 50 题 `source_quality_cases_v1.json` (已有) + 新增
  `resume_subset_smoke_6.json` (M03/M12/P04/P08/C01/K07, 覆盖宏观/省/市/县+冲突题)
  + `resume_subset_regression_10.json` (M01/M02/M08/M09/M10/P01/P02/C02/C07/K01,
  4 粒度多产业)。两子集全命中。
- Feature flags: `Settings` 增加 pipeline_planner/evidence/claim/editor/gate_mode,
  默认 "legacy", 经 .env 切换 (PIPELINE_*_MODE)。验证: get_settings 可读, 默认 legacy。
- 基线数据: 6 题 smoke 已有产物 (data/tmp/resume_eval_A_6b, 修复 max_rounds=2 后),
  Phase 0 记录为基线参照。

Objective: 不改变业务逻辑，先让每次 Provider 调用可追踪、可归因、可回滚。

Modification:
- Prompt `name/version/hash` 强制落盘到现有 `run_contexts` trace (已有 prompt 文本, 补 version/hash)
- 记录 model、temperature、schema_version、git_commit
- 冻结 6 题 (开发 smoke) / 10 题 (PR 回归) / 50 题 (里程碑) 评测集
- 建立 feature flag (planner_mode/evidence_mode/claim_mode/editor_mode)
- 保存当前质量、成本、耗时基线

Prompt Registry 最低字段 (Phase 0 完成, 不进 E):
```json
{"prompt_name":"atomic_fact_extractor","prompt_version":"2.1.0",
 "schema_version":"evidence_unit_v2","model":"provider/model",
 "temperature":0,"system_prompt_hash":"...","user_prompt_template_hash":"...",
 "run_id":"...","git_commit":"..."}
```

Validation:
- Provider trace 覆盖率 100%; 每次调用含 node_name + prompt_version
- 同一研究任务可重放; 当前结果不因 trace 改造而变化

Acceptance:
- `run_contexts` trace 均含 prompt_version/hash
- 6/10/50 题评测集文件冻结并可运行

Risks: 改动 trace 影响实时调用 — 缓解: additive, trace 写失败不阻塞主流程 (已有 try/except)

### Phase A: 核心 Schema 增量扩展

Status: **accepted** (implementation complete; L1 ✅; L2 replay ✅; L3 = pending milestone)
- L1 (unit): 56 例 Phase A + L2 7 例 + graph 聚焦回归 7 例 = 全绿
- L2 (pipeline replay): `tests/test_research_l2_replay.py` + `tests/fixtures/research_replay/{M03,C01,K07}`
  (recorded parsed_sources, 禁网, 结构性 invariant)
- L3 (live milestone): 待里程碑质量评估，不阻塞 Phase A2 开发 (Phase A2 以 shadow 模式进入)
- Regression comparison: Phase 0 基线已修复为有效 (`resume_eval_A_summary_valid.json`), live 对比在 L3 跑

Implementation (2026-06-23, EvidenceUnit quoted_span):
- `_make_atomic_evidence_item` 增加 `quoted_span` 参数 + `quote_verified` (确定性
  substring 校验, 非 LLM 信任)。`_quote_in_source` 用 NFKC + 去空白/全角转半角
  规范化后做 verbatim 匹配, 防提取器产出原文不存在的引用。
- `_llm_extract_atomic_facts` prompt 要求 quoted_span (50-150 字, 原文逐字,
  不可改写) + 传给 item。
- `_deterministic_atomic_facts` (确定性回退) 用原文句作 quoted_span (sent[:150])。
- 验证: compile OK; ruff 0 serious; 决定论: 真实原文 quote → verified=True,
  编造 quote → verified=False (防幻觉), 确定性路径 → verified=True。
- 说明: 只增 LLM 输出 token (正文已给 Extractor), 每条限 50-150 字控制成本。

Implementation (2026-08-03, ClaimCard 字段):
- `_annotate_claim_card` (确定性, 无 LLM): 在 `_enrich_claim_semantics` 循环内 + LLM supplement 路径调用。
  - `claim_type` 8 值枚举 (comparison/trend/causal/risk/outlook/synthesis/fact + evidence_gap 结构覆盖),
    按优先级关键词命中, 无命中→fact, 无证据→evidence_gap。
  - `epistemic_status` (supported/supported_with_limitation/partially_supported/conflicted/unsupported/not_found):
    limitations 含矛盾/冲突→conflicted; 无证据→unsupported(not_found 若文本含"未发现"类 marker);
    unsupported 但 avg>=0.3→partially_supported; avg>=0.6 且无 limitation→supported; 其余→supported_with_limitation。
  - `max_assertion_level` (1..4) 对齐 `_claim_strength_guard`: >=2 独立来源且 avg>=0.7→4; avg>=0.6→3;
    avg>=0.4→2; 否则 1。`forbidden_assertion_levels` = level_{max+1..4}。
  - `forbidden_expansions` (给 Editor1 的 NL 提示, 上限 3 条): 单源不得外推 / 弱证据降级 / 未投运不得断言 /
    未签约不得当落地 / 矛盾并列呈现 / 充分证据禁止新增未引用数字。
  - `slot_id` additive, 未知留空 (Contract Compiler 落地后由 claim-slot 绑定回填)。
- editor1 input pack (`_build_editor1_actual_input_pack`) claim_rows 增补 claim_type/epistemic_status/
  max_assertion_level/forbidden_assertion_levels/forbidden_expansions, 供 Editor1 按卡片约束写作。
- 验证: tests/test_research_harness_claim_card.py 12 例全绿 (8 值分类/max level/forbidden levels/
  end-to-end 各 epistemic_status); ruff 0; 相关 graph 聚焦测试 (build_claims×2 + editor1 budget) 3 例通过。
- 说明: 全部确定性代码, 无新增 LLM 调用; 字段 additive, 旧 claim dict 不受影响。

Implementation (2026-08-03, Contract Compiler + slot-driven Claim Expander + StructuredDraft):
- `packages/research_harness/research_contract.py`: `compile_research_contract(plan) -> ResearchContract v1`,
  纯确定性。从 dimension_plan + evidence_requirement_spec 派生 sections/claim_slots/writing_policy/meta。
  - 每 dimension → section; 每个 canonical source_family → claim_slot
    (slot_id=`{dim}.{family}.{purpose}`, purpose 由 family 映射稳定后缀)。
  - required 级别: 该 dimension 的 primary family 且非 context family → critical;
    context family (official_news/industry_research/commercial_media) → optional; 其余 → required。
  - min_evidence 取该 family 最强 obligation; key_fields 复用 `_DIMENSION_KEY_FIELDS`。
  - writing_policy: default_max_assertion_level=3; critical_slot_missing_mode=evidence_gap_only
    (Phase B 硬门禁的落点)。
- `real_nodes.build_claims_provider_backed` Claim Expander 改 slot-driven (删除 `len(claims)<8`):
  - `_backfill_claim_slot_ids`: 为已有 claims 按 required_source_family / 关联证据 family 回填 slot_id。
  - `_find_claim_gap_slots`: 只挑 "证据已满足 (count>=min_evidence) 但无 claim 覆盖" 的 slot。
  - `_llm_supplement_claims_slot_driven`: 逐 gap slot 一次调用, prompt 带该 slot 的 research_question/
    source_family/evidence 子集, 产出带 slot_id 的 claim; `_source="llm_supplement_slot_driven"`。
- StructuredDraft paragraph 映射 (`_annotate_draft_paragraph_mapping`, 纯确定性):
  - 按空行把 section markdown_body 切成 paragraphs; 解析 `[evidence_id]` 引用 marker
    (负向前视排除 markdown 链接); claim 绑定 = 共享 evidence_id 或 claim 文本 verbatim 出现。
  - 输出 `unused_claim_ids` (报告级未被任何 paragraph 引用的 claim)。在 editor1 包装函数末尾
    统一注入 (LLM 成功/异常回退/确定性回退 三路径都覆盖)。
- 验证: tests/test_research_harness_contract.py 20 例 (compiler 规则/determinism/空 plan 降级 +
  gap-slot 检测/backfill/paragraph 映射) + test_research_harness_claim_card.py 12 例全绿;
  ruff 0; graph 聚焦回归 (build_claims×2 + editor1 budget + deterministic fallback + finalize readable) 5 例通过。
- 说明: 全程无新增 LLM 调用 (除 gap-slot 有界补充); 不改 Planner; `_llm_supplement_claims`(count<8 版)
  已删除。唯一已知环境性测试失败: `test_editor1_draft_provider_backed_outputs_markdown_oriented_sections`
  断言英文标题, 但 live DeepSeek 按中文 system prompt 输出中文标题 (trace 证实 llm_mode=live_provider),
  与本改动无关。

Implementation (2026-08-03, 评审 4 项 must-fix + should-fix 落地):
- **Fix 1 (Contract Compiler critical 语义)**: 删除 "Source Family → critical" 推导。
  - `critical` 只来自 `plan["critical_slots"]` 显式声明 (slot_id 字符串或
    {section_id, source_family} 对); 默认 primary family slot → `required`;
    context family → `optional`; slot 增 `primary_source_required` 提示。
- **Fix 2 (ResearchGap 与 ClaimCard 分离)**:
  - 删除 `claim_type="evidence_gap"` 覆盖; 无证据 claim 保留词法 claim_type + `unsupported`。
  - 删除 `not_found` 自动赋值 (未找到需 CoverageReport, 非 claim builder 自行判断)。
  - 新增 `_build_research_gaps` (ResearchGap 对象): gap_id/slot_id/gap_type
    (no_reliable_evidence/contradiction/missing_fields)/searched_source_families/
    missing_fields/allowed_report_expression; 挂到 `build_claims` 结果 `research_gaps`。
- **Fix 3 (paragraph 映射显式化)**: Editor1 输出 `<!-- paragraph_id/claim_ids/evidence_ids -->`
  marker → `_parse_explicit_paragraph_markers` 解析, `mapping_source="editor_explicit"`,
  confidence=1.0; 无 marker 走启发式 (citation+verbatim) → `mapping_source="heuristic"`,
  confidence<1.0。Verifier (Phase C) 优先审查 heuristic/无显式映射段落。
- **Fix 4a (live provider 测试隔离)**: `test_editor1_draft_provider_backed_outputs_markdown_oriented_sections`
  用 monkeypatch 注入 fake `call_tooling_json` (固定英文标题报告), 不再依赖 live DeepSeek。
- **Fix 4b (0/0 基线修复)**: `resume_eval_A.py` `_coverage` 增加 `_extract_dossier_evidence`
  (解析 dossier.md 证据表); 用现有 6b 产物重算出有效 Phase 0 基线
  (`data/tmp/resume_eval_A_6b/resume_eval_A_summary_valid.json`, 6/6 非零)。
  live 6 题对比按用户 L1/L2/L3 建议改在 L3 里程碑跑 (避免每次 Phase 1-2 小时 live smoke)。
- **should-fix**:
  - ClaimCard `primary_slot_id` + `slot_ids` (多 slot 绑定, `_backfill_claim_slot_ids` 收集全部匹配
    slot 按 critical>required>optional 排序取 primary); 修 `canonical_source_family("")` 默认
    official_news 导致空 required_source_family 误匹配 official_news slot 的 bug。
  - `max_assertion_level` (int rank) + `assertion_level_label` (mention_only/fact_confirmed/
    pattern_supported/strong_conclusion)。
  - 全局 forbidden 规则移到 Contract `writing_policy.global_editorial_rules`
    (new_numeric_fact_requires_evidence/new_entity_requires_claim_binding), 不再每条 claim 重复。
  - Slot Expander 批量化: 按 section 分组, 每批 ≤4 slot 一次 LLM 调用, 输出含 unresolved_slots;
    新增 required-fields 门槛 (至少 1 个 key_field 存在) + contradiction 门槛 (冲突证据不生成确定 claim)。
  - EvidenceUnit `quote_loc`: quote_start/quote_end/quote_occurrence/offset_mode
    (raw 优先, 规范化回退), 支持前端定位与人工核查。

Implementation (2026-08-03, L2 前 4 个末尾修正 + 最小 L2 Replay):
- **ResearchGap reportability**: `_build_research_gaps` 输出 `reportability=pending_coverage_review` +
  `candidate_report_expression` (限定"当前已收集证据中未包含…", 不写"公开渠道暂未发现") +
  `approved_report_expression=null` (由 Phase B Sufficiency Gate 在覆盖评审后生成)。
- **Paragraph mapping 校验**: `_validate_paragraph_mapping` 确定性检查 claim_id/evidence_id 存在 +
  evidence 属于绑定 claim 支撑集 + paragraph_id 重复; 输出 `mapping_validated`/`mapping_issues`。
  "editor_explicit" 只表示来源, 不表示正确。
- **field_requirements**: Contract slot 增 `field_requirements` (mandatory_fields + any_of_fields +
  minimum_optional_fields) + `field_validation_mode` (strict 显式配置 / legacy_any_key_field 兜底);
  `_slot_evidence_satisfies_fields` 按模式执行。
- **NO_CRITICAL_SLOT_DECLARED warning**: Contract 无 critical slot 时输出 `contract_warnings`
  (warning 级, 不重新隐式推导 critical)。
- **L2 Replay** (最小): `tests/fixtures/research_replay/{M03,C01,K07}/fixture.json`
  (query/plan/parsed_sources/evidence/claims/draft, 全部录制);
  `tests/test_research_l2_replay.py` 跑确定性管线 (Contract Compiler → ClaimCard → ResearchGap →
  paragraph mapping) + 结构性 invariant (schema 完整/citation 完整/quote 真实/claim 约束/draft 映射/
  确定性/禁网)。K07 故意含 ghost id 验证 mapping 校验负例。
- 验证: L1+L2 共 63 例 + graph 聚焦 7 例全绿; ruff 0; py_compile 通过。

Objective: 把现有隐式契约 formalize，而非创建第二套。

Modification (全部 additive, 旧字段保留新字段可空):
- EvidenceUnit: 现有 atomic evidence 增加 `quoted_span` (单独存, 含 chunk_id/quote_start/quote_end)、`slot_ids`、`chunk_id`
- ClaimCard: 增加 `slot_id`、`claim_type` (fact/comparison/trend/causal/synthesis/risk/outlook/evidence_gap)、`epistemic_status` (supported/supported_with_limitation/partially_supported/conflicted/unsupported/not_found)、`max_assertion_level` + `forbidden_assertion_levels` (机器可读) + `forbidden_expansions` (给 Editor1 的 NL 提示)
- ResearchContract: 通过 **Contract Compiler** (确定性代码) 将现有 dimension_plan + evidence_requirement_spec → ResearchContract v1，**不改 Planner**
- StructuredDraft: editor1 sections 补 paragraph 级 claim_ids/evidence_ids + unused_claim_ids
- Claim Expander: 删除 `len(claims) < 8` 触发，改为 `evidence 已满足但 claim 缺失的 slot → 构建 claim`

quoted_span 硬性校验:
```python
quote_verified = quoted_span in source_chunk
# 失败→规范化匹配→仍失败→拒绝该 Evidence
```
- 每条引用限制 50-150 中文字符控制成本 (只增输出 token, 正文已提供给 Extractor)

Validation:
- quoted_span 准确率 >=95%; 数字幻觉率 <=1%; 项目状态误判率 <=3%; slot mapping 准确率 >=90%
- 6 题 smoke coverage 不退化 (对比 Phase 0 基线)

Acceptance:
- 核心 6 schema 字段落地 (slot_id/quoted_span/claim_type/epistemic_status/max_assertion_level/source lineage)
- 不再有 `<8` 数量触发

Risks: LLM 输出 token 增 (quoted_span) — 缓解: 限定 50-150 字符 + 确定性校验拒绝

### Phase A2 — Source Content Clustering

Status: **Provisionally Accepted for Shadow and Advisory Use** (2026-08-04)

Completed:
- Deterministic URL/content normalization
- Exact duplicate clustering
- Near-duplicate candidate detection
- Entity-bound FactFrame conflict protection
- Shadow three-track coverage comparison
- Human-labeled pilot and validation datasets
- Content-cluster auditability
- L1/L2 regression coverage

Accepted usage:
- Exact duplicates may be used for deterministic duplicate counting
- High-confidence reprints may generate advisory warnings
- Near-duplicate results remain shadow-only

Not accepted:
- Source independence claims
- Near-duplicate-based Gate enforcement
- Automatic Revision lineage
- Production threshold 0.78
- Formal Claim strength adjustment

Deferred:
- Calibration v3 / Validation v3
- Real revision benchmark expansion
- Advanced document lineage
- LLM or embedding-based clustering

Reopen conditions:
- Shadow logs show meaningful Gate-impacting duplicate clusters
- False merge is observed in exact/high-confidence path
- Near-duplicate recall becomes a demonstrated report-quality bottleneck
- Source lineage becomes an independent product requirement

### Phase B.2 — Evaluability Persistence

Status: **Accepted** (Schema/Store/Evaluator + Runner Integration + Real-run Acceptance done)

Runner integration (`packages/research_harness/evaluation_recorder.py` + real_nodes hooks):
- `build_runtime_coverage_report(run_id, evaluation_store, legacy_state, mode)` —
  显式双模式入口 (evaluable_persistence / legacy_shadow), 不隐式切换;
  `coverage_input_source` + `coverage_schema_version` + `legacy_fallback_used`。
- `RunEvaluationStore.to_dict()/from_dict()` 支持 checkpoint 持久化;
  幂等记录 (同 ID 同内容忽略; 同 ID 异内容记 IDEMPOTENCY_CONFLICT);
  Coverage 计数按唯一 ID。
- 稳定 search_task/search_event ID (run_id+round+slot+query hash)。
- real_nodes 包装节点挂记录钩子 (fail-open): build_evidence →
  record_claim_slots/record_search_events/record_evidence_units (key_fields 状态 +
  family→slot 链接); build_claims → record_claim_cards; write_store 写回
  `evaluation_store` + `evaluation_persistence_status`。
- 6 集成测试 (happy path / 重试幂等 / checkpoint 恢复 / 搜索失败 / 抽取失败 /
  聚类非干预), 全量 132 例绿。
- **Real-run Acceptance (2026-08-04)**: 2 个全新任务 (无旧 checkpoint):
  - Case 1 (证据充足, 合肥低空物流): completeness=1.0, satisfied 3 / unsatisfied 3 /
    not_evaluable 0, readiness=partial。
  - Case 2 (证据稀疏, 上市公司披露): completeness=0.57, satisfied 1 / unsatisfied 3 /
    not_evaluable 3, readiness=unknown。
  - coverage_input_source=evaluable_persistence, legacy_fallback_used=false 均成立。
  - 三态符合实际执行 (Case2 的 official_policy not_evaluable = 未搜索, 非未找到;
    disclosure satisfied = 15 条披露证据)。
  - 可追踪缺口: SearchTask terminal 0.875/0.889, SearchEvent recording 0.75/0.78,
    Evidence field 0.88/0.95, Case2 Evidence-to-Slot 0.75 (media/analysis 无 slot)。
  - 产物: `data/tmp/b2_real_run_acceptance/`。

### Phase B.3 — Gap Retrieval (B.3.1 Gap Derivation + B.3.2 Action Proposal)

Status: **B.3 done; C.1 done; C.2 done (Accepted); C.3.1 Structured Compare done
(决策门: 继续 Compare, 不扩 Schema / 不进 structured_primary)**;
Gate Enforcement / Editor1 Blocking / Expression Approval 均 Disabled。

### Phase C.3.1 — Structured Compare

- `structured_compare.py`: Legacy (正式) vs Structured (旁路) 同输入双轨。
  逐节真实 DeepSeek 严格 JSON → validate → 重试(≤1) → StructuredDraft →
  确定性 markdown renderer → comparison_report。Structured 只读 C.1 Editor1Input。
- 配置 `EDITOR1_MODE=legacy` + `STRUCTURED_EDITOR1_COMPARE_ENABLED=false`。
- 关键修复: Phase A ClaimCard 断言词汇归一化 (`normalize_claim_assertion`)。
- 测试 13 例全绿; 真实验收 Case1/3 pass, Case2 blocked 节被 validator 拦截,
  approved claim 使用率 0.27/0.29 (低)。
- **决策: 继续 Compare — 调 `build_section_prompt` (强制覆盖 allowed claims /
  保留 limitations / 遵守 readiness) 与 Section 输入, 不扩展 Schema/Validator。**
- **Prompt v2 校准 (2026-08-04)**: 指标语义修正 (required/eligible 两档,
  limitation not_applicable, paragraph mapping); Coverage Contract
  (required/optional claims + required limitations + forbidden conclusions +
  paragraph budget); 每 Claim 1-2 最强 Evidence; blocked/unknown 不调 LLM;
  Prompt 分层 + readiness few-shot; Retry 精准反馈; Validator 多 Claim 证据并集。
  消融: required coverage 1.0 (Case1/3/4), assertion/blocked 0, mapping 100%;
  Few-shot 未一致胜出 → 不保留; Case3/4 eligible=0.5 (<80%) →
  **按停止条件停 Prompt 迭代**, 下一轮修 Section–Claim assignment (Claim 去重 +
  required 划定), 不扩 Schema/Validator。
- **C.3.2 Section–Claim Assignment (2026-08-04)**: `section_claim_assignment.py`
  结构归属 + Claim Signature 聚类 + 代表选择 + required/optional/suppressed
  (带 reason) + ContextAudit。集成 build_section_inputs。指标空集合 null+status。
  12 测试全绿; fast 176 全绿; 真实验收 eligible 1.0 (Case3 0.5→1.0, Case5 holdout),
  Case1 validation 修复。**Accepted。**
  **人工盲审 A/B (2026-08-04)**: Legacy 更好 → 不进入 canary, 保持
  structured_compare, C.3.2 冻结。下一阶段 **Structured Synthesis Paragraph**
  (受约束综合, 不引入新事实), 达标后再评估 canary。
- **C.3.3 Constrained Synthesis Layer (2026-08-05)**: `constrained_synthesis.py`
  SynthesisContract + 确定性 Trigger Compiler + LLM 只表达 Contract + Synthesis
  Validator (闭包/assertion/limitation/forbidden) + Evidence Gap Paragraph Builder +
  Semantic Critic (advisory)。接入 structured_compare。16 测试全绿; fast 192 全绿;
  case_06 holdout 生成 3 条 synthesis; 修复 synthesis_id 注入; 真实 Case1 触发少。
  **Accepted (shadow, 受约束)。仍不进 canary。**
- 尚未实现: structured_primary_canary / structured_primary (正式迁移)。

### Phase C.2 — Structured Shadow Graph Integration

- `structured_shadow_editor1` 节点: build_claims → advisory_gap_backfill →
  structured_shadow_editor1 → editor1_draft (边固定)。只读主 evaluation_store +
  主 CoverageReport, 绝不读 advisory_backfill.evaluation_store; 只写
  `structured_draft_shadow` 命名空间; flag `STRUCTURED_DRAFT_SHADOW_ENABLED=false`
  默认 + `_MODE=shadow`; fail-open。
- Shadow Draft 稳定 ID (content hash, 无 uuid): draft_id + paragraph_id。
- 测试: C.2 8 例全绿; fast 集 146 全绿。
- 真实 OFF/ON 验收: Case1/Case2 非干预 (main/editor1 input/report_markdown/
  final_report unchanged), shadow validation passed。
- 范围外 (C.3): 替换正式 Editor1 / Markdown 迁移 / 有限重试。

### Phase C.1 — Claim-Constrained StructuredDraft (shadow, C.1.1-C.1.4)

- `packages/research_harness/structured_draft.py`:
  - C.1.1 `StructuredDraft` / `DraftSection` / `DraftParagraph` 冻结 schema;
    段落显式携带 claim_ids + evidence_ids + assertion_level + limitations。
  - C.1.2 `compile_editor1_input`: 仅 `approval_status == "approved"` ClaimCard
    进入; Evidence 裁剪为 approved claim 引用集合 (ClaimCard.evidence_ids)。
  - C.1.3 `build_structured_shadow_draft`: 确定性逐节 shadow — ready/partial →
    factual 段落 (assertion 按 claim max_allowed + section readiness 双封顶,
    limitations 保留); blocked/unknown → 仅 gap_descriptive。
  - C.1.4 `validate_structured_draft`: 引用完整性 / assertion 越级 /
    limitation 保留 / blocked-unknown 强结论 / gap 负面断言。
  - `ClaimCardRecord` 增 `text` (claim 原文, 供段落构建)。
- 测试: `tests/test_research_harness_structured_draft.py` 13 全绿。
- 真实 Case1/Case2: Case1 15 approved claims → factual; Case2 unknown sections
  → gap_descriptive, 无强结论, validation passed。
- 范围外 (C.2/C.3): 替换正式 Markdown / Editor2 / Verifier / Gate / gap 自动
  批准 / backfill 进正式 Editor1 / LLM 修复循环。

B.2 收尾补丁:
- `close_search_tasks` 作用域化 (`round_id` / `exclude_task_ids`):
  - `build_claims` **只记录 ClaimCard**, 不再全局关闭 SearchTask。
  - **B.3.3b 终结语义升级**: run-close 从 `finalize_report` 移出, 由 Runner 中心
    `finalize_evaluation_run` 覆盖全部终止路径 (REPORT_COMPLETED / HUMAN_REVIEW /
    BUDGET_EXHAUSTED / PROVIDER_FAILED / GRAPH_ERROR / USER_CANCELLED);
    HUMAN_REVIEW → 标 `suspended` (可 resume), 其余 → `cancelled`+reason;
    SearchTask 增 `suspended` / `superseded` 状态。
- `SearchEvent recording rate` 分母改为实际执行任务数 (completed+failed),
  非全部 planned task。

B.3.3b Graph Shadow Node:
- `advisory_gap_backfill` 节点 (build_claims → advisory → editor1_draft, 边固定)。
  copy-on-write shadow: 只写 `advisory_backfill` 命名空间, 不改
  sources/evidence/claims/documents/coverage/final_report; flag
  `ADVISORY_GAP_BACKFILL_ENABLED=false` 默认 + `_MODE=shadow`; fail-open。
- 真实实现 `advisory_backfill_live.py` (AnySearch 执行器 + 内容关键词证据构建);
  SearchEvent 记录 configured/executed/fallback trace;
  `SEARCH_PROVIDER_POLICY=required` 时 anysearch 无 key 启动报错。
- 测试: finalize_evaluation 9 + advisory_gap_backfill_node 11 = 20 全绿;
  B.3 相关 fast 集 125 全绿。

B.3.3a Advisory Backfill Harness (`packages/research_harness/advisory_backfill.py`):
- `run_advisory_backfill(store, current_snapshot, research_gaps, proposed_actions,
  search_executor, evidence_builder, ...)` — SearchExecutor/EvidenceBuilder 为
  Protocol 注入 (不写死 Provider, 便于测试/替换真实搜索)。
- 每轮: 重派生 ResearchGap → propose_search_actions (executed_queries 去重,
  累计 per-slot 上限) → 创建 SearchTask(origin=gap_backfill, 溯源 gap/action) →
  Provider → SearchEvent(追加式) → Evidence(Scheme B:
  originating_search_event_ids) → 重算 CoverageSnapshot → SnapshotDiff。
- 停止条件 8 条; 未解决 Gap → exhausted, approved_expression 恒 null。
- `SearchTaskRecord` 增 origin / originating_gap_id / originating_action_id
  (from_dict 回填旧 store 防幂等冲突)。
- 真实运行 `scripts/b3_advisory_backfill.py` + 12 测试 + 验收
  `data/tmp/b3_advisory_backfill/B3_BACKFILL_ACCEPTANCE.md`。

`packages/research_harness/gap_retrieval.py`:
- **ResearchGapRecord** (仅 unsatisfied slot): gap_type ∈ evidence_count /
  raw_source_count / distinct_content_count / mandatory_field_missing /
  any_of_field_missing / source_family_missing / primary_source_missing /
  contradiction_unresolved; 关联 slot/evidence/coverage_snapshot;
  reportability_status 默认 not_reviewed (approved 恒 null)。
- **EvaluationGapRecord** (仅 not_evaluable slot): reason ∈ search_not_executed /
  search_failed / field_extraction_not_run / ...; suggested_repair_action
  (第一版只自动 execute_existing_task / retry_search)。
- **SuggestedSearchAction** (确定性模板, 不执行): 缺字段 → `{entity} {field_kw}`
  模板; 缺 source family → `{entity} {family_kw}`; 优先级按
  critical(+100)/required(+50)/mandatory_field(+40)/primary(+35)/family(+30)/
  evidence(+15)/duplicate_penalty(-50); 稳定 action_id + query 去重。
- `build_snapshot_diff` (before/after 补搜对比)。
- 测试: `tests/test_research_harness_gap_retrieval.py` 11 例 (gap 类型 ×5 +
  action ×3 + 补搜 resolved + 无新证据 exhausted + 非干预)。
- 语义边界: not_evaluable → EvaluationGap, 绝不生成 ResearchGap/"未发现"。

Goal: 让新运行的 CoverageReport 不再因 Schema 缺失而大面积 not_evaluable。

Implementation (`packages/research_harness/eval_persistence.py`):
- 追加式 per-run `RunEvaluationStore`, 持久化 6 类结构:
  - `ClaimSlotRecord` (min_evidence_items / min_raw_supporting_sources /
    min_distinct_content_sources / min_independent_sources=null /
    field_requirements / source_obligations / max_assertion_level)。
  - `SearchTaskRecord` (planned/running/completed/failed/cancelled/budget_exhausted)。
  - `SearchEventRecord` (实际执行: status/result_count/accepted_source|evidence_ids)。
  - `EvidenceUnitRecord` (key_fields present/not_found/not_applicable/
    extraction_failed/not_extracted; key_field_extraction_status;
    supports_slot_ids; quote_verification_status)。
  - `ClaimCardRecord` (primary_slot_id/slot_ids/evidence_ids/approval_status)。
  - `CoverageSnapshot` (每轮不可变快照; source_count_policy 记录
    gate=raw / exact=deterministic_reference / likely_reprint=advisory_only)。
- `build_evaluable_coverage_report(store)`: 三态判定
  (satisfied / unsatisfied / not_evaluable) + `evaluation_completeness` +
  readiness (critical/required not_evaluable -> unknown, 防"排除分母"假 ready)。
  - 无 SearchEvent -> not_evaluable; 抽取未完成 -> not_evaluable;
    已搜索+明确 not_found -> unsatisfied; 满足全部 -> satisfied。
- 验收测试: `tests/test_research_harness_eval_persistence.py` 8 例
  (6 L2 replay 三态 + 2 聚类非干预)。全量 120 例绿。
- 完成标准 (待 runner 接入后验收):
  100% ClaimSlot 可追踪 / 100% SearchTask 有状态 / 100% 搜索有 SearchEvent /
  100% Evidence 有字段抽取状态 / 100% Evidence 映射到 Slot /
  CoverageReport 不再全 not_evaluable。

Tiered usage (implemented in `sufficiency_gate._slot_report`):
- `exact_duplicate_adjusted_count`: deterministic dedup (same content hash /
  canonical URL) — usable by the formal path.
- `likely_reprint_adjusted_count`: additionally collapses high-conf reprints —
  ADVISORY ONLY, emits `SOURCE_SUPPORT_MAY_SHARE_SAME_CONTENT_ORIGIN` warning,
  never a gate input.
- `distinct_supporting_content_count`: all-merges distinct (shadow).

Objective: 让 Sufficiency Gate 后续基于"内容去重后计数"而非"网页数"判断。

Modification (`packages/research_harness/source_cluster.py`, 纯确定性, 无 LLM/Embedding):
- `canonicalize_url` (去 UTM/fragment/排序参数/统一尾部斜杠/剥离 print·mobile)
- `normalize_title` (NFKC + 剥站点名前后缀 + 空白折叠)
- `normalize_content` (NFKC + 空白折叠)
- `content_fingerprint` (sha256)
- **Exact duplicate**: 同 normalized-content hash → 同簇 (confidence 1.0,
  reason=exact_content_hash); 同 canonical_url 但内容不同 → revision candidate (不合并)
- **Near-duplicate**: title char-bigram Jaccard + content SimHash + number/date 重合;
  representative-based (非 Union-Find, 防 A≈B≈C 链式误并); high(0.90) → 并簇,
  medium(0.78-0.90) → candidate only
- Shadow 输出 (不改正式 source_count/Claim/Gate/报告):
  - report: raw_source_count / shadow_distinct_content_count /
    shadow_duplicate_adjusted_source_count / clustering_mode=shadow
  - slot: raw_supporting_source_count / shadow_distinct_content_count / shadow_count_difference
  - cluster: content_cluster_id / source_ids / representative / duplicate_confidence / duplicate_reason
- 集成: `real_nodes._shadow_source_clustering_meta` 挂在 build_evidence 结果
  `shadow_source_clustering` (仅元数据, 不写 origin_source_id, 不突变 source)

Validation:
- `tests/test_research_harness_source_cluster.py` 19 例 (10 场景正负例 + 反链 + shadow 输出 + 不突变)
- 审计 `scripts/audit_source_cluster_shadow.py` → data/tmp/source_cluster_shadow_audit/audit.json:
  duplicate_precision=1.0, recall=1.0, false_merge_rate=0.0 (10 场景 fixture 集, 含 n1-n5 负例)
- L2/Phase A 回归 93 例全绿; ruff 0; py_compile 通过

Acceptance (shadow 阶段):
- 不改变正式 source_count / Claim / Gate / 报告行为 (feature 未切换)
- 每个 cluster 有 duplicate_reason; 结果重复运行一致
- 负例原则: 同一事件 ≠ 同一稿件; 语义相关 ≠ 内容重复 (n2 独立采访 / n4 政策解读 / n5 同数不同分析 不合并)

Risks: 误判不同来源为同稿 — 缓解: 阈值保守 (high=0.90), precision 优先于 recall; 正式读路径切换需
先出 Shadow Difference Report 再决定 (Phase B 是否用 duplicate_adjusted_source_count)。

### Phase A2.5: Real-data Shadow Validation & Difference Report (2026-08-04)

- 冻结 manifest 修正: `freeze_tag` + `base_commit` + `manifest_commit=null`,
  校验以 `git rev-parse research-contract-phase-a-accepted` 为准。
- per-slot 统计修正: `family_counts` (source_family 级) 与真实 `slot_counts`
  (Evidence→Claim→Slot) 分离; 无 slot 映射时 `aggregation_level=source_family_fallback`;
  不再用 `family:<sf>` 冒充 claim slot。
- critical-fact conflict: 自动合并前检查状态词/金额/年份冲突
  (`_critical_fact_conflict`), 冲突 → candidate (reason=critical_fact_conflict), 不合并。
- SimHash 缓存 + 无正文 source 单例簇 (raw==distinct 一致性)。
- `scripts/shadow_difference_report.py` (6 题录制 DB, 禁网):
  - 6 题 total raw=196, distinct=194, reduction=0.0102; 仅 P04 有真实重复簇
    (src_019 + src_001 + src_008, confidence 0.969)
  - slot_impacts=0 (无 slot 从 satisfied 翻转为 insufficient)
  - **M03 slot 口径矛盾已修复** (2026-08-04): 根因是 evidence 引用的 ReAct 补充 source
    (src_react_*) 不在 sources 表 + 空正文 source 未进簇, 导致 raw 计入但 distinct 未计;
    修复: evidence-referenced source 并入 sources + 空正文 source 作单例簇 → 现在 raw==distinct。
  - **slot 新增字段**: supporting_evidence_count / raw_supporting_source_count /
    distinct_supporting_content_count / supporting_claim_count。
  - **invariant**: 任务级无多成员簇时 raw_source_count==distinct_content_count;
    slot 级 distinct<=raw<=evidence。当前 6 题全部通过, 0 violation。
- **人工审查清单** (`scripts/audit_pairs_review.py`):
  - 扫描全部历史 checkpoint (data/tmp, 131 DB), 按 base query id 去重取 source 最多者。
  - 全集 **218 个分层 pair** (auto_merge 3 / candidate 158 / near_threshold 33 / revision 24):
    `audit_pairs_review.md` + `audit_pairs_review.csv` + `audit_pairs_all.json`。
  - **高风险首轮审查包 (2026-08-04)**: `audit_priority_review.md` + `.csv` + `_manifest.json`
    (random_seed=20260804), 共 60 对;
    **盲审协议 (2026-08-04)**: `docs/source-clustering-annotation-protocol-v1.md`
    (annotation_schema_version=source_cluster_human_label_v1 /
    labeling_protocol_version=source_cluster_review_protocol_v1; 8 值标签定义 + merge 映射 +
    confidence 规则 + 边界规则 + 质量检查; 修改须升级版本号) +
    audit 目录副本 `data/tmp/shadow_difference_report/ANNOTATION_PROTOCOL.md`; manifest 记录协议版本。
    **盲审拆分** (2026-08-04):
    `audit_priority_review_blind.csv` (仅 Pair 内容/元数据/共同片段/独有段落/事实差异,
    human_label/confidence/notes 空白, 不含 algorithm) +
    `audit_priority_review_algorithm.csv` (按 pair_id 关联, algorithm_decision/
    algorithm_suggested_label/confidence/reason; candidate→uncertain/manual_review,
    不强行判独立报道):
    - auto_merge 全部 3; revision 全部 24;
    - 相似度最高 candidate 15 (均为 0.938 档, 用于判断 0.90 阈值是否过保守);
    - 0.78 阈值附近 10 (5 刚高于 + 5 刚低于, 判断 candidate 阈值区分力);
    - 固定 seed 随机 candidate 8。
  - 每 pair 含: 标题/URL/family/tier/发布时间、正文开头、4 项相似度子分、
    duplicate_reason、**critical_fact_conflict 具体触发值** (type/a_values/b_values/
    matched/unmatched)、最长共同连续片段、A/B 独有段落、数字/金额/年份/状态词/主体差异、
    空 human_label / human_confidence / review_notes 字段 (8 值固定词表)。
- **盲审 pilot 结果 (2026-08-04, 60 对已标注)**:
  - 标签: exact_duplicate 41 / full_reprint 17 / summary_or_excerpt 2; confidence high 51 / medium 9。
  - **数据质量问题**: 24 对为 trivial self-pairs (同 source_id+URL, duplicate source rows) →
    全部 algorithm decision=`revision` 但人工 `exact_duplicate`; 单独列 `trivial_exact_pair` 排除,
    不计入聚类 precision。已修 `scripts/audit_pairs_review.py`: `_load_sources` 按 source_id 去重 +
    revision pair 仅当 canonical URL 相同且内容指纹不同。
  - **真实跨来源 36 对**: auto_merge 3/3 precision=**1.0** (false_merge=0, 均 exact_duplicate);
    candidate 28/28 **100% merge-eligible** (14 exact + 14 full) → 0.90 auto_merge 阈值可能过保守;
    near_threshold 5: 3 full_reprint + 2 summary_or_excerpt (60% merge)。
  - revision protection rate **不可评估** (该 pool 无真实跨来源 revision pair)。
  - 汇总: `scripts/blind_review_summary.py` → `data/tmp/shadow_difference_report/
    blind_review_pilot_summary.json` + `.md`。
  - 性质: **pilot validation** (auto_merge n=3 过小, 不能稳定证明 95% 泛化 precision)。
- **阈值下探实验 + blocking rules (2026-08-04)**:
  - `source_cluster.py` 新增三类 blocking rules (auto-merge 前置精度闸):
    `critical_fact_conflict` (保守版: 状态词集合 disjoint / 金额 unit 值 mismatch /
    单一年份不同) + `summary_or_excerpt` (长度比 <0.5) + `document_type_incompatible`
    (official_policy vs commercial_media/industry_research 等)。blocking 命中 → candidate,
    不合并, 阈值不是唯一精度杠杆。
  - 初版 `_critical_fact_conflict` 对长文 (多项目多状态词) 过度触发 (33/36 误拦) →
    改为保守版 (disjoint/金额/单一年份), 消除假阳性。
  - `scripts/threshold_sweep.py`: 按 task/case 做 Calibration/Validation group split;
    逐阈值 (0.90~0.78) 输出 precision/recall/false_merge/severe_false_merge/revision_protection;
    选择规则 = severe_fp==0 AND precision>=0.95 后最大 recall。
  - **pilot 结果 (36 真实跨来源标注)**: precision 全程 1.0 (0 FP, 0 severe);
    阈值 0.90→0.80 把 recall 从 0.55 提到 0.82 (校准) / 0.61 (验证);
    **selected threshold=0.80**。revision_protection 不可评估 (pilot 无真实 revision label)。
  - Clean Pool v2 生成中 (source_id 去重 + revision 内容校验 + hard_negative 扩充,
    输出 `data/tmp/shadow_difference_report_v2/` 不覆盖旧产物)。
### Phase B.2 — Observed Read Path (shadow, 2026-08-04)

- `scripts/observed_read_path_b2.py`: 三轨 (raw / dup@0.90 / dup@0.80) 逐 Slot/Section/Report
  readiness + transition; blocking-rule 命中数; 0.80 仅标 `pilot_candidate_threshold` 不替换正式阈值。
- 6 录制 case (6b): 全 not_evaluable (field-poor), 三轨平凡相等; blocking hits:
  critical_fact_conflict=2。
- synthetic demo (明确标注 non-recorded): raw=3 satisfied / dup@0.90=3 satisfied /
  dup@0.80=2 unsatisfied (min=3) → 演示阈值 0.80 会把 slot 从 satisfied 翻转为 unsatisfied。
- 纯观测, 不改 Editor1/Claim/backfill/final report/LangGraph routing。

### Clean Pool v2 正式验证集 (2026-08-04)

- `scripts/clean_pool_v2_sample.py`: 从 733 对分层抽 **194 真实对** (auto_merge 3 +
  near_threshold 33 + candidate 78 按相似度三分层 + hard_negative 80) →
  `clean_pool_v2_sample_blind.csv` (待人工标注, 0 self-pair)。
- **26 确定性 benchmark fixtures** (`clean_pool_v2_benchmark_fixtures.json`):
  revision 20 (状态/金额/年份更新, 同 URL 内容不同) + doc-type 6
  (policy-vs-interpretation 2 / announcement-vs-analysis 2 / same-event 1 / summary 1)。
- `scripts/threshold_sweep.py` 支持 `--fixtures` + `--ablation` (blocking-rule ablation)。
- **含 fixtures 的 pilot sweep**: validation precision=1.0, recall=0.65, false_merge=0,
  severe_fp=0, **revision_protection=1.0** (20/20 revision 拦截), selected=0.78;
  ablation 显示 `none` 模式会并掉 revision (recall 0.91 但 revision_protection=0.0) →
  证明 blocking rules 必要。
- 真实样本指标与 fixture 指标分离; Validation 固定后只跑一次 (防调参污染)。
- formal read path 与 Gate Enforcement 均保持 disabled。

### Clean Pool v2 正式验证结果 (2026-08-04)

- 194 对已标注 (related 86 / full_reprint 60 / exact 27 / same_event 11 / summary 10;
  high 183 / medium 11; **无 revision / near_duplicate_rewrite 正例**)。
- 跨 checkpoint 去重: 按 canonical URL pair 去重 → 127 唯一对 (移除 67; 用户报 86, 差异因
  URL 规范化粒度)。
- Group split: Calibration 102 (含 19 fixtures) / Validation 51 (含 7 doc-type fixtures)。
- **阈值扫描 (Calibration 选阈值)**: precision 全程 1.0 (0 FP / 0 severe),
  selected threshold=**0.78** (recall 0.583)。
- **Validation (固定一次)**: precision=**1.0**, recall=**0.261**, false_merge=0, severe_fp=0,
  revision_protection=0.0 (validation 无 revision 正例)。
- **Ablation**: none 模式只能到 0.86/recall 0.28 (precision 限制); all 模式 0.78/recall 0.58 →
  证明 blocking rules 必要性。
- **结论**: Precision 1.0 PASS (最高优先级指标); **Validation recall 0.26 < 0.80 未达标**,
  根因 critical_fact_conflict 过度拦截 16 对 full_reprint/exact (嵌入细微状态词/年份差异被当
  status update)。Revision protection / near_dup_rewrite 召回无法从本批验收 (无正例)。
- 建议 (不重调, 遵守 Validation 只跑一次): 细化 critical_fact_conflict 到"同项目实体状态转移",
  补 revision 正例进 Validation split。
- 报告: `data/tmp/threshold_sweep_v2/VALIDATION_SUMMARY.md`。

### Phase A2.6 — Entity-bound Critical Fact Conflict v2 (FactFrame, 2026-08-04)

- **错误分类** (`scripts/classify_false_negatives.py`, 16 对误拦截):
  multi_entity_document 8 / text_truncation 8 (无 true_revision) →
  `data/tmp/a26_error_analysis/false_negative_classification.{json,md}`。
  根因: v1 比较整篇长文的状态词/金额/年份集合, 未判断是否同一实体+属性+口径。
- **`packages/research_harness/fact_frame.py`** (确定性, 无 LLM):
  - 抽取候选实体 (书名号/引号名 + 项目/工程/公司/政策 模板, 规范化去行政前后缀)。
  - 事实框架 `(entity, attribute, scope, value)`: 金额按类型分 (总投资/一期投资/合同/
    中标/补贴/注册资本), 状态按生命周期有序 (拟建<签约<备案<开工<建设中<试运行<投运<
    正式投运<运营<停运<终止)。
  - **exact content hash → 跳过冲突** (正文相同不可能 revision)。
  - **仅同 (entity, attribute, scope) 值不同 → 硬冲突**; 未绑定差异 → 不硬拦截 (仅风险提示)。
- 接入 `source_cluster.blocking_reasons` (critical_fact_conflict 走 v2); candidate 带也
  surface blocking reason。
- 测试: `tests/test_research_harness_fact_frame.py` 8 例 (exact-hash skip / 同实体同口径
  金额冲突 / 总投资vs一期不冲突 / 多实体不冲突 / 同实体状态revision / 未绑定不冲突 /
  实体抽取 / 事实绑定) + source_cluster 回归 22 例; 全量 111 例全绿。
- **阈值配置** (记录):
  ```json
  {"production_threshold": 0.90, "pilot_candidate_threshold": 0.78,
   "entity_bound_conflict_version": "factframe_v2_implemented", "formal_read_path": "disabled"}
  ```
- **v2 Validation 已冻结为 Error Analysis Set**, 不重调; 下一轮 Calibration v3 /
  Validation v3 由剩余未标注 pool + 新 revision benchmark 构建 (Validation 固定跑一次)。

### Phase B.1: Shadow CoverageReport Integration

Status: **shadow implementation complete** (2026-08-04; 只写 Shadow State + 差异报告,
不阻止 Editor1, 不修改 Claim 强度, 不改变最终报告)

Implementation (`packages/research_harness/sufficiency_gate.py`, shadow only):
- `build_shadow_coverage_report(state)` → 完整双轨 CoverageReport:
  - report: report_version/mode/shadow_only/contract_id/clustering_version
  - critical_gate: enabled (显式 critical_slots) / reason (NO_CRITICAL_SLOT_DECLARED)
  - summary: raw_required_slot_coverage / duplicate_adjusted_required_slot_coverage /
    ready_section_count(×2) / would_block_if_*_enabled / would_change_decision
  - slots: supporting_evidence_count / raw_supporting_source_count /
    distinct_supporting_content_count / supporting_claim_count / source_family_compliance /
    primary_source_satisfied / field_requirements_satisfied / contradiction_status /
    independence_requirement_status=not_evaluated / content_distinctness_proxy_satisfied /
    raw_status / duplicate_adjusted_status / transition / affected_claim_ids /
    blocking_reasons / search_execution
  - sections: raw_status / duplicate_adjusted_status / transition (ready/partial/blocked)
  - research_gaps: shadow_reportability (eligible_if_enabled / not_evaluated) +
    shadow_report_expression + shadow_approval_reasons; approved_report_expression 恒 None
  - warnings
- slot 判定确定性公式: evidence_count>=min_evidence_items AND count_requirement>=
  min_raw_supporting_sources (raw) / min_distinct_content_sources (dup) AND family_compliance
  AND primary_satisfied AND field_requirements_satisfied AND contradiction 未 unresolved。
  **数量门槛分离** (review 2026-08-04): min_evidence_items / min_raw_supporting_sources /
  min_distinct_content_sources / min_independent_sources 各自独立, 不再用同一 min_evidence
  同时限制 Evidence 与 Source。
- **三态 (satisfied/unsatisfied/not_evaluable)**: 历史 checkpoint 缺结构化 key_field 或
  search_events → field_requirements/source_family_compliance/search_sufficiency 为 not_evaluable;
  count 子阈值且无搜索记录 → count not_evaluable (区分"未找到"vs"未搜索")。
  readiness 增 "unknown"; not_evaluable slot 不计入 coverage=0 (coverage 分母 = evaluable)。
- Content Cluster 只作 distinct-content proxy; independence_requirement_status=not_evaluable,
  不宣称真正 independent source。
- search_execution 记录 (planned/executed/successful/failed/searched_source_families/
  pending/search_rounds/stop_reason/search_sufficiency_status) 区分"未找到"vs"未搜索"。
- 集成: `build_claims_provider_backed` 末尾挂 `state["shadow_coverage_report"]` (shadow only)。
- 兼容: `build_shadow_sufficiency_report` 保留为 legacy wrapper。
- 验证: tests/test_research_harness_sufficiency_gate.py 11 例 (含 B.1 spec 8 类 +
  M03 fixture L2 replay + determinism)。

结果 (`scripts/shadow_coverage_report.py`, 6 录制 case, 三态):
- 6 case 每 case 全部 slot = **not_evaluable** (6-7 个), satisfied=0, unsatisfied=0,
  flips=0, readiness=unknown。
- 原因 (诚实): 6b checkpoint 缺结构化 key_field AND 缺 search_events → 按 review 规则
  必须 not_evaluable, 不得判 false。双轨等式由此平凡相等。
- eligible_gaps=0 (research_gaps 未持久化到 6b checkpoint; search_events 未持久化 →
  not_evaluable, 不能断言"暂未发现")。

Phase B.1 边界 (review 2026-08-04):
- 只写 Shadow State (`shadow_source_clustering`, `shadow_coverage_report`) 与差异报告。
- 不接入最终 gate 决策 / 不阻止 Editor1 / 不触发 backfill / 不改 claim assertion /
  不批准 writing expression / 不改变最终报告。
- 等 A2 shadow validation (人工审查 priority 60 pair) accepted 后, 才决定是否让
  duplicate_adjusted_source_count 参与 CoverageReport 正式读路径。

Objective: 明确"当前 Claim Pack 是否足以写报告"，且 critical 不可补偿。

Modification:
- `weighted_slot_coverage` (critical=3/required=2/optional=1) 作可视化/排序/评分
- **critical slot 硬门禁**: `report_ready = all_critical_slots_satisfied and required_coverage>=0.8 and no_blocking_contradictions and source_independence_passed and critical_claims_have_primary_sources`
- section_readiness (ready/partial/blocked) 含 blocking_reasons
- structured research_gaps (含 suggested_search_actions) 驱动现有 `_evidence_react_backfill`
- 停止条件: 关键 Gap 满足 / 预算耗尽 / 连续两轮无新增有效证据 (不再固定"补10源")

Validation:
- 8 个人工场景单元测试 (同稿多源/签约未投运/只政策无项目/数字不一致/后半段 unsupported/单一低等级/证据在claim缺/contradiction未解决)
- critical slot 缺失时 Gate 必须 blocked，不得被 optional 加权补偿

Acceptance:
- critical 缺失不可通过; 同 origin 不重复计独立来源; Gate 输出可执行 Gap; 决策可由规则复现

Risks: Gate 过严致报告不出 — 缓解: critical 缺失时 allowed_writing_mode=evidence_gap_only (降级输出, 不硬阻断)

### Phase C: 全量分层审查

Status: pending

Objective: 消除"只读前 1000-1200 字"的伪全量审查。

Modification (分层, 非全 LLM):
- **第一层 (确定性, 全量, 成本低)**: 引用 ID 存在、数字在 Evidence、日期/主体一致性、Claim 有效、paragraph 绑定 Claim、未批准 Claim、limitation 遗漏、cluster 重复计数
- **第二层 (Section-level Editor2)**: 每 Section 一次调用, 输入 Section Markdown + paragraph map + related Claim Cards + Evidence + Section Coverage
- **第三层 (高风险 Claim-level Verifier)**: 仅 critical/numeric/causal/预测/单一来源/低等级/有 contradiction/inferred 的 Claim 单独验证

Validation:
- 报告后半段故意放 unsupported claim → 检出率 = 前半段
- 未注册数字检出率 >=95%; citation integrity 错误检出率 100%

Acceptance:
- 每个 Section 被审查; 每个高风险 Claim 被验证; Editor2 issue 定位到 paragraph/claim_id

Risks: LLM 调用量增 — 缓解: 分层, 普通任务只走确定性+Section 层

### Phase D: Planner 收敛

Status: pending

Objective: 明确各 Planner 唯一职责，解决职责重叠。

Modification:
- `intent_normalizer`: 只规范化 query + 显式约束, 不生成搜索词/不规划章节
- `blueprint_planner`: 从 ResearchIntent 生成 ResearchContract (sections/claim_slots/evidence_requirements/writing_policy)
- `retrieval_planner`: 从 claim_slots 生成 search tasks (不再 dimension 驱动)
- `search_phrase_augmenter`: 只改写搜索表达, 不改 slot/family/region

Validation:
- 100% search task 绑定 claim_slot; 地域/时间约束丢失率 <2%; 域名全来自 Registry; 不再三套独立搜索规划

Acceptance:
- Contract 驱动检索; 每个节点只改自己字段; Planner 改动后 6/10/50 题回归不退化

Risks: Planner 改动影响全下游 — 缓解: 在 A/B/C 稳定后才动, 且 shadow 对比

### Phase E: 高级能力 (后续)

Status: pending

Objective: 高级来源溯源 + 治理完善。

Modification (future):
- origin_source_id 高置信判定 (真实原始发布者)
- 转载链/传播路径
- Prompt Registry UI
- 成本优化/缓存
- 复杂 discovery_policy
- 跨任务 Evidence 复用

## Continue Rule

每 Phase 验收通过且无 protected-contract 未授权改动 → 自动下一 Phase。Phase 0 进行中。

## Done Condition

- Prompt 全 trace 含 version/hash (Phase 0)
- 核心 6 schema formalize (Phase A)
- 基础来源聚类在 Gate 前生效 (Phase A2)
- critical slot 硬门禁 + slot-driven Claim (Phase B)
- 全量分层审查覆盖后半段 (Phase C)
- Planner 职责收敛 (Phase D)
- 50 题里程碑: critical_slot_satisfaction / claim_grounding / unsupported_sentence / source_independence / numeric_consistency 达标
- STATUS 与本 PLAN 一致

## Stop Conditions

- protected contract 需改未授权
- 回归指标 (6 题 coverage) 持续下降无修复
- 用户暂停
- 达 Done

## Validation Loop

每 Phase 跑对应 focused 测试 + 6 题 smoke。里程碑 (B/C/D 后) 跑 50 题。

## Progress

### 2026-06-23: PLAN 创建

- 方案源 Codex 重构方案 + 用户评审 (调整 Phase 0→A→A2→B→C→D→E, 5 项硬要求)
- 用户评审 5 项补入: (1) Prompt Registry 最低版进 Phase 0; (2) 基础聚类提前 A2; (3) critical 硬门禁; (4) Claim Expander slot-driven; (5) additive/dual-write/shadow/feature-flag
- 4 决策点答案: quoted_span 单独存(带 chunk+offset+substring 校验); 去重提前 A2; 全量审查用"确定性+Section+高风险Claim"分层; 纳入 .agent/PLANS
- 现有 evidence-react PLAN 标记为 parent 前置工作

## Risks And Rollback

| Risk | 缓解 | 回退 |
|---|---|---|
| LLM 输出 token 增 (quoted_span) | 限 50-150 字符 + 确定性校验 | 关 quoted_span 字段 |
| Gate 过严报告不出 | critical 缺失走 evidence_gap_only | 调软阈值 |
| 聚类误判 | 标题+指纹双重 + 保守阈值 | 停聚类层 |
| 全量审查成本 | 分层 (确定性+Section+高风险) | 关高风险层 |
| real_nodes proxy 限制 | 走 wrapper 层 | 撤销 patch |

## Next Action

Phase A2: 基础来源聚类 (Shadow Mode)。canonical_url / normalized_title / content_fingerprint /
content_cluster_id / duplicate_confidence; 先只写 shadow 字段
(`shadow_independent_source_count` vs `old_independent_source_count` + affected_slots), 不改变
正式 independent_source_count 和 Gate 行为; L2 fixture 验证后再切换读路径。L3 live 里程碑按计划在
B/C/D 后跑 50 题。
