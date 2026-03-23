from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from apps.api.main import app
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Document
from packages.db.models.enums import SourceType
from packages.db.session import get_engine, reset_db_session_state
from packages.ingestion.service import IngestionService


def _seed_search_api_db(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "rag_api.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str((tmp_path / "raw").as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()

    engine = get_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = IngestionService(session, max_chunk_chars=280).ingest_uploaded_file(
            file_name="grid_note.md",
            file_bytes=(
                b"# Grid Storage\n\n## Signal\n"
                b"Lithium processing constraints support pricing power.\n\n"
                b"## Risk\nProcurement delays can hurt delivery timelines."
            ),
            media_type="text/markdown",
            source_type=SourceType.REPORT,
        )
        document = session.get(Document, result.document_id)
        document.industry = "Energy Storage"
        document.published_at = datetime(2026, 2, 1)
        session.add(document)
        session.commit()


def test_search_api_endpoints(monkeypatch, tmp_path: Path) -> None:
    _seed_search_api_db(monkeypatch, tmp_path)
    with TestClient(app) as client:
        chunks_resp = client.post(
            "/search/chunks",
            json={"query": "lithium pricing power", "limit": 5, "industry": "Energy Storage"},
        )
        assert chunks_resp.status_code == 200
        chunks_payload = chunks_resp.json()
        assert chunks_payload["returned_count"] >= 1
        assert chunks_payload["items"][0]["chunk_text"]
        assert "citation_locator" in chunks_payload["items"][0]
        assert "document_title" in chunks_payload["items"][0]
        assert "score" in chunks_payload["items"][0]

        bundle_resp = client.post(
            "/search/evidence-bundle",
            json={"query": "lithium pricing power", "limit": 5, "industry": "Energy Storage"},
        )
        assert bundle_resp.status_code == 200
        bundle_payload = bundle_resp.json()
        assert bundle_payload["bundle_id"]
        assert bundle_payload["grouped_documents"]
        assert bundle_payload["items"][0]["citation_locator"]

        empty_resp = client.post(
            "/search/chunks",
            json={"query": "lithium", "limit": 5, "industry": "Semiconductors"},
        )
        assert empty_resp.status_code == 200
        assert empty_resp.json()["returned_count"] == 0
