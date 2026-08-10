# Deep Research Readable Report Quality v2

Status: superseded_partial_quality_gate_failed

Created: 2026-06-17

Primary active PLAN: no

Superseded by:

- `.agent/PLANS/deep-research-readable-report-remediation-v1.md`

Status correction:

- This PLAN produced useful intermediate improvements, including a report
  quality inspector, richer report structure, and live smoke artifacts.
- It must not be treated as completed productization. Re-running
  `scripts/report_quality_inspect.py` against all four Phase 6 smoke cases
  classified every case as `workflow_pass_product_fail`.
- The most serious remaining contradiction is that `case1_hefei` still has
  `decision=PASS` while `gate_obligation_gap_count=1`.
- The follow-up remediation PLAN now owns the remaining work.

PRD:

- `docs/prd/deep_research_readable_report_prd_v0_1.md`

## Objective

Upgrade the opt-in LangGraph Deep Research path from "can emit Markdown" to
"can reliably deliver a product-grade readable Chinese Markdown research
report", while preserving JSON, dossier, tool traces, and contract diagnostics
as audit sidecars.

The guiding product contract is:

```text
Readable report first.
Audit sidecar second.
Gate quality must reflect evidence reality, not only workflow completion.
```

## Task Classification

- Primary area: `research_workflow`
- Secondary areas:
  - `content_factory`
  - `source_layer`
  - `provider_layer`
  - `eval_policy_ops`
  - `memory_feedback`
  - `task_substrate`
  - `delivery_layer`
- Planning request type: PRD + PLAN creation, no production code implementation in this turn.
- Expected execution mode when implementation starts:
  - `local_direct` for narrow report formatter, test fixture, and status/doc updates
  - `light_subagent` for search/source quality and editor/gate slices
  - `remediation_gate` for failed live smoke or report-quality regression
  - `full_subagent` only if protected response contracts, database migrations, or broad workflow schema changes become necessary

## Current Baseline

Latest reviewed real smoke:

- `data/tmp/final_fix_smoke/case1/response.json`
- `data/tmp/final_fix_smoke/case1/summary.json`

Observed baseline:

- `status=succeeded`
- `decision=PASS`
- `report_preview.report_markdown` exists
- `report_markdown_chars=4763`
- `Audit Appendix` begins around character `869`
- `claim_count=5`
- `evidence_count=5`
- `source_count=5`
- `gate_obligation_gap_count=1`
- `obl_policy_primary.covered=false`
- `local_precision=0.6`
- `over_budget_context_packs=10`
- Editor2 found section role mismatch and low source diversity issues

Conclusion:

```text
The workflow can output Markdown, but it is not yet a product-grade readable
Deep Research report.
```

## Scope

In scope:

- enforce the PRD report output contract
- make `report_markdown` the primary user-facing artifact
- reduce audit-appendix dominance in the final Markdown
- strengthen source obligation and source-family matching before PASS
- make Editor2 / verifier P0 issues affect gate decisions
- improve Editor1 from claim-to-paragraph mapping into report-body writing
- make evidence / claim synthesis consume retrieval packs with clearer scope,
  limitations, and source diversity
- add focused unit tests and live smoke checks for report quality
- preserve graph_v1 opt-in status

Out of scope:

- replacing legacy `/deep-research/analyze` or `/research/analyze`
- browser automation, OCR, login-gated sources, or paid/private data
- broad UI redesign beyond surfacing report artifact and human review state
- direct securities investment advice
- extensive harness redesign not tied to report quality

## Protected Contracts

Do not silently change:

- legacy `/deep-research/analyze` response shape
- legacy `/research/analyze` response shape
- task/job status semantics
- existing public citation traceability expectations
- `human_review` pause/resume semantics
- report/audit boundary that JSON is audit sidecar, not final product
- product positioning as industry intelligence and research assistance

If a protected contract must change:

1. document the reason in this PLAN
2. document compatibility impact
3. add focused tests
4. run relevant API/provider checks

## Key Concepts

- `report_markdown`: final user-facing Chinese Markdown report. It must be readable without opening JSON.
- `audit sidecar`: response JSON, dossier, tool traces, context packs, and contract diagnostics. It supports review but must not dominate the main report body.
- `source obligation`: a planner/gate requirement that certain claim families require certain source families, such as policy claims requiring official policy sources.
- `source family match`: whether evidence supporting a claim comes from the source family required by that claim.
- `P0 review issue`: a review issue that blocks product-quality PASS, such as missing source obligation, policy claim supported only by disclosure, or audit appendix dominating report body.
- `report body ratio`: the portion of the Markdown before audit appendix or internal diagnostics. It measures whether the report is reader-first.

## Architecture Direction

Target flow:

```text
query
  -> dimension plan + source obligations
  -> diversified search strategy
  -> source filtering and URL review
  -> chunk + retrieval pack
  -> LLM-authored evidence bundle
  -> LLM-authored claim graph
  -> Editor1 report-body draft
  -> Editor2 / verifier product-quality review
  -> Chief Gate product-quality decision
  -> final Markdown artifact + audit sidecar
```

Design priorities:

1. Gate must not PASS when mandatory source obligations are uncovered.
2. Editor1 must produce a real report body before any audit appendix.
3. Evidence and claim synthesis must preserve source family, source IDs, chunk locators, scope, caveats, and limitations.
4. Editor2 and verifier must produce gate-consumable blocking issues.
5. Report validation must measure artifact quality, not only workflow success.

## Agent Execution Contract

When the user starts implementation:

- `invest_project_director`
  - refine this PLAN only if implementation discovers a real scope conflict
  - keep implementation focused on PRD P0 outcomes
- `invest_feature_programmer`
  - owns concrete code changes in research workflow, report composition, tests, and smoke scripts
  - must not rewrite legacy endpoints unless explicitly authorized
- `invest_agent_architecture_builder`
  - used only if schema or workflow boundary changes become necessary
- `invest_code_quality_checker`
  - runs compile, ruff, focused pytest
- `invest_functional_validator`
  - runs live smoke and checks Markdown quality against PRD metrics
- `invest_project_summarizer`
  - used only after done condition or major milestone completion

Default route:

```text
Start with local_direct or light_subagent.
Escalate only when protected contracts, schema migrations, or repeated smoke
failures require broader coordination.
```

## Milestones

### Phase 0: PRD And PLAN Freeze

Status: completed

Objective:

- Create a product PRD using `docs/prd_reference_for_codex.md`.
- Create this execution PLAN.
- Make this PLAN the primary active line in `.agent/STATUS.md`.

Acceptance criteria:

- PRD exists.
- PLAN exists.
- STATUS points to this PLAN.
- No production code changed.

Validation:

```powershell
Test-Path docs\prd\deep_research_readable_report_prd_v0_1.md
Test-Path .agent\PLANS\deep-research-readable-report-quality-v2.md
Select-String -Path .agent\STATUS.md -Pattern "deep-research-readable-report-quality-v2"
```

Progress:

- Completed in planning turn on 2026-06-17.

### Phase 1: Baseline Quality Harness

Status: pending

Objective:

- Add a report-quality inspection helper that reads `response.json` / `summary.json` and emits product-quality metrics.
- Make current baseline failures explicit and repeatable.

Required metrics:

- `report_markdown_chars`
- `business_body_chars`
- `audit_appendix_start_index`
- `business_body_ratio`
- required section coverage
- claim count
- evidence count
- source count
- source obligation gaps
- source family mismatch count
- P0 review issue count
- limitations truncation count
- over-budget context pack count

Acceptance criteria:

- Current `final_fix_smoke/case1` is classified as workflow-pass but product-fail.
- Report-quality helper can be run on future smoke outputs.
- Tests cover body ratio, obligation gap, limitation truncation, and required section detection.

Validation commands:

```powershell
python -m py_compile scripts\report_quality_inspect.py tests\test_report_quality_inspect.py
python -m ruff check scripts\report_quality_inspect.py tests\test_report_quality_inspect.py
pytest -q tests\test_report_quality_inspect.py
python scripts\report_quality_inspect.py --response data\tmp\final_fix_smoke\case1\response.json --summary data\tmp\final_fix_smoke\case1\summary.json
```

### Phase 2: Gate Quality Contract

Status: pending

Objective:

- Make Chief Gate consume product-quality blockers instead of relying only on workflow completion.
- Ensure obligation gaps, source-family mismatch, P0 review issues, and audit-body dominance prevent PASS.

Acceptance criteria:

- `gate_obligation_gap_count > 0` prevents PASS.
- policy claim supported only by company disclosure prevents PASS.
- P0 Editor2 / verifier issue prevents PASS or requires explicit human review.
- gate reason names the blocking class in Chinese-readable form.

Validation commands:

```powershell
python -m py_compile packages\research_harness\real_nodes.py tests\test_research_harness_graph.py
python -m ruff check packages\research_harness\real_nodes.py tests\test_research_harness_graph.py
pytest -q tests\test_research_harness_graph.py -k "chief_gate or obligation or source_family"
```

### Phase 3: Evidence And Claim Quality Upgrade

Status: pending

Objective:

- Improve LLM evidence / claim synthesis so it does not collapse into one source per claim when more context exists.
- Preserve source family, source IDs, chunk locators, limitations, and mismatch warnings.

Acceptance criteria:

- Key claims prefer multiple evidence/source links when available.
- Claim types include fact, interpretation, risk/uncertainty where applicable.
- Limitations are readable and not truncated.
- Deterministic fallback marks low-confidence output as degraded instead of pretending full support.

Validation commands:

```powershell
python -m py_compile packages\research_harness\tooling\llm_agents.py packages\research_harness\contracts.py packages\research_harness\real_nodes.py tests\test_research_harness_tooling.py tests\test_research_harness_graph.py
python -m ruff check packages\research_harness\tooling\llm_agents.py packages\research_harness\contracts.py packages\research_harness\real_nodes.py tests\test_research_harness_tooling.py tests\test_research_harness_graph.py
pytest -q tests\test_research_harness_tooling.py
pytest -q tests\test_research_harness_graph.py -k "build_evidence or build_claims"
```

### Phase 4: Editor1 Report Body Composer

Status: pending

Objective:

- Move Editor1 from short claim-paragraph mapping to a real report-body composer.
- Ensure final Markdown starts with reader-facing sections, not audit structures.

Acceptance criteria:

- Markdown includes title, executive summary, method/scope, dimension body sections, risk/uncertainty, conclusion, and source notes.
- Business body ratio is at least 70% for medium/full smoke cases.
- Audit appendix is absent from the main user artifact or placed after the report body.
- Editor1 prompt/context is auditable.

Validation commands:

```powershell
python -m py_compile packages\research_harness\tooling\llm_agents.py packages\research_harness\real_nodes.py tests\test_research_harness_tooling.py tests\test_research_harness_graph.py
python -m ruff check packages\research_harness\tooling\llm_agents.py packages\research_harness\real_nodes.py tests\test_research_harness_tooling.py tests\test_research_harness_graph.py
pytest -q tests\test_research_harness_tooling.py -k "editor1"
pytest -q tests\test_research_harness_graph.py -k "editor1 or finalize_report"
```

### Phase 5: Source And Search Acceptance Loop

Status: pending

Objective:

- Make search strategy and source URL review visible and enforceable.
- Continue integrating search caliber expansion where it improves source diversity and source obligation coverage.

Acceptance criteria:

- Source review artifact lists actual URLs, titles, source family, accepted/rejected reason.
- Wrong-location and weak-topic results are filtered before evidence synthesis.
- Same-domain / same-source overconcentration is visible.
- Hefei low-altitude smoke improves local precision beyond current `0.6` or triggers NEED_MORE_EVIDENCE.

Validation commands:

```powershell
python -m py_compile packages\research_harness\plan_semantic.py packages\research_harness\caliber_expander.py packages\research_harness\real_nodes.py tests\test_caliber_expander.py tests\test_research_harness_plan_semantic.py
python -m ruff check packages\research_harness\plan_semantic.py packages\research_harness\caliber_expander.py packages\research_harness\real_nodes.py tests\test_caliber_expander.py tests\test_research_harness_plan_semantic.py
pytest -q tests\test_caliber_expander.py tests\test_research_harness_plan_semantic.py
```

### Phase 6: Live Product Validation Matrix

Status: pending

Objective:

- Run live provider-backed smokes on representative cases and compare report quality, not only workflow status.

Required cases:

1. Hefei low-altitude economy policy + disclosure + project case.
2. Guangdong humanoid robot policy + project landing case.
3. China NEV policy support chain case.
4. Shenmu coal / coal chemical expansion space case.

Acceptance criteria:

- At least 3 of 4 cases meet PRD P0 quality gates.
- Any non-pass case explains whether failure is source scarcity, provider failure, gate blocker, or report-writing failure.
- Final artifacts include readable Markdown and audit sidecar.
- Before/after examples are recorded in PLAN progress.

Validation command pattern:

```powershell
python scripts\graph_provider_backed_smoke.py --query "<case query>" --max-rounds 2 --max-loop-count 1 --output-dir data\tmp\<case_output> --env-file .env --reset
python scripts\report_quality_inspect.py --response data\tmp\<case_output>\response.json --summary data\tmp\<case_output>\summary.json
```

### Phase 7: Documentation, Handoff, And Promotion Decision

Status: pending

Objective:

- Update PRD/PLAN/STATUS with final results.
- Decide whether graph_v1 remains opt-in, advances to broader beta, or needs another quality cycle.

Acceptance criteria:

- PLAN progress includes validation results and before/after examples.
- STATUS reflects current state and next action.
- Remaining risks are explicit.
- No undocumented protected contract changes exist.

## Continue Rule

After each phase, continue automatically to the next phase when:

- acceptance criteria are met
- required validation passes
- no protected-contract change is required without authorization
- no external credential, database, provider, or network blocker exists
- no live smoke shows a regression that would make the next phase unsafe

Do not stop after a phase just to ask whether to continue.

## Stop Conditions

Stop only when:

1. a protected contract change is required but not authorized in this PLAN
2. required credentials or external services are missing
3. validation repeatedly fails and the fix path is unclear
4. live report quality regresses materially
5. user explicitly asks to pause or only review
6. final done condition is reached

## Done Condition

This PLAN is complete when:

- PRD P0 requirements are implemented or explicitly deferred with user approval
- live validation matrix has been run
- at least 3 of 4 required live cases meet product-quality gates
- `report_markdown` is the dominant final artifact
- PASS is impossible when mandatory evidence obligations are uncovered
- Editor1 produces a reader-first report body
- Editor2 / verifier P0 issues influence gate decisions
- STATUS and PLAN are updated with results, risks, and next action

## Validation Loop

Use this loop for implementation:

1. Make one focused change.
2. Run compile + ruff + focused pytest.
3. Run or reuse a live smoke artifact.
4. Run report-quality inspection.
5. Record result in this PLAN.
6. Continue if metrics improved or blocker is understood.

## Risks And Rollback

| Risk | Impact | Mitigation | Rollback |
|---|---|---|---|
| Gate becomes too strict | Many reports stop at HUMAN_REVIEW | distinguish P0 blockers from soft warnings | lower only non-critical thresholds |
| Editor1 generates longer but weaker prose | Better length, worse accuracy | evidence-grounded prompt + verifier checks | restore previous prompt and keep gate changes |
| Source quality remains poor | Report cannot pass | expose NEED_MORE_EVIDENCE, improve search/source filters | do not force PASS |
| real_nodes recovery proxy limits maintainability | hard to make clean changes | reconstruct source when needed before broad changes | keep changes narrow and tested |
| Live provider instability | smoke fails intermittently | record provider diagnostics, retry once | validate with deterministic fixtures |

## Progress

### 2026-06-17 — Status Corrected After Review

This PLAN should be read as a partially successful implementation cycle, not a
completed productization cycle.

What did improve:

- `scripts/report_quality_inspect.py` exists and can classify workflow success
  separately from product-quality success.
- `tests/test_report_quality_inspect.py` passes with 11 tests.
- Phase 6 live smoke artifacts exist under `data/tmp/phase6_smoke/`.
- Generated Markdown bodies are longer and more structured than the original
  `final_fix_smoke/case1` baseline.
- Some evidence and report fields now carry richer quality signals.

What did not pass:

- All four Phase 6 live cases still classify as `workflow_pass_product_fail`
  under the report quality inspector.
- `case1_hefei` still has `decision=PASS` while
  `gate_obligation_gap_count=1`, so gate quality is not closed.
- `business_body_ratio` remains below the original 70% target and below the
  lowered 35% target in some cases.
- P0 review issues, limitations truncation, and over-budget context packs remain
  unresolved in live artifacts.
- The PLAN's prior completed wording overstated the actual product state.

## Corrected Live Validation Snapshot

Commands rerun during review:

```powershell
pytest -q tests\test_report_quality_inspect.py
python scripts\report_quality_inspect.py --response data\tmp\phase6_smoke\case1_hefei\response.json --summary data\tmp\phase6_smoke\case1_hefei\summary.json
python scripts\report_quality_inspect.py --response data\tmp\phase6_smoke\case2_robot\response.json --summary data\tmp\phase6_smoke\case2_robot\summary.json
python scripts\report_quality_inspect.py --response data\tmp\phase6_smoke\case3_nev\response.json --summary data\tmp\phase6_smoke\case3_nev\summary.json
python scripts\report_quality_inspect.py --response data\tmp\phase6_smoke\case4_coal\response.json --summary data\tmp\phase6_smoke\case4_coal\summary.json
```

Results:

- inspector tests: `11 passed`
- `case1_hefei`: `workflow_pass_product_fail`, `3/9` checks passed,
  `gate_obligation_gap_count=1`, `decision=PASS`
- `case2_robot`: `workflow_pass_product_fail`, `6/9` checks passed
- `case3_nev`: `workflow_pass_product_fail`, `8/9` checks passed
- `case4_coal`: `workflow_pass_product_fail`, `7/9` checks passed

## Corrected Before / After Comparison

| Metric | Before baseline | Phase 6 live result | Correct interpretation |
|---|---:|---:|---|
| business_body_chars | 867 | avg about 2562 | improved |
| business_body_ratio | 0.182 | avg about 0.367 | improved but below product target |
| required_sections | 3/6 | avg about 5.5/6 | improved |
| gate blind PASS | yes | still present in case1 | not fixed |
| limitations truncation | present | still present in multiple cases | not fixed |
| over-budget packs | 10 | 10-16 | not fixed |
| quality classification | workflow_pass_product_fail | workflow_pass_product_fail for all 4 | not complete |

## Corrected Promotion Recommendation

**Do not promote. Keep `graph_v1` opt-in and continue remediation.**

The follow-up active PLAN is:

- `.agent/PLANS/deep-research-readable-report-remediation-v1.md`

## Next Action

Continue in the remediation PLAN with Phase 1:

1. fix the inspector's claim/evidence/source extraction paths
2. make `gate_obligation_gap_count > 0` impossible to PASS
3. separate the reader-facing report artifact from audit appendix
4. re-run the four live smoke cases and require at least 3/4 product pass
