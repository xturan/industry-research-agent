from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from packages.tasks.schemas import (
    ContentGenerateTaskSubmitRequest,
    DeliveryDispatchTaskSubmitRequest,
    ResearchAnalyzeTaskSubmitRequest,
    TaskAcceptedResponse,
    TaskCancelResponse,
    TaskJobView,
    TaskRetryRequest,
    TaskRetryResponse,
)
from packages.tasks.service import TaskService, TaskServiceError

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/research/analyze", response_model=TaskAcceptedResponse)
def enqueue_research_analyze(
    payload: ResearchAnalyzeTaskSubmitRequest,
    session: Session = Depends(get_db_session),
) -> TaskAcceptedResponse:
    try:
        return TaskService(session).enqueue_research(payload)
    except TaskServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/content/generate", response_model=TaskAcceptedResponse)
def enqueue_content_generate(
    payload: ContentGenerateTaskSubmitRequest,
    session: Session = Depends(get_db_session),
) -> TaskAcceptedResponse:
    try:
        return TaskService(session).enqueue_content(payload)
    except TaskServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/delivery/dispatch", response_model=TaskAcceptedResponse)
def enqueue_delivery_dispatch(
    payload: DeliveryDispatchTaskSubmitRequest,
    session: Session = Depends(get_db_session),
) -> TaskAcceptedResponse:
    try:
        return TaskService(session).enqueue_delivery(payload)
    except TaskServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{task_id}", response_model=TaskJobView)
def get_task(
    task_id: int,
    session: Session = Depends(get_db_session),
) -> TaskJobView:
    view = TaskService(session).get_task(task_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return view


@router.post("/{task_id}/retry", response_model=TaskRetryResponse)
def retry_task(
    task_id: int,
    payload: TaskRetryRequest,
    session: Session = Depends(get_db_session),
) -> TaskRetryResponse:
    try:
        return TaskService(session).retry_task(
            task_id,
            available_in_seconds=payload.available_in_seconds,
        )
    except TaskServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{task_id}/cancel", response_model=TaskCancelResponse)
def cancel_task(
    task_id: int,
    session: Session = Depends(get_db_session),
) -> TaskCancelResponse:
    try:
        return TaskService(session).cancel_task(task_id)
    except TaskServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
