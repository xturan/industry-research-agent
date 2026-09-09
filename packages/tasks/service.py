from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.core.config import get_settings
from packages.core.logging import bind_log_context
from packages.core.run_log import CompactRunLogger
from packages.db.models import Run
from packages.db.models.enums import RunStatus, RunType
from packages.research_gateway.errors import ResearchRunCancelled, RunAlreadyTerminalError
from packages.research_gateway.events import RunEventRecorder, RunEventType
from packages.tasks.claim import compute_retry_delay_seconds
from packages.tasks.enums import TaskJobStatus, TaskType

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc
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


class IdempotencyConflictError(TaskServiceError):
    """The idempotency key was already used with a different request (G1.2)."""


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
        self.events = RunEventRecorder()

    # ── Run lifecycle helpers (G0.1: Run is created at enqueue, transitions in worker) ──

    def _create_research_run(
        self,
        request: ResearchAnalyzeRequest,
        *,
        idempotency_scope: str | None = None,
        idempotency_key: str | None = None,
        idempotency_request_hash: str | None = None,
    ) -> Run:
        run = Run(
            run_type=RunType.RESEARCH,
            status=RunStatus.QUEUED,
            input_json={
                "pipeline": "deep_research_graph_v2",
                "query": request.query,
                "research_strategy": request.research_strategy,
                "mode": request.mode.value if request.mode else None,
            },
            idempotency_scope=idempotency_scope,
            idempotency_key=idempotency_key,
            idempotency_request_hash=idempotency_request_hash,
        )
        self.session.add(run)
        self.session.flush()  # materialize run.id
        return run

    def _cas_update_run(
        self,
        run_id: int | None,
        *,
        from_statuses: list[RunStatus],
        values: dict[str, Any],
    ) -> int:
        """Conditional UPDATE (CAS): only transition if the run is in from_statuses.
        Returns rowcount so callers can detect a lost race (terminal wins)."""
        if run_id is None:
            return 0
        result = self.session.execute(
            update(Run)
            .where(Run.id == run_id, Run.status.in_(from_statuses))
            .values(**values)
        )
        return result.rowcount

    def _mark_run_running(self, run_id: int | None) -> None:
        self._cas_update_run(
            run_id,
            from_statuses=[RunStatus.QUEUED],
            values={"status": RunStatus.RUNNING, "started_at": datetime.now(UTC)},
        )
        # Commit so a worker crash mid-run leaves a durable RUNNING state
        # (recoverable), and the transition is externally observable.
        self.session.commit()

    def _mark_run_succeeded(self, run_id: int | None, output_json: dict[str, Any]) -> None:
        self._cas_update_run(
            run_id,
            from_statuses=[RunStatus.QUEUED, RunStatus.RUNNING],
            values={
                "status": RunStatus.SUCCEEDED,
                "output_json": output_json,
                "finished_at": datetime.now(UTC),
            },
        )
        self.session.commit()

    def _mark_run_failed(self, run_id: int | None, error: str) -> None:
        self._cas_update_run(
            run_id,
            from_statuses=[RunStatus.QUEUED, RunStatus.RUNNING],
            values={
                "status": RunStatus.FAILED,
                "output_json": {"error": str(error)[:2000]},
                "finished_at": datetime.now(UTC),
            },
        )
        self.session.commit()

    def _mark_run_cancelled(self, run_id: int | None) -> int:
        rows = self._cas_update_run(
            run_id,
            from_statuses=[RunStatus.QUEUED, RunStatus.RUNNING],
            values={
                "status": RunStatus.CANCELLED,
                "finished_at": datetime.now(UTC),
            },
        )
        self.session.commit()
        return rows

    def enqueue_research(self, payload: ResearchAnalyzeTaskSubmitRequest) -> TaskAcceptedResponse:
        """Backward-compatible thin wrapper (no run-level idempotency)."""
        accepted, _replayed = self.submit_research(payload)
        return accepted

    def submit_research(
        self,
        payload: ResearchAnalyzeTaskSubmitRequest,
        *,
        run_idempotency_key: str | None = None,
        run_idempotency_scope: str = "default",
        run_idempotency_request_hash: str | None = None,
    ) -> tuple[TaskAcceptedResponse, bool]:
        """Atomically create a Research Run + Task (G0.1) with G1.2 idempotency.

        Concurrency safety comes from the DB UNIQUE(idempotency_scope,
        idempotency_key) constraint, NOT from app-level SELECT-then-INSERT. On a
        concurrent unique violation we roll back, re-query, and replay (same
        request hash) or raise IdempotencyConflictError (different hash).
        Returns (accepted, replayed).
        """
        # Task-level idempotency (legacy /tasks path): deduplicate on the task's
        # own idempotency key before any new Run is created.
        if payload.idempotency_key:
            existing_task = self.repository.get_by_idempotency(
                task_type=TaskType.RESEARCH_ANALYZE,
                idempotency_key=payload.idempotency_key,
            )
            if existing_task is not None:
                response = TaskAcceptedResponse(
                    task_id=existing_task.id,
                    task_type=existing_task.task_type,
                    status=existing_task.status,
                    idempotency_key=existing_task.idempotency_key,
                    accepted_at=existing_task.created_at,
                    deduplicated=True,
                    run_id=existing_task.source_run_id,
                )
                return response, True

        # Fast-path run-level lookup (optimization only; the unique constraint is
        # the real guard).
        if run_idempotency_key:
            existing_run = self._find_run_by_idempotency(
                run_idempotency_scope, run_idempotency_key
            )
            if existing_run is not None:
                if existing_run.idempotency_request_hash != run_idempotency_request_hash:
                    raise IdempotencyConflictError(
                        f"Idempotency key reused with a different request "
                        f"(run={existing_run.id})."
                    )
                return self._replay_response(existing_run), True

        task_payload = payload.request.model_dump(mode="json")
        try:
            run = self._create_research_run(
                payload.request,
                idempotency_scope=run_idempotency_scope if run_idempotency_key else None,
                idempotency_key=run_idempotency_key,
                idempotency_request_hash=(
                    run_idempotency_request_hash if run_idempotency_key else None
                ),
            )
            response = self._enqueue(
                task_type=TaskType.RESEARCH_ANALYZE,
                payload_json=task_payload,
                idempotency_key=payload.idempotency_key,
                priority=payload.priority,
                max_attempts=payload.max_attempts,
                available_in_seconds=payload.available_in_seconds,
                source_run_id=run.id,
            )
        except IntegrityError:
            # Concurrent duplicate (unique constraint): re-query, decide replay/conflict.
            self.session.rollback()
            if not run_idempotency_key:
                raise
            existing_run = self._find_run_by_idempotency(
                run_idempotency_scope, run_idempotency_key
            )
            if existing_run is not None:
                if existing_run.idempotency_request_hash == run_idempotency_request_hash:
                    return self._replay_response(existing_run), True
                raise IdempotencyConflictError(
                    f"Idempotency key reused with a different request "
                    f"(run={existing_run.id})."
                ) from None
            raise
        except Exception:
            self.session.rollback()
            fresh = self.session.get(Run, run.id)
            if fresh is not None and fresh.status == RunStatus.QUEUED:
                fresh.status = RunStatus.FAILED
                fresh.output_json = {"error": "TASK_ENQUEUE_FAILED"}
                fresh.finished_at = datetime.now(UTC)
                self.session.commit()
            raise
        response.run_id = run.id
        return response, False

    def _find_run_by_idempotency(self, scope: str, key: str) -> Run | None:
        return self.session.scalar(
            select(Run)
            .where(Run.idempotency_scope == scope, Run.idempotency_key == key)
            .order_by(Run.id.asc())
            .limit(1)
        )

    def _replay_response(self, run: Run) -> TaskAcceptedResponse:
        task = self.repository.get_task_by_run_id(run.id)
        return TaskAcceptedResponse(
            task_id=task.id if task is not None else 0,
            task_type=TaskType.RESEARCH_ANALYZE,
            status=run.status.value if task is None else task.status.value,
            idempotency_key=None,
            accepted_at=run.created_at,
            deduplicated=True,
            run_id=run.id,
        )

    def create_research_run_and_task(
        self,
        payload: ResearchAnalyzeTaskSubmitRequest,
        *,
        run_idempotency_key: str | None = None,
        run_idempotency_scope: str = "default",
        run_idempotency_request_hash: str | None = None,
    ) -> TaskAcceptedResponse:
        """Create Run + Task atomically WITHOUT committing (G1.3.1).

        The caller (ResearchRunService.submit) owns the transaction: admission +
        idempotency re-check + Run/Task creation commit in ONE transaction.
        """
        run = self._create_research_run(
            payload.request,
            idempotency_scope=run_idempotency_scope if run_idempotency_key else None,
            idempotency_key=run_idempotency_key,
            idempotency_request_hash=(
                run_idempotency_request_hash if run_idempotency_key else None
            ),
        )
        task_payload = payload.request.model_dump(mode="json")
        task = self.repository.enqueue_task_no_commit(
            task_type=TaskType.RESEARCH_ANALYZE,
            payload_json=task_payload,
            idempotency_key=payload.idempotency_key,
            priority=payload.priority,
            max_attempts=payload.max_attempts,
            available_in_seconds=payload.available_in_seconds,
            source_run_id=run.id,
        )
        return TaskAcceptedResponse(
            task_id=task.id,
            task_type=task.task_type,
            status=task.status,
            idempotency_key=task.idempotency_key,
            accepted_at=task.created_at,
            deduplicated=False,
            run_id=run.id,
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

    def cancel_research_run(self, run_id: int) -> dict[str, Any]:
        """Domain-level cancel of a research Run (G1.5, cooperative).

        Returns {"status", "completed", "requested_at"}:
        - QUEUED: conditional-update Run QUEUED->CANCELLED + cancel the queued Task
          (same transaction); completed=True.
        - RUNNING: only set Run.cancel_requested_at (worker observes and stops at a
          safe boundary); completed=False.
        - CANCELLED: idempotent -> completed=True (already cancelled).
        - SUCCEEDED/FAILED: raises RunAlreadyTerminalError (terminal wins).
        All state changes are conditional (CAS) so a concurrent worker terminal
        transition wins over a late cancel request.
        """
        run = self.session.get(Run, run_id)
        if run is None:
            raise TaskServiceError(f"Run {run_id} not found.")
        if run.status in {RunStatus.SUCCEEDED, RunStatus.FAILED}:
            raise RunAlreadyTerminalError(
                f"Run {run_id} already reached a terminal state {run.status.value}.",
                {"run_id": run_id, "status": run.status.value},
            )
        if run.status == RunStatus.CANCELLED:
            return {"status": "cancelled", "completed": True, "requested_at": None}

        if run.status == RunStatus.RUNNING:
            rows = self._cas_update_run(
                run_id,
                from_statuses=[RunStatus.RUNNING],
                values={"cancel_requested_at": datetime.now(UTC)},
            )
            self.session.commit()
            if rows == 0:
                # lost the race with a concurrent terminal transition.
                fresh = self.session.get(Run, run_id)
                return {
                    "status": fresh.status.value if fresh else "unknown",
                    "completed": False,
                    "requested_at": None,
                }
            self.events.record(
                run_id=run_id,
                event_type=RunEventType.RUN_CANCEL_REQUESTED,
                stage="run",
                status="cancel_requested",
                message="Cancellation requested; worker will stop at a safe boundary.",
            )
            return {"status": "running", "completed": False, "requested_at": datetime.now(UTC)}

        # QUEUED: cancel Run + Task atomically (conditional update on the Run).
        self.events.record(
            run_id=run_id,
            event_type=RunEventType.RUN_CANCEL_REQUESTED,
            stage="run",
            status="cancel_requested",
            message="Cancellation requested for queued run.",
        )
        rows = self._mark_run_cancelled(run_id)
        if rows == 0:
            fresh = self.session.get(Run, run_id)
            return {
                "status": fresh.status.value if fresh else "unknown",
                "completed": False,
                "requested_at": None,
            }
        task = self.repository.get_task_by_run_id(run_id, statuses={TaskJobStatus.QUEUED})
        if task is not None:
            self.repository.cancel_task(task_id=task.id)
        self.events.record(
            run_id=run_id,
            event_type=RunEventType.RUN_CANCELLED,
            stage="run",
            status="cancelled",
            message="Run cancelled while queued.",
        )
        return {"status": "cancelled", "completed": True, "requested_at": None}

    def process_next(
        self, *, worker_id: str, handlers: TaskHandlers | None = None
    ) -> TaskJobView | None:
        claimed = self.repository.claim_next(worker_id=worker_id)
        if claimed is None:
            return None
        task_job, attempt = claimed
        handlers = handlers or TaskHandlers(self.session)
        task_type_text = task_job.task_type.value
        updated = task_job
        run_logger = CompactRunLogger(
            task_name=f"task_execute_{task_type_text}",
            run_id=f"task-{task_job.id}",
        )
        run_logger.start(
            input_summary={
                "task_id": task_job.id,
                "task_type": task_type_text,
                "attempt": attempt.attempt_number,
                "payload": task_job.payload_json,
            },
            decision_summary=[
                "execute claimed task with registered handler",
                "mark succeeded or structured failure without changing idempotency key",
                "schedule retry only for retryable failures",
            ],
        )

        with bind_log_context(task_id=str(task_job.id), worker_id=worker_id):
            LOGGER.info(
                "task execution started task_id=%s task_type=%s attempt=%s",
                task_job.id,
                task_job.task_type.value,
                attempt.attempt_number,
            )
            with track_task_execution(task_type_text) as timing_state:
                # G0.1: Run lifecycle transitions driven by the worker.
                self._mark_run_running(task_job.source_run_id)
                self.events.record(
                    run_id=task_job.source_run_id or 0,
                    event_type=RunEventType.WORKER_CLAIMED,
                    stage="execution",
                    status="running",
                    message=f"Task claimed by worker {worker_id}.",
                    payload={"worker_id": worker_id},
                )
                try:
                    execution = handlers.execute(
                        task_type=task_job.task_type,
                        payload_json=task_job.payload_json,
                        source_run_id=task_job.source_run_id,
                    )
                    updated = self.repository.mark_succeeded(
                        task_job=task_job,
                        attempt=attempt,
                        result_json=execution.result_json,
                        source_run_id=execution.source_run_id,
                    )
                    self._mark_run_succeeded(task_job.source_run_id, execution.result_json)
                    self.session.commit()
                    self.events.record(
                        run_id=task_job.source_run_id or 0,
                        event_type=RunEventType.RUN_COMPLETED,
                        stage="run",
                        status="succeeded",
                        message="Research run completed.",
                    )
                except ResearchRunCancelled:
                    # Cooperative cancellation observed by the executor.
                    self.session.rollback()
                    self._mark_run_cancelled(task_job.source_run_id)
                    self.events.record(
                        run_id=task_job.source_run_id or 0,
                        event_type=RunEventType.RUN_CANCELLED,
                        stage="run",
                        status="cancelled",
                        message="Run cancelled cooperatively by the worker.",
                    )
                    updated = self.repository.cancel_claimed_task(
                        task_job=task_job, attempt=attempt
                    )
                except NonRetryableTaskError as exc:
                    self.session.rollback()
                    self._mark_run_failed(task_job.source_run_id, str(exc))
                    self.session.commit()
                    self.events.record(
                        run_id=task_job.source_run_id or 0,
                        event_type=RunEventType.RUN_FAILED,
                        stage="run",
                        status="failed",
                        message=str(exc)[:300],
                    )
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
                    self._mark_run_failed(task_job.source_run_id, str(exc))
                    self.session.commit()
                    self.events.record(
                        run_id=task_job.source_run_id or 0,
                        event_type=RunEventType.RUN_FAILED,
                        stage="run",
                        status="failed",
                        message=str(exc)[:300],
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

        run_logger.finish(
            status=updated.status.value,
            output_summary={
                "task_id": updated.id,
                "task_type": updated.task_type.value,
                "status": updated.status.value,
                "attempt_count": updated.attempt_count,
                "source_run_id": updated.source_run_id,
                "error": updated.error_message,
                "result": updated.result_json,
            },
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
        source_run_id: int | None = None,
    ) -> TaskAcceptedResponse:
        run_logger = CompactRunLogger(task_name=f"task_enqueue_{task_type.value}")
        run_logger.start(
            input_summary={
                "task_type": task_type.value,
                "payload": payload_json,
                "idempotency_key": idempotency_key,
                "priority": priority,
                "max_attempts": max_attempts,
                "available_in_seconds": available_in_seconds,
                "source_run_id": source_run_id,
            },
            decision_summary=[
                "enqueue task through repository",
                "deduplicate by idempotency key when present",
            ],
        )
        row, created = self.repository.enqueue_task(
            task_type=task_type,
            payload_json=payload_json,
            idempotency_key=idempotency_key,
            priority=priority,
            max_attempts=max_attempts,
            available_in_seconds=available_in_seconds,
            source_run_id=source_run_id,
        )
        if created:
            mark_task_enqueued(task_type=task_type.value)
        response = TaskAcceptedResponse(
            task_id=row.id,
            task_type=row.task_type,
            status=row.status,
            idempotency_key=row.idempotency_key,
            accepted_at=row.created_at,
            deduplicated=not created,
        )
        run_logger.finish(status=response.status.value, output_summary=response)
        return response
