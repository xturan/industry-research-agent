# Plan: System Run Log v1

Status: completed
Priority: medium
Owner: codex/human
Scope: eval_policy_ops
Created: 2026-04-26
Last Updated: 2026-04-26

## Objective

Add a compact file-based runtime log capability that records system inputs, decision summaries, and outputs for auditable execution without large token-heavy traces.

## Scope

In scope:

- lightweight reusable runtime log service
- log file naming by run time and task name
- compact JSONL records for input, decision summary, output, and errors
- integration into key synchronous workflows where decisions are already structured:
  - research workflow
  - content generation
  - delivery dispatch/create flow if low-risk
  - async task worker execution if low-risk
- tests for naming, compaction, and at least one integrated workflow

Out of scope:

- storing hidden model reasoning or full chain-of-thought
- replacing existing DB `runs` / `run_steps`
- full observability stack or OpenTelemetry
- schema migration
- large raw payload logging

## Constraints

- Keep logs concise to reduce token/storage cost.
- Prefer deterministic summaries from structured request/output fields.
- Default log location should be local and configurable.
- Do not silently change research response shape, run/run_steps meaning, task status semantics, content asset metadata, or delivery state transitions.
- Avoid logging secrets, provider keys, or full large document bodies.

## Phases

- [x] Phase 1: Create plan and classify scope.
- [x] Phase 2: Inspect existing entry points and config style.
- [x] Phase 3: Implement compact run logger and targeted integrations.
- [x] Phase 4: Add tests and run validation.
- [x] Phase 5: Update status and document usage.

## Validation

Required:

- `python -m ruff check <changed files>`
- focused pytest for new logger tests
- relevant contract checks depending on touched modules:
  - `.agent/skills/research-contract-check.md` if research workflow changes
  - `.agent/skills/task-flow-check.md` if task worker changes

Completed:

- `python -m ruff check packages/core/config.py packages/core/run_log.py packages/agents/workflow.py packages/content/service.py packages/delivery/service.py packages/tasks/service.py tests/test_core_run_log.py`
- `python -m py_compile packages/core/run_log.py packages/agents/workflow.py packages/content/service.py packages/delivery/service.py packages/tasks/service.py`
- `pytest -q tests/test_core_run_log.py`
- `python -m ruff check apps packages tests/test_core_run_log.py tests/test_agents_workflow.py tests/test_research_api.py tests/test_research_provider_integration.py tests/test_deepseek_provider.py tests/test_tasks_service.py tests/test_tasks_api.py tests/test_content_service.py tests/test_delivery_service.py`
- `pytest -q tests/test_core_run_log.py tests/test_agents_workflow.py tests/test_research_api.py tests/test_research_provider_integration.py tests/test_deepseek_provider.py tests/test_tasks_service.py tests/test_tasks_api.py tests/test_content_service.py tests/test_delivery_service.py`

Known validation limitation:

- `python -m ruff check .` still fails on pre-existing `data/tmp/*_demo.py` import ordering and long lines unrelated to this change.

## Progress

- Task classified as primary `eval_policy_ops`.
- Secondary impacted areas: `research_workflow`, `task_substrate`, `content_factory`, `delivery_layer`.
- Key design decision: record concise decision summaries, not hidden reasoning chains.
- Added `packages/core/run_log.py` with compact JSONL writing, filename slugging, payload compaction, sensitive-key redaction, and heavy-text preview summaries.
- Added settings:
  - `SYSTEM_RUN_LOG_ENABLED`
  - `SYSTEM_RUN_LOG_DIR`
  - `SYSTEM_RUN_LOG_MAX_VALUE_CHARS`
  - `SYSTEM_RUN_LOG_MAX_ITEMS`
- Integrated side-effect-only logs into:
  - research workflow
  - content generation
  - delivery create/approve/dispatch
  - task enqueue and worker execution
- Added `tests/test_core_run_log.py`.
- Documented usage in `README.md`.

## Risks

- Logs are file-based local artifacts and may contain compact previews of user inputs/outputs; sensitive keys and reasoning fields are redacted, but deployments should still protect `SYSTEM_RUN_LOG_DIR`.
- Default logging is enabled; noisy test/demo runs can create many ignored JSONL files under `data/run_logs`.
- Full repository ruff remains blocked by unrelated existing `data/tmp` demo scripts.

## Next Action

Return to `.agent/PLANS/crawl4ai-domestic-article-extractor-v1.md` Phase 3 validation.
