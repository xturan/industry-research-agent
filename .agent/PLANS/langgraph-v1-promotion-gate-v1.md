# LangGraph v1 Promotion Gate v1

Status: active_phase4_edge_case_matrix_audited

Created: 2026-06-13

Primary active PLAN: no

## Objective

Validate whether `graph_v1` has reached promotion readiness without expanding
the broader graph productization scope.

Current reality:

- graph-v1 can complete the mechanical loop:
  search -> source -> evidence -> claim -> report -> dossier -> PASS
- but Phase 5 live smoke showed that mechanical PASS is not enough
- company/disclosure and local/source-depth cases can still pass with shallow or
  mismatched evidence

This plan exists to harden the promotion gate, not to reopen the whole
productization roadmap.

## Task Classification

- Primary area: `research_workflow`
- Secondary areas: `provider_layer`, `source_layer`, `eval_policy_ops`,
  `task_substrate`
- Expected execution mode:
  - `light_subagent` or direct scoped implementation for local rule/gate work
  - `remediation_gate` if live validation fails

## Protected Contracts

Do not silently change:

- legacy `/deep-research/analyze` response shape
- legacy `/research/analyze` response shape
- public `DeepResearchReport`, `EvidenceItem`, `SourceAssessment` schemas
- existing `EvidenceBundle` / citation fields
- existing task/job status semantics
- existing `runs` / `run_steps` meaning
- `research_reports.dossier_path`

graph-v1 must remain opt-in throughout this plan.

## Scope

In scope:

1. Search reliability gate:
   teach Chief Gate to consider partial provider failure.
2. Query-intent obligation enforcement:
   add explicit obligation checks for disclosure-grade and local/source-depth
   evidence.
3. Evidence-readiness validation:
   ensure source-family coverage is backed by evidence/claim linkage, not just
   by raw source presence.
4. Cost-capped live smoke:
   rerun the three representative cases after hardening.
5. Smoke artifact observability:
   summary output must expose the exact gate-relevant diagnostics.

Out of scope:

- replacing legacy Deep Research endpoints
- changing public research response schemas
- running a full 50-query live evaluation
- introducing new agent roles or a new graph topology
- UI or frontend work

## Baseline

This plan starts after:

- `langgraph-research-productization-v1.md` Phase 6 decision
- graph-v1 report artifact persistence is implemented
- graph report API is implemented
- three provider-backed live smoke runs completed

Confirmed blockers from Phase 5 artifact inspection:

1. Company/disclosure case:
   query asks for annual-report or disclosure evidence, but no
   `company_disclosure` source family is present.
2. Local/source-depth case:
   query asks for Hefei local evidence, but only 1 of 5 sources is actually
   location-matched.
3. Search reliability:
   some cases still PASS despite `search_error_count / search_event_count`
   exceeding 30 percent.

## PASS Thresholds

All thresholds must be observable in code or smoke artifacts. Do not rely on
subjective interpretation.

| Metric | Threshold | Meaning |
|---|---|---|
| `runtime_success` | `status == "succeeded"` | The graph run completes end to end. |
| `search_error_rate` | `search_error_count / max(search_event_count, 1) <= 0.30` | Too many failed searches should not still look fully healthy. |
| `retry_rate` | `retry_event_count / max(search_event_count, 1) <= 0.50` | Retrying is acceptable, but repeated recovery should remain visible as risk. |
| `required_obligation_coverage` | every required obligation has at least one matched supporting source | Raw source presence is not enough; the source must support a claim. |
| `claim_support_matrix_completeness` | no required claim remains unsupported | Every required claim needs linked evidence and matching source family. |
| `local_precision` | for local queries, `matched_location_source_count / max(source_count, 1) >= 0.30` | Local queries need a meaningful portion of location-matched sources. |
| `dossier_readability` | required dossier sections exist | Search Events, Sources, Claim Support Matrix, Claim Verifications, Final Report Preview. |

Interpretation rules:

- `required_obligation_coverage` means:
  if the query asks for disclosure, at least one linked supporting source must
  be `company_disclosure`;
  if the query asks for local/source-depth evidence, at least one linked
  supporting source must be location-matched.
- `local_precision` is a guardrail, not the only criterion.
  Even if the ratio passes, the linked evidence must still support the claim.

## Phases

### Phase 1: Search Reliability Gate And Semantic Planner

Status: active

Objective:

- Make partial provider failure visible to Chief Gate and smoke artifacts.
- Upgrade `plan_task` from pure rule expansion to semantic planning with API
  assistance plus deterministic fallback.

Tasks:

- Add `search_error_rate` and `retry_rate` diagnostics.
- Add `unstable_search_rate` so retry-recovered failures still remain visible.
- Reduce gate confidence or route to `REVIEW_RISK` / `HUMAN_REVIEW` when
  provider instability is too high.
- Add API-assisted semantic understanding in `plan_task` so the planner can
  infer disclosure, locality, and evidence obligations more accurately than
  simple keyword expansion.
- Keep deterministic fallback active when the planner API is unavailable or
  returns invalid output.
- Keep the policy/procurement case stable when search failure remains within the
  allowed band.

Acceptance criteria:

- `search_error_rate` is computed and exposed in smoke output.
- `retry_rate` is computed and exposed in smoke output.
- `unstable_search_rate` is computed and exposed in smoke output.
- `plan_task` can use the configured JSON LLM provider to enrich query
  requirements and search phrases.
- Invalid or unavailable planner output falls back safely to deterministic
  planning.
- High search instability can no longer silently PASS as fully healthy.

Validation:

```powershell
pytest -q tests/test_research_harness_graph.py
```

### Phase 2: Source-Family And Locality Obligations

Status: pending

Objective:

- Model query intent explicitly enough that graph-v1 can reject shallow PASS
  outcomes.

Tasks:

- Detect disclosure-oriented query intent.
- Detect location-sensitive query intent for local/source-depth cases.
- Persist or carry required obligations through the plan state.
- Make `build_claims`, `editor2_review`, `verify_claims`, or `chief_gate`
  enforce these obligations.

Acceptance criteria:

- A disclosure query without `company_disclosure` support can no longer PASS.
- A local query with weak location match can no longer PASS silently.
- Required actions explain what is missing.

Validation:

```powershell
pytest -q tests/test_research_harness_graph.py tests/test_research_api.py
```

### Phase 3: Narrow Live Revalidation

Status: pending

Objective:

- Rerun the representative smoke cases after the hardening work.

Cases:

1. Policy/procurement:
   `2025年低空经济政策与公共资源采购中标证据 官方来源`
2. Company/disclosure:
   `2025年低空经济上市公司年报披露与官方政策证据`
3. Local/source-depth:
   `2025年合肥低空经济地方政策项目公示官方来源`

Acceptance criteria:

- Case 1 remains healthy and can still PASS.
- Case 2 no longer PASSes when disclosure-grade evidence is absent.
- Case 3 no longer PASSes when location precision is too weak.
- Smoke artifacts expose the exact reason for the gate outcome.

Validation:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\promotion_gate_v1_case_policy --query "2025年低空经济政策与公共资源采购中标证据 官方来源" --max-rounds 1
python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\promotion_gate_v1_case_disclosure --query "2025年低空经济上市公司年报披露与官方政策证据" --max-rounds 1
python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\promotion_gate_v1_case_local --query "2025年合肥低空经济地方政策项目公示官方来源" --max-rounds 1
```

## Continue Rule

After each phase passes validation, continue to the next phase automatically
unless a protected-contract, credential, repeated validation, or user-pause
blocker appears.

## Validation Loop

Baseline checks:

```powershell
python -m ruff check packages\research_harness apps\api\routes\deep_research.py scripts\graph_provider_backed_smoke.py tests\test_research_harness_graph.py tests\test_research_api.py tests\test_research_run_dossier.py
python -m py_compile packages\research_harness\runner.py packages\research_harness\service.py packages\research_harness\schemas.py apps\api\routes\deep_research.py scripts\graph_provider_backed_smoke.py
pytest -q tests\test_research_harness_graph.py tests\test_research_api.py tests\test_research_run_dossier.py
pytest -q tests\test_tasks_service.py tests\test_tasks_api.py
```

Provider contract checks when needed:

```powershell
pytest -q tests\test_agents_workflow.py
pytest -q tests\test_research_provider_integration.py
pytest -q tests\test_deepseek_provider.py
```

## Stop Conditions

Stop and ask the user only when:

- a protected public contract would need to change
- provider credentials or live budget are unavailable
- validation fails repeatedly and the safe repair path is unclear
- the work would require browser automation, OCR, login-gated data, or
  paid/private data outside scope
- the user explicitly pauses or redirects

## Risks

- Over-hardening the gate could hurt the policy/procurement case.
- Query-intent rules could become too brittle if they overfit a single query.
- Locality checks based only on strings may miss some real location matches or
  accept weak ones.

## Progress

### 2026-06-13

Plan created from post-smoke artifact inspection.

Known blockers:

- disclosure queries can pass without disclosure-grade evidence
- local queries can pass with weak location precision
- partial provider search failure can still appear healthier than it should

### 2026-06-13 - Phase 1 started

- User approved continued implementation.
- Active slice now includes semantic-planner hardening in `plan_task`.
- Current target:
  add API-assisted semantic planning with deterministic fallback, while keeping
  graph-v1 opt-in and public contracts unchanged.

### 2026-06-13 - Phase 1 progress update

- Added `packages/research_harness/plan_semantic.py` as a dedicated semantic
  planner module for `plan_task`.
- `plan_task` now supports:
  - semantic planner first
  - strict schema validation
  - deterministic fallback
  - planner metadata visibility in run steps
- Added `planner_replan_request` so `Chief Gate` can hand structured evidence
  gaps back to the next planning round.
- Changed `ADD_EVIDENCE` routing from direct `collect_sources` replay to
  `plan_task -> collect_sources`, so the next search round can be replanned.
- Added smoke observability for:
  - `planner_mode`
  - `planner_reason`
  - `planner_first_mode`
  - `planner_first_reason`
  - `required_obligation_coverage`
  - `planner_replan_request`
- Strengthened semantic planner repair logic:
  partial or slightly malformed JSON payloads can now be normalized instead of
  immediately falling back.
- Real disclosure smoke now shows:
  - first planner invocation: `semantic_provider`
  - second replan invocation: `semantic_provider` with repaired payload
  - final decision: `HUMAN_REVIEW`
  - unresolved obligation: `company_disclosure`

### 2026-06-13 - Richer deterministic planner inherited from legacy DeepResearchAgent

- Upgraded `plan_task_provider_backed` deterministic fallback so it no longer
  stops at a shallow two-bucket query expansion.
- The fallback planner now carries forward the older DeepResearchAgent-style
  strengths:
  - richer `research_dimensions`
  - `caliber_notes`
  - themed `search_rounds`
  - `target_dimensions`
  - dynamic round priority under small `max_rounds`
- Added intent-aware deterministic dimensions and rounds for:
  - national policy grounding
  - local rollout / locality-matched evidence
  - auditable execution evidence
  - company disclosure evidence
  - statistics / corroboration
- Added focused tests proving that:
  - disclosure queries with `max_rounds=2` now prioritize a disclosure round
  - local queries with `max_rounds=2` now prioritize a locality-focused round
- Validation passed:
  - `python -m py_compile packages\research_harness\real_nodes.py tests\test_research_harness_graph.py`
  - `python -m ruff check packages\research_harness\real_nodes.py tests\test_research_harness_graph.py`
  - `pytest -q tests\test_research_harness_plan_semantic.py`
  - `pytest -q tests\test_research_harness_graph.py`
  - `pytest -q tests\test_agents_workflow.py`
  - `pytest -q tests\test_research_api.py`
  - `pytest -q tests\test_research_provider_integration.py`
  - `pytest -q tests\test_deepseek_provider.py`
- Live smoke reruns after the richer fallback change:
  - policy / procurement case:
    `data/tmp/promotion_gate_v1_case_policy_richer_fallback`
    - `decision=PASS`
    - `planner_mode=semantic_provider`
    - `obl_policy_primary` and `obl_procurement_award` both covered
  - disclosure case:
    `data/tmp/promotion_gate_v1_case_disclosure_richer_fallback`
    - `decision=PASS`
    - `planner_mode=semantic_provider`
    - `obl_policy_primary` and `obl_company_disclosure` both covered
  - local / source-depth case:
    `data/tmp/promotion_gate_v1_case_local_richer_fallback`
    - `decision=PASS`
    - `planner_mode=deterministic_fallback`
    - `planner_reason=provider_error:ProviderParseError`
    - `local_precision=0.75`
    - fallback preserved locality coverage despite semantic-provider parse failure

Risks surfaced by this slice:

- The richer fallback is now materially stronger, but live local queries can
  still hit semantic-provider parse fragility and drop into deterministic mode.
- Repo-wide `ruff check .` is not a reliable signal for this PLAN right now
  because unrelated generated/tooling directories emit pre-existing noise.

### 2026-06-13 - Semantic local-query stability hardening

- Hardened `packages/providers/deepseek.py` so JSON parsing is more tolerant of
  common provider wrappers:
  - markdown fenced JSON
  - extra leading or trailing prose around the JSON object
- Hardened `packages/research_harness/plan_semantic.py` prompt construction:
  - fallback draft and replan context are now injected as real JSON strings,
    not Python `dict` repr
  - prompt now explicitly requires output to start with `{` and end with `}`
  - prompt explicitly forbids markdown fences and extra prose
- Hardened semantic/fallback merge semantics:
  - semantic planner may enrich or refine the plan
  - but it may no longer silently weaken fallback-derived hard obligations such
    as `needs_company_disclosure`, `target_location`, or fallback disclosure
    obligations already justified by query intent
- Added regression coverage for:
  - DeepSeek JSON extraction from markdown fence wrappers
  - DeepSeek JSON extraction from wrapped prose
  - planner prompt using JSON reference blocks instead of Python repr
  - planner merge preserving fallback disclosure constraints even when the
    semantic payload omits them
- Validation passed:
  - `python -m py_compile packages\providers\deepseek.py packages\research_harness\plan_semantic.py tests\test_deepseek_provider.py tests\test_research_harness_plan_semantic.py`
  - `python -m ruff check packages\providers\deepseek.py packages\research_harness\plan_semantic.py tests\test_deepseek_provider.py tests\test_research_harness_plan_semantic.py`
  - `pytest -q tests\test_deepseek_provider.py`
  - `pytest -q tests\test_research_harness_plan_semantic.py`
  - `pytest -q tests\test_research_harness_graph.py -k "disclosure_query or local_query_flags or plan_task_provider_backed"`
  - `pytest -q tests\test_research_harness_graph.py`
  - `pytest -q tests\test_research_api.py`
  - `pytest -q tests\test_research_provider_integration.py tests\test_deepseek_provider.py`
  - `pytest -q tests\test_agents_workflow.py`
- Live smoke reruns after this hardening:
  - local case:
    `data/tmp/promotion_gate_v1_case_local_semantic_repair_v2`
    - `decision=PASS`
    - `planner_mode=semantic_provider`
    - `planner_reason=semantic_plan_repaired`
    - `local_precision=0.75`
  - disclosure case:
    `data/tmp/promotion_gate_v1_case_disclosure_semantic_guard_v2`
    - `decision=PASS`
    - `planner_mode=semantic_provider`
    - disclosure obligation remained covered after merge hardening

Updated risk view:

- The previous local-query `ProviderParseError` blocker is no longer the active
  dominant issue for the canonical smoke set.
- The next decision is no longer “can local semantic planning work at all”;
  it is “is this narrow three-case gate enough, or do we need a broader
  promotion-readiness sample before changing graph-v1 status.”

### 2026-06-13 - Broader promotion smoke matrix

- Added `scripts/graph_provider_backed_smoke_matrix.py` so broader promotion
  checks can be run as one batch instead of ad hoc one-case shell invocations.
- The matrix runner reuses the existing single-case smoke script, writes:
  - per-case `matrix_case_summary.json`
  - top-level `live_summary.json`
  - top-level `live_summary.md`
- Added `tests/test_graph_provider_backed_smoke_matrix.py` to lock the
  aggregation behavior for:
  - status / decision / planner-mode counts
  - semantic repaired vs deterministic fallback counts
  - unstable / uncovered-obligation case extraction
- Ran the broader matrix with five real API-backed cases:
  - `P01` policy/procurement
  - `D01` disclosure
  - `L01` Hefei local
  - `L02` Wuhan local
  - `E01` implementation/project evidence
- Real matrix artifact:
  `data/tmp/graph_provider_backed_smoke_matrix_v1`
  with markdown report:
  `data/tmp/graph_provider_backed_smoke_matrix_v1/live_summary.md`
- Matrix outcome:
  - `total_cases=5`
  - `status_counts={'succeeded': 5}`
  - `decision_counts={'PASS': 5}`
  - `planner_mode_counts={'semantic_provider': 5}`
  - `planner_reason_counts={'semantic_plan_accepted': 5}`
  - `deterministic_fallback_count=0`
  - `unstable_case_ids=[]`
  - `uncovered_obligation_case_ids=[]`
  - `average_final_score=0.906`
  - `estimated_tavily_credits=30`
- Validation passed:
  - `python -m py_compile scripts\graph_provider_backed_smoke_matrix.py tests\test_graph_provider_backed_smoke_matrix.py`
  - `python -m ruff check scripts\graph_provider_backed_smoke_matrix.py tests\test_graph_provider_backed_smoke_matrix.py`
  - `pytest -q tests\test_graph_provider_backed_smoke_matrix.py`

Updated risk view after the broader sample:

- The current blocker is no longer semantic planner fragility on the canonical
  local case set.
- The promotion question has shifted from “is graph-v1 still flaky on obvious
  intent types?” to “how much more evidence is needed before revisiting the
  opt-in/default boundary.”

### 2026-06-13 - Edge-case matrix and multi-location normalization

- Extended the matrix runner to accept external case files:
  `--cases-file`
- Added edge-case case set:
  `scripts/graph_provider_backed_smoke_cases_edge_v1.json`
- Edge cases covered:
  - `local + disclosure`
  - `policy + statistics`
  - `project + disclosure`
  - `multi-city compare`
  - `disclosure + procurement`
- During the first edge run, found a real modeling bug:
  semantic or planner-derived `target_location` values could contain
  comma-joined or malformed strings that polluted location obligations and
  created false `HUMAN_REVIEW` outcomes.
- Hardened `packages/research_harness/real_nodes.py` to:
  - normalize semantic `query_requirements`
  - extract multiple target locations explicitly
  - compute `matched_ratio`, `required_locations`, and `matched_locations`
  - require all target locations to be represented for multi-city coverage
  - generate per-location replan hints instead of comma-joined pseudo-locations
- Added regression coverage for:
  - multi-location extraction from query
  - multi-city location coverage summary
  - dropping non-location text from semantic `target_location`
- Validation passed:
  - `python -m ruff check packages\research_harness\real_nodes.py tests\test_research_harness_graph.py scripts\graph_provider_backed_smoke_matrix.py tests\test_graph_provider_backed_smoke_matrix.py`
  - `pytest -q tests\test_research_harness_graph.py`
  - `pytest -q tests\test_graph_provider_backed_smoke_matrix.py tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py`
- Real edge matrix artifact:
  `data/tmp/graph_provider_backed_smoke_matrix_edge_v3`
  with markdown report:
  `data/tmp/graph_provider_backed_smoke_matrix_edge_v3/live_summary.md`
- Edge matrix outcome after the fix:
  - `total_cases=5`
  - `decision_counts={'PASS': 4, 'HUMAN_REVIEW': 1}`
  - `planner_mode_counts={'semantic_provider': 5}`
  - `deterministic_fallback_count=0`
  - remaining uncovered-obligation case: `X01`
  - fixed false negative: `X04 multi-city compare` now passes

Updated risk view after the edge matrix:

- The dominant remaining issue is no longer multi-location parsing.
- The remaining edge gap is narrower and more interpretable:
  a mixed `local + disclosure` query with the current round/loop budget still
  fails to secure both disclosure-grade and locality-matched evidence in one
  run.

## Next Action

Continue from the edge-case-audited state:

1. Decide whether `X01 local + disclosure` is an acceptable guarded boundary
   for the current opt-in baseline, or
2. Open one more narrow implementation slice aimed specifically at mixed
   `local + disclosure` planning/search coverage
