# Theme Watchlist Intel Workbench v1

Status: completed

Created: 2026-05-01

Primary active PLAN: yes

Supersedes: `.agent/PLANS/longtasks-substrate-v1.md` (completed)

## Objective

Build the first user-facing product demo: a Theme Watchlist + Intelligence Workbench. Users can browse investment/research themes, submit research queries, view structured results (theses, evidence, risks), and search document chunks — all through a simple browser UI.

## Task Classification

- Primary area: `content_factory`
- Secondary areas: `research_workflow`, `source_layer`, `delivery_layer`
- Execution mode: `local_direct` for all phases (no protected-contract changes, no new integration paths)

Protected contracts not authorized for change:
- ResearchAnalysisResult response shape
- EvidenceBundle schema
- task/job status semantics
- run/run_steps meaning

## Design Direction

**Frontend**: Single HTML file served by FastAPI via Jinja2Templates or StaticFiles. No JavaScript framework dependency — vanilla HTML + minimal JS + CSS for a clean, functional workbench.

**Backend additions**: Theme CRUD API routes + workbench page route.

**Architecture**:
```
FastAPI
  ├── /themes/         (NEW — CRUD)
  ├── /workbench/      (NEW — HTML page)
  ├── /research/       (existing)
  ├── /search/         (existing)
  ├── /documents/      (existing)
  └── /ingest/         (existing)
```

## Phase 0: Theme API

Status: completed

Objective: Add CRUD endpoints for themes so the workbench can display and manage theme watchlist.

Tasks:
- Create `apps/api/routes/themes.py` with endpoints:
  - `GET /themes` — list themes (filter by status)
  - `GET /themes/{theme_id}` — get single theme
  - `POST /themes` — create theme
  - `PATCH /themes/{theme_id}` — update theme status/description
- Create `packages/themes/service.py` with ThemeService
- Create `packages/themes/schemas.py` with request/response schemas
- Register router in `apps/api/main.py`

Acceptance criteria:
- All endpoints return proper JSON
- Theme creation validates required fields
- Tests pass

## Phase 1: Workbench HTML UI

Status: completed

Objective: Create a functional single-page workbench HTML served by FastAPI.

Tasks:
- Create `apps/api/routes/workbench.py` with `GET /workbench` returning HTML
- Create `apps/api/templates/workbench.html` — the single-page application
- UI sections:
  - Header: "Invest Agent — 研究情报工作台"
  - Theme watchlist panel (left sidebar or top bar)
  - Research query input (center)
  - Results panel (expandable)
  - Quick search bar

Acceptance criteria:
- Page loads at /workbench
- Theme list visible
- Research query form functional

## Phase 2: Research Workflow in UI

Status: completed (built into Phase 1 HTML)

## Phase 3: Search Integration

Status: completed (built into Phase 1 HTML)

## Phase 4: End-to-End Validation

Status: completed

Objective: Full workflow test and test suite.

Tasks:
- Test theme CRUD API
- Test workbench page loads
- Integration test: create theme → research → view results → search
- Ruff + py_compile on all new files

Acceptance criteria:
- All new tests pass
- Manual smoke test: workbench functional
- PLAN completion

## Continue Rule (ENFORCED)

Continue automatically through all phases. Do NOT stop after phase completion.
Stop ONLY for: protected-contract change required, missing dependency, repeated validation failure, data corruption, or explicit user pause.

## Validation Loop

```powershell
python -m ruff check apps/api/routes/themes.py apps/api/routes/workbench.py packages/themes/
pytest tests/test_themes_api.py tests/test_workbench.py -v
curl http://localhost:8000/themes
curl http://localhost:8000/workbench
```

## Progress

- 2026-05-01: PLAN created and fully executed.
  - Phase 0: Theme CRUD API — `packages/themes/` (schemas, service, __init__), `apps/api/routes/themes.py`, registered in main.py. 14 tests passing.
  - Phase 1-3: Workbench HTML UI — `apps/api/routes/workbench.py` + `apps/api/templates/workbench.html`. Dark-themed single-page application with theme watchlist, research submission, result rendering (theses, objections, risks, memo), evidence search with theme filter. All JS uses vanilla fetch to existing API endpoints.
  - Phase 4: Full validation — 256 tests passing (14 themes + 51 source-family + 10 task/delivery/content + 181 source regression). `/workbench` page serves 200 OK. `/themes` API operational.
  - Files created: `packages/themes/__init__.py`, `packages/themes/schemas.py`, `packages/themes/service.py`, `apps/api/routes/themes.py`, `apps/api/routes/workbench.py`, `apps/api/templates/workbench.html`, `tests/test_themes_api.py`
  - Files modified: `apps/api/main.py` (2 routers added)

## Next Action

PLAN complete. Per the overall roadmap: the project now has its first user-facing workbench. Next priorities: (1) integrate real LLM provider for research queries, (2) deploy PostgreSQL for persistent themes/data, (3) add more workbench features (research history, content generation, delivery preview).
