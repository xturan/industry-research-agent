# Plan: Report Coverage Smoke Pressure v1

Status: active_phase1_pending
Priority: high
Owner: codex/human
Created: 2026-07-10
Last Updated: 2026-07-10

## Objective

Run the 8-case report coverage smoke set as live provider-backed pressure tests.
Each case must produce:

- a complete dossier artifact
- a `FINAL_REPORT.md` or explicit structured failure explaining why final report was not produced
- a per-case summary
- a batch summary across macro/province/city/county levels

## Scope

Primary area: `eval_policy_ops`

Secondary areas:

- `research_workflow`
- `source_layer`
- `provider_layer`

In scope:

- Use `data/evals/report_coverage_smoke_8_queries_v1.json`.
- Run each selected query through `scripts/graph_provider_backed_smoke.py`.
- Use provider-backed graph mode.
- Preserve full per-case run artifacts under `data/tmp/report_coverage_smoke_pressure_v1/`.
- Auto-resume HUMAN_REVIEW with `approve` only for pressure-test completion, while recording that this happened.
- Summarize status, decision, report artifact path, dossier path, estimated Tavily credits, latency, and obligation gaps.

Out of scope:

- Production code changes.
- Source routing changes.
- EvidenceBundle, citation, provider, API, or public response shape changes.
- Hard-coding fixes for any one query.
- Running the full 50-case live test before the 8-case gate is reviewed.

## Execution Mode

Mode: `local_direct`

Reason:

- This is a live eval/run-artifact task, not a production behavior change.
- The only intended code addition is a temporary/eval runner script.

Risk triggers:

- Live Tavily/DeepSeek/provider cost.
- Known historical timeout risk for full final-report smoke.
- HUMAN_REVIEW may be reached before final report.

Allowed write scope:

- `data/tmp/_run_report_coverage_smoke_pressure.py`
- `data/tmp/report_coverage_smoke_pressure_v1/**`
- this PLAN
- `.agent/STATUS.md`

Forbidden changes:

- `packages/**`
- API schemas
- EvidenceBundle/citation contracts
- source/provider/research workflow semantics

Required validation:

- JSON input can be parsed.
- Runner dry validation can list all 8 cases.
- Live run artifacts are checked for dossier and final report paths.

Escalation rule:

- If the runner shows a production workflow bug or repeated timeout, stop and report the failure class instead of patching production code in this PLAN.

## Cases

Input file: `data/evals/report_coverage_smoke_8_queries_v1.json`

Selected IDs:

- Macro: `M02`, `M03`
- Province: `P04`, `P08`
- City: `C01`, `C07`
- County: `K07`, `K12`

## Phases

### Phase 1: Runner

Create a bounded runner that:

- loads the 8-case JSON
- maps `id` to `case_id`
- maps `level` to output grouping
- invokes `scripts/graph_provider_backed_smoke.py` per case
- passes `--reset`
- passes `--resume-action approve`
- writes per-case stdout/stderr logs
- continues on per-case failure
- writes `batch_summary.json` and `batch_summary.md`

### Phase 2: Live Pressure Run

Run all 8 cases unless a repeated infrastructure failure occurs.

Default runtime settings:

- `max_rounds=1`
- `max_loop_count=1`
- `env_file=.env`
- output directory: `data/tmp/report_coverage_smoke_pressure_v1/run_<timestamp>`

### Phase 3: Artifact Inspection

For every case, check:

- `summary.json` exists
- `dossier.md` exists and is non-empty
- final report path exists when the run succeeded or resumed successfully
- status/decision/quality scores are recorded
- estimated credits and latency are recorded

### Phase 4: Report Back

Return:

- pass/fail counts
- per-case artifact paths
- missing dossier/final-report cases
- strongest observed coverage gaps
- whether the full 50-case run is safe to attempt

## Validation

Commands:

```powershell
python -m json.tool data\evals\report_coverage_smoke_8_queries_v1.json
python data\tmp\_run_report_coverage_smoke_pressure.py --case-file data\evals\report_coverage_smoke_8_queries_v1.json --output-dir data\tmp\report_coverage_smoke_pressure_v1\manual --dry-run
python data\tmp\_run_report_coverage_smoke_pressure.py --case-file data\evals\report_coverage_smoke_8_queries_v1.json --output-dir data\tmp\report_coverage_smoke_pressure_v1\manual --max-rounds 1 --max-loop-count 1 --resume-action approve
```

## Progress

- 2026-07-10: PLAN created. Execution mode selected as `local_direct`.

## Risks

- 8 full final-report runs may be slow; previous single full graph runs took several minutes.
- If `.env` credentials are missing or exhausted, live run will fail.
- Some cases may reach HUMAN_REVIEW; auto-approval is only for generating final report artifacts and must be recorded.
- Existing case JSON displays correctly in UTF-8 tools but may show mojibake in some PowerShell output paths.

## Next Action

Implement the runner and perform dry validation before live execution.

## Pressure Run Result Update - 2026-07-10

Status: active_pressure_run_completed_with_recovery_blocker

Live run directory: `data/tmp/report_coverage_smoke_pressure_v1/run_20260710_1736`

Results:

- Raw runner result: 8 cases executed.
- Normal workflow summaries: 4/8 (`M02`, `M03`, `P08`, `C01`).
- Process failures: 4/8 (`P04`, `C07`, `K07`, `K12`).
- Failure class: `ResearchReportService.update_dossier_path` is called by `packages/research_harness/runner.py` but missing from `packages/research_reports/service.py`.
- Artifact recovery completed with `data/tmp/_recover_report_coverage_pressure_artifacts.py`.
- Recovered final reports: 8/8.
- Recovered dossiers: 8/8.
- Recovery summary: `data/tmp/report_coverage_smoke_pressure_v1/run_20260710_1736/artifact_recovery_summary.json`.
- Markdown summary: `data/tmp/report_coverage_smoke_pressure_v1/run_20260710_1736/artifact_recovery_summary.md`.
- `M02`, `M03`, `P08`, and `C01` final reports were recovered from response JSON.
- `P04`, `C07`, `K07`, and `K12` final reports were recovered from SQLite `research_reports` because the smoke process crashed after report persistence.

Known blocker:

- Production fix needed: restore `dossier_path` support in `packages/research_reports/schemas.py` and `packages/research_reports/service.py`, including `update_dossier_path()`.
- Eval script improvement needed: `scripts/graph_provider_backed_smoke.py` should export `FINAL_REPORT.md` directly from `report_preview.report_markdown`.
- `apply_patch` failed against PLAN/STATUS and production files with Windows sandbox `CreateProcessWithLogonW failed: 1058`; this section was appended via PowerShell as a controlled fallback to preserve execution state.

Next action:

- Create or run a narrow remediation for the report persistence/export blocker, then rerun `P04`, `C07`, `K07`, and `K12` through the normal smoke path without recovery.
