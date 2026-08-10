# Run Dossier Observability v1

Status: completed

Created: 2026-06-08

Primary active PLAN: user_requested_sidecar

## Objective

Add a first-version human-readable Markdown dossier for each Deep Research run
and persist the dossier path in the database so a run can be inspected without
digging through JSON fragments.

## Task Classification

- Primary area: `eval_policy_ops`
- Secondary areas: `research_workflow`, `content_factory`
- Execution mode: `local_direct`
- Protected contracts: do not change EvidenceBundle schema, citation shape,
  public research response shape, provider abstraction, `run` / `run_steps`
  semantics, content asset metadata contract, or task status semantics.

## Scope

In scope for V1:

- Generate `data/run_dossiers/deep_research/<date>/report_<id>/dossier.md`.
- Store `dossier_path` on persisted `research_reports`.
- Render three sections:
  1. query expansion, search rounds, source candidates, selected sources, source
     tier scores, and evaluator mode;
  2. selected evidence and visible agent pipeline records;
  3. content assets placeholder for V1, with schema-ready section.
- Add an API endpoint to retrieve dossier Markdown by research report id.
- Run one local demo and show the generated dossier path/content summary.

Out of scope for V1:

- Raw hidden chain-of-thought capture.
- Changing public `/deep-research/analyze` response shape.
- Full content asset trace integration.
- New Alembic migration; use backward-compatible table ALTER in the existing
  lightweight `research_reports` service for this V1 slice.

## Validation

- Focused unit tests for dossier renderer / persistence.
- Focused research report API/service tests if present.
- `python -m py_compile` for changed Python files.
- One actual local Deep Research run producing a Markdown dossier and DB row.

## Progress

- 2026-06-08: PLAN created from user request. V1 chosen as a sidecar path on
  `research_reports` to avoid protected workflow/response-shape changes.
- 2026-06-08: V1 implementation completed:
  - Added `packages/research_reports/dossier.py` Markdown renderer/writer.
  - Added optional `dossier_path` to research report schemas and persistence.
  - Added `GET /research-reports/{report_id}/dossier`.
  - Connected `DeepResearchAgent.run(... persist=True)` to save the report,
    write `dossier.md`, and backfill `dossier_path`.
  - Added focused tests in `tests/test_research_run_dossier.py`.
  - Ran a local demo through `DeepResearchAgent.run()` with fake local
    providers/search to avoid external API cost; generated
    `data/run_dossiers/deep_research/20260608/report_1/dossier.md`.

## Validation Snapshot

- `python -m py_compile packages\research_reports\dossier.py packages\research_reports\schemas.py packages\research_reports\service.py apps\api\routes\research_reports.py packages\agents\deep_research.py` -> pass.
- `python -m ruff check packages\research_reports\dossier.py packages\research_reports\schemas.py packages\research_reports\service.py apps\api\routes\research_reports.py packages\agents\deep_research.py tests\test_research_run_dossier.py` -> pass.
- `pytest -q tests\test_research_run_dossier.py` -> `2 passed`.
- `pytest -q tests\test_research_run_dossier.py tests\test_deep_research_agent.py -k "not convenience_entry_point"` -> `12 passed / 1 deselected`.
- `pytest -q tests\test_research_api.py tests\test_research_run_dossier.py` -> `4 passed`.
- `pytest -q tests\test_agents_workflow.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py` -> `22 passed`.
- Demo API check: `GET /research-reports/1/dossier` against the demo SQLite DB -> `200`, `text/markdown`.
- 2026-06-08 rerun API check with FastAPI `TestClient` and fake external
  providers: `POST /deep-research/analyze` -> `200`; latest report listed with
  `dossier_path`; `GET /research-reports/1` -> `200`; `GET
  /research-reports/1/dossier` -> `200`, `text/markdown`; dossier assertions
  for section 1, section 2, section 3 placeholder, evaluator mode, source
  rating table, and agent records all passed.
- 2026-06-08 live API check with local Uvicorn HTTP server and real external
  providers: `POST /deep-research/analyze` -> `200` in `94.87s`; DeepSeek
  chat completions returned `200 OK` in server logs; Tavily-backed search
  produced `10` source candidates; report persisted with `dossier_path`;
  `GET /research-reports/1/dossier` -> `200`, `text/markdown`; estimated
  Tavily credits `22`; dossier assertions for section 1, section 2, section 3
  placeholder, evaluator mode, and agent records passed. Result artifact:
  `data/tmp/run_dossier_live_api_v1_current/live_api_result.txt`.
- Repo-wide `python -m ruff check .` -> failed on pre-existing `.agent/hooks`, `.claude/worktrees`, and Unsloth cache files outside this V1 change.

## Risks

- Existing project has mojibake in historical Chinese strings; V1 renderer must
  remain UTF-8 and robust to odd text.
- Existing `research_reports` service uses raw SQL table creation; V1 keeps
  compatibility but future work should move this table into SQLAlchemy/Alembic.
- V1 records visible decisions and summaries, not raw model private reasoning.

## Next Action

Archive this PLAN. Recommended follow-up: integrate the same dossier writer with
content generation so section 3 records real content asset LLM work records.
