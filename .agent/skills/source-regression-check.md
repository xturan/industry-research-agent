# Skill: source-regression-check

## Purpose
Validate that source-layer changes did not break:
- source routing
- adapter behavior
- evidence extraction
- evidence bundle generation
- source-assisted research compatibility

## Use when
Run this skill after changes in:
- `packages/sources/**`
- source-related parts of `packages/agents/**`
- source-related parts of `packages/evals/**`
- domestic source collector logic
- evidence bundle shaping that affects source acquisition output

## Required commands
```bash
python -m ruff check .
pytest -q tests/test_sources_layer.py
pytest -q tests/test_sources_adapters_v1.py
pytest -q tests/test_sources_hardening_step34.py
pytest -q tests/test_sources_evals_step35.py
```

## If domestic source code changed, also run
```bash
pytest -q tests/test_sources_router_domestic.py
pytest -q tests/test_sources_profile_adapter.py
pytest -q tests/test_sources_real_domestic_step42.py
pytest -q tests/test_sources_pdf_step43.py
```

## Pass criteria
- all commands pass
- source routing still returns structured recommendations
- evidence bundle output is still typed and non-drifting
- citation fields remain present where expected
- partial failure behavior remains structured

## Failure classification
Classify failures into one of:
- routing_regression
- adapter_regression
- collector_regression
- evidence_shape_regression
- citation_regression
- source_eval_regression
- pdf_processing_regression

## Repair rule
Prefer the smallest fix that restores contract stability.
Do not widen scope unless the failure proves the design itself is wrong.

## Completion note
When done, record in the relevant active plan file under `.agent/PLANS/`:
- what failed
- what was fixed
- which source area was impacted
