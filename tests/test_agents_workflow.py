from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.agents.service import ResearchWorkflowService
from packages.agents.thesis_builder import ThesisBuilderAgent
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Document, Run, RunStep, SourceType
from packages.db.models.enums import RunStatus, StepStatus
from packages.db.session import reset_db_session_state
from packages.ingestion.service import IngestionService
from packages.sources.adapters import EIAAdapter
from packages.sources.enums import (
    AccessMethod,
    SourceCategory,
    ToolErrorCode,
    ToolStatus,
    TrustTier,
)
from packages.sources.schemas import (
    Citation,
    CitationLocator,
    DocumentSection,
    EvidenceItem,
    NormalizedDocument,
    RawDocument,
    RoutingRecommendation,
    SourceAccess,
    SourceCapabilities,
    SourceProfile,
    ToolError,
    ToolResponse,
    ToolTrace,
)


def _setup_research_db(monkeypatch, tmp_path: Path) -> str:
    db_path = tmp_path / "research_workflow.db"
    raw_path = tmp_path / "raw"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str(raw_path.as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        first = IngestionService(session, max_chunk_chars=260).ingest_uploaded_file(
            file_name="battery.md",
            file_bytes=(
                b"# Battery Pricing\n\n## Signal\n"
                b"Lithium processing constraints keep contract prices elevated.\n\n"
                b"## Risk\nDemand slowdown can weaken orders."
            ),
            media_type="text/markdown",
            source_type=SourceType.REPORT,
        )
        second = IngestionService(session, max_chunk_chars=260).ingest_uploaded_file(
            file_name="supply_chain.md",
            file_bytes=(
                b"# Supply Chain Note\n\n## Signal\n"
                b"Refining utilization remains high and new capacity arrives slowly."
            ),
            media_type="text/markdown",
            source_type=SourceType.ARTICLE,
        )
        doc1 = session.get(Document, first.document_id)
        doc2 = session.get(Document, second.document_id)
        doc1.industry = "Energy Storage"
        doc2.industry = "Energy Storage"
        doc1.published_at = datetime(2026, 2, 18)
        doc2.published_at = datetime(2026, 1, 10)
        session.add_all([doc1, doc2])
        session.commit()

    return db_url


def test_multi_agent_workflow_success_and_run_trace(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_research_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        request = ResearchAnalyzeRequest(
            query="lithium pricing power",
            top_k=6,
            industry="Energy Storage",
            mode="mock",
        )
        result = ResearchWorkflowService(session).analyze(request)

        assert result.status == RunStatus.SUCCEEDED.value
        assert result.theses
        assert result.objections
        assert result.risks
        assert result.final_memo.key_theses
        assert all(thesis.evidence_refs for thesis in result.theses)
        assert result.evidence_judge.coverage
        assert result.source_acquisition is not None
        assert result.source_acquisition.enabled is False

        run = session.get(Run, result.run_id)
        steps = session.scalars(select(RunStep).where(RunStep.run_id == result.run_id)).all()

    assert run is not None
    assert run.status == RunStatus.SUCCEEDED
    assert {step.step_name for step in steps} >= {
        "retrieve_evidence",
        "build_evidence_bundle",
        "supervisor_intake",
        "thesis_builder",
        "opponent",
        "evidence_judge",
        "risk_analyst",
        "synthesize_memo",
    }
    assert {step.step_name for step in steps} >= {
        "source_route",
        "source_search",
        "source_fetch_detail",
        "source_extract_evidence",
        "source_build_bundle",
    }


def test_multi_agent_workflow_handles_no_evidence(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_research_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        result = ResearchWorkflowService(session).analyze(
            ResearchAnalyzeRequest(
                query="lithium pricing power",
                top_k=5,
                industry="Semiconductors",
                mode="mock",
            )
        )

        assert result.status == RunStatus.SUCCEEDED.value
        assert result.insufficient_evidence is True
        assert result.evidence_summary.selected_items == 0
        assert result.theses == []
        assert result.final_memo.evidence_gaps

        run = session.get(Run, result.run_id)
        skipped_steps = session.scalars(
            select(RunStep).where(
                RunStep.run_id == result.run_id,
                RunStep.status == StepStatus.SKIPPED,
            )
        ).all()

    assert run is not None
    assert run.status == RunStatus.SUCCEEDED
    assert {step.step_name for step in skipped_steps} >= {
        "thesis_builder",
        "opponent",
        "risk_analyst",
    }


def test_source_assisted_workflow_with_user_input(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_research_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        request = ResearchAnalyzeRequest(
            query="Assess lithium supply tightness from provided note",
            mode="mock",
            top_k=5,
            enable_source_acquisition=True,
            user_provided_sources=[
                {
                    "title": "Desk note",
                    "inline_text": (
                        "Refining utilization remains high and contract pricing is sticky."
                    ),
                }
            ],
        )
        result = ResearchWorkflowService(session).analyze(request)
        steps = session.scalars(select(RunStep).where(RunStep.run_id == result.run_id)).all()

    assert result.status == RunStatus.SUCCEEDED.value
    assert result.source_acquisition is not None
    assert result.source_acquisition.enabled is True
    assert "user_input" in result.source_acquisition.routed_sources
    assert result.source_acquisition.evidence_items_found >= 1
    assert result.source_acquisition.pdf_summary is not None
    assert result.source_acquisition.pdf_summary["enabled"] is False
    assert result.evidence_summary.selected_items >= 1
    assert {step.step_name for step in steps} >= {
        "source_route",
        "source_search",
        "source_fetch_detail",
        "source_extract_evidence",
        "source_build_bundle",
    }


def test_source_assisted_explicit_source_ids_no_results(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_research_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        result = ResearchWorkflowService(session).analyze(
            ResearchAnalyzeRequest(
                query="robotics revenue timeline",
                mode="mock",
                top_k=4,
                enable_source_acquisition=True,
                source_ids=["world_bank"],
                include_user_sources=False,
            )
        )

    assert result.status == RunStatus.SUCCEEDED.value
    assert result.insufficient_evidence is True
    assert result.theses == []
    assert result.source_acquisition is not None
    assert result.source_acquisition.enabled is True
    assert result.source_acquisition.routed_sources == ["world_bank"]
    assert result.source_acquisition.evidence_items_found == 0


def test_source_assisted_partial_failure_still_succeeds(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_research_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    def _fail_search(self, request):  # noqa: ANN001
        return self.error_response(
            request,
            code=ToolErrorCode.INTERNAL_ERROR,
            message="simulated eia failure",
            retryable=True,
        )

    monkeypatch.setattr(EIAAdapter, "search_documents", _fail_search)

    with Session(engine) as session:
        result = ResearchWorkflowService(session).analyze(
            ResearchAnalyzeRequest(
                query="assess with mixed sources",
                mode="mock",
                top_k=4,
                enable_source_acquisition=True,
                source_ids=["eia", "user_input"],
                include_user_sources=True,
                user_provided_sources=[
                    {
                        "title": "Desk note",
                        "inline_text": "Supply constraints remain elevated.",
                    }
                ],
            )
        )

    assert result.status == RunStatus.SUCCEEDED.value
    assert result.source_acquisition is not None
    assert result.source_acquisition.enabled is True
    assert set(result.source_acquisition.routed_sources) == {"eia", "user_input"}
    assert result.source_acquisition.evidence_items_found >= 1
    assert result.source_acquisition.source_quality_summary is not None
    assert result.source_acquisition.source_quality_summary["sources_failed"] >= 1


def test_research_request_accepts_pdf_fields() -> None:
    request = ResearchAnalyzeRequest(
        query="policy evidence",
        mode="mock",
        enable_source_acquisition=True,
        enable_pdf_processing=True,
        max_pdf_attachments_per_source=3,
        max_pdf_pages_per_attachment=15,
    )
    assert request.enable_pdf_processing is True
    assert request.max_pdf_attachments_per_source == 3
    assert request.max_pdf_pages_per_attachment == 15


def _install_fake_pdf_source_service(monkeypatch, *, with_pdf_error: bool) -> None:
    profile = SourceProfile(
        source_id="cn_policy_ndrc_tzgg_v1",
        display_name="NDRC Notices",
        category=SourceCategory.POLICY_PORTAL,
        trust_tier=TrustTier.PRIMARY_OFFICIAL,
        enabled=True,
        access=SourceAccess(access_method=AccessMethod.WEB, auth_required=False),
        capabilities=SourceCapabilities(
            supports_search=True,
            supports_document_detail=True,
            supports_evidence_extraction=True,
            supports_time_filter=True,
            supports_keyword_filter=True,
            supports_bulk=False,
        ),
    )

    class _FakeAdapter:
        def get_profile(self):
            return profile

        def search_documents(self, request):  # noqa: ANN001
            _ = request.payload
            return ToolResponse(
                status=ToolStatus.SUCCESS,
                tool_name=request.tool_name,
                source_id=profile.source_id,
                documents=[
                    RawDocument(
                        document_id="doc_1",
                        source_id=profile.source_id,
                        title="政策通知示例",
                        source_uri="https://example.cn/doc_1",
                    )
                ],
                trace=ToolTrace(
                    tool_name=request.tool_name,
                    source_id=profile.source_id,
                    status=ToolStatus.SUCCESS,
                ),
            )

        def fetch_document_detail(self, request):  # noqa: ANN001
            _ = request.payload
            errors = []
            if with_pdf_error:
                errors.append(
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message=(
                            "PDF text extraction failed for "
                            "'https://example.cn/a.pdf': invalid_pdf"
                        ),
                        retryable=False,
                    )
                )
            return ToolResponse(
                status=ToolStatus.SUCCESS,
                tool_name=request.tool_name,
                source_id=profile.source_id,
                documents=[
                    RawDocument(
                        document_id="doc_1",
                        source_id=profile.source_id,
                        title="政策通知示例",
                        source_uri="https://example.cn/doc_1",
                    )
                ],
                normalized_documents=[
                    NormalizedDocument(
                        document_id="doc_1",
                        source_id=profile.source_id,
                        title="政策通知示例",
                        sections=[
                            DocumentSection(
                                section_id="main",
                                heading="main",
                                text="正文摘要",
                            )
                        ],
                    )
                ],
                errors=errors,
                trace=ToolTrace(
                    tool_name=request.tool_name,
                    source_id=profile.source_id,
                    status=ToolStatus.SUCCESS,
                    metadata={
                        "attachment_count": 2,
                        "pdf_processing": {
                            "enabled": True,
                            "processed_attachments": 1,
                            "pages_extracted": 2,
                            "truncated": False,
                        },
                    },
                ),
            )

        def extract_evidence_items(self, request):  # noqa: ANN001
            _ = request.payload
            return ToolResponse(
                status=ToolStatus.SUCCESS,
                tool_name=request.tool_name,
                source_id=profile.source_id,
                evidence_items=[
                    EvidenceItem(
                        evidence_id="evi_1",
                        source_id=profile.source_id,
                        title="政策通知示例",
                        support_text="附件第1页证据",
                        score=0.8,
                        citation=Citation(
                            citation_id="cit_1",
                            source_id=profile.source_id,
                            document_id="doc_pdf_1",
                            locator=CitationLocator(
                                document_id="doc_pdf_1",
                                page_number=1,
                                external_ref="attachment.pdf",
                            ),
                            quote_text="附件第1页证据",
                            source_uri="https://example.cn/a.pdf",
                        ),
                        metadata={"from_pdf_attachment": True},
                    )
                ],
                trace=ToolTrace(
                    tool_name=request.tool_name,
                    source_id=profile.source_id,
                    status=ToolStatus.SUCCESS,
                ),
            )

    class _FakeRegistry:
        def __init__(self):
            self._adapter = _FakeAdapter()

        def get_adapter(self, source_id):  # noqa: ANN001
            if source_id == profile.source_id:
                return self._adapter
            return None

        def get_profile(self, source_id, enabled_only=False):  # noqa: ANN001
            if source_id == profile.source_id:
                return profile
            return None

    class _FakeSourceService:
        def __init__(self, *args, **kwargs):  # noqa: ANN003
            self.source_registry = _FakeRegistry()

        def route_sources(self, query_context):  # noqa: ANN001
            _ = query_context
            return [
                RoutingRecommendation(
                    source_id=profile.source_id,
                    reason="fake route",
                    priority=95,
                    final_score=95.0,
                    score_breakdown={"rule_match_score": 95.0},
                )
            ]

    monkeypatch.setattr("packages.agents.workflow.SourceIntelligenceService", _FakeSourceService)


def test_source_assisted_workflow_with_pdf_enabled_audit(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_research_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    _install_fake_pdf_source_service(monkeypatch, with_pdf_error=False)

    with Session(engine) as session:
        result = ResearchWorkflowService(session).analyze(
            ResearchAnalyzeRequest(
                query="政策附件证据",
                mode="mock",
                top_k=5,
                enable_source_acquisition=True,
                enable_pdf_processing=True,
                max_pdf_attachments_per_source=2,
                max_pdf_pages_per_attachment=10,
            )
        )
        steps = session.scalars(select(RunStep).where(RunStep.run_id == result.run_id)).all()

    assert result.status == RunStatus.SUCCEEDED.value
    assert result.source_acquisition is not None
    assert result.source_acquisition.pdf_summary is not None
    pdf_summary = result.source_acquisition.pdf_summary
    assert pdf_summary["enabled"] is True
    assert pdf_summary["attachments_discovered"] >= 1
    assert pdf_summary["attachments_processed"] >= 1
    assert pdf_summary["pdf_evidence_items_found"] >= 1
    assert {step.step_name for step in steps} >= {
        "pdf_discover_attachments",
        "pdf_download",
        "pdf_extract",
        "pdf_extract_evidence",
    }


def test_source_assisted_workflow_pdf_partial_failure_is_graceful(
    monkeypatch, tmp_path: Path
) -> None:
    db_url = _setup_research_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    _install_fake_pdf_source_service(monkeypatch, with_pdf_error=True)

    with Session(engine) as session:
        result = ResearchWorkflowService(session).analyze(
            ResearchAnalyzeRequest(
                query="政策附件证据",
                mode="mock",
                top_k=5,
                enable_source_acquisition=True,
                enable_pdf_processing=True,
            )
        )

    assert result.status == RunStatus.SUCCEEDED.value
    assert result.source_acquisition is not None
    pdf_summary = result.source_acquisition.pdf_summary or {}
    assert pdf_summary.get("enabled") is True
    assert pdf_summary.get("errors")
    assert result.source_acquisition.evidence_items_found >= 1


def test_multi_agent_workflow_failure_path_records_failed_run(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_research_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    def _explode(*args, **kwargs):
        raise RuntimeError("forced-thesis-failure")

    monkeypatch.setattr(ThesisBuilderAgent, "run", _explode)

    with Session(engine) as session:
        result = ResearchWorkflowService(session).analyze(
            ResearchAnalyzeRequest(
                query="lithium pricing power",
                top_k=6,
                industry="Energy Storage",
                mode="mock",
            )
        )
        failed_run = session.get(Run, result.run_id)
        failed_step = session.scalar(
            select(RunStep).where(
                RunStep.run_id == result.run_id,
                RunStep.step_name == "thesis_builder",
                RunStep.status == StepStatus.FAILED,
            )
        )

    assert result.status == RunStatus.FAILED.value
    assert result.error_message is not None
    assert "forced-thesis-failure" in result.error_message
    assert failed_run is not None
    assert failed_run.status == RunStatus.FAILED
    assert failed_step is not None
