from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.core.run_log import CompactRunLogger
from packages.db.models import (
    ContentAsset,
    DeliveryJob,
    Run,
    RunStatus,
    RunStep,
    RunType,
    StepStatus,
)
from packages.delivery.connectors import build_connector
from packages.delivery.enums import (
    DeliveryItemStatus,
    DeliveryJobStatus,
    DeliveryReviewStatus,
)
from packages.delivery.exporters import ExportBundleResult, LocalExportBundleWriter
from packages.delivery.repository import DeliveryRepository, job_to_view
from packages.delivery.review import (
    DeliveryStateError,
    derive_job_status_from_items,
    initial_review_state,
    validate_approve_transition,
    validate_dispatch_transition,
)
from packages.delivery.schemas import (
    DeliveryApprovalResponse,
    DeliveryDispatchResponse,
    DeliveryJobCreateRequest,
    DeliveryJobCreateResponse,
    DeliveryJobView,
    DispatchReceiptItem,
)
from packages.policy.schemas import DeliveryPolicyResult
from packages.policy.service import PolicyChecker

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc


class DeliveryServiceError(Exception):
    """Domain-level delivery workflow error."""


class DeliveryService:
    # TODO: Integrate real connectors for WeChat/XHS/Douyin through provider credentials.
    # TODO: Add scheduling, retry policy, and rate limiting policies for delivery queues.
    # TODO: Attach attribution analytics back into memory and growth optimization loops.

    def __init__(
        self,
        session: Session,
        *,
        repository: DeliveryRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or DeliveryRepository(session)
        self.settings = get_settings()
        self._run_logger: CompactRunLogger | None = None

    def create_job(self, request: DeliveryJobCreateRequest) -> DeliveryJobCreateResponse:
        run_logger = CompactRunLogger(task_name="delivery_create_job")
        run_logger.start(
            input_summary=request.model_dump(mode="json"),
            decision_summary=[
                "load requested content assets",
                "derive initial review/status state",
                "persist delivery job and item rows",
            ],
        )
        try:
            assets = self.repository.load_assets(request.content_asset_ids)
            if len(assets) != len(request.content_asset_ids):
                found = {asset.id for asset in assets}
                missing = sorted(set(request.content_asset_ids) - found)
                raise DeliveryServiceError(f"Unknown content_asset_ids: {missing}")

            status, review_status = initial_review_state(require_review=request.require_review)
            job = self.repository.create_job(
                source_run_id=request.source_run_id,
                status=status,
                delivery_target=request.delivery_target,
                review_status=review_status,
                mode=request.mode,
                requested_by=request.requested_by,
                metadata_json=request.metadata_json,
                content_assets=assets,
            )
            response = DeliveryJobCreateResponse(
                delivery_job_id=job.id,
                item_count=len(job.items),
                status=job.status,
                review_status=job.review_status,
            )
            run_logger.finish(status=response.status.value, output_summary=response)
            return response
        except Exception as exc:
            run_logger.finish(status=RunStatus.FAILED.value, output_summary={"error": str(exc)})
            raise

    def approve_job(self, job_id: int) -> DeliveryApprovalResponse:
        run_logger = CompactRunLogger(task_name="delivery_approve_job", run_id=f"job-{job_id}")
        run_logger.start(
            input_summary={"delivery_job_id": job_id},
            decision_summary=[
                "load delivery job",
                "validate approve transition",
                "mark job ready for dispatch",
            ],
        )
        try:
            job = self.repository.get_job(job_id)
            if job is None:
                raise DeliveryServiceError(f"Delivery job {job_id} not found.")
            try:
                validate_approve_transition(status=job.status, review_status=job.review_status)
            except DeliveryStateError as exc:
                raise DeliveryServiceError(str(exc)) from exc

            job.review_status = DeliveryReviewStatus.APPROVED
            job.status = DeliveryJobStatus.READY
            self.session.add(job)
            self.session.commit()
            self.session.refresh(job)
            response = DeliveryApprovalResponse(
                delivery_job_id=job.id,
                status=job.status,
                review_status=job.review_status,
            )
            run_logger.finish(status=response.status.value, output_summary=response)
            return response
        except Exception as exc:
            run_logger.finish(status=RunStatus.FAILED.value, output_summary={"error": str(exc)})
            raise

    def dispatch_job(self, job_id: int) -> DeliveryDispatchResponse:
        job = self.repository.get_job(job_id)
        if job is None:
            raise DeliveryServiceError(f"Delivery job {job_id} not found.")
        try:
            validate_dispatch_transition(status=job.status, review_status=job.review_status)
        except DeliveryStateError as exc:
            raise DeliveryServiceError(str(exc)) from exc

        policy_result = self._evaluate_delivery_policy(job)
        if self.settings.delivery_enforce_policy_checks and not policy_result.passed:
            raise DeliveryServiceError(
                "Delivery blocked by policy checks for assets: "
                f"{policy_result.blocked_asset_ids}"
            )
        if not policy_result.passed:
            metadata_json = job.metadata_json if isinstance(job.metadata_json, dict) else {}
            metadata_json["policy_warnings"] = {
                "blocked_asset_ids": policy_result.blocked_asset_ids,
                "asset_reports": {
                    str(asset_id): report.model_dump(mode="json")
                    for asset_id, report in policy_result.asset_reports.items()
                },
            }
            job.metadata_json = metadata_json

        job.status = DeliveryJobStatus.DISPATCHING
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)

        run = self._create_delivery_run(job)
        self._run_logger = CompactRunLogger(task_name="delivery_dispatch", run_id=run.id)
        self._run_logger.start(
            input_summary=run.input_json,
            decision_summary=[
                "validate dispatch transition",
                "evaluate delivery policy",
                "export assets before connector dispatch",
                "derive final job status from item statuses",
            ],
        )
        try:
            export_result = self._export_job_assets(job=job, run=run)
            self._dispatch_items(job=job, run=run, export_result=export_result)

            item_statuses = [item.status for item in job.items]
            final_status = derive_job_status_from_items(item_statuses)
            job.status = final_status
            if final_status in {DeliveryJobStatus.DISPATCHED, DeliveryJobStatus.PARTIAL_FAILED}:
                job.dispatched_at = datetime.now(UTC)
            self.session.add(job)
            self.session.commit()

            run_status = (
                RunStatus.SUCCEEDED
                if final_status != DeliveryJobStatus.FAILED
                else RunStatus.FAILED
            )
            self._finish_run(
                run=run,
                status=run_status,
                output_json={
                    "delivery_job_id": job.id,
                    "status": final_status.value,
                    "item_statuses": [item.status.value for item in job.items],
                    "manifest_path": export_result.manifest_path,
                },
            )
            self.session.refresh(job)
            return self._build_dispatch_response(job)
        except Exception as exc:
            job.status = DeliveryJobStatus.FAILED
            self.session.add(job)
            self.session.commit()
            self._finish_run(
                run=run,
                status=RunStatus.FAILED,
                output_json={"delivery_job_id": job.id, "error": str(exc)},
            )
            raise DeliveryServiceError(str(exc)) from exc
        finally:
            self._run_logger = None

    def get_job(self, job_id: int) -> DeliveryJobView | None:
        job = self.repository.get_job(job_id)
        if job is None:
            return None
        return job_to_view(job)

    def list_by_asset(self, asset_id: int) -> list[DeliveryJobView]:
        jobs = self.repository.list_by_asset(asset_id)
        return [job_to_view(self.repository.get_job(job.id) or job) for job in jobs]

    def list_by_run(self, run_id: int) -> list[DeliveryJobView]:
        jobs = self.repository.list_by_source_run(run_id)
        return [job_to_view(self.repository.get_job(job.id) or job) for job in jobs]

    def _create_delivery_run(self, job: DeliveryJob) -> Run:
        run = Run(
            run_type=RunType.DELIVERY_DISPATCH,
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
            input_json={
                "pipeline": "delivery_dispatch_v1",
                "delivery_job_id": job.id,
                "delivery_target": job.delivery_target.value,
                "mode": job.mode.value,
                "item_count": len(job.items),
            },
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def _export_job_assets(self, *, job: DeliveryJob, run: Run) -> ExportBundleResult:
        step = self._start_step(
            run=run,
            step_name="export_bundle",
            agent_name="delivery-exporter",
            input_json={"delivery_job_id": job.id},
        )
        try:
            writer = LocalExportBundleWriter(self.settings.delivery_export_dir)
            result = writer.export_job(job)
            step.status = StepStatus.SUCCEEDED
            step.finished_at = datetime.now(UTC)
            step.output_json = {
                "job_dir": result.job_dir,
                "manifest_path": result.manifest_path,
                "artifact_count": len(result.artifacts),
            }
            self.session.add(step)
            self.session.commit()
            if self._run_logger is not None:
                self._run_logger.step(
                    step_name="export_bundle",
                    agent_name="delivery-exporter",
                    input_summary=step.input_json,
                    output_summary=step.output_json,
                    status=StepStatus.SUCCEEDED.value,
                )
            return result
        except Exception as exc:
            self._fail_step(step=step, error_message=str(exc))
            if self._run_logger is not None:
                self._run_logger.step(
                    step_name="export_bundle",
                    agent_name="delivery-exporter",
                    input_summary=step.input_json,
                    status=StepStatus.FAILED.value,
                    error=str(exc),
                )
            raise

    def _dispatch_items(
        self, *, job: DeliveryJob, run: Run, export_result: ExportBundleResult
    ) -> None:
        connector = build_connector(job.delivery_target)
        artifacts_by_item = {
            artifact.delivery_job_item_id: artifact for artifact in export_result.artifacts
        }

        for item in sorted(job.items, key=lambda row: row.id):
            step = self._start_step(
                run=run,
                step_name=f"dispatch_item_{item.id}",
                agent_name=connector.__class__.__name__,
                input_json={
                    "delivery_job_item_id": item.id,
                    "content_asset_id": item.content_asset_id,
                },
            )

            artifact = artifacts_by_item.get(item.id)
            if artifact is not None:
                item.exported_path = artifact.markdown_path

            try:
                receipt = connector.dispatch(
                    job=job,
                    item=item,
                    artifact=artifact,
                    export_result=export_result,
                )
                item.status = DeliveryItemStatus.DISPATCHED
                item.dispatched_ref = receipt.dispatched_ref
                item.metadata_json = receipt.metadata_json
                step.status = StepStatus.SUCCEEDED
                step.output_json = {
                    "delivery_job_item_id": item.id,
                    "dispatched_ref": receipt.dispatched_ref,
                    "metadata_json": receipt.metadata_json,
                }
            except Exception as exc:
                item.status = DeliveryItemStatus.FAILED
                item.metadata_json = {"error": str(exc)}
                step.status = StepStatus.FAILED
                step.error_message = str(exc)
                step.output_json = {"delivery_job_item_id": item.id, "error": str(exc)}

            step.finished_at = datetime.now(UTC)
            self.session.add(item)
            self.session.add(step)
            self.session.commit()
            if self._run_logger is not None:
                self._run_logger.step(
                    step_name=step.step_name,
                    agent_name=step.agent_name,
                    input_summary=step.input_json,
                    output_summary=step.output_json,
                    status=step.status.value,
                    error=step.error_message,
                )

    def _start_step(
        self,
        *,
        run: Run,
        step_name: str,
        agent_name: str,
        input_json: dict[str, Any] | None,
    ) -> RunStep:
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
        return step

    def _fail_step(self, *, step: RunStep, error_message: str) -> None:
        step.status = StepStatus.FAILED
        step.error_message = error_message
        step.finished_at = datetime.now(UTC)
        self.session.add(step)
        self.session.commit()

    def _finish_run(self, *, run: Run, status: RunStatus, output_json: dict[str, Any]) -> None:
        run.status = status
        run.finished_at = datetime.now(UTC)
        run.output_json = output_json
        self.session.add(run)
        self.session.commit()
        if self._run_logger is not None:
            self._run_logger.finish(status=status.value, output_summary=output_json)

    def _build_dispatch_response(self, job: DeliveryJob) -> DeliveryDispatchResponse:
        receipts = [
            DispatchReceiptItem(
                delivery_job_item_id=item.id,
                content_asset_id=item.content_asset_id,
                status=item.status,
                exported_path=item.exported_path,
                dispatched_ref=item.dispatched_ref,
                metadata_json=item.metadata_json,
            )
            for item in sorted(job.items, key=lambda row: row.id)
        ]
        return DeliveryDispatchResponse(
            delivery_job_id=job.id,
            status=job.status,
            review_status=job.review_status,
            receipts=receipts,
        )

    def _evaluate_delivery_policy(self, job: DeliveryJob) -> DeliveryPolicyResult:
        assets: list[ContentAsset] = []
        for item in job.items:
            if item.content_asset is not None:
                assets.append(item.content_asset)
        if not assets:
            return DeliveryPolicyResult(passed=True, blocked_asset_ids=[], asset_reports={})
        return PolicyChecker().check_delivery_assets(assets)
