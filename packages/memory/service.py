from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.db.models import Run, RunStatus, RunStep, RunType, StepStatus
from packages.memory.extractors import extract_memories_from_run
from packages.memory.feedback import (
    ContentFeedbackRepository,
    FeedbackError,
    build_strategy_memory_from_feedback,
)
from packages.memory.repository import MemoryRepository, memory_to_view
from packages.memory.schemas import (
    AccountPreferenceUpsertRequest,
    FeedbackIngestRequest,
    FeedbackIngestResponse,
    MemoryCandidate,
    MemoryExtractRunResponse,
    MemoryKind,
    MemorySearchRequest,
    MemorySearchResponse,
    ScopeMemoriesResponse,
)

T = TypeVar("T")

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc


class MemoryServiceError(Exception):
    """Domain-level memory service error."""


class MemoryService:
    """Durable memory extraction, search, and growth-feedback loop orchestration."""

    # TODO: Add hybrid retrieval (keyword + vector) when pgvector memory indexing is enabled.
    # TODO: Add policy/evals signals to score and prioritize memory candidates.

    def __init__(
        self,
        session: Session,
        *,
        repository: MemoryRepository | None = None,
        feedback_repository: ContentFeedbackRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or MemoryRepository(session)
        self.feedback_repository = feedback_repository or ContentFeedbackRepository(session)

    def extract_from_run(self, run_id: int) -> MemoryExtractRunResponse:
        source_run = self.session.get(Run, run_id)
        if source_run is None:
            raise MemoryServiceError(f"Run {run_id} not found.")

        source_steps = self.session.scalars(
            select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.id.asc())
        ).all()

        refresh_run = self._create_memory_refresh_run(
            pipeline="memory_extract_from_run_v1",
            input_json={"source_run_id": run_id, "source_run_type": source_run.run_type.value},
        )

        try:
            self._run_step(
                run=refresh_run,
                step_name="load_source_run",
                agent_name="memory-extractor",
                input_json={"source_run_id": run_id},
                fn=lambda: {
                    "source_run_id": source_run.id,
                    "source_run_status": source_run.status.value,
                    "source_step_count": len(source_steps),
                },
            )
            candidates = self._run_step(
                run=refresh_run,
                step_name="extract_memory_candidates",
                agent_name="memory-extractor",
                input_json={"source_run_type": source_run.run_type.value},
                fn=lambda: extract_memories_from_run(run=source_run, steps=source_steps),
            )
            rows = self._run_step(
                run=refresh_run,
                step_name="persist_memory_records",
                agent_name="memory-repository",
                input_json={"candidate_count": len(candidates)},
                fn=lambda: self.repository.bulk_upsert(candidates),
                output_serializer=lambda result: {
                    "memory_ids": [row.id for row in result],
                    "memory_types": [row.memory_type.value for row in result],
                },
            )

            response = MemoryExtractRunResponse(
                source_run_id=run_id,
                memory_refresh_run_id=refresh_run.id,
                created_or_updated=len(rows),
                memory_ids=[row.id for row in rows],
                memory_types=sorted(
                    {memory_to_view(row).memory_type for row in rows},
                    key=lambda item: item.value,
                ),
                status=RunStatus.SUCCEEDED.value,
            )
            self._finish_run(
                refresh_run,
                status=RunStatus.SUCCEEDED,
                output_json=response.model_dump(mode="json"),
            )
            return response
        except Exception as exc:
            self._finish_run(
                refresh_run,
                status=RunStatus.FAILED,
                output_json={"error": str(exc)},
            )
            raise MemoryServiceError(str(exc)) from exc

    def ingest_content_feedback(self, payload: FeedbackIngestRequest) -> FeedbackIngestResponse:
        refresh_run = self._create_memory_refresh_run(
            pipeline="content_feedback_loop_v1",
            input_json={
                "content_asset_id": payload.content_asset_id,
                "channel": payload.channel,
            },
        )

        try:
            event = self._run_step(
                run=refresh_run,
                step_name="record_feedback_event",
                agent_name="growth-feedback",
                input_json=payload.model_dump(mode="json"),
                fn=lambda: self.feedback_repository.create_event(payload),
                output_serializer=lambda result: {
                    "event_id": result.id,
                    "content_asset_id": result.content_asset_id,
                    "channel": result.channel,
                },
            )
            events = self._run_step(
                run=refresh_run,
                step_name="load_channel_feedback",
                agent_name="growth-feedback",
                input_json={"channel": payload.channel, "limit": 50},
                fn=lambda: self.feedback_repository.list_events_by_channel(
                    payload.channel, limit=50
                ),
                output_serializer=lambda result: {"event_count": len(result)},
            )
            candidate = self._run_step(
                run=refresh_run,
                step_name="build_content_strategy_memory",
                agent_name="memory-growth-selector",
                input_json={"channel": payload.channel, "event_count": len(events)},
                fn=lambda: build_strategy_memory_from_feedback(
                    channel=payload.channel, events=events
                ),
                output_serializer=lambda result: result.model_dump(mode="json") if result else None,
            )

            strategy_rows = []
            if candidate is not None:
                strategy_rows = self._run_step(
                    run=refresh_run,
                    step_name="persist_strategy_memory",
                    agent_name="memory-repository",
                    input_json={"channel": payload.channel},
                    fn=lambda: self.repository.bulk_upsert([candidate]),
                    output_serializer=lambda result: {"memory_ids": [row.id for row in result]},
                )
            else:
                self._record_skipped_step(
                    run=refresh_run,
                    step_name="persist_strategy_memory",
                    agent_name="memory-repository",
                    reason="No feedback events available for strategy memory update.",
                )

            response = FeedbackIngestResponse(
                event_id=event.id,
                content_asset_id=event.content_asset_id,
                channel=event.channel,
                captured_at=event.captured_at,
                memory_refresh_run_id=refresh_run.id,
                strategy_memory_ids=[row.id for row in strategy_rows],
                status=RunStatus.SUCCEEDED.value,
            )
            self._finish_run(
                refresh_run,
                status=RunStatus.SUCCEEDED,
                output_json=response.model_dump(mode="json"),
            )
            return response
        except FeedbackError as exc:
            self._finish_run(
                refresh_run,
                status=RunStatus.FAILED,
                output_json={"error": str(exc)},
            )
            raise MemoryServiceError(str(exc)) from exc
        except Exception as exc:
            self._finish_run(
                refresh_run,
                status=RunStatus.FAILED,
                output_json={"error": str(exc)},
            )
            raise MemoryServiceError(str(exc)) from exc

    def upsert_account_preference(self, request: AccountPreferenceUpsertRequest) -> int:
        candidate = MemoryCandidate(
            memory_type=MemoryKind.ACCOUNT_PREFERENCE_MEMORY,
            scope_key=request.scope_key,
            content=request.content,
            score=request.score,
            metadata_json={
                **request.metadata_json,
                "memory_key": f"account_pref:{request.scope_key}",
            },
        )
        row = self.repository.bulk_upsert([candidate])[0]
        return row.id

    def search(self, request: MemorySearchRequest) -> MemorySearchResponse:
        rows = self.repository.search(request)
        items = [memory_to_view(row) for row in rows]
        return MemorySearchResponse(total=len(items), items=items)

    def list_by_scope(self, scope_key: str, *, limit: int = 50) -> ScopeMemoriesResponse:
        rows = self.repository.list_by_scope(scope_key, limit=limit)
        return ScopeMemoriesResponse(
            scope_key=scope_key,
            items=[memory_to_view(row) for row in rows],
        )

    def _create_memory_refresh_run(self, *, pipeline: str, input_json: dict[str, Any]) -> Run:
        run = Run(
            run_type=RunType.MEMORY_REFRESH,
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
            input_json={"pipeline": pipeline, **input_json},
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def _run_step(
        self,
        *,
        run: Run,
        step_name: str,
        agent_name: str,
        input_json: dict[str, Any] | None,
        fn: Callable[[], T],
        output_serializer: Callable[[T], dict[str, Any] | None] | None = None,
    ) -> T:
        step = RunStep(
            run_id=run.id,
            step_name=step_name,
            agent_name=agent_name,
            status=StepStatus.RUNNING,
            started_at=datetime.now(UTC),
            input_json=input_json,
        )
        self.session.add(step)
        self.session.commit()
        self.session.refresh(step)

        try:
            result = fn()
        except Exception as exc:
            step.status = StepStatus.FAILED
            step.error_message = str(exc)
            step.finished_at = datetime.now(UTC)
            self.session.add(step)
            self.session.commit()
            raise

        step.status = StepStatus.SUCCEEDED
        step.finished_at = datetime.now(UTC)
        if output_serializer is not None:
            step.output_json = output_serializer(result)
        else:
            step.output_json = self._to_output_json(result)
        self.session.add(step)
        self.session.commit()
        return result

    def _record_skipped_step(
        self,
        *,
        run: Run,
        step_name: str,
        agent_name: str,
        reason: str,
    ) -> None:
        step = RunStep(
            run_id=run.id,
            step_name=step_name,
            agent_name=agent_name,
            status=StepStatus.SKIPPED,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            output_json={"reason": reason},
        )
        self.session.add(step)
        self.session.commit()

    def _finish_run(self, run: Run, *, status: RunStatus, output_json: dict[str, Any]) -> None:
        run.status = status
        run.finished_at = datetime.now(UTC)
        run.output_json = output_json
        self.session.add(run)
        self.session.commit()

    def _to_output_json(self, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, list):
            serialized = []
            for item in value:
                if isinstance(item, BaseModel):
                    serialized.append(item.model_dump(mode="json"))
                elif hasattr(item, "to_dict"):
                    serialized.append(item.to_dict())
                else:
                    serialized.append(str(item))
            return {"items": serialized}
        return {"value": str(value)}
