from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.agents.service import ResearchWorkflowService
from packages.agents.thesis_builder import ThesisBuilderAgent
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Document, Run, RunStep, SourceType
from packages.db.models.enums import RunStatus, StepStatus
from packages.db.session import reset_db_session_state
from packages.ingestion.service import IngestionService


def _setup_research_db(monkeypatch, tmp_path: Path) -> str:
    db_path = tmp_path / "research_workflow.db"
    raw_path = tmp_path / "raw"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str(raw_path.as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        first = IngestionService(session, max_chunk_chars=260).ingest_uploaded_file(
            file_name="battery.md",
            file_bytes=(
                b"# Battery Pricing\n\n## Signal\n"
                b"Lithium processing constraints keep contract prices elevated.\n\n"
                b"## Risk\nDemand slowdown can weaken orders."
            ),
            media_type="text/markdown",
            source_type=SourceType.REPORT,
        )
        second = IngestionService(session, max_chunk_chars=260).ingest_uploaded_file(
            file_name="supply_chain.md",
            file_bytes=(
                b"# Supply Chain Note\n\n## Signal\n"
                b"Refining utilization remains high and new capacity arrives slowly."
            ),
            media_type="text/markdown",
            source_type=SourceType.ARTICLE,
        )
        doc1 = session.get(Document, first.document_id)
        doc2 = session.get(Document, second.document_id)
        doc1.industry = "Energy Storage"
        doc2.industry = "Energy Storage"
        doc1.published_at = datetime(2026, 2, 18)
        doc2.published_at = datetime(2026, 1, 10)
        session.add_all([doc1, doc2])
        session.commit()

    return db_url


def test_multi_agent_workflow_success_and_run_trace(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_research_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        request = ResearchAnalyzeRequest(
            query="lithium pricing power",
            top_k=6,
            industry="Energy Storage",
            mode="mock",
        )
        result = ResearchWorkflowService(session).analyze(request)

        assert result.status == RunStatus.SUCCEEDED.value
        assert result.theses
        assert result.objections
        assert result.risks
        assert result.final_memo.key_theses
        assert all(thesis.evidence_refs for thesis in result.theses)
        assert result.evidence_judge.coverage

        run = session.get(Run, result.run_id)
        steps = session.scalars(select(RunStep).where(RunStep.run_id == result.run_id)).all()

    assert run is not None
    assert run.status == RunStatus.SUCCEEDED
    assert {step.step_name for step in steps} >= {
        "retrieve_evidence",
        "build_evidence_bundle",
        "supervisor_intake",
        "thesis_builder",
        "opponent",
        "evidence_judge",
        "risk_analyst",
        "synthesize_memo",
    }


def test_multi_agent_workflow_handles_no_evidence(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_research_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        result = ResearchWorkflowService(session).analyze(
            ResearchAnalyzeRequest(
                query="lithium pricing power",
                top_k=5,
                industry="Semiconductors",
                mode="mock",
            )
        )

        assert result.status == RunStatus.SUCCEEDED.value
        assert result.insufficient_evidence is True
        assert result.evidence_summary.selected_items == 0
        assert result.theses == []
        assert result.final_memo.evidence_gaps

        run = session.get(Run, result.run_id)
        skipped_steps = session.scalars(
            select(RunStep).where(
                RunStep.run_id == result.run_id,
                RunStep.status == StepStatus.SKIPPED,
            )
        ).all()

    assert run is not None
    assert run.status == RunStatus.SUCCEEDED
    assert {step.step_name for step in skipped_steps} >= {
        "thesis_builder",
        "opponent",
        "risk_analyst",
    }


def test_multi_agent_workflow_failure_path_records_failed_run(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_research_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    def _explode(*args, **kwargs):
        raise RuntimeError("forced-thesis-failure")

    monkeypatch.setattr(ThesisBuilderAgent, "run", _explode)

    with Session(engine) as session:
        result = ResearchWorkflowService(session).analyze(
            ResearchAnalyzeRequest(
                query="lithium pricing power",
                top_k=6,
                industry="Energy Storage",
                mode="mock",
            )
        )
        failed_run = session.get(Run, result.run_id)
        failed_step = session.scalar(
            select(RunStep).where(
                RunStep.run_id == result.run_id,
                RunStep.step_name == "thesis_builder",
                RunStep.status == StepStatus.FAILED,
            )
        )

    assert result.status == RunStatus.FAILED.value
    assert result.error_message is not None
    assert "forced-thesis-failure" in result.error_message
    assert failed_run is not None
    assert failed_run.status == RunStatus.FAILED
    assert failed_step is not None
