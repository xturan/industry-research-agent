# LangGraph Live Stability Validation v1

Status: completed_live_validation

Created: 2026-06-14

Primary active PLAN: no (completed)

## Objective

Use real provider APIs to validate current LangGraph workflow stability on
practical research cases, with visible report artifacts and dossier inspection.

## Task Classification

- Primary area: `eval_policy_ops`
- Secondary areas: `research_workflow`, `provider_layer`
- Execution mode: `local_direct`

## Scope

In scope:

- run a small provider-backed live matrix with real DeepSeek and Tavily calls
- cover policy/procurement, listed-company disclosure, local project/policy,
  and multi-city comparison cases
- inspect outputs for:
  - run status
  - gate decision
  - final report artifact
  - dossier generation
  - tool trace visibility
  - evidence obligation coverage
  - search instability

Out of scope:

- changing production workflow code
- changing public response shape
- tuning source-routing logic based on a single case
- declaring graph-v1 the default product path

## Constraints

- Do not expose API keys in artifacts or logs.
- Treat cases as stability probes, not hard-coded optimization targets.
- Do not modify protected contracts.
- Keep cost bounded by using a 4-case matrix with `max_rounds=2` and
  `max_loop_count=1`.

## Phases

### Phase 1: Prepare Live Cases

Status: completed

Create a small case file under `data/tmp` using UTF-8 JSON to avoid PowerShell
Chinese query escaping issues.

### Phase 2: Run Real API Matrix

Status: completed

Run `scripts/graph_provider_backed_smoke_matrix.py` with the case file and
record the output directory.

### Phase 3: Inspect Artifacts And Report

Status: completed

Inspect matrix summary and per-case dossiers. Summarize whether the workflow
can complete reports and where it still asks for human review or risk review.

## Validation

Commands:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
python scripts\graph_provider_backed_smoke_matrix.py --reset-each-case --cases-file data\tmp\langgraph_live_stability_cases_20260614.json --output-dir data\tmp\langgraph_live_stability_validation_v1
```

Pass criteria:

- all cases finish with `status=succeeded`
- every case has a dossier artifact
- every case has provider-backed planner metadata
- every case includes tool trace visibility in the dossier
- final report artifact is generated when the run reaches a terminal graph state

Interpretation criteria:

- `PASS` means the report is generated and gate accepts auto-finalization.
- `REVIEW_RISK` means the graph generated artifacts but found reliability or
  coverage risk before clean release.
- `HUMAN_REVIEW` means the graph generated artifacts but asks for manual review,
  usually after loop budget or quality gate constraints.

## Progress

- Plan created for real API validation.
- Live matrix executed on 2026-06-14 with 4 real cases.
- Result: 3 succeeded, 1 failed.
- Successful cases produced dossiers and report artifacts.
- One disclosure-heavy case failed twice at `collect_sources` with a read
  timeout before any search events were captured.
- Stability conclusion: the graph can complete real reports, but this query
  family still has a reproducible early-source-fetch timeout risk.

## Risks

- Provider/search instability may affect observed results.
- Some live sources may change or disappear.
- Chinese query handling must use UTF-8 files rather than shell literals.
- A subset of disclosure-heavy real queries may fail before the search layer
  emits events, so report generation is not uniformly reliable yet.

## Next Action

Archive this plan after status/validation snapshots are updated.
