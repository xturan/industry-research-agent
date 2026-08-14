from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from packages.db.models import ResearchGraphCheckpoint

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc  # noqa: UP017


class GraphCheckpointRepository:
    def __init__(
        self,
        *,
        session: Session | None = None,
        base_dir: str | Path = "data/graph_checkpoints",
    ) -> None:
        self.session = session
        self.base_dir = Path(base_dir)

    def save(
        self,
        *,
        run_id: int,
        thread_id: str,
        current_node: str | None,
        state: dict[str, Any],
    ) -> str:
        root = self.base_dir / f"run_{run_id}"
        root.mkdir(parents=True, exist_ok=True)
        path = root / "latest.json"
        payload = {
            "run_id": run_id,
            "thread_id": thread_id,
            "current_node": current_node,
            "saved_at": datetime.now(UTC).isoformat(),
            "state": state,
        }
        saved_payload = self._save_db(
            run_id=run_id,
            thread_id=thread_id,
            current_node=current_node,
            state=state,
        )
        payload["checkpoint_version"] = (
            saved_payload.get("checkpoint_version") if saved_payload is not None else None
        )
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def load(self, *, run_id: int) -> dict[str, Any] | None:
        db_payload = self._load_db(run_id=run_id)
        if db_payload is not None:
            return db_payload
        path = self.base_dir / f"run_{run_id}" / "latest.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def history(self, *, run_id: int, limit: int = 20) -> list[dict[str, Any]]:
        history = self._history_db(run_id=run_id, limit=limit)
        if history:
            return history
        checkpoint = self.load(run_id=run_id)
        return [checkpoint] if checkpoint is not None else []

    def history_count(self, *, run_id: int) -> int:
        if self.session is None:
            return 1 if self.load(run_id=run_id) is not None else 0
        try:
            return (
                self.session.query(ResearchGraphCheckpoint)
                .filter_by(run_id=run_id)
                .count()
            )
        except SQLAlchemyError:
            self.session.rollback()
            return 0

    def compact(self, *, run_id: int, keep_latest: int = 20) -> dict[str, Any]:
        keep_latest = max(1, keep_latest)
        if self.session is None:
            checkpoint = self.load(run_id=run_id)
            return {
                "run_id": run_id,
                "keep_latest": keep_latest,
                "deleted_count": 0,
                "retained_count": 1 if checkpoint is not None else 0,
                "latest_checkpoint_version": checkpoint.get("checkpoint_version")
                if checkpoint is not None
                else None,
            }
        try:
            rows = (
                self.session.query(ResearchGraphCheckpoint)
                .filter_by(run_id=run_id)
                .order_by(ResearchGraphCheckpoint.checkpoint_version.desc())
                .all()
            )
            retained_rows = rows[:keep_latest]
            retained_ids = {row.id for row in retained_rows}
            deleted_count = 0
            if retained_ids:
                deleted_count = (
                    self.session.query(ResearchGraphCheckpoint)
                    .filter(ResearchGraphCheckpoint.run_id == run_id)
                    .filter(ResearchGraphCheckpoint.id.not_in(retained_ids))
                    .delete(synchronize_session=False)
                )
            self.session.commit()
            latest_version = (
                retained_rows[0].checkpoint_version if retained_rows else None
            )
            return {
                "run_id": run_id,
                "keep_latest": keep_latest,
                "deleted_count": int(deleted_count),
                "retained_count": len(retained_rows),
                "latest_checkpoint_version": latest_version,
            }
        except SQLAlchemyError:
            self.session.rollback()
            return {
                "run_id": run_id,
                "keep_latest": keep_latest,
                "deleted_count": 0,
                "retained_count": self.history_count(run_id=run_id),
                "latest_checkpoint_version": None,
            }

    def _save_db(
        self,
        *,
        run_id: int,
        thread_id: str,
        current_node: str | None,
        state: dict[str, Any],
    ) -> dict[str, Any] | None:
        if self.session is None:
            return None
        try:
            latest = (
                self.session.query(ResearchGraphCheckpoint)
                .filter_by(run_id=run_id)
                .order_by(ResearchGraphCheckpoint.checkpoint_version.desc())
                .first()
            )
            next_version = 1 if latest is None else int(latest.checkpoint_version) + 1
            row = ResearchGraphCheckpoint(
                run_id=run_id,
                checkpoint_version=next_version,
                thread_id=thread_id,
                current_node=current_node,
                state_json=state,
                saved_at=datetime.now(UTC),
            )
            self.session.add(row)
            self.session.commit()
            self.session.refresh(row)
            return self._serialize_row(row)
        except SQLAlchemyError:
            self.session.rollback()
            return None

    def _load_db(self, *, run_id: int) -> dict[str, Any] | None:
        if self.session is None:
            return None
        try:
            row = (
                self.session.query(ResearchGraphCheckpoint)
                .filter_by(run_id=run_id)
                .order_by(ResearchGraphCheckpoint.checkpoint_version.desc())
                .first()
            )
        except SQLAlchemyError:
            self.session.rollback()
            return None
        if row is None:
            return None
        return self._serialize_row(row)

    def _history_db(self, *, run_id: int, limit: int) -> list[dict[str, Any]]:
        if self.session is None:
            return []
        try:
            rows = (
                self.session.query(ResearchGraphCheckpoint)
                .filter_by(run_id=run_id)
                .order_by(ResearchGraphCheckpoint.checkpoint_version.desc())
                .limit(limit)
                .all()
            )
        except SQLAlchemyError:
            self.session.rollback()
            return []
        return [self._serialize_row(row) for row in rows]

    def _serialize_row(self, row: ResearchGraphCheckpoint) -> dict[str, Any]:
        return {
            "run_id": row.run_id,
            "checkpoint_version": row.checkpoint_version,
            "thread_id": row.thread_id,
            "current_node": row.current_node,
            "saved_at": row.saved_at.isoformat() if row.saved_at is not None else None,
            "state": row.state_json,
        }
