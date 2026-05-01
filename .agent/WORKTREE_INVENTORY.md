# Worktree Inventory

Last updated: 2026-04-28

## Purpose

This inventory records the current dirty worktree after PLAN hygiene cleanup.

It is intentionally non-destructive:

- no files were deleted;
- no code was reverted;
- no changes were staged or committed;
- no credentials were persisted.

## Current Git State Summary

Observed commands:

```powershell
git status --short
git diff --stat
```

Tracked modified files:

- `.env.example`
- `.gitignore`
- `AGENTS.md`
- `README.md`
- `command.txt`
- `packages/agents/workflow.py`
- `packages/content/service.py`
- `packages/core/config.py`
- `packages/delivery/service.py`
- `packages/sources/__init__.py`
- `packages/sources/enums.py`
- `packages/sources/profiles/__init__.py`
- `packages/sources/profiles/china_exchange.py`
- `packages/sources/profiles/china_industry.py`
- `packages/sources/profiles/china_policy.py`
- `packages/sources/router.py`
- `packages/sources/schemas.py`
- `packages/sources/service.py`
- `packages/sources/tools.py`
- `packages/tasks/service.py`
- `tests/test_agents_workflow.py`

Untracked top-level groups:

- `.agent/`
- `.codex/`
- `data/run_logs/`
- `data/tmp/`
- `docs/`
- `scripts/`
- new source modules under `packages/sources/`
- new run-log module under `packages/core/`
- new source/research tests under `tests/`

## Working Classification

### Governance / Agent Operating System

Likely related files:

- `.agent/**`
- `.codex/**`
- `AGENTS.md`
- `docs/**`

Current action:

- Keep as user-visible governance state.
- Do not promote new rules into `AGENTS.md` without a separate behavior-governance PLAN.
- `agentic-operating-system-v2.md` remains pending human review.

### Completed Domestic Source Refactor

Likely related files:

- `packages/sources/crawl4ai_extraction.py`
- `packages/sources/search_discovery.py`
- `packages/sources/search_assisted_domestic.py`
- `packages/sources/query_decomposition.py`
- `packages/sources/domestic_inventory.py`
- `packages/sources/governance.py`
- `packages/sources/packs.py`
- `packages/sources/dev_validate_sources.py`
- `packages/sources/profiles/china_scaleout.py`
- `packages/sources/profiles/*.py`
- `packages/sources/router.py`
- `packages/sources/service.py`
- `packages/sources/tools.py`
- `packages/sources/enums.py`
- `packages/sources/schemas.py`
- `tests/test_sources_*.py`
- `data/tmp/_phase5_search_assisted_domestic_eval.py`
- `data/tmp/search_assisted_domestic_phase5_*`
- `data/tmp/tavily_*`
- `data/tmp/crawl4ai_*`

Current action:

- Preserve.
- Treat as completed but uncommitted implementation work.
- `packages/sources/schemas.py` contains public additions relative to HEAD; future release boundary work should review it under a separate Architecture Gate/PLAN.

### Research Workflow Source-Assisted Integration

Likely related files:

- `packages/agents/workflow.py`
- `tests/test_agents_workflow.py`
- `packages/sources/search_assisted_domestic.py`
- `tests/test_sources_search_assisted_domestic.py`
- `data/tmp/_research_workflow_source_assisted_eval.py`

Current action:

- Preserve.
- Completed PLAN archived.
- Focused tests and eval harness passed in the completed PLAN.

### Run Logging / Execution Trace

Likely related files:

- `packages/core/run_log.py`
- `tests/test_core_run_log.py`
- `data/run_logs/**`
- `.gitignore`

Current action:

- Preserve unless user decides run logs should be ignored or cleaned.
- Do not delete `data/run_logs` without explicit approval.

### Content / Delivery / Task Substrate

Likely related files:

- `packages/content/service.py`
- `packages/delivery/service.py`
- `packages/tasks/service.py`

Current action:

- Preserve and review before next substrate-related PLAN.
- These changes are outside the most recent source-assisted workflow PLAN and need separate attribution before release.

### Config / Docs / Commands

Likely related files:

- `.env.example`
- `README.md`
- `command.txt`
- `scripts/**`

Current action:

- Preserve.
- Review before commit or release packaging.

### Historical Scratch / Eval Data

Likely related files:

- `data/tmp/_phase1_assert_validation.py`
- `data/tmp/_phase1_decomp_validation.py`
- `data/tmp/_phase1_enum_validation.py`
- `data/tmp/governance_scaleout_demo.py`
- `data/tmp/route_scaleout_demo.py`
- `data/tmp/run_domestic_source_demo.py`
- large captured files such as `ichuanghui_custom.*`

Current action:

- Preserve for now.
- Repo-wide `python -m ruff check .` still fails on several historical `data/tmp` scratch scripts.
- Recommended future action: either move historical scratch scripts under an ignored/archive location, add scoped ruff excludes, or format them if they should remain runnable source.

## Recommended Next Cleanup Decisions

1. Decide whether `.agent/PLANS/archive/` should be committed as durable project memory.
2. Decide whether historical `data/tmp` scratch scripts should be kept, ignored, archived, or lint-cleaned.
3. Decide whether to create a behavior-governance PLAN to promote accepted Group2 lane rules into `AGENTS.md`.
4. Before a release commit, review `packages/sources/schemas.py` public additions separately.
5. Before task-substrate work, review `packages/tasks/service.py`, `packages/content/service.py`, and `packages/delivery/service.py` changes under a dedicated PLAN.
