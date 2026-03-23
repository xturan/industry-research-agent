from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from packages.delivery.schemas import (
    DeliveryApprovalResponse,
    DeliveryDispatchResponse,
    DeliveryJobCreateRequest,
    DeliveryJobCreateResponse,
    DeliveryJobView,
)
from packages.delivery.service import DeliveryService, DeliveryServiceError

router = APIRouter(prefix="/delivery", tags=["delivery"])


@router.post("/jobs", response_model=DeliveryJobCreateResponse)
def create_delivery_job(
    payload: DeliveryJobCreateRequest,
    session: Session = Depends(get_db_session),
) -> DeliveryJobCreateResponse:
    try:
        return DeliveryService(session).create_job(payload)
    except DeliveryServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/approve", response_model=DeliveryApprovalResponse)
def approve_delivery_job(
    job_id: int,
    session: Session = Depends(get_db_session),
) -> DeliveryApprovalResponse:
    try:
        return DeliveryService(session).approve_job(job_id)
    except DeliveryServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/dispatch", response_model=DeliveryDispatchResponse)
def dispatch_delivery_job(
    job_id: int,
    session: Session = Depends(get_db_session),
) -> DeliveryDispatchResponse:
    try:
        return DeliveryService(session).dispatch_job(job_id)
    except DeliveryServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}", response_model=DeliveryJobView)
def get_delivery_job(
    job_id: int,
    session: Session = Depends(get_db_session),
) -> DeliveryJobView:
    view = DeliveryService(session).get_job(job_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Delivery job not found")
    return view


@router.get("/by-asset/{asset_id}", response_model=list[DeliveryJobView])
def list_delivery_jobs_by_asset(
    asset_id: int,
    session: Session = Depends(get_db_session),
) -> list[DeliveryJobView]:
    return DeliveryService(session).list_by_asset(asset_id)


@router.get("/by-run/{run_id}", response_model=list[DeliveryJobView])
def list_delivery_jobs_by_run(
    run_id: int,
    session: Session = Depends(get_db_session),
) -> list[DeliveryJobView]:
    return DeliveryService(session).list_by_run(run_id)
