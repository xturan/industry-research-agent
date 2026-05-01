---
description: "Run source-layer regression checks: ruff, focused pytest for source routing, adapters, evidence extraction, and domestic source compatibility."
---

# Source Regression Check

Validate that source-layer changes did not break source routing, adapter behavior, evidence extraction, evidence bundle generation, or source-assisted research compatibility.

Run after changes in:
- `packages/sources/**`
- source-related parts of `packages/agents/**`
- source-related parts of `packages/evals/**`
- domestic source collector logic
- evidence bundle shaping that affects source acquisition output

## Standard Checks

```bash
python -m ruff check packages/sources/
pytest -q tests/test_sources_layer.py 2>/dev/null || echo "SKIP: file not found"
pytest -q tests/test_sources_adapters_v1.py 2>/dev/null || echo "SKIP: file not found"
```

## If Domestic Source Code Changed

```bash
pytest -q tests/test_sources_router_domestic.py 2>/dev/null || echo "SKIP: file not found"
pytest -q tests/test_sources_profile_adapter.py 2>/dev/null || echo "SKIP: file not found"
```

## If Search-Assisted Domestic Changed

```bash
pytest -q tests/test_sources_search_assisted_domestic.py 2>/dev/null || echo "SKIP: file not found"
pytest -q tests/test_sources_query_decomposition.py 2>/dev/null || echo "SKIP: file not found"
```

## Pass Criteria

- all commands pass
- source routing still returns structured recommendations
- evidence bundle output is still typed and non-drifting
- citation fields remain present where expected
- partial failure behavior remains structured

## Failure Classification

Classify failures into: routing_regression, adapter_regression, collector_regression, evidence_shape_regression, citation_regression, source_eval_regression, pdf_processing_regression

See `.agent/skills/source-regression-check.md` and `.agent/skills/domestic-source-check.md` for detailed rules.
