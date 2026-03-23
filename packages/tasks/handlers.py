from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.agents.service import ResearchWorkflowService
from packages.content.schemas import ContentGenerateRequest
from packages.content.service import ContentFactoryService, ContentGenerationError
from packages.delivery.service import DeliveryService, DeliveryServiceError
from packages.tasks.enums import TaskType


class RetryableTaskError(Exception):
    """Transient task failure that can be retried."""


class NonRetryableTaskError(Exception):
    """Permanent task failure that should not be retried."""


@dataclass(slots=True)
class TaskExecutionResult:
    result_json: dict[str, Any]
    source_run_id: int | None = None


class TaskHandlers:
    def __init__(self, session: Session) -> None:
        self.session = session

    def execute(self, *, task_type: TaskType, payload_json: dict[str, Any]) -> TaskExecutionResult:
        if task_type == TaskType.RESEARCH_ANALYZE:
            return self._handle_research(payload_json)
        if task_type == TaskType.CONTENT_GENERATE:
            return self._handle_content(payload_json)
        if task_type == TaskType.DELIVERY_DISPATCH:
            return self._handle_delivery(payload_json)
        raise NonRetryableTaskError(f"Unsupported task_type: {task_type.value}")

    def _handle_research(self, payload_json: dict[str, Any]) -> TaskExecutionResult:
        try:
            request = ResearchAnalyzeRequest.model_validate(payload_json)
        except Exception as exc:  # noqa: BLE001
            raise NonRetryableTaskError(f"Invalid research payload: {exc}") from exc

        result = ResearchWorkflowService(self.session).analyze(request)
        result_json = result.model_dump(mode="json")
        if result.status != "succeeded":
            raise NonRetryableTaskError(result.error_message or "Research analysis failed.")
        return TaskExecutionResult(result_json=result_json, source_run_id=result.run_id)

    def _handle_content(self, payload_json: dict[str, Any]) -> TaskExecutionResult:
        try:
            request = ContentGenerateRequest.model_validate(payload_json)
        except Exception as exc:  # noqa: BLE001
            raise NonRetryableTaskError(f"Invalid content payload: {exc}") from exc

        try:
            result = ContentFactoryService(self.session).generate(request)
        except ContentGenerationError as exc:
            raise NonRetryableTaskError(str(exc)) from exc

        return TaskExecutionResult(
            result_json=result.model_dump(mode="json"),
            source_run_id=result.generation_run_id,
        )

    def _handle_delivery(self, payload_json: dict[str, Any]) -> TaskExecutionResult:
        delivery_job_id = payload_json.get("delivery_job_id")
        if not isinstance(delivery_job_id, int) or delivery_job_id <= 0:
            raise NonRetryableTaskError("delivery_job_id must be a positive integer.")

        try:
            result = DeliveryService(self.session).dispatch_job(delivery_job_id)
        except DeliveryServiceError as exc:
            raise NonRetryableTaskError(str(exc)) from exc

        return TaskExecutionResult(
            result_json=result.model_dump(mode="json"),
            source_run_id=None,
        )
