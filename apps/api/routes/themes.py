from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from packages.themes.schemas import (
    ThemeCreateRequest,
    ThemeResponse,
    ThemeStatusFilter,
    ThemeUpdateRequest,
)
from packages.themes.service import ThemeService, ThemeServiceError

router = APIRouter(prefix="/themes", tags=["themes"])


@router.get("", response_model=list[ThemeResponse])
def list_themes(
    status: ThemeStatusFilter = Query(default="all", description="Filter by theme status"),
    session: Session = Depends(get_db_session),
) -> list[ThemeResponse]:
    return ThemeService(session).list_themes(status)


@router.get("/{theme_id}", response_model=ThemeResponse)
def get_theme(
    theme_id: int,
    session: Session = Depends(get_db_session),
) -> ThemeResponse:
    theme = ThemeService(session).get_theme(theme_id)
    if theme is None:
        raise HTTPException(status_code=404, detail="Theme not found")
    return theme


@router.post("", response_model=ThemeResponse, status_code=201)
def create_theme(
    payload: ThemeCreateRequest,
    session: Session = Depends(get_db_session),
) -> ThemeResponse:
    try:
        return ThemeService(session).create_theme(payload)
    except ThemeServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{theme_id}", response_model=ThemeResponse)
def update_theme(
    theme_id: int,
    payload: ThemeUpdateRequest,
    session: Session = Depends(get_db_session),
) -> ThemeResponse:
    try:
        return ThemeService(session).update_theme(theme_id, payload)
    except ThemeServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
