# Plan: Source Profile Adapter Remediation v1

Status: blocked_handoff_to_source_evidence_coverage_remediation_v1
Priority: high
Owner: codex/human
Scope: source profile, source adapter entry points, source routing precision, and source-quality smoke blocker remediation
Created: 2026-04-28
Last Updated: 2026-04-28

## Objective

Reduce the remaining Source Direct Structured Execution v1 Phase 7 DeepSeek smoke blockers from `3` to `<=2` before any full 50-case live source-quality run.

This PLAN is deliberately narrower than broad source expansion. It targets the three remaining blocker cases from:

```text
data/tmp/source_quality_stress_eval/runs/direct_exec_final_live/batch_eval.json
```

Current blocker baseline:

| Case | Blocker diagnosis | Required remediation direction |
|---|---|---|
| `K07` | County-level Feixi NEV cluster query lacks county project, land/EIA, and company-disclosure coverage. | Add or improve exact local source-profile/search entry points for county official projects, Feixi/Hefei official records, and direct-lane evidence transparency. |
| `M03` | Low-altitude economy macro query lacks aviation regulator, airspace reform, airworthiness, infrastructure, local pilot, and enterprise-order evidence. | Add CAAC/aviation regulator discovery, low-altitude-specific source routing, and search/direct lane query facets. |
| `M06` | Macro real-estate demand query lacks central policy/statistics/project/company-disclosure evidence; current evidence is too local or generic. | Improve macro source targeting for central policy, statistics, three-projects, housing-stock, construction-start, and enterprise revenue evidence. |

Primary success target:

```text
12-case smoke audit: blocker_count <= 2
```

Secondary success target:

```text
No blocker caused by silent lane omission, invalid JSON handling, or source-level mismatch that can be fixed inside this PLAN's scope.
```

## Task Classification

Primary area: `source_layer`

Secondary areas:

- `domestic_source_collectors`
- `eval_policy_ops`
- `provider_layer`

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

## Scope

In scope:

- blocker-targeted source profile additions or profile updates under `packages/sources/profiles/**`
- blocker-targeted routing/decomposition adjustments in:
  - `packages/sources/query_decomposition.py`
  - `packages/sources/source_resolver.py`
  - `packages/sources/retrieval_plan.py`
  - `packages/sources/lane_execution.py`
  - `packages/sources/search_assisted_domestic.py`
- eval harness robustness in:
  - `data/tmp/_source_quality_live_inspection.py`
  - `data/tmp/_source_quality_llm_audit.py`
  - `data/tmp/_source_quality_batch_report.py`
- focused regression tests under `tests/test_sources_*.py`
- new smoke case files under `data/tmp/source_quality_stress_eval/` for the three blocker cases

Out of scope:

- full 50-case live source-quality run before the 12-case audit gate passes
- public API response shape changes
- EvidenceBundle / citation schema changes
- browser automation, OCR, login-gated sources, or private APIs
- broad national/provincial/city/county source-pack expansion unrelated to `K07`, `M03`, `M06`
- direct securities investment advice or buy/sell/hold output behavior

## Architecture Direction

Use targeted source-profile and routing remediation, not another orchestration refactor.

Chosen approach:

```text
Blocker audit
  -> exact missing source class inventory
  -> targeted source profile / resolver / query facet updates
  -> direct lane and search-assisted inspection
  -> DeepSeek audit robustness check
  -> 12-case blocker gate
```

The previous PLAN already fixed the major execution problem:

```text
required direct lanes now execute or return structured no-evidence/runtime states.
```

This PLAN should therefore focus on:

- better candidate source entry points
- better query facets for source discovery
- better profile-backed evidence retrieval where cheap and deterministic
- better invalid-JSON handling in the audit harness so real source blockers are not confused with parser failures

## Phase 0 Director Gate Result

Completed: 2026-04-28

Director scope:

- Planning-only gate. No production code is authorized or modified in Phase 0.
- Current hard set remains `K07`, `M03`, and `M06`.
- Full 50-case live source-quality run remains blocked until the 12-case smoke audit gate reaches `<=2` blockers.

Artifact inventory used:

- `data/tmp/source_quality_stress_eval/runs/direct_exec_final_live/batch_eval.json`
- `data/tmp/source_quality_stress_eval/runs/direct_exec_final_live/source_roadmap.json`
- `data/tmp/source_quality_stress_eval/runs/direct_exec_final_live/per_query/K07.json`
- `data/tmp/source_quality_stress_eval/runs/direct_exec_final_live/per_query/M03.json`
- `data/tmp/source_quality_stress_eval/runs/direct_exec_final_live/per_query/M06.json`

Existing profile / adapter coverage:

- Domestic profile inventory currently reports `67` profiles, `63` enabled profiles.
- Existing useful profiles include national policy (`cn_policy_state_council_zcwj_v1`, `cn_policy_ndrc_tzgg_v1`, `cn_policy_miit_tzgg_v1`, `cn_policy_most_tzgg_v1`), Anhui provincial policy/statistics/commerce (`cn_policy_ah_*`, `cn_data_ah_stats_bulletin_v1`, `cn_trade_ah_commerce_policy_v1`), national project backbones (`cn_project_ccgp_procurement_v1`, `cn_project_ggzy_trade_v1`, `cn_project_ndrc_approval_v1`), national data (`cn_data_stats_national_v1`, `cn_data_customs_trade_v1`, `cn_trade_mofcom_policy_v1`), and exchange disclosure (`cn_exchange_cninfo_announcement_v1`, `cn_exchange_sse_notice_v1`, `cn_exchange_szse_notice_v1`).
- Resolver/domain hints already know `hefei.gov.cn`, `fgw.hefei.gov.cn`, `jxj.hefei.gov.cn`, `tjj.hefei.gov.cn`, and `ahfeixi.gov.cn`; however `K07` still decomposed to municipal Hefei focus in the latest artifact.
- Low-altitude theme hints exist in `retrieval_plan.py` / `source_resolver.py`, but current supplemental domains are association-style (`aopa.org.cn`, `china-uav.cn`, `caai.cn`) rather than regulator / CAAC official profiles.
- No current domestic direct profile covers county land transfer, EIA, natural-resources, or project-filing records. The existing behavior correctly records `official_record_adapter_not_available`.
- No current profile is dedicated to CAAC, airspace reform, airworthiness certification, or aviation regulator notices.
- No current profile is dedicated to MOHURD / real-estate policy notices or real-estate construction-start / inventory statistics beyond generic national statistics pages.

Exact blocker inventory:

| Case | Current observed gap | Minimal repair direction |
|---|---|---|
| `K07` | Expected source classes are local government, project list, environmental/land record, and company disclosure. Latest artifact used Hefei/Anhui search-assisted policy, national CCGP/GGZY project profiles, national stats/customs, and generic exchange disclosure. Project/data/disclosure direct lanes returned `executed_without_evidence`; CC globally returned generic homepage evidence that was rejected; `official_record_adapter_not_available` and exact-local parent-fallback gaps are visible. | Repair Feixi-first decomposition and resolver scoping; add or tune exact county search facets for `ahfeixi.gov.cn`, Hefei/Feixi public-resource/project pages, and parent-fallback labeling. Keep land/EIA as explicit unsupported gap unless a narrow static profile is proven. Do not treat Anhui/Hefei parent material as county proof. |
| `M03` | Expected source classes include official policy, regulatory record, project/procurement, and company disclosure. Latest decomposition selected only policy, disclosure, and data tasks; `project_transaction` is present as a retrieval coverage gap but was not executed. No CAAC / aviation regulator domain or profile is selected. Policy evidence came from NDRC and a local Baotou page, not airspace reform or airworthiness authority. Disclosure has missing company hint; data lane hit generic stats homepage plus customs SSL failure. | Add low-altitude regulator/query facets: CAAC, airspace reform, airworthiness, infrastructure, local pilots, and enterprise orders. Ensure `project_transaction` is selected/executed for low-altitude infrastructure/procurement questions. Prefer regulator official domains before association supplement. |
| `M06` | Expected source classes are official policy, statistics, project list, and company disclosure. Latest policy search allowed broad `gov.cn`/MIIT/MOST/NDRC and accepted local Shenzhen/Guangxi materials; MOHURD was not targeted. Local rollout created an exact-local gap that is not useful for macro national validation. Project/data/disclosure direct lanes returned no usable evidence, generic homepages, or SSL errors. | Normalize the real-estate theme into focused facets: destocking, urban village renovation, three major projects, local acquisition/storage, starts/completions/sales/inventory, and downstream demand. Enforce central policy/source domains (`www.gov.cn`, `ndrc.gov.cn`, `mohurd.gov.cn`, `stats.gov.cn`) before arbitrary local portals. Keep project/data/disclosure lanes visible and reject generic homepages. |

Phase 1 minimal write scope:

- `data/tmp/_source_quality_llm_audit.py`
- `data/tmp/_source_quality_batch_report.py` only if the audit parser result shape needs reporting visibility
- `data/tmp/source_quality_stress_eval/smoke_blockers_profile_remediation_v1.json`
- focused tests or compile-only checks for the audit parsing helper

Phase 1 must not modify `packages/sources/**`, public schemas, source routing, source profiles, provider abstractions, API response shapes, task semantics, or EvidenceBundle/citation contracts.

## Real-world Validation Plan

Use real artifacts and official-source behavior, not synthetic success criteria.

Blocker fixture:

- Verify or create `data/tmp/source_quality_stress_eval/smoke_blockers_profile_remediation_v1.json` containing only `K07`, `M03`, and `M06` copied from the established smoke set.
- This fixture is the low-cost gate before any 12-case audit rerun.

Per-case validation expectations:

- `K07`: per-query artifact must show county-first Feixi/Hefei routing attempts, `ahfeixi.gov.cn` retained where applicable, parent fallback marked as parent/fallback rather than exact county proof, project/public-resource attempts visible, and land/EIA records either evidenced by a narrow static official profile or left as `official_record_adapter_not_available`.
- `M03`: per-query artifact must show CAAC / aviation-regulator discovery or a precise unsupported gap; query facets must include airspace reform, airworthiness certification, infrastructure/project procurement, local pilots, and enterprise-order/company-disclosure signals; `project_transaction` must not remain only a coverage gap.
- `M06`: per-query artifact must show central policy and statistics priority for real-estate demand transmission; accepted policy evidence must not be only arbitrary local portals; project/data/disclosure lanes must attempt specific entry points and reject generic homepages.

Low-cost validation commands:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

python -m py_compile data\tmp\_source_quality_llm_audit.py data\tmp\_source_quality_batch_report.py

pytest -q tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_source_resolver.py

python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\smoke_blockers_profile_remediation_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\profile_remediation_blockers_routing --print-json

python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_blockers_profile_remediation_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\profile_remediation_blockers_live --print-json
```

Direct-lane validation command after source/profile changes:

```powershell
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_blockers_profile_remediation_v1.json --mode extraction_inspection --max-search-tasks 0 --max-rounds 1 --max-candidates 2 --output-dir data\tmp\source_quality_stress_eval\runs\profile_remediation_blockers_direct_only --print-json
```

Final 12-case gate commands remain:

```powershell
python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\profile_remediation_final_routing --print-json
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\profile_remediation_final_live --print-json
python data\tmp\_source_quality_llm_audit.py --run-dir data\tmp\source_quality_stress_eval\runs\profile_remediation_final_live --print-json
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\profile_remediation_final_live --print-json
```

Pass criteria:

- The 3-case blocker fixture has no runtime errors and records exact lane attempts/gaps.
- The 12-case final live run has `12 success / 0 runtime error`.
- The 12-case audit has `blocker_count <= 2`.
- No remaining blocker is caused by invalid JSON parser failure, silent direct-lane omission, broad local/government source mismatch, or generic homepage evidence.

## Agent Execution Contract

`STATUS.md` is the current checkpoint. This PLAN is the execution contract. Agents are role-bound executors and validators.

Workflow:

1. `invest_project_director`
   - Read `.agent/STATUS.md` and this PLAN.
   - Refine the real-world validation plan for `K07`, `M03`, and `M06`.
   - Assign concrete Group 2 and Group 3 work.
   - May update only this PLAN and `.agent/STATUS.md` during the director gate.
2. Group 2 workers:
   - `invest_agent_architecture_builder` only if a source-profile or adapter-boundary decision is needed.
   - `invest_feature_programmer` for concrete code/profile/eval/test changes.
   - Workers must not modify public schemas or downstream contracts.
3. Group 3 validators:
   - `invest_code_quality_checker` runs focused ruff, py_compile, and pytest gates.
   - `invest_functional_validator` runs the blocker smoke validation and reports observed behavior.
4. `invest_project_summarizer`
   - Use only after this PLAN reaches its done condition.
   - Final report must include what changed, implemented capability, concrete test cases, and two before/after examples.

Phase state machine:

```text
planned -> director_gate -> assigned -> implemented -> code_checked -> functionally_validated -> phase_completed -> next_phase_started
```

Workers must treat `K07`, `M03`, and `M06` as the initial hard test set. They may not spend live budget on the full 50-case batch unless the done condition or a director-approved gate explicitly allows it.

Current Group 2 assignments:

1. `invest_feature_programmer` - Phase 1 audit/fixture setup.
   - Owns: `data/tmp/_source_quality_llm_audit.py`, `data/tmp/_source_quality_batch_report.py` only if needed, and `data/tmp/source_quality_stress_eval/smoke_blockers_profile_remediation_v1.json`.
   - Must keep writes out of `packages/sources/**` in Phase 1.
   - Must preserve private reasoning/secret redaction and never convert parser recovery into an audit pass.
2. `invest_feature_programmer` - Phase 2 `M03` remediation.
   - Owns narrow edits in `packages/sources/query_decomposition.py`, `packages/sources/source_resolver.py`, `packages/sources/retrieval_plan.py`, and narrowly targeted `packages/sources/profiles/**` additions if CAAC/regulator static HTML list-detail profiles are feasible.
   - Must make `project_transaction` visible/executed for low-altitude infrastructure/procurement validation.
   - Must not introduce browser automation, OCR, login-gated sources, or private APIs.
3. `invest_feature_programmer` - Phase 3 `M06` remediation.
   - Owns narrow real-estate macro query facets, central-domain routing precision, and profile ordering for national policy/statistics/project/disclosure lanes.
   - Candidate file ownership: `packages/sources/query_decomposition.py`, `packages/sources/source_resolver.py`, `packages/sources/retrieval_plan.py`, `packages/sources/search_assisted_domestic.py`, and targeted `packages/sources/profiles/**`.
   - Must not weaken generic-homepage rejection.
4. `invest_feature_programmer` - Phase 4 `K07` remediation.
   - Owns exact Feixi/Hefei county-first decomposition and resolver precision, plus narrowly scoped county/public-resource profile additions only if static HTML/list-detail entry points are verified.
   - Must leave land/EIA as an explicit unsupported official-record gap unless a narrow static profile can be validated without new adapter architecture.
   - Must preserve parent-fallback labeling.
5. `invest_agent_architecture_builder` - standby only.
   - Activate only if implementation would require a new public coverage lane, new adapter family, source response-shape drift, or EvidenceBundle/citation/schema changes.
   - Default decision for this PLAN is no public schema or response-shape change.

Current Group 3 validation assignments:

1. `invest_code_quality_checker`
   - Run focused ruff/py_compile on touched files.
   - Run focused source pytest for touched routing/profile/lane modules.
   - Run source regression and domestic source checks when `packages/sources/**` or profiles change.
   - Treat repo-wide `python -m ruff check .` `data/tmp` historical debt as known non-blocker only when focused touched-file checks pass.
2. `invest_functional_validator`
   - Validate the 3-case blocker fixture artifacts against the real-world expectations above.
   - Confirm `K07`, `M03`, and `M06` artifacts distinguish evidence, unsupported gaps, weak-document rejections, parent fallback, and runtime failures.
   - Run the final 12-case live/audit gate only after blocker-fixture validation passes or the PLAN records why a blocker is outside this scope.

## Milestones

### Phase 0: Director Gate and Blocker Inventory

Objective:

- Freeze exact blocker remediation scope.
- Convert the latest audit output into a source-class and component-level repair map.

Tasks:

- Read:
  - `data/tmp/source_quality_stress_eval/runs/direct_exec_final_live/batch_eval.json`
  - `data/tmp/source_quality_stress_eval/runs/direct_exec_final_live/source_roadmap.json`
  - `data/tmp/source_quality_stress_eval/runs/direct_exec_final_live/per_query/K07.json`
  - `data/tmp/source_quality_stress_eval/runs/direct_exec_final_live/per_query/M03.json`
  - `data/tmp/source_quality_stress_eval/runs/direct_exec_final_live/per_query/M06.json`
- Inventory existing source profiles and resolver domains relevant to:
  - Feixi / Hefei / Anhui official project, land, EIA, public-resource, and company evidence
  - CAAC / aviation regulator / low-altitude industry official sources
  - central real-estate policy, statistics, three-projects, housing-stock, and construction-start evidence
- Decide the minimal Phase 1 write scope.

Acceptance criteria:

- This PLAN records the Phase 0 blocker inventory.
- `.agent/STATUS.md` records the active PLAN and current phase.
- No production code changes before the Phase 0 inventory is recorded.

Validation:

```powershell
Test-Path .agent\PLANS\source-profile-adapter-remediation-v1.md
Select-String -Path .agent\STATUS.md,.agent\PLANS\INDEX.md -Pattern "source-profile-adapter-remediation-v1","K07","M03","M06"
```

### Phase 1: Audit Harness Robustness

Objective:

- Reduce false blocker noise caused by DeepSeek invalid JSON while preserving real source-quality failures.

Tasks:

- Inspect current invalid-JSON behavior in `_source_quality_llm_audit.py`.
- Add the smallest safe retry/repair/resume improvement if invalid JSON is caused by formatting drift rather than model refusal.
- Keep raw model reasoning and secrets out of artifacts.
- Verify or create `data/tmp/source_quality_stress_eval/smoke_blockers_profile_remediation_v1.json` containing only `K07`, `M03`, and `M06` from the established smoke set.
- Add tests or py_compile-level verification for new audit parsing code.
- Do not modify `packages/sources/**` in Phase 1.

Acceptance criteria:

- Invalid JSON cases are recorded with precise diagnostics.
- A second attempt can recover trivial fenced/extra-text JSON formatting when safe.
- Source blockers remain visible and are not auto-passed by parser repair.
- The 3-case blocker fixture exists and loads as JSON.
- No production source routing/profile code changed in Phase 1.

Validation:

```powershell
python -m py_compile data\tmp\_source_quality_llm_audit.py data\tmp\_source_quality_batch_report.py
python -c "import json, pathlib; p=pathlib.Path('data/tmp/source_quality_stress_eval/smoke_blockers_profile_remediation_v1.json'); data=json.loads(p.read_text(encoding='utf-8')); ids=data.get('case_ids'); assert ids == ['M03','M06','K07'], ids; print(ids)"
```

### Phase 2: `M03` Low-Altitude Economy Source Remediation

Objective:

- Improve source discovery and evidence routing for central low-altitude economy questions.

Target source needs:

- aviation regulator / CAAC
- airspace reform
- airworthiness certification
- infrastructure construction
- local pilots
- enterprise orders or listed-company disclosures

Likely write scope:

- `packages/sources/query_decomposition.py`
- `packages/sources/source_resolver.py`
- `packages/sources/profiles/**` if a narrow CAAC/aviation official profile can be added safely
- focused tests

Acceptance criteria:

- `M03` decomposition includes low-altitude-specific policy/regulator/project/disclosure facets.
- Search-assisted domains include aviation-regulator official sources where appropriate.
- Live blocker-case artifact shows aviation/regulator discovery attempts or precise unsupported source gaps.

Validation:

```powershell
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_search_assisted_domestic.py
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_blockers_profile_remediation_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\profile_remediation_phase2_blockers --print-json
```

### Phase 3: `M06` Macro Real-Estate Source Remediation

Objective:

- Improve macro real-estate source targeting so the system does not answer a national demand-transmission query with weak local/generic materials.

Target source needs:

- State Council / NDRC / MOHURD / NBS
- real-estate inventory, construction starts, investment, completion, and sales data
- three major projects / urban village renovation / affordable housing
- company revenue or order evidence where query asks for steel, cement, appliances, or machinery demand

Acceptance criteria:

- `M06` routing prioritizes national policy and national statistics before arbitrary local materials.
- Project and disclosure lanes remain visible and attempted.
- Macro source-level mismatch is reduced in the blocker artifact.

Validation:

```powershell
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_lane_execution.py
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_blockers_profile_remediation_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\profile_remediation_phase3_blockers --print-json
```

### Phase 4: `K07` County Source Remediation

Objective:

- Improve county-level exact-local evidence for Feixi NEV cluster questions without pretending that parent-level sources prove county-level claims.

Target source needs:

- Feixi county government / Feixi development zone
- Hefei city official project and industry sources as parent evidence only when county evidence is missing
- public resource / procurement / project filing
- land transfer / EIA / official-record visibility
- listed-company disclosure if company names are discovered

Acceptance criteria:

- `K07` exact-local routing stays county-first.
- Parent-level Hefei/Anhui evidence is marked as parent evidence or fallback, not exact county proof.
- If land/EIA adapters are still unavailable, artifact shows an explicit official-record gap.

Validation:

```powershell
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_lane_execution.py tests\test_sources_profile_adapter.py
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_blockers_profile_remediation_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\profile_remediation_phase4_blockers --print-json
```

### Phase 5: 12-Case Gate Rerun

Objective:

- Re-run the source-quality smoke gate and decide whether the full 50-case live run is now justified.

Tasks:

- Run routing smoke.
- Run 12-case live inspection.
- Run DeepSeek audit.
- Run batch report.
- Record full-run decision.

Acceptance criteria:

- Live smoke has `12 success / 0 runtime error`.
- DeepSeek blocker count is `<=2`.
- No blocker is caused by silent lane omission, invalid JSON parser failure, or source-level mismatch fixed by this PLAN.
- Full 50-case live run remains blocked if the gate fails.

Validation:

```powershell
python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\profile_remediation_final_routing --print-json
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\profile_remediation_final_live --print-json
python data\tmp\_source_quality_llm_audit.py --run-dir data\tmp\source_quality_stress_eval\runs\profile_remediation_final_live --print-json
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\profile_remediation_final_live --print-json
```

## Continue Rule

After each phase, continue automatically to the next phase when:

- acceptance criteria are met
- required validation passes
- no approval, credential, dependency, or human-review blocker exists
- no high-risk contract change is required without explicit PLAN authorization

Do not treat a phase summary as the default stopping point. Stop only at an explicit blocker, explicit user pause, failed validation without a safe repair, or final done condition.

## Stop Conditions

Stop and request user guidance if:

- the next step requires a public schema or EvidenceBundle/citation contract change
- the next step requires changing source routing response shape, `source_quality_summary`, provider abstraction semantics, or task/run status semantics
- a new public coverage lane or adapter family is required for land/EIA/CAAC/MOHURD instead of a narrow static profile or existing adapter path
- a required external credential is missing or invalid
- live source behavior blocks progress and no deterministic fallback exists
- the remediation requires browser automation, OCR, login-gated access, or private APIs
- a source can only be reached by defeating anti-bot controls or by using non-public/private endpoints
- a proposed fix would count parent-level or generic homepage material as exact local, regulatory, statistics, project, or disclosure evidence
- the 12-case gate still has `>2` blockers after focused remediation
- the user explicitly asks to pause

## Validation Loop

Per implementation phase:

1. Add or update focused regression tests first when feasible.
2. Make the smallest coherent source/profile/routing/eval change.
3. Run focused ruff, py_compile, and pytest for touched files.
4. Run source-layer regression checks:

```powershell
pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py
```

5. If domestic source profiles or collectors change, also run:

```powershell
pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py
```

6. Run blocker-case live inspection before spending budget on 12-case audit.
7. Record artifacts, validation, risks, and next action in this PLAN and `.agent/STATUS.md`.

Known non-blocker:

```text
python -m ruff check . currently fails on historical data/tmp scratch/demo lint debt.
Focused ruff for touched files remains required.
```

## Done Condition

This PLAN is done when:

- `K07`, `M03`, and `M06` remediation has been implemented or explicitly classified as requiring a future adapter PLAN.
- The 12-case live/audit gate has been rerun.
- DeepSeek blocker count is `<=2`, or remaining blockers are explicitly outside this PLAN's scope and no longer caused by routing/profile/eval robustness issues.
- `.agent/STATUS.md` and this PLAN contain final validation, risks, next action, and full-run decision.
- Final report includes:
  - what changed
  - implemented capability
  - concrete validation cases
  - two before/after behavior examples

## Risks

- DeepSeek audit output can still produce invalid JSON on long cases; parser recovery must not turn failed audits into false passes.
- Some county land/EIA/project records may require dedicated adapters later; do not fake success with parent-level sources.
- Company disclosure search without discovered company names remains low precision; mark missing company hints clearly.
- Macro real-estate evidence may require structured statistics beyond generic HTML profiles.
- Dirty worktree remains broad; use focused file-scope review for every implementation phase.

## Rollback

- Revert only files touched by this PLAN.
- Do not revert unrelated dirty-worktree changes.
- If a source profile introduces noisy false positives, disable that profile or narrow its query/selector in the same PLAN.
- If a routing change destabilizes existing smoke behavior, restore prior routing and leave the source need as a structured unsupported gap.

## Progress

- 2026-04-28: PLAN created from Source Direct Structured Execution v1 Phase 7 blocker baseline. No production code changed in this creation step.
- 2026-04-28: Planning validation passed. `STATUS.md` and `INDEX.md` now point to this PLAN as the active execution contract.
- 2026-04-28: Added 3-case blocker smoke file `data/tmp/source_quality_stress_eval/smoke_blockers_profile_remediation_v1.json` with `M03`, `M06`, and `K07` to control Tavily/DeepSeek cost during remediation.
- 2026-04-28: Phase 0 local inventory found existing enabled registry coverage for CCGP/GGZY/NDRC project profiles, CNINFO/SSE/SZSE disclosure lane candidates, national statistics, Anhui statistics, and Anhui policy/industry/commerce profiles. It did not find registered CAAC / civil-aviation regulator profiles, MOHURD / housing ministry profiles, Feixi/Hefei project profiles, or domestic land/EIA official-record profiles.
- 2026-04-28: Phase 0 artifact integrity issue recorded. `batch_eval.json` is parseable and authoritative for blocker diagnosis, but some per-query artifacts under `direct_exec_final_live/per_query/*.json` fail `ConvertFrom-Json` because malformed/mojibake strings break JSON parsing. This supports Phase 1 audit/runtime artifact robustness before relying on per-query JSON for automated gates.
- 2026-04-28: Phase 0 director gate completed. Added exact blocker inventory for `K07`, `M03`, and `M06`; refined real-world validation commands/pass criteria; assigned Group 2 / Group 3 ownership; authorized Phase 1 as audit/fixture-only before production source/profile remediation.
- 2026-04-28: Phase 1 audit harness robustness completed. `_source_quality_llm_audit.py` now retries truncated/invalid JSON with a smaller compact payload and no `reasoning_effort`; unrecovered failures remain `invalid_json` with `finish_reason`, usage, parse error, and raw excerpt diagnostics. Added `tests/test_source_quality_llm_audit.py` and validated the 3-case blocker fixture.
- 2026-04-28: Phase 1 validation snapshot: focused ruff for touched audit/test files -> pass; py_compile for audit/batch/test files -> pass; `pytest -q tests\test_source_quality_llm_audit.py` -> `2 passed`; blocker fixture load assertion -> `['M03', 'M06', 'K07']`; Group3 code-quality gate -> pass with known dirty-worktree caveat; Group3 functional gate -> pass with artifact `data/tmp/source_quality_stress_eval/runs/profile_remediation_phase1_validation/functional_validation.json`.
- 2026-04-28: Phase 2 `M03` low-altitude remediation completed. Added CAAC / aviation-regulator facets, low-altitude airspace reform and airworthiness search phrases, infrastructure/local-pilot project phrases, and retrieval lanes for provincial rollout and industry-association supplemental evidence.
- 2026-04-28: Phase 2 validation snapshot: focused ruff and py_compile for touched source/test files -> pass; `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_search_assisted_domestic.py` -> `82 passed`; source regression -> `27 passed`; domestic source checks -> `16 passed`; 3-case live blocker inspection at `data/tmp/source_quality_stress_eval/runs/profile_remediation_phase2_blockers` -> `3 success / 0 runtime error`, estimated Tavily credits `5`, `query_invalid_count=0`.
- 2026-04-28: Phase 2 Group3 validation completed. Code-quality gate passed with only known repo-wide `data/tmp` ruff debt. Functional gate passed with artifact `data/tmp/source_quality_stress_eval/runs/profile_remediation_phase2_validation/functional_validation.json`; `M03` now decomposes into policy, local rollout, project transaction, enterprise disclosure, industry topic, and data metrics; live artifacts show CAAC official pages discovered and fetched by Crawl4AI. Remaining risk: `project_transaction` is executed but still returns `executed_without_evidence`, and local-pilot evidence may need later profile/adapter work.
- 2026-04-28: Phase 3 `M06` macro real-estate remediation completed. Added real-estate macro theme recognition, MOHURD / State Council / NDRC / NBS policy/data targeting, housing-specific search facets, and a search-assisted candidate filter that prevents real-estate macro policy tasks from widening to arbitrary local `*.gov.cn` pages.
- 2026-04-28: Phase 3 validation snapshot: focused ruff and py_compile for touched source/test files -> pass; focused source pytest -> `94 passed`; source regression -> `27 passed`; domestic source checks -> `16 passed`; 3-case routing eval at `data/tmp/source_quality_stress_eval/runs/profile_remediation_phase3_routing` -> `3 pass`; 3-case live inspection at `data/tmp/source_quality_stress_eval/runs/profile_remediation_phase3_blockers_v2` -> `3 success / 0 runtime error`, estimated Tavily credits `4`, `query_invalid_count=0`.
- 2026-04-28: Phase 3 Group3 validation completed. Code-quality gate passed with only known repo-wide `data/tmp` ruff debt. Functional gate passed with artifact `data/tmp/source_quality_stress_eval/runs/profile_remediation_phase3_validation/functional_validation.json`; `M06` now normalizes to `房地产`, no longer generates `local_rollout` / `city_county_fallback`, rejects local `.gov.cn` policy candidates as `off_domain_candidate`, and exposes central-policy miss as `partial` / `national_policy_direction:budget_exhausted` instead of accepting weak local evidence. Remaining risk: central policy, project, statistics, and disclosure lanes still often return `executed_without_evidence`; `cn_project_ggzy_trade_v1` may need a later profile refresh due retryable 404 on `https://www.ggzy.gov.cn/jyxx/`.

- 2026-04-28: Phase 4 `K07` county source remediation completed. Local rollout now keeps county/city official domains (`ahfeixi.gov.cn`, `hefei.gov.cn`, `fgw.hefei.gov.cn`, `gxj.hefei.gov.cn`, `jxj.hefei.gov.cn`, `tjj.hefei.gov.cn`), excludes stale `xf.ahfeixi.gov.cn`, uses Feixi-specific search phrases, and avoids treating province-level Anhui evidence as exact county proof.
- 2026-04-28: Phase 4 validation snapshot: focused ruff and py_compile for touched source/test files -> pass; focused source pytest -> `97 passed`; source regression -> `27 passed`; domestic source checks -> `16 passed`; 3-case routing eval at `data/tmp/source_quality_stress_eval/runs/profile_remediation_phase4_routing_v3` -> `3 pass`; 3-case live inspection at `data/tmp/source_quality_stress_eval/runs/profile_remediation_phase4_blockers_v5` -> `3 success / 0 runtime error`, estimated Tavily credits `5`, `query_invalid_count=0`.
- 2026-04-28: Phase 4 Group3 validation completed. Code-quality gate passed with only known repo-wide `data/tmp` ruff debt. Functional gate passed: K07 no longer accepts stale Feixi Pioneer pages or broad province-level material as exact evidence; when Tavily cannot find exact county/city candidates, the artifact records `coverage_sufficient=false`, `accepted_candidate_count=0`, parent fallback remains `parent_evidence_only=true`, and land/EIA remains `official_record_adapter_not_available`.

## Next Action

Proceed to Phase 5: 12-case routing/live/audit/batch gate rerun.
