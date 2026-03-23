from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from apps.api.main import app
from packages.agents.schemas import ResearchAnalyzeRequest
from packages.agents.service import ResearchWorkflowService
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Document, SourceType
from packages.db.session import get_engine, reset_db_session_state
from packages.ingestion.service import IngestionService


def _seed_research_run(monkeypatch, tmp_path: Path) -> int:
    db_path = tmp_path / "content_api.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str((tmp_path / "raw").as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()

    engine = get_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        ingestion = IngestionService(session, max_chunk_chars=280).ingest_uploaded_file(
            file_name="content_api_seed.md",
            file_bytes=(
                b"# Battery Note\n\n## Signal\n"
                b"Lithium refining utilization is high and supports pricing.\n\n"
                b"## Risk\nPolicy shifts can damp demand."
            ),
            media_type="text/markdown",
            source_type=SourceType.REPORT,
        )
        document = session.get(Document, ingestion.document_id)
        document.industry = "Energy Storage"
        document.published_at = datetime(2026, 2, 8)
        session.add(document)
        session.commit()

        research = ResearchWorkflowService(session).analyze(
            ResearchAnalyzeRequest(
                query="lithium pricing outlook",
                top_k=6,
                industry="Energy Storage",
                mode="mock",
            )
        )
        return research.run_id


def test_content_api_generate_and_retrieve(monkeypatch, tmp_path: Path) -> None:
    research_run_id = _seed_research_run(monkeypatch, tmp_path)
    with TestClient(app) as client:
        generate = client.post(
            "/content/generate",
            json={
                "research_run_id": research_run_id,
                "content_types": [
                    "wechat_article",
                    "xiaohongshu_post",
                    "douyin_script",
                ],
                "mode": "mock",
                "style_hints": ["专业", "克制"],
            },
        )
        assert generate.status_code == 200
        payload = generate.json()
        assert payload["status"] == "succeeded"
        assert len(payload["assets"]) == 3

        first_asset_id = payload["assets"][0]["asset_id"]
        asset_resp = client.get(f"/content/assets/{first_asset_id}")
        assert asset_resp.status_code == 200
        asset_payload = asset_resp.json()
        assert asset_payload["meta_json"]["source_research_run_id"] == research_run_id
        assert asset_payload["meta_json"]["content_format"] in {
            "wechat_article",
            "xiaohongshu_post",
            "douyin_script",
        }

        list_resp = client.get(f"/content/by-run/{research_run_id}")
        assert list_resp.status_code == 200
        list_payload = list_resp.json()
        assert len(list_payload) >= 3

        invalid_resp = client.post(
            "/content/generate",
            json={
                "research_run_id": 999999,
                "content_types": ["wechat_article"],
                "mode": "mock",
            },
        )
        assert invalid_resp.status_code == 400
