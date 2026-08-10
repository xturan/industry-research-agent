# Source Local Evidence Backbone Remediation v1

Status: completed_with_successor_blocker

Created: 2026-04-29

Primary active PLAN: yes

Supersedes active execution of:

- `.agent/PLANS/source-generalized-evidence-remediation-v1.md`

## Objective

Build a generalized local strong-evidence backbone so source-quality remediation improves the reusable retrieval paradigm, not individual query cases.

The immediate trigger is the blocked Phase 5 gate from `source-generalized-evidence-remediation-v1`:

- routing gate: `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`
- live gate: `12 success / 0 runtime error`
- DeepSeek audit: `1 blocker / 8 fail / 3 weak_pass`
- estimated Tavily credits: `78`
- average latency: `34752.02 ms`

This PLAN must improve city/county/province evidence coverage through reusable source backbones:

- local government and department portals
- project lists, public-resource trading, procurement, tender and bid records
- statistics, fiscal, customs, energy and quantitative reports
- environmental impact assessment, land, natural-resource, approval and regulatory records
- extraction reliability for PDF/download/minimal-content pages
- budget-aware multi-lane execution

## Task Classification

- Primary area: `source_layer`
- Secondary areas: `domestic_source_collectors`, `eval_policy_ops`, `provider_layer`
- Later possible impact: `research_workflow` only if existing metadata visibility needs a compatibility-safe bridge

Protected contracts:

- EvidenceBundle schema
- EvidenceItem citation fields
- `source_quality_summary` shape
- research analyze response shape
- provider abstraction semantics
- source routing response shape
- task/job status semantics
- `run` / `run_steps` meaning
- direct-keep primary paths
- legacy `enable_source_acquisition=False` behavior

Any protected-contract change requires an Architecture Gate section update before implementation.

## Inputs And Baseline

Primary blocked-gate artifacts:

- `data/tmp/source_quality_stress_eval/runs/generalized_phase5_routing_v1`
- `data/tmp/source_quality_stress_eval/runs/generalized_phase5_live_v1/live_summary.json`
- `data/tmp/source_quality_stress_eval/runs/generalized_phase5_live_v1/llm_audit_summary.json`
- `data/tmp/source_quality_stress_eval/runs/generalized_phase5_live_v1/batch_eval.json`
- `data/tmp/source_quality_stress_eval/runs/generalized_phase5_live_v1/source_roadmap.json`
- `data/tmp/source_quality_stress_eval/runs/generalized_phase5_live_v1/llm_audit/*.json`

Phase 5 baseline:

| Metric | Result |
|---|---:|
| Live status | `12 success / 0 runtime error` |
| Audit status | `12 success`, audit shape diagnostics `0` |
| Audit verdicts | `1 blocker / 8 fail / 3 weak_pass` |
| Tavily credits | `78` |
| Average latency | `34752.02 ms` |

Main source-class gaps:

| Source class | Missing count | Affected cases |
|---|---:|---|
| `local_government` | `5` | `C01`, `C09`, `K07`, `K09`, `P10` |
| `project_list` | `5` | `C01`, `K07`, `K12`, `M03`, `P08` |
| `statistics` | `4` | `C01`, `K09`, `M03`, `P08` |
| `environmental_or_land_record` | `3` | `C01`, `K07`, `P08` |

## Design Direction

Move from ad hoc lane fallback to a source-backbone model:

```text
Query decomposition
  -> required evidence obligations
  -> local evidence backbone planner
       -> local_government
       -> project_public_resource
       -> statistics_fiscal
       -> environmental_land_record
       -> extraction_reliability
       -> budget_lane_scheduling
  -> source resolver / lane execution
  -> Crawl4AI extraction
  -> evidence quality summary
  -> DeepSeek audit and deterministic batch report
```

The 12-case smoke set and later 50-query set are regression instruments. They must expose weak patterns, not become hard-coded targets.

## Scope

In scope:

- Deterministic backlog/matrix artifacts from Phase 5 output.
- Reusable local source-class patterns and routing improvements.
- Search-assisted local profiles before direct adapters unless a source is stable and repeated.
- Existing metadata-only diagnostics for extraction, quality and budget decisions.
- Focused 12-case live/audit rerun before any full 50-case live expansion.

Out of scope unless explicitly reopened:

- Browser automation.
- OCR.
- Login, paid or private sources.
- Public EvidenceBundle/citation/research response schema changes.
- Query-specific hardcoding that does not generalize to a source class or evidence obligation.

## Agent Execution Contract

Project contract:

- PLAN is the execution contract.
- STATUS is the handoff checkpoint.
- The current session may execute locally. Use subagents only when explicitly authorized by the user/runtime policy.
- If subagents are used later, bind them as:
  - `invest_project_director`: refine validation and phase scope.
  - `invest_feature_programmer`: implement source/eval/script changes in narrow write scopes.
  - `invest_agent_architecture_builder`: review any Architecture Gate or protected-contract risk.
  - `invest_code_quality_checker`: ruff, compile, focused pytest.
  - `invest_functional_validator`: routing/live/audit gate validation.
  - `invest_project_summarizer`: final PLAN completion summary only after done condition.

## Phases

### Phase 0: Local Evidence Backbone Matrix

Objective:

- Convert the blocked Phase 5 run into a deterministic implementation queue grouped by reusable backbone, not by case ID.

Tasks:

- Add a deterministic artifact script that reads `batch_eval.json`, `source_roadmap.json`, `live_summary.json`, and `llm_audit/*.json`.
- Output:
  - backbone matrix JSON
  - backbone matrix Markdown
  - case-to-backbone map
  - next gate thresholds
- Add tests using synthetic artifacts.

Acceptance criteria:

- Matrix contains the six required backbone buckets.
- Matrix records affected cases and source classes.
- Matrix records the `78` credit baseline and marks budget scheduling as active when credits exceed `69`.
- No production source code changes are required in Phase 0.

Validation:

```powershell
python -m ruff check data\tmp\_source_local_evidence_backbone_matrix.py tests\test_source_local_evidence_backbone_matrix.py
python -m py_compile data\tmp\_source_local_evidence_backbone_matrix.py tests\test_source_local_evidence_backbone_matrix.py
pytest -q tests\test_source_local_evidence_backbone_matrix.py
python data\tmp\_source_local_evidence_backbone_matrix.py --run-dir data\tmp\source_quality_stress_eval\runs\generalized_phase5_live_v1 --output-dir data\tmp\source_quality_stress_eval\local_evidence_backbone_phase0 --print-json
```

### Phase 1: Local Backbone Source Pattern Upgrade

Objective:

- Turn the matrix into reusable source profile and resolver behavior.

Tasks:

- Extend source-class patterns for:
  - local government / DRC / MIIT / statistics / finance
  - local public-resource and procurement platforms
  - local natural-resource, land and EIA pages
  - local fiscal subsidy and project-support pages
- Keep patterns source-class driven.
- Add generic tests, not case-ID-only tests.

Acceptance criteria:

- City/county/province tasks get explicit local-source attempts before parent fallback.
- Source class and administrative level are visible in metadata.
- No protected public schema drift.

### Phase 2: Project And Statistics Backbones

Objective:

- Improve project-list and statistics/fiscal evidence sufficiency.

Tasks:

- Improve project/public-resource fallback phrase planning and evidence scoring.
- Improve statistics/fiscal fallback phrase planning and relevance checks.
- Add budget caps per backbone so extra recall does not unboundedly raise Tavily cost.

Acceptance criteria:

- `project_list` missing count remains `<=5` and should improve toward `<=4`.
- `statistics` missing count falls to `<=3`.
- Runtime remains `12 success / 0 runtime error`.

### Phase 3: Environmental/Land/EIA And Extraction Reliability

Objective:

- Reduce false no-evidence from official-record and PDF/download pages.

Tasks:

- Improve source-class patterns for environmental, land, natural-resource and regulatory records.
- Keep classified extraction failures visible.
- Add static link/PDF-download handling only where compatible with current rules; no OCR/browser automation.

Acceptance criteria:

- `environmental_or_land_record` missing count falls to `<=2`.
- PDF/download failures are classified and surfaced as gaps when not recoverable.

### Phase 4: Budget-Aware Lane Scheduling

Objective:

- Keep recall improvements within explicit budget policy.

Tasks:

- Record per-backbone estimated credits.
- Add a gate that flags credit expansion above baseline and explains why.
- Prefer targeted local domains over broad searches before increasing fanout.

Acceptance criteria:

- The 12-case gate records total credits.
- If credits exceed `78`, the PLAN records a justified tradeoff.
- Preferred target is `<=78` credits while improving quality.

### Phase 5: 12-Case Local Backbone Quality Gate

Objective:

- Re-run the 12-case routing/live/DeepSeek audit gate after remediation.

Acceptance criteria:

- Live gate: `12 success / 0 runtime error`.
- Audit transport/schema: `12 success`, shape diagnostics `0`.
- Audit blockers: `0`.
- At least `6/12` cases are `weak_pass` or `pass`, or fail count falls to `<=6`.
- `project_list <= 5`, `statistics <= 3`, `environmental_or_land_record <= 2`.
- Estimated Tavily credits recorded and explained.

### Phase 6: Staged 50-Query Expansion

Objective:

- Expand only after Phase 5 improves.

Tasks:

- Run 50-query routing offline.
- Run staged live subsets by macro/province/city/county.
- Run full live only if cost and latency are acceptable.
- Convert new failures into generalized source-backbone backlog.

Acceptance criteria:

- Full 50-query live is either completed with cost/latency/audit summary or explicitly deferred with evidence.
- New failures are classified by backbone, not patched as isolated cases.

## Continue Rule

After each milestone, continue automatically to the next milestone when:

- acceptance criteria are met
- required validation passes
- no credential, dependency, permission or human-review blocker exists
- no high-risk contract change is being made without explicit PLAN authorization

Stop only at an explicit blocker, explicit user pause, failed validation without a safe fix, or final done condition.

## Stop Conditions

Stop and request guidance if:

- a protected contract change is required
- live credentials are unavailable
- a source requires browser automation, OCR, login or paid access
- validation fails and the repair path is unclear or high risk
- external API behavior prevents safe completion
- the user explicitly pauses

## Done Condition

This PLAN is complete when:

- Phase 5 passes or records a precise successor blocker.
- Phase 6 is completed or explicitly deferred with cost/risk evidence.
- `.agent/STATUS.md` and this PLAN contain final progress, validation, risks and next action.
- Final handoff includes what changed, implemented capability, concrete test cases, two before/after examples, files changed, validation and remaining TODOs.

## Risks And Rollback

Risks:

- Local source sites are unstable and may require profile-specific treatment.
- More recall can raise Tavily credits unless budget caps are explicit.
- DeepSeek audit is strict and sometimes noisy; deterministic matrix should be used alongside audit verdicts.
- PDF/download extraction may remain incomplete without OCR/browser automation.
- Dirty worktree is broad; scope must be reviewed before production implementation.

Rollback:

- Disable new source profiles or local patterns while preserving existing lane execution.
- Revert only files changed by this PLAN.
- Keep `generalized_phase5_live_v1` as the comparison baseline.

## Progress

- 2026-04-29: PLAN created from blocked Phase 5 of `source-generalized-evidence-remediation-v1`. No production source code changed in the planning step.
- 2026-04-29: Phase 0 completed with TDD.
  - RED: `pytest -q tests\test_source_local_evidence_backbone_matrix.py` first failed because `data/tmp/_source_local_evidence_backbone_matrix.py` did not exist.
  - Added `data/tmp/_source_local_evidence_backbone_matrix.py`.
  - Added `tests/test_source_local_evidence_backbone_matrix.py`.
  - Generated artifacts:
    - `data/tmp/source_quality_stress_eval/local_evidence_backbone_phase0/backbone_matrix.json`
    - `data/tmp/source_quality_stress_eval/local_evidence_backbone_phase0/backbone_matrix.md`
  - Phase 0 matrix identified active backbones:
    - `local_government`: `8` cases
    - `project_public_resource`: `6` cases
    - `statistics_fiscal`: `7` cases
    - `environmental_land_record`: `4` cases
    - `extraction_reliability`: `12` cases
    - `budget_lane_scheduling`: `12` cases, `78` credits vs baseline `69`
  - Phase 0 validation passed:
    - `python -m ruff check data\tmp\_source_local_evidence_backbone_matrix.py tests\test_source_local_evidence_backbone_matrix.py` -> pass
    - `python -m py_compile data\tmp\_source_local_evidence_backbone_matrix.py tests\test_source_local_evidence_backbone_matrix.py` -> pass
    - `pytest -q tests\test_source_local_evidence_backbone_matrix.py` -> `1 passed`
    - live artifact generation command completed successfully.
- 2026-04-29: Phase 1 slice 1 completed. Added reusable backbone mapping helpers in `packages/sources/local_source_patterns.py`:
  - `local_evidence_backbone_for_source_class()`
  - `local_source_domains_for_backbones()`
  - Source classes such as `project_list`, `tender_or_procurement`, `statistics`, and `environmental_record` now map to reusable local evidence backbones instead of remaining only raw LLM/eval labels.
  - Tests now use Unicode escape strings for Chinese region names to avoid PowerShell/console mojibake in future edits.
- 2026-04-29: Phase 1 slice 1 validation passed:
  - RED: `pytest -q tests\test_sources_local_source_patterns.py` failed because the new backbone helper functions did not exist.
  - GREEN: `pytest -q tests\test_sources_local_source_patterns.py` -> `6 passed`.
  - Focused ruff/py_compile for the new matrix script, local source patterns, and tests -> pass.
  - Focused source/decomposition/profile validation: `pytest -q tests\test_sources_local_source_patterns.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_domestic_scaleout_phase7.py tests\test_sources_city_county_fallback.py tests\test_source_local_evidence_backbone_matrix.py` -> `95 passed`.
  - Source regression: `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`.
  - Domestic regression: `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`.
  - Repo-wide `python -m ruff check .` still fails on known historical `data/tmp` scratch/demo lint debt, not on files changed in this PLAN slice.
- 2026-04-29: Phase 1 slice 2 completed and Phase 1 acceptance met.
  - RED:
    - `pytest -q tests\test_sources_local_source_patterns.py::test_backbone_domain_union_respects_fiscal_flag tests\test_sources_query_decomposition.py::test_task_family_uses_local_evidence_backbone_domain_selection` first failed because `local_domains_for_task_backbones()` and `local_evidence_backbones_for_task()` did not exist.
  - Implementation:
    - `packages/sources/local_source_patterns.py` now supports `include_fiscal=False` by default for backbone domain union so fiscal pages are not over-included on generic local-government tasks.
    - `packages/sources/query_decomposition.py` now routes `local_rollout`, `project_transaction`, `data_metrics`, and `official_record` domain selection through reusable local evidence backbone helpers.
    - Fiscal/local finance domains are included only when the query contains fiscal/funding/subsidy/investment signals.
  - GREEN and focused validation passed:
    - `pytest -q tests\test_sources_local_source_patterns.py::test_backbone_domain_union_respects_fiscal_flag tests\test_sources_query_decomposition.py::test_task_family_uses_local_evidence_backbone_domain_selection` -> `2 passed`
    - `pytest -q tests\test_sources_local_source_patterns.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_domestic_scaleout_phase7.py tests\test_sources_city_county_fallback.py tests\test_source_local_evidence_backbone_matrix.py` -> `97 passed`
    - `python -m ruff check packages\sources\local_source_patterns.py packages\sources\query_decomposition.py tests\test_sources_local_source_patterns.py tests\test_sources_query_decomposition.py data\tmp\_source_local_evidence_backbone_matrix.py tests\test_source_local_evidence_backbone_matrix.py` -> pass
    - `python -m py_compile packages\sources\local_source_patterns.py packages\sources\query_decomposition.py tests\test_sources_local_source_patterns.py tests\test_sources_query_decomposition.py data\tmp\_source_local_evidence_backbone_matrix.py tests\test_source_local_evidence_backbone_matrix.py` -> pass
    - source regression `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`
    - domestic regression `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`
    - focused profile/lane/router check `pytest -q tests\test_sources_profile_adapter.py tests\test_sources_lane_execution.py tests\test_sources_router_domestic.py` -> `33 passed, 1 warning`
  - Routing/eval artifacts:
    - `data/tmp/source_quality_stress_eval/runs/local_backbone_phase1_routing_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`
    - `data/tmp/source_quality_stress_eval/local_evidence_backbone_phase1/backbone_matrix.json`
    - `data/tmp/source_quality_stress_eval/local_evidence_backbone_phase1/backbone_matrix.md`
  - Repo-wide check:
    - `python -m ruff check .` still fails on known historical `data/tmp` scratch/demo lint debt (`47` errors), not on files changed in this Phase 1 slice.
- 2026-04-29: Phase 2 slice 1 completed.
  - RED:
    - `pytest -q tests\test_sources_query_decomposition.py::test_phase2_project_and_fiscal_backbones_emit_targeted_phrases tests\test_sources_lane_execution.py::test_project_search_fallback_respects_search_credit_budget tests\test_sources_lane_execution.py::test_data_metrics_search_fallback_respects_search_credit_budget` first failed because project/data search phrases were not source-class targeted and `DirectStructuredLaneExecutor` had no project/data search-credit cap parameters.
  - Implementation:
    - `packages/sources/query_decomposition.py` now emits generalized project-list phrases when queries ask for project lists, key projects, start-up, commissioning, land projects, project distribution, or new capacity.
    - `packages/sources/query_decomposition.py` now emits fiscal/statistical phrases when queries ask for fiscal support, subsidies, special funds, funding sources, tax, or fiscal evidence.
    - `packages/sources/lane_execution.py` now exposes `max_project_fallback_search_credits` and `max_data_metrics_fallback_search_credits` with budget metadata and `search_credit_budget_exhausted` stop/status handling.
  - Validation passed:
    - RED/GREEN focused tests -> `3 passed`
    - `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_lane_execution.py tests\test_sources_retrieval_plan.py` -> `107 passed, 1 warning`
    - `python -m ruff check packages\sources\query_decomposition.py packages\sources\lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_lane_execution.py` -> pass
    - `python -m py_compile packages\sources\query_decomposition.py packages\sources\lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_lane_execution.py` -> pass
    - routing eval `data/tmp/source_quality_stress_eval/runs/local_backbone_phase2_routing_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`
    - source regression `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`
    - domestic regression `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`
    - focused profile/lane/router check `pytest -q tests\test_sources_profile_adapter.py tests\test_sources_lane_execution.py tests\test_sources_router_domestic.py` -> `35 passed, 1 warning`
  - Repo-wide check:
    - `python -m ruff check .` still fails on known historical `data/tmp` scratch/demo lint debt (`47` errors), not on files changed in this Phase 2 slice.
- 2026-04-29: Phase 2 low-cost live subset completed for project/statistics backbones.
  - Added subset case file:
    - `data/tmp/source_quality_stress_eval/local_backbone_phase2_live_subset_cases.json`
  - Project live subset:
    - Command: `python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\local_backbone_phase2_live_subset_cases.json --mode extraction_inspection --task-family project_transaction --max-search-tasks 1 --max-rounds 1 --max-candidates 1 --content-chars 800 --output-dir data\tmp\source_quality_stress_eval\runs\local_backbone_phase2_project_live_subset_v1 --print-json`
    - Result: `2 success`, estimated Tavily credits `4`, average latency `7210.45 ms`, query invalid count `0`.
    - Evidence result: `C01` and `K09` both executed without accepted project evidence.
    - Diagnostic: `C01` rejected a potentially relevant `安徽长丰` project candidate as `project_region_mismatch`; this is a generalized administrative hierarchy problem, not a one-query fix.
  - Data metrics live subset:
    - Command: `python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\local_backbone_phase2_live_subset_cases.json --mode extraction_inspection --task-family data_metrics --max-search-tasks 1 --max-rounds 1 --max-candidates 1 --content-chars 800 --output-dir data\tmp\source_quality_stress_eval\runs\local_backbone_phase2_data_live_subset_v1 --print-json`
    - Result: `2 success`, estimated Tavily credits `3`, average latency `5724.73 ms`, query invalid count `0`.
    - Evidence result: `C01` found one usable statistics document; `K09` exhausted the two-credit search budget with parent/nearby-region statistics candidates rejected.
  - Phase 2 finding:
    - Budget caps are working and visible.
    - Next improvement should be generalized administrative hierarchy semantics for child-county and parent-evidence handling. Do not add isolated `C01` or `K09` hardcoding.
- 2026-04-29: Phase 2 admin-hierarchy slice completed at the deterministic/code level.
  - RED:
    - `pytest -q tests\test_sources_local_source_patterns.py::test_local_region_match_distinguishes_child_parent_and_unrelated_evidence tests\test_sources_lane_execution.py::test_project_search_fallback_accepts_child_local_project_candidate tests\test_sources_lane_execution.py::test_data_metrics_search_fallback_marks_parent_local_statistics_candidate` first failed because `classify_local_region_match()` did not exist.
  - Implementation:
    - `packages/sources/local_source_patterns.py` now exposes `classify_local_region_match()` with `exact_local`, `child_local`, `parent_local`, `unrelated_region`, and `unknown` classifications.
    - `packages/sources/lane_execution.py` now records `local_region_match_type` and related metadata on project/data fallback candidate decisions and extracted evidence quality.
    - Evidence-quality region matching no longer treats `discovery_query` as source-region evidence, preventing query echo from making parent evidence look exact-local.
  - Validation passed:
    - RED/GREEN focused tests -> `3 passed`
    - `pytest -q tests\test_sources_local_source_patterns.py tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py` -> `117 passed, 1 warning`
    - `python -m ruff check packages\sources\local_source_patterns.py packages\sources\lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_lane_execution.py` -> pass
    - `python -m py_compile packages\sources\local_source_patterns.py packages\sources\lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_lane_execution.py` -> pass
    - source regression -> `27 passed`
    - domestic regression -> `16 passed`
    - focused profile/lane/router check -> `37 passed, 1 warning`
    - offline routing artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase2_admin_hierarchy_routing_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`
  - Live validation attempted but blocked by external provider behavior:
    - project live artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase2_project_live_subset_v2`
    - data live artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase2_data_live_subset_v2`
    - both runs completed script transport, but each Tavily request returned `Tavily HTTP error 432`; no candidate decisions were available to judge live recall.
  - Phase 2 status:
    - deterministic behavior and local gates are complete for this slice.
    - Phase 2 live acceptance is blocked until Tavily HTTP 432 is resolved or a provider-free replay fixture is adopted.
- 2026-04-29: Phase 2 provider blocker remediation completed.
  - Cause:
    - The previous live v2 subset was blocked by Tavily HTTP `432`, consistent with exhausted provider quota on the active key.
  - Implementation:
    - Added `TAVILY_API_KEYS` support in settings.
    - `TavilySearchAdapter` now resolves the primary key plus the key list, deduplicates them, rotates attempts, and falls back to the next key on provider key/quota/status failures (`401`, `403`, `429`, `432`).
    - Runtime metadata records only attempt counts and does not expose raw credentials.
    - `.env` now holds the gitignored local credential values; raw credentials were not written to PLAN, STATUS, scripts, or run artifacts.
    - `.env` was normalized to UTF-8 without BOM after discovering the BOM hid the first env var from Pydantic.
  - Validation:
    - `pytest -q tests\test_sources_search_discovery.py` -> `10 passed`
    - `pytest -q tests\test_sources_search_discovery.py tests\test_sources_lane_execution.py` -> `41 passed, 1 warning`
    - `python -m ruff check packages\core\config.py packages\sources\search_discovery.py tests\test_sources_search_discovery.py` -> pass
    - `python -m py_compile packages\core\config.py packages\sources\search_discovery.py tests\test_sources_search_discovery.py` -> pass
    - Credential marker scan found raw key markers only in `.env`.
  - Live rerun after adding the second key:
    - Project subset artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase2_project_live_subset_v3`
      - `2` cases, `2 success`, estimated Tavily credits `4`, average latency `7720.96 ms`, `query_invalid_count=0`
      - `C01` accepted a `child_local` project candidate; `K09` still had no accepted project candidate under the two-credit cap.
    - Data subset artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase2_data_live_subset_v3`
      - `2` cases, `2 success`, estimated Tavily credits `2`, average latency `6204.24 ms`, `query_invalid_count=0`
      - `C01` and `K09` both accepted exact-local data/statistics fallback candidates.
  - Phase 2 decision:
    - The Tavily `432` live blocker is resolved.
    - Phase 2 local implementation and low-cost live gate are sufficient to proceed to Phase 3.
    - Cross-case missing-count targets remain to be verified by the Phase 5 12-case quality gate, not by this two-case blocker-remediation subset.
- 2026-04-29: Phase 3 slice 1 completed.
  - RED:
    - `pytest -q tests\test_sources_query_decomposition.py::test_county_park_cluster_query_keeps_direct_lanes_when_records_requested tests\test_sources_query_decomposition.py::test_hefei_city_industrial_cluster_preserves_local_rollout_with_direct_keep` first failed because official-record phrases used short region names (`肥西`, `合肥`) instead of formal local-government names (`肥西县`, `合肥市`).
    - `pytest -q tests\test_sources_lane_execution.py::test_official_record_document_filter_rejects_unrelated_subprovincial_gov_domain` first failed because an off-domain official-record document could pass evidence filtering when title/snippet/raw text contained target-region terms.
  - Implementation:
    - `packages/sources/query_decomposition.py` now uses formal administrative names for generic `official_record` search phrases when known, without changing existing dedicated templates for `神木`, `若羌`, or `内蒙古`.
    - `packages/sources/lane_execution.py` now rejects official-record extracted documents whose final domain is outside the task allowlist unless they are region-matched `.gov.cn` records and do not explicitly declare an unrelated local government in title or metadata hints.
    - This specifically prevents a page such as another county government's "他山之石" article from being accepted as local environmental/land evidence merely because it mentions the target city.
  - Validation:
    - RED/GREEN focused tests -> pass.
    - `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py` -> `88 passed, 1 warning`
    - `pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_domestic_scaleout_phase7.py tests\test_sources_city_county_fallback.py` -> `44 passed`
    - `python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\strong_evidence_smoke_cases_v1 --output-dir data\tmp\source_quality_stress_eval\runs\local_backbone_phase3_routing_formal_region_terms_v1 --print-json` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`
    - Source regression -> `27 passed`
    - Domestic regression -> `16 passed`
    - Focused ruff/py_compile for changed Phase 3 files -> pass
    - Repo-wide `python -m ruff check .` still fails on known historical `data/tmp` scratch/demo lint debt (`47` errors), not on Phase 3 touched files.
  - Live check:
    - Created case file `data/tmp/source_quality_stress_eval/local_backbone_phase3_official_record_c01_case.json`.
    - C01 replay artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase3_official_record_c01_replay_v3` -> `1 success`, estimated Tavily credits `3`, average latency `7812.32 ms`, `query_invalid_count=0`.
    - Before this slice, the replay accepted a non-target `jiaxiang.gov.cn` page as C01 official-record evidence.
    - After this slice, the same fetched page is rejected as `official_record_domain_mismatch`, producing `executed_without_evidence` instead of false positive evidence.
  - Phase 3 status:
    - Slice 1 improves precision and failure transparency for environmental/land/EIA records.
    - C01 still lacks usable local official-record evidence; this is now represented as a transparent evidence gap rather than a false positive.
    - Continue Phase 3 with generalized source-pattern / extraction reliability improvements before the Phase 5 quality gate.
- 2026-04-29: Phase 3 slice 2 completed. Added static PDF fallback for official-record direct lanes.
  - RED:
    - `pytest -q tests\test_sources_lane_execution.py::test_official_record_pdf_candidate_uses_static_pdf_extraction` first failed because `DirectStructuredLaneExecutor` had no official-record PDF service injection and PDF candidates were rejected before extraction.
    - `pytest -q tests\test_sources_lane_execution.py::test_official_record_pdf_failure_is_reported_as_evidence_gap` first failed because unrecoverable PDF download failures were treated as `failed_runtime_error` instead of transparent evidence gaps.
  - Implementation:
    - `packages/sources/lane_execution.py` now supports `official_record_pdf_download_service`, `official_record_pdf_text_service`, `enable_official_record_pdf_fallback`, and `max_official_record_pdf_pages`.
    - Official-record PDF candidates are accepted as `accepted_official_record_pdf_fallback` and extracted through existing `LivePdfDownloadService` + `PdfTextExtractionService` + `normalize_pdf_text_to_documents`.
    - PDF/download failures are surfaced under `pdf_extraction.failure_classes` and `ToolError.detail.extraction_failure_class=pdf_or_download`.
    - Non-recoverable PDF/download-only failures now return `executed_without_evidence` + `partial`, preserving failure transparency without turning missing PDF evidence into a system runtime failure.
  - Validation:
    - PDF RED/GREEN focused tests -> `2 passed`.
    - `pytest -q tests\test_sources_lane_execution.py` -> `36 passed, 1 warning`.
    - `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_pdf_step43.py tests\test_sources_crawl4ai_extraction.py` -> `105 passed, 1 warning`.
    - Source regression -> `27 passed`.
    - Domestic regression -> `16 passed`.
    - Focused ruff/py_compile for changed Phase 3 files -> pass.
    - Routing artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase3_pdf_static_routing_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
  - Live check:
    - Official-record subset artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase3_official_record_pdf_static_live_v1` -> `5 success`, estimated Tavily credits `9`, average latency `11169.7 ms`, `query_invalid_count=0`.
    - Evidence result in the official-record subset: `3` evidence_found, `2` without evidence.
    - `K09` now succeeds through static PDF extraction (`pdf_extraction.succeeded=1`), whereas the prior cap2 baseline skipped PDF candidates as `official_record_pdf_requires_adapter`.
  - Phase 3 decision:
    - `environmental_or_land_record` official-record subset is now at `2` remaining no-evidence cases (`C01`, `K07`), meeting the Phase 3 target direction of `<=2`.
    - Phase 3 acceptance is met for the current PLAN scope.
- 2026-04-29: Phase 4 completed. Added budget-aware lane scheduling diagnostics.
  - RED:
    - `pytest -q tests\test_source_quality_budget_diagnostics.py` first failed because `data/tmp/_source_quality_budget_diagnostics.py` did not exist.
    - A second RED caught an over-broad diagnostic rule that incorrectly treated national policy lanes under local cases as local-domain fanout failures.
  - Implementation:
    - Added `data/tmp/_source_quality_budget_diagnostics.py`.
    - Added `tests/test_source_quality_budget_diagnostics.py`.
    - The diagnostics script reads `live_summary.json` plus `per_query/*.json`, records total estimated Tavily credits, compares them to a configurable baseline, aggregates credits by task family, and flags local lanes that spend search credits on broad/national domains before targeted local domains.
    - The script writes `budget_diagnostics.json` and `budget_diagnostics.md` artifacts.
  - Validation:
    - `pytest -q tests\test_source_quality_budget_diagnostics.py` -> `1 passed`.
    - `python -m ruff check data\tmp\_source_quality_budget_diagnostics.py tests\test_source_quality_budget_diagnostics.py` -> pass.
    - `python -m py_compile data\tmp\_source_quality_budget_diagnostics.py tests\test_source_quality_budget_diagnostics.py` -> pass.
    - `pytest -q tests\test_source_quality_budget_diagnostics.py tests\test_source_local_evidence_backbone_matrix.py tests\test_source_quality_live_inspection.py` -> `3 passed, 1 warning`.
    - Source regression -> `27 passed`.
    - Domestic regression -> `16 passed`.
    - Repo-wide `python -m ruff check .` still fails on known historical `data/tmp` scratch/demo lint debt (`47` errors), not on files touched in Phase 4.
  - Budget artifacts:
    - `data/tmp/source_quality_stress_eval/runs/local_backbone_phase4_budget_pdf_static_v1` -> official-record subset `9` credits, within `78` baseline, no budget flags.
    - `data/tmp/source_quality_stress_eval/runs/local_backbone_phase4_budget_baseline_v1` -> 12-case baseline `78` credits, within `78` baseline, one targeted-domain recommendation for the municipal `industry_topic` empty-domain fanout.
  - Phase 4 decision:
    - Phase 4 acceptance is met: total credits are recorded, `>78` expansion is explicitly gateable, and targeted-local-domain preference is visible before future fanout increases.
- 2026-04-29: Phase 5 completed with successor blocker. The 12-case runtime/budget gate passed, but the quality gate failed.
  - Routing gate:
    - Artifact: `data/tmp/source_quality_stress_eval/runs/local_backbone_phase5_routing_v1`
    - Result: `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
  - Live gate:
    - Artifact: `data/tmp/source_quality_stress_eval/runs/local_backbone_phase5_live_v1`
    - Result: `12 success / 0 runtime error`, average latency `36040.35 ms`, estimated Tavily credits `78`, query invalid count `0`.
  - DeepSeek audit:
    - `12 success`, audit shape diagnostics `0`.
    - Verdicts: `1 blocker / 11 fail / 0 weak_pass / 0 pass`.
    - Total tokens: `288722`.
  - Batch report:
    - `local_government=5` missing: `C01`, `C09`, `K07`, `K09`, `K12`.
    - `project_list=5` missing: `C01`, `K07`, `K12`, `M03`, `P08`.
    - `statistics=4` missing: `K07`, `K09`, `K12`, `M02`.
    - `environmental_or_land_record=2` missing: `C01`, `K07`.
    - Audit blocker: `C07`, because photovoltaic supply-chain risk lacks industry association and market-price evidence.
  - Budget diagnostics:
    - Artifact: `data/tmp/source_quality_stress_eval/runs/local_backbone_phase5_budget_v1`
    - Result: `78` credits, exactly at baseline; no budget expansion flag.
    - Remaining targeted-domain recommendation: `C07` municipal `industry_topic` used empty domains.
  - Backbone matrix:
    - Artifact: `data/tmp/source_quality_stress_eval/local_evidence_backbone_phase5`
    - Remaining active backbones: local government, project/public-resource, statistics/fiscal, environmental/land, extraction reliability.
    - Budget lane is no longer active because credit delta is `0`.
  - Phase 5 decision:
    - Runtime, schema, and budget are stable.
    - Quality acceptance failed: blockers are not `0`, weak/pass count is below `6/12`, and `statistics=4` exceeds the `<=3` target.
    - Phase 6 full 50-query expansion is explicitly deferred. Running 50 live cases now would spend budget on a known insufficient evidence model.
    - Precise successor blocker: the next PLAN must improve reusable evidence sufficiency and source-class coverage, especially local-government/statistics, project/public-resource, and industry/market specialist lanes.
    - Successor PLAN: `.agent/PLANS/source-evidence-sufficiency-remediation-v2.md`.

## Current Phase

Completed with successor blocker.

## Next Action

Adopt `.agent/PLANS/source-evidence-sufficiency-remediation-v2.md` as the next active PLAN. Do not run the full 50-query live evaluation until a successor 12-case quality gate improves materially.
