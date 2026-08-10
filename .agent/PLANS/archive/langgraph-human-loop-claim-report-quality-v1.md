# LangGraph Human Loop Claim Report Quality v1

Status: completed

Created: 2026-06-14

Primary active PLAN: yes

## Objective

Turn the current opt-in LangGraph research workflow from a mechanically
complete graph into a report-quality workflow with:

1. real human-review participation
2. richer multi-claim report structure
3. evidence-strength scoring with usable separation
4. readable final report output instead of JSON-only preview
5. formal prompt engineering and context engineering planning

The immediate baseline comes from the real `S03` live case:

- `HUMAN_REVIEW` was reached, but the user was not actually asked to make a
  decision.
- `support_strength` concentrated around `0.68`, so the score had weak
  discriminative value.
- only one claim (`claim_policy_primary`) was produced.
- final output remained a JSON preview plus dossier, not a claim-driven
  readable research report.
- `editor1_draft` accepted a live LLM call but fell back because the returned
  confidence shape did not match the strict output contract.

## Task Classification

- Primary area: `research_workflow`
- Secondary areas:
  - `content_factory`
  - `provider_layer`
  - `eval_policy_ops`
  - `task_substrate`
- Execution mode:
  - `planning_only` for Phase 0
  - expected `full_subagent` for implementation phases because the work crosses
    workflow boundaries, user-facing report behavior, and human-review routing

## Execution Mode

Mode: `planning_only`
Reason: this slice first freezes product problems and protected contracts before
any implementation.
Risk triggers:
- human-review routing affects user-visible workflow semantics
- claim architecture affects downstream report generation and evidence linkage
- readable report output affects product behavior and may touch artifact shape
Allowed write scope:
- `.agent/PLANS/`
- `.agent/STATUS.md`
- optional roadmap/status docs only
Forbidden changes:
- no production code changes in Phase 0
- no public API response shape change
- no run/task semantic change without later explicit authorization
Required validation:
- plan file exists
- `.agent/STATUS.md` points to this plan
- no production code changed during planning-only step
Escalation rule:
- if implementation changes public response shape, run lifecycle meaning, or
  report artifact contract, record that explicitly before code work starts

## Protected Contracts

Do not silently change:

- `/deep-research/graph/analyze` response shape
- legacy `/deep-research/analyze` response shape
- legacy `/research/analyze` response shape
- existing `DeepResearchReport`, `EvidenceItem`, `SourceAssessment` public
  schemas
- existing run/task status semantics
- existing `runs` / `run_steps` meaning
- current `research_reports.dossier_path` contract
- current graph checkpoint resume semantics

Possible additive changes later:

- human-review interruption metadata
- richer internal claim/evidence/report records
- readable report artifacts derived from existing graph business records
- prompt/context pack registries and diagnostics

## Problem Freeze

This plan starts from five concrete product problems observed in the real S03
case and user review:

1. `human_review` is not a real human loop.
   Current behavior:
   graph routes to a normal node, appends `issue_human_review`, then continues
   to `finalize_report`.
   Required product behavior:
   reaching `HUMAN_REVIEW` must create a real user decision point, including
   visible pending action and resume path.

2. Evidence strength is too flat.
   Current behavior:
   many `background_support` evidence items cluster at `0.68`, so
   `support_strength` does not separate weak policy context from stronger
   evidence.
   Required product behavior:
   the score must help verifier/gate/report distinguish evidence quality, not
   just exist as a decorative field.

3. Claim architecture is too thin.
   Current behavior:
   S03 produced only one policy claim despite 12 sources and 12 evidence items.
   Required product behavior:
   one research run should produce a usable set of claims that can support
   sectioned writing, review, and gap analysis.

4. Final report is not yet a readable report.
   Current behavior:
   `final_report` is effectively a JSON preview and `tool_composed_report`
   summary.
   Required product behavior:
   final report output must be readable prose/sections organized around claims,
   evidence, limitations, and review status.

5. Prompt/context engineering is not yet a first-class system.
   Current behavior:
   context packs exist, but prompt design and context design are still thin and
   under-specified for editor/reviewer/gate/report quality.
   Required product behavior:
   prompt engineering and context engineering must become formal design assets
   with validation and ownership.

## Scope

In scope:

1. human-review product contract
2. claim decomposition and claim-family design
3. evidence-strength scoring redesign
4. readable final report architecture
5. prompt/context engineering framework for graph-v1 nodes
6. live-case-based validation against real cases like `S03`

Out of scope for this plan:

- replacing legacy Deep Research endpoints by default
- a full UI redesign unrelated to human-review flow
- broad source-layer expansion unrelated to the five frozen problems
- arbitrary new agent roles unless they directly serve the above contracts

## Design Direction

### Human Loop

`human_review` means:

- the workflow must stop at a real pending review state
- the user must see what needs review and what the available actions are
- resume paths must be explicit:
  - approve current report
  - request add evidence
  - request rewrite
  - mark as rejected / incomplete

### Claim Architecture

`claim` means:

- a concrete, auditable, report-relevant assertion
- not just one top-level policy statement for the whole query
- claims should be organized by report purpose, such as:
  - policy basis claim
  - local implementation claim
  - project/public-notice claim
  - data/statistics corroboration claim
  - company disclosure claim when applicable

### Evidence Strength

`support_strength` means:

- claim-facing support intensity, not a recycled source score
- it should separate:
  - weak background context
  - moderate corroboration
  - direct support
  - high-specificity auditable support

### Readable Report

`final report` means:

- readable sections and paragraphs
- claim-linked narrative
- explicit evidence and limitation structure
- clear statement of unresolved review/human-gate state

### Prompt Engineering / Context Engineering

- `prompt engineering`:
  defines how each node asks for structured behavior from the model.
- `context engineering`:
  defines what information the node gets, in what shape, with what compression,
  and with what exclusion rules.
- both need versioning, ownership, and live-case validation.

## Phases

### Phase 0: Problem Freeze And Contract Design

Status: completed

Objective:

- convert the five observed problems into explicit implementation contracts
- identify which contracts are internal-only and which are user-visible

Tasks:

- freeze the S03 findings as baseline evidence
- define the target contract for:
  - human-review participation
  - claim decomposition
  - evidence-strength semantics
  - readable report output
  - prompt/context engineering assets
- identify which later phases may require Architecture Gate attention

Acceptance criteria:

- every problem has a clear current behavior and target behavior
- implementation can start later without rediscovering the same product gaps

### Phase 1: Human Review Product Contract

Status: completed

Objective:

- redesign `HUMAN_REVIEW` from a passive node into a true user-participation
  state

Tasks:

- define pending-review state representation
- define resume actions and their mapping back into graph routing
- define dossier/API/task visibility for pending review
- replace the current auto-pass-through `human_review` node behavior with a
  real interruption boundary
- define what the graph persists before waiting for human input
- define the minimum review payload:
  - gate reason
  - blocking issues
  - current draft/report snapshot
  - supported actions
- define how resume decisions map to:
  - approve -> `finalize_report`
  - add evidence -> planning/search loop
  - rewrite -> editor loop
  - reject/stop -> terminal reviewed failure or archived incomplete state

Acceptance criteria:

- `HUMAN_REVIEW` no longer silently finalizes without user involvement
- review blockers and options are visible and actionable
- graph state can stop and resume around human review without redefining the
  entire run/task model

### Phase 2: Claim And Evidence Quality Redesign

Status: completed

Objective:

- increase claim granularity and evidence-score usefulness

Tasks:

- define claim families by query intent
- redesign support-strength calibration bands
- ensure claims are numerous enough to support report sections
- split the current coarse claim layer into reusable claim families such as:
  - policy basis
  - local rollout / project notice
  - procurement / award / transaction
  - statistics corroboration
  - company disclosure when applicable
- redesign `support_strength` so it is driven by claim-facing evidence features,
  not mostly flattened by one background cap
- define minimum claim-count expectations by query type
- define how verifier and chief gate should consume the richer claim set

Acceptance criteria:

- S03-like policy/local cases produce multiple usable claims
- support-strength is no longer dominated by one flat background score
- claim decomposition remains auditable and does not create unsupported noise

### Phase 3: Readable Report Generation

Status: completed

Objective:

- upgrade final output from JSON preview to readable report artifact

Tasks:

- define section/paragraph report contract
- define how claims/evidence/limitations map into report sections
- define what happens when decision is `HUMAN_REVIEW` or `REVIEW_RISK`
- upgrade `finalize_report` from JSON preview assembly to readable report
  composition
- define section layout for:
  - executive summary
  - key claims
  - evidence and limitations
  - local/disclosure/procurement subsections when applicable
  - review status / pending human decisions
- decide whether readable report is stored as:
  - structured markdown/report body
  - richer JSON + renderable markdown
  - both
- preserve audit links back to claim IDs and evidence IDs

Acceptance criteria:

- final artifact is readable prose, not only summary JSON
- report remains auditable back to claim/evidence IDs
- `HUMAN_REVIEW` and `REVIEW_RISK` states remain visible in the report itself

### Phase 4: Prompt/Context Engineering System

Status: completed

Objective:

- formalize prompt/context engineering as versioned product assets

Tasks:

- identify node-by-node prompt assets
- identify node-by-node context pack requirements and budget
- define live-case validation for prompt/context quality
- create a prompt/context inventory for:
  - `plan_task`
  - `build_claims`
  - `editor1_draft`
  - `editor2_review`
  - `verify_claims`
  - `chief_gate`
  - `finalize_report`
- define prompt contracts, output contracts, fallback rules, and context budget
  for each node
- define where these prompt/context assets should live in the repository
- define how live-case regressions are evaluated against prompt/context changes

Acceptance criteria:

- prompt/context design is no longer implicit or ad hoc
- future editor/review/gate/report changes have a stable design surface
- S3-style failures can be traced to either prompt contract, context contract,
  or provider/runtime failure class

### Phase 5: Real-Case Validation Loop

Status: completed

Objective:

- validate the redesigned contracts on real API-backed cases

Tasks:

- rerun `S03` and at least one disclosure-heavy case
- compare before/after:
  - human loop behavior
  - claim count
  - support-strength spread
  - report readability
- include at least:
  - `S03` local policy/project case
  - one disclosure-heavy case that previously failed or over-simplified
  - one procurement/policy case to ensure no regression on core coverage
- record before/after examples in terms a user can directly inspect from the
  produced dossier/report

Acceptance criteria:

- live cases demonstrate practical behavior change, not only internal refactor
- validation captures both quality improvements and any new latency/cost tradeoff

## Continue Rule

After each phase passes validation, continue automatically to the next phase
unless:

- a protected public contract must change unexpectedly
- validation fails repeatedly without a safe fix path
- credentials/runtime are unavailable
- the user explicitly pauses or redirects

## Done Condition

This plan is done only when:

- `HUMAN_REVIEW` is a real user participation state
- S03-like cases produce multiple usable claims
- evidence-strength scoring has visible separation
- final graph output includes a readable report artifact
- prompt/context engineering is formalized enough to guide future iterations
- at least one real case shows before/after improvement in all major areas

## Stop Conditions

Stop and ask before implementation only when:

- a public graph response shape change becomes necessary
- task/run semantics would need to change
- a new UI/API dependency is required but not available
- the human-review product contract requires decisions outside current scope

## Validation Loop

Planning-only validation:

```powershell
Get-Content -Raw .agent\PLANS\langgraph-human-loop-claim-report-quality-v1.md
Get-Content -Raw .agent\STATUS.md
git diff -- .agent\PLANS .agent\STATUS.md
```

Expected implementation validation later:

```powershell
python -m ruff check packages\research_harness apps\api\routes\deep_research.py packages\research_reports tests
python -m py_compile packages\research_harness\runner.py packages\research_harness\nodes.py packages\research_harness\real_nodes.py packages\research_reports\dossier.py
pytest -q tests\test_research_harness_graph.py
pytest -q tests\test_research_api.py
pytest -q tests\test_research_provider_integration.py
pytest -q tests\test_deepseek_provider.py
pytest -q tests\test_tasks_service.py tests\test_tasks_api.py
```

Live validation target later:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\langgraph_human_loop_quality_s03_v1 --query "2025年合肥低空经济地方政策项目公示官方来源" --max-rounds 2 --max-loop-count 1
```

## Risks And Rollback

Risks:

- richer claim decomposition may increase noise if evidence linking is not kept
  strict
- human-review interruption may require task/API semantics clarification
- readable report generation may expose weaknesses in current draft schema
- prompt/context expansion may increase token cost and latency

Rollback:

- keep graph-v1 opt-in
- keep existing dossier and JSON preview path available while readable report
  path is built
- keep public API shapes stable unless later phases explicitly authorize change

## Progress

### 2026-06-14

- Real S03 case review exposed five product-level gaps:
  human loop, flat evidence strength, too-few claims, JSON-only final report,
  and under-specified prompt/context engineering.
- This plan was created to make those gaps the next primary LangGraph
  implementation line instead of continuing tooling-only work.

### 2026-06-14 - Phase 0 contract freeze completed

- Confirmed concrete current behavior from the real S03 artifacts:
  - `chief_gate` reached `REVIEW_RISK` then `HUMAN_REVIEW`
  - `human_review` only appended `issue_human_review` and the graph still
    finalized automatically
  - `build_claims` produced exactly one claim:
    `claim_policy_primary`
  - claim support matrix average strength stayed at `0.68`
  - `finalize_report` produced JSON preview data and `tool_composed_report`,
    not a readable report body
  - `editor1_draft` used live provider output but fell back because confidence
    values like `0.75` violated the strict contract
- Derived the implementation order:
  1. freeze human-review interruption contract
  2. redesign claim/evidence layer
  3. redesign readable report output
  4. formalize prompt/context assets
  5. rerun live validation
- Added implementation handoff:
  - `.agent/HANDOFFS/langgraph-human-loop-claim-report-quality-handoff-20260614.md`
  so the next thread can start directly from Phase 1 without re-reading the
  old tooling-era assumptions.

### 2026-06-14 - Phase 1 human-review interruption contract implemented

- Replaced the old `chief_gate -> human_review -> finalize_report` auto-pass
  path with a real interruption boundary, so graph-v1 now stops at
  `human_review` and does not auto-finalize before a human decision.
- Added additive human-review request/response contract surface:
  - `GraphAnalyzeRequest.human_review_action`
  - `GraphAnalyzeRequest.human_review_notes`
  - `GraphAnalyzeResponse.human_review`
  - `GraphRunSummary.pending_human_review`
- `human_review` now persists the minimum review payload required by this plan:
  gate reason, blocker issues, current draft snapshot, required actions, and
  supported actions.
- Resume decisions now map through the checkpointed graph state:
  - `approve` -> `finalize_report`
  - `add_evidence` -> `plan_task`
  - `rewrite` -> `editor1_draft`
  - `reject` -> terminal stop without auto-finalize
- Dossier rendering now exposes the human-review payload, so pending-review
  runs are visible in dossier output rather than only implicit in node traces.
- Phase 1 kept protected public/run/task contracts stable:
  no legacy endpoint shape changes and no new run/task status semantics.

Validation:

- `python -m py_compile packages\research_harness\runner.py packages\research_harness\nodes.py packages\research_harness\graph.py packages\research_harness\schemas.py packages\research_harness\state.py packages\research_harness\service.py packages\research_reports\dossier.py apps\api\routes\deep_research.py tests\test_research_harness_graph.py tests\test_research_api.py` -> pass
- `python -m ruff check packages\research_harness\runner.py packages\research_harness\nodes.py packages\research_harness\graph.py packages\research_harness\schemas.py packages\research_harness\state.py packages\research_harness\service.py packages\research_reports\dossier.py apps\api\routes\deep_research.py tests\test_research_harness_graph.py tests\test_research_api.py` -> pass
- `pytest -q tests\test_research_harness_graph.py::test_graph_runner_hits_human_review_when_loop_budget_is_zero tests\test_research_harness_graph.py::test_graph_runner_resume_from_pending_human_review_approval tests\test_research_api.py::test_deep_research_graph_api_human_review_pause_and_resume` -> `3 passed`
- `pytest -q tests\test_research_harness_graph.py` -> `20 passed`
- `pytest -q tests\test_research_api.py` -> `10 passed`
- `pytest -q tests\test_tasks_service.py tests\test_tasks_api.py` -> `7 passed`

### 2026-06-14 - Phase 2 slice 1 claim-family and strength spread implemented

- Expanded provider-backed claim construction beyond the old single
  `claim_policy_primary` baseline:
  - location-sensitive queries now also emit `claim_local_rollout`
  - runs with statistics/data evidence now emit `claim_statistics_corroboration`
  - existing procurement and disclosure claims remain additive
- Added internal `claim_family` labeling to provider-backed claims so later
  report-writing and prompt/context slices can distinguish policy basis, local
  rollout, procurement, disclosure, and statistics corroboration.
- Reworked provider-backed `_support_strength` so background evidence is no
  longer hard-clamped into the old `0.68` ceiling:
  - freshness now contributes to strength
  - formal policy roles and `primary_support` usage can score above the old cap
  - direct support still remains stronger than high-quality background support
- Added focused tests that pin the two Phase 2 root problems directly:
  - multi-claim output for location/statistics cases
  - non-flat background support-strength spread

Validation:

- `python -m py_compile packages\research_harness\real_nodes.py tests\test_research_harness_graph.py` -> pass
- `python -m ruff check packages\research_harness\real_nodes.py tests\test_research_harness_graph.py` -> pass
- `pytest -q tests\test_research_harness_graph.py -k "local_and_statistics_claims or flat_background_cap"` -> `2 passed`
- `pytest -q tests\test_research_harness_graph.py` -> `22 passed`
- `pytest -q tests\test_research_api.py` -> `10 passed`
- `pytest -q tests\test_research_provider_integration.py` -> `9 passed`
- `pytest -q tests\test_deepseek_provider.py` -> `4 passed`

### 2026-06-14 - Phase 2 slice 2 verifier/gate guidance refined

- Refined provider-backed review/gate guidance so richer claims now produce
  more specific evidence-acquisition instructions instead of falling back to
  generic claim IDs or bare source-family notes.
- `editor2_review_provider_backed` now emits data-oriented suggested queries
  for `claim_statistics_corroboration`, rather than only echoing the original
  query.
- `chief_gate_provider_backed` additive `ADD_EVIDENCE` actions now carry
  `suggested_search_queries`, so downstream API/UI/human-review consumers can
  reuse the same targeted search hints.
- Added location-aware search hints for `claim_local_rollout`, so local-policy
  or local-project claims surface concrete locality-sensitive search phrases.
- Extended the structured gate action contract with additive
  `RequiredAction.suggested_search_queries`, keeping existing response shapes
  backward-compatible while making action payloads more useful.

Validation:

- `python -m py_compile packages\research_harness\contracts.py packages\research_harness\real_nodes.py tests\test_research_harness_graph.py` -> pass
- `python -m ruff check packages\research_harness\contracts.py packages\research_harness\real_nodes.py tests\test_research_harness_graph.py` -> pass
- `pytest -q tests\test_research_harness_graph.py -k "statistics_claim_suggests_data_queries or local_claim_action_carries_location_queries"` -> `2 passed`
- `pytest -q tests\test_research_harness_graph.py` -> `24 passed`
- `pytest -q tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py` -> `23 passed`

### 2026-06-14 - Phase 3 slice 1 readable report contract implemented

- Upgraded `finalize_report_provider_backed` from a JSON-only preview into a
  readable report contract that now emits:
  - `sections`
  - `report_markdown`
  - claim-linked readable section bodies for executive summary, key claims,
    evidence/limitations, and review status
- Preserved backward compatibility by keeping the existing preview/artifact
  envelope and adding readable fields inside it rather than replacing the old
  report object outright.
- Added deterministic readable-report composition so the graph can produce
  a claim-led report body even when tool-mediated composition is thin.
- Tightened the evidence section to prefer source titles plus shortened
  excerpts, and added conservative suppression for obvious web-navigation /
  PDF-token noise markers before they reach the report body.
- Real local-case smoke confirmed the new readable report fields now land in
  the saved response artifact:
  - `data/tmp/langgraph_readable_report_s03_v3/response.json`
  - sections include `Executive Summary`, `Key Claims`,
    `Evidence And Limitations`, and `Review Status`
  - `claim_local_rollout` and `claim_statistics_corroboration` both appear in
    the readable report body for the `S03`-style local case
- Disclosure-heavy readable-report smoke also passed and persisted readable
  report fields:
  - `data/tmp/langgraph_readable_report_disclosure_v1/response.json`
  - `claim_company_disclosure` appears in the readable `Key Claims` section
  - `obl_company_disclosure` remained covered in the live gate result
- Remaining readable-report risk from live artifacts:
  even after source-title-first cleanup, some evidence excerpts still leak
  aggregator/PDF body noise when the extracted summary itself is low quality.
  This is now a concrete next-step cleanup target rather than a vague report
  problem.

Validation:

- `python -m py_compile packages\research_harness\real_nodes.py tests\test_research_harness_graph.py` -> pass
- `python -m ruff check packages\research_harness\real_nodes.py tests\test_research_harness_graph.py tests\test_research_run_dossier.py` -> pass
- `pytest -q tests\test_research_harness_graph.py -k "builds_readable_markdown or provider_backed_uses_search_provider"` -> `2 passed`
- `pytest -q tests\test_research_harness_graph.py` -> `25 passed`
- `pytest -q tests\test_research_api.py tests\test_research_run_dossier.py` -> `14 passed`
- `python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\langgraph_readable_report_s03_v3 --query "2025年合肥低空经济地方政策项目公示官方来源" --max-rounds 2 --max-loop-count 1` -> `status=succeeded`, `decision=PASS`
- `python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\langgraph_readable_report_disclosure_v1 --query "2025年低空经济上市公司年报披露与官方政策证据" --max-rounds 2 --max-loop-count 1` -> `status=succeeded`, `decision=PASS`

### 2026-06-14 - Phase 3 slice 2 readable-report noise cleanup refined

- Extended readable-report cleanup rules for two additional live noise classes:
  - `index.shtml` / breadcrumb-style navigation fragments
  - annual-report / investor-record boilerplate such as `公司代码` /
    `证券代码` / `投资者关系活动记录表`
- Added source-title cleaning so content-farm titles such as
  `轻松关闭推送，静享搜狐新闻时光` and `速成手册：新手攻略全解析` no longer
  surface directly in readable report evidence lines.
- Added TOC-style excerpt suppression for `目录` / `文件汇编` / gazette-like
  fragments.
- Disclosure readable-report smoke improved materially:
  - `data/tmp/langgraph_readable_report_disclosure_v5/response.json`
  - `claim_company_disclosure` evidence lines now keep compact report titles
    instead of raw `证券代码` / activity boilerplate
  - `claim_statistics_corroboration` no longer leaks `zwgklogo` or
    `index.shtml` navigation fragments into the report body

Validation:

- `pytest -q tests\test_research_harness_graph.py -k "index_shtml_navigation_and_report_boilerplate or investor_record_and_logo_navigation_noise or content_farm_titles or table_of_contents_style_pdf_text"` -> pass
- `python -m ruff check packages\research_harness\real_nodes.py tests\test_research_harness_graph.py` -> pass
- `pytest -q tests\test_research_harness_graph.py` -> `31 passed`
- `pytest -q tests\test_research_api.py tests\test_research_run_dossier.py` -> `14 passed`
- `python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\langgraph_readable_report_disclosure_v5 --query "2025年低空经济上市公司年报披露与官方政策证据" --max-rounds 2 --max-loop-count 1` -> `status=succeeded`, `decision=PASS`

### 2026-06-14 - Phase 4 slice 1 prompt/context registry implemented

- Added explicit prompt/context asset registry:
  - `packages/research_harness/prompt_assets.py`
- Registry now covers every runtime node for both:
  - `shadow_langgraph_v1`
  - `provider_backed_v1`
- `context.py` no longer owns a private pair of prompt-version maps; runtime
  prompt-version lookup now resolves through the explicit registry instead.
- Provider-backed `human_review` and `finalize_report` now have explicit
  prompt-version entries instead of relying on implicit fallback behavior.

Validation:

- `pytest -q tests\test_research_harness_prompt_assets.py` -> `2 passed`
- `python -m py_compile packages\research_harness\prompt_assets.py packages\research_harness\context.py tests\test_research_harness_prompt_assets.py` -> pass
- `python -m ruff check packages\research_harness\prompt_assets.py packages\research_harness\context.py tests\test_research_harness_prompt_assets.py` -> pass
- `pytest -q tests\test_research_harness_graph.py -k "prompt_version or provider_backed_uses_search_provider"` -> pass
- `pytest -q tests\test_research_harness_graph.py` -> `31 passed`
- `pytest -q tests\test_research_api.py tests\test_research_run_dossier.py` -> `14 passed`

### 2026-06-14 - Phase 4 slice 2 prompt/context contract metadata expanded

- Expanded the prompt/context registry from prompt-version inventory into a
  fuller node contract surface:
  - `context_budget_tokens`
  - `tool_permissions`
  - `fallback_usage_review`
- `context pack` metadata now carries these contract fields at runtime, so the
  graph records not only which prompt version was used, but also:
  - how much context that node is expected to carry
  - which tools the node is explicitly allowed to use
  - what kind of fallback behavior should be reviewed in live validation
- This remains additive and backward-compatible:
  existing graph responses keep their old fields, and the new context metadata
  is attached as extra observability rather than replacing any public contract.

Validation:

- `pytest -q tests\test_research_harness_prompt_assets.py` -> `2 passed`
- `python -m py_compile packages\research_harness\prompt_assets.py packages\research_harness\context.py packages\research_harness\schemas.py tests\test_research_harness_prompt_assets.py` -> pass
- `python -m ruff check packages\research_harness\prompt_assets.py packages\research_harness\context.py packages\research_harness\schemas.py tests\test_research_harness_prompt_assets.py` -> pass
- `pytest -q tests\test_research_harness_graph.py` -> `31 passed`
- `pytest -q tests\test_research_api.py tests\test_research_run_dossier.py` -> `14 passed`

### 2026-06-14 - Readable report evidence display priority tightened again

- Added explicit source-label degradation rules on top of raw title/excerpt
  cleaning:
  - `official_policy_original + supporting_evidence_candidate` article/news or
    compilation-like titles can now degrade to `政策支持类来源`
  - `statistics_or_data_release` gazette-like titles can now degrade to
    `统计口径或分类通知`
  - `company_disclosure` non-report disclosure materials such as investor
    records or bond issuance result notices can now degrade to
    `公司披露补充材料`
- When a source has already been downgraded to one of these generic display
  labels, the report now suppresses the excerpt instead of appending noisy text
  after the generic label.
- Real disclosure readable-report smoke improved again:
  - `data/tmp/langgraph_readable_report_disclosure_v10/response.json`
  - policy claim evidence lines now show `政策支持类来源`
  - statistics claim evidence lines now show `统计口径或分类通知`
  - remaining disclosure noise is now narrower and concentrated in a smaller
    set of report-like materials

Validation:

- `pytest -q tests\test_research_harness_graph.py -k "choose_report_source_label or omits_noisy_excerpt_when_label_is_generic"` -> pass
- `python -m ruff check packages\research_harness\real_nodes.py tests\test_research_harness_graph.py` -> pass
- `python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\langgraph_readable_report_disclosure_v10 --query "2025年低空经济上市公司年报披露与官方政策证据" --max-rounds 2 --max-loop-count 1` -> `status=succeeded`, `decision=PASS`

### 2026-06-14 - Phase 5 real-case validation loop completed

- Re-ran the three required real-case validation shapes on the redesigned
  graph-v1 path:
  - local `S03`-style case:
    `data/tmp/langgraph_readable_report_s03_v3/response.json`
  - disclosure-heavy case:
    `data/tmp/langgraph_readable_report_disclosure_v10/response.json`
  - procurement/policy case:
    `data/tmp/langgraph_readable_report_procurement_v1/response.json`
- Practical result:
  - all three real cases now finish `status=succeeded`
  - all three finish `decision=PASS`
  - all three persist readable report sections:
    `executive_summary`, `key_claims`, `evidence_and_limitations`,
    `review_status`
- Concrete before/after improvements confirmed from the preserved baseline:
  - `S03` local case before:
    `HUMAN_REVIEW`, one coarse claim, flat `0.68` support strength cluster,
    JSON-heavy final output
  - `S03` local case after:
    `PASS`, three auditable claims, visible strength spread, readable report
    sections persisted
  - disclosure-heavy case before:
    earlier validation either failed at `collect_sources` timeout or
    over-simplified disclosure handling
  - disclosure-heavy case after:
    `PASS`, `claim_company_disclosure` is explicit, readable report includes
    disclosure claim coverage, and disclosure obligation stays covered
  - procurement/policy case before:
    promotion-gate baseline was the main safety reference
  - procurement/policy case after:
    `PASS`, readable report keeps both policy and procurement-oriented claim
    coverage without regression on obligation coverage

Validation:

- `python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\langgraph_readable_report_s03_v3 --query "2025年合肥低空经济地方政策项目公示官方来源" --max-rounds 2 --max-loop-count 1` -> `status=succeeded`, `decision=PASS`
- `python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\langgraph_readable_report_disclosure_v10 --query "2025年低空经济上市公司年报披露与官方政策证据" --max-rounds 2 --max-loop-count 1` -> `status=succeeded`, `decision=PASS`
- `python scripts\graph_provider_backed_smoke.py --reset --output-dir data\tmp\langgraph_readable_report_procurement_v1 --query "2025年低空经济政策与公共资源采购中标证据 官方来源" --max-rounds 2 --max-loop-count 1` -> `status=succeeded`, `decision=PASS`

## Implementation Sequence

When implementation starts, follow this order:

1. `human_review` contract design and interruption boundary
2. state/schema additions needed for pending human review
3. claim-family redesign in provider-backed build/evidence/verify path
4. readable report contract and finalize-report rewrite
5. prompt/context asset extraction and versioning
6. real-case validation rerun

## File Targets

Likely primary implementation files:

- `packages/research_harness/nodes.py`
- `packages/research_harness/real_nodes.py`
- `packages/research_harness/runner.py`
- `packages/research_harness/state.py`
- `packages/research_harness/schemas.py`
- `packages/research_reports/dossier.py`
- `apps/api/routes/deep_research.py`
- `packages/tasks/**` only if pending-human-review requires task-state exposure
- `tests/test_research_harness_graph.py`
- `tests/test_research_api.py`
- new prompt/context asset files once the structure is chosen

Likely non-code artifacts:

- `.agent/HANDOFFS/langgraph-human-loop-claim-report-quality-handoff-20260614.md`
- `docs/technical-roadmap-evolution.md`

## Next Action

Start Phase 2 with the smallest provider-backed quality slice:

Plan completed. If work resumes later, the next logical follow-up is a new plan
focused on:

1. further readable-report evidence presentation polish for niche disclosure
   materials
2. deeper prompt/context contract governance beyond the current registry slice
3. deciding whether graph-v1 should remain opt-in or graduate further
