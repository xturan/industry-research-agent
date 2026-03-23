from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, joinedload

from packages.db.base import Base
from packages.db.bootstrap import seed_minimal_dataset
from packages.db.models import DocumentChunk, Thesis, ThesisEvidenceLink

EXPECTED_TABLES = {
    "documents",
    "document_chunks",
    "citations",
    "themes",
    "companies",
    "events",
    "theses",
    "thesis_evidence_links",
    "thesis_risks",
    "content_assets",
    "runs",
    "run_steps",
    "memory_records",
    "content_feedback_events",
    "delivery_jobs",
    "delivery_job_items",
    "task_jobs",
    "task_attempts",
    "eval_runs",
    "eval_run_items",
}


def test_model_metadata_contains_expected_tables() -> None:
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables.keys()))


def test_roundtrip_theme_document_chunk_thesis_and_evidence_link() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    assert EXPECTED_TABLES.issubset(set(inspector.get_table_names()))

    with Session(engine) as session:
        ids = seed_minimal_dataset(session)

        stmt = (
            select(Thesis)
            .options(
                joinedload(Thesis.theme),
                joinedload(Thesis.evidence_links)
                .joinedload(ThesisEvidenceLink.chunk)
                .joinedload(DocumentChunk.document),
            )
            .where(Thesis.id == ids["thesis_id"])
        )
        thesis = session.scalar(stmt)

        assert thesis is not None
        assert thesis.theme is not None
        assert thesis.theme.id == ids["theme_id"]
        assert len(thesis.evidence_links) == 1

        evidence_link = thesis.evidence_links[0]
        assert evidence_link.id == ids["evidence_link_id"]
        assert evidence_link.chunk.id == ids["chunk_id"]
        assert evidence_link.chunk.document.id == ids["document_id"]
