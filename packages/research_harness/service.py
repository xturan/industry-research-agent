from __future__ import annotations

from pathlib import Path
from typing import Literal

from sqlalchemy.orm import Session

from packages.db.models import Run
from packages.research_harness.checkpoints import GraphCheckpointRepository
from packages.research_harness.runner import ResearchGraphRunner
from packages.research_harness.schemas import (
    GraphAnalyzeRequest,
    GraphAnalyzeResponse,
    GraphCheckpointCompactionResult,
    GraphRunSummary,
)
from packages.research_reports.schemas import ResearchReportView
from packages.research_reports.service import ResearchReportService


class ResearchGraphService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.checkpoint_repository = GraphCheckpointRepository(session=session)

    def analyze(self, request: GraphAnalyzeRequest) -> GraphAnalyzeResponse:
        return ResearchGraphRunner(
            self.session,
            checkpoint_repository=self.checkpoint_repository,
        ).run(request)

    def get_run(self, run_id: int) -> GraphAnalyzeResponse | None:
        run = self.session.get(Run, run_id)
        if run is None or not isinstance(run.output_json, dict):
            return None
        payload = dict(run.output_json)
        payload["checkpoint_history"] = [
            {
                "run_id": item["run_id"],
                "checkpoint_version": item.get("checkpoint_version"),
                "thread_id": item["thread_id"],
                "current_node": item.get("current_node"),
                "saved_at": item.get("saved_at"),
            }
            for item in self.checkpoint_repository.history(run_id=run_id)
        ]
        return GraphAnalyzeResponse.model_validate(payload)

    def get_run_dossier_text(self, run_id: int) -> str | None:
        result = self.get_run(run_id)
        if result is None or not result.dossier_path:
            return None
        path = Path(result.dossier_path)
        if not path.exists() or not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def get_run_report(self, run_id: int) -> ResearchReportView | None:
        result = self.get_run(run_id)
        if result is None:
            return None
        report_id = _extract_report_id(result.report_preview)
        if report_id is None:
            return None
        return ResearchReportService(self.session).get_report(report_id)

    def compact_checkpoints(
        self,
        run_id: int,
        *,
        keep_latest: int = 20,
    ) -> GraphCheckpointCompactionResult | None:
        if self.session.get(Run, run_id) is None:
            return None
        result = self.checkpoint_repository.compact(
            run_id=run_id,
            keep_latest=keep_latest,
        )
        if self.checkpoint_repository.load(run_id=run_id) is None:
            raise RuntimeError(f"Checkpoint compaction removed latest checkpoint for run {run_id}.")
        return GraphCheckpointCompactionResult.model_validate(result)

    def list_runs(self, *, limit: int = 20) -> list[GraphRunSummary]:
        return self.list_runs_filtered(limit=limit)

    def list_runs_filtered(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        resumed_only: bool = False,
    ) -> list[GraphRunSummary]:
        rows = (
            self.session.query(Run)
            .filter(Run.input_json.is_not(None))
            .order_by(Run.id.desc())
            .limit(limit)
            .all()
        )
        result: list[GraphRunSummary] = []
        for row in rows:
            input_json = row.input_json or {}
            output_json = row.output_json or {}
            if input_json.get("pipeline") != "langgraph_research_harness_v1":
                continue
            history = self.checkpoint_repository.history(run_id=row.id, limit=1)
            latest = history[0] if history else {}
            thread_id = str(
                output_json.get("thread_id") or input_json.get("thread_id") or ""
            )
            created_at = row.created_at.isoformat() if row.created_at is not None else None
            finished_at = row.finished_at.isoformat() if row.finished_at is not None else None
            resumed_from_checkpoint = bool(output_json.get("resumed_from_checkpoint", False))
            last_failed_node = _extract_last_failed_node(output_json)
            report_preview_summary = _extract_report_preview_summary(output_json)
            report_id = _extract_report_id(output_json.get("report_preview"))
            if status is not None and row.status.value != status:
                continue
            if resumed_only and not resumed_from_checkpoint:
                continue
            result.append(
                GraphRunSummary(
                    run_id=row.id,
                    thread_id=thread_id,
                    status=row.status.value,
                    decision=output_json.get("decision"),
                    resumed_from_checkpoint=resumed_from_checkpoint,
                    checkpoint_version=latest.get("checkpoint_version"),
                    checkpoint_saved_at=latest.get("saved_at"),
                    dossier_path=output_json.get("dossier_path"),
                    report_id=report_id,
                    gate_reason=output_json.get("report_preview", {}).get("gate_reason")
                    or output_json.get("gate_reason"),
                    last_failed_node=last_failed_node,
                    report_preview_summary=report_preview_summary,
                    created_at=created_at,
                    finished_at=finished_at,
                    pending_human_review=bool(
                        isinstance(output_json.get("human_review"), dict)
                        and output_json["human_review"].get("pending", False)
                    ),
                    task_refs=[
                        {
                            "task_id": task_job.id,
                            "status": task_job.status.value,
                            "attempt_count": task_job.attempt_count,
                            "idempotency_key": task_job.idempotency_key,
                        }
                        for task_job in row.task_jobs
                    ],
                )
            )
        return result

    def resume(
        self,
        run_id: int,
        *,
        query: str,
        max_rounds: int,
        max_loop_count: int,
        human_review_action: Literal["approve", "add_evidence", "rewrite", "reject"] | None = None,
        human_review_notes: str | None = None,
        execution_mode: Literal["shadow", "provider_backed"] = "shadow",
    ) -> GraphAnalyzeResponse:
        return self.analyze(
            GraphAnalyzeRequest(
                query=query,
                max_rounds=max_rounds,
                max_loop_count=max_loop_count,
                resume_run_id=run_id,
                human_review_action=human_review_action,
                human_review_notes=human_review_notes,
                execution_mode=execution_mode,
            )
        )


def _extract_last_failed_node(output_json: dict[str, object]) -> str | None:
    node_steps = output_json.get("node_steps")
    if not isinstance(node_steps, list):
        return None
    for step in reversed(node_steps):
        if isinstance(step, dict) and step.get("status") == "failed":
            node_name = step.get("node_name")
            return str(node_name) if node_name is not None else None
    return None


def _extract_report_preview_summary(output_json: dict[str, object]) -> str | None:
    report_preview = output_json.get("report_preview")
    if not isinstance(report_preview, dict):
        return None
    summary = report_preview.get("executive_summary")
    if summary is None:
        return None
    return str(summary)[:240]


def _extract_report_id(report_preview: object) -> int | None:
    if not isinstance(report_preview, dict):
        return None
    report_id = report_preview.get("report_id")
    try:
        value = int(report_id)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None
