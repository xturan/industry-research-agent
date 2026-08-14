from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from packages.agents.deep_research import DeepResearchAgent
from packages.agents.schemas import ResearchAnalyzeRequest, ResearchRunView
from packages.agents.service import ResearchWorkflowService

router = APIRouter(prefix="/research", tags=["research"])

_STRATEGY_ROUNDS = {"quick": 2, "standard": 3, "deep": 5}


@router.post("/analyze")
def analyze_research(
    payload: ResearchAnalyzeRequest,
    session: Session = Depends(get_db_session),
):
    """Unified research endpoint. Routes to Deep Research when research_strategy is set."""
    strategy = payload.research_strategy
    if strategy and strategy in _STRATEGY_ROUNDS:
        max_rounds = _STRATEGY_ROUNDS[strategy]
        agent = DeepResearchAgent(max_rounds=max_rounds, max_sources_per_round=5)
        report = agent.run(payload.query)
        return report.model_dump(mode="json")

    # Legacy pipeline
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
