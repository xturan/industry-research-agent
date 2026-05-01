---
description: "Review a PLAN before implementation: check authority, scope, protected contracts, validation design, and continuation safety."
argument-hint: "[plan file path]"
---

# Plan Self-Review

Review a PLAN before implementation or phase transition. See `.agent/skills/plan-self-review.md` for full rules.

## Required Checks

### Authority
- STATUS points to this active PLAN
- PLAN does not create competing status/memory/plan paths
- External methodology content is advisory unless translated into project-native artifacts

### Scope
- Primary and secondary task areas are listed
- Allowed write scope is explicit for implementation phases
- Out-of-scope paths are explicit
- Existing dirty-worktree risk is recorded

### Protected Contracts
- Protected contracts are listed
- Any intended protected-contract change has: migration, compatibility, validation, and rollback block
- No hidden schema or response-shape changes implied by prose

### Validation
- Validation commands, dry-runs, evals, or manual checks are concrete
- Pass/fail criteria are observable
- Functional validation is separate from code quality validation
- Completion requires fresh evidence

### Continuation
- Next action is explicit
- Phase transition criteria are recorded
- Stop conditions are explicit

## Placeholder Scan

Flag unresolved: `TODO`, `TBD`, `etc`, `handle appropriately`, `similar`, `as needed`, `later`

## Red Flags

- PLAN says "Phase 1/2/3" but has no acceptance criteria
- PLAN names agents but does not define write scope
- Worker can self-certify completion
- Validation only says "run tests" without commands or expected behavior
- PLAN relies on hidden conversation memory

## Completion

Record review results in the PLAN progress section and `.agent/STATUS.md` when they affect the active execution path.
