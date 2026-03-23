from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.agents.service import ResearchWorkflowService
from packages.content.schemas import ContentFormat, ContentGenerateRequest
from packages.content.service import ContentFactoryService
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Document, SourceType
from packages.db.session import reset_db_session_state
from packages.delivery.enums import DeliveryJobStatus, DeliveryTarget
from packages.delivery.schemas import DeliveryJobCreateRequest
from packages.delivery.service import DeliveryService, DeliveryServiceError
from packages.ingestion.service import IngestionService


def _setup_delivery_db(monkeypatch, tmp_path: Path) -> str:
    db_path = tmp_path / "delivery_service.db"
    raw_path = tmp_path / "raw"
    export_path = tmp_path / "exports"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str(raw_path.as_posix()))
    monkeypatch.setenv("DELIVERY_EXPORT_DIR", str(export_path.as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return db_url


def _bootstrap_assets(session: Session) -> tuple[int, list[int]]:
    ingestion = IngestionService(session, max_chunk_chars=260).ingest_uploaded_file(
        file_name="delivery_seed.md",
        file_bytes=(
            b"# Battery Note\n\n## Signal\n"
            b"Lithium processing constraints support elevated pricing.\n\n"
            b"## Risk\nDemand volatility can compress margins."
        ),
        media_type="text/markdown",
        source_type=SourceType.REPORT,
    )
    document = session.get(Document, ingestion.document_id)
    document.industry = "Energy Storage"
    document.published_at = datetime(2026, 2, 16)
    session.add(document)
    session.commit()

    research = ResearchWorkflowService(session).analyze(
        ResearchAnalyzeRequest(
            query="lithium pricing power outlook",
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
    asset_ids = [item.asset_id for item in content.assets]
    return research.run_id, asset_ids


def test_delivery_create_approve_dispatch_multi_asset(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_delivery_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        run_id, asset_ids = _bootstrap_assets(session)
        service = DeliveryService(session)

        create = service.create_job(
            DeliveryJobCreateRequest(
                content_asset_ids=asset_ids[:2],
                source_run_id=run_id,
                delivery_target=DeliveryTarget.EXPORT_BUNDLE,
                require_review=True,
                mode="mock",
                metadata_json={"bundle_name": "step8_delivery_test"},
            )
        )
        assert create.item_count == 2
        assert create.status == DeliveryJobStatus.PENDING_REVIEW

        approve = service.approve_job(create.delivery_job_id)
        assert approve.status == DeliveryJobStatus.READY

        dispatch = service.dispatch_job(create.delivery_job_id)
        assert dispatch.status == DeliveryJobStatus.DISPATCHED
        assert len(dispatch.receipts) == 2
        assert all(item.status.value == "dispatched" for item in dispatch.receipts)
        assert all(item.exported_path is not None for item in dispatch.receipts)

        for item in dispatch.receipts:
            assert Path(item.exported_path or "").exists()

        loaded = service.get_job(create.delivery_job_id)
        assert loaded is not None
        assert loaded.status == DeliveryJobStatus.DISPATCHED
        assert len(loaded.items) == 2

        by_asset = service.list_by_asset(asset_ids[0])
        assert any(job.id == create.delivery_job_id for job in by_asset)
        by_run = service.list_by_run(run_id)
        assert any(job.id == create.delivery_job_id for job in by_run)


def test_delivery_invalid_transition_and_missing_job(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_delivery_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        run_id, asset_ids = _bootstrap_assets(session)
        service = DeliveryService(session)

        create = service.create_job(
            DeliveryJobCreateRequest(
                content_asset_ids=asset_ids[:2],
                source_run_id=run_id,
                delivery_target=DeliveryTarget.EXPORT_BUNDLE,
                require_review=True,
                mode="mock",
            )
        )

        with pytest.raises(DeliveryServiceError):
            service.dispatch_job(create.delivery_job_id)

        with pytest.raises(DeliveryServiceError):
            service.approve_job(999999)


def test_delivery_failed_dispatch_webhook_missing_url(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_delivery_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        run_id, asset_ids = _bootstrap_assets(session)
        service = DeliveryService(session)

        create = service.create_job(
            DeliveryJobCreateRequest(
                content_asset_ids=asset_ids[:2],
                source_run_id=run_id,
                delivery_target=DeliveryTarget.WEBHOOK,
                require_review=False,
                mode="mock",
                metadata_json={},
            )
        )
        dispatch = service.dispatch_job(create.delivery_job_id)
        assert dispatch.status == DeliveryJobStatus.FAILED
        assert all(item.status.value == "failed" for item in dispatch.receipts)
