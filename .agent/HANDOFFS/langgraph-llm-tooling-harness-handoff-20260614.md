# LangGraph LLM Tooling Harness Handoff

Date: 2026-06-14

Primary follow-up plan:
- `.agent/PLANS/langgraph-llm-tooling-harness-v1.md`

Current status:
- `active_phase1_foundation_and_editor1`

Primary area:
- `research_workflow`

Secondary areas:
- `provider_layer`
- `eval_policy_ops`
- `task_substrate`

## 1. Objective

Continue implementation of a node-scoped tooling authorization and execution
harness for LangGraph LLM-backed nodes.

This slice is intentionally narrow:

1. add tooling foundation
2. add `tool_traces`
3. connect `editor1_draft` to one real LLM API plus one read-only tool
4. only after that, expand to:
   - `editor2_review`
   - `chief_gate`
   - `finalize_report`

The user explicitly asked for:
- code implementation, not only design
- harness-level authorization / deny / allow behavior
- auditable trace visibility

## 2. What Has Already Been Done

### 2.1 Plan / status alignment

Created:
- `.agent/PLANS/langgraph-llm-tooling-harness-v1.md`

Updated:
- `.agent/STATUS.md`

The active primary plan was switched away from the promotion-gate implementation
plan and onto the new tooling harness plan.

### 2.2 Tooling foundation files created

Created:
- `packages/research_harness/tooling/specs.py`
- `packages/research_harness/tooling/policy.py`
- `packages/research_harness/tooling/harness.py`
- `packages/research_harness/tooling/executor.py`
- `packages/research_harness/tooling/__init__.py`

What they currently contain:

#### `specs.py`
- `ToolKind`
- tool input schemas
- `ToolTraceRecord`
- `ToolSpec`
- `TOOL_SPECS`
- `FORBIDDEN_TOOL_NAMES`

Tools currently registered:
- `get_evidence_bundle`
- `get_claim_support_matrix`
- `get_source_bundle`
- `request_replan`
- `request_revision`
- `compose_section_outline`
- `compose_final_report`

Forbidden placeholders:
- `write_database_record`
- `update_run_status`
- `arbitrary_network_fetch`

#### `policy.py`
Node-scoped policies added for:
- `editor1_draft`
- `editor2_review`
- `chief_gate`
- `finalize_report`

Includes:
- `allowed_tools`
- `max_tool_calls`
- `allow_network`
- `allow_state_write`
- `read_scopes`

#### `executor.py`
Implemented deterministic executor stubs for:
- `get_evidence_bundle`
- `get_claim_support_matrix`
- `get_source_bundle`
- `request_replan`
- `request_revision`
- `compose_section_outline`
- `compose_final_report`

Important:
- executor currently reads from `state`
- executor returns structured payloads
- executor does not mutate DB
- executor does not directly mutate run status

#### `harness.py`
Implemented:
- `ToolAuthorizationResult`
- `ToolHarness.authorize_call(...)`
- `ToolSession.call_tool(...)`
- trace summarization

Current checks implemented:
- forbidden tool hard block
- unknown tool block
- node policy allow-list check
- max tool call budget check
- argument schema validation

Current output behavior:
- allowed calls return `{ok: True, result: ...}`
- denied calls return `{ok: False, error_code: ..., message: ...}`
- both produce trace records

### 2.3 Graph state already extended

Updated:
- `packages/research_harness/state.py`

Added:
- `tool_traces: list[dict[str, Any]]`

Initial state now includes:
- `tool_traces=[]`

### 2.4 Runner partially wired

Updated:
- `packages/research_harness/runner.py`

Already added:
- `ToolHarness`
- `ToolExecutor`
- `ToolSession`
- node handler now creates `tool_session`
- `node_fn` is now invoked as:
  - `node_fn(dict(node_state), tool_session=tool_session)`

Also added:
- successful tool traces appended into state
- failed node execution path also preserves tool traces if any were created
- `tool_trace_count` added to step input summary
- step output can now include `tool_traces`
- dossier context now includes `tool_traces`

### 2.5 Dossier partially wired

Updated:
- `packages/research_reports/dossier.py`

Already added:
- `## 5. Tool Traces`
- `_render_graph_tool_traces(...)`
- glossary entry for `tool_traces`

This means dossier rendering side is already ready to show tool call audit
records once nodes actually emit them.

## 3. What Is NOT Done Yet

### 3.1 Node function signatures are not updated consistently

Current problem:
- `runner.make_node_handler(...)` now calls every node with:
  - `node_fn(dict(node_state), tool_session=tool_session)`

But current node functions in:
- `packages/research_harness/nodes.py`
- `packages/research_harness/real_nodes.py`

still mostly have signatures like:
- `def editor1_draft_provider_backed(state: dict[str, Any]) -> dict[str, Any]:`
- `def editor1_draft(state: dict[str, Any]) -> dict[str, Any]:`

So the code is currently in an intermediate state and will break until the node
signatures are updated.

This is the immediate next implementation step.

### 3.2 `editor1_draft` is not yet connected to real LLM API

User specifically asked for:
- real LLM API integration
- tool harness

Current state:
- `editor1_draft_provider_backed(...)` is still deterministic text assembly
- it does not call `DeepSeekProviderClient`
- it does not call `tool_session.call_tool(...)`

### 3.3 `tests/test_research_harness_tooling.py` does not exist yet

The plan already names it in validation, but the file has not been created.

### 3.4 `editor2_review`, `chief_gate`, `finalize_report` are untouched

No LLM integration yet.
No tool usage yet.
No denied-call path coverage yet.

## 4. Critical Constraints

Do not silently change:
- public `/deep-research/graph/analyze` response shape
- task/job status semantics
- run/run_steps meaning
- existing evidence / claim / source persistence shape
- `research_reports.dossier_path`

Allowed additive changes:
- `tool_traces` in internal state
- `tool_traces` in step outputs
- `tool_traces` in dossier rendering

Tooling rules that must remain true:
- LLM nodes cannot directly write DB
- LLM nodes cannot directly update run status
- arbitrary network access remains forbidden
- tool outputs remain structured
- runner / harness remains the authorization boundary

## 5. Exact Next Steps

Follow this order.

### Step A: Fix node signatures

Update all graph node functions to accept:

```python
def some_node(state: dict[str, Any], *, tool_session=None) -> dict[str, Any]:
```

This includes both:
- shadow wrappers in `packages/research_harness/nodes.py`
- provider-backed implementations in `packages/research_harness/real_nodes.py`

For nodes that do not yet use tools, accept the argument and ignore it.

This is required so the graph can run again.

### Step B: Add LLM helper for editor nodes

Recommended new helper file:
- `packages/research_harness/tooling/llm_agents.py`

Suggested content:
- builder for editor/review/gate/finalizer prompts
- one shared helper to call `DeepSeekProviderClient.generate_json(...)`
- strict structured output + fallback handling

Keep it narrow:
- do not over-generalize into a full agent framework yet

### Step C: Connect `editor1_draft_provider_backed`

Replace current deterministic paragraph assembly with:

1. `tool_session.call_tool("get_evidence_bundle", {...})`
2. optional `tool_session.call_tool("compose_section_outline", {...})`
3. call real LLM API via DeepSeek
4. validate output into `EditorDraftOutput`
5. append draft into `drafts`
6. include `tool_traces` in partial output
7. keep deterministic fallback if:
   - tool denied
   - provider error
   - schema validation fails

Important:
- fallback must preserve current graph continuity
- the old deterministic editor output can be reused as fallback

### Step D: Create tooling tests

Add:
- `tests/test_research_harness_tooling.py`

Cover at minimum:
- allowed `editor1_draft -> get_evidence_bundle`
- denied `editor1_draft -> request_replan`
- denied forbidden tool
- trace record generated for allowed call
- trace record generated for denied call

### Step E: Add graph-level proof

Update:
- `tests/test_research_harness_graph.py`
- optionally `tests/test_research_run_dossier.py`

Add assertions for:
- `editor1_draft` step output contains `tool_traces`
- dossier contains `## 5. Tool Traces`
- at least one trace line references `get_evidence_bundle`

## 6. Suggested Minimal Shape For `editor1_draft` LLM Output

Reuse existing contract:
- `EditorDraftOutput`

LLM should return:
- `draft_id`
- `draft_version`
- `sections`
  - `section_id`
  - `title`
  - `paragraphs`
    - `paragraph_id`
    - `text`
    - `claim_ids`
    - `evidence_ids`
    - `confidence`
    - `limitations`

Do not invent a new public shape.

## 7. Validation To Run After Step A-C

Minimum:

```powershell
python -m ruff check packages\research_harness packages\research_reports tests
python -m py_compile packages\research_harness\runner.py packages\research_harness\nodes.py packages\research_harness\real_nodes.py packages\research_reports\dossier.py
pytest -q tests\test_research_harness_tooling.py
pytest -q tests\test_research_harness_graph.py
pytest -q tests\test_research_api.py
pytest -q tests\test_research_provider_integration.py tests\test_deepseek_provider.py
```

If LLM-backed `editor1_draft` goes live in provider-backed path, also run one
real smoke:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\tooling_editor1_live_v1 --query "2025年低空经济上市公司年报披露与官方政策证据" --max-rounds 2 --max-loop-count 1
```

Success criteria for that smoke:
- run succeeds
- `editor1_draft` step has `tool_traces`
- dossier contains tool trace section
- no forbidden tool usage

## 8. Known Risk To Watch

The biggest immediate risk is not provider quality.
It is signature mismatch after runner was changed to pass `tool_session`.

So the very first thing the next thread should do is fix all node signatures
before deeper logic changes.

## 9. Handoff Summary

Current repo state is a partially completed Step 1:

Completed:
- tooling foundation files
- state field `tool_traces`
- runner partial harness integration
- dossier partial tool trace rendering
- plan/status handoff update

Not completed:
- node signature adaptation
- `editor1_draft` real LLM + tool call
- tooling test file
- step/dossier verification run
- expansion to `editor2_review`, `chief_gate`, `finalize_report`

The next thread should resume from:
- `.agent/PLANS/langgraph-llm-tooling-harness-v1.md`
- current phase:
  - `active_phase1_foundation_and_editor1`
