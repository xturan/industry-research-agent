from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ReadinessReport(BaseModel):
    status: str
    checks: dict[str, Any]
    failure_counts: dict[str, int]
    timestamp: datetime


class RecentFailureItem(BaseModel):
    failure_type: str
    ref_id: int
    status: str
    message: str | None
    created_at: datetime


class RecentFailuresResponse(BaseModel):
    items: list[RecentFailureItem]
