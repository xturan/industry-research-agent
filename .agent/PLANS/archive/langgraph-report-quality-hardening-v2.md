# LangGraph Report Quality Hardening v2

Status: completed

Created: 2026-06-15

Primary active PLAN: yes

## Objective

Move `graph_v1` from "functionally connected" to a product-quality research
workflow that a real user can trust, review, and read.

The previous plan proved that the opt-in LangGraph path can produce multiple
claims, support-strength scores, human-review state, prompt/context metadata,
and `report_markdown`. This plan treats those as a baseline, not the finish
line. The new finish line is practical report quality:

1. report text must be readable in the user's language, not mojibake
2. `HUMAN_REVIEW` must be demonstrated as a real pause/resume loop with live
   artifacts
3. LLM output contracts must normalize common provider shapes instead of
   repeatedly falling back on avoidable schema mismatches
4. context budgets must become enforceable governance signals, not only passive
   metadata
5. claim/evidence/report quality must be judged by real inspection criteria,
   not only `status=succeeded` and `decision=PASS`

## Task Classification

- Primary area: `research_workflow`
- Secondary areas:
  - `content_factory`
  - `provider_layer`
  - `eval_policy_ops`
  - `task_substrate`

## Execution Mode

Mode: `full_subagent`

Reason:

- The work affects user-facing research conclusions, report artifacts,
  provider-backed LLM output handling, human-review resume behavior, and
  quality gates.

Risk triggers:

- user-visible report behavior
- research workflow stage contracts
- provider output normalization
- live validation quality gates

Allowed write scope:

- `packages/research_harness/**`
- `packages/research_reports/**`
- `apps/api/routes/deep_research.py` if API visibility needs additive fields
- `scripts/graph_provider_backed_smoke*.py`
- `tests/test_research_harness_*.py`
- `tests/test_research_api.py`
- `.agent/PLANS/**`
- `.agent/STATUS.md`
- targeted docs/handoffs if needed

Forbidden changes without explicit PLAN amendment:

- no legacy `/deep-research/analyze` response shape changes
- no legacy `/research/analyze` response shape changes
- no destructive run/task status semantic changes
- no breaking EvidenceBundle or citation-field changes
- no making `graph_v1` the default path

Required validation:

- focused compile and ruff for touched files
- focused pytest for graph, API, prompt/context, dossier/report behavior
- real provider-backed smoke for readable report
- real provider-backed pause/resume smoke for `HUMAN_REVIEW`

Escalation rule:

- If a protected public response shape must change, stop and amend this PLAN
  before code changes.

## Product Quality Contracts

### Readable Report Contract

`report_markdown` is the user-facing research report body. It is not merely a
debug preview. A valid report must:

- avoid mojibake in user-visible Chinese text
- preserve claim IDs and evidence IDs for auditability
- show sections that a reader can scan without opening raw JSON
- suppress navigation, PDF boilerplate, and generic web chrome when possible
- keep limitations visible instead of overclaiming

### Human Review Contract

`HUMAN_REVIEW` is a workflow pause, not just a decision label. A valid
human-review run must:

- return a visible pending payload with reason, blockers, available actions,
  and current report/draft snapshot
- persist checkpoint state before waiting for user action
- resume from the same run with a selected action
- show the resumed action in the response, checkpoint history, and dossier

### LLM Contract Normalization

Provider-backed LLM nodes should accept common equivalent shapes when safe.
For example, if a provider returns numeric confidence such as `0.82`, the
workflow should normalize it into the schema's qualitative labels
`high` / `medium` / `low` instead of falling back when the rest of the payload
is usable.

The principle is deterministic normalization before fallback:

- normalize safe, local, explainable variants
- validate the normalized payload
- fall back only when required fields or semantics remain invalid

### Context Budget Governance

`context_budget_tokens` is the expected token budget for a node's context pack.
It belongs to prompt/context governance, not to source retrieval itself.

A valid governance implementation must:

- expose when `token_estimate` exceeds `context_budget_tokens`
- record a clear `budget_status`
- avoid silently calling an over-budget context "healthy"
- eventually compress or gate over-budget context, but this plan can start with
  observable enforcement metadata if no prompt payload is being directly sent

## Phases

### Phase 1: Product-Quality Baseline And Contracts

Status: completed

Objective:

- turn the previous completion audit into explicit hardening targets
- select the first narrow implementation slice

Acceptance criteria:

- this PLAN is active in `.agent/STATUS.md`
- the known gaps are listed as product-quality contracts
- execution mode and validation loop are explicit

### Phase 2: Report Readability And Encoding Hardening

Status: completed

Objective:

- make readable reports actually readable under real Chinese queries

Tasks:

- identify whether mojibake originates from input query, shell/API boundary,
  source text extraction, provider response, or report rendering
- add deterministic detection/repair for common UTF-8-as-GBK mojibake when
  safe
- keep original raw fields available for auditability where practical
- add tests that fail on obvious mojibake in `report_markdown`

Acceptance criteria:

- S03-style and procurement-style report bodies no longer show obvious mojibake
  for core user-facing query/section text
- report remains linked to claim/evidence IDs

### Phase 3: Real Human-Review Pause/Resume Smoke

Status: completed

Objective:

- prove `HUMAN_REVIEW` as a real user decision loop with artifacts

Tasks:

- add or extend a smoke script that can intentionally reach pending
  `HUMAN_REVIEW`
- persist the pending response artifact
- resume the same run with `approve`, and optionally `add_evidence` or
  `rewrite` when safe
- write a compact summary that shows before-resume and after-resume behavior

Acceptance criteria:

- live artifact shows `decision=HUMAN_REVIEW` with `human_review.pending=true`
- resume artifact shows `resumed_from_checkpoint=true`
- selected action and notes are visible
- approve path finalizes into a readable report

### Phase 4: Editor LLM Output Contract Normalization

Status: completed

Objective:

- reduce avoidable fallback when live provider output is semantically usable

Tasks:

- normalize numeric paragraph confidence into qualitative labels
- preserve validation metadata so we can tell normalized success from raw
  success and fallback
- add tests for numeric confidence normalization
- keep fallback path for genuinely invalid provider output

Acceptance criteria:

- live editor output with numeric confidence no longer triggers fallback solely
  for that reason
- contract metadata records normalization

### Phase 5: Context Budget Enforcement Metadata

Status: completed

Objective:

- make context budget overruns visible and actionable

Tasks:

- add context budget status metadata to context pack summaries
- identify over-budget nodes in smoke artifacts
- add tests that over-budget packs are marked explicitly

Acceptance criteria:

- `context_packs` expose budget status such as `within_budget`,
  `over_budget`, or `unbudgeted`
- live artifacts identify over-budget nodes without manual inspection

### Phase 6: Product-Quality Live Validation Matrix

Status: completed

Objective:

- validate the hardened workflow against real application scenarios

Required cases:

- S03 local policy/project case
- disclosure-heavy case
- procurement/policy case
- forced human-review pause/resume case

Acceptance criteria:

- at least three normal cases produce readable reports without obvious mojibake
- pause/resume case demonstrates actual user decision flow
- editor fallback from numeric confidence is eliminated or explicitly explained
- context budget overrun status is visible
- remaining risks are recorded as product-quality gaps, not hidden behind PASS

## Continue Rule

After each phase passes validation, continue automatically to the next phase
unless:

- validation worsens report quality or auditability
- protected response or run/task contracts need an unplanned breaking change
- credentials/network/API runtime is unavailable
- the same failure class repeats twice without a safe repair path
- the user explicitly pauses or redirects

## Done Condition

This plan is done only when:

- readable reports are actually readable for the real Chinese smoke cases
- `HUMAN_REVIEW` has a real pause/resume live artifact
- editor LLM numeric confidence is normalized or otherwise contract-aligned
- context budget governance is visible in response artifacts
- PLAN and STATUS are cleanly closed without contradictory active/next markers

## Stop Conditions

Stop and ask before continuing only when:

- a public response shape must change in a breaking way
- a database migration becomes necessary
- external credentials or network are missing
- live validation repeatedly fails and the next repair would be speculative
- graph-v1 default promotion is being considered

## Validation Loop

Focused validation:

```powershell
python -m py_compile packages\research_harness\runner.py packages\research_harness\real_nodes.py packages\research_harness\context.py packages\research_harness\schemas.py scripts\graph_provider_backed_smoke.py tests\test_research_harness_graph.py tests\test_research_harness_prompt_assets.py tests\test_research_api.py
python -m ruff check packages\research_harness packages\research_reports scripts\graph_provider_backed_smoke.py tests\test_research_harness_graph.py tests\test_research_harness_prompt_assets.py tests\test_research_api.py
pytest -q tests\test_research_harness_graph.py
pytest -q tests\test_research_harness_prompt_assets.py
pytest -q tests\test_research_api.py tests\test_research_run_dossier.py
```

Research contract validation:

```powershell
pytest -q tests\test_agents_workflow.py
pytest -q tests\test_research_provider_integration.py
pytest -q tests\test_deepseek_provider.py
```

Live validation:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\langgraph_quality_hardening_s03_v1 --query "2025年合肥低空经济地方政策项目公示官方来源" --max-rounds 2 --max-loop-count 1
python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\langgraph_quality_hardening_procurement_v1 --query "2025年低空经济政策与公共资源采购中标证据 官方来源" --max-rounds 2 --max-loop-count 1
```

## Risks And Rollback

Risks:

- mojibake repair can corrupt text if applied too aggressively
- stricter report-quality checks may reveal source extraction weaknesses
- reducing fallback may allow poorly structured LLM text if normalization is too
  broad
- budget enforcement may expose that current context packs routinely exceed
  budgets before compression exists

Rollback:

- keep graph-v1 opt-in
- keep raw source/evidence fields for audit
- limit normalization to deterministic, tested transformations
- expose over-budget status before enforcing hard truncation

## Progress

### 2026-06-15

- User clarified that system design must meet real report-quality product needs,
  not merely mark functions complete.
- Previous archived PLAN was audited and judged functionally useful but not yet
  product-quality complete.
- This PLAN was created to harden the remaining quality gaps:
  readable Chinese report output, real human-review live resume artifacts,
  editor output contract normalization, and context budget governance.

### 2026-06-15 - Phase 2 readability hardening completed

- Added display-only mojibake repair at report composition boundaries so
  query / claim / title / summary text is normalized for the readable report
  without rewriting raw stored source/evidence fields.
- Added deterministic editor output normalization before fallback:
  numeric paragraph confidence such as `0.82` now maps into
  `high` / `medium` / `low` for `EditorDraftOutput`.
- Added context budget governance metadata:
  `budget_status` and `budget_overage_tokens` are now attached to
  `GraphContextPackSummary`.
- Focused validation passed:
  - `python -m py_compile packages\research_harness\contracts.py packages\research_harness\context.py packages\research_harness\schemas.py packages\research_harness\real_nodes.py tests\test_research_harness_graph.py`
  - `python -m ruff check packages\research_harness\contracts.py packages\research_harness\context.py packages\research_harness\schemas.py packages\research_harness\real_nodes.py tests\test_research_harness_graph.py`
  - `pytest -q tests\test_research_harness_graph.py -k "human_review or readable_markdown or provider_backed_uses_search_provider or choose_report_source_label or omits_noisy_excerpt or repairs_mojibake or numeric_confidence"` -> `12 passed`
  - `pytest -q tests\test_research_harness_prompt_assets.py` -> `2 passed`
  - `pytest -q tests\test_research_api.py tests\test_research_run_dossier.py` -> `14 passed`
- Real provider-backed smoke passed:
  - `python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\langgraph_quality_hardening_s03_v1 --query "2025年合肥低空经济地方政策项目公示官方来源" --max-rounds 2 --max-loop-count 1`
  - result: `status=succeeded`, `decision=PASS`
  - readable report no longer showed the earlier `骞/绛/鍚堣偉`-style mojibake in
    the core user-facing report body
  - `editor1_draft` contract meta moved from avoidable fallback to
    `status=normalized`
  - context packs now visibly mark over-budget nodes, e.g.
    `collect_sources`, `editor1_draft`, and `finalize_report`

### 2026-06-15 - Phase 3 live human-review pause/resume completed

- Extended `scripts/graph_provider_backed_smoke.py` so it can now:
  - persist the initial response as `response.initial.json`
  - resume the same run with `--resume-action`
  - persist the resumed response as `response.resume.json`
  - summarize both the initial and resumed states in `summary.json`
- First attempted to use the local S03-style query for forced live pause/resume,
  but the current retrieval/claim path now passed directly, so it no longer
  served as a stable `HUMAN_REVIEW` forcing case.
- Switched to the historically harder `X01` local+disclosure case and verified
  the full live loop:
  - command:
    `python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\langgraph_human_review_pause_resume_x01_v1 --query "2025年合肥低空经济上市公司年报披露与地方政策项目公示官方来源" --max-rounds 2 --max-loop-count 1 --resume-action approve --resume-notes "Approved after manual review for product validation."`
  - initial artifact:
    `data/tmp/langgraph_human_review_pause_resume_x01_v1/response.initial.json`
    -> `decision=HUMAN_REVIEW`
    -> `human_review.pending=true`
    -> supported actions include `approve`, `add_evidence`, `rewrite`, `reject`
  - resumed artifact:
    `data/tmp/langgraph_human_review_pause_resume_x01_v1/response.resume.json`
    -> `decision=PASS`
    -> `resumed_from_checkpoint=true`
    -> `human_review.pending=false`
    -> `human_review.selected_action=approve`
    -> `human_review.status=approved`
- The live case also preserved a product-relevant reason for needing human
  review in the first place:
  - company disclosure obligation uncovered
  - local precision obligation uncovered
  - unstable search rate remained visible
- This phase therefore validates a real user participation loop rather than
  only unit tests.

### 2026-06-15 - Phase 4/5/6 product-quality hardening completed

- Added user-visible contract diagnostics to graph dossiers:
  - `Contract Diagnostics` now shows node-level contract status, fallback use,
    normalization notes, input mode, LLM mode, and tooling status.
  - This makes `validated` / `normalized` / `composed` / `fallback` visible
    without manually opening raw `response.json`.
- Extended `scripts/graph_provider_backed_smoke.py` summary output with:
  - `contract_diagnostics`
  - `contract_status_by_node`
  - `contract_fallback_nodes`
  - `contract_normalized_nodes`
  - `over_budget_context_packs`
  - `over_budget_node_names`
- Completed the editor contract normalization visibility path:
  - live provider output with numeric editor confidence is recorded as
    `editor1_draft.status=normalized`
  - normalization reason is visible as
    `editor_draft_numeric_confidence_to_label`
  - fallback nodes are explicitly listed and remained empty in the validated
    live cases
- Completed context-budget governance visibility:
  - dossier context pack tables and details now show `budget_status` and
    `budget_overage_tokens`
  - smoke summaries identify over-budget nodes directly, so no manual JSON
    inspection is required
- Completed final report composition diagnostics:
  - `finalize_report` now records `status=composed`,
    `used_fallback=false`, and `attempt_count=0`
- Hardened readable-report noise filtering:
  - suppressed Office/ZIP binary payloads such as `PK!`,
    `[Content_Types].xml`, `word/fontTable.xml`, and `docProps/` from report
    excerpts
  - this is display-layer cleanup and does not rewrite raw evidence/source
    storage

Validation passed:

- `python -m py_compile packages\research_harness\real_nodes.py packages\research_reports\dossier.py scripts\graph_provider_backed_smoke.py tests\test_research_harness_graph.py tests\test_research_run_dossier.py`
- `python -m ruff check packages\research_harness\real_nodes.py packages\research_reports\dossier.py scripts\graph_provider_backed_smoke.py tests\test_research_harness_graph.py tests\test_research_run_dossier.py`
- `pytest -q tests\test_research_run_dossier.py` -> `5 passed`
- `pytest -q tests\test_research_harness_graph.py -k "provider_backed_uses_search_provider or readable_markdown or numeric_confidence or clean_report_excerpt or phase3_contract_fallbacks"` -> `9 passed`

Live validation matrix:

- S03/local case:
  - `data/tmp/langgraph_quality_matrix_s03_phase6_v1/response.json`
  - result: `status=succeeded`, `decision=PASS`, `claim_count=3`
  - report has readable markdown sections:
    `executive_summary`, `key_claims`, `evidence_and_limitations`,
    `review_status`
  - `finalize_report.status=composed`
  - `contract_fallback_nodes=[]`
  - `contract_normalized_nodes=["editor1_draft"]`
- disclosure-heavy case:
  - `data/tmp/langgraph_quality_matrix_disclosure_phase6_v1/response.json`
  - result: `status=succeeded`, `decision=PASS`, `claim_count=3`
  - `obl_company_disclosure.covered=true`
  - `finalize_report.status=composed`
  - `contract_fallback_nodes=[]`
- procurement/policy case:
  - `data/tmp/langgraph_quality_matrix_procurement_phase6_v2_resume/response.json`
  - initial result entered `HUMAN_REVIEW` due real search instability
  - resumed result: `status=succeeded`, `decision=PASS`,
    `resumed_from_checkpoint=true`, `human_review.status=approved`
  - `claim_count=2`, readable report markdown present
  - ASCII binary report-noise check passed:
    `PK!`, `[Content_Types].xml`, `word/fontTable.xml`, `docProps/`,
    `% 1 0 obj`, `obj <>`, `endobj`, and `stream ` all had count `0`
- forced human-review pause/resume case:
  - `data/tmp/langgraph_quality_matrix_human_review_phase6_v1/response.json`
  - initial result: `decision=HUMAN_REVIEW`,
    `human_review.pending=true`
  - resumed result: `decision=PASS`, `resumed_from_checkpoint=true`,
    `human_review.selected_action=approve`,
    `human_review.status=approved`
  - retained product-relevant blockers:
    `company_disclosure` gap and `location_precision` gap remained visible
    after manual approval

Observed product-quality risks kept visible:

- Context packs are routinely over budget in live cases. This plan made the
  overrun visible and auditable, but did not implement compression/truncation.
- Real search instability can push otherwise covered procurement cases into
  `HUMAN_REVIEW`; this is acceptable for safety, but future work should improve
  retry/source-family routing and distinguish transient provider instability
  from actual evidence weakness.
- Human approval can intentionally finalize a report while blockers remain
  visible. This is correct for a human-in-loop workflow, but future UI/API work
  should make the approval tradeoff explicit to the reviewer.

## Next Action

Archive this completed PLAN. Suggested next PLAN:

1. context-budget compression and context-pack slimming
2. stronger source routing for procurement/disclosure evidence stability
3. UI/API presentation of human-review approval tradeoffs
