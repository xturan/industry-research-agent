# Plan: Subagent Operating Model v1

Status: completed
Priority: medium
Owner: codex/human
Scope: docs_only
Created: 2026-04-26
Last Updated: 2026-04-26

## Objective

Study the VoltAgent `awesome-codex-subagents` repository and official Codex subagent guidance, then design a project-specific subagent operating model for Invest Agent.

## Scope

In scope:

- define the number of project-specific subagents
- split them into planning/control, implementation, and testing/audit groups
- create project-scoped Codex custom agent TOML files
- document detailed workflows and handoff contracts
- preserve current active Crawl4AI plan state

Out of scope:

- changing production business code
- changing EvidenceBundle, citation, research response, task, content, or delivery contracts
- running the new agents in parallel for implementation work

## Constraints

- Use `.codex/agents/` for project-specific agents.
- Keep subagents narrow and opinionated.
- Keep `agents.max_depth = 1`.
- Do not replace the active Crawl4AI plan.
- Keep implementation agents' write scopes separate.

## Phases

- [x] Phase 1: Read memory, repository instructions, status, and active plan.
- [x] Phase 2: Study external subagent references.
- [x] Phase 3: Design agent count, roles, and workflow.
- [x] Phase 4: Add project-scoped agent configs and documentation.
- [x] Phase 5: Validate TOML/config shape and update status.

## Validation

- Parse `.codex/config.toml` and all `.codex/agents/*.toml` with Python `tomllib`.
- Review changed file scope.

## Progress

- Confirmed current active plan remains `.agent/PLANS/crawl4ai-domestic-article-extractor-v1.md`.
- Reviewed VoltAgent README/category examples and official Codex subagent docs.
- Selected 10 project-specific subagents:
  - 3 planning/control agents
  - 4 implementation agents
  - 3 testing/audit agents
- Added `.codex/config.toml` with `max_threads = 6` and `max_depth = 1`.
- Added project-scoped agent TOML files under `.codex/agents/`.
- Added `docs/subagents-operating-model.md`.

## Risks

- These agents are configuration/design assets; they have not yet been used in a live delegated implementation run.
- Actual subagent availability still depends on Codex session refresh/loading behavior.
- The current active Crawl4AI phase still requires runtime validation in an environment with Crawl4AI installed.

## Next Action

Use the new operating model on the current active Crawl4AI Phase 3 validation:

1. `invest_validation_designer` defines acceptance checks.
2. `invest_functional_tester` runs the Crawl4AI script where Crawl4AI is installed.
3. `invest_source_engineer` patches only if runtime validation reveals script behavior defects.
