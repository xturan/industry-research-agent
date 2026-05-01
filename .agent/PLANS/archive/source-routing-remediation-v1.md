# Plan: Source Routing Remediation v1

Status: completed
Priority: high
Owner: codex/human
Scope: production remediation for domestic source routing, Crawl4AI extraction reliability, and source-quality eval robustness
Created: 2026-04-28
Last Updated: 2026-04-28

## Objective

Fix the first set of production blockers surfaced by `source-quality-stress-eval-v1` smoke evaluation before running the full 50-case live eval.

This PLAN starts from observed artifacts, not from broad source expansion:

```text
data/tmp/source_quality_stress_eval/runs/manual_smoke/batch_eval.json
data/tmp/source_quality_stress_eval/runs/manual_smoke/source_roadmap.json
```

Smoke outcome:

- 12 smoke cases
- live status: 10 success, 2 error
- DeepSeek audit verdicts: 9 blocker, 3 fail
- 9 reopening-plan items
- top missing source classes: `company_disclosure`, `project_list`, `local_government`, `statistics`, `environmental_or_land_record`

Primary remediation goal:

```text
reduce false blockers caused by extraction/runtime failures and routing misclassification,
then make missing source classes explicit and testable.
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
- task/job status semantics
- `run` / `run_steps` meaning
- direct-keep primary path semantics
- legacy `enable_source_acquisition=False` behavior

## Scope

In scope:

- `packages/sources/crawl4ai_extraction.py`
- `packages/sources/query_decomposition.py`
- `packages/sources/retrieval_plan.py`
- `packages/sources/source_resolver.py`
- `packages/sources/search_assisted_domestic.py`
- focused tests under `tests/test_sources_*.py`
- temporary eval scripts under `data/tmp`
- `.agent/STATUS.md` and this PLAN

Out of scope:

- changing API response shapes
- changing EvidenceBundle or citation contracts
- adding browser automation/OCR/login-gated collection
- replacing Tavily or Crawl4AI
- making final research-answer quality claims
- broad source pack expansion without regression cases
- direct adapter implementation for disclosure/project/statistics unless a later Architecture Gate authorizes it

## Remediation Design

Use a three-layer remediation order:

1. **Extraction/runtime correctness first**
   - Fix the observed `gbk` encoding crash from Crawl4AI logging on Windows.
   - Add focused tests so Unicode logging cannot break extraction.
   - Rationale: if extraction returns zero docs, routing/source improvements cannot be judged.

2. **Local routing precision second**
   - Improve detection for city/county/province query entities that appeared in smoke cases but were repaired to `全国`.
   - Ensure city/county industrial queries keep at least one search-assisted `local_rollout` lane even when they also need direct-keep project/disclosure lanes.
   - Rationale: C01/C07 failed because tasks were direct-only and regional focus was lost.

3. **Source-class coverage visibility third**
   - Make project, disclosure, statistics, land/environmental gaps explicit in retrieval/eval artifacts.
   - Do not fake direct adapter results through Tavily.
   - Rationale: current eval correctly says these classes are missing, but the system needs deterministic coverage-gap semantics and regression checks before broader source work.

## Smoke Cases Driving This PLAN

| Case | Observed issue | First remediation target |
|---|---|---|
| `C01` 合肥新能源汽车 | region repaired to `全国`; direct-only tasks; no executed search-assisted tasks | city detection + local rollout preservation |
| `C07` 常州动力电池/光伏 | region repaired to `全国`; direct-only disclosure task | city detection + local rollout preservation |
| `K07` 肥西新能源汽车 | county-level source scarcity / national search scope | exact local hints + gap semantics |
| `K09` 神木煤炭/煤化工 | Crawl4AI `gbk` Unicode crash; local mismatch | extraction stdio fix + local routing |
| `K12` 若羌锂钾/新能源 | Crawl4AI `gbk` Unicode crash; county lane missing | extraction stdio fix + county routing |
| `M02/M03/M06` macro policy | Crawl4AI `gbk` Unicode crash made accepted URLs unusable | extraction stdio fix |
| `P04/P08/P10` province | missing source classes and regional mismatch | province/domain routing + explicit gaps |

## Milestones

### Phase 0: Architecture Gate and Regression Baseline

Objective:

- Freeze the first remediation slice and collect baseline evidence from smoke artifacts.

Allowed write scope:

- `.agent/PLANS/source-routing-remediation-v1.md`
- `.agent/STATUS.md`
- read-only artifact inspection

Acceptance criteria:

- PLAN exists and becomes primary active PLAN.
- STATUS points to this PLAN.
- First production slice is explicitly authorized.
- No production code is changed before Phase 1.

Validation:

```powershell
Select-String -Path .agent\PLANS\source-routing-remediation-v1.md,.agent\STATUS.md -Pattern "source-routing-remediation-v1","Phase 1","Crawl4AI"
```

### Phase 1: Crawl4AI Windows Unicode/GBK Runtime Remediation

Objective:

- Prevent Crawl4AI Unicode status output from crashing extraction under Windows/GBK consoles.

Allowed write scope:

- `packages/sources/crawl4ai_extraction.py`
- `tests/test_sources_crawl4ai_extraction.py`

Tasks:

- Add a narrow stdio encoding guard before invoking Crawl4AI.
- Do not suppress structured extraction errors.
- Add unit tests for stdio reconfiguration and existing extraction behavior.

Acceptance criteria:

- Focused unit tests pass.
- Existing direct-keep protection remains intact.
- No API/evidence/task contract changes.

Validation:

```powershell
python -m ruff check packages\sources\crawl4ai_extraction.py tests\test_sources_crawl4ai_extraction.py
python -m py_compile packages\sources\crawl4ai_extraction.py tests\test_sources_crawl4ai_extraction.py
pytest -q tests\test_sources_crawl4ai_extraction.py
```

### Phase 2: City/County Region Detection and Local Lane Preservation

Objective:

- Fix C01/C07-style cases where explicit city names are repaired to `全国` and search-assisted local lanes disappear.

Allowed write scope:

- `packages/sources/query_decomposition.py`
- `packages/sources/retrieval_plan.py`
- `packages/sources/source_resolver.py`
- focused tests:
  - `tests/test_sources_query_decomposition.py`
  - `tests/test_sources_source_resolver.py`
  - `tests/test_sources_retrieval_plan.py`

Tasks:

- Add first-wave local entity hints for smoke city/county cases only where safe.
- Detect `合肥`, `常州`, `肥西`, `神木`, `若羌`, `海南`, `内蒙古` where relevant.
- Preserve direct-keep project/disclosure tasks, but also keep `local_rollout` when a query asks for local policy/fiscal/project/land/government support.
- Keep parent-evidence fallback gaps explicit.

Acceptance criteria:

- `C01` and `C07` get local search-assisted tasks instead of zero executed search-assisted tasks.
- `K07/K09/K12` keep county-level fallback semantics.
- Q03 humanoid robotics negative-domain behavior remains protected.

Validation:

```powershell
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_source_resolver.py tests\test_sources_retrieval_plan.py
python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\remediation_phase2_routing --print-json
```

### Phase 3: Source-Class Coverage Gap Semantics

Objective:

- Make missing `project_list`, `company_disclosure`, `statistics`, and `environmental_or_land_record` classes deterministic and actionable without pretending Tavily replaces direct structured adapters.

Allowed write scope:

- `packages/sources/retrieval_plan.py`
- `packages/sources/search_assisted_domestic.py`
- focused tests under `tests/test_sources_retrieval_plan.py` and `tests/test_sources_search_assisted_domestic.py`

Tasks:

- Add deterministic coverage gap metadata for direct-keep-required but not executed classes.
- Preserve direct-keep primary paths.
- Surface these gaps in source traces for eval.

Acceptance criteria:

- Direct-keep classes are visible as gaps/controls, not silently missing.
- Search-assisted lanes do not execute direct-keep primary paths.

Validation:

```powershell
pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_search_assisted_domestic.py
```

### Phase 4: Eval Robustness and Roadmap Quality

Objective:

- Harden source-quality eval scripts so LLM string/list deviations do not degrade roadmap priority labels or crash aggregation.

Allowed write scope:

- `data/tmp/_source_quality_llm_audit.py`
- `data/tmp/_source_quality_batch_report.py`
- optional prompt file under `data/tmp/source_quality_stress_eval/prompts/`

Tasks:

- Keep `--resume`.
- Normalize non-object LLM recommendations into lower-priority manual review items.
- Preserve invalid JSON diagnostics.
- Do not store private reasoning content or secrets.

Acceptance criteria:

- Batch aggregation can run on existing smoke artifacts.
- `source_roadmap.json` separates production blockers from manual source suggestions.

Validation:

```powershell
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\manual_smoke --print-json
```

### Phase 5: Smoke Re-Run and Full-Run Gate

Objective:

- Re-run the 12-case smoke set after remediation and decide whether full 50 live is cost-justified.

Tasks:

- Run routing-only smoke.
- Run live smoke with bounded budgets if `.env` keys are present.
- Run DeepSeek audit only if extraction/routing quality improves enough.
- Generate comparison against `manual_smoke`.

Acceptance criteria:

- Fewer extraction/runtime blockers than baseline.
- C01/C07 no longer produce zero executed search-assisted tasks.
- Any remaining missing source classes are explicit coverage gaps.
- Full 50 live run decision is recorded with cost rationale.

Validation:

```powershell
python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\remediation_smoke_routing --print-json
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\remediation_smoke_live --print-json
```

## Continue Rule

After each phase, continue automatically when:

- acceptance criteria are met
- focused validation passes
- no protected contract change is needed
- no external API cost escalation occurs
- no explicit user pause exists

Do not treat a phase summary as a default stop point.

## Stop Conditions

Stop and request guidance when:

- a fix requires changing EvidenceBundle/API/task semantics
- live Tavily/DeepSeek cost becomes unexpectedly high
- Crawl4AI cannot run after stdio remediation and no fallback is safe
- direct adapters must be built for disclosure/project/statistics before search-assisted remediation can continue
- production code changes exceed the allowed file scope

## Agent Execution Contract

The intended v2 project workflow remains:

- Group 1 director owns PLAN scope and remediation gates.
- Group 2 implementation owns narrowly assigned source/eval files.
- Group 3 validation owns focused code-quality checks and functional smoke validation.

In this session, execution may be performed locally by Codex without spawning subagents unless the user explicitly asks for subagent delegation.

## Done Condition

This PLAN is done when:

- Phase 1 extraction remediation is implemented and tested.
- Phase 2 local routing remediation is implemented and tested.
- Phase 3 direct-keep source-class gaps are deterministic or explicitly deferred.
- Smoke re-run artifacts show improved extraction/routing behavior or a clear remaining blocker.
- STATUS and PLAN include validation, risks, and next action.
- Final report includes what changed, user-facing capability, concrete test cases, two before/after behavior examples, validation, risks, and next step.

## Risks

- Live web results are volatile; validation must distinguish runtime bugs from web changes.
- Some missing source classes require direct adapters and cannot be solved by search-assisted routing.
- City/county source coverage can be sparse; parent evidence must remain a gap, not a local claim.
- The current dirty worktree makes git-level scope proof imperfect.
- Repo-wide ruff still has known historical `data/tmp` debt; use focused checks for changed files.

## Rollback

- Revert changes only in the files touched by this PLAN.
- Do not revert unrelated dirty worktree changes.
- If Phase 1 breaks Crawl4AI behavior, remove the stdio guard and keep structured errors unchanged.
- If Phase 2 over-routes supplemental domains, restore previous query decomposition tests and Q03 negative-domain guard.

## Progress

- 2026-04-28: PLAN created from `source-quality-stress-eval-v1` smoke artifacts. First remediation order frozen: extraction runtime -> local routing -> source-class gap semantics -> eval robustness -> smoke re-run.
- 2026-04-28: Phase 0 Architecture Gate completed. Production write scope is limited to source-layer/eval files listed above; protected EvidenceBundle/API/task contracts remain unchanged.
- 2026-04-28: Phase 1 implemented. Added a Crawl4AI stdio UTF-8 guard before invoking `AsyncWebCrawler` so Unicode status output does not crash under Windows/GBK consoles. Added focused regression test. Validation: `pytest -q tests\test_sources_crawl4ai_extraction.py` -> `8 passed`; `python -m ruff check packages\sources\crawl4ai_extraction.py tests\test_sources_crawl4ai_extraction.py` -> pass; `python -m py_compile packages\sources\crawl4ai_extraction.py tests\test_sources_crawl4ai_extraction.py` -> pass.
- 2026-04-28: Phase 2 implemented. Added first-wave city/county/province routing hints and local lane preservation for C01/C07/K07/K09/K12-style cases in `query_decomposition`, `retrieval_plan`, and `source_resolver`. Validation: `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_source_resolver.py` -> `61 passed`; routing smoke improved to `11 weak_pass / 1 pass` with zero `missing_city_county_fallback_lane` failures.
- 2026-04-28: Phase 3 implemented. Split explicit disclosure queries from enterprise-evidence control needs, preventing project/policy/park queries from being over-routed into disclosure-only mode. Added deterministic direct-structured control gaps with reason `direct_structured_primary_path_required` for required statistics/project/disclosure lanes. Validation: `pytest -q tests\test_sources_retrieval_plan.py` -> `28 passed`; focused ruff/py_compile for touched source/test/eval files -> pass; combined source/search-assisted regression -> `88 passed`; routing smoke improved to `8 pass / 4 weak_pass`.
- 2026-04-28: Phase 4 completed. Existing batch aggregation handled non-object LLM recommendations as P2 manual-review items; added UTF-8 stdio guard to `data/tmp/_source_quality_batch_report.py` after remediation run output hit a Windows/GBK `UnicodeEncodeError`. Validation: `python -m py_compile data\tmp\_source_quality_batch_report.py` -> pass; batch report on remediation live artifacts -> pass.
- 2026-04-28: Phase 5 completed. Re-ran 12-case live smoke with bounded budgets: `12 success / 0 error`, estimated Tavily credits `21`, average latency `14817.63 ms`, `query_invalid_count=0`. DeepSeek audit completed via `--resume`: `10 success / 2 invalid_json`, verdicts `5 blocker / 7 fail`, total tokens `183719`. Batch roadmap generated at `data/tmp/source_quality_stress_eval/runs/remediation_smoke_live/source_roadmap.json`.

## Next Action

This remediation PLAN is complete. Do not run the full 50-case live evaluation yet. The next PLAN should focus on direct structured lane execution and evidence coverage: project/procurement, statistics, disclosure, environmental/land records, and lane-budget scheduling for cases still blocked in the remediation smoke audit (`M02`, `M06`, `P08`, `C07`, `C09`).
