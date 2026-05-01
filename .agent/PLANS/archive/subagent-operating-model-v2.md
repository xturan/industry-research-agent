# Plan: Subagent Operating Model v2

Status: completed
Priority: medium
Owner: codex/human
Scope: docs_only
Created: 2026-04-26
Last Updated: 2026-04-26

## Objective

Refine the project subagent architecture into a simpler six-role workflow that treats each PLAN as the strict construction blueprint.

## Scope

In scope:

- mark the Crawl4AI domestic article extractor plan as completed and archive it
- replace the previous 10-agent custom configuration with 6 project-specific agents
- update `docs/subagents-operating-model.md` with the new role model and workflow
- preserve project rules around plan/status visibility, validation, and contract safety

Out of scope:

- production code changes
- changing research/source/task/content/delivery schemas or runtime behavior
- changing the previously implemented compact runtime log capability

## Constraints

- PLAN is the strict execution blueprint.
- The project director must write practical validation planning into the active PLAN before worker execution.
- The project summarizer only evaluates the plan after completion and updates worker capability design only when necessary.
- Group 2 is simplified to agent architecture construction and concrete coding.
- Group 3 is simplified to code quality checks and real functional validation.
- Keep `max_depth = 1` and avoid recursive delegation.

## Phases

- [x] Phase 1: Create plan and classify scope.
- [x] Phase 2: Archive Crawl4AI plan as completed.
- [x] Phase 3: Replace subagent TOML configuration.
- [x] Phase 4: Update operating model documentation.
- [x] Phase 5: Validate TOML and update status.

## Validation

- Parse `.codex/config.toml` and all `.codex/agents/*.toml` with Python `tomllib`.
- Confirm `.codex/agents/` contains exactly the six v2 roles.
- Review docs/status scope.

Completed:

- Parsed `.codex/config.toml` and all six `.codex/agents/*.toml` files with Python `tomllib`.
- Confirmed `.codex/agents/` contains exactly:
  - `invest_project_director.toml`
  - `invest_project_summarizer.toml`
  - `invest_agent_architecture_builder.toml`
  - `invest_feature_programmer.toml`
  - `invest_code_quality_checker.toml`
  - `invest_functional_validator.toml`

## Progress

- Task classified as primary `docs_only`.
- User-defined target workflow captured:
  - project director updates PLAN with real-world validation planning and task allocation
  - Group 2 workers execute
  - Group 3 workers test and validate
  - project summarizer evaluates outcome and worker capability needs after completion
- Archived Crawl4AI domestic article extractor plan as completed by explicit user request.
- Replaced the previous 10-agent TOML design with the six-role v2 design.
- Updated `docs/subagents-operating-model.md` to the v2 workflow.

## Risks

- Marking Crawl4AI completed follows the user's explicit request even though previous status recorded missing true Crawl4AI-enabled runtime validation.
- The new simplified worker model is intentionally broader than v1 role-specific implementation agents, so the project director must write explicit ownership boundaries into the PLAN.

## Next Action

No further action for this plan. Select or create the next active project PLAN before implementation work.
