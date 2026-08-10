---
name: workflow-scope-guard
description: Define and audit stage-specific read/write boundaries for review-gated workflow skills, hooks, Group2 implementation, Group3 validation, and summarization.
---

# Workflow Scope Guard

Use this skill to define or audit workflow stage boundaries.

## Use When

- Writing hook scope rules.
- Auditing a worker's allowed writes.
- Reviewing a diff for scope violations.
- A phase claims completion.

## Skip When

- The task is read-only and has no file changes.
- The repository already has stricter active hook rules for the exact stage.

## Inputs

- Current workflow stage.
- Active PLAN phase.
- Assigned worker role.
- Changed files.
- Allowed and forbidden paths.
- Protected contracts.

## Outputs

- Scope decision: pass, warn, or block.
- Violated paths or contracts.
- Suggested remediation.
- Concise audit summary.

## Scope

Allowed writes:

- Validation reports.
- Hook scope templates.
- PLAN/STATUS notes only when assigned by governance phase.

Forbidden writes:

- Production code fixes during validation.
- Rewriting the user's intent.
- Auto-entering PRD workflow.

## Stop Conditions

- Forbidden write detected.
- Protected contract touched without explicit authorization.
- Worker role and assigned scope do not match.
- Validation cannot determine whether a change is in scope.
