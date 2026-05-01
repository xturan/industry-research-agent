# Skill: plan-self-review

## Purpose

Review a PLAN before implementation or phase transition to ensure it is executable, scoped, validation-driven, and continuation-safe.

## Use when

Use this skill when:

- Creating or updating a long-running PLAN.
- Starting implementation from an active PLAN.
- Moving from one phase to another.
- A worker reports phase completion.
- A PLAN changes agent orchestration, source routing, provider behavior, research workflow, task semantics, or protected contracts.

## Required checks

### Authority

- STATUS points to the active PLAN.
- The PLAN does not create a competing status, memory, or plan path.
- Superpowers or external methodology content is advisory unless translated into project-native artifacts.

### Scope

- Primary and secondary task areas are listed.
- Allowed write scope is explicit for implementation phases.
- Out-of-scope paths are explicit.
- Existing dirty-worktree risk is recorded if a clean scope proof is not possible.

### Protected contracts

- Protected contracts are listed.
- Any intended protected-contract change has a migration, compatibility, validation, and rollback block.
- No hidden schema or response-shape changes are implied by prose.

### Validation

- Validation commands, dry-runs, evals, or manual checks are concrete.
- Pass/fail criteria are observable.
- Functional validation is separate from code quality validation.
- Completion requires fresh evidence.

### Continuation

- The next action is explicit.
- Phase transition criteria are recorded.
- "Summarize this phase" is not treated as the default stopping point.
- Stop conditions are explicit.

## Placeholder scan

Flag unresolved placeholders unless explicitly deferred:

- `TODO`
- `TBD`
- `etc`
- `handle appropriately`
- `similar`
- `as needed`
- `later`

## Red flags

- The PLAN says "Phase 1/2/3" but has no acceptance criteria.
- The PLAN names agents but does not define write scope.
- A worker can self-certify completion.
- The validation section only says "run tests" without commands or expected behavior.
- The PLAN relies on hidden conversation memory.

## Completion note

Record review results in the PLAN progress section and `.agent/STATUS.md` when they affect the active execution path.
