from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.agents.service import ResearchWorkflowService
from packages.content.schemas import ContentFormat, ContentGenerateRequest
from packages.content.service import ContentFactoryService, ContentGenerationError
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import ContentAsset, Document, Run, RunStep, SourceType
from packages.db.models.enums import RunStatus, RunType
from packages.db.session import reset_db_session_state
from packages.ingestion.service import IngestionService


def _setup_content_db(monkeypatch, tmp_path: Path) -> str:
    db_path = tmp_path / "content_service.db"
    raw_path = tmp_path / "raw"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str(raw_path.as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return db_url


def _create_research_run(session: Session, *, industry: str = "Energy Storage") -> int:
    ingestion = IngestionService(session, max_chunk_chars=280).ingest_uploaded_file(
        file_name="content_seed.md",
        file_bytes=(
            b"# Battery Chain\n\n## Signal\n"
            b"Lithium refining constraints support elevated pricing.\n\n"
            b"## Risk\nDemand slowdown can pressure shipment volume."
        ),
        media_type="text/markdown",
        source_type=SourceType.REPORT,
    )
    document = session.get(Document, ingestion.document_id)
    document.industry = industry
    document.published_at = datetime(2026, 2, 20)
    session.add(document)
    session.commit()

    research = ResearchWorkflowService(session).analyze(
        ResearchAnalyzeRequest(
            query="lithium pricing outlook",
            top_k=6,
            industry=industry,
            mode="mock",
        )
    )
    return research.run_id


def test_content_generation_persists_all_required_formats(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_content_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        research_run_id = _create_research_run(session)
        response = ContentFactoryService(session).generate(
            ContentGenerateRequest(
                research_run_id=research_run_id,
                content_types=[
                    ContentFormat.WECHAT_ARTICLE,
                    ContentFormat.XIAOHONGSHU_POST,
                    ContentFormat.DOUYIN_SCRIPT,
                ],
                mode="mock",
            )
        )
        assert response.status == RunStatus.SUCCEEDED.value
        assert len(response.assets) == 3

        persisted_assets = session.scalars(
            select(ContentAsset).where(
                ContentAsset.id.in_([item.asset_id for item in response.assets])
            )
        ).all()
        assert len(persisted_assets) == 3
        formats = {
            (asset.meta_json or {}).get("content_format")
            for asset in persisted_assets
            if isinstance(asset.meta_json, dict)
        }
        assert formats == {
            ContentFormat.WECHAT_ARTICLE.value,
            ContentFormat.XIAOHONGSHU_POST.value,
            ContentFormat.DOUYIN_SCRIPT.value,
        }

        generation_run = session.get(Run, response.generation_run_id)
        run_steps = session.scalars(
            select(RunStep).where(RunStep.run_id == response.generation_run_id)
        ).all()
        assert generation_run is not None
        assert generation_run.run_type == RunType.CONTENT_GENERATE
        assert {
            "generate_wechat_article",
            "generate_xiaohongshu_post",
            "generate_douyin_script",
            "persist_assets",
        }.issubset({step.step_name for step in run_steps})


def test_content_generation_invalid_research_run(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_content_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        with pytest.raises(ContentGenerationError):
            ContentFactoryService(session).generate(
                ContentGenerateRequest(
                    research_run_id=99999,
                    content_types=[ContentFormat.WECHAT_ARTICLE],
                    mode="mock",
                )
            )


def test_content_generation_low_confidence_preserves_disclaimer(
    monkeypatch, tmp_path: Path
) -> None:
    db_url = _setup_content_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        _create_research_run(session, industry="Energy Storage")
        low_confidence_run = ResearchWorkflowService(session).analyze(
            ResearchAnalyzeRequest(
                query="lithium pricing outlook",
                top_k=6,
                industry="Semiconductors",
                mode="mock",
            )
        )
        response = ContentFactoryService(session).generate(
            ContentGenerateRequest(
                research_run_id=low_confidence_run.run_id,
                content_types=[
                    ContentFormat.WECHAT_ARTICLE,
                    ContentFormat.DOUYIN_SCRIPT,
                ],
                mode="mock",
            )
        )
        assert len(response.assets) == 2
        assets = session.scalars(
            select(ContentAsset).where(
                ContentAsset.id.in_([item.asset_id for item in response.assets])
            )
        ).all()
        disclaimers = []
        for asset in assets:
            meta = asset.meta_json or {}
            if isinstance(meta, dict):
                disclaimers.extend(meta.get("disclaimers", []))
        assert any("不构成" in text for text in disclaimers)
        assert any(("证据强度偏弱" in text) or ("证据仍不足" in text) for text in disclaimers)
