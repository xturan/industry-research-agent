# Source Structured Evidence Backbone v1

Status: completed_with_successor_blocker

Created: 2026-04-29

Primary active PLAN: yes

Supersedes execution follow-up from:

- `.agent/PLANS/archive/source-evidence-quality-gate-remediation-v1.md`

## Objective

Build a reusable structured-evidence backbone for source-quality evaluation and research retrieval.

The previous remediation improved runtime stability, local official precision, official-record filtering, and audit visibility. The 12-case quality gate still failed because the system does not yet reliably retrieve and package strong structured evidence:

- Live gate: `12 success / 0 runtime error`
- DeepSeek audit: `12 success`, shape diagnostics `0`
- Verdicts: `10 fail / 2 weak_pass / 0 pass`
- Estimated Tavily credits: `75`
- Average latency: `44521.71 ms`

Primary remaining gaps:

| Source class | Missing count | Affected cases |
|---|---:|---|
| `tender_or_procurement` | `7` | `C01`, `K09`, `K12`, `M02`, `M03`, `P04`, `P08` |
| `project_list` | `6` | `K07`, `K09`, `K12`, `M02`, `M03`, `P08` |
| `environmental_or_land_record` | `2` | `K07`, `M02` |
| `regulatory_record` | `2` | `K07`, `M02` |
| `industry_report` | `2` | `P04`, `P10` |

This PLAN must improve general retrieval and evidence-quality patterns, not overfit individual query IDs.

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

Use the 12-case and future 50-query sets as pressure tests.

Do not write query-specific patches like "if query_id == K07". Instead, implement reusable source families and acceptance rules:

```text
User Query
  -> evidence obligation planner
  -> structured source family router
  -> source-specific discovery/adapters
  -> static extraction / PDF-download diagnostics
  -> region/topic/entity quality gate
  -> audit-visible evidence package
```

Core backbone families:

- `public_resource_trade`: public resource trading, tender, bid-winning, procurement project pages.
- `government_procurement`: central/provincial/city/county government procurement pages.
- `project_approval_or_filing`: DRC approval, filing, key project list, start/production lists.
- `environment_land_record`: EIA, land transfer, natural-resource and planning records.
- `local_statistics_fiscal`: local statistical bulletins, fiscal budgets, subsidies, special funds.
- `regional_enterprise_disclosure`: listed company disclosures filtered by region/operation relevance.
- `industry_price_capacity`: public industry statistics, prices, capacity and production signals.

## Scope

In scope:

- Source family taxonomy and routing rules for strong structured evidence.
- Reusable domain/profile patterns for public-resource, procurement, project, land/environment, local fiscal/statistics, and regional disclosure evidence.
- Adapter-like discovery/extraction services where search-assisted recall is not enough.
- Acceptance/rejection rules for region match, topic match, document type, date, and source authority.
- Focused eval artifacts and batch reporting for source-class improvements.
- 12-case regression gate before staged 50-query expansion.

Out of scope unless reopened:

- Browser automation as the default path.
- OCR.
- Login-gated, paid, or private data.
- Full 50-query live run before a passing 12-case gate.
- Direct securities investment advice.
- Public API contract shape changes.

## Agent Execution Contract

Use this role model when subagents are explicitly authorized:

- `invest_project_director`: owns phase scope, validates that the PLAN improves generic patterns and does not overfit query IDs.
- `invest_agent_architecture_builder`: owns source-family contracts, adapter boundaries, and protected-contract compatibility.
- `invest_feature_programmer`: owns concrete implementation in `packages/sources/**`, eval scripts, and tests.
- `invest_code_quality_checker`: owns ruff, py_compile, focused pytest, and scope review.
- `invest_functional_validator`: owns live/offline validation against the 12-case gate and artifacts.
- `invest_project_summarizer`: runs only after final done condition.

Workers must not independently reinterpret the roadmap. Any protected-contract change must return to Architecture Gate before implementation.

## Phases

### Phase 0: Failure Taxonomy And Source-Family Freeze

Objective:

- Convert the latest Phase 5 failure into reusable source-family obligations.

Tasks:

- Read:
  - `data/tmp/source_quality_stress_eval/runs/source_evidence_quality_gate_v1_phase5_live_v1/batch_eval.json`
  - `data/tmp/source_quality_stress_eval/runs/source_evidence_quality_gate_v1_phase5_live_v1/source_roadmap.json`
  - `data/tmp/source_quality_stress_eval/runs/source_evidence_quality_gate_v1_phase5_live_v1/llm_audit/*.json`
- Group failures into source-family classes, not query IDs.
- Freeze the first implementation order.
- Define Phase 1 acceptance criteria.

Acceptance criteria:

- A source-family failure matrix exists.
- P0/P1/P2 source-family priorities are explicit.
- No production code changed.

Validation:

```powershell
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\source_evidence_quality_gate_v1_phase5_live_v1 --print-json
```

### Phase 1: Public-Resource And Procurement Backbone

Objective:

- Reduce `tender_or_procurement` misses from `7` toward `<=5` without increasing default fanout.

Tasks:

- Add/strengthen reusable patterns for:
  - `ggzy.gov.cn`
  - provincial public-resource platforms
  - municipal public-resource platforms
  - county branch pages where discoverable
  - `ccgp.gov.cn` and local government procurement pages
- Add candidate acceptance rules for tender/bid/procurement document signals.
- Add rejection rules for generic policy/news pages that do not prove project or tender evidence.
- Keep budget caps explicit.

Acceptance criteria:

- Deterministic tests prove public-resource/procurement source-family routing and rejection rules.
- Low-cost subset improves at least two affected cases without harming existing project-list coverage.
- No protected public contract changes.

### Phase 2: Project Approval And Key-Project Backbone

Objective:

- Reduce `project_list` misses from `6` toward `<=5`.

Tasks:

- Strengthen project list / approval / filing / start-production phrase templates.
- Add reusable DRC, development-zone, and key-project list source patterns.
- Require project evidence to include at least one of: project name, construction/start/production signal, approval/filing signal, tender/bid signal, or implementing entity.
- Avoid classifying generic policy interpretation as strong project evidence.

Acceptance criteria:

- Project-list evidence quality tests cover generic-policy rejection and project-signal acceptance.
- Low-cost subset improves project evidence without increasing query-invalid or runtime errors.

### Phase 3: Environment, Land, And Regulatory Record Backbone

Objective:

- Keep `environmental_or_land_record <= 2` stable and reduce `regulatory_record` misses.

Tasks:

- Add reusable patterns for MEE, provincial ecology/environment, natural resources, planning, land transfer, and approval pages.
- Improve PDF/download diagnostics and static text extraction where safe.
- Keep browser automation/OCR out unless a follow-up Architecture Gate authorizes them.

Acceptance criteria:

- Official-record evidence quality remains conservative: retrieval query terms alone cannot prove topic relevance.
- Extraction failures are visible to audit artifacts.
- Low-cost subset confirms no regression in P08/K09-style official-record cases.

### Phase 4: Regional Enterprise Disclosure And Industry Evidence

Objective:

- Improve non-government strong evidence where public official sources are insufficient.

Tasks:

- Add regional relevance filters for enterprise disclosure candidates.
- Strengthen industry report / price / capacity source-family routing.
- Keep disclosure direct paths primary; search remains supplementary.

Acceptance criteria:

- Regional disclosure candidates must show region, operation, project, or subsidiary relevance.
- Industry/price evidence must not be accepted from stale or unrelated generic pages.

### Phase 5: Evidence Quality Gate Rerun

Objective:

- Re-run 12-case live inspection, DeepSeek audit, and batch report.

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
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_retrieval_plan.py
pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py
pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py
```

Live gate after remediation:

```powershell
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\strong_evidence_smoke_cases_v1.json --mode extraction_inspection --max-search-tasks 2 --max-rounds 2 --max-candidates 3 --content-chars 1200 --output-dir data\tmp\source_quality_stress_eval\runs\source_structured_evidence_backbone_v1_phase5_live_v1 --print-json
python data\tmp\_source_quality_llm_audit.py --run-dir data\tmp\source_quality_stress_eval\runs\source_structured_evidence_backbone_v1_phase5_live_v1 --provider deepseek --model deepseek-v4-pro --thinking true --reasoning-effort max --timeout 240 --max-output-tokens 8192 --print-summary
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\source_structured_evidence_backbone_v1_phase5_live_v1 --print-json
```

## Done Condition

This PLAN is done when either:

- the 12-case gate passes Phase 5 acceptance and Phase 6 authorizes staged 50-query expansion, or
- a narrower successor blocker is recorded with clear source-family evidence and the full 50-query live run remains deferred.

## Progress

- 2026-04-29: PLAN created from `source-evidence-quality-gate-remediation-v1` Phase 5 failure.
  - Reused artifacts from `data/tmp/source_quality_stress_eval/runs/source_evidence_quality_gate_v1_phase5_live_v1`.
  - Initial focus is generic structured-evidence backbone, especially public-resource/procurement and project-list evidence.
- 2026-04-29: Phase 0 completed.
  - Created source-family failure matrix:
    - `data/tmp/source_quality_stress_eval/source_structured_evidence_backbone_phase0/failure_matrix.json`
    - `data/tmp/source_quality_stress_eval/source_structured_evidence_backbone_phase0/failure_matrix.md`
  - Frozen source families:
    - `public_resource_and_procurement` (`P0`, missing `7`)
    - `project_approval_and_key_project` (`P0`, missing `6`)
    - `environment_land_and_regulatory_record` (`P1`, missing `4`)
    - `regional_enterprise_disclosure` (`P1`)
    - `industry_price_capacity` (`P1`, missing `5`)
    - `local_statistics_fiscal_and_subsidy` (`P2`, missing `3`)
  - Phase 1 freeze:
    - Target family: `public_resource_and_procurement`
    - Success metric: reduce `tender_or_procurement` missing count from `7` toward `<=5` without raising default fanout or regressing project-list coverage.
    - Validation subset candidates: `C01`, `K09`, `K12`, `M02`, `M03`, `P04`, `P08`.
    - Do-not-overfit rule: source-family/domain/evidence-signal rules only; no query-id-specific branches.
  - Validation:
    - Matrix JSON parse and assertions -> `phase0_matrix_ok 6 public_resource_and_procurement`
    - PLAN exists and previous PLAN archived -> pass
- 2026-04-29: Phase 1 completed with public-resource/procurement candidate acceptance hardening.
  - Diagnosis:
    - Public-resource trading pages often expose a generic title such as `全国公共资源交易平台`.
    - The previous project-search fallback rejected those generic titles before considering Tavily snippets, even when the snippet contained region, topic, project, bid-winning, procurement, or public-resource signals.
    - This caused valid `ggzy.gov.cn` detail pages in macro/provincial cases to be discarded under the two-credit fallback budget.
  - Implementation:
    - Added a reusable public-resource/procurement search-signal gate for `ggzy`, `ccgp`, `zfcg`, `cgw`, and related domains.
    - The gate only applies to detail-like URL paths such as `deal`, `jyxx`, `jydt`, `information`, `html/b`, and similar procurement/trading paths.
    - Generic public-resource titles can pass only when the detail URL and snippet contain project or tender/procurement signals.
    - No default fanout or public contract shape changed.
  - Validation:
    - RED/GREEN test: `pytest -q tests\test_sources_lane_execution.py -k "public_resource_snippet_signals"` -> red, then `1 passed`
    - `pytest -q tests\test_sources_lane_execution.py -k "project_search_fallback"` -> `7 passed, 1 warning`
    - focused ruff -> pass
    - focused py_compile -> pass
    - focused source suite -> `173 passed, 1 warning`
    - source regression -> `27 passed`
    - domestic regression -> `16 passed`
  - Low-cost live subset:
    - Case file: `data/tmp/source_quality_stress_eval/source_structured_evidence_backbone_phase1_procurement_subset_cases.json`
    - Artifact: `data/tmp/source_quality_stress_eval/runs/source_structured_evidence_backbone_v1_phase1_procurement_subset_v1`
    - Result: `7 success`, estimated Tavily credits `13`, average latency `7430.53 ms`, `query_invalid_count=0`
    - Improved coverage:
      - `M02`: covered `project_list` and `tender_or_procurement`
      - `M03`: covered `project_list` and `tender_or_procurement`
      - `P08`: covered `project_list` and `tender_or_procurement`
    - Remaining gaps:
      - `C01` and `P04` still covered only `project_list`
      - `K09` and `K12` still lacked usable project/procurement evidence
  - Phase 1 decision:
    - The generic public-resource/procurement gate improved tender coverage without increasing default search credits.
    - Remaining `K09/K12` and some local/provincial gaps move to Phase 2 project approval/key-project backbone and later extraction robustness.
- 2026-04-29: Phase 2 completed with project approval/key-project backbone hardening.
  - Diagnosis:
    - Sparse county/project queries involving industrialization, filing, approval, resource/energy constraints, and project clusters were still routed through procurement-first phrase ordering.
    - Official project/DRC/local-government search results could contain strong project approval or key-project signals in Tavily snippets, but the fallback only trusted title/URL project signals outside public-resource domains.
    - Broad planning, public-comment, expert-view, and policy-interpretation pages could be misclassified as strong project evidence when their snippets contained generic project terms.
  - Implementation:
    - Project transaction phrase ordering now prioritizes `项目备案 审批` and `重点项目 开工 投产` for approval/filing/industrialization queries.
    - Project-cluster queries now keep `重点项目 开工 投产` plus `公共资源交易 招标 中标` in the two-credit search window.
    - Added a reusable official project-approval snippet gate for government/DRC-style detail pages.
    - Added conservative rejection for broad planning or interpretation pages such as planning-public-comment pages and expert/policy analysis pages.
    - No protected public contract shape changed.
  - Validation:
    - `pytest -q tests\test_sources_query_decomposition.py` -> `51 passed`
    - `pytest -q tests\test_sources_lane_execution.py -k "project_search_fallback"` -> `11 passed, 1 warning`
    - focused ruff -> pass
    - focused py_compile -> pass
    - focused source suite -> `180 passed, 1 warning`
    - source regression -> `27 passed`
    - domestic regression -> `16 passed`
  - Low-cost live subset:
    - Case file: `data/tmp/source_quality_stress_eval/source_structured_evidence_backbone_phase2_project_subset_cases.json`
    - Final artifact: `data/tmp/source_quality_stress_eval/runs/source_structured_evidence_backbone_v1_phase2_project_subset_v2`
    - Result: `8 success`, estimated Tavily credits `15`, average latency `10000.77 ms`, `query_invalid_count=0`
    - Project-class coverage in the subset:
      - `project_list` missing count: `1`
      - `tender_or_procurement` missing count: `4`
    - Quality hardening behavior:
      - K12 broad planning/public-comment candidate was rejected with `generic_project_planning_or_interpretation`.
      - M03 expert/policy interpretation candidates were rejected; remaining accepted project evidence came from public-resource trading pages.
    - Remaining gaps:
      - `K07` accepted exact-local project candidates but extraction produced no usable evidence; this moves to extraction/official-record/local-page robustness.
      - `C01`, `K12`, and `P08` still lack tender/procurement in this project-only slice.
      - Some accepted project-list evidence still comes from official reports/news-style pages and should be judged by Phase 5 audit rather than inflated by source-class counts alone.
  - Phase 2 decision:
    - Acceptance criteria met for reusable project approval/key-project routing and conservative generic-page rejection.
    - Continue automatically to Phase 3 for environment, land, and regulatory-record backbone hardening.
- 2026-04-29: Phase 3 completed with environment/land/regulatory-record backbone hardening.
  - Diagnosis:
    - P08/K09-style ecology and EIA records were already stable and should not be loosened.
    - M02-style macro/national queries still rejected local official EIA/regulatory detail pages as `official_record_search_off_domain`, even when those pages contained concrete computing-infrastructure, EIA, acceptance, review, approval, or filing signals.
    - DRC/FGW-style regulatory pages can carry energy-review, approval, and filing records, but the snippet-trust gate only covered ecology/natural-resource department domains.
  - Implementation:
    - Added national-scope official-record handling that allows local `.gov.cn` detail pages only when the task is unscoped/national, the page is detail-like, the result has official-record signals, and relevance terms match.
    - Added the same national-scope allowance to the post-extraction weak-document filter so accepted candidates are not discarded solely because they are local official domains.
    - Expanded official-record department snippet trust to DRC/FGW/FZGGW/NDRC-style government domains for regulatory records, while keeping record-signal and relevance gates.
    - Preserved strict regional matching for county/province tasks; K07-style county tasks still reject unrelated local-government domains.
  - Validation:
    - RED/GREEN tests for national local EIA detail and DRC regulatory snippets -> `2 passed`
    - `pytest -q tests\test_sources_lane_execution.py -k "official_record"` -> `21 passed, 1 warning`
    - `pytest -q tests\test_sources_query_decomposition.py` -> `51 passed`
    - focused ruff -> pass
    - focused py_compile -> pass
    - focused source suite -> `182 passed, 1 warning`
    - source regression -> `27 passed`
    - domestic regression -> `16 passed`
    - repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt (`47` errors).
  - Low-cost live subset:
    - Case file: `data/tmp/source_quality_stress_eval/source_structured_evidence_backbone_phase3_official_record_subset_cases.json`
    - Artifact: `data/tmp/source_quality_stress_eval/runs/source_structured_evidence_backbone_v1_phase3_official_record_subset_v1`
    - Result: `5 success`, estimated Tavily credits `13`, average latency `18320.51 ms`, `query_invalid_count=0`
    - Coverage:
      - `M02`: now covers `environmental_or_land_record` and `regulatory_record` through a local official EIA/regulatory detail page.
      - `P08`, `K09`, `K12`: retained `environmental_or_land_record` and `regulatory_record` coverage.
      - `K07`: still missing both official-record classes; this remains a county-level sparse-source/profile problem, not a generic macro official-record gate problem.
  - Phase 3 decision:
    - Acceptance criteria met: conservative official-record filtering remains covered by deterministic tests, extraction/download failure diagnostics remain visible, and the official-record subset improved M02 without regressing P08/K09/K12.
    - Continue automatically to Phase 4 for regional enterprise disclosure and industry evidence.
- 2026-04-29: Phase 4 completed with regional disclosure and industry evidence hardening.
  - Diagnosis:
    - `industry_topic` documents were only exposed as coarse `industry_report` / `industry_association` metadata, so price, capacity, and association-report obligations were not audit-visible.
    - Province/local industry-topic phrases for P04/P10-style queries did not preserve region and sector context, causing generic whitepaper/forum search instead of local industry evidence search.
    - Allowed association domains could return root or channel pages such as `caam.org.cn/` and `/hyzc`; these pages should not be treated as strong industry evidence even when Tavily snippets mention reports.
    - C07-style enterprise disclosure phrases lost local/multi-sector context; disclosure mapping then ranked generic battery companies before region-tagged candidates.
  - Implementation:
    - Added regional industry-topic phrase generation that keeps region and sector context for province/local industry evidence.
    - Added audit-visible `association_report`, `price_data`, and `industry_price_capacity` source-class metadata for industry-topic documents when search obligations include price, capacity, production, sales, shipment, or market data signals.
    - Added generic industry-topic root/channel URL rejection before Crawl4AI extraction.
    - Added regional enterprise disclosure phrases and region-tagged disclosure candidate prioritization, preserving direct disclosure as the primary path.
  - Validation:
    - RED/GREEN industry source-class and generic-channel tests -> passed.
    - RED/GREEN regional disclosure phrase and region-tagged disclosure mapping tests -> passed.
    - `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_retrieval_plan.py tests\test_sources_disclosure_mapping.py` -> `192 passed, 1 warning`.
    - source regression -> `27 passed`.
    - domestic regression -> `16 passed`.
    - focused ruff/py_compile for changed files -> pass.
    - repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt (`47` errors).
  - Low-cost live subsets:
    - Industry subset artifact: `data/tmp/source_quality_stress_eval/runs/source_structured_evidence_backbone_v1_phase4_industry_subset_v3`.
    - Industry subset result: `3 success`, estimated Tavily credits `3`, average latency `38613.34 ms`, `query_invalid_count=0`.
    - `P04` now rejects `caam.org.cn/` and `/hyzc` as `industry_topic_generic_channel_candidate`; accepted documents expose `industry_report`, `industry_association`, `association_report`, `price_data`, and `industry_price_capacity`.
    - `C07` accepted CAAM article/detail pages with `price_data` and `industry_price_capacity`.
    - `P10` accepted Hainan association/industry platform article pages with `association_report`.
    - Disclosure subset artifact: `data/tmp/source_quality_stress_eval/runs/source_structured_evidence_backbone_v1_phase4_disclosure_subset_v1`.
    - Disclosure subset result: `3 success`, estimated Tavily credits `0`, average latency `772.66 ms`, `query_invalid_count=0`.
    - `C07` disclosure mapping now prioritizes `天合光能` and `亿纬锂能` before generic battery names; `P04/P10` retain region-tagged disclosure candidates.
  - Phase 4 decision:
    - Acceptance criteria met: disclosure remains direct-primary, industry evidence avoids root/channel pages, and audit-visible source classes are richer.
    - Continue automatically to Phase 5 for the 12-case live quality gate.
- 2026-04-29: Phase 5 completed with successor blocker.
  - Live gate:
    - Artifact: `data/tmp/source_quality_stress_eval/runs/source_structured_evidence_backbone_v1_phase5_live_v1`
    - `12 success / 0 runtime error`
    - Estimated Tavily credits: `75`
    - Average latency: `61372.52 ms`
  - DeepSeek audit:
    - `12 success`
    - shape diagnostics: `0`
    - blockers: `0`
    - verdicts: `7 fail / 5 weak_pass / 0 pass`
  - Batch report:
    - `project_list=1` missing vs target `<=5`
    - `tender_or_procurement=3` missing vs target `<=5`
    - `local_government=1` missing vs target `<=3`
    - `statistics=2` missing vs target `<=3`
    - `environmental_or_land_record=1` missing vs target `<=2`
  - Gate decision:
    - Runtime, schema, blocker, and source-count thresholds passed.
    - Quality threshold failed by one case: `5/12` weak/pass vs required `>=6/12`, and `7` fail vs required `<=6`.
  - Successor blocker:
    - Remaining issue is evidence sufficiency and administrative granularity, not broad source-class discovery.
    - Created successor PLAN: `.agent/PLANS/source-multigranular-evidence-sufficiency-v1.md`.
    - Created Phase 0 obligation artifacts:
      - `data/tmp/source_quality_stress_eval/source_multigranular_evidence_sufficiency_phase0/obligation_matrix.json`
      - `data/tmp/source_quality_stress_eval/source_multigranular_evidence_sufficiency_phase0/obligation_matrix.md`

## Current Phase

Completed with successor blocker. Active execution moved to `.agent/PLANS/source-multigranular-evidence-sufficiency-v1.md`.

## Risks And Rollback

Risks:

- Public-resource and procurement pages are heterogeneous and can be anti-bot/PDF/download-heavy.
- Stronger structured-source acceptance can reduce recall if too strict.
- Increasing fallback search fanout can improve recall but raise Tavily credits.
- Some county-level evidence may be unavailable through public static pages.
- Dirty worktree remains broad; do not revert unrelated changes.

Rollback:

- Revert only files changed under this PLAN.
- Preserve `source_evidence_quality_gate_v1_phase5_live_v1` as the baseline comparison run.
- Disable new source-family patterns or adapters if they introduce domain/topic drift.

## Next Action

Use `.agent/PLANS/source-multigranular-evidence-sufficiency-v1.md` Phase 1 to implement reusable evidence-obligation metadata and sufficiency diagnostics before any full 50-query live run.
