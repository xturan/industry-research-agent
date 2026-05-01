# Source Transaction Local Record Adapter Remediation v1

Status: superseded_unexecuted

Created: 2026-04-29

Primary active PLAN: no

Superseded by:

- `.agent/PLANS/source-family-evidence-backbone-v1.md`

Supersession reason:

- Replaced by a harder source-family backbone strategy that treats the 12-case set as a smoke gate and prioritizes reusable procurement, project, statistics/fiscal, and environmental/land source families instead of a narrower transaction/local-record remediation framing.

Supersedes execution follow-up from:

- `.agent/PLANS/archive/source-multigranular-evidence-sufficiency-v1.md`

## Objective

Fix the dominant blocker from Source Multigranular Evidence Sufficiency v1 Phase 5: transaction/procurement/project/local-record evidence remains insufficient even after better multi-city and multi-sector query planning.

Latest 12-case gate:

- Live: `12 success / 0 runtime error`
- DeepSeek audit schema: `12 success`, shape diagnostics `0`
- Verdicts: `9 fail / 3 weak_pass`
- Failed quality gate:
  - weak/pass target `3/12` vs required `>=6/12`
  - fail count `9` vs required `<=6`
  - `tender_or_procurement=7` vs required `<=5`
- Passed but still fragile:
  - `project_list=5`
  - `local_government=3`
  - `statistics=3`
  - `environmental_or_land_record=2`

This PLAN must improve reusable evidence backbones, not overfit the 12-case or 50-query samples.

## Task Classification

- Primary area: `source_layer`
- Secondary areas: `domestic_source_collectors`, `eval_policy_ops`, `provider_layer`

Protected contracts:

- EvidenceBundle schema
- EvidenceItem citation fields
- `source_quality_summary` shape
- research analyze response shape
- provider abstraction semantics
- source routing response shape
- task/job status semantics
- direct-keep primary paths
- legacy `enable_source_acquisition=False` behavior

No protected-contract change is allowed without an explicit Architecture Gate section.

## Scope

In scope:

- Public-resource / government-procurement evidence routing and extraction.
- Project-list and key-project evidence profiles.
- County and city exact-local source profiles for project, land/environment, statistics/fiscal, and procurement signals.
- PDF/static extraction diagnostics and fallback decisioning for official records and public-resource documents.
- Region-matched disclosure and enterprise evidence only where it supports project/local claims.
- Offline and 12-case live validation.

Out of scope unless reopened:

- Full 50-query live run.
- Browser automation as default.
- OCR.
- Login-gated, paid, or private data.
- Direct securities investment advice.
- Public API response-shape changes.

## Design Direction

Treat the remaining failures as source-family backbone gaps:

```text
Evidence Obligation
  -> transaction/project/local-record source family
  -> exact-local or parent-fallback decision
  -> search-assisted discovery or direct structured adapter
  -> extraction diagnostics
  -> evidence sufficiency gate
```

Priority source families:

- `tender_or_procurement`
- `project_list`
- `regulatory_record`
- `environmental_or_land_record`
- `statistics`
- `local_government`

## Inputs

- Phase 5 run:
  - `data/tmp/source_quality_stress_eval/runs/source_multigranular_evidence_sufficiency_v1_phase5_live_v1`
- Phase 4 matrix:
  - `data/tmp/source_quality_stress_eval/source_multigranular_evidence_sufficiency_phase4/adapter_decision_matrix.json`
  - `data/tmp/source_quality_stress_eval/source_multigranular_evidence_sufficiency_phase4/adapter_decision_matrix.md`
- Current batch diagnostics:
  - `source_coverage_gaps`
  - `evidence_sufficiency_gaps`
  - `source_roadmap.requires_reopening_plan_items`

## Phases

### Phase 0: Blocker Matrix Freeze

Objective:

- Freeze the exact remaining blocker families before implementation.

Tasks:

- Group missing and weak evidence by source family, not query ID.
- Distinguish:
  - discovery/routing failure
  - source profile missing
  - adapter required
  - extraction/PDF failure
  - evidence scoring/reporting-only issue
- Define the first implementation slice.

Acceptance criteria:

- A blocker matrix artifact exists.
- The first slice targets a source-family class, not an individual query.
- Full 50-query live remains deferred.

### Phase 1: Public-Resource And Procurement Backbone

Objective:

- Reduce `tender_or_procurement` misses without broadening generic Tavily fanout.

Tasks:

- Strengthen public-resource/procurement domain and URL pattern recognition.
- Add exact-local public-resource profile hints where already represented by reusable city/county source patterns.
- Prefer detail pages and award/tender records over portal home pages.
- Preserve structured partial-failure behavior.

Acceptance criteria:

- Procurement/project smoke subset shows fewer `tender_or_procurement` gaps.
- Generic policy pages do not masquerade as procurement evidence.

### Phase 2: Project List And Key-Project Backbone

Objective:

- Improve `project_list` evidence using official key-project, filing, approval, start, production, and development-zone sources.

Tasks:

- Add reusable project-list signal rules.
- Strengthen city/province project phrase ordering.
- Keep project evidence distinct from policy interpretation.

Acceptance criteria:

- Project-list missing count does not exceed current Phase 5 baseline.
- At least one project subset improves without increasing invalid candidates.

### Phase 3: Exact-Local Record Backbone

Objective:

- Improve county/city exact-local evidence transparency and recall.

Tasks:

- Strengthen local government, statistics/fiscal, environmental/land, and regulatory source patterns.
- Maintain explicit parent fallback fields:
  - `parent_evidence_only`
  - `local_claim_allowed`
  - `fallback_level`
  - `fallback_source`
- Do not allow parent evidence to satisfy exact-local claims silently.

Acceptance criteria:

- County/city smoke cases clearly separate exact-local evidence from parent fallback.
- Exact-local retrieval improves where public static sources exist.

### Phase 4: PDF And Extraction Decision Gate

Objective:

- Reduce false weak evidence caused by failed official PDFs, public-resource documents, or zero-text extractions.

Tasks:

- Classify extraction failures into:
  - static HTML success
  - Crawl4AI markdown success
  - static PDF success
  - PDF download failure
  - PDF zero text
  - timeout
  - anti-bot / forbidden
- Decide which failures need adapter work versus explicit evidence gap reporting.

Acceptance criteria:

- Extraction failure classes are visible in batch diagnostics.
- No failed PDF or zero-text document is counted as strong evidence.

### Phase 5: 12-Case Gate Rerun

Objective:

- Re-run the same 12-case gate and compare against the current Phase 5 baseline.

Acceptance criteria:

- Live: `12 success / 0 runtime error`.
- DeepSeek audit: `12 success`, shape diagnostics `0`.
- `tender_or_procurement <= 5`.
- `project_list <= 5`.
- `local_government <= 3`.
- `statistics <= 3`.
- `environmental_or_land_record <= 2`.
- Weak/pass count improves from `3/12`, or a narrower blocker is recorded.

## Continue Rule

Continue automatically between phases only when:

- acceptance criteria pass
- validation commands pass
- no protected-contract change is needed
- no browser automation/OCR/login-gated source is required
- cost and latency stay visible

Stop if the next safe step requires a new adapter or extraction strategy that changes protected contracts.

## Validation Loop

Focused checks:

```powershell
python -m ruff check <changed files>
python -m py_compile <changed files>
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_retrieval_plan.py tests\test_sources_disclosure_mapping.py
pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py
pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py
```

Live gate:

```powershell
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\strong_evidence_smoke_cases_v1.json --mode extraction_inspection --max-search-tasks 2 --max-rounds 2 --max-candidates 3 --content-chars 1200 --output-dir data\tmp\source_quality_stress_eval\runs\source_transaction_local_record_adapter_v1_phase5_live_v1
python data\tmp\_source_quality_llm_audit.py --run-dir data\tmp\source_quality_stress_eval\runs\source_transaction_local_record_adapter_v1_phase5_live_v1 --provider deepseek --model deepseek-v4-pro --thinking true --reasoning-effort max --timeout 240 --max-output-tokens 8192 --print-summary
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\source_transaction_local_record_adapter_v1_phase5_live_v1 --print-json
```

## Done Condition

This PLAN is done when either:

- the 12-case gate improves enough to reopen staged 50-query planning, or
- a narrower blocker is recorded with source-family evidence and no full 50-query live spend.

## Progress

- 2026-04-29: PLAN created as successor blocker from Source Multigranular Evidence Sufficiency v1.

## Current Phase

Phase 0 pending user confirmation.

## Risks And Rollback

Risks:

- Overfitting city/county source profiles to the smoke cases.
- Increasing Tavily spend through broad transaction fanout.
- Treating failed PDFs or portal pages as strong evidence.
- Requiring browser automation/OCR, which is out of scope without Architecture Gate.

Rollback:

- Revert only files changed under this PLAN.
- Keep `source_multigranular_evidence_sufficiency_v1_phase5_live_v1` as comparison baseline.
- Disable new source-family rules if they increase source drift or cost without improving evidence sufficiency.

## Next Action

Await user confirmation before implementation. First executable slice is Phase 0: blocker matrix freeze.
