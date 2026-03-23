from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from packages.db.models import Citation, Document, DocumentChunk

router = APIRouter(tags=["documents"])


class DocumentDetailResponse(BaseModel):
    id: int
    title: str
    source_uri: str | None
    publisher: str | None
    published_at: datetime | None
    language: str | None
    industry: str | None
    summary: str | None
    raw_storage_path: str | None
    status: str
    chunk_count: int
    citation_count: int
    created_at: datetime
    updated_at: datetime


class ChunkCitationResponse(BaseModel):
    id: int
    locator: str | None
    quote_text: str


class DocumentChunkResponse(BaseModel):
    id: int
    chunk_index: int
    section_name: str | None
    token_count: int | None
    preview_text: str
    metadata_json: dict[str, object] | None
    citation_count: int
    citations: list[ChunkCitationResponse]


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: int, session: Session = Depends(get_db_session)
) -> DocumentDetailResponse:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks_count = (
        session.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).count()
    )
    citations_count = session.query(Citation).filter(Citation.document_id == document_id).count()

    return DocumentDetailResponse(
        id=document.id,
        title=document.title,
        source_uri=document.source_uri,
        publisher=document.publisher,
        published_at=document.published_at,
        language=document.language,
        industry=document.industry,
        summary=document.summary,
        raw_storage_path=document.raw_storage_path,
        status=document.status.value,
        chunk_count=chunks_count,
        citation_count=citations_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get("/documents/{document_id}/chunks", response_model=list[DocumentChunkResponse])
def get_document_chunks(
    document_id: int, session: Session = Depends(get_db_session)
) -> list[DocumentChunkResponse]:
    if session.get(Document, document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
    ).all()
    citations = session.scalars(select(Citation).where(Citation.document_id == document_id)).all()

    citations_by_chunk: dict[int, list[Citation]] = {}
    for citation in citations:
        if citation.chunk_id is None:
            continue
        citations_by_chunk.setdefault(citation.chunk_id, []).append(citation)

    responses: list[DocumentChunkResponse] = []
    for chunk in chunks:
        chunk_citations = citations_by_chunk.get(chunk.id, [])
        responses.append(
            DocumentChunkResponse(
                id=chunk.id,
                chunk_index=chunk.chunk_index,
                section_name=chunk.section_name,
                token_count=chunk.token_count,
                preview_text=chunk.text[:240],
                metadata_json=chunk.metadata_json,
                citation_count=len(chunk_citations),
                citations=[
                    ChunkCitationResponse(
                        id=item.id,
                        locator=item.locator,
                        quote_text=item.quote_text,
                    )
                    for item in chunk_citations
                ],
            )
        )
    return responses
