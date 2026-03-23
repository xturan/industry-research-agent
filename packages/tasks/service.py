from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.core.logging import bind_log_context
from packages.tasks.claim import compute_retry_delay_seconds
from packages.tasks.enums import TaskJobStatus, TaskType
from packages.tasks.handlers import NonRetryableTaskError, TaskHandlers
from packages.tasks.metrics import (
    mark_task_enqueued,
    mark_task_failed,
    mark_task_succeeded,
    track_task_execution,
)
from packages.tasks.repository import TaskRepository, to_task_view
from packages.tasks.schemas import (
    ContentGenerateTaskSubmitRequest,
    DeliveryDispatchTaskSubmitRequest,
    ResearchAnalyzeTaskSubmitRequest,
    TaskAcceptedResponse,
    TaskCancelResponse,
    TaskJobView,
    TaskRetryResponse,
)

LOGGER = logging.getLogger(__name__)


class TaskServiceError(Exception):
    """Domain-level task queue error."""


class TaskService:
    # TODO: Add Redis-backed queue/cache path for high-throughput deployments.
    # TODO: Add rate limiting and dead-letter replay UI endpoint support.
    # TODO: Add OpenTelemetry tracing for task claims and handler execution spans.

    def __init__(
        self,
        session: Session,
        *,
        repository: TaskRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or TaskRepository(session)
        self.settings = get_settings()

    def enqueue_research(self, payload: ResearchAnalyzeTaskSubmitRequest) -> TaskAcceptedResponse:
        task_payload = payload.request.model_dump(mode="json")
        return self._enqueue(
            task_type=TaskType.RESEARCH_ANALYZE,
            payload_json=task_payload,
            idempotency_key=payload.idempotency_key,
            priority=payload.priority,
            max_attempts=payload.max_attempts,
            available_in_seconds=payload.available_in_seconds,
        )

    def enqueue_content(self, payload: ContentGenerateTaskSubmitRequest) -> TaskAcceptedResponse:
        task_payload = payload.request.model_dump(mode="json")
        return self._enqueue(
            task_type=TaskType.CONTENT_GENERATE,
            payload_json=task_payload,
            idempotency_key=payload.idempotency_key,
            priority=payload.priority,
            max_attempts=payload.max_attempts,
            available_in_seconds=payload.available_in_seconds,
        )

    def enqueue_delivery(self, payload: DeliveryDispatchTaskSubmitRequest) -> TaskAcceptedResponse:
        task_payload = {"delivery_job_id": payload.delivery_job_id}
        return self._enqueue(
            task_type=TaskType.DELIVERY_DISPATCH,
            payload_json=task_payload,
            idempotency_key=payload.idempotency_key,
            priority=payload.priority,
            max_attempts=payload.max_attempts,
            available_in_seconds=payload.available_in_seconds,
        )

    def get_task(self, task_id: int) -> TaskJobView | None:
        row = self.repository.get_task(task_id)
        return to_task_view(row) if row is not None else None

    def retry_task(self, task_id: int, *, available_in_seconds: int = 0) -> TaskRetryResponse:
        row = self.repository.retry_task(task_id=task_id, available_in_seconds=available_in_seconds)
        if row is None:
            raise TaskServiceError(f"Task {task_id} not found.")
        if row.status not in {
            TaskJobStatus.QUEUED,
            TaskJobStatus.FAILED,
            TaskJobStatus.DEAD_LETTER,
            TaskJobStatus.CANCELLED,
        }:
            raise TaskServiceError(
                f"Task {task_id} cannot be retried from status={row.status.value}."
            )
        return TaskRetryResponse(task_id=row.id, status=row.status, available_at=row.available_at)

    def cancel_task(self, task_id: int) -> TaskCancelResponse:
        row = self.repository.cancel_task(task_id=task_id)
        if row is None:
            raise TaskServiceError(f"Task {task_id} not found.")
        return TaskCancelResponse(task_id=row.id, status=row.status)

    def process_next(self, *, worker_id: str) -> TaskJobView | None:
        claimed = self.repository.claim_next(worker_id=worker_id)
        if claimed is None:
            return None
        task_job, attempt = claimed
        handlers = TaskHandlers(self.session)
        task_type_text = task_job.task_type.value
        updated = task_job

        with bind_log_context(task_id=str(task_job.id), worker_id=worker_id):
            LOGGER.info(
                "task execution started task_id=%s task_type=%s attempt=%s",
                task_job.id,
                task_job.task_type.value,
                attempt.attempt_number,
            )
            with track_task_execution(task_type_text) as timing_state:
                try:
                    execution = handlers.execute(
                        task_type=task_job.task_type,
                        payload_json=task_job.payload_json,
                    )
                    updated = self.repository.mark_succeeded(
                        task_job=task_job,
                        attempt=attempt,
                        result_json=execution.result_json,
                        source_run_id=execution.source_run_id,
                    )
                except NonRetryableTaskError as exc:
                    self.session.rollback()
                    updated = self.repository.mark_failed(
                        task_job=task_job,
                        attempt=attempt,
                        error_message=str(exc),
                        retryable=False,
                        retry_delay_seconds=0,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.session.rollback()
                    retry_delay = compute_retry_delay_seconds(
                        attempt_count=max(task_job.attempt_count, 1),
                        base_delay_seconds=self.settings.task_retry_backoff_seconds,
                    )
                    updated = self.repository.mark_failed(
                        task_job=task_job,
                        attempt=attempt,
                        error_message=str(exc),
                        retryable=True,
                        retry_delay_seconds=retry_delay,
                    )

            duration = timing_state["duration_seconds"]
            if updated.status == TaskJobStatus.SUCCEEDED:
                mark_task_succeeded(task_type=task_type_text, duration_seconds=duration)
                LOGGER.info(
                    "task execution succeeded task_id=%s task_type=%s",
                    updated.id,
                    task_type_text,
                )
            elif updated.status in {TaskJobStatus.QUEUED, TaskJobStatus.DEAD_LETTER}:
                mark_task_failed(
                    task_type=task_type_text,
                    status=updated.status.value,
                    duration_seconds=duration,
                )
                LOGGER.warning(
                    "task execution failed task_id=%s task_type=%s status=%s",
                    updated.id,
                    task_type_text,
                    updated.status.value,
                )
            else:
                mark_task_failed(
                    task_type=task_type_text,
                    status="failed",
                    duration_seconds=duration,
                )
                LOGGER.warning(
                    "task execution failed task_id=%s task_type=%s status=%s",
                    updated.id,
                    task_type_text,
                    updated.status.value,
                )

        return to_task_view(updated)

    def _enqueue(
        self,
        *,
        task_type: TaskType,
        payload_json: dict[str, Any],
        idempotency_key: str | None,
        priority: int,
        max_attempts: int,
        available_in_seconds: int,
    ) -> TaskAcceptedResponse:
        row, created = self.repository.enqueue_task(
            task_type=task_type,
            payload_json=payload_json,
            idempotency_key=idempotency_key,
            priority=priority,
            max_attempts=max_attempts,
            available_in_seconds=available_in_seconds,
        )
        if created:
            mark_task_enqueued(task_type=task_type.value)
        return TaskAcceptedResponse(
            task_id=row.id,
            task_type=row.task_type,
            status=row.status,
            idempotency_key=row.idempotency_key,
            accepted_at=row.created_at,
            deduplicated=not created,
        )
