# Invest Agent Subagent Operating Model v2

## 1. Core Rule

PLAN is the strict construction blueprint.

Every non-trivial task must start from the active PLAN, not from hidden conversation memory. The active PLAN must contain:

- objective
- scope
- constraints
- current phase
- concrete worker assignments
- real-world validation plan
- validation results
- risks
- next action

The subagent workflow exists to keep implementation, testing, and post-plan review aligned with that blueprint.

## 2. Role Count

Use 6 project-specific subagents.

| Group | Count | Agents |
| --- | ---: | --- |
| Group 1: management | 2 | `invest_project_director`, `invest_project_summarizer` |
| Group 2: execution | 2 | `invest_agent_architecture_builder`, `invest_feature_programmer` |
| Group 3: validation | 2 | `invest_code_quality_checker`, `invest_functional_validator` |

This replaces the previous 10-agent design. The new model is intentionally simpler:

- Group 1 owns planning and post-plan review.
- Group 2 owns architecture construction and concrete implementation.
- Group 3 owns code checks and practical feature validation.

## 2.1 Model And Reasoning Cost Policy

Default model policy:

| Agent | Default model | Reasoning effort | Cost policy |
| --- | --- | --- | --- |
| `invest_project_director` | `gpt-5.4` | `medium` | Standard planning and routing quality without GPT-5.5 cost. |
| `invest_project_summarizer` | `gpt-5.4` | `medium` | Standard completion review; upgrade only for unusually complex postmortems. |
| `invest_agent_architecture_builder` | `gpt-5.4` | `medium` | Architecture quality retained while reducing high-reasoning cost. |
| `invest_feature_programmer` | `gpt-5.3-codex` | `medium` | Coding-optimized default; do not downgrade core implementation to Spark by default. |
| `invest_code_quality_checker` | `gpt-5.3-codex-spark` | `medium` | High-frequency, short validation tasks should use the cheaper fast coding model. |
| `invest_functional_validator` | `gpt-5.4` | `medium` | Practical validation still needs stronger judgment than Spark by default. |

Rules:

- Treat `medium` as the standard reasoning speed for project subagents.
- Do not use `gpt-5.5` by default in project subagents unless the user explicitly reopens a high-complexity gate.
- Prefer `gpt-5.3-codex-spark` for repeated short tasks such as compile/lint/test summarization and narrow mechanical checks.
- Prefer `gpt-5.4` for planning, architecture judgment, functional validation, and source-quality interpretation.
- Prefer `gpt-5.3-codex` for concrete implementation that edits code.

## 3. Group 1: Management

### `invest_project_director`

Use first for every non-trivial plan-driven task.

Primary responsibilities:

- Understand project status, repository mission, and current active PLAN.
- Treat the current PLAN as the strict construction blueprint.
- Before Group 2 starts work, design how the current PLAN will be validated in a real scenario.
- Write that validation design into the active PLAN so Group 3 can execute it later.
- Break the current PLAN phase into concrete worker assignments.
- Decide whether Group 2 needs:
  - `invest_agent_architecture_builder`
  - `invest_feature_programmer`
- Decide whether Group 3 needs:
  - `invest_code_quality_checker`
  - `invest_functional_validator`
- Update the PLAN after meaningful progress.

The project director does not primarily write feature code. Its job is to keep the work aligned with the PLAN.

Required output:

```text
task_classification:
active_plan_summary:
real_world_validation_plan:
group2_assignments:
group3_assignments:
phase_gates:
risks:
next_action:
```

### `invest_project_summarizer`

Use after a PLAN is completed.

Primary responsibilities:

- Review the completed PLAN and validation evidence.
- Summarize what changed and what remains risky.
- Evaluate current and future project needs created by this PLAN.
- Check whether Group 2 or Group 3 worker capability definitions need updates.
- If no capability update is needed, explicitly state that no update is needed.
- Recommend the next active PLAN, or mark that no active long-running PLAN exists.

The project summarizer should not rewrite worker roles for one-off issues. It only updates the operating model when a repeated or structural need appears.

Required output:

```text
completed_plan_summary:
validation_summary:
remaining_risks:
future_project_needs:
worker_capability_update_needed:
recommended_status_update:
```

## 4. Group 2: Execution

### `invest_agent_architecture_builder`

Use when the task is about agent or harness engineering architecture.

Primary responsibilities:

- Design or build agent architecture.
- Define orchestration contracts.
- Design task handoff shapes.
- Create tool/provider abstraction boundaries.
- Add execution scaffolding.
- Connect PLAN-driven validation hooks.
- Keep architecture compatible with future MCP-style tool adapters.

Typical tasks:

- build a new agent orchestration layer
- define agent handoff payloads
- design run trace or execution-log architecture
- refactor a prompt-only agent path into typed contracts
- update `.codex/agents/` or agent workflow docs when structurally necessary

Required output:

```text
architecture_intent:
files_changed:
contracts_touched:
validation_run:
risks:
next_architecture_step:
```

### `invest_feature_programmer`

Use for concrete implementation work.

Primary responsibilities:

- Write scoped production code.
- Implement specific feature requests from the active PLAN.
- Add or update tools, services, scripts, endpoints, tests, or source retrieval logic.
- Follow existing repository patterns.
- Run assigned checks and report exact results.

Typical tasks:

- change source retrieval behavior
- add a new source/tool adapter
- update an API route
- implement a workflow step
- patch a parser or script
- add focused tests

Required output:

```text
assigned_scope:
files_changed:
behavior_changed:
validation_run:
validation_result:
blockers:
contract_risks:
next_recommendation:
```

## 5. Group 3: Validation

### `invest_code_quality_checker`

Use after Group 2 implementation and before practical validation.

Primary responsibilities:

- Check whether code can run through code quality gates.
- Run or specify `ruff`, `py_compile`, focused `pytest`, and task-specific checks.
- Separate current-change failures from pre-existing unrelated failures.
- Report exact commands and results.

This role mainly handles mechanical and automated quality gates.

Required output:

```text
scope_checked:
commands_run:
results:
failures:
pre_existing_unrelated_failures:
required_fixes:
```

### `invest_functional_validator`

Use after code quality checks pass, or when a PLAN requires real-world validation.

Primary responsibilities:

- Execute the real-world validation plan written by `invest_project_director`.
- Validate the actual feature behavior, not just test pass/fail.
- Use scripts, API calls, worker ticks, generated runtime logs, or local demos as needed.
- Compare observed behavior against PLAN acceptance criteria.
- Return feedback that the director can use to continue, pause, or complete the PLAN.

This role mainly answers: does the feature actually work in the intended scenario?

Required output:

```text
plan_requirement_tested:
commands_or_operations_run:
observed_behavior:
acceptance_result:
evidence_artifacts:
blockers:
next_validation_step:
```

## 6. Standard Workflow

The required workflow is:

```text
invest_project_director
  -> update active PLAN with real-world validation plan
  -> assign Group 2 work
  -> Group 2 executes
  -> Group 3 code quality checks
  -> Group 3 functional validation
  -> invest_project_summarizer evaluates completed PLAN
  -> update worker capabilities only if needed
```

### Stage 1: Project Director Planning

Owner: `invest_project_director`

Steps:

1. Read memory, `AGENTS.md`, `.agent/STATUS.md`, and the active PLAN.
2. Classify the task into the project taxonomy.
3. Confirm the current phase and constraints.
4. Add a `Real-world validation plan` section to the active PLAN.
5. Define Group 2 implementation assignments.
6. Define Group 3 validation assignments.
7. Record gates, risks, and next action in the PLAN.

Gate:

- Group 2 should not start until the PLAN includes real-world validation requirements.

### Stage 2: Group 2 Execution

Owners:

- `invest_agent_architecture_builder` for architecture/harness work.
- `invest_feature_programmer` for concrete code/function/tool/source work.

Rules:

- Each worker gets explicit file/module ownership.
- Workers follow the PLAN, not an improvised roadmap.
- Workers must preserve high-risk contracts unless the PLAN explicitly authorizes a change.
- Workers return changed files, behavior summary, validation run, blockers, and risks.

Gate:

- No handoff to functional validation until code quality checks are complete or a blocker is documented.

### Stage 3: Group 3 Code Quality

Owner: `invest_code_quality_checker`

Responsibilities:

- Run `ruff` and compile checks for changed Python files.
- Run focused pytest suites.
- Run mandatory `.agent/skills/*` checks when the task type requires them.
- Identify unrelated pre-existing failures.

Gate:

- Code quality must pass, or the PLAN must record the blocker and assign it back to Group 2.

### Stage 4: Group 3 Functional Validation

Owner: `invest_functional_validator`

Responsibilities:

- Execute the real-world validation plan written in the PLAN.
- Validate practical behavior against acceptance criteria.
- Produce exact commands, observations, artifacts, and pass/fail result.

Gate:

- A PLAN should not be marked complete until functional validation passes, or until the user explicitly accepts completion despite a recorded validation gap.

### Stage 5: Project Summary

Owner: `invest_project_summarizer`

Responsibilities:

1. Read completed PLAN and validation results.
2. Summarize what changed.
3. Record remaining risks.
4. Evaluate future project needs.
5. Decide whether Group 2 or Group 3 worker capability definitions need updates.
6. If no update is needed, leave worker configs unchanged.
7. Recommend the next active PLAN or mark no active long-running PLAN.

Gate:

- The summarizer is the only role that should propose operating-model updates after a PLAN is completed.

## 7. Active PLAN Update Template

When `invest_project_director` prepares a phase, it should add or update this section in the active PLAN:

```markdown
## Real-world validation plan

Scenario:
- What real task/user flow this phase must prove.

Inputs:
- Concrete request payloads, files, source URLs, task ids, or CLI commands.

Expected behavior:
- Observable outputs and system state.

Acceptance criteria:
- Specific pass/fail criteria.

Validation owner:
- invest_code_quality_checker and/or invest_functional_validator.

Evidence to capture:
- Logs, JSON response fields, generated files, run ids, task ids, or screenshots.

Fallback/blocker handling:
- What to record if an external dependency or environment capability is missing.
```

## 8. Common User Commands

Use the full workflow:

```text
按 v2 subagent 工作流推进当前 active PLAN。
先用 invest_project_director 更新 PLAN 和安排 Group2/Group3，再执行实现、代码质量检查、实际功能验证，最后用 invest_project_summarizer 总结。
```

Only plan the next phase:

```text
使用 invest_project_director，读取当前 STATUS 和 active PLAN，把下一阶段的真实场景验证计划写入 PLAN，并安排 Group2/Group3 任务。
```

Only implement:

```text
使用 invest_feature_programmer，严格按 active PLAN 当前 phase 的任务实现，不要改未授权的高风险契约。
```

Only validate:

```text
使用 invest_code_quality_checker 跑代码质量检查，然后使用 invest_functional_validator 按 PLAN 的 Real-world validation plan 做实际功能验证。
```

Only summarize:

```text
使用 invest_project_summarizer，总结已完成 PLAN，评估是否需要更新 Group2/Group3 worker 能力；无必要则不要更新。
```

## 9. Operating Rules

- One active long-running PLAN drives execution.
- Completed PLANs move to `.agent/PLANS/archive/`.
- The director updates validation planning before Group 2 implementation.
- Group 2 workers do implementation, not final validation.
- Group 3 workers validate, not silently patch production code.
- The summarizer evaluates worker capability updates only after PLAN completion.
- Keep `max_depth = 1`.
- Do not spawn every agent by default.
- Keep worker write scopes explicit and narrow.
- Record validation gaps instead of hiding them.
