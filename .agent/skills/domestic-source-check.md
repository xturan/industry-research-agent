# Skill: domestic-source-check

## Purpose
Validate that domestic source collector changes did not break:
- domestic routing
- profile-driven execution
- live HTML fetch path
- detail parsing
- attachment discovery
- PDF processing
- structured partial-failure behavior

## Use when
Run this skill after changes in:
- `packages/sources/profiles/**`
- `packages/sources/profile_adapter.py`
- `packages/sources/live_fetch.py`
- `packages/sources/collectors/**`
- domestic source router logic
- domestic PDF handling

## Required commands
```bash
python -m ruff check .
pytest -q tests/test_sources_router_domestic.py
pytest -q tests/test_sources_profile_adapter.py
pytest -q tests/test_sources_real_domestic_step42.py
pytest -q tests/test_sources_pdf_step43.py
```

## Optional live verification
Run when site stability matters and external access is acceptable:
- one policy-style domestic source demo
- one announcement/disclosure-style domestic source demo

## Pass criteria
- domestic router can still recommend the correct profile families
- GenericProfileSourceAdapter still executes profile-driven paths
- attachment discovery remains present where expected
- PDF processing remains bounded and structured
- one source failure does not crash the whole source-assisted flow

## Failure classification
Classify failures into one of:
- domestic_router_regression
- profile_adapter_regression
- live_fetch_regression
- detail_parse_regression
- attachment_discovery_regression
- pdf_pipeline_regression
- partial_failure_regression

## Repair rule
Prefer per-site/profile fixes before touching generic collector architecture.
Do not over-generalize from one broken site.

## Completion note
Record whether the regression is:
- site-specific
- collector-generic
- fetch-layer
- pdf-layer
