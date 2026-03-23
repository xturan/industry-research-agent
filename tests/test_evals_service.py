from __future__ import annotations

from datetime import datetime
from pathlib import Path

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
from packages.evals.service import EvalService
from packages.ingestion.service import IngestionService
from packages.policy.service import PolicyChecker
from packages.rag.bundle import EvidenceBundleBuilder
from packages.rag.retrieval import ChunkRetrievalService


def _setup_eval_db(monkeypatch, tmp_path: Path) -> str:
    db_path = tmp_path / "evals_service.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str((tmp_path / "raw").as_posix()))
    monkeypatch.setenv("DELIVERY_EXPORT_DIR", str((tmp_path / "exports").as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return db_url


def _seed_eval_data(session: Session) -> int:
    ingestion = IngestionService(session, max_chunk_chars=260).ingest_uploaded_file(
        file_name="evals_seed.md",
        file_bytes=(
            b"# Industry Note\n\n## Signal\n"
            b"Lithium refining bottlenecks support resilient pricing.\n\n"
            b"## Risk\nDemand softness can pressure shipment growth."
        ),
        media_type="text/markdown",
        source_type=SourceType.REPORT,
    )
    document = session.get(Document, ingestion.document_id)
    document.industry = "Energy Storage"
    document.published_at = datetime(2026, 2, 25)
    session.add(document)
    session.commit()
    return ingestion.document_id


def test_evals_for_rag_research_content_and_policy(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_eval_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        _seed_eval_data(session)
        eval_service = EvalService(session)

        retrieval = ChunkRetrievalService(session).search_chunks("lithium pricing outlook")
        rag_cases = eval_service.evaluate_rag_chunks_payload(retrieval.to_dict())
        assert any(item.case_name == "rag_items_non_empty" and item.passed for item in rag_cases)

        bundle = EvidenceBundleBuilder().build_bundle(
            retrieval,
            group_by_document=True,
            max_items=5,
        )
        bundle_cases = eval_service.evaluate_evidence_bundle_payload(bundle.to_dict())
        assert any(item.case_name == "bundle_has_items" and item.passed for item in bundle_cases)

        research = ResearchWorkflowService(session).analyze(
            ResearchAnalyzeRequest(query="lithium pricing outlook", top_k=6, mode="mock")
        )
        research_cases = eval_service.evaluate_research_payload(research.model_dump(mode="json"))
        assert any(
            item.case_name == "research_thesis_evidence_refs" and item.passed
            for item in research_cases
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
        content_payload = []
        for summary in content.assets:
            asset = ContentFactoryService(session).get_asset(summary.asset_id)
            assert asset is not None
            content_payload.append(asset.model_dump(mode="json"))
        content_cases = eval_service.evaluate_content_payload(content_payload)
        assert any(
            item.case_name == "content_assets_exist" and item.passed
            for item in content_cases
        )

        checker = PolicyChecker()
        buy_sell = checker.check_content_text(
            title="urgent market call",
            body="Strong buy recommendation. Buy now before rebound.",
            disclaimers=["research only"],
        )
        assert buy_sell.passed is False
        assert any(issue.code == "forbidden_recommendation_phrase" for issue in buy_sell.issues)

        missing_disclaimer = checker.check_content_text(
            title="industry outlook",
            body="This is a neutral update with no explicit disclaimer.",
            disclaimers=[],
        )
        assert missing_disclaimer.passed is False
        assert any(issue.code == "missing_disclaimer" for issue in missing_disclaimer.issues)
