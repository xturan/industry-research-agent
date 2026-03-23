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


def _seed_research_api_db(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "research_api.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str((tmp_path / "raw").as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()

    engine = get_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = IngestionService(session, max_chunk_chars=260).ingest_uploaded_file(
            file_name="research.md",
            file_bytes=(
                b"# Research Note\n\n## Supply\n"
                b"Lithium refining constraints support elevated prices.\n\n"
                b"## Counterpoint\nDemand softness could pressure volumes."
            ),
            media_type="text/markdown",
            source_type=SourceType.REPORT,
        )
        document = session.get(Document, result.document_id)
        document.industry = "Energy Storage"
        document.published_at = datetime(2026, 2, 5)
        session.add(document)
        session.commit()


def test_research_api_analyze_and_run_view(monkeypatch, tmp_path: Path) -> None:
    _seed_research_api_db(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/research/analyze",
            json={
                "query": "lithium pricing power",
                "top_k": 6,
                "industry": "Energy Storage",
                "mode": "mock",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["run_id"] > 0
        assert payload["evidence_summary"]["selected_items"] >= 1
        assert payload["theses"]
        assert payload["theses"][0]["evidence_refs"]
        assert payload["objections"]
        assert payload["evidence_judge"]["coverage"]
        assert payload["risks"]
        assert payload["final_memo"]["executive_summary"]

        run_response = client.get(f"/research/runs/{payload['run_id']}")
        assert run_response.status_code == 200
        run_payload = run_response.json()
        assert run_payload["status"] in {"succeeded", "failed"}
        assert len(run_payload["steps"]) >= 1

        empty_response = client.post(
            "/research/analyze",
            json={
                "query": "lithium pricing power",
                "top_k": 6,
                "industry": "Semiconductors",
                "mode": "mock",
            },
        )
        assert empty_response.status_code == 200
        empty_payload = empty_response.json()
        assert empty_payload["insufficient_evidence"] is True
        assert empty_payload["theses"] == []
