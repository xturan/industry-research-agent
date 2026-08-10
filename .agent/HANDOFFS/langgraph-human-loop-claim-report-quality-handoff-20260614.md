# LangGraph Human Loop Claim Report Quality Handoff

Date: 2026-06-14

Primary active plan:
- `.agent/PLANS/langgraph-human-loop-claim-report-quality-v1.md`

Current status:
- `active_phase0_problem_freeze_and_contract_design`

Primary area:
- `research_workflow`

Secondary areas:
- `content_factory`
- `provider_layer`
- `eval_policy_ops`
- `task_substrate`

## 1. Why This New Plan Exists

The previous LangGraph work line solved the tooling/harness problem:

- node-scoped tool authorization exists
- provider-backed `editor1_draft`/`editor2_review`/`chief_gate`/`finalize_report`
  are wired
- tool traces are visible in step outputs and dossier

However, a real live case review on `S03` showed that the next bottleneck is no
longer “can the graph run” but “is the workflow a usable research product”.

This handoff exists so the next thread does not continue optimizing the old
tooling slice while missing the actual product issues.

## 2. Real Baseline Evidence From S03

Reference artifacts:

- `data/tmp/langgraph_live_stability_validation_v1/per_case/S03_local_hefei_project_policy/response.json`
- `data/tmp/langgraph_live_stability_validation_v1/per_case/S03_local_hefei_project_policy/dossier.md`

Key observed facts:

1. `HUMAN_REVIEW` is not a real human loop.
   - `chief_gate` first returned `REVIEW_RISK`, then later `HUMAN_REVIEW`
   - graph still continued automatically into `human_review` node and then
     `finalize_report`
   - the user never received a real decision prompt or resume boundary

2. Evidence strength is too flat.
   - `claim_support_matrix.avg_support_strength = 0.68`
   - many `background_support` evidence items also show `support_strength=0.68`
   - the score currently lacks practical separation power

3. Claim architecture is too thin.
   - `build_claims` produced only one claim:
     - `claim_policy_primary`
   - this is too coarse for downstream review and report writing

4. Final report is still JSON-heavy.
   - `final_report` is effectively a preview JSON
   - `tool_composed_report` is still a structured summary object
   - there is no real claim-driven readable report body yet

5. Prompt/context engineering is still thin.
   - context packs exist and are visible
   - but prompt/context design is not yet formalized as a first-class product
     surface

6. `editor1_draft` did not cleanly use the live LLM output.
   - provider call succeeded
   - returned output had confidence values like `0.75`
   - strict contract validation failed
   - node fell back to structured fallback output

This means the workflow is mechanically operational, but still product-rough.

## 3. What Has Already Been Done In This Thread

### 3.1 Plan and status alignment

Created:

- `.agent/PLANS/langgraph-human-loop-claim-report-quality-v1.md`

Updated:

- `.agent/STATUS.md`
- `docs/technical-roadmap-evolution.md`

Meaning:

- the active LangGraph line has been switched from generic opt-in/promotion
  discussion to a concrete report-quality/human-loop plan

### 3.2 Problem freeze completed

The new plan now includes:

- frozen current behavior vs target behavior for all 5 user-raised issues
- explicit implementation phases
- explicit implementation sequence
- likely file targets
- protected contracts and stop conditions

### 3.3 Memory and project context updated

Recorded:

- user correction that `HUMAN_REVIEW` must become a real human decision point
- user requirement for:
  - better support-strength scoring
  - multiple claims
  - readable final report
  - formal prompt/context engineering

## 4. Current Active Plan Shape

Plan:
- `.agent/PLANS/langgraph-human-loop-claim-report-quality-v1.md`

Current phase:
- `Phase 0: Problem Freeze And Contract Design`
- Status: `completed`

Next implementation phase:
- `Phase 1: Human Review Product Contract`

Implementation order is now frozen as:

1. human-review interruption contract
2. state/schema/API visibility for pending review
3. claim-family and evidence-strength redesign
4. readable report generation redesign
5. prompt/context asset formalization
6. real-case validation rerun

## 5. Exact Next Thread Starting Point

The next thread should start with **Phase 1: Human Review Product Contract**.

That means:

### Step A: Design the interruption boundary first

Before changing writing/report quality:

- decide what exact internal state means “waiting for human review”
- decide whether the graph should terminate into a pending state or use an
  interrupt/resume boundary
- define the allowed human actions:
  - approve current report
  - request add evidence
  - request rewrite
  - reject / stop

### Step B: Identify the minimal affected contracts

Likely files to inspect first:

- `packages/research_harness/nodes.py`
- `packages/research_harness/real_nodes.py`
- `packages/research_harness/runner.py`
- `packages/research_harness/state.py`
- `packages/research_harness/schemas.py`
- `apps/api/routes/deep_research.py`
- `packages/tasks/**` if async pending-review exposure is needed

The key question is not “how do we render the final report”.
It is first:

“how does `HUMAN_REVIEW` stop the flow and surface a real decision request”.

### Step C: Only after that move into claim/evidence redesign

Do not start with claim count or report prose first.

Reason:

- if human review still silently finalizes, the workflow semantics stay wrong
  even with nicer prose

## 6. Critical Constraints To Keep In Mind

Do not silently change:

- `/deep-research/graph/analyze` response shape
- legacy `/deep-research/analyze` response shape
- legacy `/research/analyze` response shape
- `runs` / `run_steps` meaning
- current checkpoint resume semantics
- `research_reports.dossier_path`

Allowed additive directions later:

- pending-human-review metadata
- richer internal claim/evidence/report records
- readable report artifact content
- prompt/context registries

## 7. Recommended Concrete Phase-1 Questions To Answer In Code/Design

The next thread should answer these explicitly:

1. What exact field in graph state marks a run as “waiting for human review”?
2. How is that state exposed in API response and task/job view?
3. What payload does the user need to make a decision?
4. How does resume map back into graph routing?
5. Does `finalize_report` run before human approval, after human approval, or
   in two layers (draft report vs approved report)?

If these are left implicit, later claim/report work will drift again.

## 8. Why The Other Four Problems Should Wait One Phase

They are real, but sequencing matters:

- claim count
- evidence strength separation
- readable final report
- prompt/context formalization

All of them depend on understanding whether the workflow is:

- auto-pass
- risk-review
- human-approval-gated

So Phase 1 must settle the human loop semantics first.

## 9. Validation To Use When Implementation Starts

At minimum after Phase 1 implementation:

```powershell
python -m ruff check packages\research_harness apps\api\routes\deep_research.py tests
python -m py_compile packages\research_harness\runner.py packages\research_harness\nodes.py packages\research_harness\real_nodes.py packages\research_harness\schemas.py
pytest -q tests\test_research_harness_graph.py
pytest -q tests\test_research_api.py
pytest -q tests\test_tasks_service.py tests\test_tasks_api.py
```

If task/run semantics are touched, also run the task-flow validation slice.

## 10. Handoff Summary

The repo is no longer blocked on tooling harness work.

It is now blocked on product semantics:

- real human review
- useful claim architecture
- useful evidence strength
- readable final report
- formal prompt/context engineering

The next thread should not reopen the old tooling plan.

It should resume from:

- `.agent/PLANS/langgraph-human-loop-claim-report-quality-v1.md`
- current effective next step:
  - `Phase 1: Human Review Product Contract`
