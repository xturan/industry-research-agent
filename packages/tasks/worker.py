from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from packages.db.session import SessionLocal
from packages.tasks.service import TaskService

LOGGER = logging.getLogger(__name__)


class TaskWorker:
    def __init__(self, *, worker_id: str, poll_interval_seconds: int) -> None:
        self.worker_id = worker_id
        self.poll_interval_seconds = poll_interval_seconds

    def run_once(self) -> bool:
        with SessionLocal() as session:
            return self._run_once_with_session(session)

    def run_forever(self) -> None:
        LOGGER.info(
            "task worker loop started worker_id=%s poll_interval_seconds=%s",
            self.worker_id,
            self.poll_interval_seconds,
        )
        while True:
            did_work = self.run_once()
            if not did_work:
                time.sleep(self.poll_interval_seconds)

    def _run_once_with_session(self, session: Session) -> bool:
        task = TaskService(session).process_next(worker_id=self.worker_id)
        return task is not None
