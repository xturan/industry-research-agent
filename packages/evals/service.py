from __future__ import annotations

from sqlalchemy.orm import Session

from packages.db.models.enums import EvalStatus, EvalType
from packages.evals.graders import (
    grade_content_outputs,
    grade_evidence_bundle,
    grade_rag_chunks,
    grade_research_output,
)
from packages.evals.repository import EvalRepository, to_eval_run_view
from packages.evals.runners import SmokeEvalRunner, SourceSmokeEvalRunner
from packages.evals.schemas import (
    EvalCaseResult,
    EvalRunView,
    EvalSummary,
    SmokeEvalRequest,
    SmokeEvalResponse,
    SourceSmokeEvalRequest,
    SourceSmokeEvalResponse,
)


class EvalServiceError(Exception):
    """Domain-level eval service error."""


class EvalService:
    # TODO: Add benchmark dataset registry and historical trend comparison.
    # TODO: Add optional LLM-as-judge mode behind explicit provider abstraction.

    def __init__(self, session: Session, *, repository: EvalRepository | None = None) -> None:
        self.session = session
        self.repository = repository or EvalRepository(session)

    def run_smoke(self, request: SmokeEvalRequest) -> SmokeEvalResponse:
        eval_run = self.repository.create_run(
            eval_type=EvalType.SMOKE,
            target_type="system",
            target_ref=request.query,
        )
        try:
            summary, items, artifacts = SmokeEvalRunner(self.session).run(request)
            completed = self.repository.complete_run(
                eval_run=eval_run,
                status=EvalStatus.SUCCEEDED,
                score=summary.score,
                summary_json={
                    "summary": summary.model_dump(mode="json"),
                    "artifact_keys": sorted(list(artifacts.keys())),
                },
                items=items,
            )
            return SmokeEvalResponse(
                eval_run_id=completed.id,
                status=completed.status,
                summary=summary,
            )
        except Exception as exc:  # noqa: BLE001
            summary = EvalSummary(
                passed=False,
                score=0.0,
                issue_count=1,
                issues=[str(exc)],
                case_count=1,
                passed_count=0,
            )
            self.repository.complete_run(
                eval_run=eval_run,
                status=EvalStatus.FAILED,
                score=0.0,
                summary_json={"summary": summary.model_dump(mode="json"), "error": str(exc)},
                items=[
                    EvalCaseResult(
                        case_name="smoke_runtime_exception",
                        passed=False,
                        score=0.0,
                        detail_json={"error": str(exc)},
                    )
                ],
            )
            raise EvalServiceError(str(exc)) from exc

    def run_source_smoke(self, request: SourceSmokeEvalRequest) -> SourceSmokeEvalResponse:
        eval_run = self.repository.create_run(
            eval_type=EvalType.SMOKE,
            target_type="source_smoke",
            target_ref="source_acquisition",
        )
        try:
            summary, items, artifacts, scenario_count = SourceSmokeEvalRunner(self.session).run(
                request
            )
            completed = self.repository.complete_run(
                eval_run=eval_run,
                status=EvalStatus.SUCCEEDED,
                score=summary.score,
                summary_json={
                    "summary": summary.model_dump(mode="json"),
                    "scenario_count": scenario_count,
                    "source_artifacts": artifacts,
                },
                items=items,
            )
            return SourceSmokeEvalResponse(
                eval_run_id=completed.id,
                status=completed.status,
                summary=summary,
                scenario_count=scenario_count,
            )
        except Exception as exc:  # noqa: BLE001
            summary = EvalSummary(
                passed=False,
                score=0.0,
                issue_count=1,
                issues=[str(exc)],
                case_count=1,
                passed_count=0,
            )
            self.repository.complete_run(
                eval_run=eval_run,
                status=EvalStatus.FAILED,
                score=0.0,
                summary_json={"summary": summary.model_dump(mode="json"), "error": str(exc)},
                items=[
                    EvalCaseResult(
                        case_name="source_smoke_runtime_exception",
                        passed=False,
                        score=0.0,
                        detail_json={"error": str(exc)},
                    )
                ],
            )
            raise EvalServiceError(str(exc)) from exc

    def get_eval_run(self, eval_run_id: int) -> EvalRunView | None:
        row = self.repository.get_run(eval_run_id)
        if row is None:
            return None
        return to_eval_run_view(row)

    def evaluate_rag_chunks_payload(self, payload: dict) -> list[EvalCaseResult]:
        return grade_rag_chunks(payload)

    def evaluate_evidence_bundle_payload(self, payload: dict) -> list[EvalCaseResult]:
        return grade_evidence_bundle(payload)

    def evaluate_research_payload(self, payload: dict) -> list[EvalCaseResult]:
        return grade_research_output(payload)

    def evaluate_content_payload(self, payload: list[dict]) -> list[EvalCaseResult]:
        return grade_content_outputs(payload)
