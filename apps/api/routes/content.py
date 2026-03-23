from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from packages.content.schemas import (
    ContentAssetView,
    ContentGenerateRequest,
    ContentGenerationResponse,
)
from packages.content.service import ContentFactoryService, ContentGenerationError

router = APIRouter(prefix="/content", tags=["content"])


@router.post("/generate", response_model=ContentGenerationResponse)
def generate_content(
    payload: ContentGenerateRequest,
    session: Session = Depends(get_db_session),
) -> ContentGenerationResponse:
    try:
        return ContentFactoryService(session).generate(payload)
    except ContentGenerationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/assets/{asset_id}", response_model=ContentAssetView)
def get_content_asset(
    asset_id: int,
    session: Session = Depends(get_db_session),
) -> ContentAssetView:
    view = ContentFactoryService(session).get_asset(asset_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Content asset not found")
    return view


@router.get("/by-run/{run_id}", response_model=list[ContentAssetView])
def list_content_by_run(
    run_id: int,
    session: Session = Depends(get_db_session),
) -> list[ContentAssetView]:
    return ContentFactoryService(session).list_assets_by_research_run(run_id)
