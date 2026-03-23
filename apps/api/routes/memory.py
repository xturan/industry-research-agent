from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from packages.memory.schemas import (
    AccountPreferenceUpsertRequest,
    AccountPreferenceUpsertResponse,
    FeedbackIngestRequest,
    FeedbackIngestResponse,
    MemoryExtractRunResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    ScopeMemoriesResponse,
)
from packages.memory.service import MemoryService, MemoryServiceError

router = APIRouter(tags=["memory"])


@router.post("/feedback/content", response_model=FeedbackIngestResponse)
def ingest_content_feedback(
    payload: FeedbackIngestRequest,
    session: Session = Depends(get_db_session),
) -> FeedbackIngestResponse:
    try:
        return MemoryService(session).ingest_content_feedback(payload)
    except MemoryServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/memory/extract/run/{run_id}", response_model=MemoryExtractRunResponse)
def extract_memory_from_run(
    run_id: int,
    session: Session = Depends(get_db_session),
) -> MemoryExtractRunResponse:
    try:
        return MemoryService(session).extract_from_run(run_id)
    except MemoryServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/memory/search", response_model=MemorySearchResponse)
def search_memory(
    payload: MemorySearchRequest,
    session: Session = Depends(get_db_session),
) -> MemorySearchResponse:
    try:
        return MemoryService(session).search(payload)
    except MemoryServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/memory/account-preference",
    response_model=AccountPreferenceUpsertResponse,
)
def upsert_account_preference(
    payload: AccountPreferenceUpsertRequest,
    session: Session = Depends(get_db_session),
) -> AccountPreferenceUpsertResponse:
    try:
        memory_id = MemoryService(session).upsert_account_preference(payload)
        return AccountPreferenceUpsertResponse(memory_id=memory_id)
    except MemoryServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/memory/by-scope/{scope_key}", response_model=ScopeMemoriesResponse)
def list_memory_by_scope(
    scope_key: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> ScopeMemoriesResponse:
    try:
        return MemoryService(session).list_by_scope(scope_key, limit=limit)
    except MemoryServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
