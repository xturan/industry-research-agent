from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from packages.db.models import EvalRun, EvalRunItem
from packages.db.models.enums import EvalStatus, EvalType
from packages.evals.schemas import EvalCaseResult, EvalRunView

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc


class EvalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_run(
        self,
        *,
        eval_type: EvalType,
        target_type: str,
        target_ref: str | None,
    ) -> EvalRun:
        row = EvalRun(
            eval_type=eval_type,
            target_type=target_type,
            target_ref=target_ref,
            status=EvalStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def complete_run(
        self,
        *,
        eval_run: EvalRun,
        status: EvalStatus,
        score: float,
        summary_json: dict[str, object],
        items: list[EvalCaseResult],
    ) -> EvalRun:
        eval_run.status = status
        eval_run.score = score
        eval_run.summary_json = summary_json
        eval_run.finished_at = datetime.now(UTC)
        self.session.add(eval_run)
        self.session.flush()

        for item in items:
            self.session.add(
                EvalRunItem(
                    eval_run_id=eval_run.id,
                    case_name=item.case_name,
                    passed=item.passed,
                    score=item.score,
                    detail_json=item.detail_json,
                )
            )
        self.session.commit()
        return self.get_run(eval_run.id)

    def get_run(self, eval_run_id: int) -> EvalRun | None:
        return self.session.scalar(
            select(EvalRun)
            .options(selectinload(EvalRun.items))
            .where(EvalRun.id == eval_run_id)
        )

    def list_recent_failed(self, *, limit: int = 20) -> list[EvalRun]:
        return self.session.scalars(
            select(EvalRun)
            .where(EvalRun.status == EvalStatus.FAILED)
            .order_by(EvalRun.created_at.desc(), EvalRun.id.desc())
            .limit(limit)
        ).all()


def to_eval_run_view(row: EvalRun) -> EvalRunView:
    return EvalRunView(
        id=row.id,
        eval_type=row.eval_type,
        target_type=row.target_type,
        target_ref=row.target_ref,
        status=row.status,
        score=row.score,
        summary_json=row.summary_json,
        created_at=row.created_at,
        updated_at=row.updated_at,
        items=[
            EvalCaseResult(
                case_name=item.case_name,
                passed=item.passed,
                score=item.score or 0.0,
                detail_json=item.detail_json or {},
            )
            for item in sorted(row.items, key=lambda x: x.id)
        ],
    )
