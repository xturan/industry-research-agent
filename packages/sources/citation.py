from __future__ import annotations

from datetime import datetime, timezone

from packages.sources.schemas import Citation, CitationLocator, EvidenceItem

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc


def normalize_locator(locator: CitationLocator) -> str:
    if locator.external_ref:
        return locator.external_ref
    if locator.section_id:
        return locator.section_id
    if locator.page_number is not None:
        return f"page:{locator.page_number}"
    if locator.chunk_index is not None:
        return f"chunk:{locator.chunk_index}"
    return "unknown"


def normalize_citation(
    citation: Citation,
    *,
    source_name: str,
    title: str,
    external_id: str | None = None,
    retrieved_at: datetime | None = None,
) -> Citation:
    retrieved = retrieved_at or datetime.now(UTC)
    metadata = dict(citation.metadata or {})
    metadata.update(
        {
            "source_name": source_name,
            "source_id": citation.source_id,
            "title": title,
            "url": citation.source_uri,
            "published_at": (
                citation.published_at.isoformat() if citation.published_at else None
            ),
            "retrieved_at": retrieved.isoformat(),
            "locator": normalize_locator(citation.locator),
            "external_id": external_id or citation.locator.external_ref,
        }
    )
    return citation.model_copy(update={"metadata": metadata})


def normalize_evidence_item(
    item: EvidenceItem,
    *,
    source_name: str,
    external_id: str | None = None,
    retrieved_at: datetime | None = None,
) -> EvidenceItem:
    normalized_citation = normalize_citation(
        item.citation,
        source_name=source_name,
        title=item.title,
        external_id=external_id,
        retrieved_at=retrieved_at,
    )
    metadata = dict(item.metadata or {})
    metadata["citation_normalized"] = True
    return item.model_copy(update={"citation": normalized_citation, "metadata": metadata})
