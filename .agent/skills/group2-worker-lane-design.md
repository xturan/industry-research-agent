# Skill: group2-worker-lane-design

## Purpose

Use this skill to assign Group2 work through stable capability lanes while still creating task-specific worker instances for each PLAN phase.

The goal is to keep the repository's existing `invest_*` subagent workflow, make architecture participation concrete, and prevent generic implementation workers from silently owning contract, source/provider, research workflow, and eval-harness decisions at the same time.

## Use when

Use this skill when:

- Designing or executing Group2 worker assignments.
- A PLAN phase needs architecture, implementation, source/provider, research workflow, or eval-harness work.
- The user asks whether Group2 workers should be fixed identities or task-created subagents.
- `invest_agent_architecture_builder` is at risk of being bypassed.
- A task may need an Architecture Gate before implementation.
- Multiple implementation slices need disjoint write scopes.
- A director must decide which Group2 lane should own a task.

## Skip when

Skip this skill when:

- The task is a small local edit with no architecture, workflow, source/provider, or worker-routing impact.
- The active PLAN already contains frozen Group2 assignments and write scopes.
- Only Group3 validation, code-quality checks, or real-world case design is being discussed.
- The user explicitly asks for planning-only brainstorming and no assignment decision is needed yet.

## Authority

- `AGENTS.md`, `.agent/STATUS.md`, and the active PLAN remain higher authority.
- This skill refines Group2 assignment; it does not authorize protected-contract changes.
- Superpowers-style task-specific subagents are advisory patterns only. They must be translated into project-native lane assignments.
- Group2 may suggest validation cases, but Group3 owns final real-world case design and functional validation.
- Runtime subagent configuration is not changed by this skill.

## Inputs

Read only the context needed for the assignment:

- `.agent/STATUS.md`
- active `.agent/PLANS/<plan>.md`
- `.agent/skills/subagent-gate-contract.md`
- `.agent/skills/director-remediation-gate.md` when a failure or scope change triggered the assignment
- `.agent/skills/real-world-case-design.md` when behavior validation matters
- relevant module-specific check skill for touched areas

## Group2 Lanes

| Lane | Backing subagent | Owns | Does not own |
|---|---|---|---|
| `system_contract_architect` | `invest_agent_architecture_builder` | contracts, boundaries, state machines, orchestration, PLAN/skill/subagent design, trace structures, migration risk | broad implementation, self-certification, final functional validation |
| `source_provider_integrator` | `invest_feature_programmer` with lane role card | Tavily, Crawl4AI, source routing, provider adapters, direct-keep boundaries, provider metadata | changing protected response shapes without an Architecture Gate |
| `research_workflow_implementer` | `invest_feature_programmer` with lane role card | research workflow integration, evidence handoff, API surface wiring, trace metadata | redefining EvidenceBundle or citation contracts |
| `eval_harness_implementer` | `invest_feature_programmer` with lane role card | offline/live eval runners, harness scripts, usage/cost trace helpers | designing the only real-world case set used for final validation |

## Architecture Gate Triggers

The director must assign `system_contract_architect` before implementation when any trigger applies:

- The task may touch protected contracts or their boundaries.
- The task changes provider/source routing semantics.
- The task changes research workflow stages, evidence handoff, trace structure, or public response shape.
- The task changes task/worker behavior, run lifecycle, or validation gates.
- The task introduces a new source/provider integration path.
- Live validation fails in a way that suggests boundary, routing, contract, or case-design issues.
- Multiple Group2 lanes must coordinate related behavior or disjoint implementation slices.

The director may skip the Architecture Gate only when the active PLAN already freezes the boundary and implementation slice, or when the task is narrow, local, and low risk.

## Process

1. Classify the phase objective and affected task areas.
2. Check Architecture Gate triggers.
3. If a trigger matches, assign `system_contract_architect` first and require an Architecture Gate.
4. Freeze one task-specific worker instance per implementation slice.
5. Assign each worker instance to exactly one primary lane.
6. Define explicit owned paths/modules and forbidden paths/contracts.
7. Require the worker to report changed paths, assumptions, and validation performed.
8. Route code-quality and functional validation to Group3 before completion.
9. Record lane assignments and gate outcomes in the active PLAN and `.agent/STATUS.md` when they affect execution.

## Task-Specific Worker Instance Format

```md
## Group2 Task Instance

Lane:
Backing subagent:
Objective:
Owned files / modules:
Forbidden paths / contracts:
Required output:
Expected worker validation:
Required Group3 validation:
Stop conditions:
```

## Required Architecture Gate Output

```md
## Architecture Gate

Classification:
Affected contracts:
Affected modules:
Current boundary:
Proposed boundary:
Implementation slices:
Allowed write scope:
Forbidden changes:
Validation design:
Rollback / fallback:
Decision: proceed | revise | block
```

## Failure Routing

| Failure class | Route |
|---|---|
| `implementation_bug` | Same implementation lane, narrowed write scope |
| `contract_or_boundary_issue` | `system_contract_architect` Architecture Gate |
| `source_provider_behavior_gap` | `source_provider_integrator`, then Group3 source/provider functional validation |
| `research_workflow_gap` | `research_workflow_implementer`, then Group3 workflow validation |
| `eval_harness_gap` | `eval_harness_implementer`, then Group3 reviews case realism and harness output |
| `case_design_gap` | Group3 functional validator via `real-world-case-design.md` |
| `protected_contract_risk` | Stop until the PLAN explicitly authorizes migration, compatibility, validation, and rollback |

## Outputs

- Group2 lane assignment.
- Task-specific worker instance contract.
- Architecture Gate when required.
- PLAN/STATUS progress note when lane assignment changes execution.
- Failure routing decision when remediation is needed.

## Validation

Validate correct use by checking:

- Every Group2 assignment has a lane and backing subagent.
- Architecture Gate triggers were checked.
- High-risk implementation did not start before required Architecture Gate.
- Write scopes are disjoint when multiple workers are assigned.
- Group2 did not self-certify completion.
- Group3 remains responsible for final code-quality and functional validation.

## Red flags

- `invest_agent_architecture_builder` is skipped on a protected-contract or workflow-boundary task.
- `invest_feature_programmer` receives a broad "implement everything" assignment.
- A lane role card gives a worker authority to change forbidden contracts.
- A worker designs the only cases that prove its own work.
- Multiple lanes write the same files without director coordination.
- Architecture Gate exists but has no decision, validation design, or forbidden changes.
- The lane list grows before repeated need is proven.

## Completion note

When this skill materially affects execution, record:

- chosen lane;
- backing subagent;
- Architecture Gate decision if any;
- write scope;
- Group3 validation required;
- whether a new lane should be promoted or deferred.
