from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from packages.db.models import DocumentStatus, SourceType


@dataclass(slots=True)
class RetrievalFilters:
    source_type: SourceType | None = None
    document_status: DocumentStatus | None = None
    industry: str | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None
    document_id: int | None = None
    theme_id: int | None = None
    limit: int = 10

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type.value if self.source_type else None,
            "document_status": self.document_status.value if self.document_status else None,
            "industry": self.industry,
            "published_from": self.published_from.isoformat() if self.published_from else None,
            "published_to": self.published_to.isoformat() if self.published_to else None,
            "document_id": self.document_id,
            "theme_id": self.theme_id,
            "limit": self.limit,
        }


@dataclass(slots=True)
class RetrievalChunkItem:
    chunk_id: int
    document_id: int
    chunk_index: int
    section_name: str | None
    chunk_text: str
    chunk_metadata: dict[str, Any] | None
    citation_locator: str | None
    citation_quote: str | None
    document_title: str
    source_uri: str | None
    publisher: str | None
    published_at: datetime | None
    source_type: str
    document_status: str
    industry: str | None
    score: float
    score_breakdown: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["published_at"] = self.published_at.isoformat() if self.published_at else None
        return payload


@dataclass(slots=True)
class RetrievalResponse:
    query: str
    retrieval_mode: str
    filters: RetrievalFilters
    total_candidates: int
    items: list[RetrievalChunkItem]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "retrieval_mode": self.retrieval_mode,
            "filters": self.filters.to_dict(),
            "total_candidates": self.total_candidates,
            "returned_count": len(self.items),
            "notes": self.notes,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(slots=True)
class EvidenceBundle:
    bundle_id: str
    query: str
    retrieval_mode: str
    filters: RetrievalFilters
    total_candidates: int
    items: list[RetrievalChunkItem]
    grouped_documents: list[dict[str, Any]]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "query": self.query,
            "retrieval_mode": self.retrieval_mode,
            "filters": self.filters.to_dict(),
            "total_candidates": self.total_candidates,
            "returned_count": len(self.items),
            "generated_at": self.generated_at,
            "grouped_documents": self.grouped_documents,
            "items": [item.to_dict() for item in self.items],
        }


def build_bundle_id(query: str, items: list[RetrievalChunkItem]) -> str:
    token = "|".join(
        [query.strip().lower(), *(f"{item.document_id}:{item.chunk_id}" for item in items)]
    )
    digest = hashlib.sha1(token.encode("utf-8")).hexdigest()[:16]
    return f"bundle_{digest}"
