from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.orm import Session

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.content.schemas import ContentGenerateRequest
from packages.tasks.enums import TaskType

_STRATEGY_ROUNDS = {"quick": 2, "standard": 3, "deep": 5}


class ResearchExecutor(Protocol):
    """Executes a deep-research workflow for a Run (business execution ONLY).

    The Run lifecycle (QUEUED/RUNNING/SUCCEEDED/FAILED/CANCELLED) is owned by the
    worker (TaskService). This executor only produces the business result.
    """

    def run(
        self,
        *,
        query: str,
        run_id: int | None,
        strategy: str | None,
    ) -> dict[str, Any]: ...


class RetryableTaskError(Exception):
    """Transient task failure that can be retried."""


class NonRetryableTaskError(Exception):
    """Permanent task failure that should not be retried."""


@dataclass(slots=True)
class TaskExecutionResult:
    result_json: dict[str, Any]
    source_run_id: int | None = None


class TaskHandlers:
    """Executes a claimed task. Heavy AI services are lazy-imported so that
    importing this module stays light (fast unit tests, no AI stack)."""

    def __init__(
        self,
        session: Session,
        *,
        research_executor: ResearchExecutor | None = None,
    ) -> None:
        self.session = session
        self._research_executor = research_executor

    def execute(
        self,
        *,
        task_type: TaskType,
        payload_json: dict[str, Any],
        source_run_id: int | None = None,
    ) -> TaskExecutionResult:
        if task_type == TaskType.RESEARCH_ANALYZE:
            return self._handle_research(payload_json, source_run_id=source_run_id)
        if task_type == TaskType.CONTENT_GENERATE:
            return self._handle_content(payload_json)
        if task_type == TaskType.DELIVERY_DISPATCH:
            return self._handle_delivery(payload_json)
        raise NonRetryableTaskError(f"Unsupported task_type: {task_type.value}")

    def _handle_research(
        self, payload_json: dict[str, Any], *, source_run_id: int | None = None
    ) -> TaskExecutionResult:
        try:
            request = ResearchAnalyzeRequest.model_validate(payload_json)
        except Exception as exc:  # noqa: BLE001
            raise NonRetryableTaskError(f"Invalid research payload: {exc}") from exc

        # New Deep Research graph workflow (with retrieval ranking) when a
        # research_strategy is set; otherwise fall back to the legacy agent.
        if request.research_strategy:
            return self._handle_deep_research(request, run_id=source_run_id)

        from packages.agents.service import ResearchWorkflowService  # lazy

        result = ResearchWorkflowService(self.session).analyze(request)
        result_json = result.model_dump(mode="json")
        if result.status != "succeeded":
            raise NonRetryableTaskError(result.error_message or "Research analysis failed.")
        return TaskExecutionResult(result_json=result_json, source_run_id=result.run_id)

    def _handle_deep_research(
        self, request: ResearchAnalyzeRequest, *, run_id: int | None = None
    ) -> TaskExecutionResult:
        if self._research_executor is not None:
            result_json = self._research_executor.run(
                query=request.query,
                run_id=run_id,
                strategy=request.research_strategy,
            )
            result_json.setdefault("pipeline", "deep_research_graph_v2")
            result_json["run_id"] = run_id
            return TaskExecutionResult(result_json=result_json, source_run_id=run_id)

        from packages.agents.deep_research import DeepResearchAgent  # lazy

        rounds = _STRATEGY_ROUNDS.get(request.research_strategy, 3)
        try:
            agent = DeepResearchAgent(
                max_rounds=rounds,
                max_sources_per_round=5,
                strategy=request.research_strategy,
            )
            report = agent.run(request.query, run_id=run_id, persist=True)
        except Exception as exc:  # noqa: BLE001
            raise RetryableTaskError(f"Deep research failed: {exc}") from exc

        result_json = report.model_dump(mode="json")
        result_json["pipeline"] = "deep_research_graph_v2"
        result_json["run_id"] = run_id or agent._last_run_id
        return TaskExecutionResult(
            result_json=result_json,
            source_run_id=run_id or agent._last_run_id,
        )

    def _handle_content(self, payload_json: dict[str, Any]) -> TaskExecutionResult:
        try:
            request = ContentGenerateRequest.model_validate(payload_json)
        except Exception as exc:  # noqa: BLE001
            raise NonRetryableTaskError(f"Invalid content payload: {exc}") from exc

        from packages.content.service import ContentFactoryService, ContentGenerationError  # lazy

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

        from packages.delivery.service import DeliveryService, DeliveryServiceError  # lazy

        try:
            result = DeliveryService(self.session).dispatch_job(delivery_job_id)
        except DeliveryServiceError as exc:
            raise NonRetryableTaskError(str(exc)) from exc

        return TaskExecutionResult(
            result_json=result.model_dump(mode="json"),
            source_run_id=None,
        )
