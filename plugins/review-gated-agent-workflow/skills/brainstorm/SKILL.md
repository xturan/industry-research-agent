---
name: brainstorm
description: Build a project-independent requirement frame with problem statement, goals, non-goals, alternatives, risks, assumptions, and open questions for PRD workflow.
---

# Brainstorm

Use this skill to frame the requirement before PRD/RPD generation.

## Use When

- Called by `prd-workflow`.
- The user explicitly asks for early requirement thinking before PRD.

## Skip When

- The task is already implementation-ready.
- The user only wants a code change or test run.
- Brainstorming would overwrite an approved PRD or PLAN without review.

## Inputs

- Raw user request.
- Project/product context.
- Prior PRD or design notes.
- Constraints and non-goals.

## Outputs

- Problem frame.
- User and scenario assumptions.
- Solution candidates.
- Risks and danger points.
- PRD open questions.
- Suggested acceptance themes.

## Scope

Allowed writes:

- Brainstorm draft notes.
- PRD/RPD input artifacts.

Forbidden writes:

- Production code.
- PLAN.
- STATUS.
- Hooks.
- Subagent configuration.

## Stop Conditions

- Critical product facts are missing.
- Multiple incompatible product directions remain.
- User requests to pause for review.
