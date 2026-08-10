# Evidence Eligibility + Source Quality v1

Status: active_phase4_completed_phase5_live_timeout

Created: 2026-06-25

Primary active PLAN: yes

Parent / reference PLAN:
- `.agent/PLANS/goal-driven-evidence-react-v1.md`

## Objective

Build a unified evidence eligibility layer that connects:

```text
source_family
  -> source_quality_v2
  -> evidence_type / evidence_quality_v2
  -> claim_support_eligibility
  -> chief_gate / final_report
```

The practical goal is to prevent weak or wrong-type evidence from supporting
strong claims. A source should not merely be "found"; it must be the right
source family, have sufficient source quality, produce an evidence item with
the right proof type, and be eligible for the target claim.

This task directly addresses the full final-report live test result from
2026-06-24:

- The full graph reached `final_report`.
- It required auto-approval over an initial `HUMAN_REVIEW` gate.
- The gate found source-family mismatches:
  - `official_policy` claims were supported by `official_news`.
  - `statistics` claims were supported by `company_disclosure`.
- The source quality system exists in `packages/sources/source_quality.py`, but
  the current `research_harness` full graph does not fully use it during
  source collection, evidence scoring, or claim eligibility.

## Task Classification

Primary area: `research_workflow`

Secondary areas:
- `source_layer`
- `eval_policy_ops`
- `provider_layer`

Protected contracts:
- Do not change public `/deep-research/analyze` or `/research/analyze` response
  shape without explicit authorization.
- Do not change `EvidenceBundle` schema or `EvidenceItem.citation` fields.
- New eligibility, source-quality, and evidence-quality fields must be metadata
  additions or internal graph-state additions unless a later phase explicitly
  authorizes a contract migration.

## Scope

In scope:
- Reuse `packages.sources.source_quality.assess_source_quality_v2()` in the
  `research_harness` graph source collection path.
- Add an internal `evidence_quality_v2` model or metadata structure for graph
  evidence items.
- Define an evidence eligibility matrix that combines:
  - required source family
  - actual source family
  - source quality / usage role
  - evidence type
  - proof strength
  - claim type / required evidence type
- Update claim verification and chief gate logic to use eligibility instead of
  raw family equality alone.
- Improve dossier / final-report observability so users can see why evidence
  was accepted, downgraded, or rejected.
- Add focused tests and one small live validation loop.

Out of scope:
- Large source expansion.
- New direct structured adapters.
- Database schema migrations unless a later phase explicitly approves them.
- Browser automation, OCR, or unrelated Crawl4AI changes.
- Full 50-query live run.

## Design Direction

### Core Concepts

`source_family` answers:

```text
What type of source is this?
```

Examples: `official_policy`, `official_news`, `statistics`,
`company_disclosure`, `public_resource_transaction`, `environmental_land`.

`source_quality_v2` answers:

```text
How trustworthy, auditable, fresh, and query-relevant is this source?
```

Existing implementation exists in `packages/sources/source_quality.py` and
should be reused instead of rewritten.

`evidence_type` answers:

```text
What does this extracted evidence actually prove?
```

Examples:
- `policy_original`
- `policy_signal`
- `procurement_award`
- `project_approval`
- `statistics_metric`
- `company_disclosure_statement`
- `media_context`

`proof_strength` answers:

```text
How strong is the proof for a claim?
```

Suggested values:
- `strong`
- `medium`
- `weak`
- `context_only`
- `ineligible`

`claim_support_eligibility` answers:

```text
Can this evidence support this specific claim?
```

### Target Data Flow

```text
collect_sources_provider_backed
  -> infer source_family
  -> assess_source_quality_v2
  -> source.source_quality_v2

parse_sources / build_evidence
  -> infer evidence_type
  -> inherit source_quality_v2
  -> compute evidence_quality_v2

build_claims / verify_claims
  -> compare claim requirements with evidence eligibility
  -> produce eligible / downgraded / rejected support decisions

chief_gate
  -> block or downgrade when key claims lack eligible evidence

final_report / dossier
  -> expose evidence type, source quality, proof strength, and mismatch reasons
```

### Evidence Quality Formula

Use weighted scoring plus hard gates.

Suggested score:

```text
evidence_quality_score =
  source_credibility_score * 0.40
  + claim_relevance * 0.25
  + evidence_specificity * 0.20
  + citation_integrity * 0.15
```

Hard gates:

- If `source_quality_v2.usage_role == "context_only"`, evidence cannot be
  primary support.
- If `source_family == "official_news"` and `evidence_type == "policy_signal"`,
  it cannot satisfy a `policy_original` requirement.
- If `source_family == "company_disclosure"`, it cannot satisfy a `statistics`
  requirement unless the claim is explicitly about that company's disclosure.
- If citation integrity is insufficient, evidence cannot support a key claim.
- If source freshness is incompatible with the query time horizon, downgrade
  proof strength.

## Initial Eligibility Matrix

| Claim need | Required source families | Required evidence types | Min source quality | Allowed role |
|---|---|---|---|---|
| Formal policy exists | `official_policy` | `policy_original`, `implementation_plan`, `formal_notice` | B | primary/supporting |
| Policy signal / direction | `official_policy`, `official_news` | `policy_signal`, `official_interpretation` | B | supporting |
| Project rollout | `public_resource_transaction`, `environmental_land`, `official_policy` | `procurement_award`, `project_approval`, `implementation_plan` | B | primary/supporting |
| Statistics / scale | `statistics`, `industry_research` | `statistics_metric`, `official_data_release`, `industry_metric` | B | primary/supporting |
| Company participation | `company_disclosure` | `annual_report_statement`, `announcement`, `ir_disclosure` | B | primary/supporting |
| Background context | any non-spam source | `media_context`, `expert_view`, `background_signal` | C | context only |

## Agent Execution Contract

Default execution mode: `remediation_gate`.

Reason:
- The full live gate failed / required human review, but the product goal is
  unchanged.
- The work touches research workflow and source quality, but should be
  implementable as a bounded remediation without full subagent orchestration.

If implementation expands into protected public response contracts, escalate to
`full_subagent`.

Role binding if subagents are used:
- `invest_project_director`: confirm the PLAN remains bounded and no protected
  contract is changed silently.
- `invest_feature_programmer`: implement source-quality reuse, evidence-quality
  metadata, and eligibility checks.
- `invest_code_quality_checker`: run ruff, py_compile, and focused pytest.
- `invest_functional_validator`: run the narrow source/evidence eligibility
  validation and one full final-report smoke.
- `invest_project_summarizer`: only after Done Condition is reached.

## Phases

### Phase 0: Plan Freeze and Baseline Audit

Status: completed

Objective:
- Freeze the implementation contract.
- Confirm current code paths and baseline artifacts.

Tasks:
- Record this PLAN as the active remediation task.
- Identify exact insertion points:
  - `collect_sources_provider_backed`
  - `build_evidence_provider_backed` or graph evidence construction path
  - `verify_claims_provider_backed`
  - `editor2_review_provider_backed`
  - `chief_gate`
  - dossier/final-report source notes
- Use the 2026-06-24 full report as baseline:
  `data/tmp/full_final_report_hefei_phase2_5`.

Acceptance criteria:
- PLAN and STATUS are updated.
- No production code changes yet.
- Next implementation slice is unambiguous.

Validation:
```powershell
Test-Path .agent\PLANS\evidence-eligibility-source-quality-v1.md
Get-Content .agent\STATUS.md
```

### Phase 1: Source Quality Reuse in Research Graph

Status: completed

Objective:
- Ensure graph sources carry `source_quality_v2` using the existing hybrid
  scoring function from `packages.sources.source_quality`.

Tasks:
- In `collect_sources_provider_backed`, after `source_family` is inferred and
  canonicalized, call `assess_source_quality_v2`.
- Pass:
  - query
  - domain
  - url
  - title
  - snippet
  - extracted/raw text
  - expected tier
  - source family
  - published date
  - discovered phrase
- Attach:
  - `source_quality_v2`
  - `source_tier`
  - `source_usage_role`
  - `source_credibility_score`
- Preserve backward compatibility by adding fields to source metadata/state,
  not changing public response shape.

Acceptance criteria:
- All accepted graph sources have `source_quality_v2`.
- Existing tests continue to pass.
- At least one test proves a low-quality/context source cannot be primary.

Validation:
```powershell
python -m ruff check packages\research_harness\real_nodes.py packages\sources\source_quality.py tests\test_research_harness_graph.py
python -m py_compile packages\research_harness\real_nodes.py packages\sources\source_quality.py tests\test_research_harness_graph.py
pytest -q tests\test_sources_source_quality_v2.py tests\test_research_harness_graph.py -k "source_quality or source_family or chief_gate"
```

### Phase 2: Evidence Type and Evidence Quality

Status: completed

Objective:
- Evidence items inherit source quality and receive their own proof-oriented
  classification.

Tasks:
- Add internal evidence-quality helper(s):
  - infer `evidence_type`
  - compute `claim_relevance`
  - compute `evidence_specificity`
  - compute `citation_integrity`
  - compute `proof_strength`
- Attach `evidence_quality_v2` to graph evidence metadata.
- Do not modify `EvidenceItem` schema unless explicitly approved.

Acceptance criteria:
- Evidence from `official_news` can become `policy_signal`, not
  `policy_original`.
- Evidence from `company_disclosure` can support company claims, not regional
  statistics claims.
- Evidence from public-resource sources can support project rollout claims.

Validation:
```powershell
pytest -q tests\test_research_harness_graph.py -k "evidence_quality or build_evidence or source_family"
```

### Phase 3: Claim Support Eligibility Matrix

Status: completed

Objective:
- Gate claim support through a matrix instead of raw family equality.

Tasks:
- Add a deterministic eligibility helper, for example:
  `is_evidence_eligible_for_claim(claim, evidence, source)`.
- Check:
  - required source family
  - actual source family
  - evidence type
  - source quality usage role
  - credibility threshold
  - proof strength
  - citation integrity
- Return structured reason codes:
  - `eligible`
  - `wrong_source_family`
  - `weak_source_quality`
  - `wrong_evidence_type`
  - `citation_insufficient`
  - `context_only`
  - `stale_or_period_mismatch`
- Update `verify_claims` / `editor2_review` / `chief_gate` to consume eligibility
  results.

Acceptance criteria:
- `official_news` no longer satisfies `official_policy` requirements by
  default.
- `company_disclosure` no longer satisfies `statistics` requirements by
  default.
- Strong alternatives remain allowed where explicitly defined.

Validation:
```powershell
pytest -q tests\test_research_harness_graph.py -k "chief_gate or verifier or source_family_mismatch or evidence_eligibility"
```

### Phase 4: Observability in Final Report and Dossier

Status: completed

Objective:
- Make evidence eligibility visible to users and reviewers.

Tasks:
- Add dossier sections for:
  - source quality summary
  - evidence quality summary
  - eligibility failures
  - downgraded evidence
  - human review reasons
- Improve final report source notes:
  - show source title / URL / source family / source quality / usage role
  - keep internal IDs for traceability, but do not make them the only citation
    visible to users.

Acceptance criteria:
- A reviewer can inspect why a claim was accepted, downgraded, or blocked.
- If final report passes only after manual approval, that fact remains visible.

Validation:
```powershell
python scripts\graph_provider_backed_smoke.py --query "2025年合肥低空经济地方政策、上市公司披露与项目落地情况" --max-rounds 1 --max-loop-count 1 --output-dir data\tmp\evidence_eligibility_full --env-file .env --reset
```

### Phase 5: Live Regression Gate

Status: partially_completed_full_smoke_timeout

Objective:
- Validate the remediation against a small, non-overfit case set.

Cases:
- `hefei_low_altitude`: `2025年合肥低空经济地方政策、上市公司披露与项目落地情况`
- `guangdong_humanoid_robot`: `广东人形机器人产业政策、项目落地与企业参与情况`
- `shenmu_coal_chemical`: `神木煤化工在双碳约束下是否仍具备扩张空间`

Acceptance criteria:
- No clean PASS if key claims only have ineligible evidence.
- Full report can still be generated when evidence is sufficient.
- Report level / HUMAN_REVIEW decision reflects evidence eligibility.
- Credit usage remains bounded by the parent Phase 2.5 budget remediation.

Validation:
```powershell
python scripts\inspect_spec_first_pass_live.py --query "2025年合肥低空经济地方政策、上市公司披露与项目落地情况" --max-rounds 1 --output-dir data\tmp\evidence_eligibility_inspect --env-file .env --reset --print-json
python scripts\graph_provider_backed_smoke.py --query "2025年合肥低空经济地方政策、上市公司披露与项目落地情况" --max-rounds 1 --max-loop-count 1 --output-dir data\tmp\evidence_eligibility_full --env-file .env --reset
```

## Continue Rule

After each phase, continue automatically to the next phase when:
- acceptance criteria are met
- required validation passes
- no approval, permission, dependency, or human-review blocker exists
- no high-risk public contract change is required

Do not treat a phase summary as a default stopping point. Stop only at:
- explicit user pause
- missing credentials or external dependency
- repeated validation failure without a safe fix
- need to change protected public contracts
- final Done Condition

## Done Condition

This PLAN is complete when:
- Graph sources carry `source_quality_v2` from the existing source quality system.
- Graph evidence carries internal `evidence_quality_v2`.
- Claim verification uses eligibility, not only family equality.
- `official_news` cannot silently satisfy formal `official_policy` claims.
- `company_disclosure` cannot silently satisfy `statistics` claims.
- Final report / dossier expose source quality, evidence quality, and
  eligibility decisions.
- Focused tests pass.
- One full live final-report smoke is rerun and documented.

## Stop Conditions

Stop and ask the user before proceeding if:
- Implementing the fix requires changing `EvidenceBundle` schema or public API
  response shapes.
- The current code path is bytecode/proxy limited and cannot be safely patched.
- Provider/API credentials are unavailable.
- Live validation repeatedly fails for unrelated provider/network reasons.
- The fix would expand into new source adapters or broad source expansion.

## Validation Loop

Default loop:

```text
make one focused change
  -> run targeted ruff / py_compile
  -> run focused pytest
  -> inspect generated state/JSON for source_quality/evidence_quality
  -> update PLAN/STATUS
  -> continue
```

Do not run full 50-query live evaluation in this PLAN. Use only the three
non-overfit regression cases in Phase 5.

## Progress

### 2026-06-25: PLAN created

- Created this PLAN after discussion with the user about whether evidence
  rating should depend on source rating.
- Decision: evidence quality must inherit source quality because source quality
  already contains stronger hybrid signals than evidence text rules alone.
- No production code changed in this step.

### 2026-06-25: Phase 1 completed

- Execution mode: `remediation_gate -> local_direct`.
- Implemented source-quality reuse in
  `packages/research_harness/real_nodes.py`.
  - `collect_sources_provider_backed` now calls
    `packages.sources.source_quality.assess_source_quality_v2` for each accepted
    graph source after source-family inference and canonicalization.
  - Accepted graph sources now carry:
    - `source_quality_v2`
    - `source_tier`
    - `source_usage_role`
    - `source_credibility_score`
  - If quality assessment fails, the graph keeps running and marks the source as
    `context_only` with a structured fallback reason.
- Added focused regression coverage in
  `tests/test_research_harness_graph.py` to assert accepted collect sources
  expose the new source-quality fields.
- Public response shape, `EvidenceBundle`, and citation schema were not changed.

Validation:

```powershell
python -m ruff check packages\research_harness\real_nodes.py packages\sources\source_quality.py tests\test_research_harness_graph.py
python -m py_compile packages\research_harness\real_nodes.py packages\sources\source_quality.py tests\test_research_harness_graph.py
pytest -q tests\test_sources_source_quality_v2.py tests\test_research_harness_graph.py -k "source_quality or source_family or chief_gate"
pytest -q tests\test_research_harness_graph.py::test_collect_sources_provider_backed_filters_spam_and_keeps_location_match
pytest -q tests\test_agents_workflow.py tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py
```

Results:
- ruff passed.
- py_compile passed.
- focused source/source-family/chief-gate pytest: 12 passed, 66 deselected.
- collect source-quality test: 1 passed.
- research contract pytest: 24 passed.

Known notes:
- Full `python -m ruff check .` is still not used as a blocker because
  `.agent/hooks`, `.claude/worktrees`, and generated cache directories have
  pre-existing lint failures unrelated to this slice.
- A PowerShell `Select-String` verification command failed once due to an
  incorrectly escaped pattern; rerun with a simpler pattern succeeded.

### 2026-06-25: Phase 2-4 completed, Phase 5 narrow live passed

- Execution mode: `remediation_gate -> local_direct`.
- Implemented graph evidence quality metadata in
  `packages/research_harness/real_nodes.py`.
  - Evidence items now inherit `source_quality_v2` from their source.
  - Evidence items now carry internal:
    - `evidence_quality_v2`
    - `evidence_type`
    - `proof_strength`
  - Evidence quality computes claim relevance, specificity, citation integrity,
    source credibility inheritance, and primary-support eligibility.
- Implemented deterministic claim support eligibility.
  - Added structured decisions with `eligible`, `reason_code`,
    `required_source_family`, `actual_source_family`, `evidence_type`,
    `proof_strength`, and source usage role.
  - `verify_claims_provider_backed` now attaches
    `claim_support_eligibility` to claim verifications and support-matrix rows.
  - Claims with evidence that is present but ineligible are downgraded to
    unsupported/unverified in the verifier output.
  - `chief_gate_provider_backed` now prefers `eligibility_passed` over raw
    non-empty `evidence_ids` when calculating family obligation coverage.
- Added final-report/dossier observability.
  - `finalize_report_provider_backed` now writes an internal
    `contract_meta.evidence_quality` summary.
  - The final report audit markdown now includes evidence type counts, proof
    strength counts, ineligible evidence count, and eligibility failures.
- Added focused regression coverage in `tests/test_research_harness_graph.py`.
  - Official policy originals can produce `policy_original`.
  - Official news / interpretation is downgraded to `policy_signal` and
    `context_only`.
  - Verifier output rejects ineligible policy-signal evidence for formal policy
    claims.
  - Final-report audit output exposes evidence-quality / eligibility failures.

Validation:

```powershell
python -m ruff check packages\research_harness\real_nodes.py tests\test_research_harness_graph.py
python -m py_compile packages\research_harness\real_nodes.py tests\test_research_harness_graph.py
pytest -q tests\test_research_harness_graph.py -k "evidence_quality or evidence_eligibility or build_evidence or source_family or verifier or finalize or chief_gate"
pytest -q tests\test_agents_workflow.py tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py
python scripts\inspect_spec_first_pass_live.py --query "2025年合肥低空经济地方政策、上市公司披露与项目落地情况" --max-rounds 1 --output-dir data\tmp\evidence_eligibility_inspect --env-file .env --reset --print-json
python scripts\graph_provider_backed_smoke.py --query "2025年合肥低空经济地方政策、上市公司披露与项目落地情况" --max-rounds 1 --max-loop-count 1 --output-dir data\tmp\evidence_eligibility_full --env-file .env --reset
```

Results:
- ruff passed.
- py_compile passed.
- focused research-harness pytest: 16 passed, 62 deselected.
- research/provider/API contract pytest: 24 passed.
- narrow live inspection passed:
  - `data/tmp/evidence_eligibility_inspect`
  - 10 search events, 6 spec-driven search events, 31 total sources, 25
    spec-driven sources.
  - Target families included `public_resource_transaction`,
    `company_disclosure`, and `statistics`.
  - Estimated credits remained high at 20.0, matching the known parent Phase
    2.5 budget risk.
- full final-report live smoke timed out after 364 seconds and produced no
  stable artifact in `data/tmp/evidence_eligibility_full`.

Known notes:
- The narrow live inspection still shows target/actual source-family mismatch
  in some candidates. This is expected input for the new eligibility gate: such
  evidence should now be downgraded or rejected instead of silently supporting
  strong claims.
- The PLAN is not complete until the full live final-report smoke is rerun
  successfully or replaced by a bounded full-smoke command with a stable
  artifact.

### 2026-06-25: Phase 5 risk remediation - target family mismatch diagnostics

- Addressed the first known Phase 5 risk: spec-driven retrieval can target one
  source family while the accepted candidate is classified as another family.
- Implemented diagnostic fields in `collect_sources_provider_backed`:
  - `target_source_family_match`
  - `target_source_family_mismatch_reason`
  - search-event `target_family_match_count`
  - search-event `target_family_mismatch_count`
- For mismatched candidates, the source is not deleted because it may still be
  useful for another claim family. Instead, the source's
  `source_quality_v2.not_sufficient_for` now includes
  `target_source_family:<family>`.
- Updated `scripts/inspect_spec_first_pass_live.py` so narrow live inspection
  summarizes:
  - `spec_target_family_mismatch_count`
  - preview-level `target_source_family_match`
  - preview-level `target_source_family_mismatch_reason`
- Expanded the spec-round diagnostics regression test to assert that a
  `company_disclosure` target retrieving an `official_policy` result is marked
  as a mismatch and not sufficient for the target source family.

Validation:

```powershell
python -m ruff check packages\research_harness\real_nodes.py tests\test_research_harness_graph.py scripts\inspect_spec_first_pass_live.py
python -m py_compile packages\research_harness\real_nodes.py tests\test_research_harness_graph.py scripts\inspect_spec_first_pass_live.py
pytest -q tests\test_research_harness_graph.py -k "collect_sources_provider_backed_exposes_spec_round_diagnostics or evidence_eligibility or source_family"
```

Results:
- ruff passed.
- py_compile passed.
- focused pytest was not executed because the Codex runtime rejected the command
  with a usage-limit error. This is an execution-budget blocker, not a test
  failure.

Next validation when budget is available:

```powershell
pytest -q tests\test_research_harness_graph.py -k "collect_sources_provider_backed_exposes_spec_round_diagnostics or evidence_eligibility or source_family"
```

## Risks and Rollback

| Risk | Impact | Mitigation | Rollback |
|---|---|---|---|
| Eligibility matrix too strict | Too many HUMAN_REVIEW results | Prefer downgrade before block except for key claims | Relax matrix thresholds |
| Source quality integration changes behavior broadly | Existing tests may fail | Add metadata first; keep public shape stable | Disable graph source_quality_v2 consumption |
| Evidence type inference is too rule-based | Misclassification | Start with conservative types and explicit unknown/context_only | Treat unknown as context_only |
| Dossier/report observability bloats output | Large artifacts | Summarize top failures and keep full details in JSON | Limit dossier sections |
| Bytecode/proxy limitations in `real_nodes.py` | Patching risk | Make narrow wrapper-level changes only | Revert wrapper changes |

## Next Action

Resolve the Phase 5 full live smoke timeout before marking this PLAN complete.
Recommended next slice:

1. Add or use a bounded full-smoke mode that limits provider wait time and
   writes partial state artifacts before timeout.
2. Rerun the Hefei full final-report smoke with either a longer timeout or a
   narrower retrieval budget.
3. Inspect `contract_meta.evidence_quality`, `final_report.audit_markdown`,
   and `claim_support_matrix[*].claim_support_eligibility` in the generated
   artifact.
4. If the report still PASSes with ineligible evidence, reopen Phase 3/4.
   Otherwise mark Phase 5 completed and archive this PLAN.
