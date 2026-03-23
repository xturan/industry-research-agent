from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from packages.ops.schemas import ReadinessReport, RecentFailuresResponse
from packages.ops.service import OpsService

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/readiness-report", response_model=ReadinessReport)
def readiness_report(session: Session = Depends(get_db_session)) -> ReadinessReport:
    return OpsService(session).readiness_report()


@router.get("/failures/recent", response_model=RecentFailuresResponse)
def recent_failures(
    limit: int = Query(default=30, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> RecentFailuresResponse:
    return OpsService(session).recent_failures(limit=limit)
