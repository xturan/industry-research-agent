# Skill: design-brief-template

## Purpose

Use this template to create a concise Design Brief before a PLAN or implementation phase when the task is ambiguous, cross-module, high-risk, or product-design oriented.

The Design Brief is not a replacement for a PLAN. It is the pre-PLAN artifact that freezes intent, constraints, and tradeoffs.

## Use when

Use this skill when:

- The task may become a long-running PLAN.
- The user asks for application design, agent design, source strategy, workflow design, or architecture.
- The implementation path is not obvious.
- The task may affect protected contracts, source routing, research workflow, provider behavior, task semantics, or delivery behavior.
- You need user alignment before writing detailed milestones.

## Skip when

Skip this skill when:

- The active PLAN already contains a current Design Brief or equivalent decision record.
- The user asks for a small low-risk edit.
- The task is pure debugging and the first action is to collect logs or reproduce the error.

## Required brief

```md
# Design Brief: <short name>

Status: draft | accepted | superseded
Date: <yyyy-mm-dd>
Primary area: <module classification>
Secondary areas: <comma-separated list>

## Problem

<What problem are we solving?>

## User Goal

<What outcome does the user want?>

## Success Criteria

- <Observable success condition>
- <Validation or eval condition>

## Non-Goals

- <What must not be changed?>

## Constraints

- <Repository rules>
- <Protected contracts>
- <Runtime / provider / credential constraints>

## Current System Context

- <Relevant files, services, plans, skills, or workflows>

## Options Considered

| Option | Summary | Pros | Cons | Decision |
|---|---|---|---|---|
| A | <summary> | <pros> | <cons> | accept / reject |
| B | <summary> | <pros> | <cons> | accept / reject |

## Recommended Design

<The chosen design and why it is pragmatic.>

## Validation Plan

- <Command, eval, dry-run, or manual check>

## Rollback / Fallback

- <How to undo or downgrade if it fails>

## Open Questions

- <Only questions that block safe execution>
```

## Quality bar

- Keep the brief short enough to read in one pass.
- Make the recommendation explicit.
- Do not bury unresolved risk inside prose.
- Do not authorize protected-contract changes unless the active PLAN explicitly permits them.
- Prefer concrete validation over "review manually" when possible.

## Red flags

- The brief says "TBD" for validation.
- The recommendation does not identify tradeoffs.
- The task changes agent behavior but no pressure scenario is named.
- The brief introduces a second plan/status/memory authority.
- The brief implies completion without fresh validation evidence.

## Completion note

If the brief becomes accepted, either embed it in the PLAN or link it from the PLAN progress section. Update `.agent/STATUS.md` if it changes the active execution path.
