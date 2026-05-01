# Source Local Procurement Regulatory Depth v1

Status: active_phase1_completed_pending_targeted_gate

Created: 2026-04-30

Primary active PLAN: yes

Supersedes:

- `.agent/PLANS/archive/source-local-statistics-regional-precision-v1.md`

## Objective

Build the next reusable source-family backbone after `source-local-statistics-regional-precision-v1`.

The previous PLAN fixed the statistics/source-profile blocker:

- `M02` / `M03` / `P08` data-metrics paths now recover official statistics or statistical-classification evidence.
- Phase 6 live runtime reached `12 success / 0 runtime error`.
- `statistics` no longer appears as the dominant general source-class blocker.

The remaining blocker moved to local procurement, public-resource, regulatory, environmental/land, and city/county project-record depth.

This PLAN must improve general source-family patterns, not tune isolated query IDs.

## Task Classification

- Primary area: `source_layer`
- Secondary areas: `domestic_source_collectors`, `eval_policy_ops`, `provider_layer`
- Default execution mode: `light_subagent` for scoped source implementation; `local_direct` for artifacts/status/docs.
- Escalate to `full_subagent` only for protected-contract or provider-abstraction changes.

Protected contracts not authorized for silent change:

- EvidenceBundle schema
- EvidenceItem citation fields
- `source_quality_summary` shape
- research analyze response shape
- provider abstraction semantics
- task/job status semantics
- `run` / `run_steps` meaning
- content/delivery metadata contracts

## Baseline

Input run:

- `data/tmp/source_quality_stress_eval/runs/source_local_statistics_regional_precision_v1_phase6_12case_live_v1`

Baseline snapshot:

- Live: `12 success`, `66` estimated Tavily credits, `60972.31 ms` average latency.
- DeepSeek audit: `12 success`, shape diagnostics `0`, verdicts `8 fail / 4 weak_pass`, `364916` tokens.
- Passed:
  - `statistics <= 3` at the general source-class level.
  - `project_list <= 4` with `project_list=2`.
- Failed:
  - `tender_or_procurement <= 5`, actual `7`.
- Main gaps:
  - `tender_or_procurement=7`: `C07`, `K07`, `K09`, `K12`, `P04`, `P08`, `P10`.
  - `regulatory_record=4`: `C01`, `K07`, `K09`, `M03`.
  - `environmental_or_land_record=2`: `C01`, `K07`.
  - residual city/county source-level mismatch across city/county and macro-to-local cases.

## Scope

In scope:

- Public-resource trading / government procurement source patterns.
- City/county tender and procurement fallback strategy.
- Project filing, approval, and key-project records.
- Environmental impact assessment, land transfer, planning, and natural-resource records.
- Local regulatory records and permits where publicly accessible.
- City/county domain and source-profile updates for reusable families.
- Extraction quality gates for public-resource download/detail pages.
- Low-cost targeted validation before a 12-case rerun.

Out of scope unless reopened:

- Full 50-query live run.
- Browser automation as default.
- OCR.
- Login-gated or paid databases.
- Direct securities investment advice.
- Public API response-shape changes.
- Query-ID-specific hardcoding.

## Design Direction

Use a source-family matrix instead of query-by-query fixes:

```text

query obligation
  -> expected source class
  -> expected administrative level
  -> public-resource / procurement / regulatory / land / project source family
  -> exact-local or parent fallback classification
  -> extraction quality gate
  -> evidence eligibility or explicit source gap

```

Hard rules:

- Do not count generic policy/news pages as tender, procurement, land, regulatory, or project evidence.
- Do not count parent-level records as exact-local evidence unless the claim is explicitly parent-level.
- Prefer official detail pages and files over search snippets.
- Treat download-only pages as adapter candidates if Crawl4AI cannot extract meaningful content.
- Keep the 12-case smoke set as a regression gate, not an optimization target.

## Agent Execution Contract

Default route:

- `local_direct`: Phase 0 artifacts, status updates, report parsing.
- `light_subagent`: scoped implementation in source/router/extraction tests.
- `remediation_gate`: failed live/eval gates with unchanged goals.
- `full_subagent`: protected contracts, provider semantics, public response shapes, or multi-lane architecture change.

Role expectations if subagents are used:

- Project director: refine this PLAN and keep source-family scope broad enough to avoid query overfitting.
- Group2 worker: implement only assigned source-family slice with explicit file ownership.
- Code quality checker: run focused ruff, compile, pytest, source regression, domestic regression, and scope review.
- Functional validator: inspect actual live/eval artifacts, not only test summaries.
- Summarizer: only after this PLAN reaches its done condition.

## Phase 0: Blocker Matrix Freeze

Status: completed

Execution mode: `local_direct`

Objective:

- Convert Phase 6 audit output into a reusable source-family blocker matrix.

Artifacts:

- `data/tmp/source_quality_stress_eval/source_local_procurement_regulatory_depth_phase0/blocker_matrix.json`
- `data/tmp/source_quality_stress_eval/source_local_procurement_regulatory_depth_phase0/blocker_matrix.md`

Acceptance criteria:

- Matrix groups blockers by source family, not only by case ID.
- Matrix selects first implementation slice.
- No production code changes.

## Phase 1: Tender / Public-Resource Backbone

Status: completed

Execution mode: `light_subagent`

Objective:

- Reduce `tender_or_procurement` misses without accepting irrelevant procurement pages.

Tasks:

- Add source-family tests for public-resource detail pages and government-procurement records.
- Improve domain/source-role gating for city/county procurement pages.
- Add fallback candidate quality gates for download/detail pages.
- Preserve `project_list` and `tender_or_procurement` distinction.

Acceptance criteria:

- `tender_or_procurement` improves on a low-cost targeted subset.
- Generic policy/news pages remain rejected as procurement evidence.

## Phase 2: Regulatory / Environmental / Land Backbone

Status: pending

Execution mode: `light_subagent`

Objective:

- Improve regulatory, environmental, land, planning, and natural-resource evidence.

Tasks:

- Add reusable official-record patterns for ecology/environment and natural-resource domains.
- Add city/county exact-local tests for land/environment records.
- Improve source-class assignment for EIA, land transfer, planning, and regulatory notice pages.
- Preserve parent fallback transparency.

Acceptance criteria:

- `regulatory_record` and `environmental_or_land_record` misses decline on targeted cases.
- Wrong-region or generic official-record pages stay rejected.

## Phase 3: City / County Project Record Depth

Status: pending

Execution mode: `light_subagent`

Objective:

- Improve exact-local project filing, approval, key-project, and industrial-park project records.

Tasks:

- Add source profile updates or manual source candidates for common city/county project-record patterns.
- Add query decomposition fanout for local project evidence when the user asks for project reality, construction, production, capacity, land, or filing evidence.
- Add anti-overfit tests across at least two city/county examples.

Acceptance criteria:

- City/county source-level mismatch declines on targeted cases.
- Parent-level evidence remains claim-limited.

## Phase 4: Low-Cost Targeted Gate

Status: pending

Execution mode: `remediation_gate`

Candidate cases:

- `C01`: Hefei NEV project/land/environment records.
- `C07`: Changzhou battery/PV capacity and project records.
- `K07`: Feixi county NEV project/land/environment/procurement records.
- `K09`: Shenmu coal/coal-chemical regulatory/procurement/statistics depth.
- `K12`: Ruoqiang infrastructure/procurement/company-filing project records.
- `P08`: Inner Mongolia project approval, tariff, local energy policy, and procurement evidence.

Acceptance criteria:

- Runtime succeeds for all selected cases.
- `tender_or_procurement`, `regulatory_record`, and `environmental_or_land_record` gaps improve or a narrower adapter/browser/OCR blocker is recorded.
- Cost/latency outliers are visible.

## Phase 5: 12-Case Smoke Rerun

Status: pending

Execution mode: `light_subagent`

Acceptance criteria:

- Live: `12 success / 0 runtime error`.
- DeepSeek audit: `12 success`, shape diagnostics `0`.
- `tender_or_procurement <= 5`.
- `project_list <= 4`.
- `statistics <= 3`.
- `regulatory_record` and `environmental_or_land_record` decline versus Phase 6 baseline.
- Full 50-query live remains deferred unless Phase 6 readiness approves it.

## Phase 6: 50-Query Readiness Decision

Status: pending

Execution mode: `planning_only`

Acceptance criteria:

- Record whether staged 50-query evaluation is cost-effective.
- If ready, define batches and budget caps.
- If not ready, record the next narrower blocker.

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
- the next step is full 50-query live without readiness approval;
- the user explicitly pauses.

## Validation Loop

Focused local checks:

```powershell
python -m ruff check <changed files>
python -m py_compile <changed files>
pytest -q tests\test_sources_lane_execution.py tests\test_sources_source_resolver.py tests\test_sources_local_source_patterns.py tests\test_sources_query_decomposition.py
```

Required source regressions:

```powershell
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_retrieval_plan.py tests\test_sources_disclosure_mapping.py
pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py
pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py
```

Live/eval checks:

```powershell
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\strong_evidence_smoke_cases_v1.json --mode extraction_inspection --max-search-tasks 3 --max-rounds 1 --max-candidates 2 --max-official-record-search-credits 2 --content-chars 800 --output-dir <run_dir>
python data\tmp\_source_quality_llm_audit.py --run-dir <run_dir> --provider deepseek --model deepseek-v4-pro --thinking enabled --reasoning-effort max --resume
python data\tmp\_source_quality_batch_report.py --run-dir <run_dir> --print-json
```

## Cost Controls

- Do not run the full 50-query live set during this PLAN unless Phase 6 explicitly approves it.
- Use targeted subset gates before the 12-case smoke.
- Keep Tavily low-cost defaults unless a phase records a bounded exception.
- Use DeepSeek audit only after live artifacts complete.
- Use local `.env` key pool only through process environment loading; never write raw keys to tracked files or artifacts.

## Done Condition

This PLAN is done when one of these is true:

- local procurement/regulatory/project depth passes the 12-case smoke gate and Phase 6 records staged 50-query readiness; or
- the 12-case gate identifies a narrower blocker requiring provider/data-adapter/browser/OCR Architecture Gate; or
- implementation reaches an out-of-scope requirement such as OCR, browser automation, login-gated source, paid data, or protected-contract change.

## Progress

- 2026-04-30: PLAN created from `source-local-statistics-regional-precision-v1` Phase 6 successor blocker. No production code changed in this planning step.
- 2026-04-30: Phase 0 completed:
  - Created `data/tmp/source_quality_stress_eval/source_local_procurement_regulatory_depth_phase0/blocker_matrix.json`.
  - Created `data/tmp/source_quality_stress_eval/source_local_procurement_regulatory_depth_phase0/blocker_matrix.md`.
  - Frozen six blocker families.
  - Selected first implementation slice: `public_resource_procurement`.
- 2026-05-01: Phase 1 — procurement classification AND search pipeline integration completed:
  - Added `is_procurement_domain()`, `domain_has_procurement_signal()`, `is_generic_policy_page_candidate()` in `source_resolver.py`
  - Integrated procurement detection into `search_assisted_domestic.py`: `_source_classes_for_task()` now detects procurement keywords and adds `tender_or_procurement`; `_annotate_source_class_metadata()` adds procurement source class for procurement-domain documents
  - Files changed: `packages/sources/source_resolver.py`, `packages/sources/search_assisted_domestic.py`
  - Tests: 12 new procurement tests + procurement context detection tests
  - Validation: ruff pass, 321 tests passing (276 focused regression + 45 broader source)
  - Live targeted gate DEFERRED: requires Tavily/DeepSeek API calls; deferred per Route C strategy (switch to substrate first)
- Next per Route C: pause source-layer work, create `longtasks-substrate-v1` PLAN

## Risks And Rollback

Risks:

- Overfitting city/county domains from the 12-case smoke set.
- Misclassifying generic policy/news pages as procurement or regulatory evidence.
- Increasing Tavily cost through broad fanout instead of better source-family routing.
- Treating parent/provincial records as exact city/county records.
- Adding heavy adapters before source-profile/search-assisted paths are proven insufficient.

Rollback:

- Revert only files changed under this PLAN.
- Keep `source_local_statistics_regional_precision_v1_phase6_12case_live_v1` as the comparison baseline.
- Disable new source-family rules if they increase false positives or cost without improving evidence sufficiency.

## Next Action

Phase 1 complete (classification + pipeline integration). Per Route C strategy: pause this PLAN, record `tender_or_procurement` baseline at `7` (target `≤5`), defer live targeted gate until after substrate stabilization. Next active PLAN: `longtasks-substrate-v1`.
