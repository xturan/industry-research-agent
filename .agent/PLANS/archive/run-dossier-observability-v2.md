# Run Dossier Observability v2

Status: completed

Created: 2026-06-08

Primary active PLAN: user_requested_sidecar

## Objective

Evolve the Deep Research run dossier from V1 stage summaries into a practical
debugging trace that records the visible execution process of each pipeline
agent and model/tool call.

## Task Classification

- Primary area: `eval_policy_ops`
- Secondary areas: `research_workflow`, `provider_layer`
- Execution mode: `local_direct`
- Protected contracts: do not change EvidenceBundle schema, citation shape,
  public research response shape, provider abstraction semantics, `run` /
  `run_steps` semantics, content asset metadata contract, or task status
  semantics.

## Scope

In scope for V2:

- Add a structured Deep Research trace collector for visible runtime events.
- Capture LLM calls with stage/agent, prompt previews, visible content output,
  parsed JSON output, provider metadata, latency, status, and errors.
- Capture search-loop calls with query phrase, domains, returned candidates,
  result counts, estimated credits, latency, and status.
- Capture source-tier decisions and phase-level outputs.
- Render a detailed trace section inside the Markdown dossier.
- Keep sensitive fields out of traces.
- Keep hidden model reasoning / chain-of-thought out of traces.

Out of scope for V2:

- Recording private chain-of-thought or provider reasoning content.
- Changing `/deep-research/analyze` response shape.
- Adding content asset generation trace; section 3 remains reserved.
- Moving `research_reports` to Alembic/SQLAlchemy models.

## Validation

- Focused unit tests for trace rendering and dossier output.
- Focused Deep Research tests covering trace generation with fake providers.
- Research contract check subset after `packages/agents/**` changes.
- One API demo that confirms the dossier includes detailed agent trace records.

## Progress

- 2026-06-08: PLAN created from V1 review feedback. User accepted V1 but asked
  for V2 to capture actual pipeline agent execution records so debugging no
  longer feels black-box.
- 2026-06-08: Implemented structured Deep Research trace capture:
  - Added in-memory `trace_events` sidecar records on `DeepResearchAgent`.
  - Captured phase outputs for query understanding, search planning,
    source-tiering, evidence-chain, debate, counter-evidence, report assembly,
    and run completion.
  - Captured LLM calls with agent/stage labels, prompt previews, visible
    content output, parsed JSON output, provider metadata, token usage,
    latency, status, and errors.
  - Captured search calls with phrase/domain inputs, result candidates, result
    count, estimated credits, latency, status, and errors.
  - Captured per-source tiering decisions with evaluator mode.
  - Added dossier rendering for `### Detailed Agent Trace`.
  - Added tests for trace rendering and visible LLM trace recording.

## Validation Snapshot

- `python -m py_compile packages\agents\deep_research.py packages\research_reports\dossier.py tests\test_research_run_dossier.py` -> pass.
- `python -m ruff check packages\agents\deep_research.py packages\research_reports\dossier.py tests\test_research_run_dossier.py` -> pass.
- `pytest -q tests\test_research_run_dossier.py` -> `3 passed`.
- `pytest -q tests\test_deep_research_agent.py tests\test_research_run_dossier.py -k "not convenience_entry_point"` -> `13 passed / 1 deselected`.
- `pytest -q tests\test_research_api.py tests\test_research_run_dossier.py` -> `5 passed`.
- `pytest -q tests\test_agents_workflow.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py` -> `22 passed`.
- Live local HTTP API check with real DeepSeek/Tavily providers:
  - `POST /deep-research/analyze` -> `200` in `83.67s`.
  - `GET /research-reports?limit=1` -> `200`.
  - `GET /research-reports/1` -> `200`.
  - `GET /research-reports/1/dossier` -> `200`, `text/markdown`.
  - Output: `10` sources, `7` evidence items, `1` search round, `22`
    estimated Tavily credits, `medium` confidence.
  - Dossier checks: `HAS_DETAILED_TRACE=True`, `TRACE_EVENT_COUNT=32`,
    `HAS_LLM_CALL=True`, `HAS_SEARCH_CALL=True`,
    `HAS_SOURCE_ASSESSMENT=True`, `HAS_PROMPT_INPUTS=True`,
    `HAS_JSON_OUTPUT=True`, `HAS_REASONING_SUPPRESSED=True`.
  - Result artifact:
    `data/tmp/run_dossier_live_api_v2_current/live_api_v2_result.txt`.
- `python -m ruff check .` -> still fails on pre-existing `.agent/hooks`,
  `.claude/worktrees`, and Unsloth cache files outside this V2 change.

## Risks

- Trace volume can become large; V2 should cap prompt/output previews in
  Markdown while keeping structured summaries readable.
- Capturing raw prompts may include source text; redact obvious secrets and do
  not capture API keys, authorization headers, tokens, or hidden reasoning.
- Existing live Chinese output can display as mojibake in some PowerShell
  `Get-Content` views even when API UTF-8 response is correct.

## Next Action

Archive this PLAN. Recommended follow-up: add a durable run-id/timestamp to
dossier paths and add trace volume controls for long multi-round runs.
