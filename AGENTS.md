# AGENTS.md

## Repository mission
This repository is a production-oriented, tool-driven deep research application for industry-report mining, evidence-based workflows, multi-agent orchestration, and multi-channel content generation.

All work must preserve the integrity of:
- source acquisition
- evidence bundle generation
- research workflow contracts
- content and delivery compatibility
- eval / policy visibility
- async task safety

Favor controlled progress over wide, premature changes.

## Product constraints
- Do NOT position the product as direct securities investment advice.
- Position it as industry intelligence, research assistance, and content production.
- Every conclusion must be traceable to evidence.
- Prefer deterministic code/workflows over prompt-only logic when possible.

## Engineering constraints
- Use a monorepo layout.
- Prefer Python for backend and agent orchestration.
- Prefer FastAPI for API service.
- Prefer PostgreSQL as primary database.
- Prefer pgvector for vector search.
- Prefer Redis for cache / task state / short-term memory.
- Use object storage abstraction for raw reports and generated assets.
- Use an async task queue for long-running jobs.
- Include tests for every major module.
- Add Makefile targets for setup, run, test, lint.
- Add Docker Compose for local development.
- Keep the code modular and production-oriented.

## Agent architecture expectations
Implement these roles over time:
- Supervisor Agent
- Source Hunter Agent
- Parser/Structurer Agent
- Thesis Builder Agent
- Opponent Agent
- Evidence Judge Agent
- Content Strategist Agent
- Growth Analyst Agent

## RAG expectations
- Use hybrid retrieval design in architecture.
- Preserve metadata for source, time, industry, company, document section, confidence.
- Support evidence bundles, not just raw chunks.
- Retrieval results must be auditable.

## Memory expectations
Support:
- theme memory
- content strategy memory
- user/account preference memory
- run memory / execution trace memory

## Tooling expectations
Tooling should be integrated through clean interfaces so it can later be swapped to MCP servers.
Do not tightly couple business logic to a single provider.

## Module classification
Before making changes, classify the task into one primary area:

- source_layer
- domestic_source_collectors
- research_workflow
- provider_layer
- content_factory
- delivery_layer
- memory_feedback
- task_substrate
- eval_policy_ops
- docs_only

If a task spans multiple areas, record the primary area and impacted secondary areas in the relevant active plan file under `.agent/PLANS/`.

## Planning rule
For any non-trivial, multi-stage, or cross-module task:
- create or update a dedicated plan file under `.agent/PLANS/`
- keep one plan file per long-running task / epic
- do not use a shared `current.md` plan file as the main mechanism

Create or update the relevant plan file before any of the following:

- changing schema
- changing EvidenceBundle shape
- changing citation structure
- changing provider abstraction
- changing research workflow stages
- changing task / worker behavior
- introducing or modifying a domestic source collector
- changing source routing logic
- changing response shapes used by downstream systems

For small documentation-only edits, a plan update is optional.

A valid plan file should include:
- status
- objective
- scope
- constraints
- phases
- validation
- progress
- risks
- next action

## Plan reading rule
Before starting non-trivial work:
1. read `AGENTS.md`
2. read `.agent/STATUS.md`
3. identify the relevant active plan file under `.agent/PLANS/`
4. read that specific plan file
5. read the relevant skill file(s)
6. execute only the current phase or next action defined in the plan

Completed plans under `.agent/PLANS/archive/` should not be read by default, unless the user explicitly asks to reference them.

## Active plan rule
At any given time, keep one primary active long-running plan in `.agent/STATUS.md`.
Other plans may exist as queued plans, but only one should drive the default execution path.

## Execution rule
For every non-trivial task:

1. classify the task
2. read `.agent/STATUS.md`
3. read the relevant active plan file
4. read the relevant skill file(s)
5. make the smallest coherent change
6. run required checks
7. update `.agent/STATUS.md`
8. update the relevant plan file progress and risks

Do not silently skip validation.

## PLAN implementation trigger rule
When the user says "开始实施PLAN", "开始实施 PLAN", "实施当前PLAN", "执行PLAN", "继续任务", or an equivalent instruction to start or continue implementing the active plan, first route the work through `.agent/skills/execution-mode-router.md`.

Default routing is speed-biased:

1. Use `local_direct` for small docs, eval, script, status, or report work with no protected-contract or cross-module risk.
2. Use `light_subagent` for scoped implementation where one worker plus code-quality validation is enough.
3. Use `remediation_gate` when a PLAN, live eval, or audit gate failed but the user goal remains unchanged.
4. Use `full_subagent` only when hard escalation triggers apply, such as protected-contract risk, source/provider/research workflow boundary changes, multiple Group2 lanes, or user-facing evidence/research behavior risk.

When `full_subagent` is selected, run the v2 subagent workflow:

1. use `invest_project_director` to read `.agent/STATUS.md` and the active PLAN
2. have `invest_project_director` add or refine the PLAN's real-world validation plan
3. have `invest_project_director` assign Group 2 and Group 3 work
4. run the relevant Group 2 worker(s):
   - `invest_agent_architecture_builder` for agent / harness architecture work
   - `invest_feature_programmer` for concrete coding, source/tool/service/API/script work
5. run the relevant Group 3 worker(s):
   - `invest_code_quality_checker` for ruff, compile, focused pytest, and code-quality checks
   - `invest_functional_validator` for practical validation against the PLAN
6. after the PLAN is completed, use `invest_project_summarizer` to evaluate the outcome and decide whether Group 2 or Group 3 capabilities need updates
7. update the active PLAN and `.agent/STATUS.md` with progress, validation, risks, and next action

If no active PLAN exists when the user says to start implementation, create or select the appropriate PLAN first, then route execution mode before dispatching work.

## High-risk changes
Do NOT silently modify any of the following:

- EvidenceBundle schema
- EvidenceItem citation fields
- source_quality_summary shape
- research analyze response shape
- task/job status semantics
- run/run_steps meaning
- content asset metadata contract
- delivery state transition behavior

If such a change is intended:
- write it explicitly in the relevant plan file under `.agent/PLANS/`
- document migration / compatibility impact
- include validation steps

## Mandatory checks by task type
### source_layer / domestic_source_collectors
Run:
- `.agent/skills/source-regression-check.md`
- `.agent/skills/domestic-source-check.md` if domestic source code changed

### research_workflow / provider_layer
Run:
- `.agent/skills/research-contract-check.md`

### task_substrate / worker / tasks
Run:
- `.agent/skills/task-flow-check.md`

### cross-cutting changes
Run all relevant skills.
Do not guess. Be explicit.

## Validation rule
A task is not complete when code is written.
A task is complete only when:

- required checks pass
- changed files are reviewed for scope correctness
- relevant docs are updated
- the relevant plan file is updated
- `.agent/STATUS.md` reflects the new state
- open risks / TODOs are recorded

## Change style
Prefer:
- narrow changes
- typed contracts
- explicit structured errors
- backward-compatible request fields where practical
- TODO-aware placeholders over fake completeness

Avoid:
- hidden breaking changes
- large speculative refactors
- introducing heavy infrastructure without a plan
- expanding source coverage before stabilizing current paths

## Domestic source specific rule
For domestic source work:

- prefer static HTML / list-detail / PDF-link paths first
- do not introduce browser automation unless explicitly planned
- do not introduce OCR unless explicitly planned
- keep domestic sources opt-in by default unless a plan states otherwise
- preserve structured partial-failure behavior

## Long-task rule
For long-running or multi-stage work:

- treat the relevant `.agent/PLANS/<task>.md` as the working execution plan
- treat `.agent/STATUS.md` as the current handoff/checkpoint note
- do not rely on hidden conversational memory for project state
- keep decisions visible in markdown

## Plan and status update rule
After completing a meaningful task step:
- update the relevant plan file with:
  - progress
  - validation
  - assumptions
  - risks
  - next action
- update `.agent/STATUS.md` with:
  - primary active plan
  - current phase
  - blockers
  - latest validation snapshot
  - next recommended action

If the task is complete:
- mark the plan file as `Status: completed`
- move it to `.agent/PLANS/archive/`
- update `.agent/STATUS.md` to reflect the next active plan or that no active long task exists

## Phase auto-switch rule
For active long-running plans, enforce phase continuity by default:

- when the current phase acceptance criteria are met and required validations pass,
  automatically mark that phase as completed in the plan
- in the same turn, switch `Current phase` to the next phase in:
  - the active plan file under `.agent/PLANS/`
  - `.agent/STATUS.md`
- continue execution into the next phase without waiting for an extra user prompt,
  unless the user explicitly asks to pause
- do not skip phase boundaries; every phase transition must be recorded with:
  - validation snapshot
  - key assumptions
  - risks/TODOs
- if a blocker, high-risk change, or human review gate is reached, stop auto-switching,
  record the blocker in both plan and status, and request user guidance

## Delivery rules
- Work step by step.
- At the end of each step, produce:
  1. what changed
  2. files created/modified
  3. commands to verify
  4. known risks / TODOs
- Do not silently skip failed commands.
- If something is ambiguous, choose the most pragmatic implementation and explain it in the final step summary.

## Quality gates
Before claiming a step is done:
- run tests relevant to the changed modules
- run lint/format where configured
- verify the app starts if startup code changed
- verify migrations if schema changed

## Completion output rule
When finishing a task, summarize:
- what changed
- validation run
- assumptions made
- remaining risks / TODOs
- recommended next step

## PLAN completion report rule
When completing a PLAN / long-running epic, the final report must include:
- what was done
- what user-facing or system capability was implemented
- the PLAN's concrete test cases / validation cases
- two before-and-after examples showing how actual behavior changed
- files created/modified
- validation commands and results
- remaining risks / TODOs
- recommended next step

Do not only report files or phases. Explain the practical effect of the PLAN in terms the user can test.
