PYTHON ?= python
COMPOSE_FILE ?= infra/docker-compose.yml

.PHONY: install dev-api dev-worker task-worker-once test lint format up down compose-config migrate-up migrate-down seed-dev db-tables ingest-demo-file ingest-demo-url rag-demo-chunks rag-demo-bundle research-demo research-live-deepseek content-demo memory-demo delivery-demo tasks-demo-research evals-smoke-demo

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

dev-api:
	$(PYTHON) -m uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

dev-worker:
	$(PYTHON) -m apps.worker.main

task-worker-once:
	$(PYTHON) -m apps.worker.main --once

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

up:
	docker compose -f $(COMPOSE_FILE) up -d

down:
	docker compose -f $(COMPOSE_FILE) down

compose-config:
	docker compose -f $(COMPOSE_FILE) config

migrate-up:
	$(PYTHON) -m alembic -c packages/db/alembic.ini upgrade head

migrate-down:
	$(PYTHON) -m alembic -c packages/db/alembic.ini downgrade -1

seed-dev:
	$(PYTHON) -m packages.db.dev_seed

db-tables:
	$(PYTHON) -c "from sqlalchemy import inspect; from packages.db.session import get_engine; print('\\n'.join(inspect(get_engine()).get_table_names()))"

ingest-demo-file:
	$(PYTHON) -m packages.ingestion.dev_demo --file data/samples/energy_storage_note.md --source-type report

ingest-demo-url:
	$(PYTHON) -m packages.ingestion.dev_demo --url https://example.com --source-type article

rag-demo-chunks:
	$(PYTHON) -m packages.rag.dev_demo --query "lithium refining pricing" --mode chunks --limit 5 --ingest-sample

rag-demo-bundle:
	$(PYTHON) -m packages.rag.dev_demo --query "lithium refining pricing" --mode bundle --limit 5 --ingest-sample

research-demo:
	$(PYTHON) -m packages.agents.dev_demo --query "lithium pricing power outlook" --mode mock --top-k 6 --ingest-sample

research-live-deepseek:
	$(PYTHON) -m packages.providers.deepseek_smoke --query "lithium pricing power outlook" --top-k 6 --ingest-sample

content-demo:
	$(PYTHON) -m packages.content.dev_demo --bootstrap-sample --content-types wechat_article xiaohongshu_post douyin_script --mode mock

memory-demo:
	$(PYTHON) -m packages.memory.dev_demo --bootstrap-sample --channel xiaohongshu --query "lithium pricing power outlook"

delivery-demo:
	$(PYTHON) -m packages.delivery.dev_demo --bootstrap-sample --delivery-target export_bundle --mode mock --require-review --auto-approve --auto-dispatch

tasks-demo-research:
	$(PYTHON) -m packages.tasks.dev_demo --task-type research_analyze --query "lithium pricing power outlook" --process-once

evals-smoke-demo:
	$(PYTHON) -m packages.evals.dev_demo --query "lithium pricing outlook" --top-k 6
