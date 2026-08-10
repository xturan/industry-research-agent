---
name: group2-design
description: Explicitly design project-bound Group2 implementation workers through multi-round human dialogue. Do not trigger implicitly or complete in one automatic pass.
---

# Group2 Design

Use this skill only when the user explicitly asks to design or update Group2.

## Use When

- The user invokes `$group2-design`.
- The user explicitly asks to design or update Group2 workers for a project.
- PRD workflow reaches a human-approved need for project-bound Group2 design.

## Skip When

- The user has not explicitly requested group design.
- Existing Group2 design is sufficient for the active PLAN.
- The request is ordinary implementation, test, review, or explanation.

## Required Rounds

1. Project discovery.
2. Role proposal.
3. Scope and permission boundaries.
4. Group3 validation handoff.
5. Human final review.

Do not collapse these rounds into one automatic answer.

## Outputs

- Project-bound Group2 role design.
- Mapping from universal roles to project roles.
- Allowed and forbidden write scopes.
- Validation handoff contract.
- Accepted open questions or TODOs.

## Scope

Allowed writes:

- Group design docs.
- Templates.
- Example role cards.

Forbidden writes:

- Production code.
- Active PLAN unless explicitly assigned as governance output.
- STATUS unless approved as design handoff.
- Group3 validation results.

## Stop Conditions

- Each required human review point.
- Project facts are disputed.
- Human rejects the proposed role split.
- Scope boundaries cannot be made safe.
