from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.agents.provider import ProviderResolution
from packages.agents.schemas import (
    ResearchAnalysisResult,
    ResearchAnalyzeRequest,
    ResearchRunView,
    RunStepView,
)
from packages.agents.workflow import ResearchWorkflowRunner
from packages.db.models import Run, RunStep


class ResearchWorkflowService:
    def __init__(
        self,
        session: Session,
        *,
        provider_resolution: ProviderResolution | None = None,
    ) -> None:
        self.session = session
        self.provider_resolution = provider_resolution

    def analyze(self, request: ResearchAnalyzeRequest) -> ResearchAnalysisResult:
        runner = ResearchWorkflowRunner(
            self.session,
            provider_resolution=self.provider_resolution,
        )
        return runner.run(request)

    def get_run_view(self, run_id: int) -> ResearchRunView | None:
        run = self.session.get(Run, run_id)
        if run is None:
            return None

        steps = self.session.scalars(
            select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.id.asc())
        ).all()

        return ResearchRunView(
            run_id=run.id,
            run_type=run.run_type.value,
            status=run.status.value,
            started_at=run.started_at,
            finished_at=run.finished_at,
            input_json=run.input_json,
            output_json=run.output_json,
            steps=[
                RunStepView(
                    id=step.id,
                    step_name=step.step_name,
                    agent_name=step.agent_name,
                    status=step.status.value,
                    input_json=step.input_json,
                    output_json=step.output_json,
                    error_message=step.error_message,
                    started_at=step.started_at,
                    finished_at=step.finished_at,
                )
                for step in steps
            ],
        )
