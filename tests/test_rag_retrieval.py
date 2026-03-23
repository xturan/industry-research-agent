from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Document
from packages.db.models.enums import SourceType
from packages.db.session import get_engine, reset_db_session_state
from packages.ingestion.service import IngestionService
from packages.rag.bundle import EvidenceBundleBuilder
from packages.rag.retrieval import ChunkRetrievalService
from packages.rag.schemas import RetrievalFilters


def _prepare_corpus(monkeypatch, tmp_path: Path) -> str:
    db_path = tmp_path / "rag_retrieval.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str((tmp_path / "raw").as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()

    engine = get_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = IngestionService(session, max_chunk_chars=300)
        first = service.ingest_uploaded_file(
            file_name="battery.md",
            file_bytes=(
                b"# Battery Chain\n\n## Supply\n"
                b"Lithium refining capacity is still constrained.\n\n"
                b"## Pricing\nContract pricing remains elevated."
            ),
            media_type="text/markdown",
            source_type=SourceType.REPORT,
        )
        second = service.ingest_uploaded_file(
            file_name="solar.md",
            file_bytes=(
                b"# Solar Buildout\n\n## Installations\n"
                b"Utility-scale projects accelerate.\n\n"
                b"## Component Cost\nModule costs keep declining."
            ),
            media_type="text/markdown",
            source_type=SourceType.ARTICLE,
        )
        third = service.ingest_uploaded_file(
            file_name="humanoid_cn.md",
            file_bytes=(
                "# \u4eba\u5f62\u673a\u5668\u4eba\u4ea7\u4e1a\n\n"
                "## \u51cf\u901f\u5668\n"
                "\u51cf\u901f\u5668\u91cf\u4ea7\u8282\u594f\u66f4\u5feb\uff0c2026\u5e74\u6709\u671b\u5148\u4f53\u73b0\u6536\u5165\u3002\n\n"
                "## \u4f3a\u670d\n"
                "\u4f3a\u670d\u6210\u672c\u4ecd\u5728\u4e0b\u63a2\uff0c\u4f46\u89c4\u6a21\u5316\u8282\u594f\u7565\u6162\u3002"
            ).encode(),
            media_type="text/markdown",
            source_type=SourceType.REPORT,
        )
        doc1 = session.get(Document, first.document_id)
        doc2 = session.get(Document, second.document_id)
        doc3 = session.get(Document, third.document_id)
        doc1.industry = "Energy Storage"
        doc2.industry = "Solar"
        doc3.industry = "Robotics"
        doc1.published_at = datetime(2026, 3, 1)
        doc2.published_at = datetime(2025, 6, 1)
        doc3.published_at = datetime(2026, 1, 15)
        session.add_all([doc1, doc2, doc3])
        session.commit()

    return db_url


def test_retrieval_returns_auditable_chunk(monkeypatch, tmp_path: Path) -> None:
    _prepare_corpus(monkeypatch, tmp_path)
    with Session(get_engine()) as session:
        response = ChunkRetrievalService(session).search_chunks(
            "lithium refining pricing", RetrievalFilters(limit=5)
        )
    assert response.items
    first = response.items[0]
    assert first.chunk_text
    assert first.citation_locator
    assert first.document_title
    assert first.score > 0
    assert "lexical" in first.score_breakdown


def test_retrieval_filters_and_empty_case(monkeypatch, tmp_path: Path) -> None:
    _prepare_corpus(monkeypatch, tmp_path)
    with Session(get_engine()) as session:
        filtered = ChunkRetrievalService(session).search_chunks(
            "pricing",
            RetrievalFilters(source_type=SourceType.REPORT, industry="Energy Storage", limit=5),
        )
        assert filtered.items
        assert all(item.source_type == SourceType.REPORT.value for item in filtered.items)

        empty = ChunkRetrievalService(session).search_chunks(
            "lithium",
            RetrievalFilters(industry="Aerospace", limit=5),
        )
        assert empty.items == []


def test_evidence_bundle_creation(monkeypatch, tmp_path: Path) -> None:
    _prepare_corpus(monkeypatch, tmp_path)
    with Session(get_engine()) as session:
        retrieval = ChunkRetrievalService(session).search_chunks(
            "utility projects", RetrievalFilters(limit=4)
        )
    bundle = EvidenceBundleBuilder().build_bundle(retrieval, group_by_document=True)
    payload = bundle.to_dict()
    assert payload["bundle_id"]
    assert payload["returned_count"] >= 1
    assert payload["grouped_documents"]
    assert payload["items"][0]["chunk_text"]
    assert "citation_locator" in payload["items"][0]


def test_retrieval_supports_chinese_substring_query(monkeypatch, tmp_path: Path) -> None:
    _prepare_corpus(monkeypatch, tmp_path)
    with Session(get_engine()) as session:
        response = ChunkRetrievalService(session).search_chunks(
            "\u4eba\u5f62\u673a\u5668\u4eba \u51cf\u901f\u5668 \u6536\u5165",
            RetrievalFilters(limit=5),
        )
    assert response.items
    assert any(
        "\u51cf\u901f\u5668" in item.chunk_text
        or "\u4eba\u5f62\u673a\u5668\u4eba" in item.chunk_text
        for item in response.items
    )


def test_postgres_no_hit_auto_falls_back(monkeypatch, tmp_path: Path) -> None:
    _prepare_corpus(monkeypatch, tmp_path)
    with Session(get_engine()) as session:
        service = ChunkRetrievalService(session)
        monkeypatch.setattr(service, "_dialect_name", lambda: "postgresql")
        monkeypatch.setattr(service, "_search_postgres", lambda *args, **kwargs: [])
        response = service.search_chunks(
            "\u4eba\u5f62\u673a\u5668\u4eba \u51cf\u901f\u5668",
            RetrievalFilters(limit=5),
        )

    assert response.retrieval_mode == "postgres_fts_fallback_v1"
    assert response.items
    assert any("fell back to lexical substring retrieval" in note for note in response.notes)
