from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from apps.api.main import app
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Citation, Document, DocumentChunk, Run, RunStep
from packages.db.session import get_engine, reset_db_session_state


def test_api_file_ingestion_flow(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "ingestion_api.db"
    raw_path = tmp_path / "raw"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"

    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str(raw_path.as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()

    Base.metadata.create_all(get_engine())

    with TestClient(app) as client:
        response = client.post(
            "/ingest/file",
            files={
                "file": ("api_sample.md", b"# Title\n\n## Section\nHello world.", "text/markdown")
            },
        )
        assert response.status_code == 200
        payload = response.json()
        document_id = payload["document_id"]
        run_id = payload["run_id"]

        doc_response = client.get(f"/documents/{document_id}")
        chunks_response = client.get(f"/documents/{document_id}/chunks")

    assert doc_response.status_code == 200
    assert chunks_response.status_code == 200
    assert len(chunks_response.json()) >= 1

    engine = create_engine(db_url)
    with Session(engine) as session:
        assert session.get(Document, document_id) is not None
        assert session.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        ).all()
        assert session.scalars(select(Citation).where(Citation.document_id == document_id)).all()
        assert session.get(Run, run_id) is not None
        assert session.scalars(select(RunStep).where(RunStep.run_id == run_id)).all()
