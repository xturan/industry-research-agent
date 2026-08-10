# AnySearch Production Discovery Integration v1

Status: completed
Created: 2026-07-15
Execution mode: full_subagent
Primary area: provider_layer
Secondary areas: source_layer, domestic_source_collectors, research_workflow, eval_policy_ops

## Objective

Switch the default discovery provider from Tavily to AnySearch while keeping Tavily as an explicit, configurable fallback. Cover research graph, search-assisted domestic, direct structured fallback, and legacy deep-research paths without changing EvidenceBundle, citations, research response contracts, or task/run semantics.

## Task Classification

- Primary area: provider_layer
- Secondary areas: source_layer, domestic_source_collectors, research_workflow, eval_policy_ops
- Request type: planning-only M1 director gate
- Allowed edits in this step: active PLAN and `.agent/STATUS.md` only
- Explicitly out of scope in this step: production code, tests, docs, env files, provider keys

## Decision Basis

- Prior 8-case AnySearch/Tavily comparison is already available and should be reused as the evidence baseline.
- AnySearch showed stronger retrieval on enterprise disclosure, procurement/tender, and environment/land queries; project-landing cases require explicit validation because Tavily had some localized strength.
- AnySearch general and vertical search can improve discovery, but discovery results do not replace extraction or citation verification.
- Crawl4AI and existing detail-fetch/extraction paths remain responsible for verified downstream extraction.

## Compatibility Points

| Concern | Current state | Required adaptation |
|---|---|---|
| Request contract | Tavily-named request used across modules | Provider-neutral request; Tavily aliases retained |
| Result contract | URL/title/content/raw_content/score/date | Preserve fields; add provider/route metadata additively |
| Provider construction | Direct Tavily constructors | Central factory; default AnySearch |
| Domain filters | Native Tavily include/exclude | AnySearch query augmentation plus post-filtering |
| Vertical search | Tavily topic routing | Optional AnySearch vertical params when identifiers are validated |
| Cost accounting | `estimated_tavily_credits` embedded | Preserve compatibility; add neutral usage metadata |
| Source family | Target/observed can be confused | Keep target separate; infer observed from result only |
| Original content | Tavily raw content optional | Retain AnySearch Markdown as discovery-only content |
| Failure handling | Key rotation/ToolError | Anonymous/key modes, structured fallback trace |

## Scope

- Add provider-neutral discovery models and a central factory.
- Add AnySearch discovery adapter using the official JSON-RPC call pattern.
- Parse and retain title, URL, and Markdown body as discovery content.
- Add optional finance announcement vertical routing for validated A-share identifiers only.
- Switch default provider to AnySearch by configuration.
- Keep Tavily aliases/adapters backward compatible.
- Route graph, domestic, direct-lane, and legacy defaults through the factory.
- Preserve target-vs-observed source-family separation.
- Add provider/fallback/auth/route diagnostics.
- Update technical roadmap and handoff at completion.

## Non-Goals

- No EvidenceBundle, citation, final-report, task/job, dossier, or run-step schema changes.
- No removal of Tavily code, keys, or compatibility aliases.
- General search does not replace direct structured adapters.
- No 50-query-specific hard-coded retrieval rules.
- No replacement of Crawl4AI.

## Configuration

SEARCH_DISCOVERY_PROVIDER=anysearch
SEARCH_DISCOVERY_FALLBACK_PROVIDER=tavily
SEARCH_DISCOVERY_FALLBACK_ENABLED=true
ANYSEARCH_API_KEY=__OPTIONAL_ANYSEARCH_API_KEY__
ANYSEARCH_ENDPOINT=https://api.anysearch.com/mcp
ANYSEARCH_TIMEOUT_SECONDS=30
ANYSEARCH_MAX_RESULTS=5

Anonymous access is allowed. Secrets must not enter PLAN artifacts or logs.

## Protected Contracts

- EvidenceBundle and EvidenceItem citations unchanged.
- `source_quality_summary` and research responses unchanged.
- `estimated_tavily_credits` consumers remain readable.
- Task/job/run semantics unchanged.
- Dossier/final-report persistence contract unchanged.
- Target family never overwrites observed source family.

## Protected-Contract Gates

### Gate P1: Research Output Contract Freeze
- M2-M5 must not change `EvidenceBundle`, `EvidenceItem`, `source_quality_summary`, `/research/analyze`, `/deep-research/analyze`, final-report envelope, or dossier persistence shape.
- If AnySearch integration appears to require a public response-field change, stop and revise the PLAN before implementation.

### Gate P2: Discovery Metadata Is Additive-Only
- Provider, fallback, auth-mode, route, vertical, usage, and observed-family diagnostics must be internal/additive.
- Existing Tavily-shaped fields remain readable until a later compatibility-removal PLAN authorizes cleanup.

### Gate P3: Source-Family Separation
- `target_source_family` remains a requirement signal.
- `observed_source_family` must continue to be inferred from returned source evidence only.
- A target-family hint must never upgrade source quality, source tier, or citation strength by itself.

### Gate P4: Discovery vs Extraction Boundary
- AnySearch Markdown body may be stored as discovery content for inspection and debugging.
- It must not be represented as verified extraction, crawl result, or original-source fulltext unless the existing extraction path independently verifies it.

### Gate P5: Fallback Transparency
- AnySearch -> Tavily fallback must be explicit, observable, and disableable by config.
- Silent provider switching is not allowed.

## Agent Execution Contract

- Group 1 `invest_project_director`: owns M1 scope freeze, real-world validation design, protected-contract gates, worker assignment, and phase advancement decisions.
- Group 2 `invest_agent_architecture_builder`: owns constructor inventory, neutral contract design, provider-factory cutover plan, fallback semantics, and module-level ownership boundaries. No production code without M1 approval.
- Group 2 `invest_feature_programmer`: owns M2-M4 implementation only after M1 approval, limited to provider-neutral discovery contract, AnySearch adapter, factory wiring, diagnostics, and guardrails authorized by this PLAN.
- Group 3 `invest_code_quality_checker`: owns targeted Ruff, compile, and focused pytest gates for changed modules in M2-M5.
- Group 3 `invest_functional_validator`: owns real-world live/provider validation, artifact inspection, fallback drill, target-vs-observed family audit, and bounded dossier/final-report validation.
- Workers must not reinterpret the default-switch objective, expand scope into unrelated report-generation redesign, or change protected contracts without director re-approval in this PLAN.

## Milestones

### M1 Architecture Gate
- Inventory constructors and consumers.
- Freeze neutral model/alias strategy.
- Define domain-filter, vertical, auth-mode, and fallback semantics.
- Write module ownership and validation ownership before M2 starts.
- Director and architecture worker approve.

### M2 Provider-Neutral Contract and AnySearch Adapter
- Add neutral models and Tavily aliases.
- Implement JSON-RPC transport, Markdown parsing, auth handling, and structured errors.
- Add central factory with AnySearch default and Tavily fallback.
- Test parsing, post-filtering, vertical routing, redaction, and fallback.

### M3 Production Wiring
- Replace default Tavily construction in graph, domestic, and direct-lane paths.
- Update legacy deep-research shared-boundary calls.
- Keep fake provider injection compatible.
- Record provider, route, fallback reason, and counts.

### M4 Source-Quality and Extraction Guardrails
- Infer observed family from URL/title/content without mutating target family.
- Mark AnySearch body as discovery content, not verified extraction.
- Prevent source-quality or media upgrades caused only by target family.

### M5 Validation and Live Gate
- Run source, domestic, provider, and research-contract tests.
- Live test project landing, enterprise disclosure, procurement/tender, and environment/land cases.
- Inspect original-content and source-quality artifacts.
- Audit target-vs-observed source-family separation.
- Run one bounded dossier/final-report flow.
- Verify controlled AnySearch failure to Tavily fallback.

### M6 Documentation and Completion
- Update `docs/technical-roadmap-evolution.md`.
- Update PLAN/STATUS, archive, and report before/after examples.

## Real-World Validation Plan

### RW1 Project Landing Discovery
- Goal: verify AnySearch default discovery can surface project-landing style results without degrading source-family handling.
- Scope: collect/search path only; no extraction-contract change.
- Pass signal: usable landing/project results appear with explicit provider metadata and no source-family overwrite.

### RW2 Enterprise Disclosure
- Goal: verify enterprise disclosure search still prefers disclosure-grade results when query intent targets listed-company announcements.
- Scope: finance vertical routing only when validated identifiers exist; otherwise general search plus observed-family inference.
- Pass signal: disclosure-oriented results remain auditable and do not depend on target-family self-upgrade.

### RW3 Procurement / Tender
- Goal: verify public procurement and tender discovery remains strong under AnySearch default with Tavily fallback available.
- Scope: general search, domain-filter semantics, and observed-family inference.
- Pass signal: procurement-style results remain reachable and source-family traces show why they qualified.

### RW4 Environment / Land
- Goal: verify environment/land evidence discovery still reaches official or structured public-resource material where available.
- Scope: general search plus post-filtering and source-quality linkage.
- Pass signal: environment/land queries preserve usable public-resource discovery or expose transparent gaps/fallback.

### RW5 Original-Content Inspection
- Goal: verify AnySearch Markdown body is preserved for inspection while staying separate from verified extraction.
- Required artifact checks: title, URL, Markdown preview/body, provider, auth mode, fallback trace.
- Pass signal: discovery content is inspectable and clearly labeled as discovery-only content.

### RW6 Source-Quality Linkage
- Goal: verify source-quality assessment still links to observed source evidence rather than provider name or target-family hint.
- Required artifact checks: `source_quality_summary`, source tier/role/credibility fields, downgrade reasons when sources are weak or mismatched.
- Pass signal: source quality remains attributable to observed evidence and can explain insufficiency.

### RW7 Target-vs-Observed Source-Family Separation
- Goal: verify requirement-side family targeting remains separate from result-side observed family classification.
- Required artifact checks: target family, observed family, mismatch reason, not-sufficient markers, per-search diagnostics.
- Pass signal: mismatched sources may be retained with transparent insufficiency, but never silently promoted to match the target family.

### RW8 Bounded Dossier / Final-Report Run
- Goal: run one bounded end-to-end dossier/final-report flow after M3-M4 to prove the default-provider switch does not break report-generation contracts.
- Bound: single controlled query, limited rounds/loops, explicit artifact directory, no schema changes.
- Required artifact checks: dossier generation, final report generation, provider/fallback trace, citation readability, no protected-contract regression.
- Pass signal: run completes or fails transparently for provider reasons without contract drift.

## M1 Deliverables

- Constructor/consumer inventory covering graph, search-assisted domestic, direct structured fallback, and legacy deep-research entrypoints.
- Neutral request/result contract strategy with Tavily alias compatibility notes.
- Fallback/auth/vertical/domain-filter semantics frozen in PLAN text.
- Real-world validation matrix and protected-contract gates approved.
- Group 2 and Group 3 ownership assigned by module and milestone.

## Worker Assignments

### Group 2
- `invest_agent_architecture_builder`
  - M1 owner.
  - File/module ownership for design work: `packages/sources/*`, `packages/research_harness/*`, `packages/agents/*`, domestic source collector integration touchpoints, and legacy deep-research discovery constructors.
  - Deliverables: constructor inventory, neutral contract blueprint, fallback decision tree, vertical-routing policy, and module write boundaries for M2-M4.
- `invest_feature_programmer`
  - M2-M4 owner after M1 approval.
  - Expected implementation ownership: provider-neutral discovery contract, AnySearch adapter/transport, central factory, production wiring, diagnostics, source-quality guardrails, and focused tests for those modules.
  - Must not change report/evidence/citation/task contracts.

### Group 3
- `invest_code_quality_checker`
  - Validation ownership: targeted `ruff`, `py_compile`, and focused `pytest` for changed discovery/provider/research modules.
  - Must confirm compatibility for fake providers and Tavily-shaped imports/fields that remain supported.
- `invest_functional_validator`
  - Validation ownership: RW1-RW8 live/manual checks, fallback drill, original-content inspection, source-quality linkage audit, target-vs-observed family audit, and one bounded dossier/final-report run.
  - Must record whether AnySearch success, transparent gap, or Tavily fallback produced the observable outcome.

## Validation Commands

- `python -m ruff check packages/sources packages/research_harness packages/agents tests`
- `python -m py_compile packages/sources/search_discovery.py`
- `pytest -q tests/test_sources_search_discovery.py`
- `pytest -q tests/test_sources_search_assisted_domestic.py tests/test_sources_lane_execution.py`
- `pytest -q tests/test_research_harness_graph.py tests/test_agents_workflow.py`

Mandatory gates: `source-regression-check`, `domestic-source-check`, `research-contract-check`.

## Acceptance Criteria

- Default factory returns AnySearch.
- AnySearch body is inspectable and not mislabeled as Crawl4AI or verified extraction.
- Tavily fallback is explicit and disableable.
- Existing fake providers and Tavily imports remain compatible.
- Project landing, enterprise disclosure, procurement/tender, and environment/land cases yield usable results or transparent gaps/fallback.
- Source-quality linkage remains attributable to observed evidence.
- Target and observed source family remain distinct.
- No protected-contract regression.

## Continue / Done Conditions

### M1 Continue Conditions
- M1 may advance to M2 only when the director confirms:
  - constructor inventory covers graph, domestic, direct-lane, and legacy deep-research discovery call sites;
  - neutral request/result contract strategy is frozen;
  - protected-contract gates P1-P5 are explicit;
  - RW1-RW8 validation cases and pass signals are written into the PLAN;
  - Group 2 and Group 3 ownership is explicit.

### M1 Done Condition
- M1 is done when the PLAN alone is specific enough that a Group 2 worker can implement the default-provider switch without re-deciding contracts, validation scope, or fallback semantics.

### PLAN Done Condition
- This PLAN is done only when:
  - AnySearch is the default discovery provider in authorized paths;
  - Tavily fallback remains explicit, configurable, and validated;
  - RW1-RW8 have been executed with recorded outcomes;
  - one bounded dossier/final-report run completes without protected-contract drift;
  - required code-quality and functional validation pass;
  - PLAN and STATUS are updated and the PLAN can be archived safely.

## Rollback

- Set `SEARCH_DISCOVERY_PROVIDER=tavily`.
- Keep Tavily adapter, aliases, and keys for one release cycle.
- Restore Tavily default without reverting source-quality or evidence-linked guardrails that are otherwise valid.

## Stop Conditions

- A protected contract needs a breaking change.
- AnySearch requires unavailable mandatory credentials.
- Family-level live results regress with no safe fallback.
- Validation repeatedly fails without a narrow fix.
- The next step would blur discovery content with verified extraction.

## Continue Rule

After each milestone, update Progress and STATUS, then continue automatically unless a Stop Condition is met.

## Progress

- [x] Prior AnySearch/Tavily comparison reused.
- [x] Initial call-site inventory completed.
- [x] M1 real-world validation matrix refined for project landing, enterprise disclosure, procurement/tender, environment/land, original-content inspection, source-quality linkage, target-vs-observed source-family separation, and one bounded dossier/final-report run.
- [x] M1 protected-contract gates and worker assignments refined.
- [x] M1 architecture gate approved by director plus architecture worker.
- [x] M2 provider-neutral contract, AnySearch adapter, parser, post-filter, and explicit fallback implemented.
- [x] M3 production constructors switched to the central discovery factory; AnySearch is the default and Tavily is configurable fallback.
- [x] M4 provider/content-origin diagnostics and source-quality linkage guardrails completed.
- [x] M5 completed: RW1-RW7 passed and RW8 produced direct P04/K12 dossier/final-report artifacts after persistence remediation.
- [x] M6 documentation and archival completed.

## Implementation And Validation Snapshot

### Implemented Capability

- Added an AnySearch JSON-RPC discovery adapter with anonymous/keyed access, vertical routing, inspectable original search content, domain post-filtering, and structured errors.
- Added a provider-neutral discovery factory. Default: `AnySearch`; fallback: `Tavily`; fallback can be disabled and direct Tavily remains supported for rollback.
- Rewired search-assisted domestic collection, lane execution, deep research, and real LangGraph nodes through the factory without changing EvidenceBundle, citation, report, or task contracts.
- Added diagnostics for provider attempted/used, fallback state, route, content origin, and filtering counts.

### Validation Results

- Target Ruff and `py_compile`: passed.
- Discovery tests: `13 passed`.
- Search-assisted domestic and lane execution tests: `101 passed`.
- Provider-backed collection tests: `2 passed`.
- Mandatory source/domestic regression gates: `45 passed`.
- Mandatory research-contract gates: `24 passed`.
- Live RW1-RW7: AnySearch returned inspectable original content; source-quality evaluation correctly promoted official evidence and downgraded aggregators/context sources.
- Full repository Ruff remains noisy because of unrelated existing generated/worktree files; all changed target files pass.

### RW8 Resolution

The pre-existing dossier/report persistence gap was restored in the child PLAN `report-final-artifact-persistence-remediation-v1`. Bounded P04 and K12 runs both completed through the AnySearch-first graph path and directly produced dossier, response, summary, and final-report artifacts without recovery.

## Risks

- Markdown parser drift must fail transparently.
- Anonymous limits may be insufficient for batch traffic.
- Domain filtering lacks exact native parity.
- Legacy credit naming remains temporarily misleading.
- Provider-wide replacement can hide family regressions.
- Finance vertical routing can overfit disclosure cases if identifier validation is weak.
- Discovery-content retention can be misread as extraction truth unless labels remain strict.
- Default-switch success in search-only tests may still mask dossier/final-report integration regressions; RW8 remains mandatory.

## Next Action

Archive this PLAN. Retain `SEARCH_DISCOVERY_PROVIDER=tavily` as rollback and address regional parsing, citation visibility, and context-pack budgets in separate quality work.
