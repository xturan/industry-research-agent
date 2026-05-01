# Source Transaction File Local Depth v1

Status: completed_with_successor_blocker

Created: 2026-04-30

Primary active PLAN: no

Supersedes:

- `.agent/PLANS/archive/source-local-quant-file-backbone-v1.md`

## Objective

Build the next reusable source backbone after `source-local-quant-file-backbone-v1`.

The prior PLAN stabilized runtime and made file/download failures visible, but the Phase 5 audit did not pass quality:

- live execution: `12 success / 0 runtime error`;
- DeepSeek audit: `1 blocker / 8 fail / 3 weak_pass`;
- `statistics=3` met the target `<=3`;
- `tender_or_procurement=7` regressed versus the previous baseline `4`;
- file/download candidates no longer leak into Crawl4AI as `Download is starting`, but they now expose a real adapter gap.

This PLAN should stop query-by-query remediation and build reusable source-family capabilities for:

- public-resource / government-procurement / project-list file-backed evidence;
- exact-local city/county/flag strong evidence depth;
- macro-to-local evidence obligation fanout;
- controlled industry/association/report supplement evidence.

## Task Classification

- Primary area: `source_layer`
- Secondary areas: `domestic_source_collectors`, `provider_layer`, `eval_policy_ops`
- Execution default: `light_subagent` for scoped implementation; `local_direct` for docs/status/artifacts.
- Escalate to `full_subagent` only if a phase requires protected-contract, provider-abstraction, or public response-shape changes.

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

No protected-contract change is authorized by default.

## Baseline

Input run:

- `data/tmp/source_quality_stress_eval/runs/source_local_quant_file_backbone_v1_phase5_live_v1`

Baseline snapshot:

- Live: `12 success`, `70` estimated Tavily credits, `55287.68 ms` average latency
- DeepSeek: `12 success`, `0` shape diagnostics, `361117` tokens
- Audit verdicts: `1 blocker / 8 fail / 3 weak_pass`
- Main gaps:
  - `tender_or_procurement=7`
  - `project_list=4`
  - `industry_association=4`
  - `industry_report=4`
  - `local_government=3`
  - `statistics=3`
  - `regulatory_record=2`
  - `environmental_or_land_record=1`
- File/download gates:
  - `project_file_requires_adapter`: `5` cases
  - `data_metrics_file_requires_adapter`: `3` cases
  - `file_candidates_require_adapter`: `4` cases
  - no `Download is starting` marker in task artifacts

## Scope

In scope:

- Official file/download resolver for PDF/XLS/DOC/CSV/ZIP/download endpoints.
- Text/metadata extraction path for file-backed government evidence where safe.
- Structured failure metadata for unsupported, too-large, wrong-type, zero-text, or inaccessible files.
- Public-resource, government-procurement, project-list, filing, approval, and key-project source-family profiles.
- Exact-local city/county/flag strong-evidence source profiles and parent-fallback claim guard.
- Macro query decomposition/fanout rules when the query requires policy-to-project or policy-to-demand verification.
- Low-cost subset validation and one 12-case smoke rerun.

Out of scope unless reopened:

- Full 50-query live run.
- Browser automation as default.
- OCR.
- Login-gated or paid databases.
- Direct securities investment advice.
- Public API response-shape changes.
- Query-ID-specific hardcoding.

## Design Direction

The new backbone should make file-backed and exact-local evidence first-class, but still auditable:

```text
query obligation
  -> source-family requirement
  -> official source profile / domain pattern
  -> search or direct discovery
  -> file/download decision
  -> safe extractor or structured failure
  -> evidence quality classification
  -> claim eligibility and coverage gap
```

Hard rule:

```text
Do not count a file/download candidate as strong evidence unless extracted text or verifiable metadata supports the claim.
Do not let parent-level evidence support exact-local claims unless `local_claim_allowed=true`.
```

## Phase 0: Blocker Matrix Freeze

Status: completed

Execution mode: `local_direct`

Artifacts:

- `data/tmp/source_quality_stress_eval/source_transaction_file_local_depth_phase0/blocker_matrix.json`
- `data/tmp/source_quality_stress_eval/source_transaction_file_local_depth_phase0/blocker_matrix.md`

Frozen blocker families:

- `transaction_procurement_file_adapter`
- `exact_local_strong_evidence_depth`
- `macro_to_local_obligation_fanout`
- `sector_supplement_controlled_use`

Acceptance criteria:

- Matrix records source-family blockers rather than query-specific fixes.
- No full 50-query live run is triggered.
- No production code change is made in Phase 0.

## Phase 1: File/Download Adapter Architecture Gate

Status: completed

Execution mode: `light_subagent`, escalate to `full_subagent` if provider/public-contract changes become necessary.

Objective:

- Define the internal adapter contract for official file/download evidence without changing public EvidenceBundle or response shapes.

Tasks:

- Inventory existing PDF/file utilities and source extraction helpers.
- Define internal file candidate fields:
  - `file_candidate_kind`
  - `content_type`
  - `content_length`
  - `final_url`
  - `download_status`
  - `extractor`
  - `text_chars`
  - `extraction_failure_class`
  - `extraction_failure_stage`
- Define limits:
  - max file size;
  - supported extensions;
  - timeout;
  - no OCR;
  - no browser automation by default.
- Add RED tests for:
  - official PDF project document should not be treated as plain webpage;
  - unsupported ZIP/download endpoint produces structured failure;
  - wrong-region file remains rejected before extraction;
  - extracted file evidence must retain original source/citation URL.

Acceptance criteria:

- Contract is internal and backward compatible.
- Tests define behavior before implementation.
- No public schema changes are required.

## Phase 2: Official File Extractor Slice

Status: completed

Execution mode: `light_subagent`

Objective:

- Implement the smallest safe file extraction path for official PDF/XLS-like evidence candidates.

Tasks:

- Add or reuse HTTP download helper with content-type and size guard.
- Add PDF text extraction when existing dependencies support it.
- Add XLS/XLSX metadata/table text extraction if existing dependencies support it; otherwise return structured unsupported failure.
- Attach extraction metadata into existing lane metadata without changing public contracts.
- Preserve `project_file_requires_adapter` and `data_metrics_file_requires_adapter` as fallback states when unsupported.

Acceptance criteria:

- Official PDF candidates can produce text or structured failure.
- Unsupported files never count as strong evidence.
- Crawl4AI is not invoked for file/download candidates.

## Phase 3: Transaction / Procurement / Project Source Backbone

Status: completed

Execution mode: `light_subagent`

Objective:

- Improve `tender_or_procurement` and `project_list` through reusable source profiles and file-aware candidate handling.

Tasks:

- Add source-family patterns for:
  - national/provincial/city public-resource trading;
  - government procurement;
  - DRC project approval / filing / key-project pages;
  - local project construction / start / completion lists.
- Prefer detail, notice, award, tender, transaction-result, and project pages over portal/search/list pages.
- Keep direct-structured primary lanes protected; search remains discovery/supplement unless a direct adapter exists.
- Add anti-overfit tests across at least two regions and two administrative levels.

Acceptance criteria:

- `tender_or_procurement` gap improves on targeted subset without raising false positives.
- Portal/list/download-only pages become either extracted evidence or structured gaps.

## Phase 4: Exact-Local Strong Evidence Depth

Status: completed

Execution mode: `light_subagent`

Objective:

- Improve local claim eligibility for city/county/flag queries without enumerating every locality.

Tasks:

- Extend local source patterns for government, DRC, industry/MIIT, statistics, fiscal, ecology, natural resources, public resources, and procurement.
- Preserve exact-local -> parent -> national ordering.
- Add claim guards so parent evidence cannot support exact-local conclusions unless explicitly allowed.
- Add tests using at least one city, one county, and one flag/county-level banner.

Acceptance criteria:

- Exact-local official evidence has priority.
- Parent fallback is transparent and claim-limited.

## Phase 5: Macro-To-Local Obligation Fanout

Status: completed

Execution mode: `light_subagent`

Objective:

- For macro queries asking whether policy became real demand/project/order, add required local/project/statistical lanes instead of relying on central policy evidence.

Tasks:

- Detect policy-to-project, policy-to-demand, energy/cost constraint, and implementation-validation intents.
- Add bounded provincial/local fanout lanes with explicit cost caps.
- Preserve direct-keep boundaries for disclosure/project/data lanes.
- Add tests for macro queries such as data centers, low-altitude economy, real estate demand, and energy constraints.

Acceptance criteria:

- Macro questions do not pass coverage with central policy evidence alone when local/project/statistical verification is required.
- Search fanout remains budget-capped and trace-visible.

## Phase 6: Low-Cost Targeted Gate

Status: completed

Execution mode: `light_subagent`

Subset candidates:

- `P08`: Inner Mongolia energy/statistics/project/procurement
- `C07`: Changzhou project/procurement PDF candidates
- `K07`: Feixi county project/land/environment/local depth
- `M02`: data-center policy-to-project/energy fanout
- `M03`: low-altitude economy local/regulatory/statistics fanout
- `C01`: Hefei local project/procurement/land

Acceptance criteria:

- Runtime succeeds for all selected cases.
- `tender_or_procurement` and `project_list` gaps improve, or a narrower file/provider blocker is recorded.
- File/download behavior is either extracted or structured; no `Download is starting` appears.

## Phase 7: 12-Case Smoke Rerun

Status: completed_with_successor_blocker

Execution mode: `light_subagent`

Acceptance criteria:

- Live: `12 success / 0 runtime error`.
- DeepSeek audit: `12 success`, shape diagnostics `0`.
- `tender_or_procurement <= 5`.
- `project_list <= 4`.
- `statistics <= 3`.
- Weak/pass count improves from current `3/12`, or a narrower out-of-scope blocker is recorded.
- Full 50-query live remains deferred unless Phase 8 approves it.

## Phase 8: 50-Query Readiness Decision

Status: completed_not_ready

Execution mode: `planning_only` or `local_direct`

Acceptance criteria:

- Record whether staged 50-query evaluation is cost-effective.
- If ready, define a budget cap and split execution into batches.
- If not ready, record the remaining source-family blocker.

## Continue Rule

Continue automatically to the next phase when:

- acceptance criteria pass;
- required validation passes;
- no protected-contract change is needed;
- no browser automation, OCR, login-gated source, or paid/private data is required;
- cost and latency remain visible;
- the next phase has a safe execution mode.

Stop when:

- a protected-contract change is required;
- a provider/config architecture change is required;
- validation fails and safe remediation is unclear;
- remediation would become query-specific hardcoding;
- the next step is full 50-query live without Phase 8 readiness;
- the user explicitly pauses.

## Validation Loop

Focused local checks:

```powershell
python -m ruff check <changed files>
python -m py_compile <changed files>
pytest -q tests\test_sources_lane_execution.py -k "file or project_search_fallback or data_metrics"
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_source_resolver.py tests\test_sources_local_source_patterns.py tests\test_sources_lane_execution.py
```

Regression checks:

```powershell
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_retrieval_plan.py tests\test_sources_disclosure_mapping.py
pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py
pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py
```

Live/eval checks:

```powershell
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\strong_evidence_smoke_cases_v1.json --mode extraction_inspection --max-search-tasks 3 --max-rounds 1 --max-candidates 2 --max-official-record-search-credits 2 --content-chars 800 --print-json
python data\tmp\_source_quality_llm_audit.py --run-dir <run_dir> --provider deepseek --model deepseek-v4-pro --thinking --reasoning-effort max --resume
python data\tmp\_source_quality_batch_report.py --run-dir <run_dir> --print-json
```

## Cost Controls

- Do not run full 50-query live during this PLAN unless Phase 8 explicitly approves it.
- Use targeted subset gates before the 12-case smoke.
- Keep Tavily `basic` / low-cost search defaults unless a phase records a bounded exception.
- Use DeepSeek audit only after live artifacts complete.
- Use local `.env` key pool only through process environment loading; never write raw keys to tracked files or artifacts.

## Done Condition

This PLAN is done when one of these is true:

- transaction/procurement/project/file-backed evidence passes the 12-case smoke gate and Phase 8 records staged 50-query readiness; or
- the 12-case gate identifies a narrower blocker requiring provider/file-parser/browser/OCR Architecture Gate; or
- implementation reaches an out-of-scope requirement such as OCR, browser automation, login-gated source, paid data, or protected-contract change.

## Progress

- 2026-04-30: PLAN created after `source-local-quant-file-backbone-v1` Phase 5 exposed a narrower successor blocker.
- 2026-04-30: Phase 0 completed with blocker matrix artifacts:
  - `data/tmp/source_quality_stress_eval/source_transaction_file_local_depth_phase0/blocker_matrix.json`
  - `data/tmp/source_quality_stress_eval/source_transaction_file_local_depth_phase0/blocker_matrix.md`
- 2026-04-30: Phase 1 completed with an internal file evidence contract:
  - Added `packages/sources/file_evidence.py`.
  - Added `tests/test_sources_file_evidence.py`.
  - File candidate classification now has a reusable internal contract for `pdf`, `xls`, `xlsx`, `doc`, `docx`, `csv`, `zip`, and `download_endpoint`.
  - PDF candidates are classified as `static_pdf` candidates but remain non-claim-eligible until extracted.
  - Unsupported ZIP/download-style candidates return structured failure metadata with `claim_eligible=false`.
  - `packages/sources/lane_execution.py` now reuses `file_candidate_kind_from_url()` instead of maintaining a separate file-kind parser.
  - Validation:
    - RED: `pytest -q tests\test_sources_file_evidence.py` failed before implementation with missing `packages.sources.file_evidence`.
    - GREEN: `pytest -q tests\test_sources_file_evidence.py` -> `3 passed`.
    - Focused file/lane tests -> `39 passed`.
    - Focused source suite -> `223 passed`.
    - Source regression -> `27 passed`.
    - Domestic source regression -> `16 passed`.
- 2026-04-30: Phase 2 completed with a minimal official PDF extraction slice:
  - `project_transaction` PDF candidates now use static PDF extraction instead of being rejected as `project_file_requires_adapter`.
  - `data_metrics` PDF candidates now use static PDF extraction instead of being rejected as `data_metrics_file_requires_adapter`.
  - Non-PDF files such as XLS/XLSX/DOC/ZIP/download endpoints still return structured unsupported metadata and are not counted as strong evidence.
  - Project PDF evidence is tagged with `source_class=tender_or_procurement` and `project_pdf_fallback=true`.
  - Data-metrics PDF evidence is tagged with `source_class=statistics` and `data_metrics_pdf_fallback=true`.
  - Crawl4AI is not invoked for PDF candidates.
  - Validation:
    - RED: `pytest -q tests\test_sources_lane_execution.py -k "pdf_candidate_uses_static_pdf_extraction"` failed before implementation for project/data PDF candidates.
    - GREEN: same targeted test -> `3 passed`.
    - `python -m ruff check packages\sources\file_evidence.py packages\sources\lane_execution.py tests\test_sources_file_evidence.py tests\test_sources_lane_execution.py` -> pass.
    - `python -m py_compile packages\sources\file_evidence.py packages\sources\lane_execution.py tests\test_sources_file_evidence.py tests\test_sources_lane_execution.py` -> pass.
    - Focused file/lane tests -> `39 passed`.
    - Focused source suite -> `228 passed`.
    - Source regression -> `27 passed`.
    - Domestic source regression -> `16 passed`.
- 2026-04-30: Phase 3 completed with transaction/procurement/project backbone hardening:
  - Project fallback now prioritizes stronger public-resource / procurement / approval candidates inside a search response before consuming the candidate budget.
  - Project PDF-backed evidence now exposes `pdf_backed_evidence` and `extraction_pdf_quality_gate`.
  - Generic policy/news pages are no longer promoted to `tender_or_procurement` only because正文 contains 招标/采购/中标 terms; promotion now requires a public-resource/procurement domain or procurement-like source id.
  - Low-cost live project subset v2:
    - Run dir: `data/tmp/source_quality_stress_eval/runs/source_transaction_file_local_depth_v1_phase3_project_subset_v2`
    - Cases: `M02`, `P08`, `C09`
    - Result: `3 success / 0 runtime error`
    - Estimated Tavily credits: `4`
    - Average latency: `6282.69 ms`
    - No `Download is starting` marker found.
    - `C09` public-resource records retain `tender_or_procurement` and `public_resource_procurement`.
    - `M02`/`P08` NDRC news/activity pages are downgraded to `project_list` instead of false `tender_or_procurement`.
  - Remaining blocker carried forward: P08 public-resource download endpoints still require a non-PDF file/download adapter before they can become strong evidence.
  - Validation:
    - RED: new project fallback tests failed for missing PDF quality family, weak candidate ordering, and false procurement promotion.
    - GREEN: targeted project fallback tests -> `17 passed`.
    - `python -m ruff check packages\sources\lane_execution.py tests\test_sources_lane_execution.py` -> pass.
    - `python -m py_compile packages\sources\lane_execution.py tests\test_sources_lane_execution.py` -> pass.
    - Focused source suite -> `230 passed`.
    - Source regression -> `27 passed`.
    - Domestic source regression -> `16 passed`.
- 2026-04-30: Phase 4 completed with exact-local ordering and parent-claim guard hardening:
  - Local rollout repair no longer sorts exact-local domains behind parent/fiscal domains.
  - Known exact-local city/county entities such as `神木` and `若羌` now keep the exact local domain first in `local_rollout`.
  - Generic flag/county-level evidence on a province-level domain is classified as `parent_local`, not `exact_local`, so it becomes `parent_evidence_only=true` and `local_claim_allowed=false`.
  - Added anti-overfit tests using one county-level city (`神木`), one county (`若羌`), and one flag/county-level banner (`准格尔旗`).
  - Validation:
    - RED: three Phase 4 tests failed for local-domain ordering and generic flag parent evidence.
    - GREEN: targeted Phase 4 tests -> `3 passed`.
    - Focused exact-local/query tests -> `8 passed`.
    - Focused local-region/lane tests -> `7 passed`.
    - `python -m ruff check packages\sources\query_decomposition.py packages\sources\local_source_patterns.py packages\sources\lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_local_source_patterns.py tests\test_sources_lane_execution.py` -> pass.
    - `python -m py_compile packages\sources\query_decomposition.py packages\sources\local_source_patterns.py packages\sources\lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_local_source_patterns.py tests\test_sources_lane_execution.py` -> pass.
    - Focused source suite -> `233 passed`.
    - Source regression -> `27 passed`.
    - Domestic source regression -> `16 passed`.
- 2026-04-30: Phase 5 completed with macro-to-local obligation fanout:
  - Macro policy-to-demand/project/order queries now add `local_rollout` in query decomposition when no local region is named and the query explicitly asks for real-world implementation evidence.
  - Retrieval plans now keep `national_policy_direction` and require `provincial_policy_rollout` for macro disclosure/project/data validation queries such as M02.
  - `macro_to_local_obligation` is attached to rollout/project/data/disclosure lanes where applicable.
  - Generic macro-to-local search phrases are used only for topics without stronger existing templates; low-altitude and real-estate special templates remain intact.
  - Validation:
    - RED: new Phase 5 decomposition/retrieval tests failed for missing `local_rollout`, missing national/provincial lanes, and `全国`-prefixed project fanout.
    - GREEN: targeted Phase 5 tests -> `2 passed`; project-prefix regression -> `1 passed`.
    - Phase-adjacent query/retrieval tests -> `26 passed`.
    - `python -m ruff check packages\sources\query_decomposition.py packages\sources\retrieval_plan.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py` -> pass.
    - `python -m py_compile packages\sources\query_decomposition.py packages\sources\retrieval_plan.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py` -> pass.
    - Focused source suite -> `235 passed`.
    - Source regression -> `27 passed`.
    - Domestic source regression -> `16 passed`.
- 2026-04-30: Phase 6 completed with a low-cost targeted gate:
  - Added `data/tmp/source_quality_stress_eval/source_transaction_file_local_depth_phase6_subset_cases.json`.
  - Added focused M02 regression case file: `data/tmp/source_quality_stress_eval/source_transaction_file_local_depth_phase6_m02_case.json`.
  - Live subset v1:
    - Run dir: `data/tmp/source_quality_stress_eval/runs/source_transaction_file_local_depth_v1_phase6_subset_v1`
    - Result: `6 success`, `34` estimated Tavily credits, `35546.57 ms` average latency.
    - Finding: M02 `local_rollout` existed but was still rejected because the task regional level was `national`.
  - Remediation:
    - Macro-to-local `local_rollout` now uses `RegionalLevel.PROVINCIAL`.
    - Macro-to-local rollout includes bounded official domains: `gov.cn`, `ndrc.gov.cn`, `miit.gov.cn`.
  - Focused M02 regression:
    - Run dir: `data/tmp/source_quality_stress_eval/runs/source_transaction_file_local_depth_v1_phase6_m02_v1`
    - Result: `1 success`, `6` estimated Tavily credits, `32404.02 ms` latency.
    - M02 `local_rollout` now enters `first_wave_local_policy_generic`; remaining result is `partial/budget_exhausted`, not `invalid_request`.
  - Live subset v2:
    - Run dir: `data/tmp/source_quality_stress_eval/runs/source_transaction_file_local_depth_v1_phase6_subset_v2`
    - Result: `6 success`, `35` estimated Tavily credits, `39021.25 ms` average latency.
    - `Download is starting` marker count: `0`.
    - Batch report has no audit blockers because DeepSeek audit was not run in Phase 6.
  - Narrower blockers carried forward:
    - M02 macro-to-local rollout can still hit slow municipal pages and exhaust the one-credit lane budget.
    - K07 local rollout still has anti-bot/forbidden extraction partials on stale local pages.
    - Several direct structured lanes remain partial by design until full 12-case audit confirms whether evidence is sufficient.
  - Validation:
    - `python -m ruff check packages\sources\query_decomposition.py packages\sources\retrieval_plan.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py` -> pass.
    - `python -m py_compile packages\sources\query_decomposition.py packages\sources\retrieval_plan.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py` -> pass.
    - Phase-adjacent query/retrieval tests -> `26 passed`.
    - Focused source suite -> `235 passed`.
    - Source regression -> `27 passed`.
    - Domestic source regression -> `16 passed`.
- 2026-04-30: Phase 7 completed the 12-case smoke rerun and identified a narrower successor blocker:
  - Live run:
    - Run dir: `data/tmp/source_quality_stress_eval/runs/source_transaction_file_local_depth_v1_phase7_live_v1`
    - Result: `12 success / 0 runtime error`
    - Estimated Tavily credits: `69`
    - Average latency: `37125.15 ms`
    - `Download is starting` marker count: `0`
  - DeepSeek audit:
    - Audit status: `12 success`
    - Shape diagnostics: `0`
    - Verdicts: `8 fail / 4 weak_pass`
    - Total tokens: `360596`
  - Batch source gaps:
    - `tender_or_procurement=5` passed the Phase 7 threshold `<=5`.
    - `project_list=3` passed the Phase 7 threshold `<=4`.
    - `statistics=4` failed the Phase 7 threshold `<=3`.
    - Other recurring gaps: `industry_association=3`, `industry_report=3`, `local_government=3`, `regulatory_record=2`.
  - Phase 7 assessment:
    - Runtime, extraction leakage, audit transport, audit shape, `tender_or_procurement`, and `project_list` improved enough for this PLAN's focus.
    - The remaining blocker is not another transaction/file-specific problem. It is now a reusable local/regional quantitative and regional-precision problem: local statistics, energy, fiscal, trade/customs, exact-local source profiles, and city/county source-level mismatch.
    - The full 50-query live run remains deferred.
- 2026-04-30: Phase 8 completed as a readiness decision:
  - Staged 50-query live is not cost-effective yet.
  - Current 12-case gate already exposes the next reusable blocker class clearly enough.
  - Successor PLAN selected: `.agent/PLANS/source-local-statistics-regional-precision-v1.md`.
  - This PLAN is closed as `completed_with_successor_blocker` rather than continuing query-specific remediation.

## Risks And Rollback

Risks:

- Overfitting file/source patterns to the 12-case smoke set.
- Weakening evidence gates to improve scores artificially.
- Counting file metadata as evidence when content was not extracted.
- Expanding Tavily budget instead of improving source precision.
- Accidentally moving direct-keep primary lanes into Tavily/Crawl4AI primary execution.

Rollback:

- Revert only files changed under this PLAN.
- Keep `source_local_quant_file_backbone_v1_phase5_live_v1` as the comparison baseline.
- Disable new file extraction or source-family rules if they increase false positives or cost without improving evidence sufficiency.

## Next Action

Hand off to successor PLAN:

1. Make `.agent/PLANS/source-local-statistics-regional-precision-v1.md` the active PLAN.
2. Use the Phase 7 artifacts as the baseline, not as query-specific tuning targets.
3. Do not run full 50-query live until the successor PLAN passes a 12-case smoke or records a narrower blocker.
