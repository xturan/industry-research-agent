# Source Generalized Evidence Remediation v1

Status: blocked_at_phase5_gate

Created: 2026-04-29

Primary active PLAN: yes

Supersedes active execution of:

- `.agent/PLANS/source-strong-evidence-adapter-remediation-v1.md`

## Objective

Improve the general source-routing, discovery, extraction, and evidence-quality paradigm exposed by the 12-case strong-evidence gate.

This PLAN exists because `source-strong-evidence-adapter-remediation-v1` improved runtime and several direct evidence backbones, but its Phase 7 DeepSeek gate still failed:

- live gate: `12 success / 0 runtime error`
- audit schema: `12 success / 0 invalid_json`
- audit verdicts: `10 fail / 1 weak_pass / 1 blocker`
- estimated Tavily credits: `69`
- average latency: `21752.27 ms`

The goal is not to overfit the 12 smoke cases. The 12-case set and later 50-query set are regression instruments. Every remediation must generalize to a reusable source class, routing lane, source profile pattern, extraction rule, or evidence sufficiency rule.

## Task Classification

- Primary area: `source_layer`
- Secondary areas: `domestic_source_collectors`, `eval_policy_ops`, `provider_layer`
- Later possible impact: `research_workflow` only if evidence visibility needs a compatibility-safe metadata bridge

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

Any protected-contract change requires an explicit Architecture Gate section update before implementation.

## Inputs And Baseline

Authoritative Phase 7 artifacts:

- `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_live_final_v1/live_summary.json`
- `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_live_final_v1/llm_audit_summary.json`
- `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_live_final_v1/batch_eval.json`
- `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_live_final_v1/source_roadmap.json`
- `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_live_final_v1/llm_audit/*.json`

Phase 7 baseline:

| Metric | Result |
|---|---:|
| Live status | `12 success / 0 runtime error` |
| Audit status | `12 success / 0 invalid_json` |
| Audit verdicts | `10 fail / 1 weak_pass / 1 blocker` |
| Total DeepSeek tokens | `176844` |
| Tavily credits | `69` |
| Average latency | `21752.27 ms` |

Main missing source classes from the latest batch report:

| Source class | Missing count | Affected cases |
|---|---:|---|
| `project_list` | `7` | `C01`, `K07`, `K09`, `K12`, `P04`, `P08`, `P10` |
| `statistics` | `7` | `C01`, `K09`, `K12`, `M02`, `P04`, `P08`, `P10` |
| `environmental_or_land_record` | `5` | `C01`, `K07`, `K09`, `K12`, `P08` |
| `official_policy` | `2` | `M02`, `P04` |

Other repeated gaps:

- industry association / market price / capacity data for sector-cycle questions
- aviation regulator and CAAC-style sources for low-altitude economy
- local fund, university, research-center, and launch/project lanes for commercial aerospace
- county-level statistics, land, EIA, fiscal, and public-resource records
- PDF/download and anti-bot extraction reliability
- evaluator/source-roadmap normalization for non-object LLM recommendations

## Diagnosis

1. The system now executes more lanes, but execution is not enough. Some accepted evidence still does not satisfy the source class, administrative level, sector specificity, or proof strength required by the query.
2. `project_transaction`, `data_metrics`, and `official_record` lanes still behave too much like generic search fallbacks. They need stronger source-class contracts and local source templates.
3. Query decomposition is still under-specified for certain industry research patterns: regulator lane, industry association lane, local fund lane, university/research lane, market-price lane, and county fiscal/statistics lane.
4. Local coverage remains the weakest layer. City/county claims need explicit local government, statistics, project, public-resource, land/EIA, and fiscal evidence or a transparent gap.
5. DeepSeek audit output is useful but noisy. Non-object recommendations must be normalized into typed source/profile/adapter/routing items before driving production changes.

## Architecture Direction

Move from "tasks execute" to "coverage lanes prove the query".

```text
User query
  -> query decomposition
  -> coverage lane planner
       -> required source classes by query intent and administrative level
       -> optional supplemental lanes
       -> budget policy
  -> source router
       -> direct structured adapters
       -> search-assisted source profiles
       -> local fallback profiles
  -> discovery/fetch/extraction
  -> source-class and relevance scoring
  -> lane-level evidence sufficiency decision
  -> existing evidence bundle / trace metadata
  -> audit and regression gate
```

Coverage lane examples:

| Coverage lane | Purpose | Strong source preference |
|---|---|---|
| `official_policy` | policy direction and implementation rules | central/province/city/county official files |
| `local_rollout` | local implementation and pilots | local government, DRC, MIIT, data/industry bureaus |
| `project_transaction` | project reality | public-resource trading, procurement, tenders, approvals |
| `data_metrics` | quantitative proof | statistics bureau, customs, industry association, fiscal/energy data |
| `enterprise_disclosure` | company proof | CNINFO/SSE/SZSE/BSE reports and announcements |
| `official_record` | land/EIA/regulatory proof | ecology/environment, natural resources, approval/permit records |
| `industry_association` | sector capacity, price, shipment, whitepaper context | official/recognized associations |
| `regulator_specialist` | sector regulator constraints | CAAC, NMPA, NEA, MIIT topic regulators |
| `local_capital_research` | funds, university, research-center, park platform signals | government fund, university/park/project announcements |

## Scope

In scope:

- Phase 7 audit normalization into a deterministic failure taxonomy.
- Query decomposition and coverage lane improvements when they generalize beyond one case.
- Source profile/domain pattern improvements by source class and administrative level.
- Evidence relevance and sufficiency scoring in existing metadata/trace structures.
- PDF/download/anti-bot failure classification and static extraction improvements if compatible with current source architecture.
- Focused regression tests and live gates on the 12-case set before 50-query expansion.

Out of scope unless explicitly reopened:

- Full 50-case live run before the 12-case gate improves.
- Public EvidenceBundle / citation / research response schema changes.
- Browser automation, OCR, login-gated sources, or paid sources.
- Direct securities investment advice.
- Case-id-specific hardcoding.

## Generalization Guardrail

Do not implement a fix that only works for one query, one company, one city, or one domain unless the PLAN records why it represents a reusable broader class.

Allowed examples:

- Add a county-level official-record profile pattern used by multiple county cases.
- Add regulator-specialist decomposition for low-altitude economy, pharmaceuticals, energy, or similar regulated sectors.
- Add source-class scoring that rejects any document missing target region and industry signals.
- Add public-resource/project fallback templates by administrative level.

Disallowed examples:

- Special-case `M03` to always add a specific URL.
- Hardcode a single company solely because it appears in one smoke case.
- Raise a case score by weakening evidence requirements.

## Agent Execution Contract

STATUS is the current checkpoint. This PLAN is the execution contract. Agents are role-bound executors and validators.

Default execution flow when implementation is triggered:

1. `invest_project_director`
   - Confirm current phase.
   - Refine validation gates from this PLAN.
   - Stop if a protected contract change is required.
2. Group 2 workers
   - `invest_agent_architecture_builder`: Architecture Gate, coverage lane design, protected-contract impact.
   - `invest_feature_programmer`: scripts, source profiles, routing/decomposition changes, tests.
3. Group 3 validators
   - `invest_code_quality_checker`: ruff, compile, focused pytest, scope checks.
   - `invest_functional_validator`: artifact/live validation against 12-case and staged 50-case gates.
4. `invest_project_summarizer`
   - Only after the done condition is reached.

Workers must not reinterpret the goal as "make the 12 cases pass at any cost". The goal is reusable evidence-quality improvement.

## Milestones

### Phase 0: Failure Taxonomy And Successor Gate Freeze

Objective:

- Convert Phase 7 outputs into a deterministic failure taxonomy and freeze the next acceptance gate.

Tasks:

- Load `batch_eval.json`, `source_roadmap.json`, and per-case `llm_audit/*.json`.
- Produce a typed taxonomy of:
  - missing source class
  - routing/decomposition gap
  - source profile gap
  - extraction gap
  - evidence relevance/scoring gap
  - evaluator/harness gap
- Identify which failures are general enough to implement and which remain case caveats.
- Freeze the next 12-case gate and cost ceiling.

Acceptance criteria:

- A Phase 0 taxonomy artifact exists under `data/tmp/source_quality_stress_eval/generalized_remediation_phase0/`.
- The taxonomy maps every failed/weak case to at least one general failure family.
- The PLAN records which families proceed to implementation.
- No production source code changes are required in Phase 0.

Validation:

```powershell
Test-Path data\tmp\source_quality_stress_eval\runs\strong_evidence_phase6_live_final_v1\batch_eval.json
Test-Path data\tmp\source_quality_stress_eval\runs\strong_evidence_phase6_live_final_v1\source_roadmap.json
Get-ChildItem data\tmp\source_quality_stress_eval\runs\strong_evidence_phase6_live_final_v1\llm_audit\*.json | Measure-Object
```

### Phase 1: Coverage Lane Planner Upgrade

Objective:

- Improve query decomposition so it emits source lanes that match the query's proof obligations.

Tasks:

- Add or refine reusable lane triggers for:
  - regulator-specialist evidence
  - industry association / market price / capacity evidence
  - local fund / university / research-center evidence
  - city/county fiscal and statistics evidence
  - project/procurement/land/EIA evidence for local industrial claims
- Bind each lane to source class, administrative level, source strategy, and budget policy.
- Add tests that use generic query patterns, not only the 12 case IDs.

Acceptance criteria:

- Decomposition emits required lanes for representative macro/province/city/county patterns.
- Lane additions are source-class driven and not case-id-specific.
- Existing direct-keep controls remain direct-keep.

Validation:

```powershell
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py
python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\generalized_phase1_routing --print-json
```

### Phase 2: Local Source Profile Pattern Upgrade

Objective:

- Improve province/city/county source coverage through reusable source profile patterns.

Tasks:

- Add source profile patterns for local:
  - statistics / communiques / annual reports
  - public-resource trading and procurement
  - land transfer and natural-resources notices
  - EIA and ecological-environment notices
  - fiscal/support/subsidy evidence where relevant
- Prefer search-assisted profiles first; promote to direct adapters only when stable and repeated.
- Add region and source-class scoring so province/city/county evidence is not substituted by weaker upper-level material without a gap.

Acceptance criteria:

- City/county lanes have explicit local-source attempts before parent-level fallback.
- Local fallback metadata distinguishes exact-local, parent, and national evidence.
- Remaining unsupported sources are transparent.

Validation:

```powershell
pytest -q tests\test_sources_profile_adapter.py tests\test_sources_lane_execution.py tests\test_sources_source_resolver.py
```

### Phase 3: Extraction Reliability And Failure Classification

Objective:

- Reduce false no-evidence and false evidence caused by PDF/download/anti-bot/minimal-content extraction behavior.

Tasks:

- Classify extraction failures as PDF/download, anti-bot/403, SSL/certificate, minimal text, or irrelevant content.
- Add static PDF/link handling only if compatible with current source rules and without browser automation/OCR.
- Ensure extraction failures surface as lane gaps instead of being hidden behind generic fail messages.

Acceptance criteria:

- Extraction diagnostics are visible in existing trace metadata.
- PDF/download failures no longer look like source irrelevance.
- No browser automation or OCR is introduced.

Validation:

```powershell
pytest -q tests\test_source_quality_live_inspection.py tests\test_sources_crawl4ai_extraction.py tests\test_sources_pdf_step43.py
```

### Phase 4: Evidence Relevance And Sufficiency Scoring

Objective:

- Make lane success depend on proof strength, not just any accepted document.

Tasks:

- Add scoring rules for:
  - target region
  - target industry/topic
  - source class
  - administrative level
  - date/period recency
  - claim type relevance
- Separate usable evidence, weak evidence, and explicit gaps in existing metadata.
- Preserve public schema compatibility.

Acceptance criteria:

- Generic/source-mismatched pages are rejected or downgraded consistently.
- Strong evidence class missing counts align more closely between deterministic live artifacts and DeepSeek audit.
- No public schema drift.

Validation:

```powershell
pytest -q tests\test_sources_lane_execution.py tests\test_sources_search_assisted_domestic.py tests\test_source_quality_batch_report.py
```

### Phase 5: 12-Case Generalized Quality Gate

Objective:

- Prove the generalized remediation improves evidence quality before any full 50-case live run.

Tasks:

- Run routing inspection.
- Run live source acquisition with explicit budget settings.
- Run DeepSeek audit with resume support and `--max-output-tokens 8192`.
- Run batch report and compare to the Phase 7 baseline.

Acceptance criteria:

- Live gate: `12 success / 0 runtime error`.
- Audit schema: `0 invalid_json`, `0 invalid_schema`.
- Audit blockers: `0`.
- Audit verdict improvement: at least `6/12` cases are `weak_pass` or `pass`, or fail count falls to `<=6`.
- Missing source-class targets:
  - `project_list <= 6/12`
  - `statistics <= 3/12`
  - `environmental_or_land_record <= 2/12`
- Total estimated Tavily credits should be recorded; if credits exceed Phase 7's `69`, explain the tradeoff.

Validation:

```powershell
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\generalized_phase5_live --max-cases 12 --print-json
python data\tmp\_source_quality_llm_audit.py --run-dir data\tmp\source_quality_stress_eval\runs\generalized_phase5_live --provider deepseek --model deepseek-v4-pro --thinking true --reasoning-effort max --resume --max-output-tokens 8192 --print-summary
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\generalized_phase5_live --print-json
```

### Phase 6: Staged 50-Query Expansion

Objective:

- Use the 50-query set as a broader regression pressure set after the 12-case gate improves.

Tasks:

- Run offline routing for all 50 cases.
- Run a staged live subset by level: macro, province, city, county.
- Run full live only if cost and latency are acceptable.
- Convert failures into the next roadmap without overfitting.

Acceptance criteria:

- 50-query expansion is either completed with cost/latency/audit summary or explicitly deferred with evidence.
- New failures are classified by general failure family.
- No blocker or schema failure is hidden.

Validation:

```powershell
python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\source_quality_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\generalized_50_routing --print-json
```

## Continue Rule

After each milestone, continue automatically to the next milestone when:

- acceptance criteria are met
- required validation passes
- no permission, dependency, credential, or human-review blocker exists
- no high-risk contract change is being made without explicit PLAN authorization

Do not treat a milestone summary as the default stop point. Stop only at an explicit blocker, explicit user pause, failed validation without a safe fix, or final done condition.

## Stop Conditions

Stop and request guidance if:

- a protected contract change is required
- live credentials are unavailable
- a source requires browser automation, OCR, login, or paid access not authorized by this PLAN
- validation fails and the repair path is unclear or high risk
- external API behavior prevents safe completion
- the user explicitly pauses

## Done Condition

This PLAN is complete when:

- Phase 5 passes or records a precise successor blocker
- Phase 6 is completed or explicitly deferred with cost/risk evidence
- `.agent/STATUS.md` and this PLAN contain final progress, validation, risks, and next action
- final handoff includes what changed, implemented capability, test cases, two before/after examples, files changed, validation, and remaining TODOs

## Risks And Rollback

Risks:

- Local source sites may be unstable or anti-bot protected.
- Adding lanes may raise Tavily credit usage if budgets are not controlled.
- DeepSeek audit can be strict or noisy; use deterministic missing-class diagnostics alongside verdicts.
- PDF/static extraction may remain incomplete without OCR/browser automation.
- Dirty worktree is broad; scope must be reviewed before implementation.

Rollback:

- Disable new source profiles or registrations while preserving previous behavior.
- Revert only files changed by this PLAN.
- Keep Phase 7 artifact baseline as comparison.

## Progress

- 2026-04-29: PLAN created from failed Phase 7 of `source-strong-evidence-adapter-remediation-v1`. No production source code changed in this planning step.
- 2026-04-29: Phase 0 completed. Added deterministic taxonomy script `data/tmp/_source_quality_failure_taxonomy.py` and test `tests/test_source_quality_failure_taxonomy.py`. Generated artifacts:
  - `data/tmp/source_quality_stress_eval/generalized_remediation_phase0/failure_taxonomy.json`
  - `data/tmp/source_quality_stress_eval/generalized_remediation_phase0/failure_taxonomy.md`
- 2026-04-29: Phase 0 taxonomy mapped all 12 smoke cases into general failure families. Highest-impact families: `evidence_sufficiency_scoring=12`, `extraction_reliability=12`, `local_statistics_data=10`, `local_project_public_resource=9`, `local_official_record=5`, `industry_capacity_market=5`, `local_capital_research=3`, `policy_routing_relevance=3`, `coverage_lane_planner=2`, `specialist_regulator=1`.
- 2026-04-29: Phase 0 validation passed:
  - RED: `pytest -q tests\test_source_quality_failure_taxonomy.py` first failed because the taxonomy script did not exist.
  - GREEN: `python -m ruff check data\tmp\_source_quality_failure_taxonomy.py tests\test_source_quality_failure_taxonomy.py` -> pass.
  - GREEN: `python -m py_compile data\tmp\_source_quality_failure_taxonomy.py tests\test_source_quality_failure_taxonomy.py` -> pass.
  - GREEN: `pytest -q tests\test_source_quality_failure_taxonomy.py` -> `1 passed`.
- 2026-04-29: Phase 1 slice 1 completed. Enhanced existing coverage lanes without adding public task families:
  - `industry_topic` now handles capacity/market-price proof obligations such as power-battery/PV capacity and price signals.
  - `local_rollout` now emits local-fund and university/research phrases when queries ask for fund / university / research-to-order proof.
  - `data_metrics` now emits low-altitude market-scale, infrastructure-statistics, and enterprise-order phrases when scaleout/enterprise-order proof is requested.
- 2026-04-29: Phase 1 slice 1 validation passed:
  - RED: three new tests first failed for missing industry-topic lane, missing local-fund/research phrases, and missing low-altitude scale/order data phrases.
  - GREEN: `python -m ruff check packages\sources\query_decomposition.py data\tmp\_source_quality_failure_taxonomy.py data\tmp\_source_quality_llm_audit.py tests\test_sources_query_decomposition.py tests\test_source_quality_failure_taxonomy.py tests\test_source_quality_llm_audit.py` -> pass.
  - GREEN: py_compile for the same touched source/eval/test files -> pass.
  - GREEN: `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_source_quality_failure_taxonomy.py tests\test_source_quality_llm_audit.py` -> `81 passed`.
  - Source regression: `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`.
  - Domestic regression: `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`.
  - Routing gate: `data/tmp/source_quality_stress_eval/runs/generalized_phase1_routing_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
- 2026-04-29: Phase 2 completed. Added reusable local source-class domain patterns in `packages/sources/local_source_patterns.py` and connected them to query decomposition and source resolver domain-region matching.
- 2026-04-29: Phase 2 implementation maps local domains by proof class instead of by smoke-case ID:
  - `statistics` and optional fiscal/local-government domains for local quantitative lanes.
  - `project_public_resource` domains for project/procurement/public-resource lanes.
  - `environmental_or_land_record` domains for EIA, land, natural-resources, and regulatory record lanes.
  - local-government domains for local rollout lanes.
- 2026-04-29: Phase 2 validation passed:
  - RED: `pytest -q tests\test_sources_local_source_patterns.py tests\test_sources_query_decomposition.py::test_county_park_cluster_query_keeps_direct_lanes_when_records_requested tests\test_sources_query_decomposition.py::test_environmental_land_record_need_is_visible_in_missing_sources` first failed because `packages.sources.local_source_patterns` did not exist.
  - GREEN: same command -> `6 passed`.
  - Focused ruff: `python -m ruff check packages\sources\local_source_patterns.py packages\sources\query_decomposition.py packages\sources\source_resolver.py tests\test_sources_local_source_patterns.py tests\test_sources_query_decomposition.py tests\test_sources_domestic_scaleout_phase7.py` -> pass.
  - Focused py_compile for the same files -> pass.
  - Focused source/decomposition/profile tests: `pytest -q tests\test_sources_local_source_patterns.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_domestic_scaleout_phase7.py tests\test_sources_city_county_fallback.py` -> `92 passed`.
  - Focused profile/lane/router tests: `pytest -q tests\test_sources_profile_adapter.py tests\test_sources_lane_execution.py tests\test_sources_router_domestic.py` -> `33 passed`.
  - Source regression: `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`.
  - Domestic regression: `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`.
  - Routing gate: `data/tmp/source_quality_stress_eval/runs/generalized_phase2_routing_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
  - Repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt.
- 2026-04-29: Phase 3 completed. Added structured Crawl4AI extraction failure classification without changing public evidence/citation schemas and without adding browser automation or OCR.
- 2026-04-29: Phase 3 classification now records `extraction_failure_class` and `extraction_failure_stage` on ToolError detail and response-level `failure_classes` counts for:
  - `pdf_or_download`
  - `anti_bot_or_forbidden`
  - `ssl_certificate_error`
  - `timeout`
  - `minimal_text_or_empty`
  - `runtime_error`
  - `runtime_missing_result`
- 2026-04-29: Phase 3 validation passed:
  - RED: Crawl4AI tests first failed because `failure_classes` and error-level extraction classification were missing.
  - GREEN: `pytest -q tests\test_sources_crawl4ai_extraction.py::test_crawl4ai_partial_failure_keeps_successful_documents tests\test_sources_crawl4ai_extraction.py::test_crawl4ai_failure_classification_covers_pdf_ssl_and_empty_content` -> `2 passed`.
  - Focused ruff: `python -m ruff check packages\sources\crawl4ai_extraction.py tests\test_sources_crawl4ai_extraction.py tests\test_source_quality_live_inspection.py` -> pass.
  - Focused py_compile for the same files -> pass.
  - Extraction/PDF validation: `pytest -q tests\test_source_quality_live_inspection.py tests\test_sources_crawl4ai_extraction.py tests\test_sources_pdf_step43.py` -> `16 passed`.
  - Source regression: `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`.
  - Domestic regression: `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`.
- 2026-04-29: Phase 4 completed. Added direct-lane evidence-quality diagnostics under existing metadata only, with no EvidenceBundle/citation/research response shape change:
  - accepted direct/fallback documents now receive `metadata["evidence_quality"]`
  - accepted/rejected lane metadata now includes `evidence_quality_summary`
  - weak-document rejections now include `evidence_quality` explaining source-class, topic, region, administrative-level, content, and date signals
  - weak proof is rejected through the existing weak-document rejection path instead of being counted as lane evidence
- 2026-04-29: Phase 4 validation passed:
  - RED: `pytest -q tests\test_sources_lane_execution.py::test_project_search_fallback_uses_candidate_hints_when_crawl_page_is_sparse tests\test_sources_lane_execution.py::test_data_metrics_lane_rejects_irrelevant_direct_documents tests\test_sources_lane_execution.py::test_official_record_lane_uses_search_fallback_without_direct_adapter` first failed because `evidence_quality` / `evidence_quality_summary` were missing.
  - GREEN: same command -> `3 passed`.
  - Focused ruff: `python -m ruff check packages\sources\lane_execution.py tests\test_sources_lane_execution.py tests\test_sources_search_assisted_domestic.py tests\test_source_quality_batch_report.py` -> pass.
  - Focused py_compile for the same files -> pass.
  - Focused Phase 4 validation: `pytest -q tests\test_sources_lane_execution.py tests\test_sources_search_assisted_domestic.py tests\test_source_quality_batch_report.py` -> `51 passed`.
  - Source regression: `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`.
  - Domestic regression: `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`.
  - Focused decomposition/profile checks: `pytest -q tests\test_sources_local_source_patterns.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_domestic_scaleout_phase7.py tests\test_sources_city_county_fallback.py` -> `92 passed`.
  - Repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt.
- 2026-04-29: Phase 5 generalized quality gate executed and failed acceptance. This is a quality blocker, not a runtime blocker.
  - Routing artifact: `data/tmp/source_quality_stress_eval/runs/generalized_phase5_routing_v1`
  - Routing result: `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
  - Live artifact: `data/tmp/source_quality_stress_eval/runs/generalized_phase5_live_v1`
  - Live result: `12 success / 0 runtime error`, average latency `34752.02 ms`, estimated Tavily credits `78`, `query_invalid_count=0`.
  - DeepSeek audit used `deepseek-v4-pro` with thinking/max reasoning and `--resume`. The first run hit the tool wall-clock timeout after writing partial per-case audit files; the resume run completed the remaining cases.
  - DeepSeek audit result: `12 success`, audit shape diagnostics `0`, verdicts `1 blocker / 8 fail / 3 weak_pass`, total tokens `274905`.
  - Batch report artifact: `data/tmp/source_quality_stress_eval/runs/generalized_phase5_live_v1/batch_eval.json`
  - Source roadmap artifact: `data/tmp/source_quality_stress_eval/runs/generalized_phase5_live_v1/source_roadmap.json`
- 2026-04-29: Phase 5 acceptance comparison:
  - Passed: live stability (`12 success / 0 runtime error`).
  - Passed: audit transport/schema (`12 success`, audit shape diagnostics `0`).
  - Failed: audit blockers must be `0`, but `C01` remained a blocker.
  - Failed: audit verdict improvement target requires at least `6/12` weak_pass/pass or fail count `<=6`; actual result was `3/12` weak_pass/pass and `8` fail.
  - Passed: `project_list=5` missing, target `<=6`.
  - Failed narrowly: `statistics=4` missing, target `<=3`.
  - Failed narrowly: `environmental_or_land_record=3` missing, target `<=2`.
  - Cost tradeoff recorded: `78` estimated Tavily credits exceeded the Phase 7 baseline `69`, mainly because stronger direct fallback and multi-lane evidence acquisition ran more discovery paths.
- 2026-04-29: Phase 5 systemic gaps to carry into the successor remediation:
  - `local_government=5`: `C01`, `C09`, `K07`, `K09`, `P10`
  - `project_list=5`: `C01`, `K07`, `K12`, `M03`, `P08`
  - `statistics=4`: `C01`, `K09`, `M03`, `P08`
  - `environmental_or_land_record=3`: `C01`, `K07`, `P08`
  - Recurring operational issue: PDF/download/minimal-content extraction failures are now classified but still reduce usable evidence.
- 2026-04-29: Phase 6 staged 50-query expansion is explicitly deferred. Running the full 50-case live set before fixing the Phase 5 blocker would amplify known quality gaps and risk overfitting instead of improving the general source-quality paradigm.

## Current Phase

Phase 5: blocked at 12-case generalized quality gate.

## Next Action

Create a narrow successor remediation PLAN before any 50-query live expansion. The successor should generalize fixes around local-government backbones, project/public-resource evidence, local statistics/fiscal reports, environmental/land/EIA records, extraction reliability, and budget-aware multi-lane scheduling. Do not optimize for one case ID; use the 12 smoke cases as symptoms and regression checks.
