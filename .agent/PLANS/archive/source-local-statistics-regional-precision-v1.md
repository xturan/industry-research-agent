# Source Local Statistics Regional Precision v1

Status: completed_with_successor_blocker

Created: 2026-04-30

Primary active PLAN: yes

Supersedes:

- `.agent/PLANS/archive/source-transaction-file-local-depth-v1.md`

## Objective

Build the next reusable source backbone after `source-transaction-file-local-depth-v1`.

The previous PLAN fixed or improved the transaction/project/file/local-depth slice enough to remove the blocker and meet several 12-case thresholds:

- live execution: `12 success / 0 runtime error`;
- DeepSeek audit transport: `12 success`, shape diagnostics `0`;
- `tender_or_procurement=5`, meeting the target `<=5`;
- `project_list=3`, meeting the target `<=4`;
- no `Download is starting` leakage.

The remaining bottleneck is now a more general class:

- local / regional statistics;
- energy, fiscal, production, trade/customs, and electricity data;
- exact-local city/county source precision;
- source-level mismatch where parent or unrelated locality evidence is accepted as if it were local evidence.

This PLAN must improve reusable source-family and routing patterns. The 12-case smoke set and 50-query pressure set are regression instruments, not targets for query-specific hardcoding.

## Task Classification

- Primary area: `source_layer`
- Secondary areas: `domestic_source_collectors`, `eval_policy_ops`, `provider_layer`
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

- `data/tmp/source_quality_stress_eval/runs/source_transaction_file_local_depth_v1_phase7_live_v1`

Baseline snapshot:

- Live: `12 success`, `69` estimated Tavily credits, `37125.15 ms` average latency
- DeepSeek: `12 success`, shape diagnostics `0`, `360596` tokens
- Audit verdicts: `8 fail / 4 weak_pass`
- Main gaps:
  - `tender_or_procurement=5`
  - `statistics=4`
  - `industry_association=3`
  - `industry_report=3`
  - `local_government=3`
  - `project_list=3`
  - `regulatory_record=2`
- Threshold status:
  - `tender_or_procurement <= 5`: passed
  - `project_list <= 4`: passed
  - `statistics <= 3`: failed
- Phase 0 artifacts:
  - `data/tmp/source_quality_stress_eval/source_local_statistics_regional_precision_phase0/blocker_matrix.json`
  - `data/tmp/source_quality_stress_eval/source_local_statistics_regional_precision_phase0/blocker_matrix.md`

## Scope

In scope:

- Local statistics and statistical-bulletin source profiles.
- Fiscal budget / final-account source profiles.
- Energy, electricity, production, and industrial operation data source profiles.
- Trade/customs and port/logistics statistics source profiles where publicly accessible.
- Exact-local source matching and homonym disambiguation.
- Stronger claim guards for parent-level or unrelated locality evidence.
- Bounded direct/data-adapter candidates for stable public official data pages where search-assisted discovery is insufficient.
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

The new backbone should make local quantitative evidence and regional precision first-class:

```text
query obligation
  -> expected administrative level
  -> source class requirement
  -> local/statistical/fiscal/energy/trade source profile
  -> discovery or direct data path
  -> exact-local / parent / unrelated locality classification
  -> evidence quality and claim eligibility
  -> source gap or eligible evidence
```

Hard rules:

```text
Do not count provincial or unrelated locality evidence as city/county evidence unless parent fallback is explicit and claim-limited.
Do not count broad policy or news pages as statistics unless they contain an official statistical bulletin, data table, or clearly dated quantitative release.
Do not tune for one query ID; add source-family rules that generalize across region, industry, and administrative level.
```

## Phase 0: Blocker Matrix Freeze

Status: completed

Execution mode: `local_direct`

Artifacts:

- `data/tmp/source_quality_stress_eval/source_local_statistics_regional_precision_phase0/blocker_matrix.json`
- `data/tmp/source_quality_stress_eval/source_local_statistics_regional_precision_phase0/blocker_matrix.md`

Frozen blocker families:

- `local_statistics_energy_fiscal_trade`
- `exact_local_regional_precision`
- `regional_homonym_disambiguation`
- `local_project_procurement_residual`
- `sector_quantitative_supplement`

Acceptance criteria:

- Matrix records source-family blockers rather than query-specific fixes.
- Phase 7 baseline numbers are captured.
- No production code change is made in Phase 0.
- Full 50-query live remains deferred.

## Phase 1: Exact-Local And Homonym Precision

Status: completed

Execution mode: `light_subagent`

Objective:

- Prevent unrelated locality and parent-level evidence from being counted as local evidence.

Tasks:

- Add tests for wrong-locality homonyms such as a county/region name matching an unrelated district in another province.
- Strengthen exact-local classification for city, county, district, banner, and prefecture targets.
- Preserve parent fallback, but keep `parent_evidence_only=true` and `local_claim_allowed=false` unless the claim is explicitly parent-level.
- Add diagnostics that expose the expected locality and accepted evidence locality.

Acceptance criteria:

- Wrong-locality official pages are rejected or claim-limited.
- Exact-local evidence stays preferred over parent evidence.
- No public response shape changes.

## Phase 2: Local Statistics / Fiscal / Energy Backbone

Status: completed

Execution mode: `light_subagent`

Objective:

- Improve statistics, fiscal, energy, electricity, production, and regional quantitative evidence across macro/province/city/county cases.

Tasks:

- Add source-family patterns for:
  - national and provincial statistical bureaus;
  - city/county statistical bulletins;
  - finance budget and final-account reports;
  - energy bureau / power operation / electricity transaction records;
  - customs, commerce, port, and logistics statistics where relevant.
- Prioritize dated official bulletins and tables over news summaries.
- Keep data metrics separate from policy interpretation and media context.
- Add anti-overfit tests across at least two provinces and two city/county levels.

Acceptance criteria:

- `statistics` gap improves on a targeted subset without increasing false positives.
- Broad news/policy pages are not counted as strong quantitative evidence unless they include a real dated official data release.

## Phase 3: Direct Data Adapter Candidate Gate

Status: completed

Execution mode: `light_subagent`; escalate if provider abstraction changes are required.

Objective:

- Decide which recurring data sources need direct adapters or source-profile updates instead of Tavily-only discovery.

Tasks:

- Inventory stable public data endpoints found in Phase 7 roadmap.
- Classify each candidate as:
  - `search_assisted`;
  - `existing_source_profile_update`;
  - `manual_source_profile`;
  - `direct_structured_adapter_candidate`;
  - `out_of_scope`.
- Add tests for routing decisions and adapter candidacy metadata.

Acceptance criteria:

- Direct adapter candidates are documented and claim contracts remain unchanged.
- No new provider abstraction is introduced without an Architecture Gate.

## Phase 4: Sector Quantitative Supplement Control

Status: completed

Execution mode: `light_subagent`

Objective:

- Improve controlled use of association/report/industry supplemental sources without letting weak sources replace official quantitative evidence.

Tasks:

- Add source-family rules for association/report sources only as supplemental evidence.
- Require official statistics or official project/approval evidence for core quantitative claims.
- Add tests for low-altitude, commercial aerospace, NEV, energy, and real-estate macro-to-local cases.

Acceptance criteria:

- `industry_association` and `industry_report` gaps are transparent.
- Weak supplemental sources do not satisfy strong official evidence obligations.

## Phase 5: Low-Cost Targeted Gate

Status: completed_with_narrower_blocker

Execution mode: `light_subagent`

Subset candidates:

- `M02`: data-center policy-to-project and energy/statistics fanout
- `M03`: low-altitude regulatory/statistics/industry supplement
- `P04`: Anhui NEV province/city production/statistics
- `P08`: Inner Mongolia energy/statistics/project
- `K09`: Shenmu coal/coal-chemical county-level statistics/fiscal/energy
- `K12`: Ruoqiang salt-lake county-level regional precision and project data

Acceptance criteria:

- Runtime succeeds for all selected cases.
- `statistics` gap improves, or a narrower direct-data/provider blocker is recorded.
- Wrong-locality or parent-level evidence is visible and claim-limited.

## Phase 6: 12-Case Smoke Rerun

Status: completed_with_successor_blocker

Execution mode: `light_subagent`

Acceptance criteria:

- Live: `12 success / 0 runtime error`.
- DeepSeek audit: `12 success`, shape diagnostics `0`.
- `statistics <= 3`.
- `tender_or_procurement <= 5`.
- `project_list <= 4`.
- City/county source-level mismatch blockers decline versus Phase 7 baseline.
- Full 50-query live remains deferred unless Phase 7 approves it.

## Phase 5B: Official Statistics Source-Profile Remediation

Status: completed

Execution mode: `light_subagent` implemented locally under the speed-biased router.

Objective:

- Reduce the remaining `statistics` blocker before running Phase 6 by improving reusable official data source profiles and data-metrics search phrases.

Scope:

- `M02`-style compute / data-center / power-demand quantitative evidence.
- `M03`-style low-altitude economy statistical classification and official quantitative framing.
- `P08`-style Inner Mongolia energy / electricity / coal-chemical quantitative evidence.

Allowed changes:

- query decomposition phrases and include-domain selection;
- local statistics / energy source-domain patterns;
- data-metrics candidate source-role and quantitative-signal guards;
- tests and low-cost diagnostics.

Forbidden changes:

- public EvidenceBundle / citation / research response shape changes;
- direct investment advice behavior;
- query-ID-specific hardcoding;
- full 12-case or 50-query live runs before this gate records a reduced blocker.

Acceptance criteria:

- New tests prove the remediation is source-family based, not tied to a case ID.
- Compute/data-center metrics route to official energy/data/MIIT-style sources.
- Low-altitude metrics prioritize official statistical-classification evidence before generic market-size pages.
- Inner Mongolia energy metrics include energy-operation domains and phrases without treating media/context pages as statistics.
- Focused source tests and required source regressions pass.

## Phase 7: 50-Query Readiness Decision

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
- the next step is full 50-query live without readiness approval;
- the user explicitly pauses.

## Validation Loop

Focused local checks:

```powershell
python -m ruff check <changed files>
python -m py_compile <changed files>
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_source_resolver.py tests\test_sources_local_source_patterns.py tests\test_sources_lane_execution.py tests\test_sources_retrieval_plan.py
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
python data\tmp\_source_quality_llm_audit.py --run-dir <run_dir> --provider deepseek --model deepseek-v4-pro --thinking enabled --reasoning-effort max --resume
python data\tmp\_source_quality_batch_report.py --run-dir <run_dir> --print-json
```

## Cost Controls

- Do not run full 50-query live during this PLAN unless Phase 7 explicitly approves it.
- Use targeted subset gates before the 12-case smoke.
- Keep Tavily `basic` / low-cost search defaults unless a phase records a bounded exception.
- Use DeepSeek audit only after live artifacts complete.
- Use local `.env` key pool only through process environment loading; never write raw keys to tracked files or artifacts.

## Done Condition

This PLAN is done when one of these is true:

- local statistics/regional precision passes the 12-case smoke gate and Phase 7 records staged 50-query readiness; or
- the 12-case gate identifies a narrower blocker requiring provider/data-adapter/browser/OCR Architecture Gate; or
- implementation reaches an out-of-scope requirement such as OCR, browser automation, login-gated source, paid data, or protected-contract change.

## Progress

- 2026-04-30: PLAN created after `source-transaction-file-local-depth-v1` Phase 7 reduced transaction/project/file blockers but left `statistics=4` and recurring local/regional source mismatch as the next bottleneck.
- 2026-04-30: Phase 0 completed with blocker matrix artifacts:
  - `data/tmp/source_quality_stress_eval/source_local_statistics_regional_precision_phase0/blocker_matrix.json`
  - `data/tmp/source_quality_stress_eval/source_local_statistics_regional_precision_phase0/blocker_matrix.md`
- 2026-04-30: Phase 1 started with a narrow exact-local policy-direction guard:
  - Problem: exact-local queries could still accept unrelated local `.gov.cn` subdomains through the broad `gov.cn` policy lane, as seen in the K12 salt-lake case where `policy_direction` accepted unrelated `yanhu.gov.cn` results.
  - Change: `policy_direction` now rejects unrelated local government candidates when the user query has an exact-local focus, while preserving central/national policy domains and parent/province fallback.
  - Validation:
    - RED/GREEN targeted test: `pytest -q tests\test_sources_source_resolver.py::test_policy_direction_exact_local_query_rejects_unrelated_local_gov_domain` -> `1 passed` after implementation.
    - Source resolver tests -> `23 passed`.
    - Focused ruff/py_compile for `packages\sources\source_resolver.py` and `tests\test_sources_source_resolver.py` -> pass.
    - Focused source suite -> `233 passed, 1 warning`.
    - Source regression -> `27 passed`.
    - Domestic regression -> `16 passed`.
- 2026-04-30: Phase 1 completed:
  - Added anti-overfit coverage beyond K12:
    - exact-local city query for `合肥` rejects unrelated `sz.gov.cn` policy results.
    - exact-local query still accepts central `ndrc.gov.cn` policy context.
  - Final Phase 1 validation:
    - Source resolver tests -> `25 passed`.
    - Focused source suite -> `235 passed, 1 warning`.
    - Source regression -> `27 passed`.
    - Domestic regression -> `16 passed`.
- 2026-04-30: Phase 2 completed:
  - Added test-first coverage for data-metrics fallback source roles across multiple reusable patterns:
    - provincial energy / electricity operation pages from energy bureau domains;
    - provincial trade / import-export data pages from commerce department domains;
    - county-level export data pages from commerce bureau domains;
    - negative guard that commerce policy/news pages are still rejected as non-statistical evidence.
  - Changed `packages/sources/lane_execution.py` to recognize official quantitative department candidates for energy, electricity, trade/customs, port/logistics, budget execution, and import/export data semantics while preserving media/news path rejection.
  - No EvidenceBundle, citation, provider, research response, or public routing response shape changed.
  - Validation:
    - RED: `pytest -q tests\test_sources_lane_execution.py -k "provincial_energy_operation_page or provincial_trade_statistics_page or county_trade_export_statistics_page or commerce_policy_news"` -> `3 failed, 1 passed` before implementation.
    - GREEN: same targeted command -> `4 passed`.
    - Data metrics lane tests -> `20 passed`.
    - Full lane execution tests -> `70 passed`.
    - Focused ruff / py_compile for `packages\sources\lane_execution.py` and `tests\test_sources_lane_execution.py` -> pass.
    - Focused source suite -> `239 passed, 1 warning`.
    - Source regression -> `27 passed`.
    - Domestic regression -> `16 passed`.
  - Phase 2 deliberately did not run the full 50-query live set; live validation remains staged for Phase 5/6.
- 2026-04-30: Phase 3 completed:
  - Added internal candidate classification in `packages/sources/data_adapter_candidates.py` with deterministic access-method choices:
    - `search_assisted`;
    - `existing_source_profile_update`;
    - `manual_source_profile`;
    - `direct_structured_adapter_candidate`;
    - `out_of_scope`.
  - Added tests proving adapter candidacy is source-class / level based, not query-ID based.
  - Generated candidate gate artifacts from the Phase 7 baseline roadmap:
    - `data/tmp/source_quality_stress_eval/source_local_statistics_regional_precision_phase3/data_adapter_candidates.json`
    - `data/tmp/source_quality_stress_eval/source_local_statistics_regional_precision_phase3/data_adapter_candidates.md`
  - Candidate gate summary:
    - `54` candidates total;
    - `22` manual source-profile candidates;
    - `13` existing source-profile update candidates;
    - `5` direct structured adapter candidates;
    - `12` search-assisted candidates;
    - `2` out-of-scope context sources.
  - No provider abstraction or public response contract changed.
  - Validation:
    - RED: `pytest -q tests\test_sources_data_adapter_candidates.py` -> missing module before implementation.
    - GREEN: same test -> `6 passed`.
    - Focused candidate/data-metrics tests -> `26 passed`.
    - Focused ruff / py_compile for changed Phase 2/3 files -> pass.
    - Candidate artifact JSON validation -> pass.
    - Focused source suite -> `245 passed, 1 warning`.
    - Source regression -> `27 passed`.
    - Domestic regression -> `16 passed`.
- 2026-04-30: Phase 4 completed:
  - Added `sector_quantitative_supplement_control` to the internal source-family backbone contract.
  - Added `official_quantitative_obligation_satisfied(...)` so association/report/third-party context sources cannot satisfy official quantitative obligations without an official source class such as `statistics` or `trade_data`.
  - Search-assisted industry-topic evidence now carries:
    - `source_family_backbones=["sector_quantitative_supplement_control"]`;
    - `official_quantitative_obligation_satisfied=false`.
  - This keeps industry association/report evidence available as supplemental context while preventing it from replacing official statistics/project/disclosure records.
  - Validation:
    - RED: `pytest -q tests\test_sources_source_family_backbone.py` -> missing obligation helper before implementation.
    - GREEN: source-family tests -> `7 passed`.
    - RED/GREEN search-assisted industry metadata test -> `1 passed` after implementation.
    - Focused source-family/search-assisted tests -> `8 passed`.
    - Focused ruff / py_compile for changed Phase 4 files -> pass.
    - Focused source suite -> `252 passed, 1 warning`.
    - Source regression -> `27 passed`.
    - Domestic regression -> `16 passed`.
- 2026-04-30: Phase 5 completed with a narrower blocker:
  - Main 6-case live gate:
    - Case file: `data/tmp/source_quality_stress_eval/source_local_statistics_regional_precision_phase5_subset_cases.json`
    - Run: `data/tmp/source_quality_stress_eval/runs/source_local_statistics_regional_precision_v1_phase5_subset_v1`
    - Live result: `6 success`, `41` estimated Tavily credits, `40155.02 ms` average latency.
    - DeepSeek audit: `6 success`, shape diagnostics `0`, verdicts `3 fail / 3 weak_pass`, `180621` tokens.
    - Source gaps: `statistics=4`, `tender_or_procurement=5`, `industry_association=3`, `industry_report=3`.
    - Conclusion: runtime is stable, but the main 6-case audit is not strong enough to justify the 12-case smoke rerun.
  - Exact-local remediation:
    - Fixed known exact-local entities such as `神木` and `若羌` so local/data/project/official-record tasks use the existing `municipal` city/county bucket instead of `provincial`.
    - Fixed source resolver so exact-local official domains such as `sxsm.gov.cn` and `xjrq.gov.cn` are not downgraded to parent-city fallback.
    - K09/K12 local-rollout gate v2 / retry:
      - `K09`: `fallback_level=exact_park_or_county`, `parent_evidence_only=false`, `local_claim_allowed=true`.
      - `K12`: retry recovered after transient Tavily SSL EOF and reached `fallback_level=exact_park_or_county`, `parent_evidence_only=false`, `local_claim_allowed=true`.
  - Statistics remediation:
    - Province multi-city distribution data metrics now start with the province statistics agency / statistical bulletin phrase.
    - Official statistical-classification PDFs are accepted as data-metrics fallback candidates.
    - Data-metrics retry run:
      - Case file: `data/tmp/source_quality_stress_eval/source_local_statistics_regional_precision_phase5_data_metrics_retry_cases.json`
      - Run: `data/tmp/source_quality_stress_eval/runs/source_local_statistics_regional_precision_v1_phase5_data_metrics_retry_v1`
      - Result: `3 success`, `6` estimated Tavily credits, `9472.44 ms` average latency.
      - `P04` recovered `statistics` coverage through `安徽省2025年国民经济和社会发展统计公报`.
      - `M03` and `P08` still lacked usable statistics evidence under the low-cost search budget.
  - Validation:
    - Targeted RED/GREEN tests for exact-local regional buckets, exact-local resolver, statistical classification PDF, and statistics-agency phrase ordering passed.
    - Changed-file ruff / py_compile -> pass.
    - Focused source suite -> `243 passed, 1 warning`.
    - Source regression -> `27 passed`.
    - Domestic regression -> `16 passed`.
  - Phase 6 is deliberately deferred because `statistics=4` remains above the Phase 6 target `<=3`; running the full 12-case gate now would likely spend budget to confirm a known blocker.
- 2026-04-30: Phase 5B completed:
  - Changed `data_metrics` query decomposition so Inner Mongolia energy metrics prioritize energy-operation and statistics-bulletin phrases instead of generic market/media terms.
  - Updated the Inner Mongolia statistics bulletin profile to use the statistics-bulletin entry URL and real list/detail selectors.
  - Added query-aware profile list ranking so mixed statistical bulletin pages prefer broad annual economic/social statistics bulletins for energy/output/trade/fiscal-style metric queries, while retaining narrow bulletins for matching narrow queries.
  - Added detail hydration for `direct_structured_lane + data_metrics` HTML list-detail profiles so direct official data profiles are judged on detail-page text, not only list-item titles.
  - Added a generic statistics homepage guard so `stats.gov.cn/sj/`, `/sj/zxfb`, and title `数据` do not count as strong statistics evidence even if their index text contains relevant links.
  - Live validation:
    - `M02` data_metrics single-case v1: `success`, `executed_with_evidence`, statistics coverage complete, `1` Tavily fallback credit, first document `全国数据资源调查报告（2023年）`.
    - `P08` data_metrics single-case v3: `success`, `executed_with_evidence`, statistics coverage complete, `0` Tavily fallback credits, first document `内蒙古自治区2025年国民经济和社会发展统计公报`.
    - `M03/P04/P08` data_metrics retry v8: `3 success`, `2` estimated Tavily credits, average latency `5928.64 ms`; M03 uses `[PDF] 低空经济及其核心产业统计分类（试行）`, P04 uses a Wuhu statistics bulletin, P08 uses the Inner Mongolia annual statistics bulletin.
  - Local validation:
    - Focused source suite for changed Phase 5B files -> `166 passed, 1 warning`.
    - Changed-file ruff -> pass.
    - Changed-file py_compile -> pass.
    - Source regression -> `252 passed, 1 warning`.
    - Source layer regression -> `27 passed`.
    - Domestic/profile/PDF regression -> `18 passed`.
  - Phase 6 is now reopened for the 12-case smoke rerun; full 50-query live remains deferred.
- 2026-04-30: Phase 6 12-case smoke rerun completed with successor blocker:
  - Live artifact: `data/tmp/source_quality_stress_eval/runs/source_local_statistics_regional_precision_v1_phase6_12case_live_v1`.
  - Live result: `12 success`, `66` estimated Tavily credits, `60972.31 ms` average latency, `query_invalid_count=0`.
  - Batch report before audit showed no source-coverage gaps at the runtime/source-class layer.
  - DeepSeek audit result: `12 success`, shape diagnostics `0`, verdicts `8 fail / 4 weak_pass`, `364916` tokens.
  - Phase 6 thresholds:
    - `statistics <= 3`: passed at the general `statistics` gap level; residual granular gaps remain as `city_level_statistics=1` and `county_statistics=1`.
    - `project_list <= 4`: passed with `project_list=2`.
    - `tender_or_procurement <= 5`: failed with `tender_or_procurement=7`.
  - Main successor blockers:
    - `tender_or_procurement=7`: affected `C07`, `K07`, `K09`, `K12`, `P04`, `P08`, `P10`.
    - `regulatory_record=4`: affected `C01`, `K07`, `K09`, `M03`.
    - `environmental_or_land_record=2`: affected `C01`, `K07`.
    - city/county source-level mismatch remains material for `C01`, `C07`, `C09`, `K07`, `K09`, `K12`, `M02`, `M03`, `M06`, `P04`, `P08`, `P10`.
  - Phase 7 readiness decision: not ready for full 50-query live. The next PLAN should target local procurement / public-resource, regulatory-record, environmental/land, and city/county project-record depth rather than continuing statistics remediation.

## Risks And Rollback

Risks:

- Overfitting exact source domains to the 12-case smoke set.
- Weakening statistics gates by allowing broad policy/news pages to count as data.
- Expanding Tavily budget instead of improving source precision.
- Treating parent-level data as exact-local data.
- Introducing direct adapters before the source-profile path is proven insufficient.

Rollback:

- Revert only files changed under this PLAN.
- Keep `source_transaction_file_local_depth_v1_phase7_live_v1` as the comparison baseline.
- Disable new local statistics or regional precision rules if they increase false positives or cost without improving evidence sufficiency.

## Next Action

Create a successor PLAN focused on local procurement / public-resource, regulatory-record, environmental/land, and city/county project-record depth.

Do not run the full 50-query live evaluation yet.
