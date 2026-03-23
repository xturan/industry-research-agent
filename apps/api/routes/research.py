from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from packages.agents.schemas import ResearchAnalysisResult, ResearchAnalyzeRequest, ResearchRunView
from packages.agents.service import ResearchWorkflowService

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/analyze", response_model=ResearchAnalysisResult)
def analyze_research(
    payload: ResearchAnalyzeRequest,
    session: Session = Depends(get_db_session),
) -> ResearchAnalysisResult:
    service = ResearchWorkflowService(session)
    return service.analyze(payload)


@router.get("/runs/{run_id}", response_model=ResearchRunView)
def get_research_run(
    run_id: int,
    session: Session = Depends(get_db_session),
) -> ResearchRunView:
    run_view = ResearchWorkflowService(session).get_run_view(run_id)
    if run_view is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    return run_view
