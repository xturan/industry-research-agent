# Source Evidence Sufficiency Remediation v2

Status: completed_with_successor_blocker

Created: 2026-04-29

Primary active PLAN: no

Supersedes active execution of:

- `.agent/PLANS/source-local-evidence-backbone-remediation-v1.md`

## Objective

Improve the reusable source-routing, discovery, extraction, and evidence-quality paradigm so the 12-case source-quality gate can pass without overfitting individual queries.

The immediate trigger is the successor blocker from `source-local-evidence-backbone-remediation-v1` Phase 5:

- routing gate: `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`
- live gate: `12 success / 0 runtime error`
- DeepSeek audit: `12 success`, `0` shape diagnostics, `1 blocker / 11 fail`
- estimated Tavily credits: `78`, exactly at baseline
- average latency: `36040.35 ms`

The quality failure is no longer a runtime or budget problem. It is an evidence-sufficiency and source-class coverage problem.

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

Primary Phase 5 artifacts:

- `data/tmp/source_quality_stress_eval/runs/local_backbone_phase5_routing_v1`
- `data/tmp/source_quality_stress_eval/runs/local_backbone_phase5_live_v1/live_summary.json`
- `data/tmp/source_quality_stress_eval/runs/local_backbone_phase5_live_v1/llm_audit_summary.json`
- `data/tmp/source_quality_stress_eval/runs/local_backbone_phase5_live_v1/batch_eval.json`
- `data/tmp/source_quality_stress_eval/runs/local_backbone_phase5_live_v1/source_roadmap.json`
- `data/tmp/source_quality_stress_eval/runs/local_backbone_phase5_budget_v1/budget_diagnostics.json`
- `data/tmp/source_quality_stress_eval/local_evidence_backbone_phase5/backbone_matrix.json`

Baseline failure counts:

| Metric | Result |
|---|---:|
| Live runtime | `12 success / 0 runtime error` |
| Audit transport/schema | `12 success`, shape diagnostics `0` |
| Audit verdicts | `1 blocker / 11 fail / 0 weak_pass / 0 pass` |
| Tavily credits | `78` |
| Budget delta vs baseline | `0` |

Main source-class gaps:

| Source class | Missing count | Target | Affected cases |
|---|---:|---:|---|
| `local_government` | `5` | improve toward `<=3` | `C01`, `C09`, `K07`, `K09`, `K12` |
| `project_list` | `5` | `<=5`, improve toward `<=4` | `C01`, `K07`, `K12`, `M03`, `P08` |
| `statistics` | `4` | `<=3` | `K07`, `K09`, `K12`, `M02` |
| `environmental_or_land_record` | `2` | `<=2` | `C01`, `K07` |
| `industry_report` / `market_price_data` | `2+` | improve | `C07`, `P04`, `P10` |

Known audit blocker:

- `C07`: photovoltaic supply-chain risk lacks industry association and market-price evidence. This should be treated as an industry/market specialist source-class failure, not as a Changzhou-only fix.

## Design Direction

Move from "we found some documents" to "we found enough strong evidence by required source class."

```text
Query decomposition
  -> evidence obligations by source class
  -> source-class targeted lane planner
       -> local government / department
       -> project and public-resource records
       -> statistics / fiscal / quantitative evidence
       -> industry association / market price evidence
       -> official records and binary attachments
  -> discovery and extraction
  -> source-class coverage diagnostics
  -> evidence sufficiency gate
  -> 12-case audit
```

The 12-case smoke set and future 50-query set are regression instruments. Fixes must generalize to a source class, administrative level, extraction failure class, or evidence obligation.

## Scope

In scope:

- Source-class coverage diagnostics and evidence visibility under existing metadata.
- Reusable local government/statistics/project/official-record source profile updates.
- Search-assisted source-class lane improvements before new heavy adapters.
- Static binary/download handling for stable public documents where compatible with existing rules.
- Industry/market specialist discovery for source classes such as association reports, prices, capacity, and market data.
- 12-case live and DeepSeek audit validation before any 50-query expansion.

Out of scope unless explicitly reopened:

- Browser automation.
- OCR.
- Login, paid, or private sources.
- Public EvidenceBundle/citation/research response schema changes.
- Query-specific hardcoding.
- Full 50-query live run before the 12-case gate materially improves.

## Agent Execution Contract

Project contract:

- PLAN is the execution contract.
- STATUS is the handoff checkpoint.
- The current session may execute locally. Use subagents only when explicitly authorized by the user/runtime policy.
- If subagents are used later, bind them as:
  - `invest_project_director`: refine validation scope and phase gates.
  - `invest_feature_programmer`: implement source/eval/script changes in narrow write scopes.
  - `invest_agent_architecture_builder`: review protected-contract or adapter-boundary risk.
  - `invest_code_quality_checker`: ruff, compile, focused pytest.
  - `invest_functional_validator`: routing/live/audit gate validation.
  - `invest_project_summarizer`: final PLAN completion summary only after done condition.

## Phases

### Phase 0: Phase 5 Failure Synthesis And Gate Freeze

Objective:

- Convert the Phase 5 failed gate into a precise implementation queue and freeze acceptance thresholds before code changes.

Tasks:

- Reuse `batch_eval.json`, `source_roadmap.json`, `budget_diagnostics.json`, and `backbone_matrix.json`.
- Produce a concise failure synthesis grouped by source-class backbone.
- Freeze the next 12-case acceptance thresholds.
- Confirm that the next work is not a budget problem and should not run 50 live cases yet.

Acceptance criteria:

- Successor blocker is stated in terms of source classes, not case-specific patches.
- Phase 5 thresholds are visible in the PLAN.
- No production code changes are required in Phase 0.

Validation:

```powershell
python data\tmp\_source_local_evidence_backbone_matrix.py --run-dir data\tmp\source_quality_stress_eval\runs\local_backbone_phase5_live_v1 --output-dir data\tmp\source_quality_stress_eval\source_evidence_sufficiency_v2_phase0 --credit-baseline 78 --print-json
```

### Phase 1: Source-Class Coverage Visibility

Objective:

- Make accepted documents and task metadata clearly expose which source classes they satisfy, so the audit can distinguish "documents exist" from "required strong evidence exists."

Tasks:

- Add or improve metadata-only diagnostics for:
  - expected source classes per task
  - covered source classes per accepted document
  - missing source classes per lane
  - weak-document rejection reasons by source class
- Keep public EvidenceBundle/citation/research response schemas unchanged.
- Add tests proving source-class coverage diagnostics do not drift public contracts.

Acceptance criteria:

- Per-query artifacts can show covered/missing source classes without relying on LLM inference from raw text alone.
- No protected public schema drift.

### Phase 2: Local Government And Statistics/Fiscal Backbone

Objective:

- Reduce local-government and statistics gaps through reusable administrative-level source patterns.

Tasks:

- Improve exact-local and parent/child source classification for city/county statistics and fiscal reports.
- Add or refine source patterns for local government, statistics bureau, finance bureau, and official annual/statistical bulletins.
- Prefer exact-local official domains before parent fallback.
- Keep query examples as regression cases, not hardcoded routing.

Acceptance criteria:

- `statistics` missing count falls from `4` to `<=3`.
- `local_government` missing count improves toward `<=3`.
- Runtime remains `12 success / 0 runtime error`.

### Phase 3: Project/Public-Resource And Official-Record Backbone

Objective:

- Improve project-list and project-validity evidence without unbounded search fanout.

Tasks:

- Improve public-resource/procurement/project-list source-class targeting.
- Add static handling for common public binary/download pages where current Crawl4AI reports "download is starting" or minimal content.
- Preserve explicit evidence gaps for unrecoverable downloads.
- Keep project and official-record lanes budget-capped.

Acceptance criteria:

- `project_list` remains `<=5` and improves toward `<=4`.
- `environmental_or_land_record` remains `<=2`.
- Budget diagnostics show no unjustified credit expansion above `78`, or record the tradeoff if exceeded.

### Phase 4: Industry/Market Specialist Backbone

Objective:

- Handle C07-style industry risk questions through reusable industry association, market price, capacity, and company-disclosure source classes.

Tasks:

- Add source-class targeting for industry association and market-price evidence.
- Avoid paid/private data dependencies; use public association, official, company disclosure, and public market context first.
- Add routing tests for industry risk/capacity/price-cycle questions.

Acceptance criteria:

- C07 blocker is removed or converted into an explicit non-production-data limitation.
- `industry_report` / `market_price_data` gaps are visible and reduced.

### Phase 5: 12-Case Evidence Sufficiency Gate

Objective:

- Re-run the same 12-case gate after remediation.

Acceptance criteria:

- Live gate: `12 success / 0 runtime error`.
- Audit transport/schema: `12 success`, shape diagnostics `0`.
- Audit blockers: `0`.
- At least `6/12` cases are `weak_pass` or `pass`, or fail count falls to `<=6`.
- `project_list <= 5`, `statistics <= 3`, `environmental_or_land_record <= 2`.
- Estimated Tavily credits are recorded and explained.

### Phase 6: Staged 50-Query Expansion

Objective:

- Expand only after the 12-case evidence-sufficiency gate materially improves.

Tasks:

- Run 50-query routing offline.
- Run staged live subsets by macro/province/city/county.
- Run full live only if cost and latency are acceptable.
- Convert new failures into generalized source-backbone backlog.

Acceptance criteria:

- Full 50-query live is either completed with cost/latency/audit summary or explicitly deferred with evidence.
- New failures are classified by source-class backbone.

## Continue Rule

After each milestone, continue automatically to the next milestone when:

- acceptance criteria are met
- required validation passes
- no credential, dependency, permission, or human-review blocker exists
- no high-risk contract change is being made without explicit PLAN authorization

Do not treat a milestone summary as a default stop point.

## Stop Conditions

Stop and request guidance if:

- a protected contract change is required
- live credentials are unavailable
- a source requires browser automation, OCR, login, or paid access
- validation fails and the repair path is unclear or high risk
- external API behavior prevents safe completion
- the user explicitly pauses

## Done Condition

This PLAN is complete when:

- Phase 5 passes, or records a narrower successor blocker with evidence.
- Phase 6 is completed or explicitly deferred with cost/risk evidence.
- `.agent/STATUS.md` and this PLAN contain final progress, validation, risks, and next action.
- Final handoff includes what changed, implemented capability, concrete test cases, two before/after examples, files changed, validation, and remaining TODOs.

## Risks And Rollback

Risks:

- DeepSeek audit can be stricter than the current artifact shape; use deterministic source-class metrics alongside audit verdicts.
- Local official sites may require source-profile treatment before direct adapters.
- Industry/market evidence may require sources with limited public availability.
- More recall can raise Tavily credits unless budget gates remain active.
- Dirty worktree is broad; scope must be reviewed before production implementation.

Rollback:

- Disable new source-profile rules or diagnostics while preserving existing lane execution.
- Revert only files changed by this PLAN.
- Keep `local_backbone_phase5_live_v1` as the comparison baseline.

## Progress

- 2026-04-29: PLAN created from `source-local-evidence-backbone-remediation-v1` Phase 5 successor blocker. No production code changed in the planning step.
- 2026-04-29: Phase 0 completed.
  - Generated frozen failure synthesis artifact:
    - `data/tmp/source_quality_stress_eval/source_evidence_sufficiency_v2_phase0/backbone_matrix.json`
    - `data/tmp/source_quality_stress_eval/source_evidence_sufficiency_v2_phase0/backbone_matrix.md`
  - Confirmed the successor blocker is not runtime or budget:
    - live runtime: `12 success / 0 runtime error`
    - budget: `78` credits, credit delta `0`
    - audit schema: `0` shape diagnostics
  - Frozen evidence-sufficiency gaps:
    - `local_government=5`
    - `project_list=5`
    - `statistics=4`
    - `environmental_or_land_record=2`
    - `industry_report/market_price_data` remain visible due C07/P04/P10-style evidence needs
  - Phase 0 decision:
    - Do not run full 50-query live evaluation yet.
    - Start Phase 1 with source-class coverage visibility before adding broader source adapters.
- 2026-04-29: Phase 1 completed with metadata-only eval artifact visibility.
  - RED:
    - `pytest -q tests\test_source_quality_live_inspection.py` first failed because `_source_class_coverage()` did not exist.
  - Implementation:
    - `data/tmp/_source_quality_live_inspection.py` now computes `metadata.source_class_coverage` for each executed task.
    - Coverage diagnostics include `expected_source_classes`, `covered_source_classes`, `missing_source_classes`, and `coverage_complete`.
    - Document snapshots now preserve optional `source_class`, `source_classes`, `source_type`, and `evidence_quality` metadata for audit visibility.
    - This is eval artifact metadata only; public EvidenceBundle, citation, research response, provider, and task/run contracts were not changed.
  - Validation:
    - `pytest -q tests\test_source_quality_live_inspection.py` -> `2 passed, 1 warning`.
    - `python -m ruff check data\tmp\_source_quality_live_inspection.py tests\test_source_quality_live_inspection.py data\tmp\_source_quality_budget_diagnostics.py tests\test_source_quality_budget_diagnostics.py` -> pass.
    - `python -m py_compile data\tmp\_source_quality_live_inspection.py tests\test_source_quality_live_inspection.py data\tmp\_source_quality_budget_diagnostics.py tests\test_source_quality_budget_diagnostics.py` -> pass.
    - focused eval harness tests -> `4 passed, 1 warning`.
    - source regression -> `27 passed`.
    - domestic regression -> `16 passed`.
  - Low-cost live smoke:
    - Artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase1_visibility_smoke_v1`
    - Result: `2 success`, estimated Tavily credits `3`, average latency `8139.45 ms`, `query_invalid_count=0`.
    - C01 and K09 `data_metrics` tasks now show `statistics` as expected and covered with no missing source class in task metadata.
  - Phase 1 decision:
    - Per-query artifacts now expose source-class coverage without requiring LLM inference from raw text alone.
    - Move to Phase 2 local government and statistics/fiscal backbone remediation.
- 2026-04-29: Phase 2 slice 1 completed with local-government visibility and exact-local statistics/fiscal domain ordering.
  - RED:
    - `pytest -q tests\test_sources_search_assisted_domestic.py -k "local_rollout_generic_first_wave"` first failed because accepted `local_rollout` documents did not carry `source_class` / `source_classes` metadata.
    - `pytest -q tests\test_sources_query_decomposition.py -k "county_park_cluster_query_keeps_direct_lanes_when_records_requested"` first failed because domain repair sorted domains alphabetically and because `data_metrics` national defaults could appear before exact-local statistics/fiscal domains.
  - Implementation:
    - `SearchAssistedDomesticOrchestrator` now annotates accepted search-assisted documents and normalized documents with metadata-only source-class coverage for `policy_direction`, `local_rollout`, and `industry_topic`.
    - `repair_domains()` now preserves original priority order while deduping valid domains.
    - `data_metrics` source routing now prioritizes exact-local entity domains and local statistics/fiscal backbone domains before region-generic and national defaults.
    - No public EvidenceBundle, citation, research response, provider, or task/run contract shape changed.
  - Validation:
    - `pytest -q tests\test_sources_query_decomposition.py` -> `46 passed`.
    - `pytest -q tests\test_sources_search_assisted_domestic.py` -> `23 passed`.
    - `pytest -q tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_retrieval_plan.py` -> `76 passed, 1 warning`.
    - source regression -> `27 passed`.
    - domestic regression -> `16 passed`.
    - focused ruff/py_compile for changed production/test files -> pass.
    - repo-wide `python -m ruff check .` still fails on known historical `data/tmp` scratch/demo lint debt (`47` errors), not on files touched in this slice.
  - Low-cost live visibility smoke:
    - Artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase2_local_rollout_visibility_smoke_v1`
    - Result: `2 success`, estimated Tavily credits `2`, average latency `5431.21 ms`, `query_invalid_count=0`.
    - `C01` and `K09` `local_rollout` task artifacts now show `expected_source_classes=["local_government","official_policy"]`, covered classes equal expected classes, and no missing source classes.
    - `C01` also exposed a structured Crawl4AI anti-bot/minimal-text extraction error while preserving partial-failure behavior and accepted metadata visibility.
  - Phase 2 decision:
    - This slice improves artifact-visible local-government coverage and exact-local statistics/fiscal routing priority.
    - Phase 2 is not complete yet; missing-count acceptance still requires a broader Phase 2 live/audit or 12-case gate.
- 2026-04-29: Phase 2 slice 2 completed with direct-lane source-class promotion and stricter local-region hierarchy diagnostics.
  - RED:
    - `data_metrics` fallback tests first failed because accepted direct/fallback documents carried `evidence_quality.source_class="statistics"` but did not expose `metadata.source_class` / `metadata.source_classes`.
    - `classify_local_region_match()` first misclassified a parent-government domain page that merely mentioned the exact local region as `exact_local`.
  - Implementation:
    - `_attach_evidence_quality()` now promotes `evidence_quality.source_class` into common document metadata fields `source_class` and `source_classes` for direct/fallback documents.
    - Parent-domain pages that mention an expected local region are no longer upgraded to `exact_local`; they remain `parent_local` unless the domain/source itself is exact local.
    - `data_metrics` search phrases now use a balanced ordering:
      - first: exact-local statistics agency phrase, e.g. `神木市统计局 煤化工 统计公报`
      - second: broader regional fiscal/funding fallback, e.g. `神木 煤化工 财政资金 补贴`
      - third: exact-local finance agency phrase, e.g. `神木市财政局 煤化工 财政资金 补贴`
    - This keeps exact-local preference without losing recall under the two-credit fallback budget.
  - Validation:
    - RED/GREEN focused tests -> pass.
    - `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_retrieval_plan.py` -> `146 passed, 1 warning`.
    - source regression -> `27 passed`.
    - domestic regression -> `16 passed`.
    - focused ruff/py_compile for changed production/test files -> pass.
    - repo-wide `python -m ruff check .` still fails on known historical `data/tmp` scratch/demo lint debt (`47` errors), not on files touched in this slice.
  - Low-cost live statistics/fiscal smoke:
    - Final artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase2_data_metrics_visibility_smoke_v5`
    - Result: `2 success`, estimated Tavily credits `3`, average latency `6791.12 ms`, `query_invalid_count=0`.
    - `C01` `data_metrics`: covered `statistics`, document metadata has `source_class=["statistics"]`, local-region match is `child_local` from an Anhui parent-domain statistical bulletin.
    - `K09` `data_metrics`: covered `statistics`, document metadata has `source_class=["statistics"]`, local-region match is `parent_local` from a Shaanxi parent-domain government work report.
  - Phase 2 decision:
    - Phase 2 implementation gate is complete: local-government and statistics/fiscal coverage are now visible in artifacts, and parent/exact/child hierarchy is more transparent.
    - The full missing-count acceptance (`statistics <= 3`, `local_government` improves toward `<=3`) remains deferred to the Phase 5 12-case evidence-sufficiency gate because running a full 12-case audit after each backbone slice would over-spend credits and overfit intermediate cases.
    - Move to Phase 3 project/public-resource and official-record backbone remediation.
- 2026-04-29: Phase 3 completed at implementation-gate level with project/public-resource and official-record multi-source-class visibility.
  - RED / diagnosis:
    - Official-record parent-department candidates could be rejected when the land/environment signal appeared in the official department search snippet rather than title/URL.
    - A proposed parent natural-resources regression initially used a `/dxal/` typical-case URL and was correctly rejected as `generic_official_record_case_page`; the test was corrected to a non-case detail path so the existing typical-case protection remains intact.
    - Project/public-resource fallback documents exposed only `project_list`, even when accepted pages were tender/procurement records.
    - Official-record fallback documents exposed only `environmental_or_land_record`, even when accepted pages were approval/filing/regulatory records.
  - Implementation:
    - Added conservative official-record search-signal handling: only ecology/environment or natural-resources department domains may use search snippets/content to satisfy land/environment record signals. Broad `gov.cn` and unrelated local domains remain protected.
    - Kept `/dxal/` / typical-case page rejection as a weak-evidence guardrail.
    - Added multi-source-class evidence metadata for direct/fallback documents:
      - project evidence can now expose `project_list` plus `tender_or_procurement`.
      - official-record evidence can now expose `environmental_or_land_record` plus `regulatory_record`.
    - No public EvidenceBundle, citation, research response, provider, or task/run contract shape changed.
  - Validation:
    - Official-record RED/GREEN and guardrail tests -> `4 passed, 1 warning`.
    - Project/official-record multi-source-class RED/GREEN tests -> `4 passed, 1 warning`.
    - `pytest -q tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_retrieval_plan.py` -> `79 passed, 1 warning`.
    - `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py` -> `70 passed`.
    - focused ruff/py_compile for changed production/test files -> pass.
    - source regression -> `27 passed`.
    - domestic regression -> `16 passed`.
    - repo-wide `python -m ruff check .` still fails on known historical `data/tmp` scratch/demo lint debt (`47` errors), not on files touched in this slice.
  - Low-cost live project/public-resource smoke:
    - Artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase3_project_smoke_v2`
    - Result: `2 success`, estimated Tavily credits `4`, average latency `17751.6 ms`, `query_invalid_count=0`.
    - `K09` `project_transaction`: coverage is now complete for `project_list` and `tender_or_procurement`; accepted document metadata has `source_classes=["project_list","tender_or_procurement"]`.
    - `C01` `project_transaction`: still covers `project_list` but not `tender_or_procurement`; this remains a source-availability/search-recall gap, not a metadata-shape bug.
  - Low-cost live official-record smoke:
    - Artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase3_official_record_smoke_v3`
    - Result: `2 success`, estimated Tavily credits `2`, average latency `3247.3 ms`, `query_invalid_count=0`.
    - `C01` `official_record`: coverage is now complete for `environmental_or_land_record` and `regulatory_record`; accepted 安徽生态环境厅 document metadata has `source_classes=["environmental_or_land_record","regulatory_record"]`.
    - `K09` `official_record`: still has no usable document because the selected official PDF produced `zero_text`; the failure remains structured as `pdf_or_download` / `zero_text`.
  - Phase 3 decision:
    - Phase 3 implementation gate is complete: source-class coverage is more faithful for project/public-resource and official-record evidence, with low-cost live improvement on K09 project and C01 official-record cases.
    - Full cross-case acceptance remains deferred to Phase 5 after Phase 4 industry/market specialist remediation.
    - Move to Phase 4 industry/market specialist backbone remediation.
- 2026-04-29: Phase 4 completed at implementation-gate level with generalized industry/market specialist remediation.
  - Diagnosis:
    - Phase 4 smoke v1/v2 showed `industry_topic` tasks had either empty/insufficient theme-specific domains or accepted none because newer public supplemental domains were still classified as `other`, producing `source_role_mismatch`.
    - After splitting C07-style multi-industry phrases, resolver theme matching initially leaked the full task phrase set across rounds, causing a current "动力电池" round to be rejected by a later "光伏" theme constraint.
  - Implementation:
    - Extended theme-specific public supplemental domain selection for industry/market questions:
      - automotive / NEV / battery: `caam.org.cn`, `battery100.org`, `ccpit.org`
      - photovoltaic: `chinapv.org.cn`, `ccpit.org`
      - Hainan free-trade-port investment context: `hiipb.com`, `hiac.org.cn`
    - `source_resolver.SUPPLEMENTAL_DOMAINS` now reuses `SUPPLEMENTAL_ALLOWED_DOMAINS` from query decomposition, preventing future allowlist drift between routing and compatibility gates.
    - C07-style capacity/price industry phrases now split mixed subindustries into separate search phrases and add a recency-oriented `最新` token:
      - `动力电池 产能 价格 最新 行业协会`
      - `光伏 产能 价格 最新 行业协会`
    - `industry_topic` theme matching now scopes theme inference to the current Tavily query phrase, avoiding cross-round / cross-subindustry `domain_topic_mismatch`.
    - No public EvidenceBundle, citation, research response, provider, or task/run contract shape changed.
  - Validation:
    - `pytest -q tests\test_sources_source_resolver.py tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py` -> `92 passed`.
    - `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_retrieval_plan.py` -> `171 passed, 1 warning`.
    - source regression -> `27 passed`.
    - domestic regression -> `16 passed`.
    - focused ruff/py_compile for changed production/test files -> pass.
  - Low-cost live industry/market smoke:
    - Final artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase4_industry_market_smoke_v6`
    - Result: `3 success`, estimated Tavily credits `3`, average latency `44585.64 ms`, `query_invalid_count=0`.
    - `C07`, `P04`, and `P10` `industry_topic` task artifacts now show complete `industry_report` / `industry_association` source-class coverage.
    - C07 now accepts public supplemental industry candidates after the domain-role and per-round theme-scope fixes.
  - Residual risks:
    - C07 public industry discovery can still return stale/weak CAAM/CCPIT material under a one-credit first-round budget; this is now visible in extracted content and should be judged in Phase 5 rather than patched with query-specific rules.
    - One accepted CAAM homepage candidate in the v6 smoke produced a structured Crawl4AI `timeout` extraction failure; partial-failure behavior remained visible in task errors and extraction metadata.
  - Phase 4 decision:
    - Industry/market source-class coverage is now visible and reduced at the implementation-gate level.
    - Remaining quality questions are source freshness/relevance questions for the Phase 5 12-case evidence-sufficiency audit.
    - Move to Phase 5 12-case evidence-sufficiency gate.
- 2026-04-29: Phase 5 completed with successor blocker; Phase 6 50-query expansion deferred.
  - Live extraction gate:
    - Artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase5_live_v1`
    - Result: `12 success / 0 runtime error`
    - Estimated Tavily credits: `79`
    - Average latency: `43861.95 ms`
    - Query invalid count: `0`
  - Batch report:
    - `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase5_live_v1/batch_eval.json`
    - `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase5_live_v1/source_roadmap.json`
  - DeepSeek audit:
    - First run failed with `12` authentication errors because a manually loaded `.env` value preserved a trailing quote in `DEEPSEEK_API_KEY`.
    - Rerun after clearing the inherited process variable let the audit script load `.env` with quote stripping.
    - Final status: `12 success`, shape diagnostics `0`, total tokens `298099`.
    - Final verdicts: `11 fail / 1 weak_pass / 0 pass`, audit blockers `0`.
  - Acceptance result:
    - Failed `weak_pass/pass >= 6` target: actual `1/12`.
    - Failed `fail <= 6` target: actual `11`.
    - Failed `project_list <= 5` target: actual `7`.
    - Passed `statistics <= 3` target: actual `2`.
    - Passed `environmental_or_land_record <= 2` target: actual `2`.
    - Runtime, audit transport, audit shape, and credential gates passed after remediation.
  - Generalized successor blocker:
    - Source-class metadata visibility improved, but DeepSeek still rejects evidence quality.
    - The next work must focus on strong evidence quality rather than labels:
      - project/public-resource and tender/procurement evidence
      - city/county local-government source precision
      - official policy / regulatory record recall for macro project claims
      - PDF/download extraction and content-quality handling
      - audit-visible evidence packaging
    - Do not run the full 50-query live set yet.
  - Successor PLAN:
    - `.agent/PLANS/source-evidence-quality-gate-remediation-v1.md`

## Current Phase

Completed with successor blocker. Phase 6 50-query expansion is explicitly deferred.

## Next Action

Use `.agent/PLANS/source-evidence-quality-gate-remediation-v1.md` as the next active execution plan.
