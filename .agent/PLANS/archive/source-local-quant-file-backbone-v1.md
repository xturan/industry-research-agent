# Source Local Quant File Backbone v1

Status: completed_with_successor_blocker

Created: 2026-04-30

Primary active PLAN: yes

Supersedes:

- `.agent/PLANS/archive/source-family-evidence-backbone-v1.md` successor blocker

## Objective

Build the next reusable source backbone after the Source Family Evidence Backbone v1 gate.

The prior PLAN improved source-family precision and reduced several source-class gaps, but the 12-case smoke gate still failed quality. The remaining blocker is narrower:

- local statistics / fiscal / quantitative official evidence is still too weak;
- download-style PDF/XLS/DOC endpoints and failed file extraction are reducing strong evidence;
- exact-local city/county profile coverage is not yet strong enough for local claims;
- several audits recommend adapters or profile updates, but they must be generalized rather than hard-coded to one smoke query.

This PLAN should improve the general retrieval/extraction pattern for local quantitative and file-backed evidence before any full 50-query live run.

## Baseline

Input artifact:

- `data/tmp/source_quality_stress_eval/runs/source_family_evidence_backbone_v1_phase7_live_v1`

Phase 7 baseline:

- Live: `12 success / 0 runtime error`
- DeepSeek audit: `12 success`, shape diagnostics `0`
- Verdicts: `8 fail / 4 weak_pass`
- Estimated Tavily credits: `71`
- Average latency: `41380.16 ms`
- Source-class gaps:
  - `statistics=4` failed target `<=3`
  - `tender_or_procurement=4` passed target `<=5`
  - `project_list=3` passed target `<=5`
  - `local_government=1` passed target `<=3`
  - `environmental_or_land_record=1` passed target `<=2`
- Reopen cases from roadmap: `C07`, `C09`, `K07`, `M02`, `M03`, `P04`, `P08`
- Adapter candidates from roadmap: `K07`, `M02`, `M03`, `P04`, `P08`

## Task Classification

- Primary area: `source_layer`
- Secondary areas: `domestic_source_collectors`, `eval_policy_ops`, `provider_layer`
- Execution default: `light_subagent` for scoped source/eval implementation; `local_direct` for Phase 0 artifact work.

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

No protected-contract change is allowed without an explicit Architecture Gate and `full_subagent` escalation.

## Scope

In scope:

- Local statistics / fiscal source role and domain pattern improvements.
- Official quantitative evidence routing for province/city/county tasks.
- Download-capable file decisioning for PDF/XLS/DOC endpoints when they are strong evidence candidates.
- Extraction failure classification and candidate downgrading for download, SSL, anti-bot, zero-text, and unsupported file cases.
- Exact-local source profile seed rules for city/county official sources.
- Low-cost subset validation and one 12-case smoke rerun after focused changes.

Out of scope unless reopened:

- Full 50-query live run.
- Browser automation as a default crawler.
- OCR.
- Login-gated, paid, or private databases.
- Direct securities investment advice.
- Public API response-shape changes.
- Query-specific hard-coded fixes.

## Design Direction

Move from generic search success to strong local quantitative/file evidence:

```text
tiaokuai evidence obligation
  -> local quantitative source expectation
  -> exact-local / parent fallback source profile
  -> discovery candidate
  -> file/download decision gate
  -> extraction or structured failure metadata
  -> evidence quality gate
  -> source sufficiency diagnostics
```

## Implementation Principles

- Treat the 12-case set as symptoms, not tuning targets.
- Add reusable source-family and source-role rules; do not branch by query ID or case ID.
- Prefer deterministic URL/domain/path/source-class checks before LLM judgment.
- Do not count failed downloads, portal pages, or wrong-level statistics as strong evidence.
- Preserve parent fallback transparency with `parent_evidence_only`, `local_claim_allowed`, `fallback_level`, and `fallback_source`.
- Use low-cost subset runs before any 12-case rerun.

## Phases

### Phase 0: Successor Blocker Matrix

Execution mode: `local_direct`

Objective:

- Normalize the Phase 7 audit/batch outputs into a concise blocker matrix for this PLAN.

Tasks:

- Read `batch_eval.json`, `source_roadmap.json`, and `llm_audit_summary.json`.
- Group blockers by reusable source family:
  - local quantitative statistics/fiscal;
  - download/file extraction;
  - exact-local city/county profile;
  - sector/company/association supplement.
- Create matrix artifacts under `data/tmp/source_quality_stress_eval/source_local_quant_file_backbone_phase0/`.
- Select the first implementation slice.

Acceptance criteria:

- Matrix JSON and markdown exist.
- The matrix records source-family blockers rather than query-specific fixes.
- No full 50-query live run is triggered.
- No production code is changed.

### Phase 1: Local Quantitative Source Contract

Execution mode: `light_subagent`

Objective:

- Strengthen the internal expectation for official quantitative evidence without public response-shape changes.

Tasks:

- Add or refine internal source-role helpers for statistics, fiscal, energy, customs/trade, and industry quantitative sources.
- Add tests proving statistics/fiscal pages are accepted by source role and media/news mirrors are rejected.
- Ensure parent-level quantitative evidence cannot silently satisfy exact-local claims.

Acceptance criteria:

- Statistics/fiscal source recognition improves without weakening false-positive gates.
- Tests cover at least province and city/county examples.

### Phase 2: Download/File Extraction Gate

Execution mode: `light_subagent`

Objective:

- Stop losing strong evidence merely because the URL is a PDF/XLS/DOC/download endpoint, while keeping failed files audit-visible.

Tasks:

- Add a deterministic download/file candidate classifier.
- Decide when to use Crawl4AI, direct HTTP download, existing PDF extraction, or structured failure metadata.
- Add negative tests for zero-text, unsupported file, wrong-region download, and portal download endpoints.

Acceptance criteria:

- Failed file candidates are not counted as strong evidence.
- Usable PDF/XLS/DOC candidates can produce auditable text/metadata or a clear extraction failure.
- No browser automation or OCR is introduced.

### Phase 3: Exact-Local Profile Seed Rules

Execution mode: `light_subagent`

Objective:

- Improve city/county coverage without enumerating every locality.

Tasks:

- Add source profile seed patterns for local government, statistics bureau, fiscal bureau, DRC, MIIT/industry bureau, ecology bureau, natural resources bureau, and public-resource platforms.
- Preserve exact-local -> parent -> national fallback ordering.
- Add anti-overfit tests proving the rules work across at least two different regions and levels.

Acceptance criteria:

- Exact-local candidate routing improves without hard-coded smoke-case branches.
- Parent-only fallback remains explicit and cannot support exact-local claims.

### Phase 4: Low-Cost Targeted Subset

Execution mode: `light_subagent`

Objective:

- Validate the new rules before another full 12-case smoke gate.

Subset candidates:

- `P04` for provincial statistics/fiscal.
- `P08` for energy/statistics/download evidence.
- `K07` for county exact-local file/profile stress.
- `C07` for city quantitative/project evidence.
- `M02` or `M03` for macro query requiring quantitative/local rollout supplement.

Acceptance criteria:

- Runtime succeeds for all selected cases.
- `statistics` missing count improves versus Phase 7 subset baseline or a narrower blocker is recorded.
- Download/file failures are structured and visible.

### Phase 5: 12-Case Smoke Rerun

Execution mode: `light_subagent`

Objective:

- Re-run the same 12-case gate only after focused subset validation.

Acceptance criteria:

- Live: `12 success / 0 runtime error`.
- DeepSeek audit: `12 success`, shape diagnostics `0`.
- `statistics <= 3`.
- Weak/pass count improves from `4/12`, or a narrower blocker is recorded.
- Full 50-query live remains deferred unless Phase 6 approves it.

### Phase 6: 50-Query Readiness Decision

Execution mode: `planning_only` or `local_direct`

Objective:

- Decide whether the system is ready for staged 50-query evaluation.

Acceptance criteria:

- A cost-aware decision is recorded.
- No full 50-query live run occurs by default.

## Continue Rule

After each phase, continue automatically when:

- acceptance criteria pass;
- required validation passes;
- no protected-contract change is needed;
- no browser automation, OCR, login-gated source, or paid/private data is required;
- cost and latency remain visible;
- the next phase has a safe execution mode.

Stop when:

- a protected-contract change is required;
- full 50-query live is the next step but cost/quality gate is not met;
- validation fails and the safe fix is unclear;
- implementation would become query-specific hardcoding;
- the user explicitly pauses.

## Validation Loop

Focused source checks:

```powershell
python -m ruff check <changed files>
python -m py_compile <changed files>
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_retrieval_plan.py tests\test_sources_disclosure_mapping.py
pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py
pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py
```

## Cost Controls

- Do not run full 50-query live during this PLAN unless Phase 6 explicitly records readiness and budget cap.
- Use subset evals before the 12-case gate.
- Use DeepSeek audit only after live artifacts are complete and worth judging.
- Record estimated credits and latency in every live gate summary.
- Use the local `.env` Tavily key pool only through process env loading; never write raw keys to tracked files.

## Done Condition

This PLAN is done when one of these is true:

- local quantitative/file evidence passes the 12-case smoke gate and Phase 6 records staged 50-query readiness; or
- the 12-case gate identifies a narrower blocker requiring an adapter/provider Architecture Gate; or
- implementation reaches a legitimate out-of-scope requirement such as browser automation, OCR, login-gated sources, or protected-contract change.

## Progress

- 2026-04-30: PLAN created from `source-family-evidence-backbone-v1` Phase 7 / Phase 8 successor blocker.
- 2026-04-30: Phase 0 completed with successor blocker matrix artifacts:
  - `data/tmp/source_quality_stress_eval/source_local_quant_file_backbone_phase0/blocker_matrix.json`
  - `data/tmp/source_quality_stress_eval/source_local_quant_file_backbone_phase0/blocker_matrix.md`
  - Frozen four reusable blocker families: `local_quantitative_statistics_fiscal`, `download_file_extraction`, `exact_local_city_county_profile`, and `sector_company_association_supplement`.
  - First implementation slice selected: `local_quantitative_statistics_fiscal`.
  - Phase 0 stayed artifact-only; no production code changed and no full 50-query live run was triggered.
- 2026-04-30: Phase 1 completed with local quantitative source-role expansion:
  - Added a RED/GREEN regression for official energy-operation quantitative data pages, using `nyj.*.gov.cn` as a source-role example rather than a query-specific branch.
  - `data_metrics` search fallback now accepts official quantitative department pages from energy/DRC/industry/transport/commerce-style government domains only when title/URL carries strong quantitative signals such as energy operation, industry operation, monthly report, monitoring data, generated power, electricity usage, output, price index, or investment data.
  - Existing media/news false-positive gates remain intact.
  - Validation passed:
    - RED: `pytest -q tests\test_sources_lane_execution.py -k "official_energy_operation_data_pages"` failed before implementation.
    - GREEN: same targeted test -> `1 passed`.
    - `pytest -q tests\test_sources_lane_execution.py -k "data_metrics"` -> `12 passed`.
    - `python -m ruff check packages\sources\lane_execution.py tests\test_sources_lane_execution.py` -> pass.
    - `python -m py_compile packages\sources\lane_execution.py tests\test_sources_lane_execution.py` -> pass.
    - Focused source suite -> `214 passed`.
    - Source regression -> `27 passed`.
    - Domestic source regression -> `16 passed`.
- 2026-04-30: Phase 2 completed with download/file extraction gate:
  - Added deterministic data-metrics file/download candidate classification for `pdf`, `xls`, `xlsx`, `doc`, `docx`, `csv`, `zip`, and generic download/attachment endpoints.
  - Strong official file/download candidates are no longer sent to Crawl4AI as webpage candidates when no file adapter is available.
  - File/download candidates are downgraded with structured metadata: `data_metrics_file_requires_adapter`, `file_candidate_kind`, `extraction_failure_class=file_or_download`, and `extraction_failure_stage=candidate_classification`.
  - Wrong-region file/download candidates remain rejected as regional mismatches before the file gate, preserving exact-local evidence quality.
  - Validation passed:
    - RED: `pytest -q tests\test_sources_lane_execution.py -k "file_download_as_evidence"` failed before implementation because the `.xlsx` candidate was sent to Crawl4AI.
    - GREEN: same targeted test -> `1 passed`.
    - `pytest -q tests\test_sources_lane_execution.py -k "data_metrics"` -> `15 passed`.
    - `python -m ruff check packages\sources\lane_execution.py tests\test_sources_lane_execution.py` -> pass.
    - `python -m py_compile packages\sources\lane_execution.py tests\test_sources_lane_execution.py` -> pass.
    - Focused source suite -> `217 passed`.
    - Source regression -> `27 passed`.
    - Domestic source regression -> `16 passed`.
- 2026-04-30: Phase 3 completed with exact-local profile seed rules:
  - Added generic local city/county/flag extraction for unknown exact-local names such as `昆山市`, `曹县`, and `准格尔旗` without enumerating every locality.
  - Added false-positive guards so generic words such as `市场`, `区分`, and `地方扶持` do not create fake regional focus or local-rollout lanes.
  - Added `gov.cn` as a generic exact-local discovery seed while preserving region-match gates so broad national pages cannot satisfy local evidence without local text.
  - Preserved exact-local `data_metrics` domain ordering by keeping local domains before parent/province domains during repair.
  - Validation passed:
    - RED/GREEN generic exact-local query tests and source-resolver broad-`gov.cn` rejection tests.
    - Phase 3 related tests -> `155 passed`.
    - `python -m ruff check` on changed source/test files -> pass.
    - `python -m py_compile` on changed source/test files -> pass.
    - Focused source suite -> `223 passed`.
    - Source regression -> `27 passed`.
    - Domestic source regression -> `16 passed`.
- 2026-04-30: Phase 4 completed with low-cost targeted subset and file-gate remediation:
  - Created `data/tmp/source_quality_stress_eval/source_local_quant_file_backbone_phase4_subset_cases.json`.
  - Ran v1 targeted subset for `P04`, `P08`, `K07`, `C07`, `M02`, and `M03`: `6 success`, `33` estimated Tavily credits, `33278.28 ms` average latency.
  - v1 exposed that `project_transaction` download/PDF candidates still reached Crawl4AI as `Download is starting`; this was generalized into a project fallback file/download gate rather than handled by query ID.
  - Added project fallback file/download classification with `project_file_requires_adapter`, `file_candidate_kind`, `extraction_failure_class=file_or_download`, and `file_candidates_require_adapter`.
  - Ran v2 targeted subset after remediation: `6 success`, `37` estimated Tavily credits, `29029.82 ms` average latency.
  - v2 artifact confirms file/download candidates are visible as structured file gates and no `Download is starting` marker remains in per-query task artifacts.
  - Remaining narrower blockers before/inside Phase 5:
    - `P08` `data_metrics` still hits `search_credit_budget_exhausted` under the low-cost one-round budget.
    - `M03` `data_metrics` has PDF file candidates requiring a file adapter.
    - `P08` `project_transaction` has public-resource download endpoint candidates requiring a file/download adapter.
  - Validation passed:
    - Project/data fallback file-gate tests -> `28 passed`.
    - Phase 3/4 related tests -> `155 passed`.
    - `python -m ruff check` on changed source/test files -> pass.
    - `python -m py_compile` on changed source/test files -> pass.
    - Focused source suite -> `223 passed`.
    - Source regression -> `27 passed`.
    - Domestic source regression -> `16 passed`.
- 2026-04-30: Phase 5 completed with successor blocker:
  - Live artifact: `data/tmp/source_quality_stress_eval/runs/source_local_quant_file_backbone_v1_phase5_live_v1`.
  - Live result: `12 success`, `70` estimated Tavily credits, `55287.68 ms` average latency, `query_invalid_count=0`.
  - DeepSeek audit: `12 success`, `0` shape diagnostics, `361117` tokens.
  - Audit verdicts: `1 blocker / 8 fail / 3 weak_pass`.
  - Acceptance result:
    - Runtime passed.
    - Audit transport/schema passed.
    - `statistics=3` met target `<=3`.
    - Weak/pass count did not improve from baseline `4/12`; current result is `3/12`.
    - `tender_or_procurement=7` regressed versus baseline `4` and failed target `<=5`.
  - Positive practical change:
    - File/download candidates are now structured as adapter-required gaps.
    - No per-query task artifact contains `Download is starting`.
  - Narrower successor blocker:
    - Public-resource / government-procurement / project-list file/download candidates need a real official file adapter.
    - Exact-local city/county/flag evidence still lacks enough project, land, environmental, statistics, and procurement depth.
    - Macro policy-to-project queries need bounded local/statistical fanout rather than central policy evidence alone.
  - Phase 6 full 50-query readiness was not reached; full 50-query live remains deferred.
  - Successor PLAN created:
    - `.agent/PLANS/source-transaction-file-local-depth-v1.md`
    - Phase 0 artifacts:
      - `data/tmp/source_quality_stress_eval/source_transaction_file_local_depth_phase0/blocker_matrix.json`
      - `data/tmp/source_quality_stress_eval/source_transaction_file_local_depth_phase0/blocker_matrix.md`

## Risks And Rollback

Risks:

- Overfitting city/county source patterns to the 12 smoke cases.
- Counting weak media or portal pages as quantitative evidence.
- Expanding live search budget instead of improving precision.
- Introducing brittle file extraction paths for government download endpoints.
- Accidentally changing public response or EvidenceBundle contracts.

Rollback:

- Revert only files changed under this PLAN.
- Keep `source_family_evidence_backbone_v1_phase7_live_v1` as the comparison baseline.
- Disable a new source-role or file gate if it increases source drift or cost without improving evidence sufficiency.

## Next Action

This PLAN reached its done condition by identifying a narrower adapter/source-depth blocker.

Next active PLAN:

- `.agent/PLANS/source-transaction-file-local-depth-v1.md`

Next action:

1. Execute the successor PLAN Phase 1 file/download adapter Architecture Gate.
2. Do not run the full 50-query live evaluation until the successor PLAN records 12-case readiness.
