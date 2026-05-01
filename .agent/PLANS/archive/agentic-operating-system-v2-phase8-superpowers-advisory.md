# Agentic Operating System v2 Phase 8: Superpowers Advisory Decision

Status: completed
Date: 2026-04-27
Primary area: `eval_policy_ops`

## Decision

Keep Superpowers as an advisory reference only.

Do not install, activate, or promote Superpowers as a controlling plugin for this repository unless a future PLAN explicitly reopens this decision.

## Rationale

- The project now has native `.agent` artifacts for intent discovery, design briefs, plan review, verification, debugging, TDD policy, subagent gates, run traces, and workflow pressure scenarios.
- The repository already has a canonical authority model: system/developer instructions, `AGENTS.md`, global memory, `.agent/STATUS.md`, active PLAN, and project-native skills.
- Activating Superpowers directly could introduce competing plan/status/memory paths and heavier default process.
- The useful Superpowers concepts have been translated into project-native governance artifacts.

## Compatibility Contract

Superpowers may be used only as:

- A source of ideas for future project-native skill improvements.
- A comparison benchmark for workflow design.
- A reference during future Phase or PLAN design.

Superpowers must not:

- Override `AGENTS.md`.
- Override `.agent/STATUS.md`.
- Override the active PLAN.
- Create a canonical `docs/superpowers/plans` path.
- Create competing long-term memory.
- Bypass `invest_*` role gates.
- Require private chain-of-thought logging.
- Weaken protected contract rules or validation gates.

## Reopen Criteria

Reopen only if:

- The native `.agent` operating model proves insufficient.
- A specific Superpowers plugin capability is needed.
- The active PLAN includes a compatibility test and rollback.
- The user explicitly authorizes plugin activation.

## Validation

- Native `.agent` artifacts now exist for the key adopted/adapted concepts.
- Phase 0 authority-freeze artifact already blocks competing Superpowers authority.
- No Superpowers installation or activation occurred in this phase.
