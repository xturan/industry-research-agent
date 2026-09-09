"""G1.3.1 Global Queue Admission & Backpressure.

Hard-enforces a global QUEUED-run capacity. The DB (Run.status = QUEUED) is the
source of truth. Production (PostgreSQL) uses a transaction-scoped advisory lock
to serialize the COUNT->INSERT critical section; SQLite tests use an explicit
in-process guard (NOT a production multi-instance guarantee).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from packages.db.models import Run
from packages.db.models.enums import RunStatus

# Fixed advisory lock key for the global research-queue admission critical section.
_ADMISSION_LOCK_KEY = 74747474
# Shared in-process lock so all InProcessAdmissionGuard instances serialize.
_IN_PROCESS_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class AdmissionPolicy:
    max_queued_runs: int = 200  # G1.3.1: global QUEUED capacity only
    retry_after_seconds: int = 30


@dataclass(frozen=True, slots=True)
class AdmissionSnapshot:
    queued_count: int
    running_count: int  # G1.3.1: counted only, NOT enforced (scheduling is G3)
    capacity: int


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    accepted: bool
    retry_after_seconds: int | None = None
    reason: str | None = None


class AdmissionGuard:
    """Context manager that serializes the admission critical section."""

    def __enter__(self) -> AdmissionGuard:
        raise NotImplementedError

    def __exit__(self, *exc: Any) -> bool:
        raise NotImplementedError


class PostgresAdvisoryGuard(AdmissionGuard):
    """Transaction-scoped advisory lock — released at commit/rollback."""

    def __init__(self, session: Session, lock_key: int = _ADMISSION_LOCK_KEY) -> None:
        self.session = session
        self.lock_key = lock_key

    def __enter__(self) -> PostgresAdvisoryGuard:
        self.session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": self.lock_key}
        )
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


class InProcessAdmissionGuard(AdmissionGuard):
    """Test double: serializes within this process only. NOT a multi-instance guarantee."""

    def __init__(self, lock: threading.Lock | None = None) -> None:
        self.lock = lock or _IN_PROCESS_LOCK

    def __enter__(self) -> InProcessAdmissionGuard:
        self.lock.acquire()
        return self

    def __exit__(self, *exc: Any) -> bool:
        self.lock.release()
        return False


def _default_guard(session: Session) -> AdmissionGuard:
    try:
        dialect = session.get_bind().dialect.name
    except Exception:  # noqa: BLE001
        dialect = "sqlite"
    if dialect == "postgresql":
        return PostgresAdvisoryGuard(session)
    return InProcessAdmissionGuard()


class AdmissionController:
    def __init__(
        self,
        session: Session,
        *,
        policy: AdmissionPolicy | None = None,
        guard: AdmissionGuard | None = None,
    ) -> None:
        self.session = session
        self.policy = policy or AdmissionPolicy()
        self.guard = guard or _default_guard(session)

    def snapshot(self) -> AdmissionSnapshot:
        queued = (
            self.session.scalar(
                select(func.count()).select_from(Run).where(Run.status == RunStatus.QUEUED)
            )
            or 0
        )
        running = (
            self.session.scalar(
                select(func.count()).select_from(Run).where(Run.status == RunStatus.RUNNING)
            )
            or 0
        )
        return AdmissionSnapshot(
            queued_count=queued,
            running_count=running,
            capacity=self.policy.max_queued_runs,
        )

    def evaluate(self, snapshot: AdmissionSnapshot | None = None) -> AdmissionDecision:
        snap = snapshot or self.snapshot()
        if snap.queued_count >= snap.capacity:
            return AdmissionDecision(
                accepted=False,
                retry_after_seconds=self.policy.retry_after_seconds,
                reason="RESEARCH_QUEUE_CAPACITY_EXCEEDED",
            )
        return AdmissionDecision(accepted=True, retry_after_seconds=None)

    @property
    def current_policy(self) -> AdmissionPolicy:
        return self.policy
