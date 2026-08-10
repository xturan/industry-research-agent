---
name: prd-workflow
description: Explicitly start the review-gated PRD workflow for a feature, generating brainstorm output, reviewable PRD/RPD, human review gates, and PLAN creation only after approval. Do not trigger for ordinary coding, testing, review, or explanation tasks.
---

# PRD Workflow

Use this skill only when the user explicitly invokes PRD workflow.

## Use When

- The user says `$prd-workflow`.
- The user explicitly asks to start PRD design or PRD review workflow.
- The user asks to generate a PRD/RPD before implementation.

## Skip When

- The user asks to fix a bug.
- The user asks to continue an existing PLAN.
- The user asks for code explanation, tests, review, or a small edit.
- The active task already has an approved PLAN and no PRD change is requested.

## Workflow

1. Confirm feature frame: name, context, users, goals, non-goals, constraints.
2. Invoke or follow `brainstorm`.
3. Invoke or follow `prd-html-review`.
4. Stop for human PRD review.
5. After approval, invoke or follow `plan-from-prd`.
6. Stop for human PLAN review.
7. Wait for explicit PLAN implementation instruction.

## Outputs

- Brainstorm brief.
- Reviewable PRD/RPD artifact path.
- PRD review questions.
- Approval state.
- PLAN path after approval.

## Scope

Allowed writes:

- PRD/RPD draft folder.
- PLAN file only after PRD approval.
- Status/handoff only when creating or updating an active PLAN.

Forbidden writes:

- Production code.
- Test code.
- Runtime config.
- Project-bound Group2 design unless explicit `group2-design` is invoked.

## Stop Conditions

- PRD/RPD is ready for human review.
- PLAN is ready for human review.
- User rejects or redirects scope.
- Required feature facts cannot be inferred safely.
