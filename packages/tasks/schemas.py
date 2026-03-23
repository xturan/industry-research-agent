from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.content.schemas import ContentGenerateRequest
from packages.tasks.enums import TaskJobStatus, TaskType


class TaskSubmitOptions(BaseModel):
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)
    priority: int = Field(default=100, ge=1, le=1000)
    max_attempts: int = Field(default=3, ge=1, le=20)
    available_in_seconds: int = Field(default=0, ge=0, le=86400)


class ResearchAnalyzeTaskSubmitRequest(TaskSubmitOptions):
    request: ResearchAnalyzeRequest


class ContentGenerateTaskSubmitRequest(TaskSubmitOptions):
    request: ContentGenerateRequest


class DeliveryDispatchTaskSubmitRequest(TaskSubmitOptions):
    delivery_job_id: int = Field(ge=1)


class TaskAcceptedResponse(BaseModel):
    task_id: int
    task_type: TaskType
    status: TaskJobStatus
    idempotency_key: str | None
    accepted_at: datetime
    deduplicated: bool


class TaskAttemptView(BaseModel):
    id: int
    task_job_id: int
    attempt_number: int
    worker_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    metadata_json: dict[str, Any] | None


class TaskJobView(BaseModel):
    id: int
    task_type: TaskType
    status: TaskJobStatus
    priority: int
    idempotency_key: str | None
    payload_json: dict[str, Any]
    result_json: dict[str, Any] | None
    error_message: str | None
    attempt_count: int
    max_attempts: int
    available_at: datetime
    locked_at: datetime | None
    locked_by: str | None
    source_run_id: int | None
    created_at: datetime
    updated_at: datetime
    attempts: list[TaskAttemptView]


class TaskRetryResponse(BaseModel):
    task_id: int
    status: TaskJobStatus
    available_at: datetime


class TaskCancelResponse(BaseModel):
    task_id: int
    status: TaskJobStatus


class TaskRetryRequest(BaseModel):
    available_in_seconds: int = Field(default=0, ge=0, le=86400)
