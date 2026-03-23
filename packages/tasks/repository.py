from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Select, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from packages.db.models import TaskAttempt, TaskJob
from packages.tasks.enums import TaskAttemptStatus, TaskJobStatus, TaskType
from packages.tasks.schemas import TaskAttemptView, TaskJobView

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def enqueue_task(
        self,
        *,
        task_type: TaskType,
        payload_json: dict[str, Any],
        idempotency_key: str | None,
        priority: int,
        max_attempts: int,
        available_in_seconds: int,
    ) -> tuple[TaskJob, bool]:
        if idempotency_key:
            existing = self.get_by_idempotency(task_type=task_type, idempotency_key=idempotency_key)
            if existing is not None:
                return existing, False

        available_at = datetime.now(UTC) + timedelta(seconds=available_in_seconds)
        row = TaskJob(
            task_type=task_type,
            status=TaskJobStatus.QUEUED,
            priority=priority,
            idempotency_key=idempotency_key,
            payload_json=payload_json,
            max_attempts=max_attempts,
            available_at=available_at,
        )
        self.session.add(row)

        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            if not idempotency_key:
                raise
            existing = self.get_by_idempotency(task_type=task_type, idempotency_key=idempotency_key)
            if existing is None:
                raise
            return existing, False

        self.session.refresh(row)
        return row, True

    def get_by_idempotency(self, *, task_type: TaskType, idempotency_key: str) -> TaskJob | None:
        return self.session.scalar(
            self._task_with_attempts_stmt().where(
                TaskJob.task_type == task_type,
                TaskJob.idempotency_key == idempotency_key,
            )
        )

    def get_task(self, task_id: int) -> TaskJob | None:
        return self.session.scalar(self._task_with_attempts_stmt().where(TaskJob.id == task_id))

    def claim_next(self, *, worker_id: str) -> tuple[TaskJob, TaskAttempt] | None:
        now = datetime.now(UTC)
        dialect = (
            self.session.bind.dialect.name
            if self.session.bind and self.session.bind.dialect
            else "unknown"
        )
        if dialect == "postgresql":
            return self._claim_next_postgres(worker_id=worker_id, now=now)
        return self._claim_next_fallback(worker_id=worker_id, now=now)

    def mark_succeeded(
        self,
        *,
        task_job: TaskJob,
        attempt: TaskAttempt,
        result_json: dict[str, Any],
        source_run_id: int | None,
    ) -> TaskJob:
        now = datetime.now(UTC)
        task_job.status = TaskJobStatus.SUCCEEDED
        task_job.result_json = result_json
        task_job.error_message = None
        task_job.locked_at = None
        task_job.locked_by = None
        if source_run_id is not None:
            task_job.source_run_id = source_run_id
        attempt.status = TaskAttemptStatus.SUCCEEDED
        attempt.finished_at = now
        attempt.error_message = None
        self.session.add(task_job)
        self.session.add(attempt)
        self.session.commit()
        return self.get_task(task_job.id)

    def mark_failed(
        self,
        *,
        task_job: TaskJob,
        attempt: TaskAttempt,
        error_message: str,
        retryable: bool,
        retry_delay_seconds: int,
    ) -> TaskJob:
        now = datetime.now(UTC)
        can_retry = retryable and task_job.attempt_count < task_job.max_attempts

        if can_retry:
            task_job.status = TaskJobStatus.QUEUED
            task_job.available_at = now + timedelta(seconds=max(retry_delay_seconds, 0))
            attempt.status = TaskAttemptStatus.RETRY_SCHEDULED
        else:
            task_job.status = TaskJobStatus.DEAD_LETTER if retryable else TaskJobStatus.FAILED
            task_job.available_at = now
            attempt.status = TaskAttemptStatus.FAILED

        task_job.error_message = error_message[:4000]
        task_job.locked_at = None
        task_job.locked_by = None
        attempt.finished_at = now
        attempt.error_message = error_message[:4000]
        self.session.add(task_job)
        self.session.add(attempt)
        self.session.commit()
        return self.get_task(task_job.id)

    def retry_task(self, *, task_id: int, available_in_seconds: int = 0) -> TaskJob | None:
        task_job = self.get_task(task_id)
        if task_job is None:
            return None
        if task_job.status not in {
            TaskJobStatus.FAILED,
            TaskJobStatus.DEAD_LETTER,
            TaskJobStatus.CANCELLED,
        }:
            return task_job
        task_job.status = TaskJobStatus.QUEUED
        task_job.error_message = None
        task_job.locked_at = None
        task_job.locked_by = None
        task_job.available_at = datetime.now(UTC) + timedelta(seconds=max(available_in_seconds, 0))
        self.session.add(task_job)
        self.session.commit()
        return self.get_task(task_id)

    def cancel_task(self, *, task_id: int) -> TaskJob | None:
        task_job = self.get_task(task_id)
        if task_job is None:
            return None
        if task_job.status in {TaskJobStatus.SUCCEEDED, TaskJobStatus.CANCELLED}:
            return task_job
        task_job.status = TaskJobStatus.CANCELLED
        task_job.error_message = task_job.error_message or "Cancelled by user request."
        task_job.locked_at = None
        task_job.locked_by = None
        self.session.add(task_job)
        self.session.commit()
        return self.get_task(task_id)

    def _task_with_attempts_stmt(self) -> Select[tuple[TaskJob]]:
        return select(TaskJob).options(selectinload(TaskJob.attempts))

    def _claim_next_postgres(
        self, *, worker_id: str, now: datetime
    ) -> tuple[TaskJob, TaskAttempt] | None:
        stmt = (
            select(TaskJob)
            .where(
                TaskJob.status == TaskJobStatus.QUEUED,
                TaskJob.available_at <= now,
            )
            .order_by(TaskJob.priority.asc(), TaskJob.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        row = self.session.scalar(stmt)
        if row is None:
            self.session.rollback()
            return None

        row.status = TaskJobStatus.RUNNING
        row.locked_at = now
        row.locked_by = worker_id
        row.attempt_count += 1
        attempt = TaskAttempt(
            task_job_id=row.id,
            attempt_number=row.attempt_count,
            worker_id=worker_id,
            status=TaskAttemptStatus.RUNNING,
            started_at=now,
            metadata_json={"claimed_at": now.isoformat()},
        )
        self.session.add(row)
        self.session.add(attempt)
        self.session.commit()
        self.session.refresh(attempt)
        row = self.get_task(row.id)
        return row, attempt

    def _claim_next_fallback(
        self, *, worker_id: str, now: datetime
    ) -> tuple[TaskJob, TaskAttempt] | None:
        candidate = self.session.scalar(
            select(TaskJob.id)
            .where(
                TaskJob.status == TaskJobStatus.QUEUED,
                TaskJob.available_at <= now,
            )
            .order_by(TaskJob.priority.asc(), TaskJob.id.asc())
            .limit(1)
        )
        if candidate is None:
            return None

        update_result = self.session.execute(
            update(TaskJob)
            .where(
                TaskJob.id == candidate,
                TaskJob.status == TaskJobStatus.QUEUED,
            )
            .values(
                status=TaskJobStatus.RUNNING,
                locked_at=now,
                locked_by=worker_id,
                attempt_count=TaskJob.attempt_count + 1,
            )
        )
        if update_result.rowcount == 0:
            self.session.rollback()
            return None

        row = self.session.get(TaskJob, candidate)
        if row is None:
            self.session.rollback()
            return None

        attempt = TaskAttempt(
            task_job_id=row.id,
            attempt_number=row.attempt_count,
            worker_id=worker_id,
            status=TaskAttemptStatus.RUNNING,
            started_at=now,
            metadata_json={"claimed_at": now.isoformat(), "mode": "fallback"},
        )
        self.session.add(attempt)
        self.session.commit()
        self.session.refresh(attempt)
        row = self.get_task(row.id)
        return row, attempt


def to_attempt_view(row: TaskAttempt) -> TaskAttemptView:
    return TaskAttemptView(
        id=row.id,
        task_job_id=row.task_job_id,
        attempt_number=row.attempt_number,
        worker_id=row.worker_id,
        status=row.status.value,
        started_at=row.started_at,
        finished_at=row.finished_at,
        error_message=row.error_message,
        metadata_json=row.metadata_json,
    )


def to_task_view(row: TaskJob) -> TaskJobView:
    return TaskJobView(
        id=row.id,
        task_type=row.task_type,
        status=row.status,
        priority=row.priority,
        idempotency_key=row.idempotency_key,
        payload_json=row.payload_json,
        result_json=row.result_json,
        error_message=row.error_message,
        attempt_count=row.attempt_count,
        max_attempts=row.max_attempts,
        available_at=row.available_at,
        locked_at=row.locked_at,
        locked_by=row.locked_by,
        source_run_id=row.source_run_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        attempts=[to_attempt_view(item) for item in sorted(row.attempts, key=lambda x: x.id)],
    )
