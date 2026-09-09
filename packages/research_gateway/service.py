"""ResearchRunService — the single domain entry point for creating/observing runs.

G1.1: external callers see a Research Run (not a Task).
G1.2: `submit` is the idempotent submission entry — canonical request hash +
      DB UNIQUE(scope, key) guarantee exactly-once Run creation under retries.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.db.models import Run, RunEvent
from packages.db.models.enums import RunStatus
from packages.research_gateway.admission import AdmissionController, AdmissionGuard, AdmissionPolicy
from packages.research_gateway.errors import (
    IdempotencyKeyReusedError,
    InvalidResearchRequestError,
    QueueCapacityExceededError,
    RunFailedError,
    RunNotCompletedError,
    RunNotFoundError,
)
from packages.research_gateway.events import RunEventRecorder, RunEventType
from packages.research_gateway.schemas import (
    ResearchRunAcceptedResponse,
    ResearchRunCancelResponse,
    ResearchRunCreateRequest,
    ResearchRunEventsResponse,
    ResearchRunResultResponse,
    ResearchRunView,
    RunEventView,
)
from packages.tasks.schemas import ResearchAnalyzeTaskSubmitRequest
from packages.tasks.service import (
    IdempotencyConflictError,
    TaskService,
    TaskServiceError,
)

_DEFAULT_SCOPE = "default"


def _canonical_request_hash(request: ResearchAnalyzeRequest) -> str:
    """Stable business-identity hash of the request (excludes volatile fields)."""
    canonical = {
        "query": request.query,
        "research_strategy": request.research_strategy,
        "mode": request.mode.value if request.mode else None,
        "provider": request.provider.value if request.provider else None,
        "model": request.model,
    }
    blob = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _links(run_id: int) -> dict[str, str]:
    return {
        "self": f"/v1/research/runs/{run_id}",
        "result": f"/v1/research/runs/{run_id}/result",
    }


class ResearchRunService:
    def __init__(
        self,
        session: Session,
        *,
        admission_policy: AdmissionPolicy | None = None,
        admission_guard: AdmissionGuard | None = None,
    ) -> None:
        from packages.core.config import get_settings

        self.session = session
        self.task_service = TaskService(session)
        self.events = RunEventRecorder()
        policy = admission_policy or AdmissionPolicy(
            max_queued_runs=get_settings().admission_max_queued_runs
        )
        self.admission_controller = AdmissionController(
            session, policy=policy, guard=admission_guard
        )

    def create_run(self, payload: ResearchRunCreateRequest) -> ResearchRunAcceptedResponse:
        """Backward-compatible G1.1 entry (no idempotency)."""
        return self.submit(payload.request)

    def submit(
        self,
        request: ResearchAnalyzeRequest,
        *,
        idempotency_key: str | None = None,
        idempotency_scope: str = _DEFAULT_SCOPE,
    ) -> ResearchRunAcceptedResponse:
        """Idempotent, admission-controlled Run submission (G1.2 + G1.3.1).

        Order: Idempotency (before admission) -> Admission (global QUEUED cap) ->
        Run + Task creation — all in ONE transaction owned by this method.

        Same key + same request -> replay (no queue capacity consumed).
        Same key + different request -> 409 IDEMPOTENCY_KEY_REUSED (before admission).
        Queue full -> 503 RESEARCH_QUEUE_CAPACITY_EXCEEDED (no Run/Task created).
        """
        request_hash = _canonical_request_hash(request) if idempotency_key else None
        _created_snapshot: dict[str, Any] | None = None
        try:
            with self.session.begin():
                # 1. Idempotency resolution (fast path; replay does not enter admission).
                replay = self._resolve_idempotency(
                    idempotency_scope, idempotency_key, request_hash
                )
                if replay is not None:
                    return self._accepted_response(replay, replayed=True)

                # 2. Admission critical section (transaction-scoped guard).
                with self.admission_controller.guard:
                    # 2a. Re-check idempotency inside the critical section
                    #     (concurrent duplicate protection after the guard serializes).
                    replay = self._resolve_idempotency(
                        idempotency_scope, idempotency_key, request_hash
                    )
                    if replay is not None:
                        return self._accepted_response(replay, replayed=True)

                    # 2b. Global QUEUED-capacity decision.
                    decision = self.admission_controller.evaluate()
                    if not decision.accepted:
                        raise QueueCapacityExceededError(
                            "Research queue capacity exceeded.",
                            {
                                "queued_capacity": (
                                    self.admission_controller.current_policy.max_queued_runs
                                ),
                                "retry_after_seconds": decision.retry_after_seconds,
                            },
                        )

                    # 2c. Create Run + Task in the same transaction (no separate commit).
                    accepted = self.task_service.create_research_run_and_task(
                        ResearchAnalyzeTaskSubmitRequest(request=request),
                        run_idempotency_key=idempotency_key,
                        run_idempotency_scope=idempotency_scope,
                        run_idempotency_request_hash=request_hash,
                    )
                    run = self.session.get(Run, accepted.run_id)
                    if run is None:
                        raise RunNotFoundError(str(accepted.run_id))
                    # Snapshot fields before commit (the ORM instance expires after
                    # commit; touching it would open a new transaction).
                    _created_snapshot = {
                        "run_id": run.id,
                        "status": run.status.value,
                        "created_at": run.created_at,
                        "has_idem_key": run.idempotency_key is not None,
                    }
        except IdempotencyConflictError as exc:
            raise IdempotencyKeyReusedError(
                str(exc), {"idempotency_key": idempotency_key}
            ) from exc
        except TaskServiceError as exc:
            raise InvalidResearchRequestError(str(exc)) from exc

        # After the transaction commits: record RUN_CREATED (fail-open; a timeline
        # failure must not fail a successfully created Run).
        if _created_snapshot is not None:
            self.events.record(
                run_id=_created_snapshot["run_id"],
                event_type=RunEventType.RUN_CREATED,
                stage="run",
                status="created",
                message="Research run created and queued.",
            )
            return self._accepted_response_from_snapshot(_created_snapshot, replayed=False)
        raise RunNotFoundError("Run was not created.")

    def _resolve_idempotency(
        self, scope: str, key: str | None, request_hash: str | None
    ) -> Run | None:
        if not key:
            return None
        run = self.session.scalar(
            select(Run)
            .where(Run.idempotency_scope == scope, Run.idempotency_key == key)
            .order_by(Run.id.asc())
            .limit(1)
        )
        if run is None:
            return None
        if run.idempotency_request_hash != request_hash:
            raise IdempotencyConflictError(
                f"Idempotency key reused with a different request (run={run.id})."
            )
        return run

    def _accepted_response(self, run: Run, *, replayed: bool) -> ResearchRunAcceptedResponse:
        return ResearchRunAcceptedResponse(
            run_id=run.id,
            status=run.status.value,
            created_at=run.created_at,
            links=_links(run.id),
            idempotency={"replayed": replayed}
            if run.idempotency_key is not None
            else None,
        )

    def _accepted_response_from_snapshot(
        self, snap: dict[str, Any], *, replayed: bool
    ) -> ResearchRunAcceptedResponse:
        return ResearchRunAcceptedResponse(
            run_id=snap["run_id"],
            status=snap["status"],
            created_at=snap["created_at"],
            links=_links(snap["run_id"]),
            idempotency={"replayed": replayed} if snap["has_idem_key"] else None,
        )

    def get_run(self, run_id: int) -> ResearchRunView:
        run = self.session.get(Run, run_id)
        if run is None:
            raise RunNotFoundError(f"Research run {run_id} was not found.", {"run_id": run_id})
        error = None
        if run.status == RunStatus.FAILED and isinstance(run.output_json, dict):
            err = run.output_json.get("error")
            if err:
                error = {"type": "workflow_error", "message": str(err)[:500]}
        return ResearchRunView(
            run_id=run.id,
            run_type=run.run_type.value,
            status=run.status.value,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            request=dict(run.input_json or {}),
            error=error,
            links=_links(run.id),
        )

    def get_result(self, run_id: int) -> ResearchRunResultResponse:
        run = self.session.get(Run, run_id)
        if run is None:
            raise RunNotFoundError(f"Research run {run_id} was not found.", {"run_id": run_id})
        if run.status == RunStatus.SUCCEEDED:
            return ResearchRunResultResponse(
                run_id=run.id,
                status="succeeded",
                result=dict(run.output_json or {}),
            )
        if run.status == RunStatus.FAILED:
            err = (
                run.output_json.get("error") if isinstance(run.output_json, dict) else None
            )
            raise RunFailedError(
                str(err or "Research run failed."),
                {"run_id": run_id, "status": run.status.value},
            )
        raise RunNotCompletedError(
            "Research run has not completed.",
            {"run_id": run_id, "status": run.status.value},
        )

    def cancel_run(self, run_id: int) -> ResearchRunCancelResponse:
        """G1.5 cancel. QUEUED -> immediately CANCELLED; RUNNING -> cooperative
        cancel_requested (worker stops at a safe boundary). Terminal states are
        idempotent for CANCELLED and 409 RUN_ALREADY_TERMINAL otherwise."""
        from packages.research_gateway.errors import RunAlreadyTerminalError

        try:
            result = self.task_service.cancel_research_run(run_id)
        except RunAlreadyTerminalError:
            raise
        except TaskServiceError as exc:
            raise RunNotFoundError(str(exc), {"run_id": run_id}) from exc
        return ResearchRunCancelResponse(
            run_id=run_id,
            status=result["status"],
            cancellation={"requested": True, "completed": result["completed"]},
        )

    def get_run_events(
        self, run_id: int, *, after_sequence: int | None = None
    ) -> ResearchRunEventsResponse:
        run = self.session.get(Run, run_id)
        if run is None:
            raise RunNotFoundError(f"Research run {run_id} was not found.", {"run_id": run_id})
        stmt = (
            select(RunEvent)
            .where(RunEvent.run_id == run_id)
            .order_by(RunEvent.sequence.asc())
        )
        if after_sequence is not None:
            stmt = stmt.where(RunEvent.sequence > after_sequence)
        events = self.session.scalars(stmt).all()
        return ResearchRunEventsResponse(
            run_id=run_id,
            events=[
                RunEventView(
                    sequence=e.sequence,
                    event_type=e.event_type,
                    stage=e.stage,
                    status=e.status,
                    message=e.message,
                    payload=dict(e.payload_json or {}),
                    created_at=e.created_at,
                )
                for e in events
            ],
        )
