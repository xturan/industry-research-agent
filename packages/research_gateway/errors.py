"""Unified Gateway error contract (G1.1).

Every Gateway error carries a stable machine-readable `code` so clients (and the
later G2 Capability Gateway) can branch on semantics instead of HTTP strings.
"""

from __future__ import annotations

from typing import Any


class GatewayError(Exception):
    code = "GATEWAY_ERROR"
    status_code = 400
    retry_after_seconds: int | None = None

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_response(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class RunNotFoundError(GatewayError):
    code = "RUN_NOT_FOUND"
    status_code = 404


class RunNotCompletedError(GatewayError):
    code = "RUN_NOT_COMPLETED"
    status_code = 409


class RunFailedError(GatewayError):
    code = "RUN_FAILED"
    status_code = 409


class InvalidResearchRequestError(GatewayError):
    code = "INVALID_RESEARCH_REQUEST"
    status_code = 400


class IdempotencyKeyReusedError(GatewayError):
    code = "IDEMPOTENCY_KEY_REUSED"
    status_code = 409


class QueueCapacityExceededError(GatewayError):
    code = "RESEARCH_QUEUE_CAPACITY_EXCEEDED"
    status_code = 503
    retry_after_seconds = 30

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)
        self.retry_after_seconds = (details or {}).get("retry_after_seconds") or 30


class RunAlreadyTerminalError(GatewayError):
    code = "RUN_ALREADY_TERMINAL"
    status_code = 409


class ResearchRunCancelled(Exception):
    """Internal control-flow signal: a cooperative cancellation was observed.

    NOT a GatewayError — it is raised by the executor at safe stage boundaries and
    caught by the worker, which then moves the Run/Task to CANCELLED.
    """
