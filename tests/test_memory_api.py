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


def _seed_runs_and_asset(monkeypatch, tmp_path: Path) -> dict[str, int]:
    db_path = tmp_path / "memory_api.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str((tmp_path / "raw").as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()

    engine = get_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        ingestion = IngestionService(session, max_chunk_chars=280).ingest_uploaded_file(
            file_name="memory_api_seed.md",
            file_bytes=(
                b"# Battery Insight\n\n## Signal\n"
                b"Lithium processing constraints support near-term pricing.\n\n"
                b"## Risk\nDemand volatility can pressure realized margins."
            ),
            media_type="text/markdown",
            source_type=SourceType.REPORT,
        )
        document = session.get(Document, ingestion.document_id)
        document.industry = "Energy Storage"
        document.published_at = datetime(2026, 2, 14)
        session.add(document)
        session.commit()

        research = ResearchWorkflowService(session).analyze(
            ResearchAnalyzeRequest(
                query="lithium pricing power",
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
            "research_run_id": research.run_id,
            "content_run_id": content.generation_run_id,
            "asset_id": content.assets[0].asset_id,
        }


def test_memory_api_feedback_and_search_flow(monkeypatch, tmp_path: Path) -> None:
    ids = _seed_runs_and_asset(monkeypatch, tmp_path)

    with TestClient(app) as client:
        research_extract = client.post(f"/memory/extract/run/{ids['research_run_id']}")
        assert research_extract.status_code == 200

        content_extract = client.post(f"/memory/extract/run/{ids['content_run_id']}")
        assert content_extract.status_code == 200

        feedback = client.post(
            "/feedback/content",
            json={
                "content_asset_id": ids["asset_id"],
                "channel": "xiaohongshu",
                "views": 1500,
                "likes": 190,
                "comments": 24,
                "shares": 21,
                "saves": 44,
                "clicks": 52,
                "conversions": 5,
            },
        )
        assert feedback.status_code == 200
        feedback_payload = feedback.json()
        assert feedback_payload["strategy_memory_ids"]

        search = client.post(
            "/memory/search",
            json={
                "query": "lithium risk",
                "limit": 12,
                "recent_first": True,
            },
        )
        assert search.status_code == 200
        search_payload = search.json()
        assert search_payload["total"] >= 1
        assert any(
            item["memory_type"]
            in {
                "theme_memory",
                "content_strategy_memory",
                "run_memory",
            }
            for item in search_payload["items"]
        )

        account_pref = client.post(
            "/memory/account-preference",
            json={
                "scope_key": "account:default",
                "content": "Prefer concise headlines and balanced risk framing.",
                "score": 0.72,
            },
        )
        assert account_pref.status_code == 200
        assert account_pref.json()["memory_id"] > 0

        by_scope = client.get("/memory/by-scope/channel:xiaohongshu")
        assert by_scope.status_code == 200
        scope_payload = by_scope.json()
        assert scope_payload["scope_key"] == "channel:xiaohongshu"
        assert len(scope_payload["items"]) >= 1

        missing_run = client.post("/memory/extract/run/999999")
        assert missing_run.status_code == 400

        invalid_feedback = client.post(
            "/feedback/content",
            json={
                "content_asset_id": 999999,
                "channel": "xiaohongshu",
                "views": 10,
            },
        )
        assert invalid_feedback.status_code == 400
