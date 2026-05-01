# Agentic Operating System v2 Skill Router

Status: active
Date: 2026-04-27

## Purpose

Map recurring task classes to project-native `.agent` skills and gates.

This router is lower authority than system/developer instructions, `AGENTS.md`, `.agent/STATUS.md`, and the active PLAN. It should help Codex choose the right project skill without growing a monolithic prompt.

## Routing Rules

| Task signal | Use skill / artifact | Gate |
|---|---|---|
| Ambiguous goal, product design, agent design, architecture tradeoff | `.agent/skills/intent-discovery-gate.md` | intake before implementation |
| User asks to brainstorm, explore, compare options, or discuss an open-ended design | `.agent/skills/brainstorming.md` | option exploration before Design Brief |
| Need pre-PLAN design alignment | `.agent/skills/design-brief-template.md` | Design Brief before PLAN |
| Creating/updating a long-running PLAN | user-level `plan-creator` plus active PLAN rules | durable PLAN + STATUS |
| Starting PLAN execution, continuing implementation, or choosing whether to use subagents | `.agent/skills/execution-mode-router.md` | speed-biased route selection before worker dispatch |
| PLAN completeness, continuation, write scope, protected contract review | `.agent/skills/plan-self-review.md` | self-review before implementation |
| About to claim a task is complete | `.agent/skills/verification-before-completion.md` | fresh evidence required |
| Debugging a failure or flaky behavior | `.agent/skills/systematic-debugging.md` | reproduce/root-cause before patch |
| New behavior or bug fix where tests are practical | `.agent/skills/tdd-policy.md` | test-first or characterization first |
| Execution mode selects full subagent workflow or a phase explicitly requires role-bound subagents | `.agent/skills/subagent-gate-contract.md` | director -> worker -> validator |
| Group2 worker identity, lane assignment, architecture-builder participation, or task-specific worker instances | `.agent/skills/group2-worker-lane-design.md` | fixed capability lane + scoped worker instance |
| PLAN execution hits blocker, validation failure, scope risk, or ambiguous remediation | `.agent/skills/director-remediation-gate.md` | director-controlled remediation gate |
| Need realistic functional validation cases, holdouts, negative controls, or live eval cases | `.agent/skills/real-world-case-design.md` | Group 3 case design before completion |
| Creating or updating `.agent` skills or skill router entries | `.agent/skills/skill-design-standard.md` | Superpowers-compatible skill format review |
| Source-layer changes | `.agent/skills/source-regression-check.md` | source regression checks |
| Domestic source code changes | `.agent/skills/domestic-source-check.md` | domestic source checks |
| Research/provider contract changes | `.agent/skills/research-contract-check.md` | research contract checks |
| Task/worker/substrate changes | `.agent/skills/task-flow-check.md` | task flow checks |

## Skill Design Standard

Use `.agent/skills/skill-design-standard.md` when creating or materially changing a skill.

Core rule:

```text
Trigger metadata decides when the skill is loaded.
The skill body decides what to do after loading.
Validation proves the behavior changed correctly.
```

Project-native `.agent` skills must have:

- `Purpose`
- `Use when`
- `Skip when`
- `Authority`
- `Inputs`
- `Process`
- `Outputs`
- `Validation`
- `Red flags`
- `Completion note`

For user-level Codex skills, the frontmatter `description` must include all important trigger conditions. Do not rely on body sections for discoverability.

Bad descriptions are broad internal-process summaries such as "asks questions, writes a plan, validates work, and updates status" because they do not tell the agent when to use the skill.

## Conflict Handling

- If a skill conflicts with `AGENTS.md`, follow `AGENTS.md`.
- If a skill conflicts with `.agent/STATUS.md`, follow STATUS and update it only within authorized scope.
- If a skill conflicts with the active PLAN, follow the active PLAN unless higher authority says otherwise.
- If Superpowers guidance conflicts with any project-native rule, keep Superpowers advisory only.
- If the user asks to skip validation, keep protected contracts and PLAN acceptance criteria in force.

## Minimum Context Policy

Before loading a skill, read only enough to execute the current task.

Do not bulk-load every skill. Prefer:

- active PLAN
- STATUS
- directly relevant skill
- mandatory check skill for touched module

## Router Dry Runs

| Scenario | Expected route |
|---|---|
| "Fix this failing source test" | systematic debugging, source regression check |
| "Design a new agent workflow" | intent discovery, brainstorming, design brief, plan creator |
| "Brainstorm how our source retrieval should evolve" | brainstorming, then design brief if a direction is selected |
| "Execute current PLAN" | active PLAN, subagent gate contract, relevant validation skills |
| "Execute current PLAN quickly" | execution mode router; default to `local_direct` or `light_subagent` unless hard escalation triggers apply |
| "Continue this source remediation" | execution mode router; use `remediation_gate` for failed live/eval gates before full workflow restart |
| "Should Group2 use fixed workers or task-specific workers?" | group2 worker lane design, then subagent gate contract if execution follows |
| "The PLAN failed live validation" | director remediation gate, systematic debugging, then real-world case design |
| "Design real validation examples for this feature" | real-world case design |
| "Make this skill clearer" | skill design standard |
| "Update EvidenceBundle citation fields" | intent discovery, plan creator, research contract check; stop unless PLAN authorizes protected-contract change |
| "This is done" | verification before completion |
