from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

API_REQUEST_TOTAL = Counter(
    "invest_agent_api_request_total",
    "Total API requests by method, path template, and status code.",
    ["method", "path", "status_code"],
)
API_REQUEST_LATENCY_SECONDS = Histogram(
    "invest_agent_api_request_latency_seconds",
    "API request latency by method and path template.",
    ["method", "path"],
)

TASK_ENQUEUED_TOTAL = Counter(
    "invest_agent_task_enqueued_total",
    "Total tasks accepted into the queue by task type.",
    ["task_type"],
)
TASK_STARTED_TOTAL = Counter(
    "invest_agent_task_started_total",
    "Total tasks started by workers.",
    ["task_type"],
)
TASK_SUCCEEDED_TOTAL = Counter(
    "invest_agent_task_succeeded_total",
    "Total tasks completed successfully by task type.",
    ["task_type"],
)
TASK_FAILED_TOTAL = Counter(
    "invest_agent_task_failed_total",
    "Total failed tasks by task type and terminal status.",
    ["task_type", "status"],
)
TASK_RUNNING_GAUGE = Gauge(
    "invest_agent_task_running",
    "Current running tasks by task type.",
    ["task_type"],
)
TASK_EXECUTION_DURATION_SECONDS = Histogram(
    "invest_agent_task_execution_duration_seconds",
    "Task execution duration by task type and final status.",
    ["task_type", "status"],
)


def metrics_payload() -> bytes:
    return generate_latest()


def metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST


def record_api_request(
    *,
    method: str,
    path: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    status_text = str(status_code)
    API_REQUEST_TOTAL.labels(method=method, path=path, status_code=status_text).inc()
    API_REQUEST_LATENCY_SECONDS.labels(method=method, path=path).observe(
        max(duration_seconds, 0.0)
    )


def mark_task_enqueued(*, task_type: str) -> None:
    TASK_ENQUEUED_TOTAL.labels(task_type=task_type).inc()


@contextmanager
def track_task_execution(task_type: str) -> Generator[dict[str, float], None, None]:
    start = time.perf_counter()
    TASK_STARTED_TOTAL.labels(task_type=task_type).inc()
    TASK_RUNNING_GAUGE.labels(task_type=task_type).inc()
    state: dict[str, float] = {"duration_seconds": 0.0}
    try:
        yield state
    finally:
        duration = max(time.perf_counter() - start, 0.0)
        state["duration_seconds"] = duration
        TASK_RUNNING_GAUGE.labels(task_type=task_type).dec()


def mark_task_succeeded(*, task_type: str, duration_seconds: float) -> None:
    TASK_SUCCEEDED_TOTAL.labels(task_type=task_type).inc()
    TASK_EXECUTION_DURATION_SECONDS.labels(task_type=task_type, status="succeeded").observe(
        max(duration_seconds, 0.0)
    )


def mark_task_failed(*, task_type: str, status: str, duration_seconds: float) -> None:
    TASK_FAILED_TOTAL.labels(task_type=task_type, status=status).inc()
    TASK_EXECUTION_DURATION_SECONDS.labels(task_type=task_type, status=status).observe(
        max(duration_seconds, 0.0)
    )
