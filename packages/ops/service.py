from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.db.models import DeliveryJob, EvalRun, Run, TaskAttempt, TaskJob
from packages.db.models.enums import EvalStatus, RunStatus, TaskJobStatus
from packages.delivery.enums import DeliveryJobStatus
from packages.ops.schemas import ReadinessReport, RecentFailureItem, RecentFailuresResponse
from packages.sources.performance import SourcePerformanceService
from packages.sources.schemas import SourcePerformanceSummary

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc


class OpsService:
    # TODO: Add SLO evaluation and OTEL-backed dependency health summary.
    # TODO: Add deployment manifest checks and queue depth alert thresholds.

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()

    def readiness_report(self) -> ReadinessReport:
        db_ok = False
        migration_revision = None
        db_error = None
        try:
            self.session.execute(text("SELECT 1"))
            db_ok = True
            migration_revision = self.session.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar_one_or_none()
        except Exception as exc:  # noqa: BLE001
            db_error = str(exc)

        raw_dir = Path(self.settings.raw_storage_dir)
        export_dir = Path(self.settings.delivery_export_dir)
        directories = {
            str(raw_dir): raw_dir.exists(),
            str(export_dir): export_dir.exists(),
        }

        latest_attempt = self.session.scalar(
            select(TaskAttempt)
            .order_by(TaskAttempt.started_at.desc(), TaskAttempt.id.desc())
            .limit(1)
        )
        worker_hint = None
        if latest_attempt is not None:
            worker_hint = {
                "worker_id": latest_attempt.worker_id,
                "last_seen_at": latest_attempt.started_at.isoformat(),
                "status": latest_attempt.status.value,
            }

        failure_counts = {
            "tasks_failed": self._count_tasks_failed(),
            "runs_failed": self._count_runs_failed(),
            "delivery_failed": self._count_delivery_failed(),
            "evals_failed": self._count_evals_failed(),
        }

        ready = db_ok and all(directories.values())
        checks = {
            "database": {"ok": db_ok, "error": db_error},
            "migration_revision": migration_revision,
            "directories": directories,
            "worker_hint": worker_hint,
            "metrics_endpoint": "/metrics",
        }
        return ReadinessReport(
            status="ready" if ready else "degraded",
            checks=checks,
            failure_counts=failure_counts,
            timestamp=datetime.now(UTC),
        )

    def recent_failures(self, *, limit: int = 30) -> RecentFailuresResponse:
        items: list[RecentFailureItem] = []

        task_rows = self.session.scalars(
            select(TaskJob)
            .where(TaskJob.status.in_([TaskJobStatus.FAILED, TaskJobStatus.DEAD_LETTER]))
            .order_by(TaskJob.created_at.desc(), TaskJob.id.desc())
            .limit(limit)
        ).all()
        for row in task_rows:
            items.append(
                RecentFailureItem(
                    failure_type="task_job",
                    ref_id=row.id,
                    status=row.status.value,
                    message=row.error_message,
                    created_at=row.created_at,
                )
            )

        run_rows = self.session.scalars(
            select(Run)
            .where(Run.status == RunStatus.FAILED)
            .order_by(Run.created_at.desc(), Run.id.desc())
            .limit(limit)
        ).all()
        for row in run_rows:
            items.append(
                RecentFailureItem(
                    failure_type="run",
                    ref_id=row.id,
                    status=row.status.value,
                    message=(
                        (row.output_json or {}).get("error")
                        if isinstance(row.output_json, dict)
                        else None
                    ),
                    created_at=row.created_at,
                )
            )

        delivery_rows = self.session.scalars(
            select(DeliveryJob)
            .where(
                DeliveryJob.status.in_([DeliveryJobStatus.FAILED, DeliveryJobStatus.PARTIAL_FAILED])
            )
            .order_by(DeliveryJob.created_at.desc(), DeliveryJob.id.desc())
            .limit(limit)
        ).all()
        for row in delivery_rows:
            metadata_json = row.metadata_json if isinstance(row.metadata_json, dict) else {}
            items.append(
                RecentFailureItem(
                    failure_type="delivery_job",
                    ref_id=row.id,
                    status=row.status.value,
                    message=str(metadata_json.get("error")) if metadata_json.get("error") else None,
                    created_at=row.created_at,
                )
            )

        eval_rows = self.session.scalars(
            select(EvalRun)
            .where(EvalRun.status == EvalStatus.FAILED)
            .order_by(EvalRun.created_at.desc(), EvalRun.id.desc())
            .limit(limit)
        ).all()
        for row in eval_rows:
            summary_json = row.summary_json if isinstance(row.summary_json, dict) else {}
            items.append(
                RecentFailureItem(
                    failure_type="eval_run",
                    ref_id=row.id,
                    status=row.status.value,
                    message=str(summary_json.get("error")) if summary_json.get("error") else None,
                    created_at=row.created_at,
                )
            )

        items.sort(key=lambda x: x.created_at, reverse=True)
        return RecentFailuresResponse(items=items[:limit])

    def sources_performance(
        self,
        *,
        lookback_days: int = 30,
        max_runs: int = 500,
    ) -> SourcePerformanceSummary:
        return SourcePerformanceService(self.session).summarize(
            lookback_days=lookback_days,
            max_runs=max_runs,
        )

    def _count_tasks_failed(self) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(TaskJob)
                .where(TaskJob.status.in_([TaskJobStatus.FAILED, TaskJobStatus.DEAD_LETTER]))
            )
            or 0
        )

    def _count_runs_failed(self) -> int:
        return int(
            self.session.scalar(
                select(func.count()).select_from(Run).where(Run.status == RunStatus.FAILED)
            )
            or 0
        )

    def _count_delivery_failed(self) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(DeliveryJob)
                .where(
                    DeliveryJob.status.in_(
                        [DeliveryJobStatus.FAILED, DeliveryJobStatus.PARTIAL_FAILED]
                    )
                )
            )
            or 0
        )

    def _count_evals_failed(self) -> int:
        return int(
            self.session.scalar(
                select(func.count()).select_from(EvalRun).where(EvalRun.status == EvalStatus.FAILED)
            )
            or 0
        )
