# Phase 4: P0 Review Issue Gate Consumption — Design Spec

Status: approved | Date: 2026-06-17 | PLAN: deep-research-readable-report-remediation-v1

## Objective

让 Editor2 / verifier 的 P0 问题影响 graph-v1 最终 gate 决策。PASS 要求 zero P0 issues。

## Design: Three-Part Change

### Part 1 — Editor2 Severity Calibration

File: `packages/research_harness/real_nodes.py` — `editor2_review_provider_backed`

Extend fallback issue generation beyond the single `section_role_mismatch` (warning).
Produce five issue types with correct severity:

| issue_type | severity | trigger |
|------------|----------|---------|
| `section_role_mismatch` | warning | claim's section role ≠ claim_family |
| `source_family_mismatch` | blocker | evidence source_family ≠ claim's required_source_family |
| `unsupported_claim` | blocker | claim has empty evidence_ids |
| `low_source_diversity` | warning | claim has only one evidence/source |
| `critical_limitation_unresolved` | warning | evidence limitations contain unresolved critical items |

blame → gate blocks PASS. warning → gate downgrades quality without blocking.

### Part 2 — Gate Unified P0 Consumption

File: `packages/research_harness/real_nodes.py` — `chief_gate_provider_backed`

Remove ad-hoc heuristics (lines 1697-1709: `has_source_family_mismatch`, `section_role_mismatches` counting).
Read P0 classification exclusively from `review_issues` list.

```python
hard_blockers = [i for i in review_issues if i["severity"] == "blocker"]
warnings     = [i for i in review_issues if i["severity"] == "warning"]
has_hard_blockers = len(hard_blockers) > 0
has_warnings = len(warnings) > 0
```

Block chain (order preserved):

1. **Block 1** — obligation gaps: `has_obligation_gap` → ADD_EVIDENCE (unchanged)
2. **Block 2** — P0 hard blockers: `has_hard_blockers` → decision ≠ PASS
   - If HUMAN_REVIEW priority already active → keep HUMAN_REVIEW
   - Else → REVIEW_RISK, route to `editor2_review`
   - `gate_reason` names the specific P0 issue_types
3. **Block 3** — warnings downgrade: `has_warnings` and no hard blockers → `quality_scores.final_score *= 0.85`, decision may still PASS

### Part 3 — HUMAN_REVIEW API Extension

Files: `packages/research_harness/schemas.py`, `packages/research_harness/runner.py`

#### 3a. GraphHumanReviewState extension

```python
class P0IssueSummary(BaseModel):
    issue_type: str       # source_family_mismatch, unsupported_claim
    description: str      # human-readable
    claim_id: str | None
    source_id: str | None

class P0ReviewContext(BaseModel):
    available_actions: list[str]  # ["approve","add_evidence","rewrite","reject","override_p0"]
    suggested_action: str | None
    suggested_reason: str | None

class GraphHumanReviewState(BaseModel):
    pending: bool
    selected_action: str | None
    reason: str | None
    blocking_p0_issues: list[P0IssueSummary]   # NEW
    p0_review_context: P0ReviewContext | None   # NEW
```

#### 3b. New `override_p0` action

When reviewer judges a P0 classification is a false positive, they can override.
`_apply_human_review_action` marks overridden issues with `overridden_by_human=True`,
and gate skips them on reentry.

## Protected Contracts

- `GraphHumanReviewState` fields are additive — existing consumers unaffected
- `review_issues` list shape unchanged — only new entry types added
- Obligation gap block unchanged — only new P0 blocks added after it
- Legacy `/deep-research/analyze` and `/research/analyze` untouched

## Validation

```powershell
# Part 1: editor2 produces correct severity
pytest -q tests/test_research_harness_graph.py -k "editor2"

# Part 2: gate consumes P0 correctly
pytest -q tests/test_research_harness_graph.py -k "chief_gate or p0 or review_issue"

# Part 3: HUMAN_REVIEW schema
python -m py_compile packages/research_harness/schemas.py

# Full gate + editor2 suite
pytest -q tests/test_research_harness_graph.py -k "chief_gate or editor2 or verifier"
```

## Fallback / Safety

- If `review_issues` list is empty or missing, all P0 counts default to 0
- Overridden P0 issues are tracked with `overridden_by_human` flag, not deleted
- `override_p0` is gated: only usable when gate explicitly routes to HUMAN_REVIEW from P0 block
