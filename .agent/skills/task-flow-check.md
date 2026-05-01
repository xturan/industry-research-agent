# Skill: task-flow-check

## Purpose
Validate that task/worker/long-task related changes did not break:
- task submission
- worker execution
- state transitions
- retries
- idempotency
- persisted task/run traceability

## Use when
Run this skill after changes in:
- `apps/worker/**`
- `apps/api/routes/tasks.py`
- `packages/tasks/**`
- `packages/longtasks/**`
- task-related run/run_steps integration
- async research/content/delivery execution flow

## Required commands
```bash
python -m ruff check .
pytest -q tests/test_tasks_service.py
pytest -q tests/test_tasks_api.py
```

## If long-task substrate files were changed, also run
```bash
pytest -q tests/test_longtasks.py
```

If `tests/test_longtasks.py` does not exist yet, record this as a TODO instead of inventing a fake pass.

## Pass criteria
- task submission remains valid
- worker can execute expected task types
- failure path remains structured
- idempotent submissions do not duplicate side effects
- state transitions remain coherent

## Failure classification
Classify failures into one of:
- task_schema_regression
- worker_execution_regression
- retry_regression
- idempotency_regression
- traceability_regression
- longtask_checkpoint_regression

## Repair rule
Do not "fix" task failures by weakening assertions without understanding the state-machine implication.

## Completion note
If task semantics changed, update the relevant active plan file under `.agent/PLANS/` and note migration impact.
