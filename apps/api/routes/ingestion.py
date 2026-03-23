from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import AnyHttpUrl, BaseModel
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from packages.db.models import SourceType
from packages.ingestion.service import IngestionError, IngestionService

router = APIRouter(prefix="/ingest", tags=["ingestion"])


class IngestUrlRequest(BaseModel):
    url: AnyHttpUrl
    source_type: SourceType = SourceType.ARTICLE


class IngestResponse(BaseModel):
    document_id: int
    run_id: int
    chunks_count: int
    citations_count: int
    status: str
    ingested_at: datetime


@router.post("/file", response_model=IngestResponse)
def ingest_file(
    file: UploadFile = File(...),
    source_type: SourceType = Form(SourceType.OTHER),
    session: Session = Depends(get_db_session),
) -> IngestResponse:
    try:
        file_bytes = file.file.read()
        service = IngestionService(session)
        result = service.ingest_uploaded_file(
            file_name=file.filename or "uploaded.txt",
            file_bytes=file_bytes,
            media_type=file.content_type,
            source_type=source_type,
        )
        return IngestResponse(
            document_id=result.document_id,
            run_id=result.run_id,
            chunks_count=result.chunks_count,
            citations_count=result.citations_count,
            status=result.status,
            ingested_at=datetime.now(timezone.utc),
        )
    except IngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/url", response_model=IngestResponse)
def ingest_url(
    payload: IngestUrlRequest,
    session: Session = Depends(get_db_session),
) -> IngestResponse:
    try:
        service = IngestionService(session)
        result = service.ingest_url(str(payload.url), source_type=payload.source_type)
        return IngestResponse(
            document_id=result.document_id,
            run_id=result.run_id,
            chunks_count=result.chunks_count,
            citations_count=result.citations_count,
            status=result.status,
            ingested_at=datetime.now(timezone.utc),
        )
    except IngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
