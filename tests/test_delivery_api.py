from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from apps.api.main import app
from packages.agents.schemas import ResearchAnalyzeRequest
from packages.agents.service import ResearchWorkflowService
from packages.content.schemas import ContentFormat, ContentGenerateRequest
from packages.content.service import ContentFactoryService
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Document, SourceType
from packages.db.session import get_engine, reset_db_session_state
from packages.ingestion.service import IngestionService


def _seed_assets(monkeypatch, tmp_path: Path) -> dict[str, object]:
    db_path = tmp_path / "delivery_api.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str((tmp_path / "raw").as_posix()))
    monkeypatch.setenv("DELIVERY_EXPORT_DIR", str((tmp_path / "exports").as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()

    engine = get_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        ingestion = IngestionService(session, max_chunk_chars=260).ingest_uploaded_file(
            file_name="delivery_api_seed.md",
            file_bytes=(
                b"# Market Note\n\n## Signal\n"
                b"Refining bottlenecks keep battery inputs tight.\n\n"
                b"## Risk\nDemand softening can pressure shipment growth."
            ),
            media_type="text/markdown",
            source_type=SourceType.REPORT,
        )
        document = session.get(Document, ingestion.document_id)
        document.industry = "Energy Storage"
        document.published_at = datetime(2026, 2, 13)
        session.add(document)
        session.commit()

        research = ResearchWorkflowService(session).analyze(
            ResearchAnalyzeRequest(
                query="battery supply chain pricing",
                top_k=6,
                industry="Energy Storage",
                mode="mock",
            )
        )
        content = ContentFactoryService(session).generate(
            ContentGenerateRequest(
                research_run_id=research.run_id,
                content_types=[
                    ContentFormat.WECHAT_ARTICLE,
                    ContentFormat.XIAOHONGSHU_POST,
                    ContentFormat.DOUYIN_SCRIPT,
                ],
                mode="mock",
            )
        )
        return {
            "run_id": research.run_id,
            "asset_ids": [item.asset_id for item in content.assets],
        }


def test_delivery_api_flow(monkeypatch, tmp_path: Path) -> None:
    seed = _seed_assets(monkeypatch, tmp_path)
    asset_ids = seed["asset_ids"]

    with TestClient(app) as client:
        create = client.post(
            "/delivery/jobs",
            json={
                "content_asset_ids": asset_ids[:2],
                "delivery_target": "export_bundle",
                "mode": "mock",
                "require_review": True,
                "source_run_id": seed["run_id"],
            },
        )
        assert create.status_code == 200
        create_payload = create.json()
        job_id = create_payload["delivery_job_id"]
        assert create_payload["item_count"] == 2
        assert create_payload["status"] == "pending_review"

        dispatch_before_approve = client.post(f"/delivery/jobs/{job_id}/dispatch")
        assert dispatch_before_approve.status_code == 400

        approve = client.post(f"/delivery/jobs/{job_id}/approve")
        assert approve.status_code == 200
        assert approve.json()["status"] == "ready"

        dispatch = client.post(f"/delivery/jobs/{job_id}/dispatch")
        assert dispatch.status_code == 200
        dispatch_payload = dispatch.json()
        assert dispatch_payload["status"] == "dispatched"
        assert len(dispatch_payload["receipts"]) == 2
        assert all(item["exported_path"] for item in dispatch_payload["receipts"])

        get_job = client.get(f"/delivery/jobs/{job_id}")
        assert get_job.status_code == 200
        assert get_job.json()["id"] == job_id
        assert len(get_job.json()["items"]) == 2

        by_asset = client.get(f"/delivery/by-asset/{asset_ids[0]}")
        assert by_asset.status_code == 200
        assert any(item["id"] == job_id for item in by_asset.json())

        by_run = client.get(f"/delivery/by-run/{seed['run_id']}")
        assert by_run.status_code == 200
        assert any(item["id"] == job_id for item in by_run.json())

        invalid_job = client.post("/delivery/jobs/999999/approve")
        assert invalid_job.status_code == 400


def test_delivery_api_failed_webhook_dispatch(monkeypatch, tmp_path: Path) -> None:
    seed = _seed_assets(monkeypatch, tmp_path)
    asset_ids = seed["asset_ids"]

    with TestClient(app) as client:
        create = client.post(
            "/delivery/jobs",
            json={
                "content_asset_ids": asset_ids[:2],
                "delivery_target": "webhook",
                "mode": "mock",
                "require_review": False,
                "source_run_id": seed["run_id"],
                "metadata_json": {},
            },
        )
        assert create.status_code == 200
        job_id = create.json()["delivery_job_id"]

        dispatch = client.post(f"/delivery/jobs/{job_id}/dispatch")
        assert dispatch.status_code == 200
        payload = dispatch.json()
        assert payload["status"] == "failed"
        assert all(item["status"] == "failed" for item in payload["receipts"])
