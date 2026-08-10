---
name: prd-html-review
description: Generate a reviewable PRD/RPD artifact, usually HTML plus Markdown source, with diagrams, risk matrix, acceptance criteria, and human review questions.
---

# PRD HTML Review

Use this skill after brainstorm to create a reviewable PRD/RPD artifact.

## Use When

- Called by `prd-workflow` after brainstorm.
- The user explicitly asks for an HTML PRD/RPD review artifact.

## Skip When

- PRD has not been framed.
- User asks for PLAN creation directly from an already approved document.
- The task is ordinary implementation.

## Inputs

- Brainstorm brief.
- PRD template.
- Project/product context.
- Review audience.
- Risks and open questions.

## Outputs

- `reviewable_prd.html`.
- Optional `reviewable_prd.md`.
- Diagrams or embedded Mermaid.
- Review checklist.
- Risk and decision summary.

## Scope

Allowed writes:

- PRD/RPD files.
- PRD assets.

Forbidden writes:

- PLAN files.
- STATUS.
- Production code.
- Project worker configuration.

## Stop Conditions

- PRD/RPD is generated and ready for human review.
- Template requirements conflict with user-provided scope.
- Required review fields are missing.
