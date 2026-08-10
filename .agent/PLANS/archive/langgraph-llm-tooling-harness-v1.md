# LangGraph LLM Tooling Harness v1

Status: completed_phase2_review_gate_finalize_expansion

Created: 2026-06-14

Primary active PLAN: no (completed and archived)

## Objective

Introduce a first-class tooling harness for LangGraph LLM-backed nodes so
selected nodes can call approved tools through auditable authorization instead
of reading or mutating graph state ad hoc.

This slice implements the minimum safe path:

1. add tooling foundation
2. add `tool_traces`
3. connect `editor1_draft` to one real LLM + one read-only tool
4. expand the same mechanism to `editor2_review`, `chief_gate`, and
   `finalize_report`

## Task Classification

- Primary area: `research_workflow`
- Secondary areas: `provider_layer`, `eval_policy_ops`, `task_substrate`
- Execution mode: `light_subagent` / direct scoped implementation

## Protected Contracts

Do not silently change:

- public `/deep-research/graph/analyze` response shape
- task/job status semantics
- existing run / run_steps meaning
- dossier path contract
- existing evidence / claim / source persistence shapes

Tooling traces may be added to internal graph state, step outputs, and dossier
rendering as additive observability.

## Scope

In scope:

1. tooling spec registry
2. node-level policy registry
3. harness authorization + execution shell
4. tool trace recording
5. one read-only tool for `editor1_draft`
6. expansion to `editor2_review`, `chief_gate`, `finalize_report`

Out of scope:

- full agent-loop autonomy
- arbitrary network tools
- DB write tools for LLM nodes
- redesigning public API response models
- full prompt/context engineering optimization

## Phases

### Phase 1: Foundation And Editor1

Status: completed

Tasks:

- add:
  - `packages/research_harness/tooling/specs.py`
  - `packages/research_harness/tooling/policy.py`
  - `packages/research_harness/tooling/harness.py`
  - `packages/research_harness/tooling/executor.py`
- add `tool_traces` to graph state
- add one read-only tool:
  - `get_evidence_bundle`
- connect `editor1_draft_provider_backed` to:
  - real LLM API
  - tool harness
  - step output trace
  - dossier visibility

Acceptance criteria:

- `editor1_draft` can request `get_evidence_bundle`
- harness authorizes or denies based on node policy
- tool call trace is persisted in state / step output
- dossier shows tool trace visibility

### Phase 2: Review, Gate, Finalize Expansion

Status: completed

Tasks:

- connect `editor2_review` to read/review tools
- connect `chief_gate` to read/replan tools
- connect `finalize_report` to compose tools
- keep forbidden tools blocked

Acceptance criteria:

- all four target nodes use the tooling harness
- at least one denied call path is test-covered
- no node can directly mutate DB or run status via tool layer

## Validation

Baseline:

```powershell
python -m ruff check packages\research_harness tests
python -m py_compile packages\research_harness\runner.py packages\research_harness\nodes.py packages\research_harness\real_nodes.py
pytest -q tests\test_research_harness_graph.py
pytest -q tests\test_research_api.py
pytest -q tests\test_research_provider_integration.py tests\test_deepseek_provider.py
```

Tooling-specific:

```powershell
pytest -q tests\test_research_harness_tooling.py
```

## Risks

- LLM tool outputs may drift from contract if prompt boundaries are weak.
- Tool traces could bloat step outputs if result payloads are not summarized.
- Over-permissive policies would recreate black-box behavior under a new name.

## Progress

### 2026-06-14

Plan created after user requested concrete implementation of:

- tooling authorization / allow / deny
- editor1/editor2/chief_gate/finalize_report LLM API integration
- harness-level permission control

### 2026-06-14 Implementation completion

Completed:

- unified all graph node signatures to accept `tool_session`
- added `packages/research_harness/tooling/llm_agents.py` as a narrow shared
  helper for structured DeepSeek JSON calls
- connected `editor1_draft_provider_backed` to:
  - `get_evidence_bundle`
  - `compose_section_outline`
  - real LLM-backed JSON drafting with deterministic fallback
- connected `editor2_review_provider_backed` to:
  - `get_claim_support_matrix`
  - `get_source_bundle`
  - `request_revision`
- connected `chief_gate_provider_backed` to:
  - `get_claim_support_matrix`
  - `get_source_bundle`
  - `request_replan`
  while preserving the existing planner replan contract fields
- connected `finalize_report` provider-backed path to:
  - `compose_final_report`
  - `get_evidence_bundle`
- added `tests/test_research_harness_tooling.py`
- expanded graph and dossier tests to assert tool trace visibility
- completed one live smoke run:
  - `data/tmp/tooling_editor1_live_v1`
  - status `succeeded`
  - decision `HUMAN_REVIEW`
  - tool traces visible in dossier for editor/review/gate/finalize nodes

Validation completed:

- `python -m py_compile packages\research_harness\nodes.py packages\research_harness\real_nodes.py packages\research_harness\tooling\llm_agents.py packages\research_reports\dossier.py tests\test_research_harness_tooling.py tests\test_research_harness_graph.py tests\test_research_run_dossier.py`
- `python -m ruff check packages\research_harness\nodes.py packages\research_harness\real_nodes.py packages\research_harness\tooling\llm_agents.py packages\research_reports\dossier.py tests\test_research_harness_tooling.py tests\test_research_harness_graph.py tests\test_research_run_dossier.py`
- `pytest -q tests\test_research_harness_tooling.py`
- `pytest -q tests\test_research_harness_graph.py`
- `pytest -q tests\test_research_run_dossier.py`
- `pytest -q tests\test_research_api.py`
- `pytest -q tests\test_research_provider_integration.py`
- `pytest -q tests\test_deepseek_provider.py`
- `pytest -q tests\test_tasks_service.py tests\test_tasks_api.py`
- `python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\tooling_editor1_live_v1 --query "2025年低空经济上市公司年报披露与官方政策证据" --max-rounds 2 --max-loop-count 1`

Assumptions:

- keep the LLM helper narrow and local to this harness slice instead of
  introducing a larger agent framework
- keep existing public response shapes unchanged and expose tooling only through
  additive `tool_traces` and `contract_meta`

Risks:

- live provider-backed runs can still end in `REVIEW_RISK` or `HUMAN_REVIEW`
  when search instability remains high even if evidence coverage passes
- tool trace volume may grow on longer loops; future slices may need stronger
  summarization or truncation policies

## Next Action

Next recommended action:

1. decide whether to promote this tooling-enabled graph slice into a broader
   productization/promotion-gate plan
2. if continuing graph productization, add tighter live-eval assertions for
   tool-trace volume, repeated loops, and denied-call audit visibility
