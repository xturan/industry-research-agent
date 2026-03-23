from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.agents.service import ResearchWorkflowService
from packages.content.schemas import ContentFormat, ContentGenerateRequest
from packages.content.service import ContentFactoryService
from packages.db.models import SourceType
from packages.delivery.enums import DeliveryTarget
from packages.delivery.schemas import DeliveryJobCreateRequest
from packages.delivery.service import DeliveryService
from packages.evals.datasets import SMOKE_SAMPLE_FILE_PATH
from packages.evals.graders import (
    grade_content_outputs,
    grade_evidence_bundle,
    grade_rag_chunks,
    grade_research_output,
    grade_task_delivery_flow,
)
from packages.evals.schemas import EvalCaseResult, EvalSummary, SmokeEvalRequest
from packages.ingestion.service import IngestionService
from packages.rag.bundle import EvidenceBundleBuilder
from packages.rag.retrieval import ChunkRetrievalService


class SmokeEvalRunner:
    def __init__(self, session: Session) -> None:
        self.session = session

    def run(
        self, request: SmokeEvalRequest
    ) -> tuple[EvalSummary, list[EvalCaseResult], dict[str, Any]]:
        artifacts: dict[str, Any] = {}

        if request.bootstrap_sample:
            sample_path = Path(SMOKE_SAMPLE_FILE_PATH)
            if sample_path.exists():
                IngestionService(self.session).ingest_local_file(
                    sample_path,
                    source_type=SourceType.REPORT,
                )

        retrieval_filters = ResearchAnalyzeRequest(
            query=request.query,
            top_k=request.top_k,
        ).to_retrieval_filters()
        retrieval = ChunkRetrievalService(self.session).search_chunks(
            request.query,
            filters=retrieval_filters,
        )
        chunks_payload = retrieval.to_dict()
        artifacts["rag_chunks"] = chunks_payload
        cases = grade_rag_chunks(chunks_payload)

        bundle = EvidenceBundleBuilder().build_bundle(
            retrieval,
            group_by_document=True,
            max_items=request.top_k,
        )
        bundle_payload = bundle.to_dict()
        artifacts["evidence_bundle"] = bundle_payload
        cases.extend(grade_evidence_bundle(bundle_payload))

        research_result = ResearchWorkflowService(self.session).analyze(
            ResearchAnalyzeRequest(
                query=request.query,
                top_k=request.top_k,
                mode=request.research_mode,
            )
        )
        research_payload = research_result.model_dump(mode="json")
        artifacts["research"] = research_payload
        cases.extend(grade_research_output(research_payload))

        content_result = ContentFactoryService(self.session).generate(
            ContentGenerateRequest(
                research_run_id=research_result.run_id,
                content_types=[
                    ContentFormat.WECHAT_ARTICLE,
                    ContentFormat.XIAOHONGSHU_POST,
                    ContentFormat.DOUYIN_SCRIPT,
                ],
                mode=request.content_mode,
            )
        )
        content_assets = []
        content_service = ContentFactoryService(self.session)
        for item in content_result.assets:
            view = content_service.get_asset(item.asset_id)
            if view is not None:
                content_assets.append(view.model_dump(mode="json"))
        artifacts["content_assets"] = content_assets
        cases.extend(grade_content_outputs(content_assets))

        delivery_response = {"status": "skipped"}
        if len(content_result.assets) >= 2:
            job = DeliveryService(self.session).create_job(
                DeliveryJobCreateRequest(
                    content_asset_ids=[
                        content_result.assets[0].asset_id,
                        content_result.assets[1].asset_id,
                    ],
                    delivery_target=DeliveryTarget.EXPORT_BUNDLE,
                    mode="mock",
                    require_review=False,
                    source_run_id=research_result.run_id,
                )
            )
            dispatch = DeliveryService(self.session).dispatch_job(job.delivery_job_id)
            delivery_response = dispatch.model_dump(mode="json")
            cases.extend(
                grade_task_delivery_flow(
                    {"status": "succeeded", "result_json": delivery_response},
                )
            )
        artifacts["delivery"] = delivery_response

        passed_count = sum(1 for item in cases if item.passed)
        score = round((sum(item.score for item in cases) / len(cases)) if cases else 0.0, 4)
        issues = [item.case_name for item in cases if not item.passed]
        summary = EvalSummary(
            passed=passed_count == len(cases) if cases else False,
            score=score,
            issue_count=len(issues),
            issues=issues,
            case_count=len(cases),
            passed_count=passed_count,
        )
        return summary, cases, artifacts
