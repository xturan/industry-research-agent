# Plan: Agentic Operating System v2

Status: completed_pending_human_review
Priority: high
Owner: codex/human
Scope: agent operating model, durable planning, skill governance, validation gates
Created: 2026-04-27
Last Updated: 2026-04-27

## Objective

Upgrade the repository's `.agent` operating model into an Agentic Operating System v2.

The goal is to absorb the useful engineering discipline from the Superpowers methodology while preserving this repository's existing authority model, protected contracts, long-running PLAN workflow, and `invest_*` subagent orchestration.

This plan should make future long-running work more reliable by adding:

- Socratic intake before ambiguous or high-risk tasks.
- Design Briefs before PLAN creation when the task is unclear, creative, or cross-module.
- Skill trigger governance so behavior rules live in focused skills rather than one monolithic prompt.
- PLAN self-review gates before implementation starts.
- Verification-before-completion gates before any completion claim.
- Systematic debugging gates before patching failures.
- Subagent review separation: spec compliance, code quality, functional validation.
- External run traces that record engineering evidence without recording private chain-of-thought.
- Workflow evals and pressure scenarios for changes to AGENTS, PLAN templates, skills, and orchestration.

## Task Classification

Primary area: `eval_policy_ops`

Secondary areas:

- `memory_feedback`
- `task_substrate`
- `research_workflow`
- `source_layer`
- `provider_layer`
- `docs_only`

Current step classification:

- planning-only
- no production code changes
- no `AGENTS.md` changes yet
- no Superpowers plugin activation

## Background Reused

This plan reuses these existing project decisions and conclusions:

- `.agent/STATUS.md` is the current handoff checkpoint.
- `.agent/PLANS/<task>.md` is the durable execution contract for long-running work.
- One primary active long-running PLAN should drive default execution.
- `AGENTS.md` protects EvidenceBundle, citations, research workflow responses, task semantics, source routing, provider boundaries, and delivery contracts.
- The v2 subagent workflow is based on `invest_project_director`, Group 2 workers, Group 3 validators, and `invest_project_summarizer`.
- `domestic-source-lite-refactor-v1.md` proved that explicit continuation rules, validation gates, and live eval artifacts reduce phase-boundary stopping.
- The local Superpowers repository is treated as a reference methodology, not as an authority override.

## Scope

In scope:

- Design the target `.agent` operating model v2.
- Define compatibility rules between existing project governance and Superpowers-inspired workflows.
- Define the authority hierarchy for AGENTS, STATUS, PLAN, skills, memory, traces, and optional external plugins.
- Design a Socratic Intake Gate and Design Brief artifact.
- Design a Skill Router and skill trigger conventions.
- Design PLAN Schema v3 and PLAN self-review checks.
- Design subagent gate sequencing for current `invest_*` roles.
- Design verification-before-completion and systematic-debugging checklists.
- Design external run trace artifacts under `.agent/RUNS/`.
- Design workflow evals and pressure scenarios for future AGENTS/skill/PLAN changes.

Out of scope for this planning step:

- Modifying `AGENTS.md`.
- Modifying production source code.
- Installing or activating Superpowers as a controlling plugin.
- Creating new subagent types.
- Changing protected product contracts.
- Recording or requiring private chain-of-thought.
- Creating mandatory git worktrees or commits for every task.

## Protected Contracts

The following must not change silently in this PLAN:

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
- Domestic source direct-keep boundaries.

If a later implementation phase needs to modify any of these, it must reopen the PLAN with an explicit migration, compatibility, and validation block.

## Authority Model

The project authority order is:

```text
System / developer instructions
  -> repository AGENTS.md
  -> global memory ACTIVE.md / PROFILE.md
  -> .agent/STATUS.md
  -> active .agent/PLANS/<plan>.md
  -> project skills under .agent/skills or user-level Codex skills
  -> optional Superpowers skills as advisory reference only
  -> conversation context
```

Rules:

- Superpowers must not create a competing primary plan path such as `docs/superpowers/plans` for this repository.
- Superpowers must not override `.agent/STATUS.md` as the active checkpoint.
- Superpowers must not bypass the `invest_project_director -> Group 2 -> Group 3 -> summarizer` workflow when the active PLAN requires it.
- Superpowers must not maintain a conflicting long-term memory system alongside `C:\Users\LEGION\.codex\memories`.
- Superpowers-style gates may be adopted only after they are translated into project-native `.agent` skills, PLAN sections, or status rules.
- Completion remains validation-driven, not summary-driven.

## Superpowers Compatibility Position

Use Superpowers as upstream design inspiration in these areas:

| Superpowers concept | Project-native adaptation | Adopt level |
|---|---|---|
| `using-superpowers` bootstrap | `.agent` Skill Router and task trigger matrix | adapt |
| `brainstorming` | `.agent/skills/brainstorming.md` plus Socratic Intake Gate and Design Brief | adopt with lighter weight |
| `writing-plans` | PLAN Schema v3 and PLAN self-review | adopt |
| `executing-plans` | PLAN state machine and continuation rule | adapt |
| `subagent-driven-development` | current `invest_*` role gates | adapt, do not replace |
| `verification-before-completion` | required completion evidence checklist | adopt |
| `systematic-debugging` | root-cause-before-patch gate | adopt |
| `test-driven-development` | test-first where suitable, characterization/live eval for source/provider work | adapt |
| `dispatching-parallel-agents` | use only when user explicitly authorizes subagents and write scopes are disjoint | adapt |
| `using-git-worktrees` | optional for large risky branches, not mandatory for every task | defer |
| trace / transcripts | external engineering trace only; no private chain-of-thought | adapt with boundary |

Do not adopt as-is:

- The global rule that a skill must be invoked on even a 1% chance if it would make routine tasks too heavy.
- The absolute TDD deletion rule for legacy, integration, external API, source crawling, or live-eval contexts.
- Mandatory worktrees for every task.
- A fresh generic subagent for every 2-5 minute step if it conflicts with the existing `invest_*` roles.
- Any instruction that requires recording hidden reasoning or private chain-of-thought.

## Target Architecture

```text
Bootstrap / Policy Layer
  AGENTS.md
  global memories
  .agent/STATUS.md

Skill Router Layer
  .agent/SKILL_ROUTER.md
  .agent/skills/*.md
  user-level Codex skills where explicitly loaded

Durable Planning Layer
  Socratic Intake
  Design Brief
  PLAN Schema v3
  STATUS checkpoint

Execution Orchestration Layer
  invest_project_director
  Group 2 architecture / implementation workers
  Group 3 code quality / functional validation workers
  invest_project_summarizer

Evidence / Trace Layer
  .agent/RUNS/<timestamp>-<task>/
    run.md
    decisions.md
    validation.md
    risks.md
    artifacts/

Workflow Eval Layer
  pressure scenarios
  workflow regression cases
  validation commands
  behavior-change release notes
```

## Proposed Artifacts

Artifacts to design or create in later implementation phases:

| Artifact | Purpose | Initial status |
|---|---|---|
| `.agent/SKILL_ROUTER.md` | Maps task types and trigger phrases to project-native skills and gates | completed |
| `.agent/skills/intent-discovery-gate.md` | Socratic intake rules before ambiguous, risky, or product-design work | completed |
| `.agent/skills/brainstorming.md` | Open-ended option exploration before Design Brief or PLAN | completed |
| `.agent/skills/design-brief-template.md` | Reusable pre-PLAN design brief structure | completed |
| `.agent/skills/plan-self-review.md` | Checks PLAN completeness, placeholders, write scope, validation, high-risk blocks | completed |
| `.agent/skills/verification-before-completion.md` | Requires fresh evidence before completion claims | completed |
| `.agent/skills/systematic-debugging.md` | Requires root cause, reproduction, hypothesis, and focused fix | completed |
| `.agent/skills/tdd-policy.md` | Defines when test-first is required and when characterization/live eval is acceptable | completed |
| `.agent/skills/subagent-gate-contract.md` | Documents director, Group 2, Group 3, and completion gates | completed |
| `.agent/skills/director-remediation-gate.md` | Defines Group 1 limited authority to adjust execution path during failures without changing user goals | completed |
| `.agent/skills/real-world-case-design.md` | Defines Group 3 ownership of realistic case design, negative controls, holdouts, and live eval cases | completed |
| `.agent/skills/skill-design-standard.md` | Defines Superpowers-compatible project-native skill format and trigger standards | completed |
| `.agent/RUNS/README.md` | Defines trace artifacts and chain-of-thought boundary | completed |
| `.agent/evals/workflow-pressure-scenarios.md` | Regression cases for agent behavior under pressure | completed |

## Socratic Intake Policy

Use Socratic Intake before implementation when any of these are true:

- The user's goal is ambiguous.
- The task changes architecture, workflow, protected contracts, data flow, or user-facing behavior.
- The task could become a long-running PLAN.
- The user is asking for product design, agent design, or process design.
- Multiple reasonable strategies exist with different tradeoffs.
- The request could create irreversible or high-cost changes.

Do not overuse Socratic Intake when:

- The user asks a small factual question.
- The user asks for a clearly scoped bug fix with an obvious reproduction.
- The active PLAN already defines the next action and the user says to continue.
- The question is docs-only and low-risk.

Socratic Intake output:

- Objective in one sentence.
- Success criteria.
- Non-goals.
- Known constraints.
- 2-3 viable approaches when relevant.
- Recommended approach with reasoning.
- Questions only if required to avoid a risky assumption.

## Design Brief Policy

For ambiguous or high-risk tasks, produce a Design Brief before creating or modifying a PLAN.

Required Design Brief fields:

- Problem statement.
- User goal.
- Current system constraints.
- Proposed workflow.
- Affected modules and contracts.
- Non-goals.
- Validation strategy.
- Rollback or fallback.
- Open questions.

The Design Brief may be embedded in the PLAN for smaller epics or stored as a separate artifact for larger epics.

## Skill Router Design Rules

Skill descriptions should answer "when to use this skill", not summarize the full workflow.

Good trigger style:

```yaml
description: Use when a task may change protected contracts, long-running workflow state, validation gates, or agent orchestration.
```

Bad trigger style:

```yaml
description: This skill asks questions, writes a plan, validates work, and updates status.
```

Skill governance rules:

- Keep skills narrow and trigger-specific.
- Do not put every project rule into every skill.
- Skills may add gates, but AGENTS and the active PLAN remain higher authority.
- Skills that change agent behavior must include pressure scenarios or validation notes.
- Skill updates should be treated as behavior-changing code, not casual documentation.

## PLAN Schema v3 Requirements

Future long-horizon PLANs should include:

- Status.
- Objective.
- Task classification.
- Background reused.
- Scope.
- Out of scope.
- Protected contracts.
- Authority model if workflows or plugins are involved.
- Architecture direction.
- Agent execution contract.
- Phase state machine.
- Per-phase acceptance criteria.
- Per-phase validation commands.
- Continue rule.
- Stop conditions.
- Done condition.
- Rollback or fallback.
- Progress log.
- Risks and TODOs.
- Next action.

PLAN self-review checks:

- No unresolved placeholders such as `TODO`, `TBD`, `etc`, or "handle appropriately" unless explicitly marked as deferred.
- Write scope is explicit for implementation phases.
- High-risk contracts are listed and protected.
- Validation commands or manual checks are concrete.
- Phase transition conditions are machine-checkable where possible.
- Continuation rule prevents stopping after a summary.
- Stop conditions are explicit.

## Agent Execution Contract

Core principle:

```text
STATUS is the checkpoint.
PLAN is the execution contract and state machine.
Agents are role-bound executors and validators.
```

Role binding:

| Agent | Responsibility | Boundary |
|---|---|---|
| `invest_project_director` | Reads STATUS and active PLAN, freezes the current phase, adds real-world validation, assigns Group 2 and Group 3, decides phase transitions | Does not directly perform broad implementation |
| `invest_agent_architecture_builder` | Designs contracts, orchestration, harnesses, workflow gates, skill schemas, trace structures | Does not rewrite production feature code unless assigned |
| `invest_feature_programmer` | Implements concrete scoped changes, tests, scripts, adapters, services, or docs | Must follow explicit write scope and avoid unauthorized high-risk changes |
| `invest_code_quality_checker` | Runs ruff, compile checks, focused pytest, import safety, and scope review | Does not self-certify product behavior |
| `invest_functional_validator` | Validates practical behavior against the active PLAN, real scenarios, and failure modes | Does not treat code checks alone as functional success |
| `invest_project_summarizer` | Runs only after final done condition to summarize outcomes and capability updates | Does not replace the director during active phases |

Phase state machine:

```text
planned
  -> director_gate
  -> group2_assigned
  -> implemented
  -> code_checked
  -> functionally_validated
  -> phase_completed
  -> next_phase_started
```

## Run Trace Policy

Run traces should record external engineering evidence, not private chain-of-thought.

Allowed trace content:

- Task objective.
- Files read.
- Skills used.
- PLAN and STATUS versions consulted.
- Assumptions.
- Decisions and alternatives considered.
- Commands executed.
- Validation output summaries.
- Artifacts created.
- Risks and TODOs.
- User approvals or blockers.

Not allowed:

- Private chain-of-thought.
- Hidden deliberation transcripts.
- Secrets or API keys.
- Unredacted provider credentials.
- Raw copyrighted content beyond allowed excerpt limits.

Proposed trace structure:

```text
.agent/RUNS/<yyyy-mm-dd-hhmm>-<slug>/
  run.md
  decisions.md
  validation.md
  risks.md
  artifacts/
```

## Validation Loop

For workflow and governance changes, validation must include:

- File existence checks for new skills, router docs, eval docs, or trace templates.
- STATUS points to the active PLAN.
- No production code changed during docs/planning-only phases.
- Protected contracts are not modified unless explicitly authorized.
- Pressure scenarios are added or updated for behavior-changing rules.
- New skills do not require recording private chain-of-thought.
- Completion claims are backed by fresh command output or documented manual checks.

## Workflow Eval Pressure Scenarios

At minimum, future implementation should define scenarios for:

- User asks to skip tests or validation.
- User asks to "just summarize" after one phase when the PLAN says continue.
- User asks to modify EvidenceBundle, citations, provider responses, or task semantics without a PLAN.
- A live eval fails while offline tests pass.
- Tavily or another external API behaves differently than expected.
- The shell environment differs between Windows PowerShell and WSL.
- A secret appears in conversation and must not be persisted.
- `rg` fails with `Access is denied` and a fallback search is required.
- A code quality check passes but functional behavior fails.
- A worker tries to self-certify completion without independent validation.

## Continue Rule

After each milestone, continue automatically to the next milestone when:

- Acceptance criteria are met.
- Required validation passes.
- STATUS and PLAN are updated.
- No missing credential, dependency, network, sandbox, approval, or human-review blocker exists.
- No high-risk contract change is required without explicit authorization.
- The user has not explicitly asked to pause.

Do not treat "summarize this milestone" as the default stopping point.

## Stop Conditions

Stop and request user guidance only when:

- The next step would modify `AGENTS.md` and the PLAN phase has not authorized it.
- The next step would install or activate Superpowers as a controlling plugin.
- A required credential, dependency, runtime, or network path is missing.
- Validation fails and the repair path is unclear or high-risk.
- A protected contract must change.
- The user explicitly asks to pause or only plan.
- The final done condition is reached.

## Done Condition

This PLAN is complete when:

- The authority model is documented and accepted in project-native artifacts.
- Socratic Intake and Design Brief rules exist as project-native skills or docs.
- Skill Router rules exist and map common task classes to gates.
- PLAN Schema v3 and plan self-review checks exist.
- Verification-before-completion and systematic-debugging checks exist.
- Subagent gate sequencing is documented for the current `invest_*` roles.
- Run trace rules exist and explicitly exclude private chain-of-thought.
- Workflow pressure scenarios exist for behavior-changing agent governance.
- STATUS reflects completion or the next active PLAN.
- No protected product contract was modified without explicit authorization.

## Phased Roadmap

### Phase 0: Compatibility Matrix and Authority Freeze

Goal:

- Freeze how Superpowers concepts may be used without conflicting with existing project governance.

Tasks:

- Create a compatibility matrix: adopt, adapt, defer, avoid.
- Freeze the authority hierarchy.
- Identify conflicts with PLAN, STATUS, memory, subagents, validation, and protected contracts.
- Decide which concepts become project-native skills.

Acceptance:

- `.agent/STATUS.md` points to this PLAN.
- The plan clearly states Superpowers is advisory, not authoritative.
- No ambiguity remains about which plan/status/memory system is canonical.

Validation:

- Confirm this PLAN exists.
- Confirm STATUS points to this PLAN.
- Confirm no production code changed.

Current state:

- completed_with_scope_risk

Phase 0 artifact:

- `.agent/PLANS/agentic-operating-system-v2-phase0-authority-freeze.md`

Validation snapshot:

- Confirmed `.agent/PLANS/agentic-operating-system-v2.md` exists.
- Confirmed `.agent/STATUS.md` points to this PLAN.
- Confirmed Phase 0 stayed docs/governance-only within `.agent`.
- Confirmed no production code, schema, provider, source, task, `AGENTS.md`, or Superpowers activation change was made by this phase.
- Group 3 functional governance validation passed all four dry-run scenarios:
  - Superpowers conflict.
  - Request to edit `AGENTS.md`.
  - Request to change protected contracts.
  - Worker self-certifies without Group 3 validation.
- Group 3 code-quality/scope validation passed artifact/content checks, but flagged a scope-proof risk:
  - the working tree was already dirty, including `AGENTS.md` and production files, before Phase 0 validation;
  - `.agent` is untracked from git's perspective;
  - therefore git cannot independently prove that Phase 0 introduced no non-`.agent` changes without a baseline, even though Phase 0 artifacts do not authorize such changes.

Next action:

- Resolve or explicitly accept the dirty-worktree scope-proof risk before Phase 1 auto-advance.
- If accepted, Phase 1 should define the Socratic Intake and Design Brief project-native skills.

### Phase 1: Socratic Intake and Design Brief

Goal:

- Add a lightweight pre-implementation design gate for ambiguous, high-risk, or product-design tasks.

Tasks:

- Define `.agent/skills/intent-discovery-gate.md`.
- Define `.agent/skills/design-brief-template.md`.
- Define when to ask questions and when to proceed with pragmatic assumptions.
- Add pressure scenarios for users asking to skip planning.

Acceptance:

- A future Codex session can decide whether to ask clarifying questions, create a brief, or execute directly.
- The rule does not block small low-risk tasks.

Validation:

- Dry-run against at least three task examples: small bug fix, ambiguous product design, high-risk workflow change.

Current state:

- completed

Artifacts:

- `.agent/skills/intent-discovery-gate.md`
- `.agent/skills/brainstorming.md`
- `.agent/skills/design-brief-template.md`

Validation snapshot:

- Dry-run examples cover small bug fix, ambiguous product design, and high-risk protected-contract change.
- Skill rules define when to ask questions versus proceed with pragmatic assumptions.
- Brainstorming now has an explicit project-native skill for option exploration, recommendation, validation framing, and transition into Design Brief / PLAN.

### Phase 2: Skill Router and Trigger Governance

Goal:

- Move recurring behavior rules into narrow, triggerable project-native skills.

Tasks:

- Create `.agent/SKILL_ROUTER.md`.
- Map task classes to skills and validation gates.
- Define skill description conventions.
- Define skill update governance and eval expectations.

Acceptance:

- The router avoids monolithic prompt growth.
- Skill triggers are based on "when to use", not workflow summaries.

Validation:

- Dry-run router decisions for source work, provider work, research workflow changes, docs-only changes, and debugging.

Current state:

- completed

Artifact:

- `.agent/SKILL_ROUTER.md`

Validation snapshot:

- Router maps source, provider, research, task, docs, debugging, PLAN, and completion tasks to project-native skills.
- Router dry-runs cover source test failure, agent workflow design, PLAN execution, protected-contract edits, and completion claims.

### Phase 3: PLAN Schema v3 and Plan Self-Review

Goal:

- Make future PLANs more executable, reviewable, and continuation-safe.

Tasks:

- Create `.agent/skills/plan-self-review.md`.
- Define PLAN Schema v3.
- Add placeholder scan, write-scope review, protected-contract review, and validation completeness review.
- Define plan upgrade path for existing active plans.

Acceptance:

- Future PLANs can be reviewed before implementation starts.
- "Phase-only" plans are rejected unless they include continuation and validation gates.

Validation:

- Run self-review against this PLAN and the completed domestic-source plan.

Current state:

- completed

Artifact:

- `.agent/skills/plan-self-review.md`

Validation snapshot:

- Review checks cover authority, scope, protected contracts, validation, continuation, placeholders, and red flags.
- Dirty-worktree scope risk is explicitly modeled as a review concern.

### Phase 4: Subagent Gate Refactor

Goal:

- Align Superpowers-style review separation with the existing `invest_*` subagent system.

Tasks:

- Define director gate, Group 2 implementation gate, Group 3 validation gate, and summarizer gate.
- Define when subagents are required and when local execution is enough.
- Define disjoint write-scope expectations for parallel workers.
- Define reviewer independence rules.

Acceptance:

- Workers cannot self-certify completion.
- Spec compliance, code quality, and functional validation are separate concepts.

Validation:

- Dry-run against a source-layer phase, a docs-only phase, and a provider-layer phase.

Current state:

- completed

Artifact:

- `.agent/skills/subagent-gate-contract.md`

Validation snapshot:

- Gate contract separates director, Group 2, Group 3 code-quality, Group 3 functional validation, and completion gates.
- Dry-runs cover source-layer, docs-only, and provider-layer phases.

### Phase 5: Verification and Debugging Skills

Goal:

- Make completion and debugging evidence-driven.

Tasks:

- Create `.agent/skills/verification-before-completion.md`.
- Create `.agent/skills/systematic-debugging.md`.
- Create `.agent/skills/tdd-policy.md`.
- Define how source/provider live evals fit into test policy.

Acceptance:

- No agent should claim completion without fresh evidence.
- No agent should patch a bug without a reproduction or root-cause hypothesis unless explicitly doing exploratory triage.

Validation:

- Pressure-test with a failing command, a flaky external API, and a user request to skip tests.

Current state:

- completed

Artifacts:

- `.agent/skills/verification-before-completion.md`
- `.agent/skills/systematic-debugging.md`
- `.agent/skills/tdd-policy.md`

Validation snapshot:

- Verification skill requires fresh evidence before completion claims.
- Debugging skill requires exact failure capture, classification, root-cause hypothesis, focused fix, and re-validation.
- TDD policy distinguishes test-first, characterization tests, live evals, and manual governance dry-runs.

### Phase 6: Run Trace and Decision Evidence

Goal:

- Add durable, auditable execution traces without storing private chain-of-thought.

Tasks:

- Create `.agent/RUNS/README.md`.
- Define trace file names and required fields.
- Define redaction rules for secrets and API keys.
- Define when a trace is required.

Acceptance:

- Another session can audit what happened without relying on hidden conversation memory.
- The trace boundary clearly excludes private chain-of-thought.

Validation:

- Create one sample trace for a docs-only task and verify no secrets or hidden reasoning are required.

Current state:

- completed

Artifacts:

- `.agent/RUNS/README.md`
- `.agent/RUNS/2026-04-27-agentic-os-v2-docs-governance/run.md`
- `.agent/RUNS/2026-04-27-agentic-os-v2-docs-governance/decisions.md`
- `.agent/RUNS/2026-04-27-agentic-os-v2-docs-governance/validation.md`
- `.agent/RUNS/2026-04-27-agentic-os-v2-docs-governance/risks.md`

Validation snapshot:

- Trace format stores external engineering evidence only.
- Sample docs-governance trace records objective, context read, decisions, validation, risks, and next action without secrets or private chain-of-thought.

### Phase 7: Workflow Evals and Pressure Scenarios

Goal:

- Treat behavior-changing rules like testable software.

Tasks:

- Create `.agent/evals/workflow-pressure-scenarios.md`.
- Define scenario format: setup, expected trigger, forbidden shortcut, pass condition.
- Add cases for phase-boundary stopping, skipped validation, high-risk contract edits, live-vs-offline mismatch, shell mismatch, and secret handling.

Acceptance:

- Future changes to AGENTS, skills, and PLAN templates have regression scenarios.

Validation:

- Manually dry-run at least five pressure scenarios.

Current state:

- completed

Artifact:

- `.agent/evals/workflow-pressure-scenarios.md`

Validation snapshot:

- Ten pressure scenarios exist, including skipped validation, phase-boundary stopping, protected contract edits, live-vs-offline mismatch, shell mismatch, secret handling, worker self-certification, dirty worktree risk, Superpowers conflict, and functional failure after code checks pass.

### Phase 8: Optional Superpowers Advisory Mode

Goal:

- Decide whether to install, activate, or keep Superpowers as a reference-only plugin.

Tasks:

- Review compatibility after project-native skills exist.
- Decide whether Superpowers adds value beyond the native `.agent` operating system.
- If activation is desired, define a strict compatibility contract.

Acceptance:

- Superpowers is either explicitly deferred or activated only as advisory.
- It does not override PLAN, STATUS, memory, protected contracts, or subagent flow.

Validation:

- Confirm no competing plan/status/memory paths are created.

Current state:

- completed

Artifact:

- `.agent/PLANS/agentic-operating-system-v2-phase8-superpowers-advisory.md`

Validation snapshot:

- Superpowers remains advisory only.
- No Superpowers plugin installation or activation occurred.
- Reopen criteria require explicit PLAN authorization and compatibility validation.

## Progress

- 2026-04-27: Created this PLAN as the new primary active long-running plan.
- 2026-04-27: Preserved `domestic-source-lite-refactor-v1.md` as completed and pending human archive.
- 2026-04-27: Planning step only; no production code or `AGENTS.md` changes.
- 2026-04-27: Completed Phase 0 by creating `.agent/PLANS/agentic-operating-system-v2-phase0-authority-freeze.md`; authority hierarchy, Superpowers compatibility, conflict rules, skill migration candidates, and four governance dry-runs are now frozen.
- 2026-04-27: Group 3 validation passed Phase 0 artifact and dry-run checks, but scope cleanliness is inconclusive because the repository already had unrelated dirty/untracked files, including `AGENTS.md` and production paths.
- 2026-04-27: User accepted the dirty-worktree scope-proof risk by instructing continuation; subsequent writes remained `.agent`-only.
- 2026-04-27: Completed Phase 1 by creating Socratic Intake, Brainstorming, and Design Brief project-native skills.
- 2026-04-27: Completed Phase 2 by creating `.agent/SKILL_ROUTER.md`.
- 2026-04-27: Completed Phase 3 by creating `.agent/skills/plan-self-review.md`.
- 2026-04-27: Completed Phase 4 by creating `.agent/skills/subagent-gate-contract.md`.
- 2026-04-27: Completed Phase 5 by creating verification, systematic debugging, and TDD policy skills.
- 2026-04-27: Completed Phase 6 by creating `.agent/RUNS/README.md` and a docs-governance sample trace.
- 2026-04-27: Completed Phase 7 by creating `.agent/evals/workflow-pressure-scenarios.md`.
- 2026-04-27: Completed Phase 8 by creating the Superpowers advisory decision artifact.
- 2026-04-27: Final docs/governance validation passed: required artifacts exist, STATUS and PLAN show `completed_pending_human_review`, no Tavily credential prefix match was found under `.agent`, and no production tests were required because no production code was intentionally changed.
- 2026-04-27: Added missing explicit `.agent/skills/brainstorming.md` after human review identified that the Superpowers `brainstorming` concept had been compressed into intake/design-brief artifacts without preserving a discoverable skill name.
- 2026-04-27: Added review corrections for Group1/Group3 workflow and skill design standards:
  - `.agent/skills/director-remediation-gate.md`
  - `.agent/skills/real-world-case-design.md`
  - `.agent/skills/skill-design-standard.md`
  - updated `.agent/SKILL_ROUTER.md`, `.agent/skills/subagent-gate-contract.md`, and workflow pressure scenarios.
- 2026-04-27: Redesigned `.agent/skills/brainstorming.md` after human review found the first version too lightweight. The new version adapts Superpowers' stronger process discipline into project-native form: context exploration, assumption ledger, one-question-at-a-time Socratic loop, real options, recommendation, pressure test, staged design sections, and Design Brief/PLAN exit.

## Risks and Rollback

Risks:

- Over-adopting Superpowers could make routine tasks too heavy.
- Competing plan/status/memory systems could fragment project state.
- Skill proliferation could reduce clarity if triggers are vague.
- Mandatory gates could slow urgent low-risk fixes.
- Trace design could accidentally encourage recording private reasoning unless the boundary is explicit.
- Workflow changes could become prompt-only unless paired with validation and pressure scenarios.
- Git-based scope proof remains inconclusive because the repository had pre-existing dirty/untracked `AGENTS.md`, production, docs, tests, scripts, and data files before this continuation.

Rollback:

- Keep Superpowers advisory until project-native artifacts are created.
- Do not edit `AGENTS.md` until a later phase explicitly authorizes it.
- If the new operating model proves too heavy, keep only verification, debugging, and plan self-review gates.
- If a skill creates confusion, remove it from `.agent/SKILL_ROUTER.md` while preserving the higher-level PLAN/STATUS rules.

## Next Action

This PLAN has reached its done condition and is pending human review.

Recommended next options:

- Review the new `.agent` operating artifacts and decide whether to promote any stable rules into `AGENTS.md` under a separate PLAN.
- Create the next product PLAN, likely `research-workflow-source-assisted-integration-v1.md`.
- Keep Superpowers advisory unless a future PLAN explicitly reopens plugin activation.
