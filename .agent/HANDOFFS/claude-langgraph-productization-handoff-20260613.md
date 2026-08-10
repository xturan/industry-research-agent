# Claude Handoff: LangGraph Research Productization v1

Date: 2026-06-13

Workspace: `e:\invest_agent`

Primary area: `research_workflow`

Secondary areas: `task_substrate`, `provider_layer`, `source_layer`, `content_factory`, `eval_policy_ops`

## 0. Read This First

This handoff is for continuing the LangGraph graph-v1 Deep Research productization work. Do not rely on hidden chat history. Treat this document plus the project markdown files as the execution contract.

Before changing files, Claude must read:

1. `C:\Users\LEGION\.codex\memories\PROFILE.md`
2. `C:\Users\LEGION\.codex\memories\ACTIVE.md`
3. `e:\invest_agent\AGENTS.md`
4. `e:\invest_agent\.agent\STATUS.md`
5. `e:\invest_agent\.agent\PLANS\langgraph-research-productization-v1.md`
6. This handoff file
7. Relevant validation skills:
   - `e:\invest_agent\.agent\skills\execution-mode-router.md`
   - `e:\invest_agent\.agent\skills\research-contract-check.md`
   - `e:\invest_agent\.agent\skills\task-flow-check.md`

The worktree is broad and dirty. Do not revert unrelated changes. Do not use `git reset --hard` or `git checkout --` unless the user explicitly asks.

## 1. Current State Summary

The active long-running plan is:

```text
.agent/PLANS/langgraph-research-productization-v1.md
```

The graph-v1 product loop has now reached a working opt-in product path:

```text
query
  -> provider-backed source discovery
  -> source/evidence/claim durable business records
  -> claim support matrix
  -> verifier/chief gate using business records
  -> report artifact persisted in research_reports
  -> dossier artifact written as Markdown
  -> run inspection / resume / checkpoint compaction
  -> graph run report API
  -> cost-capped live smoke artifacts
```

Important: graph-v1 remains opt-in. Do not promote it to replace legacy `/deep-research/analyze` or `/research/analyze`.

## 2. Key Terms Claude Must Preserve And Explain In Chinese

When reporting back to the user, do not only list these English field names. Explain what each means in plain Chinese.

- `graph_v1`: 当前 LangGraph 深度研究路径的版本名。它表示新的可审计 graph workflow，不是 legacy endpoint 的默认替代。
- `report_id`: `research_reports` 表中保存的报告记录 ID。它用于从 graph run 跳转到用户可读报告 artifact。
- `report_artifact`: graph run response 中的索引对象，包含 `report_id`、`workflow_version`、`graph_run_id`、`dossier_path`，用于把 run、报告、审计文档串起来。
- `workflow_version`: 工作流版本标识。当前为 `graph_v1`，用于区分 legacy DeepResearchAgent 和新 LangGraph path。
- `graph_run_id`: `runs.id`，表示一次 graph-v1 research run 的运行记录 ID。
- `dossier_path`: Markdown 审计文档路径，用于查看 source、evidence、claim、agent trace、context pack 和 final report preview。
- `claim_support_matrix`: 从 durable source/evidence/claim business records 生成的断言支持矩阵。它回答“每个 claim 由哪些 evidence/source 支持，source family 是否匹配，支持强度如何”。
- `source_family`: 源类别，例如 `official_policy`、`public_resource_transaction`。它用于判断某个 claim 需要哪类来源支持。
- `usage_role`: Source Quality v2 给 source 的使用角色，例如是否可作为 primary evidence candidate。它不是最终 claim 判断，而是 source 层的使用建议。
- `search_error_count`: provider-backed 搜索中失败的搜索事件数量。当前 live smoke 即使 PASS，也要记录这个指标，因为它可能影响证据覆盖稳定性。
- `retry_event_count`: 搜索重试事件数量。它说明 provider 有过瞬时失败或不稳定，但部分失败可能被 retry 恢复。

## 3. What Has Already Been Implemented

Do not reimplement these from scratch. First verify current diff and tests.

### Phase 1: Durable Graph Business Records

Implemented earlier:

- Alembic migration:
  - `packages/db/alembic/versions/f6a7b8c9d0e1_add_research_graph_business_records.py`
- ORM models in:
  - `packages/db/models/entities.py`
  - `packages/db/models/__init__.py`
- Repository:
  - `packages/research_harness/persistence.py`
- Runner integration:
  - `packages/research_harness/runner.py`
- Tests:
  - `tests/test_research_harness_graph.py`
  - `tests/test_migrations.py`

### Phase 2: Claim Support Matrix And Gate Hardening

Implemented:

- `ResearchGraphState.claim_support_matrix`
- `GraphBusinessRecordRepository.build_claim_support_matrix(run_id)`
- Runner injects DB-backed `claim_support_matrix` before:
  - `verify_claims`
  - `chief_gate`
  - `finalize_report`
- Provider-backed verifier uses `claim_support_matrix` when present.
- Provider-backed Chief Gate enriches `ADD_EVIDENCE` required actions using the matrix.
- Dossier renders `### Claim Support Matrix`.
- Tests assert Verifier/Gate `contract_meta.business_record_view == "claim_support_matrix"`.

### Phase 3: Graph-v1 Report Artifact Persistence

Implemented in current working tree:

- `packages/research_harness/runner.py`
  - Saves a graph-v1 report artifact through existing `ResearchReportService`.
  - Adds `report_id` and `report_artifact` into `report_preview`.
  - Reuses existing `report_id` on resume instead of duplicating report rows.
  - Report JSON includes:
    - `workflow_version`
    - `graph_run_id`
    - `thread_id`
    - `dossier_path`
    - `key_claims`
    - `evidence_table`
    - `limitations`
    - `source_quality_summary`
    - `claim_support_matrix`
    - `quality_scores`
    - `cost_latency_diagnostics`
    - `compliance_statement`

Acceptance already validated:

- Graph run produces both report artifact and dossier artifact.
- Report links back to graph run and dossier.
- Compliance statement says it is research assistance / industry intelligence, not direct securities investment advice.

### Phase 4: Graph Report API And Run Summary

Implemented in current working tree:

- `packages/research_harness/schemas.py`
  - `GraphRunSummary.report_id`
- `packages/research_harness/service.py`
  - `ResearchGraphService.get_run_report(run_id)`
  - Extracts `report_id` from `report_preview`.
- `apps/api/routes/deep_research.py`
  - New endpoint:
    - `GET /deep-research/graph/runs/{run_id}/report`
  - Existing graph endpoints remain opt-in.
- `tests/test_research_api.py`
  - Verifies graph analyze response has `report_preview.report_id`.
  - Verifies `GET /deep-research/graph/runs/{run_id}/report`.
  - Verifies graph run list exposes `report_id`.

### Phase 5: Cost-Capped Live Smoke

Three real provider-backed smoke runs completed with Tavily loaded from `.env`.

Artifacts:

1. Policy / public procurement case:
   - `data/tmp/langgraph_productization_live_smoke_phase5_v1/summary.json`
   - `data/tmp/langgraph_productization_live_smoke_phase5_v1/response.json`
   - `data/tmp/langgraph_productization_live_smoke_phase5_v1/dossier.md`
   - Result:
     - status: `succeeded`
     - decision: `PASS`
     - final_score: `0.89`
     - search_event_count: `6`
     - search_success_count: `5`
     - search_error_count: `1`
     - estimated_credits: `6`
     - retry_event_count: `2`
     - report_id: `1`
     - dossier has Search Events and Claim Verifications

2. Company / disclosure or enterprise signal case:
   - `data/tmp/langgraph_productization_live_smoke_phase5_company_v1/summary.json`
   - `data/tmp/langgraph_productization_live_smoke_phase5_company_v1/response.json`
   - `data/tmp/langgraph_productization_live_smoke_phase5_company_v1/dossier.md`
   - Result:
     - status: `succeeded`
     - decision: `PASS`
     - final_score: `0.88`
     - search_event_count: `6`
     - search_success_count: `5`
     - search_error_count: `1`
     - estimated_credits: `6`
     - retry_event_count: `3`
     - report_id: `1`

3. Local / source-depth case:
   - `data/tmp/langgraph_productization_live_smoke_phase5_local_v1/summary.json`
   - `data/tmp/langgraph_productization_live_smoke_phase5_local_v1/response.json`
   - `data/tmp/langgraph_productization_live_smoke_phase5_local_v1/dossier.md`
   - Result:
     - status: `succeeded`
     - decision: `PASS`
     - final_score: `0.90`
     - search_event_count: `6`
     - search_success_count: `4`
     - search_error_count: `2`
     - estimated_credits: `6`
     - retry_event_count: `3`
     - report_id: `1`

Risk note: all three live cases succeeded, but provider search had partial failures. The current Chief Gate permits PASS when evidence coverage is enough even if some search events failed. This is acceptable for opt-in graph-v1 smoke, but not enough to promote graph-v1 as default.

## 4. Validation Already Run

Focused validations that passed:

```powershell
python -m py_compile packages\research_harness\runner.py tests\test_research_harness_graph.py
python -m ruff check packages\research_harness\runner.py tests\test_research_harness_graph.py
pytest -q tests\test_research_harness_graph.py
```

Result:

```text
10 passed
```

API / dossier / task validations:

```powershell
pytest -q tests\test_research_api.py tests\test_research_run_dossier.py
pytest -q tests\test_tasks_service.py tests\test_tasks_api.py
```

Results:

```text
13 passed
7 passed
```

Provider contract tests were initially run as one combined command and timed out at 124 seconds. They were then split and all passed:

```powershell
pytest -q tests\test_agents_workflow.py
pytest -q tests\test_research_provider_integration.py
pytest -q tests\test_deepseek_provider.py
```

Results:

```text
11 passed
9 passed
2 passed
```

Final local regression:

```powershell
python -m ruff check packages\research_harness apps\api\routes\deep_research.py packages\research_reports\dossier.py scripts\graph_provider_backed_smoke.py tests\test_research_harness_graph.py tests\test_research_api.py tests\test_research_run_dossier.py
python -m py_compile packages\research_harness\runner.py packages\research_harness\service.py packages\research_harness\schemas.py apps\api\routes\deep_research.py scripts\graph_provider_backed_smoke.py tests\test_research_harness_graph.py tests\test_research_api.py
pytest -q tests\test_research_harness_graph.py tests\test_research_api.py tests\test_research_run_dossier.py
pytest -q tests\test_tasks_service.py tests\test_tasks_api.py
```

Results:

```text
ruff: pass
py_compile: pass
23 passed
7 passed
```

Known environment caveats:

- PowerShell output emits a pre-existing `requests` dependency warning. It did not block tests.
- SQLite datetime adapter deprecation warnings appear in tests. They are not new blockers for this work.
- If running provider tests together, use a timeout above 180 seconds or split them.

## 5. Immediate Tasks For Claude

Claude should execute these in order.

### Task 0: Verify Current Diff Without Reverting

Objective:

- Confirm current worktree contains the implemented graph-v1 report artifact/API/smoke changes.
- Do not assume HEAD is clean.
- Do not revert unrelated historical modifications.

Commands:

```powershell
git status --short
git diff -- packages\research_harness\runner.py packages\research_harness\service.py packages\research_harness\schemas.py apps\api\routes\deep_research.py scripts\graph_provider_backed_smoke.py tests\test_research_harness_graph.py tests\test_research_api.py
```

Acceptance criteria:

- Claude can identify the graph-v1 changes listed in sections 3 and 4.
- Claude does not delete or rewrite unrelated dirty files.
- If a diff has changed since this handoff, Claude records the difference before editing.

### Task 1: Sync PLAN And STATUS

Objective:

- Update project durable memory so future agents do not think Phase 2 is still active.

Required files:

- `.agent/PLANS/langgraph-research-productization-v1.md`
- `.agent/STATUS.md`
- `.agent/PLANS/INDEX.md`

Required updates:

- Mark Phase 2 as `completed`.
- Mark Phase 3 as `completed`.
- Mark Phase 4 as `completed`.
- Mark Phase 5 as `completed_with_risk` or equivalent wording.
- Mark Phase 6 decision as:

```text
keep_opt_in_with_followup
```

Meaning in Chinese:

- `keep_opt_in_with_followup` 表示 graph-v1 已经形成可运行的产品闭环，但仍只允许显式 opt-in 使用；后续需要一个更窄的 promotion gate 来判断是否能替代 legacy 默认路径。

Required status content:

- Current graph-v1 product loop works opt-in.
- Legacy `/deep-research/analyze` and `/research/analyze` remain unchanged.
- Latest validation snapshot includes the exact commands and results from section 4.
- Latest live smoke snapshot includes the three artifact directories and partial search failure risk.
- Next recommended action is not more broad productization; it is a narrower promotion/readiness follow-up.

Acceptance criteria:

- `Select-String -Path .agent\STATUS.md -Pattern "keep_opt_in_with_followup","langgraph-research-productization-v1.md"` returns matches.
- `Select-String -Path .agent\PLANS\langgraph-research-productization-v1.md -Pattern "Phase 3","Phase 4","Phase 5","keep_opt_in_with_followup"` returns matches.
- No production code is changed in this task unless necessary to resolve a docs consistency issue.

### Task 2: Re-run Focused Regression After STATUS/PLAN Sync

Objective:

- Ensure docs-only status updates did not hide an unverified production state.

Commands:

```powershell
python -m ruff check packages\research_harness apps\api\routes\deep_research.py packages\research_reports\dossier.py scripts\graph_provider_backed_smoke.py tests\test_research_harness_graph.py tests\test_research_api.py tests\test_research_run_dossier.py
python -m py_compile packages\research_harness\runner.py packages\research_harness\service.py packages\research_harness\schemas.py apps\api\routes\deep_research.py scripts\graph_provider_backed_smoke.py tests\test_research_harness_graph.py tests\test_research_api.py
pytest -q tests\test_research_harness_graph.py tests\test_research_api.py tests\test_research_run_dossier.py
pytest -q tests\test_tasks_service.py tests\test_tasks_api.py
```

Acceptance criteria:

- All commands pass.
- If `pytest` provider tests are also needed, split them:

```powershell
pytest -q tests\test_agents_workflow.py
pytest -q tests\test_research_provider_integration.py
pytest -q tests\test_deepseek_provider.py
```

- If any command fails, Claude must capture the exact error and classify whether it is:
  - docs-only drift
  - graph response contract regression
  - report artifact persistence regression
  - task/resume regression
  - provider/runtime instability

### Task 3: Inspect Live Smoke Artifacts Before Designing Follow-up

Objective:

- Do not rely only on PASS status. Inspect what sources/evidence/claims were actually used.

Required artifacts:

```text
data/tmp/langgraph_productization_live_smoke_phase5_v1/summary.json
data/tmp/langgraph_productization_live_smoke_phase5_v1/response.json
data/tmp/langgraph_productization_live_smoke_phase5_v1/dossier.md

data/tmp/langgraph_productization_live_smoke_phase5_company_v1/summary.json
data/tmp/langgraph_productization_live_smoke_phase5_company_v1/response.json
data/tmp/langgraph_productization_live_smoke_phase5_company_v1/dossier.md

data/tmp/langgraph_productization_live_smoke_phase5_local_v1/summary.json
data/tmp/langgraph_productization_live_smoke_phase5_local_v1/response.json
data/tmp/langgraph_productization_live_smoke_phase5_local_v1/dossier.md
```

Inspection checklist:

- Are `report_id` and `report_artifact.workflow_version == "graph_v1"` present?
- Does dossier contain:
  - `### Search Events`
  - `### Claim Support Matrix`
  - `### Claim Verifications`
  - `## 5. Final Report Preview`
- Are failed search events visible and understandable?
- Are claim support matrix rows linked to real `evidence_ids` and `source_ids`?
- Does `compliance_statement` avoid direct investment advice?
- Does the company/disclosure query actually collect disclosure-quality evidence, or only policy pages?
- Does the local/source-depth query actually collect local project/source-depth evidence, or only broad policy pages?

Acceptance criteria:

- Claude writes a short artifact inspection note into the active PLAN or a new follow-up PLAN.
- The note must distinguish runtime success from evidence-quality readiness.
- If evidence is shallow despite PASS, record it as a promotion blocker.

### Task 4: Create Narrow Follow-up PLAN For Promotion Gate

Objective:

- Do not keep expanding broad graph productization. Open a focused follow-up plan for promotion readiness.

Recommended new plan:

```text
.agent/PLANS/langgraph-v1-promotion-gate-v1.md
```

Primary area:

```text
research_workflow
```

Secondary areas:

```text
provider_layer, source_layer, task_substrate, eval_policy_ops
```

Required scope:

1. Search failure and retry semantics:
   - Define when partial provider search errors should block PASS.
   - Define whether `search_error_count > 0` should reduce final gate confidence.
   - Define when a retry-recovered query is acceptable.

2. Evidence-quality readiness:
   - Company/disclosure queries must show disclosure or enterprise-signal evidence when requested.
   - Local/source-depth queries must show local or source-depth evidence when requested.
   - Policy-only evidence must not satisfy disclosure/local-depth obligations.

3. API/readiness compatibility:
   - Keep graph-v1 opt-in.
   - Verify legacy `/deep-research/analyze` and `/research/analyze` response shapes stay stable.
   - Verify graph report endpoint and dossier endpoint remain readable.

4. Live smoke gate:
   - Run a small, cost-capped set first.
   - Do not run full 50-query live eval unless the user explicitly asks.

Acceptance criteria for the new PLAN:

- Has explicit objective, scope, protected contracts, phases, validation loop, done condition, stop conditions, risks, and next action.
- Defines exact PASS thresholds for:
  - runtime success
  - search error tolerance
  - retry tolerance
  - source-family coverage
  - claim support matrix completeness
  - report/dossier readability
- Contains at least 3 test cases:
  - policy/project or procurement case
  - company/disclosure case
  - local/source-depth case
- Contains concrete PowerShell validation commands.
- `.agent/STATUS.md` points to the new plan only if the user agrees to continue immediately.

### Task 5: Do Not Promote Graph-v1 Yet

Objective:

- Prevent accidental product default switch.

Hard constraints:

- Do not replace legacy `/deep-research/analyze`.
- Do not replace legacy `/research/analyze`.
- Do not change public `DeepResearchReport`, `EvidenceItem`, `SourceAssessment`, or `EvidenceBundle` shapes.
- Do not change task status semantics.
- Do not reinterpret `runs` / `run_steps` meaning.
- Do not hide provider failures in polished output.

Acceptance criteria:

- If Claude recommends promotion, it must cite passing evidence from the new promotion gate, not only the three smoke runs in this handoff.
- If Claude keeps graph-v1 opt-in, it must record the exact blocker and next smallest remediation.

## 6. Suggested Follow-up Implementation Ideas

These are not mandatory unless included in the new PLAN.

1. Add gate-level search reliability diagnostics:
   - Include `search_success_count`, `search_error_count`, `retry_event_count`, and `max_attempt_count` in report artifact and Chief Gate context.
   - Consider reducing `final_score` or adding a `REVIEW_RISK` action when evidence relies on too few successful source-family-matched searches.

2. Strengthen source obligations:
   - If query asks for disclosure, require `company_disclosure` or equivalent source family.
   - If query asks for local/source-depth, require local official or project-list/source-depth source family.
   - Policy pages can provide background but must not satisfy these obligations alone.

3. Add artifact API tests:
   - `GET /deep-research/graph/runs/{run_id}/report`
   - `GET /research-reports/{report_id}`
   - `GET /research-reports/{report_id}/dossier`

4. Add promotion-gate smoke script output fields:
   - `source_family_counts`
   - `required_obligation_coverage`
   - `unsupported_claim_count`
   - `search_failure_reasons`

## 7. Stop Conditions

Claude must stop and ask the user if:

- A protected public response contract must change.
- Provider API keys are missing or live budget is unavailable.
- Validation fails repeatedly and the safe repair path is unclear.
- A fix requires browser automation, OCR, login-gated data, or paid/private data outside the plan.
- The user asks to pause or only review.

Claude should not stop merely because a phase completed. Continue according to the active PLAN unless a stop condition applies.

## 8. Final Report Requirements For Claude

When Claude finishes the next task, the final answer must include:

- What changed.
- Files modified.
- Validation commands and results.
- Whether graph-v1 remains opt-in.
- Whether legacy endpoints were preserved.
- Current blocker or next recommended action.
- Plain Chinese explanation of any English field names introduced.

Do not only list files. Explain the practical effect the user can test.

