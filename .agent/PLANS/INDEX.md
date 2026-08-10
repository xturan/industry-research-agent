# PLAN Index

Last updated: 2026-07-16

WS2 cleanup (harness-governance-activation-v1, executed 2026-06-21): archived 15
completed/superseded/blocked PLANs; active dir reduced 25 → 10. This index now
matches the on-disk state.

## Active (in execution)

| Plan | Status | Notes |
|---|---|---|
| `goal-driven-evidence-react-v1.md` | `active_phase2_5_live_diagnostics_passed_pending_budget_tuning` | Narrow live inspection passed for spec-driven first-pass retrieval; budget tuning is needed before Phase 2.5 completion. |
| `search-caliber-expansion-v1.md` | `active_phase2_graph_integration` | Search caliber expansion (Intent Planner → phrase builder → caliber guard). |
| `research-product-v1.md` | `active_phase1_report_persistence` | Deep Research product persistence work. |
| `source-local-procurement-regulatory-depth-v1.md` | `active_phase1_completed_pending_targeted_gate` | Source procurement/regulatory depth; paused pending targeted gate. |

## Active Reference (Phase-0 contracts, consulted not executed)

| Plan | Status | Notes |
|---|---|---|
| `deep-research-report-rubric-v1.md` | `active_reference_rubric` | Reference rubric for what counts as a real final deep-research report. |
| `deep-research-agent-contract-matrix-v1.md` | `active_phase0_contract_matrix` | Node-by-node prompt/context/output contract matrix. |
| `deep-research-memory-contract-v1.md` | `active_phase1_contract_freeze` | Memory contract freeze for the research graph. |
| `langgraph-v1-promotion-gate-v1.md` | `active_phase4_edge_case_matrix_audited` | Promotion-gate baseline; gate reference, not primary contract. |

## Pending Human Review

| Plan | Status | Notes |
|---|---|---|
| `agentic-operating-system-v2.md` | `completed_pending_human_review` | Governance OS work complete; awaiting accept/archive decision. |
| `source-quality-scoring-v2.md` | `pending_human_review_phase1_shadow_implemented` | Source Quality v2 shadow layer implemented; awaiting next scoring slice. |
| `langgraph-research-workflow-harness-v1.md` | `pending_next_slice_design_provider_backed_slice2_completed` | Harness sidecar baseline; awaiting next-slice design. |

## Recently Archived (WS2 cleanup 2026-06-21)

Completed / superseded:
- `archive/report-narrative-context-budget-remediation-v1.md` — completed (narrative v2, actual prompt budget, context payload slimming, honest level gate)
- `archive/deep-research-readable-report-remediation-v1.md` — completed (depth track 4/4 product_pass)
- `archive/deep-research-readable-report-quality-v2.md` — superseded by remediation v1
- `archive/deep-research-report-productization-v1.md` — superseded by quality v2
- `archive/langgraph-research-productization-v1.md` — completed (keep opt-in)
- `archive/theme-watchlist-intel-workbench-v1.md` — completed
- `archive/deep-research-agent-v1.md` — completed
- `archive/longtasks-substrate-v1.md` — completed
- `archive/search-quality-improvement-v1.md` — completed
- `archive/unified-research-pipeline-v1.md` — completed

Blocked / superseded remediation chain:
- `archive/source-direct-structured-execution-v1.md` — blocked_at_phase7_gate
- `archive/source-generalized-evidence-remediation-v1.md` — blocked_at_phase5_gate
- `archive/source-local-evidence-backbone-remediation-v1.md` — completed_with_successor_blocker
- `archive/source-profile-adapter-remediation-v1.md` — blocked_handoff
- `archive/source-strong-evidence-adapter-remediation-v1.md` — blocked_handoff
- `archive/source-quality-stress-eval-v1.md` — blocked_pending_remediation

## Hygiene Rules

- Keep only active / active-reference / pending-human-review PLANs in `.agent/PLANS/`.
- Move completed/superseded/abandoned PLANs to `.agent/PLANS/archive/`.
- This index is inventory only. Execution authority: `AGENTS.md` → `.agent/STATUS.md`
  → selected PLAN → relevant skills.
