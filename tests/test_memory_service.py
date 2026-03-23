from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.agents.service import ResearchWorkflowService
from packages.content.schemas import ContentFormat, ContentGenerateRequest
from packages.content.service import ContentFactoryService
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import ContentFeedbackEvent, Document, MemoryRecord, MemoryType, SourceType
from packages.db.session import reset_db_session_state
from packages.ingestion.service import IngestionService
from packages.memory.schemas import FeedbackIngestRequest, MemorySearchRequest
from packages.memory.service import MemoryService


def _setup_memory_db(monkeypatch, tmp_path: Path) -> str:
    db_path = tmp_path / "memory_service.db"
    raw_path = tmp_path / "raw"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str(raw_path.as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return db_url


def _bootstrap_runs(session: Session) -> dict[str, int]:
    ingestion = IngestionService(session, max_chunk_chars=280).ingest_uploaded_file(
        file_name="memory_seed.md",
        file_bytes=(
            b"# Energy Storage Note\n\n## Signal\n"
            b"Lithium refining utilization remains elevated and supports pricing.\n\n"
            b"## Risk\nPolicy shifts can reduce demand visibility."
        ),
        media_type="text/markdown",
        source_type=SourceType.REPORT,
    )
    document = session.get(Document, ingestion.document_id)
    document.industry = "Energy Storage"
    document.published_at = datetime(2026, 2, 24)
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

    return {
        "research_run_id": research.run_id,
        "content_run_id": content.generation_run_id,
        "asset_id": content.assets[0].asset_id,
    }


def test_extract_memory_from_research_run(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_memory_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        ids = _bootstrap_runs(session)
        response = MemoryService(session).extract_from_run(ids["research_run_id"])

        assert response.status == "succeeded"
        assert response.created_or_updated >= 2

        rows = session.scalars(
            select(MemoryRecord).where(MemoryRecord.id.in_(response.memory_ids))
        ).all()
        types = {row.memory_type for row in rows}
        assert MemoryType.THEME in types
        assert MemoryType.RUN_TRACE in types


def test_extract_memory_from_content_run(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_memory_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        ids = _bootstrap_runs(session)
        response = MemoryService(session).extract_from_run(ids["content_run_id"])

        assert response.status == "succeeded"
        rows = session.scalars(
            select(MemoryRecord).where(MemoryRecord.id.in_(response.memory_ids))
        ).all()
        types = {row.memory_type for row in rows}
        assert MemoryType.CONTENT_STRATEGY in types
        assert MemoryType.RUN_TRACE in types


def test_feedback_ingestion_updates_content_strategy_memory(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_memory_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        ids = _bootstrap_runs(session)
        service = MemoryService(session)

        first = service.ingest_content_feedback(
            FeedbackIngestRequest(
                content_asset_id=ids["asset_id"],
                channel="xiaohongshu",
                views=1000,
                likes=110,
                comments=18,
                shares=14,
                saves=27,
                clicks=33,
                conversions=3,
            )
        )
        second = service.ingest_content_feedback(
            FeedbackIngestRequest(
                content_asset_id=ids["asset_id"],
                channel="xiaohongshu",
                views=1800,
                likes=200,
                comments=30,
                shares=25,
                saves=50,
                clicks=60,
                conversions=5,
            )
        )

        assert first.status == "succeeded"
        assert second.status == "succeeded"
        assert second.strategy_memory_ids

        events = session.scalars(
            select(ContentFeedbackEvent).where(ContentFeedbackEvent.channel == "xiaohongshu")
        ).all()
        assert len(events) == 2

        strategy_memories = session.scalars(
            select(MemoryRecord).where(
                MemoryRecord.memory_type == MemoryType.CONTENT_STRATEGY,
                MemoryRecord.scope_key == "channel:xiaohongshu",
            )
        ).all()
        assert len(strategy_memories) == 1
        metadata_json = strategy_memories[0].metadata_json or {}
        assert metadata_json.get("event_count") == 2

        search = service.search(
            MemorySearchRequest(
                query="xiaohongshu engagement",
                limit=10,
                recent_first=True,
            )
        )
        assert search.total >= 1
        assert any(item.memory_type.value == "content_strategy_memory" for item in search.items)
