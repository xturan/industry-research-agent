from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/deep-research", tags=["deep-research"])


class DeepResearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500, description="Research query")
    max_rounds: int = Field(default=12, ge=1, le=12, description="Max search rounds")


@router.post("/analyze")
def deep_research_analyze(payload: DeepResearchRequest):
    """Execute deep research with multi-round search, source tiering, and evidence chain."""
    from packages.agents.deep_research import DeepResearchAgent

    agent = DeepResearchAgent(max_rounds=payload.max_rounds, max_sources_per_round=5)
    report = agent.run(payload.query)
    return report.model_dump(mode="json")
