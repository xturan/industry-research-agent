from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from packages.evals.schemas import EvalRunView, SmokeEvalRequest, SmokeEvalResponse
from packages.evals.service import EvalService, EvalServiceError

router = APIRouter(prefix="/evals", tags=["evals"])


@router.post("/run-smoke", response_model=SmokeEvalResponse)
def run_smoke_eval(
    payload: SmokeEvalRequest,
    session: Session = Depends(get_db_session),
) -> SmokeEvalResponse:
    try:
        return EvalService(session).run_smoke(payload)
    except EvalServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs/{eval_run_id}", response_model=EvalRunView)
def get_eval_run(
    eval_run_id: int,
    session: Session = Depends(get_db_session),
) -> EvalRunView:
    view = EvalService(session).get_eval_run(eval_run_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Eval run not found")
    return view
