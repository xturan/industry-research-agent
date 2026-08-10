# LangGraph Research Productization v1

Status: completed_keep_opt_in_with_followup

Created: 2026-06-12

Primary active PLAN: no

## Objective

Turn the existing opt-in LangGraph research harness into a complete `graph_v1`
Deep Research product path while keeping legacy `/deep-research/analyze` and
`/research/analyze` unchanged until an explicit promotion decision is made.

Selected direction:

```text
Build a full graph_v1 product loop first.
Do not replace the legacy entrypoints yet.
Promote later only after validation proves stability, evidence quality, and
response compatibility.
```

## Task Classification

- Primary area: `research_workflow`
- Secondary areas:
  - `task_substrate`
  - `provider_layer`
  - `source_layer`
  - `memory_feedback`
  - `content_factory`
  - `eval_policy_ops`
- Expected execution mode:
  - `full_subagent` for schema, persistence, API, and workflow phases
  - `light_subagent` for isolated helper, dossier, and smoke-script work
  - `remediation_gate` for failed live or quality gates

## Protected Contracts

Do not silently change:

- legacy `/deep-research/analyze` response shape
- legacy `/research/analyze` response shape
- public `DeepResearchReport`, `EvidenceItem`, `SourceAssessment` schemas
- existing `EvidenceBundle` / citation fields
- existing task/job status semantics
- existing `runs` / `run_steps` meaning
- existing `research_reports.dossier_path` behavior
- direct securities investment advice boundary

## Product Definition

`graph_v1` is product-complete when it can run this loop:

```text
query
  -> source obligation plan
  -> provider-backed discovery/fetch/parse/score
  -> durable source/evidence/claim/review/gate records
  -> claim-level verification and Chief Gate routing
  -> final research report artifact
  -> human-readable dossier
  -> task retry/resume/checkpoint operations
  -> report/history API inspection
  -> cost/latency/source-quality diagnostics
```

Key terms:

- `source obligation plan`:
  来源义务计划，定义一个查询必须覆盖哪些来源类型，例如政策、项目、
  招采、统计、公告、环评或土地。
- `claim-level verification`:
  断言级验证，检查每条具体 claim 是否有证据和来源支持。
- `Chief Gate`:
  总质量门，根据证据覆盖、引用完整性、来源匹配、风险和循环次数决定
  PASS、ADD_EVIDENCE、REVISE_TEXT、REVIEW_RISK 或 HUMAN_REVIEW。
- `product loop`:
  产品闭环，不是一次脚本跑通，而是 API、持久化、报告、dossier、
  任务恢复和验证都能形成可重复路径。

## Scope

In scope:

- durable graph business records
- claim support matrix and gate hardening
- report artifact persistence
- graph report and run inspection APIs
- task retry, resume, and checkpoint inspection
- cost-capped provider-backed live smoke
- promotion-readiness decision

Out of scope:

- replacing legacy endpoints by default
- changing public research response schemas
- full 50-query live source-quality evaluation
- browser automation, OCR, login-gated, or paid/private sources

## Phases

### Phase 0: Architecture Freeze And Baseline Guard

Status: completed

Result:

- confirmed opt-in graph boundary
- preserved legacy endpoint boundary
- recorded graph persistence and API write scope

### Phase 1: Durable Graph Business Records

Status: completed

Result:

- internal graph business records were added for sources, evidence items,
  claims, claim-evidence links, claim verifications, draft versions,
  review issues, and quality gate results
- provider-backed graph runs can persist and reload business records by `run_id`
- resume remains idempotent

Validation:

```powershell
python -m py_compile packages\research_harness\persistence.py packages\research_harness\runner.py packages\db\models\entities.py packages\db\models\__init__.py tests\test_research_harness_graph.py
python -m ruff check packages\research_harness packages\db\models\entities.py packages\db\models\__init__.py tests\test_research_harness_graph.py
pytest -q tests\test_research_harness_graph.py
pytest -q tests\test_research_api.py tests\test_research_run_dossier.py
pytest -q tests\test_tasks_service.py tests\test_tasks_api.py
pytest -q tests\test_migrations.py
pytest -q tests\test_agents_workflow.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py
```

### Phase 2: Claim-Level Evidence And Chief Gate Hardening

Status: completed

Result:

- added DB-backed `claim_support_matrix`
- verifier and chief gate now consume durable source/evidence/claim records
- dossier shows source -> evidence -> claim -> verification -> gate chain

Validation:

```powershell
pytest -q tests\test_research_harness_graph.py tests\test_research_run_dossier.py
python -m ruff check packages\research_harness packages\research_reports\dossier.py
```

### Phase 3: Graph-v1 Report Artifact And Content Output

Status: completed

Result:

- graph-v1 final report artifact persists via `ResearchReportService`
- `report_preview` now includes `report_id` and `report_artifact`
- report JSON links back to graph run, dossier, claims, evidence, and quality diagnostics

Validation:

```powershell
pytest -q tests\test_research_api.py tests\test_research_run_dossier.py tests\test_research_harness_graph.py
```

### Phase 4: Product API And Task Integration

Status: completed

Result:

- graph run inspection APIs remain opt-in
- added `GET /deep-research/graph/runs/{run_id}/report`
- async task path can run, resume, and inspect graph-v1 runs

Validation:

```powershell
pytest -q tests\test_tasks_service.py tests\test_tasks_api.py tests\test_research_api.py
```

### Phase 5: Live Smoke And Quality Gate

Status: completed_with_risk

Result:

- three real provider-backed live smoke cases completed successfully
- report and dossier artifacts are readable
- graph-v1 remains mechanically usable
- but live smoke exposed promotion blockers

Artifacts:

- `data/tmp/langgraph_productization_live_smoke_phase5_v1`
- `data/tmp/langgraph_productization_live_smoke_phase5_company_v1`
- `data/tmp/langgraph_productization_live_smoke_phase5_local_v1`

### Phase 6: Promotion Readiness Decision

Status: keep_opt_in_with_followup

Decision:

- keep graph-v1 opt-in
- do not promote graph-v1 to the default path yet
- open a narrower promotion gate follow-up for evidence-quality readiness and
  search reliability

## Validation Loop

Focused validation that passed:

```powershell
python -m py_compile packages\research_harness\runner.py packages\research_harness\service.py packages\research_harness\schemas.py apps\api\routes\deep_research.py scripts\graph_provider_backed_smoke.py tests\test_research_harness_graph.py tests\test_research_api.py
python -m ruff check packages\research_harness apps\api\routes\deep_research.py packages\research_reports\dossier.py scripts\graph_provider_backed_smoke.py tests\test_research_harness_graph.py tests\test_research_api.py tests\test_research_run_dossier.py
pytest -q tests\test_research_harness_graph.py
pytest -q tests\test_research_api.py tests\test_research_run_dossier.py
pytest -q tests\test_tasks_service.py tests\test_tasks_api.py
pytest -q tests\test_agents_workflow.py
pytest -q tests\test_research_provider_integration.py
pytest -q tests\test_deepseek_provider.py
pytest -q tests\test_migrations.py
```

## Risks And Rollback

Risks:

- graph-v1 can still over-pass weak evidence in some query classes
- provider-backed partial failure is visible but not yet strict enough in gate logic
- source-family obligations are not fully enforced for disclosure and local-depth queries

Rollback:

- keep graph-v1 opt-in
- keep legacy routes untouched
- if gate quality fails, preserve graph-v1 as diagnostic harness rather than default path

## Progress

### 2026-06-13 - Artifact inspection note

Live smoke findings:

- Policy/procurement case:
  sources and evidence mix `official_policy` and `public_resource_transaction`
  appropriately, though search still had partial failure.
- Company/disclosure case:
  query asked for disclosure-grade evidence, but the run returned policy and
  statistics pages instead of `company_disclosure` sources.
- Local/source-depth case:
  query asked for Hefei local evidence, but only 1 of 5 sources matched the
  target location and unrelated regions still appeared in the supporting pool.

Bottom line:

- graph-v1 works mechanically
- evidence quality is not ready for promotion
- PASS can still happen when source-family or locality obligations are not met

### 2026-06-13 - Phase 2-5 completion summary

- Phase 2:
  claim support matrix and gate hardening completed
- Phase 3:
  graph-v1 report artifact persistence completed
- Phase 4:
  graph report API and run summary support completed
- Phase 5:
  three provider-backed live smoke runs completed with partial-failure risk
- Phase 6:
  promotion decision recorded as `keep_opt_in_with_followup`

## Next Action

The next implementation slice, when explicitly approved, is the narrower
follow-up plan:

- `.agent/PLANS/langgraph-v1-promotion-gate-v1.md`

That follow-up should focus on:

1. search failure and retry gating
2. disclosure and locality obligation enforcement
3. small cost-capped live revalidation
4. preserving graph-v1 as opt-in until the narrower gate passes
