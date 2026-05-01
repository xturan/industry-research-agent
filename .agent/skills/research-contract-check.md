# Skill: research-contract-check

## Purpose
Validate that research workflow changes did not break:
- request schema
- provider integration
- evidence bundle handoff
- research stage outputs
- final memo contract
- response metadata compatibility

## Use when
Run this skill after changes in:
- `packages/agents/**`
- `packages/providers/**`
- `apps/api/routes/research.py`
- research-related request/response schemas
- source-assisted research integration paths

## Required commands
```bash
python -m ruff check .
pytest -q tests/test_agents_workflow.py
pytest -q tests/test_research_api.py
pytest -q tests/test_research_provider_integration.py
pytest -q tests/test_deepseek_provider.py
```

## If source-assisted research changed, also run
```bash
pytest -q tests/test_sources_layer.py
pytest -q tests/test_sources_evals_step35.py
```

## Pass criteria
- research analyze still works for legacy mode
- source-assisted path still works when enabled
- structured outputs remain schema-valid
- provider/model metadata remains visible where expected
- reasoning content remains suppressed by default unless explicitly enabled

## Failure classification
Classify failures into one of:
- request_schema_regression
- provider_selection_regression
- evidence_bundle_handoff_regression
- stage_output_regression
- final_memo_regression
- api_response_regression

## Repair rule
Do not silently change research response shape.
If a breaking change is intended, document it in the relevant active plan file under `.agent/PLANS/`.

## Completion note
Update `.agent/STATUS.md` if the repository's default research path changed.
