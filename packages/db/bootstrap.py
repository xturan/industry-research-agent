from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.db.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    RelationType,
    SourceType,
    Theme,
    ThemeStatus,
    Thesis,
    ThesisEvidenceLink,
    ThesisStance,
    ThesisStatus,
)


def seed_minimal_dataset(session: Session) -> dict[str, int]:
    """Insert a tiny traceability-focused sample dataset for local/dev verification."""
    slug = "battery-supply-chain"
    content_hash = "sample-battery-report-2026"

    existing_link = session.scalar(
        select(ThesisEvidenceLink)
        .join(Thesis)
        .join(DocumentChunk)
        .join(Document)
        .join(Theme)
        .where(Theme.slug == slug, Document.content_hash == content_hash)
        .order_by(ThesisEvidenceLink.id.asc())
    )
    if existing_link is not None:
        return {
            "theme_id": existing_link.thesis.theme.id,
            "document_id": existing_link.chunk.document.id,
            "chunk_id": existing_link.chunk.id,
            "thesis_id": existing_link.thesis.id,
            "evidence_link_id": existing_link.id,
        }

    theme = Theme(
        name="Battery Supply Chain",
        slug=slug,
        description="Signals around battery material sourcing and pricing power.",
        status=ThemeStatus.ACTIVE,
    )
    document = Document(
        title="Global Battery Materials Outlook 2026",
        source_type=SourceType.REPORT,
        source_uri="https://example.com/reports/battery-materials-2026",
        publisher="Example Research",
        published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        language="en",
        industry="Energy Storage",
        summary="Raw material bottlenecks could pressure EV margins through 2027.",
        raw_storage_path="reports/2026/battery-materials-outlook.pdf",
        content_hash=content_hash,
        status=DocumentStatus.INDEXED,
    )
    chunk = DocumentChunk(
        document=document,
        chunk_index=0,
        section_name="Lithium Supply",
        text=(
            "Lithium hydroxide refining capacity is expanding slower than demand, "
            "which may keep contract pricing elevated in 2026."
        ),
        metadata_json={"page": 14, "section": "Lithium Supply"},
        token_count=42,
        embedding_json=[0.12, -0.04, 0.88],
        embedding_model="placeholder-mini-embed-v1",
        embedding_dimension=3,
    )
    thesis = Thesis(
        theme=theme,
        title="Battery input costs remain sticky through 2026",
        stance=ThesisStance.BULLISH,
        summary="Persistently high processing constraints could support pricing power upstream.",
        confidence_score=0.73,
        status=ThesisStatus.ACTIVE,
    )
    evidence_link = ThesisEvidenceLink(
        thesis=thesis,
        chunk=chunk,
        relation_type=RelationType.SUPPORTING,
        weight=0.84,
        note="Core evidence from report section on refining bottlenecks.",
    )

    session.add_all([theme, document, chunk, thesis, evidence_link])
    session.commit()

    return {
        "theme_id": theme.id,
        "document_id": document.id,
        "chunk_id": chunk.id,
        "thesis_id": thesis.id,
        "evidence_link_id": evidence_link.id,
    }
