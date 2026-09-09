"""G1.1 Research Run API contract schemas.

External callers see a Research Run (not a Task). The internal Run/Task/Worker
execution details are intentionally hidden behind this contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from packages.agents.schemas import ResearchAnalyzeRequest


class ResearchRunCreateRequest(BaseModel):
    """Gateway request contract for creating a research run.

    Wraps the business `ResearchAnalyzeRequest` so the Gateway contract can grow
    independently (priority, client_metadata, callback, ...) without polluting
    the agent's input schema.
    """

    request: ResearchAnalyzeRequest


class ResearchRunAcceptedResponse(BaseModel):
    run_id: int
    status: str
    created_at: datetime
    links: dict[str, str]
    idempotency: dict[str, Any] | None = None  # {"replayed": bool} when a key was sent


class ResearchRunView(BaseModel):
    run_id: int
    run_type: str
    status: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    request: dict[str, Any]
    error: dict[str, Any] | None = None
    links: dict[str, str]


class ResearchRunResultResponse(BaseModel):
    run_id: int
    status: Literal["succeeded"]
    result: dict[str, Any]


class GatewayErrorResponse(BaseModel):
    error: dict[str, Any]


class ResearchRunCancelResponse(BaseModel):
    run_id: int
    status: str
    cancellation: dict[str, Any]  # {"requested": bool, "completed": bool}


class RunEventView(BaseModel):
    sequence: int
    event_type: str
    stage: str
    status: str
    message: str | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime


class ResearchRunEventsResponse(BaseModel):
    run_id: int
    events: list[RunEventView]
