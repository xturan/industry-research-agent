from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

REQUEST_ID_CTX: ContextVar[str] = ContextVar("request_id", default="-")
TASK_ID_CTX: ContextVar[str] = ContextVar("task_id", default="-")
RUN_ID_CTX: ContextVar[str] = ContextVar("run_id", default="-")
WORKER_ID_CTX: ContextVar[str] = ContextVar("worker_id", default="-")
STEP_NAME_CTX: ContextVar[str] = ContextVar("step_name", default="-")


class ContextFieldsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        record.request_id = REQUEST_ID_CTX.get()
        record.task_id = TASK_ID_CTX.get()
        record.run_id = RUN_ID_CTX.get()
        record.worker_id = WORKER_ID_CTX.get()
        record.step_name = STEP_NAME_CTX.get()
        return True


def configure_logging(log_level: str = "INFO") -> None:
    formatter = (
        "%(asctime)s %(levelname)s [%(name)s] %(message)s "
        "request_id=%(request_id)s task_id=%(task_id)s run_id=%(run_id)s "
        "worker_id=%(worker_id)s step_name=%(step_name)s"
    )
    logging.basicConfig(
        level=log_level.upper(),
        format=formatter,
        force=True,
    )
    context_filter = ContextFieldsFilter()
    root = logging.getLogger()
    root.filters.clear()
    root.addFilter(context_filter)
    for handler in root.handlers:
        handler.filters.clear()
        handler.addFilter(context_filter)


def clear_log_context() -> None:
    REQUEST_ID_CTX.set("-")
    TASK_ID_CTX.set("-")
    RUN_ID_CTX.set("-")
    WORKER_ID_CTX.set("-")
    STEP_NAME_CTX.set("-")


@contextmanager
def bind_log_context(
    *,
    request_id: str | None = None,
    task_id: str | None = None,
    run_id: str | None = None,
    worker_id: str | None = None,
    step_name: str | None = None,
) -> Generator[None, None, None]:
    request_token = REQUEST_ID_CTX.set(request_id or REQUEST_ID_CTX.get())
    task_token = TASK_ID_CTX.set(task_id or TASK_ID_CTX.get())
    run_token = RUN_ID_CTX.set(run_id or RUN_ID_CTX.get())
    worker_token = WORKER_ID_CTX.set(worker_id or WORKER_ID_CTX.get())
    step_token = STEP_NAME_CTX.set(step_name or STEP_NAME_CTX.get())
    try:
        yield
    finally:
        REQUEST_ID_CTX.reset(request_token)
        TASK_ID_CTX.reset(task_token)
        RUN_ID_CTX.reset(run_token)
        WORKER_ID_CTX.reset(worker_token)
        STEP_NAME_CTX.reset(step_token)
