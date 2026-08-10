# Plan: Source Direct Structured Execution v1

Status: blocked_at_phase7_gate
Priority: high
Owner: codex/human
Scope: source-layer execution planning, direct structured lane dispatch, and smoke evidence coverage remediation
Created: 2026-04-28
Last Updated: 2026-04-28

## Objective

Move the domestic source system from "direct structured lanes are visible as gaps" to
"direct structured lanes are actually dispatched, audited, and either produce evidence or
return a precise unsupported/coverage-gap reason."

This PLAN continues from:

```text
.agent/PLANS/archive/source-routing-remediation-v1.md
data/tmp/source_quality_stress_eval/runs/remediation_smoke_live/batch_eval.json
data/tmp/source_quality_stress_eval/runs/remediation_smoke_live/source_roadmap.json
```

Latest remediation smoke baseline:

- Live inspection: `12 success / 0 error`
- Estimated Tavily credits: `21`
- DeepSeek audit: `5 blocker / 7 fail`
- Remaining blocker cases: `M02`, `M06`, `P08`, `C07`, `C09`
- Dominant missing source classes:
  - `company_disclosure`: 12/12
  - `project_list`: 12/12
  - `statistics`: 8/12
  - `environmental_or_land_record`: 5/12
  - `local_government`: 4/12

Primary remediation goal:

```text
required direct structured lanes must not be silently skipped by the execution loop.
```

Secondary goal:

```text
the next smoke run should reduce DeepSeek blockers caused by "lane not executed",
"critical source class missing", or "only policy evidence was fetched".
```

## Task Classification

Primary area: `source_layer`

Secondary areas:

- `domestic_source_collectors`
- `eval_policy_ops`
- `research_workflow` only if the final integration phase is explicitly opened

Protected contracts that must not change silently:

- EvidenceBundle schema
- EvidenceItem citation fields
- `source_quality_summary` shape
- research analyze response shape
- provider abstraction semantics
- source routing response shape
- task/job status semantics
- `run` / `run_steps` meaning
- content asset metadata contract
- direct-keep primary path semantics
- legacy `enable_source_acquisition=False` behavior

## Design Decision

Use a staged direct-lane execution bridge, not a broad source expansion.

Chosen approach:

```text
RetrievalPlan / QueryDecomposition
  -> lane-aware execution scheduler
  -> search-assisted lanes use Tavily + Crawl4AI
  -> direct structured lanes use SourceRegistry / SourceToolRegistry / profile adapters when available
  -> unavailable direct lanes return structured unsupported gaps
  -> eval artifacts record which required lanes executed, produced evidence, or remained unsupported
```

Rejected approaches:

- Do not make Tavily the primary path for disclosure, project transaction, statistics,
  environmental, or land records.
- Do not build all provincial/city/county direct adapters at once.
- Do not change downstream research API or EvidenceBundle shapes just to surface this
  planning-level visibility.

Rationale:

- The previous PLAN already proved runtime extraction and first-wave routing are stable enough.
- The blocker is now orchestration coverage: direct lanes are planned but not executed.
- A narrow execution bridge lets us test real behavior before investing in dozens of
  source-specific adapters.

## Scope

In scope:

- `packages/sources/retrieval_plan.py`
- `packages/sources/query_decomposition.py`
- `packages/sources/source_resolver.py`
- `packages/sources/search_assisted_domestic.py`
- `packages/sources/service.py`
- `packages/sources/tools.py`
- `packages/sources/registry.py`
- `packages/sources/profile_adapter.py`
- optional new source-layer module, for example:
  - `packages/sources/lane_execution.py`
  - `packages/sources/direct_structured_execution.py`
- focused tests under `tests/test_sources_*.py`
- eval scripts under `data/tmp`, especially:
  - `data/tmp/_source_quality_live_inspection.py`
  - `data/tmp/_source_quality_routing_eval.py`
  - `data/tmp/_source_quality_batch_report.py`

Conditionally in scope after an Architecture Gate:

- `packages/sources/profiles/**` when adding narrowly scoped source profiles for blocker cases.
- `packages/agents/workflow.py` only if direct-lane execution must be surfaced in research workflow traces.

Out of scope:

- changing public API response schemas
- changing EvidenceBundle / EvidenceItem citation contracts
- replacing Tavily or Crawl4AI
- browser automation, OCR, login-gated sources
- direct investment advice or securities recommendation behavior
- full 50-case live run before the smoke gate passes
- broad source-pack expansion unrelated to the blocker cases

## Source Classes This PLAN Must Handle

| Source class | PLAN role | Primary method | Smoke pressure cases |
|---|---|---|---|
| `company_disclosure` / `enterprise_disclosure` | Direct keep | Exchange / CNINFO / listed-company disclosure profiles or explicit unsupported gap | `M02`, `M06`, `P08`, `C07`, `C09` |
| `project_list` | Direct or official structured source | Public resource, procurement, major-project, approval/filing profiles | `M02`, `M06`, `P08`, `C07`, `C09` |
| `tender_or_procurement` | Direct structured | `ccgp.gov.cn`, `ggzy.gov.cn`, local public resource profiles | `M02`, `M03`, `C09`, `P08` |
| `statistics` | Direct structured | national/provincial/local stats, customs, commerce, sector statistics | `M02`, `M06`, `P08`, `C07` |
| `environmental_or_land_record` | Strong official record | EIA, natural resources, land transfer / project approval profiles | `P08`, `C01`, `K07`, `K09`, `K12` |
| `local_government` | Search-assisted and profile-assisted | exact local official domains, city/county fallback, park/zone official sites | `C09`, `P10`, county cases |

## Blocker Cases Driving This PLAN

| Case | Current blocker | This PLAN target |
|---|---|---|
| `M02` 东数西算 / 算力网络 | enterprise disclosure, project, statistics lanes not executed | all required direct lanes are dispatched or return exact unsupported reasons |
| `M06` 房地产去库存 / 三大工程 | no evidence for policy, statistics, project, enterprise revenue | execute data/project/disclosure lanes and improve precise policy query allocation |
| `P08` 内蒙古绿电绿氢煤化工 | project and data tasks not executed; local extraction weak | execute provincial project/statistics/environment lanes with region-aware profile selection |
| `C07` 常州动力电池和光伏 | photovoltaic side missing; no relevant city-level capacity-risk evidence | preserve battery + PV query facets and execute project/disclosure/statistics lanes |
| `C09` 西安商业航天硬科技 | no city-level sources; project/disclosure not executed | add city source hints and execute project/disclosure lanes |

## Architecture Direction

### Execution State Model

Every required lane should end in one of these states:

```text
executed_with_evidence
executed_without_evidence
skipped_budget_exhausted
skipped_no_adapter
skipped_unsupported_source_class
refused_direct_keep_boundary
failed_runtime_error
```

The state must be visible in eval artifacts without changing downstream public API shapes.

### Direct Lane Semantics

Direct structured lanes remain protected primary paths.

- `search_assisted_sources` may discover supplementary context.
- `direct_structured_sources` must not be marked satisfied by Tavily-only evidence.
- If no adapter exists, return a structured gap such as:

```json
{
  "lane_id": "enterprise_disclosure",
  "reason_code": "direct_adapter_not_available",
  "required": true,
  "execution_state": "skipped_no_adapter"
}
```

### Evidence Conversion

Use existing source-layer evidence structures:

- `RawDocument`
- `NormalizedDocument`
- `EvidenceItem`
- `Citation`
- `ToolTrace`
- `ToolError`

Do not add fields to public EvidenceBundle or research analyze responses in this PLAN.

### Budget Policy

Search-assisted budgets and direct structured budgets must be tracked separately:

```text
search_budget:
  tavily_search_credits
  crawl4ai_extractions

direct_budget:
  max_direct_lanes
  max_profiles_per_lane
  max_documents_per_profile
  max_detail_fetches
```

The smoke run should not exhaust all budget on policy-direction lanes before direct lanes are attempted.

## Phase 0 Architecture Gate Result

Status: completed on 2026-04-28.

Inventory method:

- Imported `build_default_source_registry()` and listed enabled `SourceProfile` entries.
- Read `packages/sources/retrieval_plan.py`, `packages/sources/query_decomposition.py`,
  `packages/sources/registry.py`, `packages/sources/tools.py`,
  `packages/sources/profile_adapter.py`, `packages/sources/router.py`,
  `packages/sources/search_assisted_domestic.py`, and
  `data/tmp/_source_quality_live_inspection.py`.
- Confirmed current execution gap: direct structured lanes are planned as
  `direct_structured_sources`, but the live inspection execution loop still primarily
  selects search-assisted tasks and uses `SearchAssistedDomesticOrchestrator`.

Registry snapshot:

- Total profiles: 71
- Enabled profiles: 67
- Profiles with adapter entry: 71
- Enabled HTML list/detail collector profiles: 66
- Direct profile execution mechanism available: `GenericProfileSourceAdapter`
- Bundle-level execution mechanism available: `SourceToolRegistry.build_evidence_bundle`

### Coverage Lane Inventory

| Coverage lane | Source intents | Existing enabled profiles / adapters | Availability assessment | Phase 1 implication |
|---|---|---|---|---|
| `national_policy_direction` | `state_council`, `national_drc`, `national_miit` | 5 national policy/trade profiles, including `cn_policy_state_council_zcwj_v1`, `cn_policy_ndrc_tzgg_v1`, `cn_policy_miit_tzgg_v1`, `cn_policy_most_tzgg_v1`, `cn_trade_mofcom_policy_v1` | Strong profile coverage; current primary execution remains Tavily/Crawl4AI for search-assisted lanes | Do not route this through direct scheduler first; keep search-assisted path stable |
| `provincial_policy_rollout` | `province_government`, `province_drc`, `province_industry_department`, `province_commerce` | 34 provincial policy/commerce profiles across Anhui, Guangdong, Jiangsu, Zhejiang, Sichuan, Shanghai, plus selected Fujian/Henan/Hubei/Shandong DRC/industry profiles | Good partial coverage, but not full national province coverage. Inner Mongolia has resolver domains but no registered profile in this inventory | Keep as search-assisted for Phase 1; later profile updates may target `P08` |
| `city_county_fallback` | `city_government`, `city_drc`, `city_industry_department`, `city_statistics` | 7 municipal policy profiles: Shenzhen, Guangzhou, Hangzhou, Suzhou, Wuhan, Chengdu, Nanjing | Weak and sparse. No Xi'an, Changzhou, Hefei, Feixi, Shenmu, or Ruoqiang profile coverage in registry | Keep exact-local search-assisted fallback; do not claim direct city/county coverage from parent sources |
| `statistics_or_industry_data` | `national_statistics`, `national_customs`, `national_commerce`, `province_statistics`, `province_commerce`, `city_statistics` | 15 data/trade/statistics-related profiles, including NBS, customs, Anhui/GD/JS/SC/SH/ZJ statistics, and commerce profiles | Profile-backed document/list coverage exists; true structured indicator adapters are still absent. No city statistics profiles | Phase 1 can dispatch this lane through profile-backed direct execution and mark it as profile-backed, not structured-table complete |
| `project_transaction` | `public_resource_trade`, `government_procurement`, `national_drc` | 4 project profiles: `cn_project_ccgp_procurement_v1`, `cn_project_ggzy_trade_v1`, `cn_project_ndrc_approval_v1`, `cn_park_sh_lingang_tzgg_v1` | Usable first bridge coverage for procurement/public-resource/NDRC project signals; local project coverage remains weak | Phase 1 should attempt these profiles before declaring project lane unsupported |
| `enterprise_disclosure` | `exchange_disclosure` | 2 enabled profiles: `cn_exchange_cninfo_announcement_v1`, `cn_exchange_sse_notice_v1`; disabled profiles include SZSE and generic exchange examples | Usable but low precision when query has no company/ticker. Missing BSE and enabled SZSE in current registry | Phase 1 should attempt CNINFO/SSE and record `missing_company_hint` when no explicit company exists |
| `industry_association_signal` | `theme_association` | 2 enabled association profiles: CAAM and China Electronics Society; generic association profile disabled | Limited; does not cover low-altitude AOPA/UAV associations as direct profiles | Keep supplemental Tavily/Crawl4AI path; do not block Phase 1 direct lanes on this |
| `park_zone_signal` | `park_zone_official` | 1 enabled park profile: Shanghai Lingang | Very limited and not relevant for most smoke blockers | Keep search-assisted exact-local fallback; profile expansion belongs to a later source-profile plan |
| `media_news_context` | `official_media` | No dedicated official-media profile | Not available | Keep out of Phase 1 direct bridge; return unsupported if required later |
| `environmental_or_land_record` | Not represented as a dedicated `CoverageLane` / `SourceIntent` in v1 | No domestic EIA, natural resources, land-transfer, or environmental-record profile. The only inventory hit is the unrelated US EIA energy adapter | Not available as a domestic direct lane | Do not add a new `CoverageLane` in Phase 1. Represent as a `project_transaction` / regulatory sub-intent in eval metadata and return `official_record_adapter_not_available` when requested |

### Phase 0 Decisions

- Proceed to Phase 1 with a minimal lane execution bridge.
- Do not add a new public `CoverageLane` for `environmental_or_land_record` in this PLAN.
- Do not modify `packages/sources/schemas.py`, downstream API response shapes, EvidenceBundle,
  citation fields, run/task semantics, or research workflow response contracts.
- Phase 1 may introduce an internal source-layer module such as
  `packages/sources/lane_execution.py`; it may update
  `data/tmp/_source_quality_live_inspection.py` to record direct lane attempts.
- Phase 1 may add focused tests under `tests/test_sources_lane_execution.py` or existing
  `tests/test_sources_*.py`.
- Phase 1 must not edit `packages/sources/profiles/**` yet; missing profiles must be recorded
  as `skipped_no_adapter` or `skipped_unsupported_source_class`.

Protected contract assessment:

- No public schema change is required for Phase 1.
- Direct lane execution states are internal/eval metadata only.
- Existing `SourceRegistry`, `SourceToolRegistry`, `ToolResponse`, `ToolTrace`,
  `RawDocument`, `NormalizedDocument`, `EvidenceItem`, and `ToolError` contracts are sufficient
  for the first bridge.

## Milestones

### Phase 0: Architecture Gate and Existing Adapter Inventory

Objective:

- Freeze exact implementation scope before code changes.
- Inventory existing adapters/profiles that can serve direct structured lanes.

Tasks:

- Map `CoverageLane` -> `SourceIntent` -> `SourceProfile` / adapter availability.
- Identify which blocker source classes can be handled by existing `SourceRegistry` and `GenericProfileSourceAdapter`.
- Decide whether `environmental_or_land_record` requires a new `CoverageLane` or can be represented as a `PROJECT_TRANSACTION` sub-intent in v1.
- Freeze write scope for Phase 1.

Acceptance criteria:

- PLAN contains a completed inventory table.
- No production code changed in Phase 0.
- Protected contract impact is explicitly assessed.

Validation:

```powershell
Select-String -Path .agent\PLANS\source-direct-structured-execution-v1.md,.agent\STATUS.md -Pattern "source-direct-structured-execution-v1","Phase 0","direct structured"
```

### Phase 1: Lane Execution Contract and Scheduler

Objective:

- Add an internal execution contract that dispatches required lanes instead of silently filtering to search-assisted tasks.

Likely write scope:

- optional new module `packages/sources/lane_execution.py`
- `packages/sources/retrieval_plan.py`
- `data/tmp/_source_quality_live_inspection.py`
- focused tests

Tasks:

- Define internal lane execution result model.
- Dispatch search-assisted lanes through the existing orchestrator.
- Dispatch direct structured lanes through `SourceIntelligenceService` / `SourceToolRegistry` where possible.
- Return structured unsupported gaps where no adapter exists.
- Add direct/search budget metadata to eval artifacts.

Acceptance criteria:

- Required direct lanes appear in live inspection as executed or explicitly unsupported.
- No direct lane is silently omitted because `include_non_search_gates` is false.
- `M02` inspection artifact records attempts for `enterprise_disclosure`, `project_transaction`, and `statistics_or_industry_data`.

Validation:

```powershell
pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_search_assisted_domestic.py
pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\direct_exec_phase1_smoke --print-json
```

### Phase 2: Project / Procurement / Public Resource Lane

Objective:

- Make `project_transaction` lane execution useful enough for smoke validation.

Target source classes:

- `project_list`
- `tender_or_procurement`
- project approval / filing where existing profiles support it

Target cases:

- `M02`
- `P08`
- `C09`
- `C07`

Tasks:

- Route project lane to available procurement/public-resource/major-project profiles.
- Add region-aware query terms for macro/province/city cases.
- Preserve direct structured semantics: no Tavily-only satisfaction.
- Surface no-adapter or no-result conditions as source-class gaps.

Acceptance criteria:

- `M02`, `P08`, and `C09` artifacts show project lane attempted.
- At least one project/procurement lane produces a document or a precise `no_result` trace.
- DeepSeek audit no longer flags "project lane not executed" as a blocker for `M02`.

Validation:

```powershell
pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py
pytest -q tests\test_sources_retrieval_plan.py
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\direct_exec_phase2_smoke --print-json
```

### Phase 3: Statistics / Data Metrics Lane

Objective:

- Make `statistics_or_industry_data` lane executable and auditable.

Target source classes:

- `statistics`
- official data portals
- customs/commerce where query includes trade/export
- local statistics where city/county or province is explicit

Target cases:

- `M02`
- `M06`
- `P08`
- `C07`

Tasks:

- Map statistics lane to national/province/city stats profiles where available.
- Add exact local-statistics source hints for blocker regions.
- Keep data freshness and source-class metadata visible in eval artifacts.
- Return structured gap if the data path is known but unavailable.

Acceptance criteria:

- `M02` and `M06` artifacts show statistics lane attempted.
- `P08` artifact shows province-level statistics/data source attempts.
- DeepSeek audit no longer reports "statistics task not executed" for `M02`.

Validation:

```powershell
pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_source_resolver.py
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\direct_exec_phase3_smoke --print-json
```

### Phase 4: Enterprise Disclosure Lane

Objective:

- Make `enterprise_disclosure` lane executable as a direct structured control path.

Target source classes:

- `company_disclosure`
- `enterprise_disclosure`
- exchange/CNINFO/IR profiles when available

Target cases:

- `M02`
- `M06`
- `P08`
- `C07`
- `C09`

Tasks:

- Inventory existing domestic disclosure profiles.
- Dispatch disclosure lane through direct profiles.
- If query has no explicit company, use theme/region/company-discovery phrases but keep confidence lower.
- Do not output direct securities investment advice.
- Keep search-assisted company pages as supplementary only.

Acceptance criteria:

- Disclosure lane is attempted for all five blocker cases.
- Missing company name is recorded as a retrieval limitation, not fabricated.
- DeepSeek audit no longer reports "enterprise disclosure lane not executed" for `M02`.

Validation:

```powershell
pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_search_assisted_domestic.py
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\direct_exec_phase4_smoke --print-json
```

### Phase 5: Environmental / Land / Regulatory Records

Objective:

- Represent environmental/land record needs explicitly enough for source-quality eval and future adapter work.

Target source classes:

- `environmental_or_land_record`
- `regulatory_record`
- EIA / natural resources / land transfer / project approval

Target cases:

- `P08`
- `K07`
- `K09`
- `K12`
- `C01`

Tasks:

- Decide whether to add a new source-layer lane or encode this as a project/regulatory sub-intent.
- Add source-class metadata and expected source intent to retrieval/eval artifacts.
- Route to available environment/natural-resource profiles if present.
- Otherwise return structured gap `official_record_adapter_not_available`.

Acceptance criteria:

- Environmental/land record needs are no longer only inferred by LLM audit.
- `P08` artifact records environmental/land lane or sub-intent status.
- No downstream public contract changes.

Validation:

```powershell
pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_source_resolver.py
python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\direct_exec_phase5_routing --print-json
```

### Phase 6: Lane Budget and Execution Priority

Objective:

- Prevent policy/search-assisted lanes from consuming the execution budget before direct lanes are attempted.

Tasks:

- Add per-lane execution caps.
- Guarantee all required lanes receive at least one attempt before optional lanes.
- Track skipped lanes with reason and budget state.
- Keep Tavily credit controls separate from direct execution limits.

Acceptance criteria:

- Required direct lanes are attempted before optional association/media context lanes.
- `C07` includes both battery and photovoltaic facets in search/direct phrases.
- `C09` keeps city-level execution attempts.

Validation:

```powershell
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\direct_exec_phase6_smoke --print-json
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\direct_exec_phase6_smoke --print-json
```

### Phase 7: Smoke Audit and Full-Run Gate

Objective:

- Re-run the 12-case smoke set and decide whether the 50-case live eval is cost-justified.

Tasks:

- Run routing smoke.
- Run live smoke.
- Run DeepSeek audit with `--resume`.
- Generate batch roadmap.
- Compare against remediation baseline.

Acceptance criteria:

- Live smoke remains `12 success / 0 runtime error`.
- DeepSeek blocker count is reduced from `5` to `<=2`.
- No blocker reason says "critical source lanes were not executed".
- Remaining blockers are true source scarcity or adapter-not-available issues, not scheduler omissions.
- Full 50-case live eval is allowed only if the above passes.

Validation:

```powershell
python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\direct_exec_final_routing --print-json
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\direct_exec_final_live --print-json
python data\tmp\_source_quality_llm_audit.py --run-dir data\tmp\source_quality_stress_eval\runs\direct_exec_final_live --provider deepseek --model deepseek-v4-pro --thinking enabled --reasoning-effort max --resume --print-summary
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\direct_exec_final_live --print-json
```

## Validation Loop

For each implementation phase:

1. Add focused failing tests or an eval assertion for the exact blocker.
2. Implement the smallest coherent source-layer change.
3. Run focused ruff / py_compile / pytest.
4. Run the phase smoke command.
5. Update PLAN and STATUS with:
   - what changed
   - validation result
   - remaining blockers
   - next phase

Required source-layer checks when production source files change:

```powershell
python -m ruff check packages\sources\*.py tests\test_sources_*.py
pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py
pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py
```

Known caveat:

- Repo-wide `python -m ruff check .` has historical `data/tmp` debt. Focused checks for touched files must pass; repo-wide failures must be recorded if still unrelated.

## Agent Execution Contract

If the user says "执行 PLAN" or equivalent:

1. Group 1 / director performs Phase 0 Architecture Gate and writes the inventory into this PLAN.
2. Group 2 `source_provider_integrator` owns source-layer execution bridge and direct lane implementation.
3. Group 2 `eval_harness_implementer` owns live inspection / audit harness updates.
4. Group 3 `invest_code_quality_checker` validates focused ruff, compile, and pytest.
5. Group 3 `invest_functional_validator` validates smoke artifacts against this PLAN.
6. Summarizer runs only after the done condition is reached.

In this session, Codex may execute locally without spawning subagents unless the user explicitly asks for subagent delegation.

## Continue Rule

After each milestone, continue automatically to the next milestone when:

- acceptance criteria are met
- required validation passes
- no approval, permission, dependency, or human-review blocker exists
- no high-risk contract change is needed outside this PLAN
- no live API cost escalation exceeds the smoke budget

Do not treat "phase summary" as a default stop point.

## Stop Conditions

Stop and ask for guidance when:

- a phase requires changing EvidenceBundle/API/task/run semantics
- a direct adapter requires login, OCR, browser automation, or paid/private API access
- Tavily/DeepSeek cost becomes unexpectedly high
- live source sites block access in a way that cannot be represented as structured partial failure
- adding environmental/land coverage requires a new public contract rather than source-layer metadata
- validation fails and the repair path is not narrow

## Done Condition

This PLAN is done when:

- Direct structured required lanes are no longer silently skipped.
- `M02`, `M06`, `P08`, `C07`, and `C09` have visible direct-lane execution attempts.
- Live smoke remains `12 success / 0 runtime error`.
- DeepSeek blocker count is `<=2`.
- Remaining failures are explicit source scarcity or adapter-not-available gaps.
- The full 50-case live run decision is recorded with cost/quality rationale.
- STATUS and PLAN include validation, risks, next action, and two before/after behavior examples.

## Risks

- Some direct structured sources may require site-specific adapters; v1 must not hide this behind fake success.
- Querying exchange disclosures without a company name is inherently low precision; record this as a limitation.
- Project/procurement platforms are heterogeneous; first implementation may return partial results.
- Environmental/land records may need a new source-layer lane in a later PLAN.
- DeepSeek audit can produce invalid JSON when output is too long; use `--resume` and preserve invalid diagnostics.
- Dirty worktree remains broad; scope proof must rely on plan/file review and focused checks.

## Rollback

- Revert only files touched by this PLAN.
- Do not revert unrelated dirty worktree changes.
- If lane execution bridge destabilizes existing search-assisted behavior, disable the bridge behind eval-harness scope first.
- If direct structured execution causes schema drift, stop and restore the previous source-layer gap-only behavior.

## Progress

- 2026-04-28: PLAN created from remediation smoke artifacts. No production code changed. Initial design freezes the next work as direct structured lane execution and evidence coverage, not broad source expansion.
- 2026-04-28: Planning validation completed. Confirmed PLAN exists and `.agent/STATUS.md` / `.agent/PLANS/INDEX.md` point to this PLAN. `git status --short -- .agent packages data\tmp tests` still shows broad pre-existing dirty/untracked workspace state, so future implementation phases must use focused file-scope review rather than assuming a clean git baseline.
- 2026-04-28: Cleaned `.agent/STATUS.md` so earlier Crawl4AI remediation results are not recorded as progress for this PLAN. This PLAN remains `planned`; Phase 0 has not started.
- 2026-04-28: Phase 0 Architecture Gate completed. Inventory found 71 registered profiles, 67 enabled profiles, profile-backed coverage for project/statistics/disclosure lanes, sparse city/county coverage, and no domestic environmental/land-record direct profile. Phase 1 is authorized to add an internal lane execution bridge and eval-script integration without changing public EvidenceBundle/API contracts.
- 2026-04-28: Phase 1 implementation completed. Added `packages/sources/lane_execution.py` as an internal direct structured lane bridge, updated `data/tmp/_source_quality_live_inspection.py` so direct structured tasks are executed even when search tasks are capped, and added focused lane execution tests. No public EvidenceBundle/API/citation/task/run contracts changed.
- 2026-04-28: Phase 1 TDD remediation completed for `M02`. Initial low-cost smoke showed `M02` attempted enterprise disclosure and statistics lanes but missed project transaction because national computing queries suppressed project lanes. Added a failing regression test, then updated `packages/sources/query_decomposition.py` so explicit requests for `地方项目清单` / `项目清单` / `建设需求` keep `project_transaction` even when the query is national-level.
- 2026-04-28: Phase 1 validation snapshot:
  - `pytest -q tests\test_sources_lane_execution.py` -> `3 passed`
  - `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_search_assisted_domestic.py tests\test_sources_lane_execution.py` -> `75 passed`
  - `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`
  - `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`
  - `python -m ruff check packages\sources\*.py tests\test_sources_*.py` -> pass
  - Focused ruff/py_compile for touched source/test/eval files -> pass
  - `python -m ruff check .` -> fails only on known historical `data/tmp` scratch/demo lint debt, not touched Phase 1 files
  - Live smoke `data/tmp/source_quality_stress_eval/runs/direct_exec_phase1_smoke` -> `12 success / 0 error`, estimated Tavily credits `12`, `query_invalid_count=0`
  - Direct-only M02 smoke `data/tmp/source_quality_stress_eval/runs/direct_exec_phase1_m02_direct_only` -> `1 success / 0 error`, estimated Tavily credits `0`; `project_transaction`, `enterprise_disclosure`, and `data_metrics` all reached `executed_with_evidence`
- 2026-04-28: Phase 2 project/procurement lane remediation completed. Added Xi'an/Shaanxi regional routing hints, added `商业航天` / `硬科技` theme recognition, and filtered generic homepage/list-page documents from project direct lanes so `ccgp.gov.cn` homepages no longer count as project evidence.
- 2026-04-28: Phase 2 validation snapshot:
  - `pytest -q tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py` -> `61 passed`
  - `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`
  - `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`
  - `python -m ruff check packages\sources\*.py tests\test_sources_*.py` -> pass
  - Focused py_compile for touched source/test/eval files -> pass
  - Project direct-only smoke `data/tmp/source_quality_stress_eval/runs/direct_exec_phase2_project_direct_only_v2` -> `3 success / 0 error`, estimated Tavily credits `0`; `M02`, `P08`, and `C09` all attempted project lanes and returned `executed_without_evidence` with `weak_document_rejections` instead of false homepage evidence.
- 2026-04-28: Phase 3 statistics/data metrics lane remediation completed. Added data-metrics preservation for disclosure/direct-keep queries that explicitly request price, capacity, scale, statistics, or data evidence; added Inner Mongolia statistics profile `cn_data_nmg_stats_bulletin_v1`; changed data lane source ordering to prefer regional statistics profiles before national statistics; and filtered generic statistics homepages such as `stats.gov.cn/english/` from valid evidence.
- 2026-04-28: Phase 3 validation snapshot:
  - `pytest -q tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_source_resolver.py` -> `73 passed`
  - `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`
  - `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`
  - `python -m ruff check packages\sources\*.py tests\test_sources_*.py` -> pass
  - Focused ruff/py_compile for touched source/test files -> pass
  - `python -m ruff check .` -> fails only on known historical `data/tmp` scratch/demo lint debt, not touched Phase 3 files
  - Statistics direct-only smoke `data/tmp/source_quality_stress_eval/runs/direct_exec_phase3_stats_direct_only` -> `4 success / 0 error`, estimated Tavily credits `0`; `M02`, `M06`, `P08`, and `C07` all generated or executed `data_metrics` lanes. `M02`/`M06`/`P08` returned `executed_without_evidence` with generic statistics homepage rejections instead of false evidence. `P08` attempted `cn_data_nmg_stats_bulletin_v1` before national statistics. `C07` attempted Jiangsu statistics/commerce profiles and recorded HTTP 403 runtime errors as structured failures.
- 2026-04-28: Phase 4 enterprise disclosure lane remediation completed. Added query-decomposition preservation for enterprise disclosure when blocker queries ask for enterprise revenue, orders, investment, downstream demand, local funds, or company evidence; tightened weak disclosure filtering so CNINFO generic homepages and SSE non-disclosure party-building pages no longer count as valid company disclosure evidence; and changed generic `上市公司` wording to a missing-company limitation instead of a company hint.
- 2026-04-28: Phase 4 validation snapshot:
  - `pytest -q tests\test_sources_lane_execution.py -k disclosure_lane_rejects` -> `1 passed`
  - `pytest -q tests\test_sources_query_decomposition.py -k disclosure_control_lane` -> `1 passed`
  - `pytest -q tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_search_assisted_domestic.py` -> `82 passed`
  - `python -m ruff check packages\sources\lane_execution.py packages\sources\query_decomposition.py packages\sources\profiles\china_scaleout.py tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py` -> pass after fixing two line-length issues
  - Focused py_compile for touched source/test files -> pass
  - `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`
  - `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`
  - `python -m ruff check packages\sources\*.py tests\test_sources_*.py` -> pass
  - `python -m ruff check .` -> fails only on known historical `data/tmp` scratch/demo lint debt, not touched Phase 4 files
  - Disclosure direct-only smoke `data/tmp/source_quality_stress_eval/runs/direct_exec_phase4_disclosure_direct_only` -> `5 success / 0 error`, estimated Tavily credits `0`, average latency `2776.86 ms`, `query_invalid_count=0`; `M02`, `M06`, `P08`, `C07`, and `C09` all generated and attempted `enterprise_disclosure` lanes. Each lane ended as `executed_without_evidence` with `missing_company_hint=true`, `document_count=0`, `rejected_document_count=2`, and weak-document rejections for CNINFO `首页` (`generic_disclosure_homepage`) and SSE `党建动态` (`non_disclosure_page`) instead of false evidence.
- 2026-04-28: Phase 5 environmental / land / regulatory record visibility completed. Added deterministic official-record need detection for EIA, natural-resources, land-transfer, project-filing, land, energy-consumption, project-approval, and filing queries. No new public `CoverageLane`, EvidenceBundle, citation, API, task, or run contract was introduced.
- 2026-04-28: Phase 5 implementation details:
  - `QueryDecomposition.unsupported_or_missing_sources` now records when environmental / land / regulatory records may need dedicated adapters.
  - `RetrievalPlan.coverage_gaps` now records `official_record_adapter_not_available` on the existing `project_transaction` lane with `fallback_source=environmental_or_land_record` and notes for `environmental_or_land_record` / `regulatory_record`.
  - `data/tmp/_source_quality_live_inspection.py` now writes a compact `retrieval_plan` section containing coverage lanes, coverage gaps, and planner metadata, so live artifacts can expose official-record gaps without changing downstream product contracts.
  - Added Phase 5 smoke case file `data/tmp/source_quality_stress_eval/smoke_official_records_phase5.json` for `P08`, `K07`, `K09`, `K12`, and `C01`.
- 2026-04-28: Phase 5 validation snapshot:
  - RED tests first failed for missing official-record visibility in retrieval plan and query decomposition.
  - `pytest -q tests\test_sources_retrieval_plan.py -k environmental_land_record` -> `1 passed`
  - `pytest -q tests\test_sources_query_decomposition.py -k environmental_land_record` -> `1 passed`
  - `pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py tests\test_sources_lane_execution.py tests\test_sources_search_assisted_domestic.py` -> `84 passed`
  - `python -m py_compile packages\sources\retrieval_plan.py packages\sources\query_decomposition.py data\tmp\_source_quality_live_inspection.py tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py` -> pass
  - Focused ruff for touched source/test/eval files -> pass
  - Source regression pytest -> `27 passed`
  - Domestic source pytest -> `16 passed`
  - `python -m ruff check packages\sources\*.py tests\test_sources_*.py` -> pass
  - `python -m ruff check .` -> fails only on known historical `data/tmp` scratch/demo lint debt, not touched Phase 5 files
  - Routing smoke `data/tmp/source_quality_stress_eval/runs/direct_exec_phase5_routing` -> `5 pass / 0 fail`; all `P08`, `K07`, `K09`, `K12`, and `C01` artifacts include `official_record_adapter_not_available` with `fallback_source=environmental_or_land_record`
  - Direct-only live artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_phase5_official_records_direct_only` -> `4 success / 1 error`, estimated Tavily credits `0`; `P08`, `K09`, `K12`, and `C01` succeeded and include the retrieval-plan official-record gap. `K07` has the same gap in the artifact but no selected direct task under `--max-search-tasks 0` because query decomposition currently emits only `local_rollout`; this is recorded as a Phase 6 lane scheduling input, not a Phase 5 contract failure.
- 2026-04-28: Phase 6 first remediation completed for the `K07` empty direct-only execution issue. Park/city holdout remains local-only for generic park policy queries, but if a park/county query explicitly asks for project clusters, real projects, land, enterprise evidence, announcements, statistics, capacity, prices, or labor data, query decomposition now preserves direct control lanes (`project_transaction`, `enterprise_disclosure`, and `data_metrics` where applicable).
- 2026-04-28: Phase 6 scheduling update:
  - `data/tmp/_source_quality_live_inspection.py` now orders direct structured tasks before capped search-assisted tasks, keeping Tavily search budget separate from direct lane attempts.
  - Direct-first selection was validated from the UTF-8 C01 case file; selected task order became `enterprise_disclosure`, `project_transaction`, then `local_rollout`.
  - Direct-only live artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_phase6_official_records_direct_only` -> `5 success / 0 error`, estimated Tavily credits `0`, average latency `2659.15 ms`; this fixes the previous K07 `0 selected direct task` artifact failure.
- 2026-04-28: Phase 6 partial validation snapshot:
  - RED test first failed for K07 because decomposition returned only `local_rollout`.
  - `pytest -q tests\test_sources_query_decomposition.py -k county_park_cluster` -> failed before remediation, then passed after remediation.
  - `pytest -q tests\test_sources_query_decomposition.py -k "park or county_park_cluster or hefei_city or changzhou_capacity"` -> `6 passed`
  - `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_lane_execution.py tests\test_sources_search_assisted_domestic.py` -> `85 passed`
  - `python -m ruff check data\tmp\_source_quality_live_inspection.py packages\sources\query_decomposition.py tests\test_sources_query_decomposition.py` -> pass
  - `python -m py_compile data\tmp\_source_quality_live_inspection.py packages\sources\query_decomposition.py tests\test_sources_query_decomposition.py` -> pass
  - Inline C01 task-order validation initially failed when Chinese text was passed through a PowerShell here-string; rerunning from the UTF-8 case file passed. This re-confirms the existing Windows validation rule: use UTF-8 files or escaped strings for Chinese live checks.
- 2026-04-28: Phase 6 final remediation completed after the first full low-cost smoke exposed remaining scheduler/decomposition gaps for `M06` and `C07`.
  - Added RED/GREEN regressions so `M06` real-estate / three-projects queries and `C07` Changzhou capacity-risk queries preserve `project_transaction` when they ask for `开工`, `投产`, `资金来源`, `项目备案`, or `土地项目` evidence.
  - `packages/sources/query_decomposition.py` now treats these terms as project execution evidence requests in both generic decomposition and disclosure-direct-keep branches.
  - Direct-only artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_phase6_smoke_direct_only_v2` -> `12 success / 0 error`, estimated Tavily credits `0`; `M06` and `C07` now execute `project_transaction`.
  - Low-cost live artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_phase6_smoke_lowcost_v2` -> `12 success / 0 error`, estimated Tavily credits `12`, average latency `14804.15 ms`, `query_invalid_count=0`.
  - Batch report `data/tmp/source_quality_stress_eval/runs/direct_exec_phase6_smoke_lowcost_v2/batch_eval.json` -> `12 success`, no runtime blockers, no routing failures, no citation/compliance failures in the non-LLM batch layer.
  - Blocker-driving cases `M02`, `M06`, `P08`, `C07`, and `C09` all show required direct-lane execution attempts or structured runtime/no-evidence states; no required direct lane is silently skipped in the final Phase 6 artifact.
  - Validation: RED tests failed first, then `pytest -q tests\test_sources_query_decomposition.py -k "startup_and_ramp or three_projects"` -> `2 passed`; focused query/retrieval/lane/search-assisted pytest -> `87 passed`; source regression pytest -> `27 passed`; domestic source pytest -> `16 passed`; focused source/test ruff and py_compile -> pass.
  - `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt, not touched Phase 6 files.
- 2026-04-28: Phase 7 smoke audit and full-run gate executed. The gate did not pass, so the full 50-case live run remains blocked.
  - Routing smoke artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_final_routing` -> `8 pass / 4 weak_pass`, `0 fail`, `0 blocker`; weak passes are expected-lane coverage gaps, not runtime failures.
  - Live smoke artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_final_live` -> `12 success / 0 runtime error`, estimated Tavily credits `20`, average latency `29012.79 ms`, `query_invalid_count=0`.
  - DeepSeek audit on `direct_exec_final_live` -> `7 success / 5 invalid_json`, verdicts `3 blocker / 9 fail`, total tokens `202538`.
  - Batch report `data/tmp/source_quality_stress_eval/runs/direct_exec_final_live/batch_eval.json` confirms blockers: `K07`, `M03`, and `M06`.
  - The remaining blockers are not silent direct-lane scheduling omissions. They are source coverage / adapter / source-profile issues: county project-land-EIA-company coverage for `K07`, aviation regulator / airspace / airworthiness / pilot-source coverage for `M03`, and macro real-estate project-statistics-disclosure evidence for `M06`.
  - Main missing source classes remain `company_disclosure` (`11`), `project_list` (`11`), `statistics` (`8`), `environmental_or_land_record` (`5`), and `local_government` (`3`).
  - Full 50-case live eval decision: deferred. The PLAN stop condition is triggered because DeepSeek blocker count is `3`, above the `<=2` gate.

## Next Action

Open a follow-up remediation PLAN focused on source profile / adapter coverage for the remaining blockers before spending budget on the full 50-case live run. Recommended scope: `K07`, `M03`, `M06`, source-profile entry points, county official records, aviation regulator sources, macro statistics/project/disclosure evidence, and DeepSeek invalid-JSON robustness.
