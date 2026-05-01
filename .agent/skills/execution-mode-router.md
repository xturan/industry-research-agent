# Skill: execution-mode-router

## Purpose

Use this skill to choose the lightest safe execution route before implementing a PLAN, remediation gate, or non-trivial task.

The project default is speed-biased: start with `local_direct` or `light_subagent` when safe, and escalate only when risk triggers require the full v2 subagent workflow.

## Use when

- The user asks to execute a PLAN, continue implementation, or start a remediation.
- A task could be handled either directly or through subagents.
- A PLAN phase has unclear execution weight.
- A validation failure may need a narrow remediation gate instead of a full workflow restart.
- External API spend, live eval cost, or latency should be controlled before running.

## Skip when

- The user is only asking a conceptual question and no work will be executed.
- The active PLAN already freezes an execution mode for the current phase.
- Higher-priority instructions explicitly require a specific workflow.
- An emergency blocker requires immediate stop and user guidance.

## Authority

- `AGENTS.md`, `.agent/STATUS.md`, and the active PLAN remain higher authority.
- This skill chooses the execution route; it does not authorize protected-contract changes.
- If this skill selects `full_subagent`, `.agent/skills/subagent-gate-contract.md` controls the detailed role flow.
- If this skill selects `remediation_gate`, `.agent/skills/director-remediation-gate.md` controls the gate.
- If this skill selects `light_subagent`, Group3 validation is still required for code-quality or practical behavior claims.

## Inputs

- `AGENTS.md`
- `.agent/STATUS.md`
- active `.agent/PLANS/<plan>.md` when one exists
- relevant changed/target files
- recent validation failure, live run artifact, or blocker summary when applicable
- cost/latency constraints for live provider work

## Execution Modes

| Mode | Default use | Required validation |
|---|---|---|
| `planning_only` | Brainstorming, design, PLAN creation, option comparison | Design/PLAN review only; no implementation claims |
| `local_direct` | Small docs, scripts, isolated tests, low-risk config or report updates | Main agent runs focused checks and updates PLAN/STATUS if relevant |
| `light_subagent` | Single module or source-family implementation with clear scope and no protected-contract change | One implementation worker when useful, code-quality gate, optional functional gate |
| `full_subagent` | Cross-module, source/provider/research/evidence/workflow boundary, protected-contract risk, live quality gate ownership | Director, architecture gate when triggered, Group2 lanes, Group3 code-quality and functional validation, summarizer at completion |
| `remediation_gate` | A PLAN/live/eval failed but the user goal remains unchanged | Narrow failure classification, allowed write scope, fresh validation, then route to `local_direct`, `light_subagent`, or `full_subagent` |

## Fast Default

Prefer the fastest safe route:

1. Use `local_direct` for docs/governance/report/test-harness edits that do not alter production behavior.
2. Use `light_subagent` for scoped source/provider/eval implementation when protected contracts are not touched.
3. Escalate to `full_subagent` only when a hard trigger applies.
4. Use `remediation_gate` for failed live/eval gates before opening another broad PLAN.

## Hard Escalation Triggers

Select `full_subagent` when any of these are true:

- EvidenceBundle, citation, research response, provider abstraction, task status, run lifecycle, or public response shape may change.
- Source routing/provider semantics change across multiple modules.
- A new source/provider integration path is introduced.
- Multiple Group2 lanes must coordinate related behavior.
- Live validation fails in a way that suggests boundary, contract, or case-design problems.
- The task can materially affect user-facing research conclusions.

Select `remediation_gate` when:

- A PLAN phase, live eval, or audit gate failed.
- The product goal remains valid.
- The next safe step is a narrower failure-class fix.

## Process

1. Classify the task area and write scope.
2. Check whether the active PLAN already names an execution mode.
3. Check hard escalation triggers.
4. Choose the lightest safe mode.
5. Record an execution-mode note when the choice affects PLAN execution.
6. Run the mode-specific workflow and validation.
7. Escalate if validation fails twice for the same failure class or if a protected-contract risk appears.

## Outputs

When material, record:

```md
## Execution Mode

Mode:
Reason:
Risk triggers:
Allowed write scope:
Forbidden changes:
Required validation:
Escalation rule:
```

## Validation

- The chosen mode is recorded in the active PLAN, STATUS, or step summary when it affects execution.
- `local_direct` tasks still run focused validation before completion claims.
- `light_subagent` tasks do not bypass Group3 code-quality validation when code changed.
- `full_subagent` tasks still follow `.agent/skills/subagent-gate-contract.md`.
- Failed live/eval gates use `remediation_gate` before another broad workflow restart.

## Red flags

- Defaulting every PLAN to full director/worker/validator/summarizer flow.
- Calling a source/provider boundary change "local_direct".
- Using `light_subagent` to avoid Architecture Gate triggers.
- Running expensive live evals before recording cost and scope.
- Treating a smoke query as a target for hard-coded fixes instead of a symptom of a source-family gap.
- Skipping validation because the route is "light".

## Completion note

Record the selected mode, why it was safe, what validation ran, and whether the route should be promoted or adjusted.
