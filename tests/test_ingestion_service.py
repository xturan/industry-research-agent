from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import (
    Citation,
    Document,
    DocumentChunk,
    DocumentStatus,
    Run,
    RunStatus,
    RunStep,
)
from packages.db.models.enums import StepStatus
from packages.db.session import reset_db_session_state
from packages.ingestion.service import IngestionError, IngestionService
from packages.ingestion.storage import LocalRawStorage


def _setup_sqlite_env(monkeypatch, tmp_path: Path) -> str:
    db_path = tmp_path / "ingestion_service.db"
    raw_path = tmp_path / "raw"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str(raw_path.as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()
    return db_url


def test_ingestion_persistence_roundtrip(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_sqlite_env(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    sample_file = tmp_path / "sample.md"
    sample_file.write_text(
        (
            "# Metals Outlook\n\n"
            "## Supply\n"
            "Tight refining capacity.\n\n"
            "## Demand\n"
            "Demand keeps growing."
        ),
        encoding="utf-8",
    )

    with Session(engine) as session:
        service = IngestionService(
            session, storage=LocalRawStorage(tmp_path / "raw"), max_chunk_chars=120
        )
        result = service.ingest_local_file(sample_file)

        document = session.get(Document, result.document_id)
        assert document is not None
        assert document.status == DocumentStatus.INDEXED

        chunks = session.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == result.document_id)
        ).all()
        citations = session.scalars(
            select(Citation).where(Citation.document_id == result.document_id)
        ).all()
        run = session.get(Run, result.run_id)
        steps = session.scalars(select(RunStep).where(RunStep.run_id == result.run_id)).all()

        assert len(chunks) > 0
        assert len(citations) == len(chunks)
        assert run is not None and run.status == RunStatus.SUCCEEDED
        assert {step.step_name for step in steps} >= {
            "fetch",
            "store",
            "persist_document",
            "parse",
            "chunk",
            "persist_chunks",
        }


def test_ingestion_failure_records_failed_run(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_sqlite_env(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = IngestionService(
            session, storage=LocalRawStorage(tmp_path / "raw"), max_chunk_chars=120
        )
        with pytest.raises(IngestionError):
            service.ingest_uploaded_file(
                file_name="empty.txt",
                file_bytes=b"",
            )

        failed_run = session.scalar(select(Run).order_by(Run.id.desc()))
        assert failed_run is not None
        assert failed_run.status == RunStatus.FAILED

        failed_steps = session.scalars(
            select(RunStep).where(
                RunStep.run_id == failed_run.id, RunStep.status == StepStatus.FAILED
            )
        ).all()
        assert len(failed_steps) >= 1
