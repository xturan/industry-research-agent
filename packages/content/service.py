from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from packages.agents.schemas import ResearchAnalysisResult
from packages.content.provider import ContentProviderResolution, resolve_content_provider
from packages.content.repository import (
    ContentAssetRepository,
    asset_to_view,
    map_format_to_content_type,
)
from packages.content.schemas import (
    ContentAssetSummary,
    ContentAssetView,
    ContentGenerateRequest,
    ContentGenerationResponse,
    GeneratedContentDraft,
)
from packages.core.run_log import CompactRunLogger
from packages.db.models import Run, RunStatus, RunStep, RunType, StepStatus
from packages.policy.service import PolicyChecker

T = TypeVar("T")


class ContentGenerationError(Exception):
    """Domain-level content generation error."""


class ContentFactoryService:
    """Generate multi-platform content assets from structured research memo."""

    # TODO: Add publishing connector hooks (WeChat/XHS/Douyin) in a separate delivery layer.
    # TODO: Add cover image generation metadata and growth feedback loop integration.

    def __init__(
        self,
        session: Session,
        *,
        provider_resolution: ContentProviderResolution | None = None,
        repository: ContentAssetRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or ContentAssetRepository(session)
        self.provider_resolution = provider_resolution
        self._run_logger: CompactRunLogger | None = None

    def generate(self, request: ContentGenerateRequest) -> ContentGenerationResponse:
        research, source_run = self._load_research_source(request)
        source_research_run_id = source_run.id if source_run is not None else research.run_id
        resolution = self.provider_resolution or resolve_content_provider(request.mode)
        generation_run = self._create_generation_run(
            request=request,
            source_research_run_id=source_research_run_id,
            theme_id=source_run.theme_id if source_run is not None else None,
            resolved_mode=resolution.resolved_mode.value,
        )
        self._run_logger = CompactRunLogger(task_name="content_generate", run_id=generation_run.id)
        self._run_logger.start(
            input_summary=generation_run.input_json,
            decision_summary=[
                "load validated research memo",
                "resolve content provider",
                "generate requested content formats",
                "persist assets after policy checks",
            ],
        )

        try:
            drafts: list[GeneratedContentDraft] = []
            for content_format in request.content_types:
                draft = self._run_step(
                    run=generation_run,
                    step_name=f"generate_{content_format.value}",
                    agent_name="content-deterministic-generator",
                    input_json={
                        "content_format": content_format.value,
                        "style_hints": request.style_hints,
                        "title_preference": request.title_preference,
                    },
                    fn=lambda content_format=content_format: resolution.generator.generate(
                        content_format=content_format,
                        research=research,
                        style_hints=request.style_hints,
                        title_preference=request.title_preference,
                    ),
                    output_serializer=lambda result: result.model_dump(mode="json"),
                )
                drafts.append(draft)

            assets = self._run_step(
                run=generation_run,
                step_name="persist_assets",
                agent_name="content-repository",
                input_json={"draft_count": len(drafts)},
                fn=lambda: self._persist_assets(
                    drafts=drafts,
                    source_research_run_id=source_research_run_id,
                    generation_run_id=generation_run.id,
                    theme_id=source_run.theme_id if source_run is not None else None,
                    generation_mode=resolution.resolved_mode.value,
                ),
                output_serializer=lambda result: {"asset_ids": [item.asset_id for item in result]},
            )

            notes = [
                *resolution.notes,
                (
                    "content_type uses existing DB enum mapping; exact platform format is "
                    "stored in meta_json.content_format."
                ),
            ]
            response = ContentGenerationResponse(
                generation_run_id=generation_run.id,
                source_research_run_id=source_research_run_id,
                status=RunStatus.SUCCEEDED.value,
                assets=assets,
                notes=notes,
            )
            self._finish_run(
                generation_run,
                status=RunStatus.SUCCEEDED,
                output_json=response.model_dump(mode="json"),
            )
            return response
        except Exception as exc:
            self._finish_run(
                generation_run,
                status=RunStatus.FAILED,
                output_json={"error": str(exc)},
            )
            raise ContentGenerationError(str(exc)) from exc
        finally:
            self._run_logger = None

    def get_asset(self, asset_id: int) -> ContentAssetView | None:
        row = self.repository.get_asset(asset_id)
        return asset_to_view(row) if row is not None else None

    def list_assets_by_research_run(self, run_id: int) -> list[ContentAssetView]:
        rows = self.repository.list_by_research_run_id(run_id)
        return [asset_to_view(row) for row in rows]

    def _load_research_source(
        self, request: ContentGenerateRequest
    ) -> tuple[ResearchAnalysisResult, Run | None]:
        if request.research_run_id is not None:
            run = self.session.get(Run, request.research_run_id)
            if run is None:
                raise ContentGenerationError(f"Research run {request.research_run_id} not found.")
            if run.run_type != RunType.RESEARCH:
                raise ContentGenerationError(
                    f"Run {request.research_run_id} is not a research run."
                )
            if not isinstance(run.output_json, dict):
                raise ContentGenerationError(
                    f"Research run {request.research_run_id} has no structured output_json."
                )
            try:
                result = ResearchAnalysisResult.model_validate(run.output_json)
            except ValidationError as exc:
                raise ContentGenerationError(
                    f"Research run {request.research_run_id} output_json schema mismatch: {exc}"
                ) from exc
            return result, run

        if request.research_memo is None:
            raise ContentGenerationError("Missing research input.")
        try:
            result = ResearchAnalysisResult.model_validate(request.research_memo)
        except ValidationError as exc:
            raise ContentGenerationError(f"research_memo schema mismatch: {exc}") from exc
        return result, None

    def _create_generation_run(
        self,
        *,
        request: ContentGenerateRequest,
        source_research_run_id: int | None,
        theme_id: int | None,
        resolved_mode: str,
    ) -> Run:
        run = Run(
            run_type=RunType.CONTENT_GENERATE,
            theme_id=theme_id,
            status=RunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            input_json={
                "pipeline": "content_factory_v1",
                "source_research_run_id": source_research_run_id,
                "content_types": [item.value for item in request.content_types],
                "mode_requested": request.mode.value,
                "mode_resolved": resolved_mode,
                "style_hints": request.style_hints,
                "title_preference": request.title_preference,
            },
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
            started_at=datetime.now(timezone.utc),
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
            step.finished_at = datetime.now(timezone.utc)
            self.session.add(step)
            self.session.commit()
            if self._run_logger is not None:
                self._run_logger.step(
                    step_name=step_name,
                    agent_name=agent_name,
                    input_summary=input_json,
                    status=StepStatus.FAILED.value,
                    error=str(exc),
                )
            raise

        step.status = StepStatus.SUCCEEDED
        step.finished_at = datetime.now(timezone.utc)
        if output_serializer is not None:
            step.output_json = output_serializer(result)
        else:
            step.output_json = self._to_output_json(result)
        self.session.add(step)
        self.session.commit()
        if self._run_logger is not None:
            self._run_logger.step(
                step_name=step_name,
                agent_name=agent_name,
                input_summary=input_json,
                output_summary=step.output_json,
                status=StepStatus.SUCCEEDED.value,
            )
        return result

    def _persist_assets(
        self,
        *,
        drafts: list[GeneratedContentDraft],
        source_research_run_id: int | None,
        generation_run_id: int,
        theme_id: int | None,
        generation_mode: str,
    ) -> list[ContentAssetSummary]:
        created: list[ContentAssetSummary] = []
        policy_checker = PolicyChecker()
        for draft in drafts:
            mapped_type = map_format_to_content_type(draft.content_format)
            policy_report = policy_checker.check_content_text(
                title=draft.title,
                body=draft.body_text,
                disclaimers=[draft.disclaimer],
            )
            row = self.repository.create_asset(
                draft=draft,
                mapped_content_type=mapped_type,
                theme_id=theme_id,
                source_research_run_id=source_research_run_id,
                generation_run_id=generation_run_id,
                generation_mode=generation_mode,
                policy_report=policy_report.model_dump(mode="json"),
            )
            created.append(
                ContentAssetSummary(
                    asset_id=row.id,
                    content_format=draft.content_format,
                    content_type=row.content_type.value,
                    title=row.title,
                    status=row.status.value,
                    preview=(row.body_markdown or "")[:140],
                )
            )
        self.session.commit()
        return created

    def _finish_run(self, run: Run, *, status: RunStatus, output_json: dict[str, Any]) -> None:
        run.status = status
        run.finished_at = datetime.now(timezone.utc)
        run.output_json = output_json
        self.session.add(run)
        self.session.commit()
        if self._run_logger is not None:
            self._run_logger.finish(status=status.value, output_summary=output_json)

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
                else:
                    serialized.append(item)
            return {"items": serialized}
        return {"value": str(value)}
