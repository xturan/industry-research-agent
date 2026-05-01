# Skill: subagent-gate-contract

## Purpose

Use this skill when a PLAN phase is executed through role-bound subagents or when a worker claims a phase is complete.

The contract keeps implementation, code quality, and functional validation separate.

This skill is no longer the default first step for every PLAN execution. Use `.agent/skills/execution-mode-router.md` first unless the active PLAN or user instruction already requires the full v2 subagent workflow.

## Use when

Use this skill when:

- The user explicitly asks to execute a PLAN with subagents or parallel agents.
- The active PLAN requires the v2 subagent workflow.
- `.agent/skills/execution-mode-router.md` selects `full_subagent`.
- A phase has architecture, implementation, and validation work that should not be self-certified.
- Multiple workers may touch disjoint write scopes.

## Skip when

Skip this skill when:

- `.agent/skills/execution-mode-router.md` selects `local_direct` and the task has no protected-contract or cross-module risk.
- `.agent/skills/execution-mode-router.md` selects `light_subagent` and no director/architecture gate is needed.
- The task is docs-only and focused file/content checks are enough.

## Role flow

```text
invest_project_director
  -> freeze phase objective and validation
  -> open director remediation gate when execution fails or scope changes
  -> classify Group 2 lane needs
  -> require Architecture Gate when lane triggers apply
  -> assign Group 2 task-specific worker instances
  -> Group 2 implements or designs within lane write scope
  -> Group 3 code-quality validation
  -> Group 3 real-world case design when practical behavior matters
  -> Group 3 functional validation
  -> director records phase transition
  -> invest_project_summarizer only after final done condition
```

## Gate requirements

### Director gate

- Reads STATUS and active PLAN.
- Confirms current phase and write scope.
- Confirms protected contracts.
- Adds real-world validation where needed.
- Assigns workers only with explicit ownership.
- Uses `director-remediation-gate.md` when blockers, failed validation, ambiguous requirements, or scope risks appear.
- May refine execution path inside the existing user goal.
- Must not silently change the user goal or protected contracts.

### Group 2 gate

- Works only inside assigned scope.
- Does not revert unrelated dirty work.
- Does not modify protected contracts unless the PLAN authorizes it.
- Reports changed paths and validation performed.
- Uses `.agent/skills/group2-worker-lane-design.md` when assigning or executing Group2 work through lanes.
- Every non-trivial Group2 assignment should name one primary lane and one backing subagent.
- A Group2 task-specific worker instance must define objective, owned files/modules, forbidden paths/contracts, required output, worker validation, and required Group3 validation.

### Group 2 lane model

Group2 uses fixed capability lanes plus task-specific worker instances.

| Lane | Backing subagent | Responsibility |
|---|---|---|
| `system_contract_architect` | `invest_agent_architecture_builder` | contracts, boundaries, state machines, orchestration, PLAN/skill/subagent design, trace structures, migration risk |
| `source_provider_integrator` | `invest_feature_programmer` with lane role card | Tavily, Crawl4AI, source routing, provider adapters, direct-keep boundaries, provider metadata |
| `research_workflow_implementer` | `invest_feature_programmer` with lane role card | research workflow integration, evidence handoff, API surface wiring, trace metadata |
| `eval_harness_implementer` | `invest_feature_programmer` with lane role card | offline/live eval runners, harness scripts, usage/cost trace helpers |

### Model cost gate

- Standard reasoning effort for project subagents is `medium`.
- Default `gpt-5.5` usage is disabled for project subagents; use `gpt-5.4` for director, summarizer, architecture, and functional validation roles.
- Use `gpt-5.3-codex` for concrete code implementation by default.
- Use `gpt-5.3-codex-spark` for high-frequency, short-duration mechanical validation tasks such as ruff/compile/focused pytest checks.
- Do not downgrade protected-contract architecture decisions, source-quality judgment, or functional validation to Spark unless the active PLAN explicitly accepts the quality/cost tradeoff.

### Architecture Gate

The director must assign `system_contract_architect` before implementation when any of these are true:

- The task may touch protected contracts or their boundaries.
- The task changes provider/source routing semantics.
- The task changes research workflow stages, evidence handoff, trace structure, or public response shape.
- The task changes task/worker behavior, run lifecycle, or validation gates.
- The task introduces a new source/provider integration path.
- Live validation fails in a way that suggests boundary, routing, contract, or case-design issues.
- Multiple Group2 lanes must coordinate related behavior or disjoint implementation slices.

Required Architecture Gate output:

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

### Group 3 code-quality gate

- Checks scope correctness.
- Runs relevant lint, compile, tests, or docs checks.
- Reports failures and unrelated dirty-worktree risks.
- Does not certify functional success alone.

### Group 3 functional gate

- Tests behavior against the PLAN acceptance criteria.
- Uses practical scenarios, evals, or dry-runs.
- Treats "tests pass" as insufficient if behavior does not match the PLAN.
- Uses `real-world-case-design.md` when realistic validation cases, negative controls, holdouts, live evals, or evidence-quality checks are needed.
- Owns final case design for practical behavior validation; Group 2 may suggest cases but must not be the sole case designer.

### Completion gate

- Phase is complete only when required code-quality and functional gates pass or blockers are recorded.
- STATUS and PLAN are updated.
- Next phase is selected unless a stop condition applies.

## Red flags

- A worker says "done" without Group 3 validation.
- A worker edits outside assigned write scope.
- A Group2 worker receives a broad assignment without a lane, owned scope, and forbidden scope.
- `invest_agent_architecture_builder` is bypassed when an Architecture Gate trigger applies.
- A validator only reads the worker summary and does not inspect artifacts.
- Multiple workers share the same write files without coordination.
- A phase transition is recorded without validation evidence.
- Group 1 changes the product goal under the label of remediation.
- Group 2 designs the only real-world cases used to judge its own work.

## Dry-run examples

### Source-layer phase

Expected flow:

- Director freezes source-layer scope and protected source/evidence contracts.
- Director assigns `system_contract_architect` first if source routing semantics, provider boundaries, or evidence handoff may change.
- Group 2 assigns `source_provider_integrator` for scoped source/provider implementation.
- Code-quality validator runs source regression and import checks.
- Functional validator runs representative source queries or eval cases.

### Docs-only phase

Expected flow:

- Director may assign local execution or a docs worker.
- Code-quality validation is file existence, content, link, and scope review.
- Functional validation is dry-run against the governance scenario.
- No production tests are required unless docs change executable behavior.

### Provider-layer phase

Expected flow:

- Director freezes provider abstraction and response-shape constraints.
- `system_contract_architect` produces an Architecture Gate if provider abstraction semantics or public response shape may change.
- `source_provider_integrator` implements provider changes within explicit files.
- Code-quality validator runs ruff, compile, and provider tests.
- Functional validator verifies provider selection, metadata, and failure transparency.

### Research workflow integration phase

Expected flow:

- Director freezes EvidenceBundle, citation, source routing, and research response boundaries.
- `system_contract_architect` produces an Architecture Gate for evidence handoff and response-surface risk.
- `research_workflow_implementer` implements scoped workflow/API/trace wiring.
- `eval_harness_implementer` implements offline/live eval runners if needed.
- Group 3 owns final real-world case design and functional validation.

## Completion note

Record gate results in the active PLAN and `.agent/STATUS.md`.
