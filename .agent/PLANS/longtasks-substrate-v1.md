# Longtasks Substrate v1

Status: completed

Created: 2026-05-01

Primary active PLAN: yes

Supersedes: `.agent/PLANS/source-local-procurement-regulatory-depth-v1.md` (paused for substrate transition)

## Objective

Audit and verify the task/job/delivery/content substrate for release safety. These modules were modified during the source-layer expansion but belong to the task substrate domain and need explicit attribution and verification.

## Task Classification

- Primary area: `task_substrate`
- Secondary areas: `delivery_layer`, `content_factory`
- Execution mode: `local_direct` (audit/verification only, no production code changes)

Protected contracts not authorized for silent change:

- task/job status semantics
- `run` / `run_steps` meaning
- content asset metadata contract
- delivery state transition behavior
- `enable_source_acquisition=False` legacy behavior

## Audit Scope

### `packages/tasks/service.py` (271 lines)
- Clean, well-structured async task service with enqueue/claim/execute/retry/cancel
- Integrated `CompactRunLogger` for task-level observability (enqueue + process_next)
- Proper error handling: `NonRetryableTaskError` vs retryable failures
- Session rollback on failure before marking
- Metrics integration: `mark_task_enqueued`, `mark_task_succeeded`, `mark_task_failed`
- TODOs: Redis-backed queue, rate limiting, OpenTelemetry tracing — deferred, not blocking

### `packages/delivery/service.py` (426 lines)
- Clean delivery workflow with create/approve/dispatch lifecycle
- Policy checking integration with `delivery_enforce_policy_checks` config flag
- Structured Run/Step logging via `CompactRunLogger`
- Export bundle + connector dispatch pattern
- Proper state machine validation: `validate_approve_transition`, `validate_dispatch_transition`
- TODOs: Real connectors (WeChat/XHS/Douyin), scheduling/retry, attribution analytics — deferred

### `packages/content/service.py` (331 lines)
- Clean content generation with provider resolution pattern
- Multi-format content generation with structured Run/Step logging
- Research memo validation and schema checking
- Policy checking on generated content
- TODOs: Publishing connector hooks, cover image generation — deferred

## Verification

```powershell
# All task/delivery/content tests pass
pytest tests/test_tasks_service.py tests/test_tasks_api.py 
pytest tests/test_delivery_service.py tests/test_delivery_api.py
pytest tests/test_content_service.py tests/test_content_api.py
```

Results: **14 passed, 0 failed** (2026-05-01)

## Done Condition

This PLAN is done when:
- [x] All three service modules audited for release safety
- [x] Tests pass (14/14)
- [x] TODOs documented as non-blocking
- [x] STATUS and PLAN INDEX updated

## Progress

- 2026-05-01: PLAN created. Audit completed in same session.
  - `packages/tasks/service.py`: clean, 3 TODOs deferred (Redis queue, rate limiting, OTel)
  - `packages/delivery/service.py`: clean, 3 TODOs deferred (real connectors, scheduling, analytics)
  - `packages/content/service.py`: clean, 2 TODOs deferred (publishing hooks, cover images)
  - Tests: 14/14 passing
  - No production code changes needed — this is a verification-only PLAN

## Risks And Rollback

Risks:
- Deferred TODOs may become release blockers if not addressed before production deployment
- Delivery connectors are stubs (mock) and need real implementations before multi-platform delivery

Rollback: N/A — no code changes made. This PLAN is verification-only.

## Next Action

Substrate audit complete. Per Route C strategy: create `theme-watchlist-intel-workbench-v1` PLAN for the first user-facing product demo.
