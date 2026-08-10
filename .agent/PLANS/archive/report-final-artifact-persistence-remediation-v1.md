# Report Final Artifact Persistence Remediation v1

Status: completed
Created: 2026-07-15
Execution mode: full_subagent
Primary area: research_workflow
Secondary areas: task_substrate, eval_policy_ops, provider_layer
Parent PLAN: `.agent/PLANS/anysearch-production-discovery-integration-v1.md`

## Objective

Restore the existing dossier-path persistence contract and make the provider-backed smoke runner export `FINAL_REPORT.md` directly when a real report preview exists, so the normal graph path no longer depends on the recovery script for dossier/report artifact persistence.

## Task Classification

- Primary area: `research_workflow`
- Secondary areas: `task_substrate`, `eval_policy_ops`, `provider_layer`
- Request type: planning/director gate only in this step
- Protected contract focus: existing `dossier_path` persistence and report artifact export semantics

## Problem Statement

The 2026-07-10 eight-case pressure run completed normally for M02, M03, P08, and C01, but P04, C07, K07, and K12 failed during report persistence because `ResearchReportService.update_dossier_path` and the schema field had disappeared from the implementation. A recovery script later reconstructed 8/8 artifacts, masking the broken normal path. The AnySearch RW8 gate reproduced the same defect.

## Scope

- Restore additive `dossier_path` support in `ResearchReportCreate`, `ResearchReportSummary`, and `ResearchReportView`.
- Add backward-compatible SQLite column creation/migration in `ResearchReportService._ensure_table`.
- Persist, read, list, and update `dossier_path`.
- Keep `report_json["dossier_path"]` synchronized when the path is updated.
- Export `FINAL_REPORT.md` directly from `report_preview.report_markdown` in `scripts/graph_provider_backed_smoke.py`.
- Add focused regression tests for old databases, save/get/update behavior, and final-report export.
- Rerun representative cases P04 and K12 from `report_coverage_smoke_8_queries_v1.json`.
- Compare normal-path artifacts with the prior recovered artifacts.

## Protected Contracts

- This PLAN restores an already-tested field and method; it does not introduce a new public response shape.
- `dossier_path` is treated as an existing contract because the focused regression suite already exercises `ResearchReportCreate.dossier_path`, `ResearchReportView.dossier_path`, and `ResearchReportService.update_dossier_path`.
- EvidenceBundle, EvidenceItem citations, source-quality shape, graph decision semantics, task/job/run-step semantics, and report markdown structure remain unchanged.
- Existing databases without a `dossier_path` column must migrate additively.
- A missing report body must remain a transparent failure; the runner must not synthesize a fake final report.

## Non-Goals

- No EvidenceBundle or citation redesign.
- No changes to AnySearch/Tavily routing or source ranking.
- No query-specific retrieval rules for P04 or K12.
- No full 50-query live run.
- No use of the recovery script as the normal production path.

## Agent Execution Contract

- Director: confirm this is restoration of the existing persistence contract and freeze the P04/K12 comparison gate.
- Group 2 implementation: `packages/research_reports/schemas.py`, `packages/research_reports/service.py`, `scripts/graph_provider_backed_smoke.py`, and focused tests only.
- Group 3 code-quality: targeted Ruff, compile, and focused pytest.
- Group 3 functional validation: normal-path P04 and K12 dossier/final-report generation plus comparison to the 2026-07-10 recovered artifacts.
- Summarizer: only after both representative cases produce direct artifacts or fail transparently for an unrelated provider reason.

## Real-World Validation Plan

Purpose: validate contract restoration, not query-specific retrieval quality.

Baseline evidence for "restoration" rather than "new feature":
- `tests/test_research_run_dossier.py` already asserts `ResearchReportCreate(..., dossier_path=...)`, `ResearchReportService.update_dossier_path(...)`, and `fetched.dossier_path`.
- `scripts/graph_provider_backed_smoke.py` already consumes `response["dossier_path"]` and writes `dossier.md`, so the missing behavior is a broken normal-path persistence/export chain rather than a new downstream contract.

Case design:
- `P04` is the richer province-level Anhui NEV coordination case. It is the positive-path comparison for direct dossier persistence plus direct `FINAL_REPORT.md` export when `report_preview.report_markdown` is present.
- `K12` is the evidence-scarce Ruoqiang industrialization case. It is the transparency-path comparison for "no fake report" semantics: dossier persistence must still work, and `FINAL_REPORT.md` must be exported only if the workflow actually produced non-empty report markdown.

Comparison rules against the 2026-07-10 recovered artifacts:
- Compare contract-level outputs only: presence/absence of `dossier.md`, presence/absence of `FINAL_REPORT.md`, `summary.json` artifact pointers, workflow `status`, `decision`, and visible evidence/claim diagnostics.
- Do not require byte-identical markdown to the recovered artifacts because the current discovery path is AnySearch-first and may legitimately change source mix and report wording.
- Require compatibility on artifact semantics:
  - if `response["dossier_path"]` is non-empty and readable, the normal path must write `dossier.md` without recovery;
  - if `report_preview.report_markdown` is non-empty, the normal path must write `FINAL_REPORT.md` directly and expose its path in `summary.json`;
  - if `report_preview.report_markdown` is empty, no `FINAL_REPORT.md` may be synthesized, and `summary.json` must make that absence explicit rather than surfacing a persistence failure.

Pass criteria:
- `P04`: successful run must prove the restored direct-export path by producing `dossier.md`, `FINAL_REPORT.md`, `response.json`, and `summary.json` without the recovery script.
- `K12`: successful run must prove the restored persistence contract by producing `dossier.md`, `response.json`, and `summary.json`; `FINAL_REPORT.md` is required only when non-empty report markdown exists.
- For both cases, any provider/network/runtime failure must be classified separately from persistence failure.

## Milestones

### M1 Contract Restoration

- Add failing/confirming tests for dossier-path save, retrieval, update, and old-table additive migration.
- Restore the schema and service implementation.

Acceptance:
- Existing `test_research_report_service_persists_dossier_path` passes.
- Old SQLite tables are upgraded without deleting reports.
- `update_dossier_path` updates both the column and embedded report JSON.

### M2 Final Report Export

- Add a small export helper used by the smoke script.
- Write `FINAL_REPORT.md` only when non-empty `report_preview.report_markdown` exists.
- Expose the artifact path/existence in `summary.json`.

Acceptance:
- Focused test proves exact markdown is written.
- Empty report preview does not create a misleading file.

### M3 Focused Regression

- Run report/dossier and graph-focused tests.
- Run mandatory research-contract checks.

Acceptance:
- Targeted Ruff and compile pass.
- Focused report/dossier tests pass.
- Existing graph response and report-preview tests remain compatible.

### M4 Live Comparison

- Rerun P04: 安徽省新能源汽车产业链全省协同。
- Rerun K12: 若羌县盐湖锂钾与新能源产业化条件。
- Use bounded rounds and the configured AnySearch-first discovery path.

Acceptance:
- `P04` successful normal-path run writes `dossier.md`, `FINAL_REPORT.md`, `response.json`, and `summary.json` directly.
- `K12` successful normal-path run writes `dossier.md`, `response.json`, and `summary.json` directly, and writes `FINAL_REPORT.md` only when non-empty `report_preview.report_markdown` exists.
- No recovery script is invoked.
- Comparison records report length, sections, citations/evidence diagnostics, decision, source-family coverage, and evidence-gap transparency.
- Provider/network failure is recorded as such and is not confused with persistence failure.

### M5 Parent Gate Closure

- Update the AnySearch parent PLAN RW8 result.
- Archive this PLAN and the parent PLAN only if the full normal path passes.

## Validation Commands

```powershell
python -m ruff check packages/research_reports/schemas.py packages/research_reports/service.py scripts/graph_provider_backed_smoke.py tests/test_research_run_dossier.py
python -m py_compile packages/research_reports/schemas.py packages/research_reports/service.py scripts/graph_provider_backed_smoke.py
pytest -q tests/test_research_run_dossier.py
pytest -q tests/test_research_harness_graph.py -k "dossier or report_preview or report_artifact"
pytest -q tests/test_agents_workflow.py tests/test_research_api.py tests/test_research_provider_integration.py tests/test_deepseek_provider.py
```

## Continue Rule

After each milestone passes, continue automatically. Stop only for a breaking protected-contract requirement, repeated validation failure without a safe repair, missing credentials/network for the live comparison, or data corruption risk.

## Done Condition

- The normal graph path persists `dossier_path`.
- The smoke runner writes a real `FINAL_REPORT.md` whenever non-empty `report_preview.report_markdown` exists.
- P04 no longer requires artifact recovery for dossier/final-report artifacts when its graph run succeeds.
- K12 no longer requires artifact recovery for dossier artifacts, and no longer misclassifies missing preview markdown as a persistence defect.
- The parent AnySearch RW8 gate has a recorded result.

## Rollback

- Revert only the additive schema/service/export changes from this PLAN.
- Existing `dossier_path` columns remain harmless if code rollback is required.
- Preserve prior recovered artifacts for comparison and audit.

## Risks

- SQLite and PostgreSQL column discovery/migration differ; changes must remain portable or explicitly scope the lightweight migration.
- A graph HUMAN_REVIEW decision may legitimately withhold final report generation.
- Live provider latency may prevent both cases from completing in one run.
- Prior recovered reports may differ because the discovery provider changed from Tavily to AnySearch.

## Progress

- [x] Existing failure baseline and eight-case set identified.
- [x] P04 and K12 selected as representative comparison cases.
- [x] Director gate confirmed this is a backward-compatible restoration of the existing `dossier_path`/report-artifact contract.
- [x] M1 contract restoration.
- [x] M2 final-report export.
- [x] M3 focused regression.
- [x] M4 live comparison.
- [x] M5 parent gate closure.

## Completion Snapshot

- Restored additive `dossier_path` schema/service persistence, old-table migration, JSON fallback, list/get consistency, and update synchronization.
- Added direct smoke export of `FINAL_REPORT.md` only when real `report_preview.report_markdown` exists.
- Target Ruff and compile passed.
- Four focused persistence/export compatibility tests passed.
- Mandatory research-contract suite: `24 passed`.
- P04 normal path: `PASS`, `report_preview.report_id=1`, dossier exported, final report exported, 10/10 search events successful.
- K12 normal path: `PASS`, `report_preview.report_id=1`, dossier exported, final report exported, 10/10 search events successful.
- Neither live case invoked the recovery script.
- Comparison artifact: `data/tmp/anysearch_final_report_remediation/COMPARISON.md`.

## Remaining Quality Risks

- K12 regional precision is `0.2`; location parsing incorrectly expands the query body into pseudo-locations.
- P04 and K12 both report one uncovered location obligation despite final `PASS`.
- Report citations remain concentrated in source tables rather than claim-level inline citations.
- Context packs remain severely over budget.
- Isolated SQLite smoke databases both allocate `run_id=1`, so the global dossier path can collide; case-local copied artifacts remain isolated.
- Three unrelated stale assertions in the full dossier test file remain: old English dossier headings and an old `_call_llm(step=...)` signature.

## Next Action

Archive this PLAN. Open a separate quality PLAN only for location parsing, claim-level citations, context-pack budgets, and isolated-run artifact paths; do not reopen persistence remediation.
