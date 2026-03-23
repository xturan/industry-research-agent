from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from packages.db.models import DocumentStatus, SourceType
from packages.rag.bundle import EvidenceBundleBuilder
from packages.rag.retrieval import ChunkRetrievalService
from packages.rag.schemas import RetrievalFilters

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=400)
    source_type: SourceType | None = None
    document_status: DocumentStatus | None = None
    industry: str | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None
    document_id: int | None = None
    theme_id: int | None = None
    limit: int = Field(default=10, ge=1, le=50)


class SearchChunkItemResponse(BaseModel):
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
    published_at: str | None
    source_type: str
    document_status: str
    industry: str | None
    score: float
    score_breakdown: dict[str, float]


class SearchChunksResponse(BaseModel):
    query: str
    retrieval_mode: str
    filters: dict[str, Any]
    total_candidates: int
    returned_count: int
    notes: list[str]
    items: list[SearchChunkItemResponse]


class EvidenceBundleResponse(BaseModel):
    bundle_id: str
    query: str
    retrieval_mode: str
    filters: dict[str, Any]
    total_candidates: int
    returned_count: int
    generated_at: str
    grouped_documents: list[dict[str, Any]]
    items: list[SearchChunkItemResponse]


def _to_filters(payload: SearchRequest) -> RetrievalFilters:
    return RetrievalFilters(
        source_type=payload.source_type,
        document_status=payload.document_status,
        industry=payload.industry,
        published_from=payload.published_from,
        published_to=payload.published_to,
        document_id=payload.document_id,
        theme_id=payload.theme_id,
        limit=payload.limit,
    )


@router.post("/chunks", response_model=SearchChunksResponse)
def search_chunks(
    payload: SearchRequest, session: Session = Depends(get_db_session)
) -> SearchChunksResponse:
    filters = _to_filters(payload)
    response = ChunkRetrievalService(session).search_chunks(payload.query, filters)
    return SearchChunksResponse.model_validate(response.to_dict())


@router.post("/evidence-bundle", response_model=EvidenceBundleResponse)
def search_evidence_bundle(
    payload: SearchRequest, session: Session = Depends(get_db_session)
) -> EvidenceBundleResponse:
    filters = _to_filters(payload)
    retrieval = ChunkRetrievalService(session).search_chunks(payload.query, filters)
    bundle = EvidenceBundleBuilder().build_bundle(
        retrieval, group_by_document=True, max_items=payload.limit
    )
    return EvidenceBundleResponse.model_validate(bundle.to_dict())
