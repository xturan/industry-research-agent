# PLAN: Team Task Board

Status: approved_example
Scope: generic SaaS feature

## Objective

Implement a basic team task board with task creation, assignment, status changes,
due-date filtering, and minimal audit visibility.

## Phase Status Display

```text
phase 1✅：workflow-director froze scope, validation cases, and worker assignment
phase 2⏳：Group2 implements task model, service, and board filters
phase 3：Group3 validation has not started
phase 4：workflow-summarizer has not started
```

## Phase 1: Director Gate

Acceptance:

- Scope is limited to task creation, status change, filtering, and minimal audit.
- Non-goals remain out of scope.
- Validation cases are frozen before implementation.

Group2 assignment:

- `architecture-builder`: status transition and audit boundary.
- `feature-implementer`: task CRUD and filter implementation.

Group3 assignment:

- `code-quality-validator`: lint, compile, focused tests.
- `functional-validator`: acceptance cases TC-001 to TC-004.

## Phase 2: Group2 Implementation

Allowed writes:

- task model/service/API files;
- focused tests;
- docs for the feature.

Forbidden writes:

- PLAN changes;
- unrelated auth or billing modules;
- release automation.

## Phase 3: Group3 Validation

Code-quality checks:

```powershell
python -m ruff check .
pytest -q tests/test_task_board.py
```

Functional checks:

- TC-001 create valid task.
- TC-002 reject missing title.
- TC-003 filter by assignee and overdue.
- TC-004 reject forbidden status transition.

## Phase 4: Summary

Summarizer checks:

- Did the feature match the PRD?
- Did validation pass?
- Are new worker skills needed?
- Are hook scope rules sufficient?

## Stop Conditions

- A new billing, sprint, or AI-prioritization feature is requested.
- Status transition policy is unresolved.
- Validation fails and safe remediation is unclear.
