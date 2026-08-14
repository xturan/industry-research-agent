"""G1.1 Research Run API Contract — external control plane.

External callers interact with Research Runs, not Tasks. Task/Worker/Queue are
internal execution-plane details hidden behind this contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from packages.research_gateway.schemas import (
    ResearchRunAcceptedResponse,
    ResearchRunCancelResponse,
    ResearchRunCreateRequest,
    ResearchRunEventsResponse,
    ResearchRunResultResponse,
    ResearchRunView,
)
from packages.research_gateway.service import ResearchRunService

router = APIRouter(prefix="/v1/research/runs", tags=["research-gateway"])


@router.post("", response_model=ResearchRunAcceptedResponse, status_code=202)
def create_research_run(
    payload: ResearchRunCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_db_session),
) -> ResearchRunAcceptedResponse:
    return ResearchRunService(session).submit(payload.request, idempotency_key=idempotency_key)


@router.get("/{run_id}", response_model=ResearchRunView)
def get_research_run(
    run_id: int,
    session: Session = Depends(get_db_session),
) -> ResearchRunView:
    return ResearchRunService(session).get_run(run_id)


@router.get("/{run_id}/result", response_model=ResearchRunResultResponse)
def get_research_run_result(
    run_id: int,
    session: Session = Depends(get_db_session),
) -> ResearchRunResultResponse:
    return ResearchRunService(session).get_result(run_id)


@router.post("/{run_id}/cancel", response_model=ResearchRunCancelResponse)
def cancel_research_run(
    run_id: int,
    response: Response,
    session: Session = Depends(get_db_session),
) -> ResearchRunCancelResponse:
    result = ResearchRunService(session).cancel_run(run_id)
    if not result.cancellation.get("completed"):
        response.status_code = 202  # cancellation requested, worker not yet stopped
    return result


@router.get("/{run_id}/events", response_model=ResearchRunEventsResponse)
def get_research_run_events(
    run_id: int,
    after_sequence: int | None = Query(default=None, ge=0),
    session: Session = Depends(get_db_session),
) -> ResearchRunEventsResponse:
    return ResearchRunService(session).get_run_events(
        run_id, after_sequence=after_sequence
    )
