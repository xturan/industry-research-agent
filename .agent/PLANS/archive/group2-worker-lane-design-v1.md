# Plan: Group2 Worker Lane Design v1

Status: completed
Priority: high
Owner: codex/human
Scope: agent operating model, Group2 worker design, subagent routing, validation gates
Created: 2026-04-27
Last Updated: 2026-04-27

## Objective

Adopt the selected Group2 design: fixed capability lanes plus task-specific worker instances.

The goal is to make Group2 worker assignment concrete enough that architecture work participates when it should, implementation work remains scoped, and Superpowers-style task-specific execution can be used without replacing the repository's `invest_*` workflow.

## Task Classification

Primary area: `eval_policy_ops`

Secondary areas:

- `task_substrate`
- `memory_feedback`
- `docs_only`

Current step classification:

- docs/governance implementation
- no production code changes
- no `AGENTS.md` changes
- no protected product contract changes

## Background Reused

This plan reuses:

- `.agent/STATUS.md` as the active checkpoint.
- `.agent/PLANS/agentic-operating-system-v2.md` as the completed parent governance plan.
- `.agent/skills/subagent-gate-contract.md` as the current director -> Group2 -> Group3 contract.
- `.agent/skills/skill-design-standard.md` for project-native skill format.
- `.agent/evals/workflow-pressure-scenarios.md` for governance pressure scenarios.
- User-selected option 2: fixed capability lanes plus task-specific worker instances.

## Scope

In scope:

- Define Group2 capability lanes.
- Define how existing `invest_agent_architecture_builder` and `invest_feature_programmer` map to lanes.
- Define when architecture work must produce an Architecture Gate before implementation.
- Define how task-specific worker instances are assigned inside a stable lane.
- Update subagent routing and pressure scenarios.
- Update STATUS with the new operating model state.

Out of scope:

- Creating new real subagent types in runtime configuration.
- Editing `AGENTS.md`.
- Modifying production code.
- Changing task/job status semantics.
- Changing EvidenceBundle, citation, provider, research response, source routing, or delivery contracts.
- Installing or activating Superpowers as a controlling plugin.

## Protected Contracts

No protected product contracts may change in this plan.

Protected contracts remain:

- EvidenceBundle schema.
- EvidenceItem citation fields.
- `source_quality_summary` shape.
- Research analyze response shape.
- Provider abstraction semantics.
- Source routing response shape.
- Task/job status semantics.
- `run` / `run_steps` meaning.
- Content asset metadata contract.
- Delivery state transition behavior.

## Design Direction

Use this model:

```text
stable capability lane = persistent responsibility, standards, and boundaries
task-specific worker instance = one scoped execution assignment inside that lane
```

Group2 should not become a large set of permanent narrow agents yet. Instead:

- keep the existing specialized subagents;
- add project-native lane semantics around them;
- assign each execution with a lane, objective, write scope, forbidden scope, and required output;
- require an Architecture Gate when a task can change contracts, orchestration, workflow state, or validation strategy.

## Group2 Lane Model

Initial lanes:

| Lane | Backing subagent | Responsibility | Required output |
|---|---|---|---|
| `system_contract_architect` | `invest_agent_architecture_builder` | Contracts, boundaries, state machines, orchestration, PLAN/skill/subagent design, trace structure, migration risk | Architecture Gate |
| `source_provider_integrator` | `invest_feature_programmer` with lane role card | Tavily, Crawl4AI, source routing, provider adapters, direct-keep boundaries, provider metadata | scoped patch plus source/provider validation notes |
| `research_workflow_implementer` | `invest_feature_programmer` with lane role card | Research workflow integration, evidence handoff, API surface wiring, trace metadata | scoped patch plus workflow validation notes |
| `eval_harness_implementer` | `invest_feature_programmer` with lane role card | Offline/live eval runners, test scripts, harness utilities, usage/cost trace helpers | scoped patch plus harness usage notes |

Group3 remains responsible for final real-world case design and functional validation. Group2 may suggest cases but must not be the only case designer.

## Architecture Gate Trigger

The director must assign `system_contract_architect` before implementation when any of these are true:

- The phase touches protected contracts or their boundaries.
- The phase changes provider/source routing semantics.
- The phase changes research workflow stages, evidence handoff, trace structure, or public response shape.
- The phase changes task/worker behavior, run lifecycle, or validation gates.
- The phase introduces a new source/provider integration path.
- Live validation fails in a way that suggests a boundary, routing, contract, or case-design problem rather than a local bug.
- Multiple Group2 lanes must write related behavior and need implementation slicing.

The director may skip the Architecture Gate only when the task is narrow, local, and already has a frozen implementation slice in the PLAN.

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

## Agent Execution Contract

```text
invest_project_director
  -> classify phase and lane needs
  -> require Architecture Gate if trigger matches
  -> freeze task-specific worker instance contract
  -> assign one or more Group2 lanes with disjoint write scopes
  -> route implementation to lane-backed workers
  -> Group3 code-quality validation
  -> Group3 real-world case design where behavior matters
  -> Group3 functional validation
  -> record results in PLAN and STATUS
```

Every Group2 task instance must include:

- lane name;
- backing subagent;
- objective;
- files or modules owned;
- forbidden paths/contracts;
- required output;
- validation expected from the worker;
- Group3 validation required before completion.

## Phases

### Phase 0: Planning and Authority Freeze

Acceptance:

- Dedicated PLAN exists before worker-behavior docs are changed.
- STATUS can point to this PLAN while implementation proceeds.
- Protected contracts and out-of-scope changes are listed.

Validation:

- PLAN file exists.
- PLAN includes objective, scope, protected contracts, lane model, validation, risks, and next action.

Current state:

- completed

### Phase 1: Lane Skill and Router Update

Acceptance:

- New project-native skill defines Group2 worker lanes and task instance format.
- Skill follows `.agent/skills/skill-design-standard.md`.
- `.agent/SKILL_ROUTER.md` routes Group2 worker design and architecture-gate questions to the new skill.

Validation:

- `Select-String` confirms required skill sections.
- Router entry exists.

Current state:

- completed

### Phase 2: Subagent Gate Contract Update

Acceptance:

- `.agent/skills/subagent-gate-contract.md` references Group2 lanes.
- Architecture Gate trigger and required output are documented.
- Group2 task-specific worker instance requirements are documented.

Validation:

- `Select-String` confirms lane names, Architecture Gate, and task-specific worker instance terms.

Current state:

- completed

### Phase 3: Pressure Scenario and STATUS Update

Acceptance:

- Workflow pressure scenarios include architecture-builder bypass and lane-overproliferation risks.
- `.agent/STATUS.md` records this plan and latest validation snapshot.
- No production code or `AGENTS.md` changes are made.

Validation:

- File/content checks pass.
- `git status --short -- .agent AGENTS.md packages` is reviewed for scope risk.

Current state:

- completed

## Continue Rule

After each phase, continue automatically when:

- acceptance criteria are met;
- validation passes;
- no protected contract change is required;
- no production code edit is required;
- no user pause is requested.

Do not stop after a phase summary if the next phase is safe and in scope.

## Stop Conditions

Stop and ask for user guidance only when:

- implementing this design requires editing `AGENTS.md`;
- runtime subagent configuration must change;
- a protected product contract must change;
- validation fails and the repair path is unclear;
- the user asks to pause.

## Done Condition

This plan is complete when:

- Group2 lane design exists as a project-native skill.
- Skill router and subagent gate contract reference the lane model.
- Pressure scenarios cover architecture bypass and lane proliferation.
- STATUS reflects the new completed state.
- Validation checks pass or risks are recorded.

## Validation Loop

Required checks:

```powershell
Select-String -Path '.agent\skills\group2-worker-lane-design.md' -Pattern 'Purpose','Use when','Skip when','Authority','Inputs','Process','Outputs','Validation','Red flags','Completion note'
Select-String -Path '.agent\SKILL_ROUTER.md','.agent\skills\subagent-gate-contract.md','.agent\evals\workflow-pressure-scenarios.md' -Pattern 'group2-worker-lane-design','Architecture Gate','system_contract_architect','task-specific worker instance','WPS-015','WPS-016'
git status --short -- .agent AGENTS.md packages
```

Production tests are not required unless production code changes.

## Progress

- 2026-04-27: Created plan for user-selected option 2: fixed Group2 capability lanes plus task-specific worker instances.
- 2026-04-27: Completed Phase 1 by creating `.agent/skills/group2-worker-lane-design.md` and adding a router entry for Group2 worker identity, lane assignment, architecture-builder participation, and task-specific worker instances.
- 2026-04-27: Completed Phase 2 by updating `.agent/skills/subagent-gate-contract.md` with Group2 lanes, Architecture Gate triggers, required Architecture Gate output, and research workflow integration dry-run flow.
- 2026-04-27: Completed Phase 3 by adding workflow pressure scenarios `WPS-015` and `WPS-016` for architecture-worker bypass and lane overproliferation.
- 2026-04-27: Validation passed for skill section presence, router/gate/eval keyword coverage, and scope review. Production tests were not run because this plan changed only `.agent` governance artifacts.
- 2026-04-28: Human review accepted the Group2 lane design. Status moved from `completed_pending_human_review` to `completed`. No production code, runtime subagent configuration, `AGENTS.md`, or protected product contracts changed.

## Validation Snapshot

Completed checks:

```powershell
Select-String -Path '.agent\skills\group2-worker-lane-design.md' -Pattern 'Purpose','Use when','Skip when','Authority','Inputs','Process','Outputs','Validation','Red flags','Completion note'
Select-String -Path '.agent\SKILL_ROUTER.md','.agent\skills\subagent-gate-contract.md','.agent\evals\workflow-pressure-scenarios.md' -Pattern 'group2-worker-lane-design','Architecture Gate','system_contract_architect','task-specific worker instance','WPS-015','WPS-016'
git status --short -- .agent AGENTS.md packages
```

Results:

- New skill contains required project-native skill sections.
- Router, subagent gate contract, and pressure scenarios contain required Group2 lane and Architecture Gate terms.
- `git status` still shows pre-existing dirty/untracked `AGENTS.md` and production paths; `.agent` is untracked, so git cannot independently prove clean scope without a baseline.
- No production code, `AGENTS.md`, runtime subagent configuration, or protected product contracts were intentionally modified by this plan.

## Risks and Rollback

Risks:

- More lanes may make director assignment heavier if prompts are vague.
- Architecture Gate could become performative if not treated as a blocking artifact.
- Existing runtime only has two Group2 backing subagents, so some lanes initially map to `invest_feature_programmer` via role cards.
- Dirty worktree already contains unrelated production and `AGENTS.md` changes, so git scope proof remains inconclusive.

Rollback:

- Remove the new router entry and skill.
- Revert `subagent-gate-contract.md` to the prior two-worker wording.
- Keep Group3 validation and existing v2 workflow unchanged.

## Next Action

No execution action remains for this PLAN.

Recommended follow-up:

- Use `.agent/skills/group2-worker-lane-design.md` during future product PLAN execution.
- Defer promoting the rule into `AGENTS.md` until it proves stable across at least one real PLAN execution.
- If promotion into `AGENTS.md` is desired, create a separate behavior-governance PLAN with validation.
