# PLAN: {Feature Name}

Status: draft_pending_human_review
Scope: {scope}
Created: {YYYY-MM-DD}

## Objective

{Outcome that must be true when the PLAN is done.}

## Scope

In scope:

- {Item}

Out of scope:

- {Item}

## Phase Status Display

Use phase status only after PLAN execution starts:

```text
phase 1：workflow-director has not started
phase 2：Group2 has not started
phase 3：Group3 has not started
phase 4：workflow-summarizer has not started
```

## Phase 1: Director Gate

Acceptance:

- PLAN scope is frozen.
- Validation cases are defined.
- Group2 and Group3 assignments are explicit.

## Phase 2: Group2 Implementation

Allowed writes:

- {Assigned paths}

Forbidden writes:

- PLAN/STATUS unless assigned as governance output.
- Unrelated modules.
- Protected contracts not authorized in this PLAN.

## Phase 3: Group3 Validation

Code-quality checks:

```powershell
{commands}
```

Functional checks:

- {Case}

## Phase 4: Summary

Summarizer checks:

- Outcome.
- Validation.
- Risks.
- Whether skills/hooks/roles need updates.

## Stop Conditions

- Human review is pending.
- Protected contract change is required.
- Validation fails without a safe repair path.
