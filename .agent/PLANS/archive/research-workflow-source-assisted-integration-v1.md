# Plan: Research Workflow Source-Assisted Integration v1

Status: completed
Priority: high
Owner: codex/human
Scope: research workflow, source-assisted domestic retrieval, evidence handoff, trace visibility, eval harness
Created: 2026-04-27
Last Updated: 2026-04-27

## Objective

Wire the validated Tavily + Crawl4AI search-assisted domestic source path into the end-to-end research workflow without changing protected response schemas.

The system should support user queries such as:

```text
安徽的低空经济未来前景如何
```

When `enable_source_acquisition=True`, the research workflow should be able to decompose the query, execute allowed search-assisted source tasks, preserve direct-keep controls, build evidence for the existing research pipeline, expose trace/quality metadata, and fail transparently when live providers or held-out source classes are unavailable.

## Task Classification

Primary area: `research_workflow`

Secondary areas:

- `source_layer`
- `domestic_source_collectors`
- `provider_layer`
- `eval_policy_ops`
- `task_substrate`

## Background Reused

This plan reuses:

- `domestic-source-lite-refactor-v1.md` conclusions and completed validation.
- `packages.sources.query_decomposition.decompose_query`.
- `packages.sources.search_assisted_domestic.SearchAssistedDomesticOrchestrator`.
- `packages.sources.search_discovery.TavilySearchAdapter`.
- `packages.sources.crawl4ai_extraction.Crawl4AIExtractionService`.
- Existing research workflow source path in `packages/agents/workflow.py`.
- Existing `ResearchAnalyzeRequest.enable_source_acquisition` flag.
- Existing `SourceAcquisitionSummary` response shape.
- Group2 lane model from `.agent/skills/group2-worker-lane-design.md`.

## Scope

In scope:

- Add an Architecture Gate for evidence handoff and response-boundary risks.
- Integrate search-assisted domestic source execution into the existing source acquisition path.
- Preserve existing legacy source acquisition behavior.
- Preserve direct-keep controls for disclosure, project transaction, and structured data tasks.
- Convert search-assisted normalized documents into existing source evidence items or a compatible evidence path.
- Expose trace metadata through existing `source_acquisition` fields.
- Add offline tests for integration behavior and controls.
- Add a practical eval command or script for offline/live smoke validation.

Out of scope:

- Changing EvidenceBundle schema.
- Changing EvidenceItem citation fields.
- Changing `source_quality_summary` shape.
- Changing research analyze response shape.
- Changing task/job status semantics.
- Making Tavily search the direct-keep path for disclosure, procurement, statistics, GSXT, or judicial sources.
- Adding browser automation or OCR.
- Replacing existing RAG fallback behavior.
- Installing or activating Superpowers.

## Protected Contracts

Do not silently change:

- EvidenceBundle schema.
- EvidenceItem citation fields.
- `source_quality_summary` shape.
- Research analyze response shape.
- Provider abstraction semantics.
- Source routing response shape.
- Task/job status semantics.
- `run` / `run_steps` meaning.
- Content asset metadata contract.
- Delivery state transition behavior.

Any required protected-contract change must stop execution and reopen this PLAN with migration, compatibility, validation, and rollback sections.

## Architecture Gate

Classification:

- research_workflow + source_layer integration

Affected contracts:

- `ResearchAnalyzeRequest` must remain backward compatible.
- `ResearchAnalysisResult` and `SourceAcquisitionSummary` shape must remain unchanged.
- RAG `EvidenceBundle` shape must remain unchanged.
- Source `EvidenceItem` / `Citation` shape must remain unchanged.

Affected modules:

- `packages/agents/workflow.py`
- `packages/agents/schemas.py` only if a backward-compatible optional request field is required
- `packages/sources/search_assisted_domestic.py`
- `packages/sources/query_decomposition.py`
- `packages/sources/schemas.py`
- tests under `tests/`
- optional eval script under `data/tmp/`

Current boundary:

- Research workflow already supports `enable_source_acquisition=True`.
- Current path routes source IDs through `SourceIntelligenceService.route_sources()` and then uses registry adapters.
- Search-assisted domestic orchestration exists separately and returns documents/normalized documents plus candidate decisions, but is not yet part of research workflow evidence handoff.

Proposed boundary:

- Keep existing source registry/adapters as legacy/direct path.
- Add a search-assisted domestic branch inside the research source acquisition stage, gated by query decomposition and execution bucket rules.
- Run only allowed search-assisted tasks in first integration.
- Convert extracted normalized documents to existing Source EvidenceItems with valid citations.
- Merge search-assisted evidence with legacy source evidence only through existing bundle conversion.
- Preserve direct-keep tasks as notes/controls, not Tavily calls.

Implementation slices:

- `system_contract_architect`: freeze Architecture Gate and validation design.
- `source_provider_integrator`: add search-assisted source execution and evidence conversion.
- `research_workflow_implementer`: wire workflow summary/trace metadata without response-shape drift.
- `eval_harness_implementer`: add offline eval or smoke script and tests.
- Group3 validators: run code-quality checks and realistic functional cases.

Allowed write scope:

- `.agent/PLANS/research-workflow-source-assisted-integration-v1.md`
- `.agent/STATUS.md`
- `packages/agents/workflow.py`
- `packages/agents/schemas.py` only for backward-compatible optional fields if needed
- `packages/sources/search_assisted_domestic.py`
- `packages/sources/schemas.py` only for backward-compatible helper fields if needed
- `tests/test_agents_workflow.py`
- `tests/test_research_api.py`
- `tests/test_sources_search_assisted_domestic.py`
- new focused tests under `tests/`
- optional eval script under `data/tmp/`

Forbidden changes:

- No protected response-shape or schema-breaking changes.
- No broad source taxonomy rewrite.
- No direct-keep source migration to Tavily.
- No Superpowers activation.
- No credential persistence.

Validation design:

- Unit tests for query decomposition -> search-assisted task selection -> research source evidence handoff.
- Research workflow tests proving source-assisted evidence reaches thesis/evidence stages.
- Control tests proving direct-keep tasks are not routed to Tavily/Crawl4AI.
- Offline eval for `安徽的低空经济未来前景如何`.
- Optional live eval when `TAVILY_API_KEY` is present.

Rollback / fallback:

- Keep `enable_source_acquisition=False` legacy RAG path unchanged.
- Keep existing source registry path available.
- If search-assisted branch fails, record structured source acquisition notes and continue with available evidence or insufficient-evidence path.

Phase 0 director gate result:

- Date: 2026-04-27
- Decision: proceed to Phase 1 without protected-contract changes.
- Protected contract verification:
  - `ResearchAnalyzeRequest` already has `enable_source_acquisition`, source limits, PDF controls, source ID overrides, and user-provided source fields needed for first integration.
  - `ResearchAnalysisResult` already exposes `source_acquisition` without requiring response-shape changes.
  - `SourceAcquisitionSummary` already has `routing_recommendations`, `source_quality_summary`, `source_traces`, `notes`, `truncated_sources`, and `pdf_summary` for trace/quality visibility.
  - Source `EvidenceItem`, `Citation`, and source `EvidenceBundle` already support metadata and bundle conversion into the existing RAG bundle path.
- Implementation may proceed only if workers preserve these shapes. If any worker believes a schema, response shape, citation field, provider abstraction semantic, source routing response shape, task/job status semantic, or run/run_steps meaning must change, stop and reopen this PLAN with migration, compatibility, validation, rollback, and human review.
- `packages/agents/schemas.py` and `packages/sources/schemas.py` are not expected to change in Phase 1. Treat schema edits as an Architecture Gate revision unless they are strictly non-public helper code and explicitly justified.

Decision:

- proceed_without_protected_contract_changes

## Group2 Execution Contract

Use `.agent/skills/group2-worker-lane-design.md`.

Initial Group2 assignments:

### Task Instance 1

Lane: `system_contract_architect`

Backing subagent: `invest_agent_architecture_builder`

Objective: Review this PLAN and Architecture Gate, refine write scope and validation, and identify protected-contract risks before production edits.

Owned files / modules:

- `.agent/PLANS/research-workflow-source-assisted-integration-v1.md`

Forbidden paths / contracts:

- Do not edit production code.
- Do not authorize protected-contract changes.

Required output:

- Architecture Gate refinement or confirmation.
- Implementation slice recommendations.
- Group3 validation recommendations.

Expected worker validation:

- Documentation-only scope review of this PLAN and protected-contract list.
- No production tests required for Task Instance 1 unless production code is edited.

Required Group3 validation:

- Confirm PLAN and STATUS record the Architecture Gate decision and protected-contract stop condition.
- Confirm no production files changed during Phase 0.

Stop conditions:

- Any need to change protected contracts.
- Any ambiguity about whether source-assisted evidence can be converted through existing Source EvidenceItems and RAG EvidenceBundle conversion.

### Task Instance 2

Lane: `source_provider_integrator`

Backing subagent: `invest_feature_programmer`

Objective: Implement allowed search-assisted domestic execution and evidence conversion inside source acquisition.

Owned files / modules:

- `packages/sources/search_assisted_domestic.py`
- `packages/agents/workflow.py`
- focused tests

Forbidden paths / contracts:

- No direct-keep Tavily migration.
- No response-shape breaking changes.

Required output:

- Scoped patch.
- Tests for allowed tasks, holdouts, direct-keep controls, and evidence conversion.

Expected worker validation:

- Focused unit tests for query decomposition task selection, direct-keep controls, search-assisted orchestration, and Source EvidenceItem conversion.
- No live provider dependency in required unit tests.

Required Group3 validation:

- `invest_code_quality_checker` runs source-focused tests and relevant ruff/compile checks.
- `invest_functional_validator` verifies allowed, direct-keep, holdout, and provider-failure scenarios against the real-world validation plan.

Stop conditions:

- Need to route disclosure, procurement, statistics, GSXT, judicial, or other direct-keep tasks through Tavily as the primary path.
- Need to change EvidenceItem/Citation/EvidenceBundle shapes.
- Live provider behavior cannot be represented as structured partial failure.

### Task Instance 3

Lane: `research_workflow_implementer`

Backing subagent: `invest_feature_programmer`

Objective: Ensure search-assisted evidence and trace metadata are visible through existing `SourceAcquisitionSummary` and research run steps.

Owned files / modules:

- `packages/agents/workflow.py`
- `tests/test_agents_workflow.py`
- `tests/test_research_api.py`

Forbidden paths / contracts:

- No response model breaking changes.

Required output:

- Scoped patch or test coverage proving no workflow contract drift.

Expected worker validation:

- Workflow tests proving `enable_source_acquisition=False` remains legacy behavior.
- Workflow/API tests proving `enable_source_acquisition=True` exposes source-assisted trace/quality through existing `SourceAcquisitionSummary` fields.

Required Group3 validation:

- `invest_code_quality_checker` runs research workflow/API focused tests and research contract checks.
- `invest_functional_validator` verifies response-shape stability and run-step trace visibility against practical cases.

Stop conditions:

- Need to change research analyze response shape.
- Need to redefine `run` / `run_steps` semantics.
- Need to make source acquisition mandatory for legacy mode.

### Task Instance 4

Lane: `eval_harness_implementer`

Backing subagent: `invest_feature_programmer`

Objective: Add or update offline/live smoke validation for the integrated path.

Owned files / modules:

- `data/tmp/`
- focused tests if needed

Forbidden paths / contracts:

- No secret persistence.
- No live provider requirement for unit tests.

Required output:

- Runnable command and documented pass/fail criteria.

Expected worker validation:

- Offline smoke command for realistic cases with mocked or deterministic providers.
- Optional live command guarded by explicit environment variables and cost/credential notes.

Required Group3 validation:

- `invest_code_quality_checker` confirms the eval script or focused tests are runnable without secrets.
- `invest_functional_validator` owns final case design and validates offline/live results when available.

Stop conditions:

- Eval requires persisted credentials.
- Unit or offline validation depends on live Tavily/Crawl4AI availability.
- Eval cases only cover easy success and omit direct-keep, holdout, or provider-failure controls.

## Group3 Validation Contract

Code-quality validation:

- `python -m ruff check .` may still fail on unrelated historical `data/tmp` scripts; focused checks must be used if repo-wide ruff remains blocked.
- `pytest -q tests/test_agents_workflow.py tests/test_research_api.py`
- `pytest -q tests/test_sources_query_decomposition.py tests/test_sources_search_assisted_domestic.py`
- `pytest -q tests/test_sources_layer.py tests/test_sources_evals_step35.py`

Functional validation:

- Primary success: `安徽的低空经济未来前景如何`.
- Direct-keep control: `中信海直（000099.SZ）在低空经济方向有哪些公告和项目`.
- Holdout control: `成都人工智能产业园区有哪些政策和项目机会`.
- API/workflow smoke: research analyze with `enable_source_acquisition=True` and mocked search/extraction.
- Live optional: Tavily/Crawl4AI only when env is present and cost limits are explicit.

## Real-world Validation Plan

Group3 owns final practical validation design. Group2 may implement hooks, fixtures, and scripts, but Group2 must not be the only designer of the cases used to certify completion.

Group3 functional validator update 2026-04-27:

- Case IDs are frozen as `RW-SAI-01` through `RW-SAI-09`.
- Offline tests must use UTF-8 source files or Unicode escape strings for Chinese queries. Do not copy mojibake-rendered query text into tests.
- Group2 cannot self-certify these cases. Group3 must review final behavior after implementation.

Mandatory offline cases:

- Legacy control: research analyze with `enable_source_acquisition=False` must keep the existing retrieval/evidence bundle behavior and disabled source summary.
- Source-assisted success: `安徽的低空经济未来前景如何` with `enable_source_acquisition=True` and mocked Tavily/Crawl4AI must decompose into allowed search-assisted tasks, produce existing Source EvidenceItems, convert into the existing RAG EvidenceBundle path, and expose trace/quality notes through existing `SourceAcquisitionSummary` fields.
- Direct-keep control: `中信海直（00099.SZ）在低空经济方向有哪些公告和项目` must not route disclosure/project-transaction primary paths through Tavily/Crawl4AI.
- Holdout control: `成都人工智能产业园区有哪些政策和项目机会` must keep unsupported or not-yet-integrated source classes transparent as held/partial output instead of pretending coverage.
- Provider failure transparency: Tavily or Crawl4AI failure must become structured notes/errors/traces and should not alter protected response shapes.
- Evidence quality check: source-assisted items must include citation locator/document/source URI data where available, non-empty support text or summary, bounded score, and metadata identifying the search-assisted path without changing EvidenceItem fields.
- Cost/limit smoke: small `max_sources`, `max_docs_per_source`, `max_evidence_per_source`, and `top_k` limits must cap fanout and candidate extraction.

Required offline case matrix:

| Case ID | Type | Scenario | Pass criteria |
|---|---|---|---|
| `RW-SAI-01` | legacy_control | `enable_source_acquisition=False` | No search-assisted orchestrator call; `source_acquisition.enabled=False`; existing RAG behavior and source stage skip semantics remain intact. |
| `RW-SAI-02` | primary_success_case | Anhui low-altitude economy outlook with `enable_source_acquisition=True` | Allowed search-assisted tasks produce Source EvidenceItems, enter the existing RAG EvidenceBundle path, and expose trace/quality notes through existing fields. |
| `RW-SAI-03` | direct_keep_control | Listed-company disclosure/project query | Direct-keep task families do not call Tavily/Crawl4AI as primary path. |
| `RW-SAI-04` | holdout_case | Chengdu AI industrial park policy/project opportunity query | Park/city/municipal families remain held/unsupported/partial with transparent notes; no fake coverage. |
| `RW-SAI-05` | provider_failure_transparency | Tavily or Crawl4AI error/partial result | Errors become structured notes/traces/quality summary data without response-shape drift. |
| `RW-SAI-06` | evidence_quality_case | Inspect successful source-assisted EvidenceItems | Title, support text or summary, score, citation document/locator/source URI or metadata, and search-assisted path metadata are present. |
| `RW-SAI-07` | api_workflow_smoke | FastAPI `/research/analyze`, `mode=mock`, mocked search/extraction | HTTP 200, response remains `ResearchAnalysisResult`, `SourceAcquisitionSummary` shape remains compatible, run-step semantics remain unchanged. |
| `RW-SAI-08` | cost_latency_case | Success case with small limits | Search/extraction fanout is capped; rejected candidate reasons remain visible. |
| `RW-SAI-09` | optional_live_case | Live Anhui low-altitude economy smoke when `TAVILY_API_KEY` exists | No credential persistence; live pass/skip/fail is recorded; live failure is provider-transparent and does not block offline pass. |

Recommended offline fixtures:

- `FakeSearchAdapter` with call counters and allowlisted/off-domain/attachment/search-page/duplicate/error candidates.
- `FakeExtractionService` returning `RawDocument` plus `NormalizedDocument` with source URI, summary, sections, and metadata.
- failing search/extraction fakes returning `ToolError` and `ToolStatus.ERROR` or `ToolStatus.PARTIAL`.
- workflow/API monkeypatches that keep unit tests offline by default.
- direct-keep spy asserting direct tasks do not call Tavily/Crawl4AI.

Mandatory API/workflow checks:

- `/research/analyze` response model remains `ResearchAnalysisResult`.
- `source_acquisition` remains nullable and shape-compatible.
- `source_quality_summary` remains a dictionary payload inside `SourceAcquisitionSummary`; do not introduce a new public top-level field.
- `run_steps` keep existing stage meanings; additional search-assisted details must be represented as existing source stage outputs, trace metadata, or notes unless an Architecture Gate revision approves otherwise.

Optional live validation:

- Run only when `TAVILY_API_KEY` is already present in the process environment.
- Do not persist credentials in PLAN, STATUS, scripts, fixtures, logs, or repository files.
- Use explicit candidate/doc limits and record whether live validation was skipped, passed, or failed with provider-transparent errors.

## Phases

### Phase 0: Director and Architecture Gate

Acceptance:

- PLAN is active in STATUS.
- Architecture Gate is confirmed or refined.
- Group2 lanes and Group3 validation are assigned.

Validation:

- PLAN exists.
- STATUS points to this PLAN.
- Protected contracts are listed and unchanged.

Current state:

- completed 2026-04-27 by Phase 0 director gate. Architecture Gate confirmed, real-world validation plan added, Group2/Group3 responsibilities refined, and implementation may proceed without protected-contract changes.

### Phase 1: Search-Assisted Evidence Handoff

Acceptance:

- Allowed search-assisted domestic tasks can produce existing Source EvidenceItems.
- Direct-keep tasks remain controls and do not call Tavily/Crawl4AI.
- Legacy source acquisition path remains available.

Validation:

- Focused source-assisted unit tests pass.

Current state:

- completed 2026-04-27. Group2 implementation was independently confirmed by Group3 code-quality and functional validation. Direct-keep controls, holdout transparency, and existing Source EvidenceItem/Citation conversion path are preserved.

### Phase 2: Research Workflow Wiring

Acceptance:

- `enable_source_acquisition=True` can use the integrated search-assisted path.
- `SourceAcquisitionSummary` exposes route/task/trace notes through existing fields.
- Existing research response shape remains unchanged.

Validation:

- `tests/test_agents_workflow.py` and `tests/test_research_api.py` pass.

Current state:

- completed 2026-04-27. `enable_source_acquisition=True` now uses the integrated search-assisted branch through existing `SourceAcquisitionSummary` fields, while `enable_source_acquisition=False` remains legacy behavior.

### Phase 3: Eval Harness and Practical Cases

Acceptance:

- Offline smoke validation exists for realistic cases.
- Optional live validation is documented without persisting credentials.

Validation:

- Offline eval command passes.
- Live eval is run only when environment is available.

Current state:

- completed 2026-04-27. Added `data/tmp/_research_workflow_source_assisted_eval.py` with offline RW-SAI-01..08 coverage and optional RW-SAI-09 live status handling. The script does not persist credentials.

### Phase 4: Full Validation and Handoff

Acceptance:

- Required focused tests pass or blockers are recorded.
- PLAN and STATUS contain validation snapshot and next action.

Validation:

- Research contract checks.
- Source regression checks.
- Functional case results.

Current state:

- completed 2026-04-27. Focused research/source checks, eval harness checks, Group3 code-quality gate, Group3 functional gate, and director remediation review passed with non-blocking caveats recorded below.

## Continue Rule

After each phase, continue automatically when:

- acceptance criteria are met;
- required validation passes;
- no protected contract change is needed;
- no missing credential blocks offline validation;
- no explicit user pause exists.

Do not stop at phase summaries.

## Stop Conditions

Stop and request guidance only when:

- a protected contract must change;
- direct-keep sources would need to use Tavily as primary path;
- live provider failure cannot be made transparent;
- production tests fail and repair path is unclear;
- a credential or external dependency is required for a mandatory validation;
- the user asks to pause.

## Done Condition

This PLAN is complete when:

- Search-assisted domestic evidence can enter research workflow through existing contracts.
- Direct-keep and holdout controls are preserved.
- Research/source focused tests pass.
- Practical cases are validated offline and live status is recorded if available.
- PLAN and STATUS are updated with final validation and risks.

## Validation Loop

Required focused checks:

```powershell
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py
pytest -q tests\test_agents_workflow.py tests\test_research_api.py
pytest -q tests\test_sources_layer.py tests\test_sources_evals_step35.py
```

Optional repo-wide check:

```powershell
python -m ruff check .
```

Known caveat:

- Repo-wide ruff may fail on unrelated historical `data/tmp` scratch/demo scripts. If so, record the failure and run focused validation.

## Progress

- 2026-04-27: Created PLAN and set Phase 0 to in progress after user requested PLAN execution. Reused completed domestic source and Group2 lane designs.
- 2026-04-27: Completed Phase 0 director gate. Confirmed Architecture Gate decision `proceed_without_protected_contract_changes`, verified existing request/result/source evidence contracts are sufficient for Phase 1, added a concrete real-world validation plan, refined Group2 task instance validation/stop conditions, and assigned Group3 code-quality plus functional validation ownership.
- 2026-04-27: Group2 `source_provider_integrator` implemented Phase 1 in scoped files only. Added query-decomposition-gated search-assisted domestic execution inside `packages/agents/workflow.py`, preserved direct-keep controls (no Tavily/Crawl4AI primary routing for direct-keep tasks), preserved legacy source acquisition path, and converted search-assisted normalized/raw documents into existing source `EvidenceItem`/`Citation` contracts through new helpers in `packages/sources/search_assisted_domestic.py`. Added focused tests for conversion and workflow controls/success. Validation snapshot: `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py` -> `30 passed`; `pytest -q tests\test_agents_workflow.py tests\test_research_api.py` -> `13 passed`; focused lint for touched files passed via `python -m ruff check packages\agents\workflow.py packages\sources\search_assisted_domestic.py tests\test_agents_workflow.py tests\test_sources_search_assisted_domestic.py`.
- 2026-04-27: Group3 code-quality gate passed for Phase 1/2. Validation: `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py` -> `30 passed`; `pytest -q tests\test_agents_workflow.py tests\test_research_api.py` -> `13 passed`; `pytest -q tests\test_sources_layer.py tests\test_sources_evals_step35.py` -> passed; `pytest -q tests\test_research_provider_integration.py tests\test_deepseek_provider.py` -> `11 passed`; focused ruff on touched files passed; `python -m compileall packages\agents packages\sources tests` passed. Repo-wide `python -m ruff check .` still fails on unrelated historical `data/tmp` scratch/demo files.
- 2026-04-27: Group3 functional gate passed offline RW-SAI-01..08 for Phase 1/2 behavior. RW-SAI-09 was skipped because `TAVILY_API_KEY` was not present in the current process environment; this is non-blocking because live validation is optional and credentials must not be required for offline completion.
- 2026-04-27: Director remediation gate decided `phase1_2_complete`. `packages/sources/schemas.py` has public schema additions relative to HEAD, but this is recorded as pre-existing dirty-worktree risk and Group2 did not modify or depend on it for this PLAN. No Architecture Gate reopen is required unless future work relies on or modifies those public schema additions.
- 2026-04-27: Added Phase 3 eval harness `data/tmp/_research_workflow_source_assisted_eval.py`. It runs deterministic offline RW-SAI-01..08 workflow/API/evidence/failure/holdout/cost cases and optional RW-SAI-09 live status handling. Validation: `python data\tmp\_research_workflow_source_assisted_eval.py --mode offline --print-json` -> passed; `python data\tmp\_research_workflow_source_assisted_eval.py --mode auto --print-json` -> passed with RW-SAI-09 structured skip; `python -m ruff check data\tmp\_research_workflow_source_assisted_eval.py` -> passed; `python -m compileall data\tmp\_research_workflow_source_assisted_eval.py` -> passed.
- 2026-04-27: Phase 3 functional remediation passed after strengthening RW-SAI-06 and RW-SAI-08. RW-SAI-06 now validates title, summary/support text, bounded score, citation document/source URI/external ref, citation metadata path, item metadata path, and conversion path. RW-SAI-08 now records and asserts an offline total provider-call budget of `3` and live caps of `2` search-assisted tasks, `1` phrase per task, and `1` candidate per task.
- 2026-04-27: Phase 4 handoff completed. Done condition met: search-assisted domestic evidence enters the research workflow through existing contracts; direct-keep and holdout controls are preserved; research/source focused checks pass; practical cases are validated offline; live status is recorded as skipped when no `TAVILY_API_KEY` exists in the current process; PLAN/STATUS final validation and risks are recorded.

## Risks and Rollback

Risks:

- Search-assisted documents may need evidence conversion heuristics; poor conversion can inflate weak evidence.
- Live Tavily/Crawl4AI behavior may differ from offline tests.
- Direct-keep controls must not regress into search-assisted mode.
- Dirty worktree has pre-existing unrelated changes, so scope proof remains limited.
- `packages/sources/schemas.py` has public schema additions relative to HEAD. This PLAN does not depend on them and does not claim ownership of them; if they enter a release boundary, open a separate Architecture Gate/PLAN.
- RW-SAI-09 live validation was skipped in this run because the current process had no `TAVILY_API_KEY`. Offline completion remains valid; live can be run later with explicit environment setup.
- Physical archive move is deferred for human review, matching the existing pattern used by the completed domestic source PLAN.

Rollback:

- Disable integrated branch behind existing `enable_source_acquisition` behavior or fallback notes.
- Keep legacy RAG path unchanged when `enable_source_acquisition=False`.
- Remove search-assisted branch from workflow while preserving standalone source modules.

## Next Action

Done condition met. Recommended next action is human review plus optional live smoke:

```powershell
$env:TAVILY_API_KEY="<set in this terminal only>"
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
python data\tmp\_research_workflow_source_assisted_eval.py --mode live --print-json
```

Do not persist credentials. If live behavior exposes provider or budget issues, open a narrow remediation gate instead of changing protected contracts directly.
