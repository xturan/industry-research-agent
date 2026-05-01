# Source Multigranular Evidence Sufficiency v1

Status: completed_with_successor_blocker

Created: 2026-04-29

Primary active PLAN: no

Supersedes execution follow-up from:

- `.agent/PLANS/archive/source-structured-evidence-backbone-v1.md`

## Objective

Raise source-quality results from "source classes are present" to "evidence is sufficient for the query's administrative level, sector split, and claim type."

The previous structured-evidence backbone materially improved runtime and source-class coverage:

- Live gate: `12 success / 0 runtime error`
- DeepSeek audit transport/schema: `12 success`, shape diagnostics `0`
- Audit blockers: `0`
- Source-count thresholds passed:
  - `project_list=1` missing vs target `<=5`
  - `tender_or_procurement=3` missing vs target `<=5`
  - `local_government=1` missing vs target `<=3`
  - `statistics=2` missing vs target `<=3`
  - `environmental_or_land_record=1` missing vs target `<=2`

But the 12-case quality threshold still failed:

- Audit verdicts: `7 fail / 5 weak_pass / 0 pass`
- Required gate: at least `6/12` weak/pass or fail count `<=6`
- Result: failed by one case.

The remaining issue is not broad source-class coverage. It is evidence sufficiency:

- a province-level distribution query needs multi-city evidence, not one anchor-city example
- a city-level cluster query needs city-specific project/statistics/land/company evidence, not national or provincial substitutes
- a macro policy-transmission query needs aggregate data and demand/industry metrics, not only project examples
- a multi-sector query needs explicit sector sublanes
- a county query needs exact-local or transparently marked parent fallback evidence

This PLAN must improve reusable retrieval and evidence-quality patterns. It must not overfit individual 50-query examples.

## Task Classification

- Primary area: `source_layer`
- Secondary areas: `domestic_source_collectors`, `eval_policy_ops`, `provider_layer`

Protected contracts:

- EvidenceBundle schema
- EvidenceItem citation fields
- `source_quality_summary` shape
- research analyze response shape
- provider abstraction semantics
- source routing response shape
- task/job status semantics
- direct-keep primary paths
- legacy `enable_source_acquisition=False` behavior

No protected-contract change is allowed without an explicit Architecture Gate section in this PLAN.

## Design Direction

Treat source coverage and evidence sufficiency as different gates.

```text
User Query
  -> query decomposition
  -> evidence obligation planner
  -> administrative granularity lanes
  -> sector / entity / metric sublanes
  -> source family routing
  -> extraction and diagnostics
  -> evidence sufficiency gate
  -> audit-visible package
```

Core additions:

- `administrative_granularity_obligation`: macro/province/city/county evidence requirements.
- `multi_city_distribution_obligation`: province-level distribution or coordination questions need non-anchor-city evidence.
- `multi_sector_obligation`: queries that name several sectors need separate sector sublanes.
- `quantitative_metric_obligation`: demand, cost, capacity, price, fiscal, and statistics claims need quantitative evidence.
- `exact_local_obligation`: county/city claims must distinguish exact-local, parent-local, and national evidence.
- `evidence_sufficiency_gate`: source classes are not enough when source level, source count, or claim match is weak.

## Scope

In scope:

- Query decomposition and retrieval-plan metadata that express evidence obligations.
- Source profile/domain patterns for reusable local, statistical, land/environment, public-resource, industry, and disclosure evidence.
- Evidence quality scoring and batch diagnostics that distinguish source-class presence from claim support.
- Offline and low-cost live validation using the 12-case smoke set.
- Staged decision about the 50-query run only after the 12-case quality gate materially improves.

Out of scope unless reopened:

- Browser automation as a default path.
- OCR.
- Login-gated, paid, or private data.
- Full 50-query live run before a passing or explicitly accepted 12-case gate.
- Direct securities investment advice.
- Public API contract shape changes.

## Agent Execution Contract

Use this role model only when subagents are explicitly authorized:

- `invest_project_director`: owns scope, prevents query overfitting, and verifies that changes target reusable evidence-sufficiency patterns.
- `invest_agent_architecture_builder`: owns obligation schema compatibility and protected-contract review.
- `invest_feature_programmer`: owns implementation in `packages/sources/**`, eval scripts, and tests.
- `invest_code_quality_checker`: owns ruff, py_compile, focused pytest, and scope checks.
- `invest_functional_validator`: owns artifact and live validation against the 12-case gate.
- `invest_project_summarizer`: runs only after the final done condition.

Workers must not add query-ID branches. Validation cases are pressure tests, not production logic inputs.

## Phases

### Phase 0: Failure-To-Obligation Matrix Freeze

Objective:

- Convert the latest 12-case quality failure into reusable evidence obligations.

Tasks:

- Read:
  - `data/tmp/source_quality_stress_eval/runs/source_structured_evidence_backbone_v1_phase5_live_v1/batch_eval.json`
  - `data/tmp/source_quality_stress_eval/runs/source_structured_evidence_backbone_v1_phase5_live_v1/source_roadmap.json`
  - `data/tmp/source_quality_stress_eval/runs/source_structured_evidence_backbone_v1_phase5_live_v1/llm_audit/*.json`
- Group remaining failures by obligation family, not query ID.
- Freeze Phase 1 implementation target.

Acceptance criteria:

- A failure-to-obligation matrix exists.
- The next implementation target is explicit.
- No production code changed.

Validation:

```powershell
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\source_structured_evidence_backbone_v1_phase5_live_v1 --print-json
```

### Phase 1: Evidence Obligation Planner

Objective:

- Make query decomposition and retrieval planning express the evidence needed to answer the query, not just task family and source class.

Tasks:

- Add obligation metadata for:
  - macro aggregate data / central policy / policy-transmission claims
  - province multi-city distribution and coordination claims
  - city cluster claims
  - county exact-local claims
  - multi-sector and multi-entity claims
  - quantitative metric claims
- Add deterministic tests for representative generic patterns.
- Keep existing public response contracts backward compatible.

Acceptance criteria:

- Tests show that P04-style province distribution queries require multi-city evidence.
- Tests show that P10/C07-style multi-sector queries produce sector-aware obligations.
- Tests show that M02/M06/P08-style cost/demand/capacity queries require quantitative metric evidence.
- Tests show that K07/K12-style county queries retain exact-local obligation metadata.

### Phase 2: Source Profile And Lane Expansion

Objective:

- Convert obligations into reusable source profiles and lane routing, without hard-coding query IDs.

Tasks:

- Add or strengthen source patterns for:
  - local government department portals
  - local statistics/fiscal releases
  - local public-resource/procurement portals
  - local land/environment records
  - province/city industry association and price/capacity sources
  - region-matched disclosure candidates
- Add multi-city expansion rules for province distribution queries.
- Add multi-sector lane expansion rules for sector-mix queries.
- Keep budget caps explicit and visible.

Acceptance criteria:

- The first-wave route for province distribution queries includes non-anchor city candidates.
- City/county queries prioritize exact-local sources before parent fallback.
- Multi-sector queries create separate source obligations instead of a single blended search.

### Phase 3: Evidence Sufficiency Gate

Objective:

- Make evaluation and batch diagnostics flag weak evidence even when broad source classes are present.

Tasks:

- Add sufficiency checks for:
  - source level mismatch
  - only one locality when multi-locality is required
  - broad source class present but no claim-level support
  - missing quantitative metric evidence
  - parent evidence used as exact-local evidence
- Expose diagnostics in eval artifacts without changing protected public API shapes.

Acceptance criteria:

- P04-style cases cannot pass merely because they have `official_policy`, `statistics`, `project_list`, and `company_disclosure`; they must show multi-city evidence or an explicit gap.
- C01-style cases distinguish "city class present" from "city-specific evidence sufficient."
- Batch report can separate `coverage_gap` from `sufficiency_gap`.

### Phase 4: Extraction And Adapter Decision Gate

Objective:

- Decide which remaining evidence gaps require profiles, adapters, or extraction improvements.

Tasks:

- Classify failures into:
  - source profile update
  - source registry entry
  - direct structured adapter
  - extraction/binary/PDF/DOC improvement
  - no-code eval/reporting adjustment
- Keep browser automation and OCR out unless a new Architecture Gate authorizes them.

Acceptance criteria:

- Each unresolved gap has an owner category and validation query group.
- No full 50-query live run is authorized from unresolved adapter/extraction blockers.

### Phase 5: 12-Case Quality Gate Rerun

Objective:

- Re-run the 12-case live inspection, DeepSeek audit, and batch report.

Acceptance criteria:

- Live gate: `12 success / 0 runtime error`.
- Audit transport/schema: `12 success`, shape diagnostics `0`.
- Audit blockers: `0`.
- At least `6/12` cases are `weak_pass` or `pass`, or fail count falls to `<=6`.
- `project_list <= 5`.
- `tender_or_procurement <= 5`.
- `local_government <= 3`.
- `statistics <= 3`.
- `environmental_or_land_record <= 2`.
- Sufficiency diagnostics are recorded.
- Estimated Tavily credits are recorded and justified.

### Phase 6: Staged 50-Query Decision

Objective:

- Decide whether to move beyond the 12-case gate.

Acceptance criteria:

- If Phase 5 passes, run staged offline/low-cost expansion before a full 50-query live run.
- If Phase 5 fails, record a narrower successor blocker instead of spending 50-query live budget.

## Continue Rule

After each milestone, continue automatically when:

- acceptance criteria are met
- required validation passes
- no credential, dependency, permission, or human-review blocker exists
- no high-risk contract change is required without PLAN authorization

Do not treat a milestone summary as a default stop point.

## Stop Conditions

Stop and request guidance if:

- a protected contract change is required
- live credentials are unavailable
- a source requires browser automation, OCR, login, paid access, or private data
- validation fails and the safe repair path is unclear
- external API behavior prevents reliable validation
- the user explicitly pauses

## Validation Loop

Minimum focused checks after implementation slices:

```powershell
python -m ruff check <changed files>
python -m py_compile <changed files>
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_retrieval_plan.py tests\test_sources_disclosure_mapping.py
pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py
pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py
```

Live gate after remediation:

```powershell
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\strong_evidence_smoke_cases_v1.json --mode extraction_inspection --max-search-tasks 2 --max-rounds 2 --max-candidates 3 --content-chars 1200 --output-dir data\tmp\source_quality_stress_eval\runs\source_multigranular_evidence_sufficiency_v1_phase5_live_v1 --print-json
python data\tmp\_source_quality_llm_audit.py --run-dir data\tmp\source_quality_stress_eval\runs\source_multigranular_evidence_sufficiency_v1_phase5_live_v1 --provider deepseek --model deepseek-v4-pro --thinking true --reasoning-effort max --timeout 240 --max-output-tokens 8192 --print-summary
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\source_multigranular_evidence_sufficiency_v1_phase5_live_v1 --print-json
```

## Done Condition

This PLAN is done when either:

- the 12-case gate passes Phase 5 acceptance and Phase 6 authorizes staged 50-query expansion, or
- a narrower successor blocker is recorded with clear source-family/evidence-obligation evidence and the full 50-query live run remains deferred.

## Progress

- 2026-04-29: PLAN created from `source-structured-evidence-backbone-v1` Phase 5 result.
  - Reused artifact: `data/tmp/source_quality_stress_eval/runs/source_structured_evidence_backbone_v1_phase5_live_v1`.
  - Key baseline: `12 success`, `0` audit blockers, `5 weak_pass / 7 fail`, source-count thresholds passed, quality threshold failed by one case.
  - Initial focus is multi-granular evidence sufficiency rather than broad source-class coverage.
- 2026-04-29: Phase 0 completed.
  - Created:
    - `data/tmp/source_quality_stress_eval/source_multigranular_evidence_sufficiency_phase0/obligation_matrix.json`
    - `data/tmp/source_quality_stress_eval/source_multigranular_evidence_sufficiency_phase0/obligation_matrix.md`
  - Frozen obligation families:
    - `administrative_granularity`
    - `multi_city_distribution`
    - `multi_sector_decomposition`
    - `quantitative_metric_evidence`
    - `exact_local_depth`
    - `extraction_or_adapter_decision`
  - Phase 1 target:
    - Implement evidence-obligation metadata in query decomposition/retrieval planning.
    - No query-ID-specific branches.
- 2026-04-29: Phase 1 completed.
  - Added internal `evidence_obligations` metadata to query decomposition tasks and retrieval-plan lanes.
  - Obligations now expose:
    - `administrative_granularity:macro|province|city|county`
    - `multi_city_distribution`
    - `multi_sector_decomposition`
    - `quantitative_metric_evidence`
    - `exact_local_depth`
  - RED/GREEN validation:
    - query decomposition phase1 tests first failed because `QueryDecompositionTask` had no `evidence_obligations`, then passed after implementation.
    - retrieval plan phase1 tests first failed because `CoverageLanePlan` had no `evidence_obligations`, then passed after implementation.
  - Validation:
    - `pytest -q tests\test_sources_query_decomposition.py` -> `56 passed`
    - `pytest -q tests\test_sources_retrieval_plan.py` -> `35 passed`
    - focused source suite -> `198 passed, 1 warning`
    - source regression -> `27 passed`
    - domestic regression -> `16 passed`
    - focused ruff -> pass
    - focused py_compile -> pass
- 2026-04-29: Phase 2 completed.
  - Converted obligation metadata into reusable source/lane expansion behavior.
  - Province distribution queries now add non-anchor city domains and phrases.
  - Multi-sector queries now emit sector-specific policy/project/data phrases.
  - Existing special strategies such as real estate macro and Xi'an commercial aerospace remain protected.
  - Validation:
    - `pytest -q tests\test_sources_query_decomposition.py -k "phase2"` -> `3 passed`
    - `pytest -q tests\test_sources_retrieval_plan.py -k "phase2"` -> `2 passed`
    - `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py` -> `95 passed`
    - focused source suite -> `202 passed, 1 warning`
    - source regression -> `27 passed`
    - domestic regression -> `16 passed`
    - focused ruff/py_compile -> pass
  - Practical effect:
    - Anhui NEV province-distribution queries now search Wuhu and Ma'anshan project/data/policy signals instead of only generic Anhui/Hefei signals.
    - Hainan free-trade-port multi-sector queries now split medicine, shipping, and digital-trade project/data phrases rather than using one blended query.
- 2026-04-29: Phase 3 completed.
  - Added batch-report diagnostics that separate broad source-class coverage gaps from evidence sufficiency gaps.
  - New `evidence_sufficiency_gaps` distinguishes missing critical sources, source-level mismatch, weak claim support, and weak regional granularity.
  - Baseline preview on `source_structured_evidence_backbone_v1_phase5_live_v1` produced:
    - `evidence_sufficiency_gaps=56`
    - `source_coverage_gaps=22`
  - Validation:
    - `pytest -q tests\test_source_quality_batch_report.py -k "phase3"` -> `1 passed`
    - `pytest -q tests\test_source_quality_batch_report.py tests\test_source_quality_llm_audit.py tests\test_source_quality_live_inspection.py` -> `9 passed, 1 warning`
    - focused ruff/py_compile -> pass
- 2026-04-29: Phase 4 completed.
  - Created:
    - `data/tmp/source_quality_stress_eval/source_multigranular_evidence_sufficiency_phase4/adapter_decision_matrix.json`
    - `data/tmp/source_quality_stress_eval/source_multigranular_evidence_sufficiency_phase4/adapter_decision_matrix.md`
  - Classified unresolved gaps into:
    - `source_profile_update`
    - `source_registry_or_adapter_candidate`
    - `direct_structured_adapter`
    - `extraction_or_binary_improvement`
    - `no_code_eval_or_reporting`
  - Full 50-query live authorization remains `deferred`.
  - Validation:
    - `phase4_matrix_ok 5 56`
- 2026-04-29: Phase 5 completed and failed quality acceptance.
  - Live artifact:
    - `data/tmp/source_quality_stress_eval/runs/source_multigranular_evidence_sufficiency_v1_phase5_live_v1`
  - Live gate:
    - `12 success / 0 runtime error`
    - `estimated_tavily_credits=76`
    - `average_latency_ms=79597.44`
  - DeepSeek audit:
    - `12 success`
    - `audit_shape_diagnostic_count=0`
    - `verdicts=9 fail / 3 weak_pass`
    - `total_tokens=399861`
  - Failed Phase 5 acceptance:
    - weak/pass target failed: `3/12` vs required `>=6/12`
    - fail-count target failed: `9` vs required `<=6`
    - `tender_or_procurement=7` vs target `<=5`
  - Passed source-count thresholds:
    - `project_list=5` vs target `<=5`
    - `local_government=3` vs target `<=3`
    - `statistics=3` vs target `<=3`
    - `environmental_or_land_record=2` vs target `<=2`
  - Recorded successor blocker:
    - transaction/procurement/project/local-record sufficiency is now the dominant blocker
    - county exact-local and PDF/public-resource extraction remain unresolved
    - full 50-query live run remains deferred
  - Follow-up PLAN:
    - `.agent/PLANS/source-transaction-local-record-adapter-remediation-v1.md`

## Current Phase

Completed with successor blocker after Phase 5. Phase 6 50-query expansion remains deferred.

## Risks And Rollback

Risks:

- Evidence sufficiency scoring can become too strict and reduce useful partial answers.
- Multi-city and multi-sector expansion can increase Tavily credits if budget caps are not explicit.
- Some county-level exact-local evidence may remain unavailable through static public pages.
- DeepSeek audit scores can be noisy; use verdicts and structured gap fields, not raw score alone.
- Dirty worktree remains broad; do not revert unrelated changes.

Rollback:

- Revert only files changed under this PLAN.
- Preserve `source_structured_evidence_backbone_v1_phase5_live_v1` as the comparison run.
- Disable obligation expansion if it causes cost explosion or source drift.

## Next Action

Do not run the full 50-query live evaluation. Use the successor PLAN:

- `.agent/PLANS/source-transaction-local-record-adapter-remediation-v1.md`

The successor should focus on reusable transaction/project/local-record evidence and extraction improvements, not query-specific overfitting.
