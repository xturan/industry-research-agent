---
name: plan-from-prd
description: Convert an approved PRD/RPD into a durable PLAN with phases, validation, gates, scope boundaries, and explicit stop conditions.
---

# Plan From PRD

Use this skill only after the PRD/RPD has been approved.

## Use When

- Human has approved the PRD/RPD.
- The user explicitly asks to create a PLAN from an approved PRD.
- `prd-workflow` reaches the PLAN creation gate.

## Skip When

- PRD/RPD has not been approved.
- User asks for a draft PRD, not a PLAN.
- The task is a small one-off edit where repository rules do not require PLAN.

## Inputs

- Approved PRD/RPD.
- Approval notes.
- Scope and non-goals.
- Acceptance criteria.
- Risks.
- Project planning rules.

## Outputs

- PLAN file.
- STATUS handoff update, when applicable.
- Validation loop.
- Phase status scheme.
- Stop conditions.

## Scope

Allowed writes:

- PLAN file.
- STATUS or equivalent handoff file.
- Optional planning artifacts.

Forbidden writes:

- Production code.
- Tests.
- Hooks.
- Project worker config.

## Stop Conditions

- PLAN is ready for human review.
- PRD approval is missing or ambiguous.
- PLAN requires a protected contract change not approved in PRD.
