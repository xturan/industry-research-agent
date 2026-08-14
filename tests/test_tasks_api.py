from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from apps.api.main import app
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Document, SourceType
from packages.db.session import get_engine, reset_db_session_state
from packages.ingestion.service import IngestionService
from packages.tasks.worker import TaskWorker


def _setup_tasks_api_db(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "tasks_api.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str((tmp_path / "raw").as_posix()))
    monkeypatch.setenv("DELIVERY_EXPORT_DIR", str((tmp_path / "exports").as_posix()))
    monkeypatch.setenv("TASK_RETRY_BACKOFF_SECONDS", "0")
    get_settings.cache_clear()
    reset_db_session_state()

    engine = get_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ingestion = IngestionService(session, max_chunk_chars=260).ingest_uploaded_file(
            file_name="tasks_api_seed.md",
            file_bytes=(
                b"# Storage Insight\n\n## Signal\n"
                b"Lithium refining capacity remains constrained.\n\n"
                b"## Risk\nDemand policy volatility can weaken growth."
            ),
            media_type="text/markdown",
            source_type=SourceType.REPORT,
        )
        document = session.get(Document, ingestion.document_id)
        document.industry = "Energy Storage"
        document.published_at = datetime(2026, 2, 19)
        session.add(document)
        session.commit()


def test_tasks_api_flow_and_observability(monkeypatch, tmp_path: Path) -> None:
    _setup_tasks_api_db(monkeypatch, tmp_path)
    worker = TaskWorker(worker_id="api-worker", poll_interval_seconds=1)

    with TestClient(app) as client:
        research_submit = client.post(
            "/tasks/research/analyze",
            json={
                "idempotency_key": "api:research:1",
                "request": {
                    "query": "lithium pricing outlook",
                    "top_k": 6,
                    "industry": "Energy Storage",
                    "mode": "mock",
                },
            },
        )
        assert research_submit.status_code == 200
        research_payload = research_submit.json()
        assert research_payload["status"] == "queued"
        task_id = research_payload["task_id"]

        research_dup = client.post(
            "/tasks/research/analyze",
            json={
                "idempotency_key": "api:research:1",
                "request": {
                    "query": "lithium pricing outlook",
                    "top_k": 6,
                    "industry": "Energy Storage",
                    "mode": "mock",
                },
            },
        )
        assert research_dup.status_code == 200
        assert research_dup.json()["deduplicated"] is True
        assert research_dup.json()["task_id"] == task_id

        assert worker.run_once() is True

        research_task = client.get(f"/tasks/{task_id}")
        assert research_task.status_code == 200
        research_task_payload = research_task.json()
        assert research_task_payload["status"] == "succeeded"
        research_run_id = research_task_payload["result_json"]["run_id"]
        assert research_task_payload["result_json"]["source_acquisition"]["enabled"] is False

        source_assisted_submit = client.post(
            "/tasks/research/analyze",
            json={
                "idempotency_key": "api:research:source:1",
                "request": {
                    "query": "Assess supply from user source",
                    "mode": "mock",
                    "enable_source_acquisition": True,
                    "enable_pdf_processing": True,
                    "max_pdf_attachments_per_source": 2,
                    "max_pdf_pages_per_attachment": 10,
                    "user_provided_sources": [
                        {
                            "title": "Desk note",
                            "inline_text": "Supply remains constrained across key refiners.",
                        }
                    ],
                },
            },
        )
        assert source_assisted_submit.status_code == 200
        source_task_id = source_assisted_submit.json()["task_id"]

        assert worker.run_once() is True
        source_task = client.get(f"/tasks/{source_task_id}")
        assert source_task.status_code == 200
        source_task_payload = source_task.json()
        assert source_task_payload["status"] == "succeeded"
        source_summary = source_task_payload["result_json"]["source_acquisition"]
        assert source_summary["enabled"] is True
        assert "user_input" in source_summary["routed_sources"]
        assert source_summary["pdf_summary"]["enabled"] is True

        content_submit = client.post(
            "/tasks/content/generate",
            json={
                "idempotency_key": "api:content:1",
                "request": {
                    "research_run_id": research_run_id,
                    "content_types": [
                        "wechat_article",
                        "xiaohongshu_post",
                        "douyin_script",
                    ],
                    "mode": "mock",
                },
            },
        )
        assert content_submit.status_code == 200
        content_task_id = content_submit.json()["task_id"]

        assert worker.run_once() is True
        content_task = client.get(f"/tasks/{content_task_id}")
        assert content_task.status_code == 200
        content_payload = content_task.json()
        assert content_payload["status"] == "succeeded"
        asset_ids = [item["asset_id"] for item in content_payload["result_json"]["assets"]]
        assert len(asset_ids) >= 2

        create_delivery_job = client.post(
            "/delivery/jobs",
            json={
                "content_asset_ids": asset_ids[:2],
                "delivery_target": "export_bundle",
                "mode": "mock",
                "require_review": False,
                "source_run_id": research_run_id,
            },
        )
        assert create_delivery_job.status_code == 200
        delivery_job_id = create_delivery_job.json()["delivery_job_id"]

        delivery_submit = client.post(
            "/tasks/delivery/dispatch",
            json={
                "idempotency_key": "api:delivery:1",
                "delivery_job_id": delivery_job_id,
            },
        )
        assert delivery_submit.status_code == 200
        delivery_task_id = delivery_submit.json()["task_id"]

        assert worker.run_once() is True
        delivery_task = client.get(f"/tasks/{delivery_task_id}")
        assert delivery_task.status_code == 200
        assert delivery_task.json()["status"] == "succeeded"

        missing_task = client.get("/tasks/999999")
        assert missing_task.status_code == 404

        readyz = client.get("/readyz")
        assert readyz.status_code == 200
        assert readyz.json()["status"] == "ready"
        assert readyz.json()["database"] == "ok"

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "invest_agent_api_request_total" in metrics.text
        assert "invest_agent_task_enqueued_total" in metrics.text
