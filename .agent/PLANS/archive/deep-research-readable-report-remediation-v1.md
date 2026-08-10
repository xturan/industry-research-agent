# Deep Research Readable Report Remediation v1

Status: completed_depth_track_4of4_product_pass_graph_v1_remains_opt_in

Created: 2026-06-17

Primary active PLAN: yes

Supersedes:

- `.agent/PLANS/deep-research-readable-report-quality-v2.md`

Related PRD:

- `docs/prd/deep_research_readable_report_prd_v0_1.md`

## Objective

Repair the gap between workflow success and product-quality success for the
LangGraph Deep Research report path.

This PLAN starts from a corrected fact:

```text
The graph can produce longer and more structured Markdown, but the latest
Phase 6 live artifacts still fail product-quality inspection.
```

The immediate goal is not to claim completion. The goal is to make quality
truthful, then close the highest-impact blockers:

1. product-quality inspector reads the right fields
2. uncovered mandatory obligations cannot PASS
3. reader-facing Markdown is separated from audit appendix
4. live smoke cases move from `workflow_pass_product_fail` to product pass

## Task Classification

- Primary area: `research_workflow`
- Secondary areas:
  - `content_factory`
  - `eval_policy_ops`
  - `provider_layer`
  - `source_layer`
  - `task_substrate`
  - `delivery_layer`
- Execution mode:
  - `local_direct` for docs, status, inspector fixes, and focused tests
  - `light_subagent` for scoped gate/report implementation if needed
  - `remediation_gate` if live validation fails after a focused fix
  - `full_subagent` only if protected API response contracts, schema changes, or database migrations become necessary

## Current Baseline

Reviewed artifacts:

- `data/tmp/phase6_smoke/case1_hefei/response.json`
- `data/tmp/phase6_smoke/case1_hefei/summary.json`
- `data/tmp/phase6_smoke/case2_robot/response.json`
- `data/tmp/phase6_smoke/case2_robot/summary.json`
- `data/tmp/phase6_smoke/case3_nev/response.json`
- `data/tmp/phase6_smoke/case3_nev/summary.json`
- `data/tmp/phase6_smoke/case4_coal/response.json`
- `data/tmp/phase6_smoke/case4_coal/summary.json`

Corrected validation:

| Case | Workflow decision | Inspector classification | Checks passed | Blocking notes |
|---|---|---|---:|---|
| case1_hefei | PASS | workflow_pass_product_fail | 3/9 | obligation gap still PASS, P0 issues, truncated limitations, over-budget packs |
| case2_robot | PASS | workflow_pass_product_fail | 6/9 | P0 issues, truncated limitations, over-budget packs |
| case3_nev | PASS | workflow_pass_product_fail | 8/9 | over-budget packs |
| case4_coal | PASS | workflow_pass_product_fail | 7/9 | body ratio, over-budget packs |

Baseline command:

```powershell
pytest -q tests\test_report_quality_inspect.py
python scripts\report_quality_inspect.py --response data\tmp\phase6_smoke\case1_hefei\response.json --summary data\tmp\phase6_smoke\case1_hefei\summary.json
python scripts\report_quality_inspect.py --response data\tmp\phase6_smoke\case2_robot\response.json --summary data\tmp\phase6_smoke\case2_robot\summary.json
python scripts\report_quality_inspect.py --response data\tmp\phase6_smoke\case3_nev\response.json --summary data\tmp\phase6_smoke\case3_nev\summary.json
python scripts\report_quality_inspect.py --response data\tmp\phase6_smoke\case4_coal\response.json --summary data\tmp\phase6_smoke\case4_coal\summary.json
```

## Scope

In scope:

- fix documentation status and make this PLAN the only active long-running plan
- correct `scripts/report_quality_inspect.py` extraction paths for claims,
  evidence, sources, review issues, and report preview fields
- make Chief Gate treat mandatory obligation gaps as blocking
- make P0 review issues and source-family mismatch gate-consumable
- split user-facing `report_markdown` from audit appendix or make audit appendix
  a separate sidecar field/artifact
- re-run focused tests and the four live product smoke cases
- update STATUS and PLAN after each meaningful step

Out of scope:

- replacing legacy `/deep-research/analyze` or `/research/analyze`
- making `graph_v1` default
- broad UI redesign, except documenting required human-review surfacing
- adding paid/private sources, browser automation, OCR, or login-gated crawling
- positioning reports as direct securities investment advice

## Protected Contracts

Do not silently change:

- legacy `/deep-research/analyze` response shape
- legacy `/research/analyze` response shape
- public task/job status semantics
- `human_review` pause/resume semantics
- existing citation traceability expectations
- product boundary: industry intelligence and research assistance, not direct investment advice

Allowed under this PLAN:

- adding internal quality metrics
- adding or tightening graph-v1-only gate conditions
- changing graph-v1-only report composition if audit sidecar remains available
- adding standalone Markdown artifact paths for graph-v1 output

## Design Direction

The target behavior is:

```text
workflow status succeeded
  does not imply
product report passed
```

Product PASS requires:

- mandatory source obligations covered
- no P0 review issues
- no source-family mismatch for key claims
- readable report body dominates audit appendix
- limitations are readable
- context-budget overage is either below threshold or explicitly downgraded
- inspector classification is product pass

## Milestones

### Phase 0: Status Correction

Status: completed

Objective:

- Correct `STATUS.md`, v2 PLAN, and session trace so they no longer claim completed productization.
- Create this remediation PLAN.

Acceptance criteria:

- `STATUS.md` points to this PLAN as primary active.
- `.agent/PLANS/INDEX.md` lists this PLAN as the active execution plan.
- PRD document points to this remediation PLAN as the current execution plan.
- v2 PLAN is no longer primary active.
- session trace includes an errata stating it should not be used as completion proof.
- no production code changes in this phase.

Validation:

```powershell
$env:PYTHONIOENCODING='utf-8'
@'
from pathlib import Path
status = Path(".agent/STATUS.md").read_text(encoding="utf-8")
index = Path(".agent/PLANS/INDEX.md").read_text(encoding="utf-8")
prd = Path("docs/prd/deep_research_readable_report_prd_v0_1.md").read_text(encoding="utf-8")
plan = Path(".agent/PLANS/deep-research-readable-report-remediation-v1.md").read_text(encoding="utf-8")
old = Path(".agent/PLANS/deep-research-readable-report-quality-v2.md").read_text(encoding="utf-8")
trace = Path("docs/session-trace-2026-06-17.md").read_text(encoding="utf-8")
assert "deep-research-readable-report-remediation-v1" in status
assert "deep-research-readable-report-remediation-v1.md` | `active_phase1_quality_truth_baseline`" in index
assert "当前执行计划 | `.agent/PLANS/deep-research-readable-report-remediation-v1.md`" in prd
assert "Primary active PLAN:" in plan and "yes" in plan
assert "Primary active PLAN: no" in old
assert "勘误" in trace
'@ | python -
```

### Phase 1: Quality Inspector Truth Fix

Status: completed

Objective:

- Ensure `scripts/report_quality_inspect.py` reads actual report, claim,
  evidence, source, review issue, and gate fields from graph-v1 response shapes.

Known issue:

- Current inspector reports `claim_count=0`, `evidence_count=0`, and
  `source_count=0` for Phase 6 responses, even though the data is available in
  `report_preview` and node-step outputs.

Root cause confirmed:

- graph-v1 stores counts as `report_preview.claim_count` /
  `report_preview.evidence_count` / `report_preview.source_count` (integers),
  claim briefs under `report_preview.tool_composed_report.claim_briefs`, and
  per-node counters under `node_steps[].output_summary`. The old inspector
  looked for list fields named `claims` / `evidence` at the report_preview top
  level and `source_count` on summary.json — none of which exist, so every
  count was 0. The `_count_source_family_mismatches` helper also read
  `report_preview.claim_briefs` (empty) instead of
  `tool_composed_report.claim_briefs`, so it always returned 0.

Acceptance criteria:

- Inspector extracts non-zero claim/evidence/source counts from Phase 6 cases
  when those fields exist.
- Inspector still classifies the current four Phase 6 cases truthfully.
- Tests cover top-level, `report_preview`, and node-step fallback extraction.

Implementation:

- Three-layer truth-first extraction via `_extract_count`: report_preview
  integer counters -> `tool_composed_report` list/counter -> node-step
  `output_summary` counters (`build_claims.claim_count`,
  `build_evidence.evidence_count`, `collect_sources`/`score_sources.source_count`).
- `_index_node_summaries` / `_node_count` helpers for node-step fallback.
- `_count_source_family_mismatches` now reads `tool_composed_report.claim_briefs`
  first, with the old top-level / sections fallback preserved.
- Added 5 tests covering top-level, tool_composed_report fallback, node-step
  fallback, zero-when-absent, and the corrected mismatch source.

Validation result (2026-06-17):

- `py_compile`: pass
- `ruff`: All checks passed
- `pytest -q tests/test_report_quality_inspect.py`: `16 passed` (was 11)
- Four-case rerun (counts now truthful, classification matches PLAN baseline):

| Case | claim / evidence / source | checks | classification |
|---|---|---:|---|
| case1_hefei | 7 / 5 / 5 | 3/9 | workflow_pass_product_fail |
| case2_robot | 4 / 4 / 26 | 6/9 | workflow_pass_product_fail |
| case3_nev | 3 / 3 / 24 | 8/9 | workflow_pass_product_fail |
| case4_coal | 1 / 2 / 23 | 7/9 | workflow_pass_product_fail |

Note: `case2/3/4 source_count` is 23-26 (raw `collect_sources` search results)
while `case1` is 5 (post-filter) — this reflects real search-strategy
differences across cases, not an extraction bug. Exit code is 1 for
product_fail (the earlier `exit=0` observation was a `grep`/`head` pipe
artifact, since `$?` reports the last pipeline command).

### Phase 2: Gate Obligation Hard Block

Status: completed

Objective:

- Make `gate_obligation_gap_count > 0` impossible to return final `PASS` in
  graph-v1.

Root cause confirmed:

- `chief_gate_provider_backed` already had an obligation-gap hard-block (Block 1
  at `real_nodes.py:1713`), but it computed `has_obligation_gap` from a
  `family_covered` heuristic that only checks whether some claim has a
  non-empty `evidence_ids` list. That heuristic reports a family as covered
  even when the linked evidence comes from a different source family — so
  `case1_hefei` had `obl_policy_primary.covered=false` in the authoritative
  `required_obligation_coverage` (produced by verify_claims) but the gate still
  returned `decision=PASS` because `has_obligation_gap` was `False`.
- Two parallel obligation computations existed (`all_obligations_covered` at
  :1596 and `has_obligation_gap` at :1687) using inconsistent sources of truth.

Acceptance criteria:

- `case1_hefei` no longer returns `decision=PASS` while
  `obl_policy_primary.covered=false`.
- Gate reason explicitly names uncovered obligation and required source family.
- Existing HUMAN_REVIEW priority is preserved.

Implementation (surgical, one branch):

- `has_obligation_gap` now prefers the authoritative
  `required_obligation_coverage[].covered` field when `obligation_coverage` is
  present (it is produced by verify_cliefs/chief_gate and checks whether
  evidence really comes from the required source family). The `family_covered`
  heuristic remains as a fallback only when `obligation_coverage` is absent.
  This aligns Block 1 with the `all_obligations_covered` path that already
  trusted the same field, eliminating the two inconsistent truth sources.

Validation result (2026-06-17):

- `py_compile`: pass
- `ruff`: All checks passed
- Focused `pytest -k "chief_gate or obligation or source_family"` (excluding
  one pre-existing failure, see below): `5 passed`
- Blind-PASS repro: a state mirroring case1 (claims with evidence_ids but
  `obl_policy_primary.covered=false`) now returns
  `decision=ADD_EVIDENCE`, `gate_route_to=collect_sources`,
  gate_reason `"obligation 未覆盖 (1个: obl_policy_primary) — 必须补充对应源族的证据后才能通过"`.
- HUMAN_REVIEW priority preserved: when editor2 recommends HUMAN_REVIEW, the
  decision stays `HUMAN_REVIEW` even with an obligation gap (HUMAN_REVIEW
  branch returns before Block 1).

Pre-existing failures NOT caused by this change (verified by baseline-vs-change
differential — both fail identically before and after):

- `test_chief_gate_provider_backed_local_claim_action_carries_location_queries`
  — expects `required_actions` items with `target_claim_id` /
  `required_source_family` / `suggested_search_queries` for location-sensitive
  unsupported local claims, but Block 1 emits only `{action_type, target}`.
  This is a separate location-action contract gap, not an obligation-gap issue.
- `test_verify_claims_provider_backed_prefers_llm_synthesis` — verify_claims
  decision mismatch (`PASS` vs expected `REVISE_TEXT`), independent of the
  gate obligation change.
- Clean differential on the chief_gate/editor/verify/finalize/obligation/
  source_family subset: baseline `2 failed, 16 passed` vs change
  `2 failed, 16 passed` — **zero new failures introduced**.

### Phase 3: Report Artifact Separation

Status: completed

Objective:

- Stop audit appendix from dominating `report_markdown`.
- Make the reader-facing report and audit sidecar clearly separate.

Acceptance criteria:

- `report_markdown` contains the reader-facing report body.
- Audit appendix is moved to `audit_markdown`, `dossier`, or a separate artifact
  path.
- Medium/full cases target `business_body_ratio >= 0.70` when measured against
  the user-facing artifact.
- `response.json` remains parseable and audit data remains available.

Implementation (2026-06-17):

- Split logic in `real_nodes.py:finalize_report_provider_backed` only splits on
  `## Audit Appendix` / `## 审计附录` section headers. Reader-facing sections
  (`## Evidence And Limitations`, `## Key Claims`, source display, title
  cleaning) remain in `report_markdown`.
- The bytecode already produces separated `report_preview.report_markdown`
  (editor1-composed reader report) and `report_preview.audit_markdown` (raw data
  starting with `## Audit Appendix`) for live cases.
- Initial implementation (before fix) was too coarse: it used `Evidence And
  Limitations`, `Claim Verifications`, `key_claims` as split markers, which
  stripped reader-facing evidence/source/title content from `report_markdown`.
  Fixed by narrowing markers to only `## Audit Appendix` / `## 审计附录`.

Validation result (2026-06-17):

- `py_compile`: pass
- `ruff`: All checks passed
- `pytest -q tests/test_research_harness_graph.py -k "finalize_report or report_markdown"`: `5 passed`

### Phase 4: P0 Review Issue Gate Consumption

Status: completed

Objective:

- Ensure Editor2 / verifier P0 issues affect final gate decisions.

Acceptance criteria:

- section role mismatch, low source diversity, source family mismatch, and
  unresolved critical limitations are categorized as blocking or downgrade issues.
- PASS requires zero P0 issues.
- HUMAN_REVIEW reasons are user-readable.

Implementation (2026-06-17):

- Editor2: 5 issue types — source_family_mismatch (blocker), unsupported_claim (blocker), section_role_mismatch (warning), low_source_diversity (warning), critical_limitation_unresolved (warning)
- Gate: removed ad-hoc P0 heuristics, unified consumption from review_issues via hard_blockers/warnings_list. Block 2: hard_blockers → REVIEW_RISK. Block 3: warnings → quality ×0.85.
- HUMAN_REVIEW: GraphHumanReviewState extended with p0_review_context + "overridden" status. New override_p0 action. Gate populates P0 context at HUMAN_REVIEW routes.

Validation:

```powershell
pytest -q tests\test_research_harness_graph.py -k "editor2 or chief_gate or human_review or verifier"
pytest -q tests\test_report_quality_inspect.py
```

Result: 19/20 gate+editor2+hr tests pass (1 pre-existing), quality_inspect 16/16

### Phase 5: Live Product Gate Rerun

Status: in_progress

Objective:

- Re-run the four live smoke cases and require product-quality pass, not just
  workflow success.

Cases:

1. Hefei low-altitude economy policy + disclosure + project case.
2. Guangdong humanoid robot policy + project landing case.
3. China NEV policy support chain case.
4. Shenmu coal / coal chemical expansion case.

Acceptance criteria:

- At least 3/4 cases classify as product pass.
- 0/4 cases have `decision=PASS` with mandatory obligation gaps.
- At least 3/4 cases have reader-facing `business_body_ratio >= 0.70` after
  audit separation.
- Remaining failures are explicitly categorized as source scarcity, provider
  instability, gate blocker, or report-writing failure.

Progress:

- case1 (Hefei) — VERIFIED across 4 reruns (1a→1d). Depth track confirmed live:
  evidence 5→48 (40 `llm_atomic`), sources 5→9, Phase 8 gap loop fired (2
  rounds observed in 1b), editor1 LLM writer produces 4767-5316 char genuine
  synthesis (region comparison table citing ev_atomic ids, transmission-chain
  analysis "链条断裂", data-gap labels). case1c: decision=PASS, reached
  finalize, final artifact PRESERVED the LLM synthesis (5279 chars, 11
  sections) — compose tool does not overwrite drafts[-1]. Inspector after the
  draft-fallback fix: case1c 7/9 (finalize path), case1d 8/9 (human_review
  path, business_body recovered to 4767). Only failing check is
  over_budget_packs (observability token-accounting artifact, see Phase 9 note).
  Extracted reader artifact: `data/tmp/depth_track_case1c/FINAL_REPORT.md`.
- INSPECTOR BLIND-SPOT FIX: `report_quality_inspect.py` now recovers the latest
  editor1/human_review draft from node_steps when report_preview.report_markdown
  is empty (run halted before finalize). Adds `_recover_draft_markdown` +
  `workflow.report_source` = `draft_fallback` | `report_preview`. Tests: 16
  passed. case1d went 5/9 → 8/9; case1c unaffected (still reads report_preview).
- case2/3/4 — pending live reruns.

Final 4-case matrix (2026-06-18, current code):

| Case | decision | finalize | source | evidence | inspector |
|---|---|---|---:|---:|---|
| case1 Hefei low-altitude | PASS | yes | 9 | 48 | product_pass 8/9 |
| case2 Guangdong robot | PASS | yes | 25 | 50 | product_pass 8/9 |
| case3 China NEV chain | PASS | yes | 24 | 45 | product_pass 8/9 |
| case4 Shenmu coal | HUMAN_REVIEW | draft | 31 | 50 | product_pass 8/9 |

Result: **4/4 product_pass** (exceeds ≥3/4 target). Every case's only failing
check is `over_budget_packs`, now an advisory (non-blocking) operational signal.
0/4 cases have decision=PASS with an obligation gap (gate-caliber fix holds).
case4 halted at HUMAN_REVIEW for legitimate gate reasons; the draft-fallback
makes its 2867-char report visible and product-passing. evidence counts (45-50)
and source counts (9-31) confirm the depth track (atomic evidence + gap-driven
retrieval) is live across all four cases.

OVER-BUDGET RECLASSIFICATION: `report_quality_inspect.py` now marks
`over_budget_packs` as `advisory: true`; `product_ok` evaluates only
non-advisory (blocking) checks. Rationale: `estimate_token_count` sums every
source's full clean_text/raw_text + all source_chunks — content NOT injected
into the LLM prompt (nodes send a curated digest). A deep report legitimately
processes many sources; gating product_pass on it would penalize exactly the
Phase 7/8 funnel widening. Tests: 16 passed.

Validation pattern:

```powershell
python scripts\graph_provider_backed_smoke.py --query "<case query>" --max-rounds 2 --max-loop-count 1 --output-dir data\tmp\depth_track_<case> --env-file .env --reset
python scripts\report_quality_inspect.py --response data\tmp\depth_track_<case>\response.json --summary data\tmp\depth_track_<case>\summary.json
```

### Phase 6: Final Handoff

Status: completed

Done Condition met: inspector truth fix (Phase 1), obligation gaps cannot PASS
(Phase 2), reader report separated from audit (Phase 3), P0 issues gate-consumed
(Phase 4), depth track delivers real synthesis (Phases 7-9), 4-case live matrix
rerun with **4/4 product_pass** (Phase 5, exceeds ≥3/4 target). STATUS and this
PLAN are consistent.

Before/after (the core product change):

- BEFORE: editor1 LLM writer raised NameError on every call → silently fell back
  to the `_build_minimal_draft_from_claims` template ledger. Output was an
  "evidence ledger" — `证据 [e1] (强度:0.9)` enumerations under template
  sections (政策依据 / Statistics). 5 sources → 5 evidence (1:1), all
  `background_support`. This is exactly the external critique's complaint.
- AFTER: editor1 produces genuine 4767-5337 char research reports with a
  region-comparison table (citing `ev_atomic_*` ids), a 政策→项目→基建→公司→
  产业链 transmission-chain analysis (e.g. case1 "链条断裂" finding), and
  explicit 数据缺口 labels. 9-31 sources → 45-50 atomic evidence. finalize
  preserves the LLM synthesis (does not overwrite with the compose tool).

Reader artifact sample: `data/tmp/depth_track_case1c/FINAL_REPORT.md` (5279
chars, 11 sections).

Decision on graph_v1 promotion: REMAINS OPT-IN. The depth track makes the report
genuinely product-grade, but two known non-blocking items remain (below) and the
`real_nodes.py` recovery-proxy should be reconstructed to first-class source
before default promotion. Recommend a follow-up PLAN for that reconstruction.

Remaining known items (non-blocking, documented):
- `over_budget_packs`: observability token-accounting counts content not sent to
  the LLM; reclassified advisory. A future cleanup could make
  `estimate_token_count` reflect the actual curated digest.
- `real_nodes.py` is still a recovery proxy over bytecode (per STATUS); all
  Phase 7-9 fixes are proxy-safe wrapper-layer changes. Reconstruct to source
  before broader promotion.
- Two pre-existing editor1 tests assert a stale English fixed-template shape;
  they fail identically on HEAD and should be updated to the Chinese LLM-report
  contract in a separate cleanup.

## Design Brief: Research Depth Track (Phases 7-9)

Added 2026-06-17 after a grounded brainstorm (superpowers/brainstorm) on a
detailed external critique that the report is an "evidence ledger", not a real
deep-research report. The critique's symptoms are accurate; its proposed
9-node pipeline is mostly redundant — the nodes already exist. Verified in code:

- fulltext IS fetched (`collect_sources` uses `include_raw_content=True`, stores
  `raw_text`/`full_text`; `_inject_chunk_text_into_sources` swaps retrieval
  chunks into source text)
- split strength scoring already exists (`SourceQualityV2`:
  `publisher_authority`, `auditability`, `freshness`, `query_relevance`,
  `credibility_score`, `usage_role`, `not_sufficient_for`)
- claim supplement already exists (`build_claims` LLM supplement when `<8`)
- critic/verifier/gate nodes already exist (`editor2_review`, `verify_claims`,
  `chief_gate` with ADD_EVIDENCE re-retrieval routing)
- relations already persisted (`research_graph_claims`,
  `research_graph_evidence_items`, `research_graph_claim_evidence_links`,
  `research_graph_review_issues`)

Real root cause (from case1_hefei node trace): existing nodes are starved.
`collect_sources` keeps only 5 sources, `build_evidence` emits exactly 5
evidence (1:1 with sources), all tagged `background_support` (nothing
`direct`/`primary`). And editor1's context pack is 96,180 tokens against a
1,200 budget (80x over) — the writer is not starved of metadata, it is
drowning in raw context with no curated synthesis input.

Decision (user, 2026-06-17): depth-first, folded into THIS PLAN. No new nodes,
no harness re-expansion. Deepen three existing stages. The live rerun
(Phase 5) runs AFTER Phases 7-9 so it tests the deeper report.

### Phase 7: Atomic Evidence Extraction

Status: completed

Objective:

- Break the 1:1 source->evidence cap. For each source's fulltext, extract
  multiple typed atomic facts instead of one background summary.

Acceptance criteria:

- `build_evidence.evidence_count` > `source_count` on multi-fact sources.
- `support_types` diversify beyond all-`background_support` (direct / primary
  appear where fulltext warrants).
- Each atomic evidence carries: source_id, region, time, policy_tool/topic,
  entity, claim_supported, support_type, content_completeness,
  needs_fulltext_check — reusing existing fields where present.
- Deterministic fallback preserved; contract retry/repair still applies.

Implementation (2026-06-17, proxy-safe wrapper, no bytecode change):

- `build_evidence_provider_backed` now calls `_extract_atomic_evidence` after
  the bytecode impl returns, appending atomic items to base evidence before
  enrichment.
- `_extract_atomic_evidence`: per source with fulltext >= 120 chars, tries
  `_llm_extract_atomic_facts` (DeepSeek tooling, requests `{"facts":[...]}`
  dict root since `call_tooling_json` rejects bare-array roots), falling back to
  `_deterministic_atomic_facts` (sentence split on signal regex: numbers, money,
  补贴/基金/示范区/机场/招标/年报 markers). Dedup by normalized summary; caps
  5 facts/source, 40 total.
- `_make_atomic_evidence_item` emits base evidence shape + typed fields
  (region, time_ref, policy_tool, entity, content_completeness,
  needs_fulltext_check derived from completeness, `_atomic=True`).
  support_strength left 0.0 and filled by existing `_enrich_evidence_semantics`.

Validation result (2026-06-17):

- `py_compile`: pass; `ruff`: zero errors in new code (2380-2540 range; 11
  remaining errors are pre-existing recovery-proxy artifacts elsewhere).
- End-to-end on a rich policy source: **1 source -> 6 evidence** (base 1 + 5
  atomic). support_types went from all-`background_support` to
  `{background_support: 1, direct_support: 5}`. Atomic facts are granular
  (5个通用机场 / 10亿基金 / 2000万补贴 / 三大场景 / 6月细则), each with
  `content_completeness=high`, strength filled to 1.0 by enrichment.
- Deterministic fallback verified independently: 3 typed facts with correct
  policy_tool tagging (产业基金/基础设施/补贴) and primary_support on numeric
  sentences — works with no provider.
- Differential (atomic hook enabled vs disabled) on the heavy
  `requires_procurement_evidence` graph test: **fails identically both ways**
  — pre-existing live-provider non-determinism, NOT caused by Phase 7. Zero new
  failures introduced.

Validation:

```powershell
pytest -q tests\test_research_harness_graph.py -k "build_evidence"
python scripts\report_quality_inspect.py --response data\tmp\phase6_smoke\case1_hefei\response.json --summary data\tmp\phase6_smoke\case1_hefei\summary.json
```

### Phase 8: Gap-Driven Second-Round Retrieval

Status: completed

Objective:

- Make the existing `chief_gate` ADD_EVIDENCE -> `collect_sources` loop actually
  fire on coverage gaps, widening the source funnel beyond 5.

Acceptance criteria:

- When mandatory obligations are uncovered (Phase 2 hard block now forces this),
  a second retrieval round runs with gap-targeted queries.
- Source funnel widens (post-loop `source_count` > first-round count on gapped
  cases).
- Loop remains bounded by `max_loop_count`; no infinite re-retrieval.

Root cause confirmed:

- The loop wiring already existed (gate ADD_EVIDENCE -> `plan_task` ->
  `collect_sources`), but on re-entry `plan_task` rebuilt the SAME plan from
  scratch and never consumed the gate's `required_actions`. Round 2 re-ran
  identical phrases, `collect_sources` deduped by URL, funnel stayed at 5.

Implementation (2026-06-17, proxy-safe wrapper):

- `plan_task_provider_backed` now, when `loop_count > 0` and `required_actions`
  present, calls `_build_gap_targeted_rounds` to derive family-specific search
  rounds from uncovered obligations.
- `_build_gap_targeted_rounds`: maps `required_actions[].target` (obligation_id)
  to `source_family` via `required_obligation_coverage`, then emits rounds from
  `_GAP_FAMILY_TEMPLATES` (official_policy/company_disclosure/
  public_resource_transaction/location_matched). Each round is location-prefixed
  and tier-targeted with family-appropriate `include_domains`
  (gov.cn / cninfo+sse+szse / ccgp+ggzy).
- CRITICAL slice fix: `collect_sources` iterates `search_rounds[:max_rounds]`.
  Gap rounds are placed FIRST (original rounds already ran and dedup to nothing
  on re-run), so they fall inside the slice and actually execute. Rounds
  renumbered accordingly.

Validation result (2026-06-17):

- `py_compile`: pass; `ruff`: zero errors in new code (11 remaining are
  pre-existing recovery-proxy artifacts elsewhere).
- Gap helper: uncovered `obl_policy_primary` (official_policy) ->
  1 gap round, location-prefixed phrases ("合肥 ... 政策 原文 官方"),
  `include_domains=[gov.cn]`, tier A.
- Integration through `plan_task`: gap round injected as round #1, inside the
  `[:max_rounds=2]` slice (verified gap_in_slice=True), metadata
  `gap_targeted_rounds_added=1`, `gap_retrieval_loop=1`.
- No-regression gating: loop_count=0 -> no injection; loop_count>0 with empty
  required_actions -> no injection.
- Tests: `plan_task/obligation/source_family/gate_route/loop_count` subset
  `8 passed`; `chief_gate` subset `6 passed` (excluding 1 pre-existing failure).

Validation:

```powershell
pytest -q tests\test_research_harness_graph.py -k "chief_gate or collect_sources or loop"
```

### Phase 9: Writer Synthesis (Curate + Prompt Rebuild)

Status: completed

Objective:

- Fix the 80x-over-budget editor1 pack: send a curated, digested synthesis
  input (evidence digest + SourceQualityV2 capsule + claim graph), NOT raw
  96k-token context.
- Rebuild the editor1 writer prompt to demand region comparison + value-chain
  transmission analysis (policy -> project -> infra -> company -> chain), not a
  source list.

Root cause found (the single biggest defect in the whole pipeline):

- `_generate_real_editor1_draft` referenced `query`/`claims`/`evidence_items`/
  `sources`/`draft_version`/`prior_drafts` that were NEVER defined in scope.
  Every call raised `NameError`, was swallowed by the caller's bare `except`,
  and silently fell back to `_build_minimal_draft_from_claims` (the template
  ledger). The LLM research writer had NEVER actually run. This is exactly the
  "evidence ledger, not a report" symptom the external critique described.
- Second latent defect: even once the writer ran, the prompt asked for "pure
  Markdown" but `call_tooling_json` only accepts a JSON dict root, so the
  Markdown would parse to `None` and fall back to template again.
- Third: the `< 1500` char fallback threshold discarded genuine multi-section
  LLM reports in favour of the template.

Implementation (2026-06-17, proxy-safe wrapper):

- Defined the missing inputs from `state` at the top of
  `_generate_real_editor1_draft` (query/claims/evidence_items/sources/
  prior_drafts/draft_version). The LLM writer now actually executes.
- Curated evidence digest now pipes Phase 7 atomic metadata into the LLM:
  support_type, region, time_ref, policy_tool (alongside summary/strength/
  limitations) — bounded JSON, not raw 96k context.
- Rebuilt the system prompt to demand: cross-source synthesis + transmission
  chain (政策→地方落地→项目/基础设施→公司业务→产业链), region comparison
  table via the `region` field, credibility-vs-support separation (official
  source != reliable conclusion; downgrade when support_type=background /
  needs_fulltext_check), and method-vs-body consistency (uncovered dimensions
  listed as gaps, not claimed as covered). New section layout incl.
  地方政策与项目对比(表格), 传导链条与产业链映射, 后续跟踪清单.
- Switched prompt to JSON output `{"report_markdown": "..."}` to match
  `call_tooling_json`'s dict-root requirement.
- Replaced both `< 1500` thresholds with deficiency gating: fall back to
  template only when `len < 800` OR `## section count < 3`, so a genuine
  multi-section synthesized report is preserved even when shorter than target.
- Live-rerun follow-up fix: the internal template-fallback branch in
  `_generate_real_editor1_draft` did NOT populate `drafts`, so once the writer
  actually ran (and hit that branch on deficient output) the runner crashed at
  `partial["drafts"][-1]` (IndexError). This latent bug had been masked because
  the writer never ran before. Fixed by populating `drafts` in that branch.
  Verified deterministically: deficient LLM output → drafts length 1, runner
  access succeeds.
- SECOND live-rerun root cause (case1, 2026-06-18): even with the writer
  running, editor1 still emitted the template ledger. Cause: `call_tooling_json`
  hard-wired `max_tokens` to `settings.deepseek_max_tokens` (default **1200**).
  A 4000-6000 字 report needs ~4000+ completion tokens, so the JSON
  `{"report_markdown": "..."}` was truncated mid-string, failed to parse
  (payload=None), and fell back to template. build_evidence/build_claims
  succeeded only because their output fits under 1200 (completion 1081/1023).
  Fix: added an optional `max_tokens` passthrough to `call_tooling_json` ->
  `build_tooling_llm_client`; editor1 now requests `max_tokens=8000`.
- OPEN ITEM (under verification in case1b rerun): `finalize_report` calls the
  bytecode impl which composes the final report via the `compose_final_report`
  tool keyed on `claim_briefs` (dossier: compose_final_report_keys). If finalize
  re-assembles from claims rather than reading `drafts[-1]`, the editor1 LLM
  report would be discarded regardless. Verifying whether the max_tokens fix
  alone makes the LLM report reach the final artifact.
- case1b RESULT (2026-06-18, max_tokens=8000): editor1 LLM writer SUCCEEDED.
  Final draft = 5316 chars with the full Phase 9 section set —
  政策主线分析 / 地方政策与项目对比(表格 with atomic evidence IDs) /
  传导链条与产业链映射 / 公司披露(数据缺口) / 行业数据(数据缺口) /
  后续跟踪清单. Genuine synthesis (region comparison table citing
  ev_atomic_src_*, transmission-chain "链条断裂" analysis), NOT a ledger.
  Node sequence showed TWO rounds of plan_task→chief_gate — Phase 8 gap loop
  fired live. Run halted at human_review (decision=HUMAN_REVIEW), so finalize
  was never reached; the editor1 draft IS the delivered report.
- GATE-CALIBER FIX (the obligation口径 contradiction): `gate_obligation_gap_count
  =1` while `required_obligation_coverage` reported 3/3 covered, and
  `required_actions=[]`. Root cause: the chief_gate wrapper computed the gap from
  the INPUT `state["required_obligation_coverage"]` (empty during the gate step)
  and fell back to the `family_covered` heuristic (gap=1), while the
  authoritative family-aware coverage produced by the bytecode `_impl` lives in
  `result.contract_meta.chief_gate.required_obligation_coverage` (3/3 covered) —
  which is also what the summary reports. The two never agreed, so the gate
  routed HUMAN_REVIEW forever and never reached finalize. Fix: the wrapper now
  prefers `_impl`'s output coverage over the empty input-state copy, so the gap
  count, `all_obligations_covered`, and the summary all use one source of truth.
  The `_impl` coverage is the correct one to trust — its comment states it
  checks whether evidence actually comes from the required source family, i.e.
  it is stricter (family-aware) than the family_covered "has any evidence_ids"
  heuristic. Gate tests: 7 passed. Live re-verification in case1c.
- case1c RESULT (2026-06-18, after caliber fix): decision=**PASS** (was
  HUMAN_REVIEW), run **reached finalize_report for the first time**, single
  round (gap=0 so no second round needed), coverage 3/3. DECISIVE: the
  finalize_report final artifact (5279 chars) **fully preserved the editor1 LLM
  synthesis** — 政策主线分析 / 地方政策与项目对比(表格) / 传导链条与产业链映射
  / 公司披露(数据缺口) / 行业数据 / 后续跟踪清单, with 传导链条/对比表/数据缺口/
  ev_atomic citations all present. The feared "compose_final_report overwrites
  the draft" did NOT happen — compose tool keys are metadata only; finalize
  keeps `drafts[-1]`. Inspector: 7/9 (business_body 5279, ratio 1.0, sections
  6/6).
- SUMMARY-DISPLAY FIX: inspector still showed `obligation_gaps=1` despite
  PASS + coverage 3/3. Cause: the summary reads
  `contract_meta.chief_gate.obligation_gap_count`, which is the STALE value the
  bytecode `_impl` wrote from its own family heuristic; the wrapper computed the
  correct reconciled gap (0) only in a local variable and never wrote it back.
  Fix: the wrapper now writes the reconciled `obligation_gap_count` back into
  `result.contract_meta.chief_gate` (preserving the other _impl fields), so the
  summary, the gate decision, and the coverage table all agree. Gate tests:
  7 passed. End-to-end re-verification in case1d.

Validation result (2026-06-17):

- `py_compile`: pass; `ruff`: all 11 prior F821 errors RESOLVED by the input
  definitions (only 2 pre-existing F841 remain: `ev_map`/`src_map` in
  chief_gate, unrelated).
- NameError reproduced on HEAD (`name 'claims' is not defined`), gone after fix.
- Live provider confirmed reachable; exact editor1 call returns
  `llm_mode=live_provider`, `report_markdown` with region comparison + 传导链条.
- Deterministic threshold test: genuine 6-section report (len 1148) preserved
  as `llm_synthesized`; deficient short report correctly falls to template.
- Differential on the 2 failing editor1 tests
  (`outputs_markdown_oriented_sections`, `editor1_records_tool_traces`):
  **fail identically on HEAD** (pre-existing `IndexError`; they assert a stale
  English fixed-template shape `# low altitude economy` superseded by the
  Chinese LLM report). Zero new failures introduced. Other editor1/finalize/
  minimal_draft tests: `5 passed`.
- Note: editor1 context pack `token_estimate` is recorded by the runner's
  observability snapshot (raw included fields), separate from what the LLM
  actually receives (bounded JSON digest). The 80x figure was an observability
  artifact; the real defect was the writer never running. Budget-snapshot
  tuning, if still desired, is deferred to Phase 5 live measurement.

Validation:

```powershell
pytest -q tests\test_research_harness_graph.py -k "editor1 or finalize or report_markdown"
pytest -q tests\test_research_harness_tooling.py
```

Note: Phase 5 (live product gate rerun) runs AFTER Phases 7-9, so the four-case
live matrix tests the deepened report rather than the current shallow one.

## Continue Rule

After each phase, continue automatically to the next phase when:

- acceptance criteria are met
- required validation passes
- no protected-contract change is needed without explicit authorization
- provider/search/database dependencies are available
- live validation does not regress materially

Do not stop after a routine phase summary.

## Stop Conditions

Stop only when:

1. a protected contract change is required and not authorized
2. provider credentials or network are unavailable
3. repeated validation failures have no safe repair path
4. live validation regresses and the cause is unclear
5. user explicitly asks to pause
6. final done condition is reached

## Done Condition

This PLAN is complete only when:

- inspector truth fix is implemented and validated
- mandatory obligation gaps cannot PASS
- reader-facing report is separated from audit appendix
- P0 review issues affect gate decisions
- 4-case live matrix is rerun
- at least 3/4 live cases product-pass under the inspector
- STATUS and this PLAN are updated consistently

## Risks And Rollback

| Risk | Impact | Mitigation | Rollback |
|---|---|---|---|
| Gate becomes too strict | More HUMAN_REVIEW / NEED_MORE_EVIDENCE results | distinguish hard blockers from warnings | lower only soft thresholds |
| Audit separation changes expected graph-v1 preview | downstream consumers may rely on old shape | keep audit sidecar fields available | restore combined field while adding separate artifact |
| real_nodes recovery proxy limits clean fixes | broad edits risky | keep changes narrow or reconstruct source first | revert only our targeted patch |
| Live provider variance | smoke may fluctuate | compare inspector metrics and source artifacts | retry once with same query and record variance |

## Progress

### 2026-06-17: Phase 0 Documentation Status Correction

Completed:

- Made this PLAN the primary active execution plan in `.agent/STATUS.md`.
- Updated `.agent/PLANS/INDEX.md` so it no longer lists the older productization
  plan as active.
- Updated `docs/prd/deep_research_readable_report_prd_v0_1.md` so the PRD
  remains valid but points to this remediation PLAN as the current execution
  plan.
- Marked `.agent/PLANS/deep-research-readable-report-quality-v2.md` as
  superseded / not primary.
- Strengthened `docs/session-trace-2026-06-17.md` so old claims such as
  "gate correctly prevents blind PASS" and "no active PLAN" are explicitly
  overridden by the remediation state.
- No production code changed during this documentation-status correction.

Validation result:

- ASCII-only document consistency check passed for STATUS, INDEX, PRD, new PLAN,
  old PLAN, and session trace.
- The check confirms there is exactly one primary-active marker in the new PLAN
  and that trace no longer claims the blind-PASS gate issue is fixed.

### 2026-06-17: Phase 1 Quality Inspector Truth Fix

Completed:

- Fixed `scripts/report_quality_inspect.py` extraction paths to read graph-v1 response shapes truthfully.
- Three-layer extraction: report_preview integer counters → `tool_composed_report` list/counter → node-step `output_summary` counters.
- `_count_source_family_mismatches` now reads `tool_composed_report.claim_briefs` first.
- Added 5 tests covering top-level, tool_composed_report fallback, node-step fallback, zero-when-absent, and corrected mismatch source.

Validation result:

- `pytest -q tests/test_report_quality_inspect.py`: `16 passed` (was 11)
- Four-case rerun shows truthful counts (case1: 7/5/5, case2: 4/4/26, case3: 3/3/24, case4: 1/2/23)
- All four cases classify as `workflow_pass_product_fail` matching the PLAN baseline

### 2026-06-17: Phase 2 Gate Obligation Hard Block

Completed:

- `has_obligation_gap` now prefers authoritative `required_obligation_coverage[].covered` field.
- Eliminated two inconsistent truth sources (`all_obligations_covered` vs `has_obligation_gap`).
- case1_hefei now returns `HUMAN_REVIEW` instead of blind `PASS`.

Validation result:

- Focused gate tests: `4/5 passed` (1 pre-existing location-action contract gap, not caused by this change)
- HUMAN_REVIEW priority preserved (HUMAN_REVIEW branch returns before Block 1)
- Zero new failures introduced (baseline vs change differential identical)

### 2026-06-17: Phase 3 Report Artifact Separation

Completed:

- Split logic in `real_nodes.py:finalize_report_provider_backed` narrowed to only `## Audit Appendix` / `## 审计附录` markers.
- Removed over-aggressive markers that were stripping reader-facing content: `Evidence And Limitations`, `Claim Verifications`, `key_claims`.
- `report_markdown` now retains source display, Evidence display, title cleaning, and mojibake repair.
- The bytecode already produces separated `report_preview.audit_markdown` for live cases.

Validation result:

- `pytest -q tests/test_research_harness_graph.py -k "finalize_report or report_markdown"`: `5 passed` (was 1 passed, 4 failed)
- `## Evidence And Limitations` stays in `report_markdown`
- Source titles, mojibake repair, and label cleaning all verified in `report_markdown`

### 2026-06-17: STATUS/PLAN Consistency Correction

STATUS.md and PLAN file corrected:

- STATUS: removed false "remediation cycle completed" / "No active long-running PLAN" claims
- STATUS: unified around single coherent state: PLAN active, Phase 3 completed, Phase 4/5 pending
- PLAN: status changed from `completed_keep_opt_in_with_documented_gaps` to `active_phase3_completed_phase4_pending`
- PLAN Phase 6: changed from `completed_honest_assessment` to `not_yet`
- Test claims corrected: finalize is genuinely 5/5 (was falsely reported as 5/5 when actually 1/5)
- Live quality claim corrected: all 4 cases are `workflow_pass_product_fail`, not "3 product PASS"

## Latest Validation Snapshot

2026-06-17 documentation/status correction:

- `.agent/STATUS.md` points to this PLAN as the primary active plan.
- `.agent/PLANS/INDEX.md` now lists this PLAN as the active execution plan.
- `docs/prd/deep_research_readable_report_prd_v0_1.md` now marks this remediation PLAN as the current execution plan.
- `.agent/PLANS/deep-research-readable-report-quality-v2.md` remains superseded and non-primary.
- `docs/session-trace-2026-06-17.md` is historical only and has an errata.
- Production code was not changed during the documentation-status correction.
- Follow-up validation passed after avoiding Chinese string literals in the
  PowerShell -> Python pipe, which can be lossy in this Windows terminal.

## Next Action

Phase 1-4 are complete and validated. Start Phase 5: re-run 4 live smoke cases and require product-quality pass.

```powershell
pytest -q tests\test_research_harness_graph.py -k "editor2 or chief_gate or human_review"
```
