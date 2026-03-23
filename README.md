# Invest Agent Monorepo

Production-oriented engineering scaffold for an AI application focused on industry-report mining,
evidence-based research workflows, multi-agent orchestration, and multi-channel content generation.

This repository is positioned for industry intelligence and content production, not direct securities investment advice.

## Monorepo Layout

- `apps/api` - FastAPI service
- `apps/worker` - task queue worker service
- `packages/core` - shared configuration, logging, and utilities
- `packages/db` - SQLAlchemy models, repositories, and Alembic migration setup
- `packages/ingestion` - source fetch/store/parse/chunk/persist ingestion pipeline
- `packages/agents` - deterministic multi-agent research workflow (v1) with provider abstraction
- `packages/providers` - shared LLM transport abstraction and DeepSeek provider client
- `packages/content` - deterministic content factory layer for multi-platform asset generation
- `packages/delivery` - delivery job orchestration with review/approval and deterministic dispatch connectors
- `packages/tasks` - PostgreSQL/SQLite-backed async task queue, worker claim/execute loop, retries, idempotency
- `packages/rag` - RAG interface placeholders
- `packages/memory` - durable memory extraction/search and growth-feedback loop services
- `packages/evals` - deterministic eval rubrics, smoke runner, and eval persistence
- `packages/policy` - deterministic policy/guardrail checks for research/content/delivery
- `packages/registry` - versionable template/policy/style-pack registry
- `packages/ops` - readiness and recent-failure reporting services
- `infra` - local Docker Compose and infrastructure notes
- `tests` - API, config, and database tests

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   make install
   ```
3. Copy environment file and adjust values as needed:
   ```bash
   cp .env.example .env
   ```
4. Optional for live DeepSeek research mode:
   - set `DEEPSEEK_API_KEY`
   - prefer `DEEPSEEK_RESEARCH_MODEL=deepseek-chat` for faster structured JSON workflows
   - optional per-step model routing via:
     - `DEEPSEEK_MODEL_SUPERVISOR_INTAKE`
     - `DEEPSEEK_MODEL_THESIS_BUILDER`
     - `DEEPSEEK_MODEL_OPPONENT`
     - `DEEPSEEK_MODEL_EVIDENCE_JUDGE`
     - `DEEPSEEK_MODEL_RISK_ANALYST`
     - `DEEPSEEK_MODEL_SYNTHESIZE_MEMO`
   - keep `LLM_PROVIDER=mock` for safe default unless you explicitly want live LLM mode

PowerShell tip:
- `Invoke-RestMethod` renders nested arrays as `System.Object[]` in table/list view.
- To inspect full nested payload, pipe to JSON:
  ```powershell
  $resp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/research/analyze" -ContentType "application/json" -Body '{"query":"人形机器人 2026 收入兑现环节","top_k":6,"mode":"llm","provider":"deepseek"}'
  $resp | ConvertTo-Json -Depth 100
  ```

## Run Commands

- Start local infra (PostgreSQL + Redis):
  ```bash
  make up
  ```
- Run API:
  ```bash
  make dev-api
  ```
- Run worker:
  ```bash
  make dev-worker
  ```
- Run one worker tick (claim one eligible task if exists):
  ```bash
  make task-worker-once
  ```
- Stop local infra:
  ```bash
  make down
  ```

## Database Migrations and Seed

- Apply migrations:
  ```bash
  make migrate-up
  ```
- Roll back one migration:
  ```bash
  make migrate-down
  ```
- Seed a tiny traceability dataset (theme -> document -> chunk -> thesis -> evidence link):
  ```bash
  make seed-dev
  ```
- List current tables for the configured database:
  ```bash
  make db-tables
  ```

## Ingestion Endpoints

- `POST /ingest/file` - multipart file upload ingestion (`.txt`, `.md`, `.html`)
- `POST /ingest/url` - URL-based ingestion for standard web pages
- `GET /documents/{document_id}` - document metadata and status
- `GET /documents/{document_id}/chunks` - chunk summaries and citations

## Retrieval Endpoints (RAG v1)

- `POST /search/chunks` - chunk-level retrieval with metadata filters and explainable scoring
- `POST /search/evidence-bundle` - auditable evidence bundle builder for downstream thesis/content agents

## Multi-Agent Research Endpoints

- `POST /research/analyze` - run multi-agent workflow over retrieved evidence (`mode=mock` by default, `mode=llm` + `provider=deepseek` supported)
- `GET /research/runs/{run_id}` - inspect persisted run and step outputs for auditability

## Content Factory Endpoints

- `POST /content/generate` - generate platform content assets from `research_run_id` or supplied memo payload
- `GET /content/assets/{asset_id}` - retrieve persisted content asset details
- `GET /content/by-run/{run_id}` - list assets generated from a research run

## Memory and Feedback Endpoints

- `POST /feedback/content` - record content performance metrics and refresh strategy memory
- `POST /memory/extract/run/{run_id}` - extract reusable memory records from an existing run
- `POST /memory/search` - search memory by type/scope/keywords with deterministic ranking
- `POST /memory/account-preference` - upsert account-level preference memory
- `GET /memory/by-scope/{scope_key}` - inspect memories by scope prefix

## Delivery Endpoints

- `POST /delivery/jobs` - create delivery jobs from one or more content assets
- `POST /delivery/jobs/{job_id}/approve` - approve a pending-review delivery job
- `POST /delivery/jobs/{job_id}/dispatch` - dispatch approved jobs via deterministic connectors
- `GET /delivery/jobs/{job_id}` - inspect delivery job details and item-level status
- `GET /delivery/by-asset/{asset_id}` - list delivery jobs associated with a content asset
- `GET /delivery/by-run/{run_id}` - list delivery jobs associated with a source run

## Async Task Endpoints

- `POST /tasks/research/analyze` - enqueue research analysis task
- `POST /tasks/content/generate` - enqueue content generation task
- `POST /tasks/delivery/dispatch` - enqueue delivery dispatch task
- `GET /tasks/{task_id}` - inspect task metadata, attempts, result/error
- `POST /tasks/{task_id}/retry` - requeue failed/dead-letter/cancelled task
- `POST /tasks/{task_id}/cancel` - cancel queued/running task

## Evals / Ops / Registry Endpoints

- `POST /evals/run-smoke` - run deterministic smoke eval and persist results
- `GET /evals/runs/{eval_run_id}` - inspect persisted eval run + case items
- `GET /ops/readiness-report` - system readiness snapshot (DB, dirs, worker hint, failures)
- `GET /ops/failures/recent` - recent failed tasks/runs/delivery/evals
- `GET /registry/templates` - list versioned content templates/style packs
- `GET /registry/policies` - list versioned policy bundles

## Ingestion Demo

- Ingest the bundled local markdown sample:
  ```bash
  make ingest-demo-file
  ```
- Ingest a URL sample:
  ```bash
  make ingest-demo-url
  ```

- Run chunk retrieval demo (auto-ingests sample first):
  ```bash
  make rag-demo-chunks
  ```

- Run evidence bundle demo (auto-ingests sample first):
  ```bash
  make rag-demo-bundle
  ```

- Run multi-agent research demo (auto-ingests sample first):
  ```bash
  make research-demo
  ```
- Run manual DeepSeek smoke demo for research (requires `DEEPSEEK_API_KEY`):
  ```bash
  make research-live-deepseek
  ```

- Run content factory demo (auto-ingests sample, runs research, then generates assets):
  ```bash
  make content-demo
  ```

- Run memory + feedback loop demo (auto-ingests sample, runs research/content, ingests feedback, extracts/searches memory):
  ```bash
  make memory-demo
  ```

- Run delivery demo (auto-ingests sample, runs research/content, creates delivery job, approves, dispatches):
  ```bash
  make delivery-demo
  ```
- Run async task demo for research enqueue + one worker execution:
  ```bash
  make tasks-demo-research
  ```
- Run smoke eval demo:
  ```bash
  make evals-smoke-demo
  ```

Raw source files are persisted under `data/raw/` for later traceability.

## Validation Commands

- Tests:
  ```bash
  make test
  ```
- Lint:
  ```bash
  make lint
  ```
- Format:
  ```bash
  make format
  ```
- Docker Compose config check:
  ```bash
  make compose-config
  ```
- API health check:
  ```bash
  curl http://127.0.0.1:8000/healthz
  ```
- API readiness check:
  ```bash
  curl http://127.0.0.1:8000/readyz
  ```
- Metrics check:
  ```bash
  curl http://127.0.0.1:8000/metrics
  ```
- File ingestion check:
  ```bash
  curl -X POST "http://127.0.0.1:8000/ingest/file" -F "file=@data/samples/energy_storage_note.md"
  ```
- Chunk retrieval check:
  ```bash
  curl -X POST "http://127.0.0.1:8000/search/chunks" \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"lithium refining pricing\",\"limit\":5}"
  ```
- Multi-agent research check:
  ```bash
  curl -X POST "http://127.0.0.1:8000/research/analyze" \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"lithium pricing power outlook\",\"top_k\":6,\"mode\":\"mock\"}"
  ```
- DeepSeek-backed research check (manual, requires key):
  ```bash
  curl -X POST "http://127.0.0.1:8000/research/analyze" \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"lithium pricing power outlook\",\"top_k\":6,\"mode\":\"llm\",\"provider\":\"deepseek\",\"enable_thinking\":false}"
  ```
- DeepSeek per-step model override at request time:
  ```bash
  curl -X POST "http://127.0.0.1:8000/research/analyze" \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"humanoid robotics revenue path\",\"top_k\":6,\"mode\":\"llm\",\"provider\":\"deepseek\",\"model\":\"deepseek-chat\",\"step_models\":{\"thesis_builder\":\"deepseek-reasoner\",\"synthesize_memo\":\"deepseek-reasoner\"}}"
  ```
- Content generation check:
  ```bash
  curl -X POST "http://127.0.0.1:8000/content/generate" \
    -H "Content-Type: application/json" \
    -d "{\"research_run_id\":1,\"content_types\":[\"wechat_article\",\"xiaohongshu_post\",\"douyin_script\"],\"mode\":\"mock\"}"
  ```
- Extract memory from run:
  ```bash
  curl -X POST "http://127.0.0.1:8000/memory/extract/run/1"
  ```
- Record feedback and refresh content-strategy memory:
  ```bash
  curl -X POST "http://127.0.0.1:8000/feedback/content" \
    -H "Content-Type: application/json" \
    -d "{\"content_asset_id\":1,\"channel\":\"xiaohongshu\",\"views\":1200,\"likes\":120,\"comments\":20,\"shares\":15,\"saves\":30,\"clicks\":40,\"conversions\":4}"
  ```
- Search memory:
  ```bash
  curl -X POST "http://127.0.0.1:8000/memory/search" \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"lithium risk\",\"limit\":5,\"recent_first\":true}"
  ```
- Upsert account preference memory:
  ```bash
  curl -X POST "http://127.0.0.1:8000/memory/account-preference" \
    -H "Content-Type: application/json" \
    -d "{\"scope_key\":\"account:default\",\"content\":\"Prefer concise risk-balanced copy.\",\"score\":0.7}"
  ```
- Create delivery job:
  ```bash
  curl -X POST "http://127.0.0.1:8000/delivery/jobs" \
    -H "Content-Type: application/json" \
    -d "{\"content_asset_ids\":[1,2],\"delivery_target\":\"export_bundle\",\"mode\":\"mock\",\"require_review\":true,\"source_run_id\":1}"
  ```
- Approve and dispatch delivery job:
  ```bash
  curl -X POST "http://127.0.0.1:8000/delivery/jobs/1/approve"
  curl -X POST "http://127.0.0.1:8000/delivery/jobs/1/dispatch"
  ```
- Enqueue async research/content/delivery tasks:
  ```bash
  curl -X POST "http://127.0.0.1:8000/tasks/research/analyze" \
    -H "Content-Type: application/json" \
    -d "{\"idempotency_key\":\"rq-1\",\"request\":{\"query\":\"lithium pricing power outlook\",\"top_k\":6,\"mode\":\"mock\"}}"
  curl -X POST "http://127.0.0.1:8000/tasks/content/generate" \
    -H "Content-Type: application/json" \
    -d "{\"idempotency_key\":\"cg-1\",\"request\":{\"research_run_id\":1,\"content_types\":[\"wechat_article\",\"xiaohongshu_post\",\"douyin_script\"],\"mode\":\"mock\"}}"
  curl -X POST "http://127.0.0.1:8000/tasks/delivery/dispatch" \
    -H "Content-Type: application/json" \
    -d "{\"idempotency_key\":\"dd-1\",\"delivery_job_id\":1}"
  ```
- Poll async task status:
  ```bash
  curl http://127.0.0.1:8000/tasks/1
  ```
- Run smoke eval:
  ```bash
  curl -X POST "http://127.0.0.1:8000/evals/run-smoke" \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"lithium pricing outlook\",\"top_k\":6,\"bootstrap_sample\":true}"
  ```
- Readiness report and recent failures:
  ```bash
  curl http://127.0.0.1:8000/ops/readiness-report
  curl http://127.0.0.1:8000/ops/failures/recent
  ```
- Registry listing:
  ```bash
  curl http://127.0.0.1:8000/registry/templates
  curl http://127.0.0.1:8000/registry/policies
  ```

## TODO Markers for Next Steps

- Add pgvector-backed embedding columns and ANN indexes for `document_chunks` retrieval.
- Add PDF parser improvements (digitally-readable first) and OCR adapter later if needed.
- Add additional LLM providers and model routing policies beyond DeepSeek research integration.
- Add richer agent policies, self-reflection loops, and scoring/evals integration for research quality.
- Integrate real LLM provider in `packages/content/provider.py` for richer generation quality.
- Add brand/style packs and title A/B testing for content generation quality uplift.
- Add publishing connectors, cover image generation, and growth feedback loop.
- Add memory-informed hooks into research planning and content generation prompts/policies.
- Add hybrid memory retrieval (keyword + pgvector) and retention/forgetting policies.
- Integrate real delivery connectors with credential management and platform auth flows.
- Add delivery scheduling, retry policy, rate limiting, and attribution analytics.
- Implement hybrid retrieval upgrades and optional embedding-based search in `packages/rag`.
- Integrate MCP-compatible tool adapters behind stable interfaces.
- Extend queue backend with Redis streams and autoscaling worker coordination.
- Add richer eval datasets, LLM-as-judge options, and prompt/template experiment pipelines.
- Add policy dashboards, approval workflows, and deployment-grade policy enforcement toggles.
- Add OTEL tracing, SLO alerts, and production deployment manifests.
