"""G1.4 RunEvent Timeline — append-only domain events.

Run.status remains the authoritative current state; RunEvent is the "why we got
here" timeline. Events are best-effort / fail-open: a timeline write failure must
never fail a successful Research Run.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from packages.db.models import RunEvent

LOGGER = logging.getLogger(__name__)


class RunEventType(StrEnum):
    RUN_CREATED = "RUN_CREATED"
    WORKER_CLAIMED = "WORKER_CLAIMED"
    PLANNER_STARTED = "PLANNER_STARTED"
    PLANNER_COMPLETED = "PLANNER_COMPLETED"
    SEARCH_STARTED = "SEARCH_STARTED"
    SEARCH_COMPLETED = "SEARCH_COMPLETED"
    EVIDENCE_BUILT = "EVIDENCE_BUILT"
    CLAIMS_BUILT = "CLAIMS_BUILT"
    EDITOR_STARTED = "EDITOR_STARTED"
    EDITOR_COMPLETED = "EDITOR_COMPLETED"
    RUN_CANCEL_REQUESTED = "RUN_CANCEL_REQUESTED"
    RUN_CANCELLED = "RUN_CANCELLED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"


class RunEventRecorder:
    """Writes append-only RunEvent rows. Always uses an isolated session so a
    timeline failure cannot poison the caller's transaction (fail-open)."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self._session_factory = session_factory

    def _factory(self) -> Callable[[], Session]:
        if self._session_factory is not None:
            return self._session_factory
        from packages.db.session import SessionLocal

        return SessionLocal

    def record(
        self,
        *,
        run_id: int,
        event_type: RunEventType | str,
        stage: str,
        status: str,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int | None:
        """Insert one event; returns its id or None on failure (never raises).

        Sequence allocation takes a per-run row lock (SELECT ... FOR UPDATE on the
        Run row) so concurrent writers for the SAME run cannot collide on the same
        sequence (G1.4 concurrency hardening). Different runs are unaffected.
        """
        try:
            with self._factory()() as session:
                # Per-run lock serializes sequence allocation for this run only
                # (PostgreSQL; SQLite skips the lock — no concurrent writers there).
                if session.get_bind().dialect.name == "postgresql":
                    session.execute(
                        text("SELECT id FROM runs WHERE id = :rid FOR UPDATE"),
                        {"rid": run_id},
                    )
                max_seq = (
                    session.scalar(
                        select(func.max(RunEvent.sequence)).where(
                            RunEvent.run_id == run_id
                        )
                    )
                    or 0
                )
                evt = RunEvent(
                    run_id=run_id,
                    sequence=int(max_seq) + 1,
                    event_type=str(event_type),
                    stage=stage,
                    status=status,
                    message=(str(message)[:500] if message else None),
                    payload_json=payload or {},
                )
                session.add(evt)
                session.commit()
                return evt.id
        except Exception:  # noqa: BLE001 - timeline is best-effort
            LOGGER.warning(
                "RUN_EVENT_PERSIST_FAILED run_id=%s event_type=%s stage=%s",
                run_id,
                event_type,
                stage,
                exc_info=True,
            )
            return None
