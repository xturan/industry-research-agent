from __future__ import annotations

from packages.sources.adapters.base import BaseSourceAdapter
from packages.sources.collectors import PdfTextDocument, PdfTextPage
from packages.sources.crawl4ai_extraction import Crawl4AIExtractionResponse
from packages.sources.enums import (
    AccessMethod,
    GovernanceAxis,
    InfoType,
    LineFamily,
    PublisherType,
    RegionalLevel,
    SourceCategory,
    SourceRole,
    ToolStatus,
    TrustTier,
)
from packages.sources.lane_execution import (
    DirectStructuredLaneExecutor,
    _direct_document_evidence_quality,
    _domain_allowed_for_official_record_search,
    _weak_direct_document_reason,
)
from packages.sources.live_pdf import LivePdfDownloadError
from packages.sources.query_decomposition import QueryDecompositionTask
from packages.sources.registry import SourceRegistry
from packages.sources.schemas import (
    DocumentSection,
    NormalizedDocument,
    RawDocument,
    SourceAccess,
    SourceCapabilities,
    SourceProfile,
    ToolRequest,
    ToolResponse,
)
from packages.sources.search_discovery import (
    TavilySearchResponse,
    TavilySearchResult,
    TavilyUsageMetadata,
)
from packages.sources.source_family_backbone import SourceFamilyBackbone


class _FakeProfileAdapter(BaseSourceAdapter):
    def __init__(
        self,
        profile: SourceProfile,
        *,
        document_title: str = "direct doc",
        source_uri: str | None = None,
        raw_text: str = "direct lane document body",
    ) -> None:
        self.profile = profile
        self.document_title = document_title
        self.source_uri = source_uri
        self.raw_text = raw_text
        self.search_calls: list[ToolRequest] = []

    def get_profile(self) -> SourceProfile:
        return self.profile

    def search_documents(self, request: ToolRequest) -> ToolResponse:
        self.search_calls.append(request)
        raw = RawDocument(
            document_id=f"{self.profile.source_id}_doc_1",
            source_id=self.profile.source_id,
            title=self.document_title,
            source_uri=self.source_uri or f"https://example.com/{self.profile.source_id}/doc/1",
            raw_text=self.raw_text,
        )
        normalized = NormalizedDocument(
            document_id=raw.document_id,
            source_id=self.profile.source_id,
            title=self.document_title,
            summary=self.raw_text,
            sections=[
                DocumentSection(
                    section_id=f"{raw.document_id}_sec_1",
                    heading="section",
                    text=self.raw_text,
                )
            ],
        )
        return ToolResponse(
            status=ToolStatus.SUCCESS,
            tool_name=request.tool_name,
            source_id=self.profile.source_id,
            documents=[raw],
            normalized_documents=[normalized],
        )

    def fetch_document_detail(self, request: ToolRequest) -> ToolResponse:
        return self.not_implemented(request, "fetch_document_detail")

    def extract_evidence_items(self, request: ToolRequest) -> ToolResponse:
        return self.not_implemented(request, "extract_evidence_items")


def test_official_record_domain_allowlist_does_not_expand_gov_cn_to_all_local_gov() -> None:
    assert not _domain_allowed_for_official_record_search(
        "jiaxiang.gov.cn",
        ["gov.cn", "zrzyt.ah.gov.cn", "sthjj.hefei.gov.cn"],
    )
    assert _domain_allowed_for_official_record_search(
        "www.gov.cn",
        ["gov.cn", "zrzyt.ah.gov.cn", "sthjj.hefei.gov.cn"],
    )
    assert _domain_allowed_for_official_record_search(
        "zrzyt.ah.gov.cn",
        ["gov.cn", "zrzyt.ah.gov.cn", "sthjj.hefei.gov.cn"],
    )


class _FakeProjectSearchProvider:
    def __init__(self, *, result: TavilySearchResult | None = None) -> None:
        self.requests = []
        self.result = result or TavilySearchResult(
            title="西安商业航天重大项目开工",
            url="https://xian.gov.cn/project/space-1.html",
            content="西安 商业航天 硬科技 项目 开工 建设",
            score=0.91,
            published_date="2026-04-01",
        )

    def search(self, request):
        self.requests.append(request)
        return TavilySearchResponse(
            status=ToolStatus.SUCCESS,
            query=request.query,
            results=[self.result],
            usage=TavilyUsageMetadata(
                search_depth="basic",
                max_results=request.max_results or 5,
                estimated_credits=1,
                result_count=1,
            ),
        )

    def search_task(self, task):  # noqa: ANN001
        return [self.search(request) for request in task.search_phrases]


class _FakeProjectExtractionProvider:
    def __init__(self) -> None:
        self.requests = []

    def extract(self, request):
        self.requests.append(request)
        item = request.inputs[0]
        raw = RawDocument(
            document_id="project_fallback_doc_1",
            source_id=item.source_id,
            title=item.title_hint or "project fallback",
            source_uri=item.url,
            raw_text="西安 商业航天 硬科技 项目 开工 建设",
        )
        normalized = NormalizedDocument(
            document_id=raw.document_id,
            source_id=raw.source_id,
            title=raw.title,
            summary=raw.raw_text,
            sections=[
                DocumentSection(
                    section_id="project_fallback_doc_1_sec_1",
                    heading=raw.title,
                    text=raw.raw_text or "",
                )
            ],
        )
        return Crawl4AIExtractionResponse(
            status=ToolStatus.SUCCESS,
            documents=[raw],
            normalized_documents=[normalized],
            metadata={"provider": "fake_crawl4ai", "requested": 1, "succeeded": 1},
        )


class _FakeProjectExtractionProviderWithHintOnlyPage:
    def __init__(self) -> None:
        self.requests = []

    def extract(self, request):
        self.requests.append(request)
        item = request.inputs[0]
        raw = RawDocument(
            document_id="project_hint_doc_1",
            source_id=item.source_id,
            title="detail.shtml",
            source_uri=item.url,
            raw_text="全国公共资源交易平台",
            metadata={
                "title_hint": item.title_hint,
                "snippet_hint": item.snippet_hint,
                "discovery_query": item.discovery_query,
            },
        )
        normalized = NormalizedDocument(
            document_id=raw.document_id,
            source_id=raw.source_id,
            title=raw.title,
            summary=raw.raw_text,
            sections=[
                DocumentSection(
                    section_id="project_hint_doc_1_sec_1",
                    heading=raw.title,
                    text=raw.raw_text or "",
                )
            ],
            metadata=raw.metadata,
        )
        return Crawl4AIExtractionResponse(
            status=ToolStatus.SUCCESS,
            documents=[raw],
            normalized_documents=[normalized],
            metadata={"provider": "fake_crawl4ai", "requested": 1, "succeeded": 1},
        )


class _FakeDataMetricsSearchProvider:
    def __init__(self, *, result: TavilySearchResult | None = None) -> None:
        self.requests = []
        self.result = result or TavilySearchResult(
            title="安徽省新能源汽车产量数据发布",
            url="https://tjj.ah.gov.cn/data/nev-output.html",
            content="安徽 新能源汽车 产量 数据 统计",
            score=0.9,
            published_date="2026-03-01",
        )

    def search(self, request):
        self.requests.append(request)
        return TavilySearchResponse(
            status=ToolStatus.SUCCESS,
            query=request.query,
            results=[self.result],
            usage=TavilyUsageMetadata(
                search_depth="basic",
                max_results=request.max_results or 5,
                estimated_credits=1,
                result_count=1,
            ),
        )

    def search_task(self, task):  # noqa: ANN001
        return [self.search(request) for request in task.search_phrases]


class _FakeDataMetricsExtractionProviderWithHintOnlyPage:
    def __init__(self) -> None:
        self.requests = []

    def extract(self, request):
        self.requests.append(request)
        item = request.inputs[0]
        raw = RawDocument(
            document_id="data_metrics_hint_doc_1",
            source_id=item.source_id,
            title="data.html",
            source_uri=item.url,
            raw_text="统计数据发布页面",
            metadata={
                "title_hint": item.title_hint,
                "snippet_hint": item.snippet_hint,
                "discovery_query": item.discovery_query,
            },
        )
        normalized = NormalizedDocument(
            document_id=raw.document_id,
            source_id=raw.source_id,
            title=raw.title,
            summary=raw.raw_text,
            sections=[
                DocumentSection(
                    section_id="data_metrics_hint_doc_1_sec_1",
                    heading=raw.title,
                    text=raw.raw_text or "",
                )
            ],
            metadata=raw.metadata,
        )
        return Crawl4AIExtractionResponse(
            status=ToolStatus.SUCCESS,
            documents=[raw],
            normalized_documents=[normalized],
            metadata={"provider": "fake_crawl4ai", "requested": 1, "succeeded": 1},
        )


class _FakeOfficialRecordSearchProvider:
    def __init__(
        self,
        *,
        result: TavilySearchResult | None = None,
        results: list[TavilySearchResult] | None = None,
    ) -> None:
        self.requests = []
        default_result = result or TavilySearchResult(
            title="神木煤化工项目环境影响评价公示",
            url="https://sxsm.gov.cn/zwgk/hpgs/coal-chemical-eia.html",
            content="神木 煤化工 环评 环境影响评价 公示 项目备案",
            score=0.92,
            published_date="2026-03-10",
        )
        self.results = results or [default_result]

    def search(self, request):
        self.requests.append(request)
        return TavilySearchResponse(
            status=ToolStatus.SUCCESS,
            query=request.query,
            results=self.results,
            usage=TavilyUsageMetadata(
                search_depth="basic",
                max_results=request.max_results or 5,
                estimated_credits=1,
                result_count=len(self.results),
            ),
        )

    def search_task(self, task):  # noqa: ANN001
        return [self.search(request) for request in task.search_phrases]


class _SequentialOfficialRecordSearchProvider:
    def __init__(self, results_by_call: list[list[TavilySearchResult]]) -> None:
        self.requests = []
        self.results_by_call = results_by_call

    def search(self, request):
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self.results_by_call) - 1)
        results = self.results_by_call[index]
        return TavilySearchResponse(
            status=ToolStatus.SUCCESS,
            query=request.query,
            results=results,
            usage=TavilyUsageMetadata(
                search_depth="basic",
                max_results=request.max_results or 5,
                estimated_credits=1,
                result_count=len(results),
            ),
        )

    def search_task(self, task):  # noqa: ANN001
        return [self.search(request) for request in task.search_phrases]


class _FakeOfficialRecordExtractionProviderWithHintOnlyPage:
    def __init__(self, *, raw_text: str = "政府信息公开页面") -> None:
        self.requests = []
        self.raw_text = raw_text

    def extract(self, request):
        self.requests.append(request)
        item = request.inputs[0]
        raw = RawDocument(
            document_id="official_record_hint_doc_1",
            source_id=item.source_id,
            title="record.html",
            source_uri=item.url,
            raw_text=self.raw_text,
            metadata={
                "title_hint": item.title_hint,
                "snippet_hint": item.snippet_hint,
                "discovery_query": item.discovery_query,
            },
        )
        normalized = NormalizedDocument(
            document_id=raw.document_id,
            source_id=raw.source_id,
            title=raw.title,
            summary=raw.raw_text,
            sections=[
                DocumentSection(
                    section_id="official_record_hint_doc_1_sec_1",
                    heading=raw.title,
                    text=raw.raw_text or "",
                )
            ],
            metadata=raw.metadata,
        )
        return Crawl4AIExtractionResponse(
            status=ToolStatus.SUCCESS,
            documents=[raw],
            normalized_documents=[normalized],
            metadata={"provider": "fake_crawl4ai", "requested": 1, "succeeded": 1},
        )


class _FakeOfficialRecordPdfDownloadService:
    def __init__(self) -> None:
        self.calls = []

    def download_pdf(self, url, **kwargs):  # noqa: ANN001, ANN201
        self.calls.append({"url": url, **kwargs})

        class _Result:
            final_url = url
            file_path = "tests/fixtures/sources/sample_attachment.pdf"
            warnings = []
            retry_count = 0

            def to_dict(self) -> dict:
                return {
                    "url": url,
                    "final_url": url,
                    "file_path": self.file_path,
                    "warnings": self.warnings,
                    "retry_count": self.retry_count,
                }

        return _Result()


class _FailingOfficialRecordPdfDownloadService:
    def download_pdf(self, url, **kwargs):  # noqa: ANN001, ANN201, ARG002
        raise LivePdfDownloadError(
            "timeout while downloading official-record PDF",
            url=url,
            retryable=True,
            status_code=None,
            attempts=2,
            retry_count=1,
            latency_ms=1200.0,
            detail={"stage": "download"},
        )


class _FakeOfficialRecordPdfTextService:
    def __init__(self, page_text: str | None = None) -> None:
        self.calls = []
        self.page_text = page_text or (
            "\u82e5\u7f8c \u76d0\u6e56\u9502\u94be "
            "\u9879\u76ee \u73af\u5883\u5f71\u54cd\u8bc4\u4ef7 "
            "\u516c\u793a \u77ff\u4ea7\u8d44\u6e90 \u5907\u6848"
        )

    def extract_from_file(self, *, file_path, source_id, artifact, title=None, **kwargs):  # noqa: ANN001, ANN201
        self.calls.append(
            {
                "file_path": file_path,
                "source_id": source_id,
                "artifact": artifact,
                "title": title,
                **kwargs,
            }
        )
        return PdfTextDocument(
            artifact_id=artifact.artifact_id,
            source_id=source_id,
            title=title,
            url=artifact.url,
            pages=[
                PdfTextPage(
                    page_number=1,
                    text=self.page_text,
                )
            ],
            metadata=kwargs.get("metadata") or {},
        )


class _FakeDisclosureApiProvider:
    def __init__(self) -> None:
        self.requests = []

    def search(self, *, task, spec, max_results):  # noqa: ANN001
        self.requests.append({"task": task, "spec": spec, "max_results": max_results})
        raw = RawDocument(
            document_id="cninfo_direct_000099_1",
            source_id="cn_exchange_cninfo_announcement_v1",
            title="中信海直：2025年年度报告",
            source_uri="https://static.cninfo.com.cn/finalpage/2026-03-17/1225012497.PDF",
            published_at="2026-03-17",
            raw_text="中信海直 000099 2025年年度报告 公司持续推进低空经济相关业务。",
            metadata={
                "disclosure_search_spec": spec.to_dict(),
                "source_class": "company_disclosure",
            },
        )
        normalized = NormalizedDocument(
            document_id=raw.document_id,
            source_id=raw.source_id,
            title=raw.title,
            summary=raw.raw_text,
            published_at=raw.published_at,
            sections=[
                DocumentSection(
                    section_id=f"{raw.document_id}_sec_1",
                    heading=raw.title,
                    text=raw.raw_text or "",
                    metadata={
                        "requested_url": raw.source_uri,
                        "final_url": raw.source_uri,
                    },
                )
            ],
            metadata={
                **raw.metadata,
                "requested_url": raw.source_uri,
                "final_url": raw.source_uri,
            },
        )
        return [raw], [normalized], [], {
            "attempted": True,
            "provider": "cninfo_direct_api",
            "status": "evidence_found",
            "document_count": 1,
            "normalized_document_count": 1,
            "estimated_tavily_credits": 0,
        }


def _profile(
    source_id: str,
    *,
    category: SourceCategory,
    line_family: LineFamily,
    info_type: InfoType,
    regional_level: RegionalLevel = RegionalLevel.NATIONAL,
) -> SourceProfile:
    return SourceProfile(
        source_id=source_id,
        display_name=source_id,
        category=category,
        trust_tier=TrustTier.PRIMARY_OFFICIAL,
        access=SourceAccess(access_method=AccessMethod.WEB, base_url="https://example.com"),
        capabilities=SourceCapabilities(supports_search=True),
        profile_family="test",
        governance_axis=GovernanceAxis.LINE,
        line_family=line_family,
        regional_level=regional_level,
        info_type=info_type,
        publisher_type=PublisherType.INSTITUTION,
        source_role=SourceRole.PRIMARY,
    )


def _registry_with(*adapters: _FakeProfileAdapter) -> SourceRegistry:
    registry = SourceRegistry()
    for adapter in adapters:
        registry.register(adapter)
    return registry


def _task(
    task_family: str,
    *,
    search_phrases: list[str] | None = None,
    include_domains: list[str] | None = None,
) -> QueryDecompositionTask:
    return QueryDecompositionTask(
        task_id=f"{task_family}_1",
        task_family=task_family,
        tiaokuai_axis=GovernanceAxis.MIXED,
        line_family=LineFamily.CROSS_DOMAIN,
        regional_level=RegionalLevel.CROSS_REGION,
        info_type=(
            InfoType.REGULATORY_ANNOUNCEMENT
            if task_family == "enterprise_disclosure"
            else InfoType.REGULATORY_ANNOUNCEMENT
            if task_family == "official_record"
            else InfoType.PROJECT_TRANSACTION
            if task_family == "project_transaction"
            else InfoType.INDUSTRY_NOTICE
        ),
        execution_bucket="direct_structured_sources",
        source_cluster=(
            "official_disclosure_backbone"
            if task_family == "enterprise_disclosure"
            else "official_record_backbone"
            if task_family == "official_record"
            else "project_transaction_backbone"
            if task_family == "project_transaction"
            else "structured_data_backbone"
        ),
        source_strategy_hint="test_direct_lane",
        include_domains=include_domains or [],
        exclude_domains=[],
        search_phrases=search_phrases or ["test direct lane"],
        exact_phrases=[],
        negative_terms=[],
        evidence_goal="test direct lane execution",
        fallback_path="test fallback",
    )


def test_direct_executor_dispatches_project_lane_to_available_profiles() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        )
    )
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        max_profiles_per_lane=2,
        max_documents_per_profile=1,
    ).execute_task(_task("project_transaction"))

    assert result.execution_state == "executed_with_evidence"
    assert result.source_ids_selected == ["cn_project_ccgp_procurement_v1"]
    assert result.document_count == 1
    assert result.normalized_document_count == 1
    assert result.metadata["lane_id"] == "project_transaction"
    assert ccgp.search_calls[0].query_context.query == "test direct lane"


def test_project_lane_rejects_generic_homepage_documents_as_no_evidence() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="首页",
    )
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(_task("project_transaction", search_phrases=["西安 商业航天 项目"]))

    assert result.execution_state == "executed_without_evidence"
    assert result.document_count == 0
    assert result.metadata["rejected_document_count"] == 1
    assert result.metadata["weak_document_rejections"][0]["reason_code"] == (
        "generic_project_navigation"
    )


def test_project_lane_rejects_irrelevant_project_documents() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="厦门税务系统中标公告",
    )
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(_task("project_transaction", search_phrases=["西安 商业航天 项目"]))

    assert result.execution_state == "executed_without_evidence"
    assert result.document_count == 0
    assert result.metadata["rejected_document_count"] == 1
    assert result.metadata["weak_document_rejections"][0]["reason_code"] == (
        "project_relevance_mismatch"
    )


def test_project_lane_uses_search_fallback_after_direct_profiles_have_no_evidence() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="厦门税务系统中标公告",
    )
    search_provider = _FakeProjectSearchProvider()
    extraction_provider = _FakeProjectExtractionProvider()
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(_task("project_transaction", search_phrases=["西安 商业航天 项目"]))

    assert result.execution_state == "executed_with_evidence"
    assert result.document_count == 1
    assert result.evidence_count == 1
    assert result.metadata["rejected_document_count"] == 1
    assert result.metadata["project_search_fallback"]["status"] == "evidence_found"
    assert search_provider.requests[0].include_domains == []
    assert extraction_provider.requests[0].allow_supplemental_direct_keep is True


def test_project_search_fallback_does_not_send_download_candidate_to_crawl4ai() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="\u9996\u9875",
    )
    search_provider = _FakeProjectSearchProvider(
        result=TavilySearchResult(
            title="\u5408\u80a5\u65b0\u80fd\u6e90\u6c7d\u8f66\u96f6\u90e8\u4ef6\u9879\u76ee\u4e2d\u6807\u516c\u544a",
            url="https://www.ggzy.gov.cn/admin/api/downloadFile.do?id=abc123",
            content=(
                "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                "\u96f6\u90e8\u4ef6 \u9879\u76ee \u4e2d\u6807 \u516c\u544a"
            ),
            score=0.91,
            published_date="2026-04-01",
        )
    )
    extraction_provider = _FakeProjectExtractionProvider()
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(
        _task(
            "project_transaction",
            include_domains=["ggzy.gov.cn"],
            search_phrases=[
                "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 \u62db\u6807 \u4e2d\u6807"
            ],
        )
    )

    fallback = result.metadata["project_search_fallback"]
    assert result.execution_state == "executed_without_evidence"
    assert extraction_provider.requests == []
    assert fallback["status"] == "file_candidates_require_adapter"
    assert fallback["file_candidate_count"] == 1
    assert fallback["file_candidate_kinds"] == {"download_endpoint": 1}
    assert fallback["selected_candidate_count"] == 0
    assert fallback["candidate_decisions"][0]["reason_code"] == "project_file_requires_adapter"
    assert fallback["candidate_decisions"][0]["file_candidate_kind"] == "download_endpoint"
    assert result.errors[0].detail["extraction_failure_class"] == "file_or_download"


def test_project_search_fallback_pdf_candidate_uses_static_pdf_extraction() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="\u9996\u9875",
    )
    search_provider = _FakeProjectSearchProvider(
        result=TavilySearchResult(
            title=(
                "\u5408\u80a5\u65b0\u80fd\u6e90\u6c7d\u8f66"
                "\u9879\u76ee\u4e2d\u6807\u516c\u544a PDF"
            ),
            url="https://www.ggzy.gov.cn/files/hefei-nev-award.pdf",
            content=(
                "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                "\u9879\u76ee \u4e2d\u6807 \u516c\u544a"
            ),
            score=0.91,
            published_date="2026-04-01",
        )
    )
    extraction_provider = _FakeProjectExtractionProvider()
    pdf_download_service = _FakeOfficialRecordPdfDownloadService()
    pdf_text_service = _FakeOfficialRecordPdfTextService(
        page_text=(
            "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
            "\u9879\u76ee \u4e2d\u6807 \u516c\u544a \u91c7\u8d2d"
        )
    )
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        official_record_pdf_download_service=pdf_download_service,
        official_record_pdf_text_service=pdf_text_service,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_project_fallback_candidates=1,
    ).execute_task(
        _task(
            "project_transaction",
            include_domains=["ggzy.gov.cn"],
            search_phrases=[
                "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 \u62db\u6807 \u4e2d\u6807"
            ],
        )
    )

    fallback = result.metadata["project_search_fallback"]
    assert result.execution_state == "executed_with_evidence"
    assert extraction_provider.requests == []
    assert pdf_download_service.calls
    assert pdf_text_service.calls
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "accepted_project_pdf_fallback"
    )
    assert fallback["pdf_extraction"]["succeeded"] == 1
    assert result.documents[0].metadata["source_class"] == "tender_or_procurement"
    assert result.documents[0].metadata["from_pdf_attachment"] is True
    assert "pdf_backed_evidence" in result.documents[0].metadata["source_classes"]
    assert SourceFamilyBackbone.EXTRACTION_PDF_QUALITY_GATE.value in (
        result.documents[0].metadata["source_family_backbones"]
    )


def test_project_search_fallback_prefers_procurement_detail_over_generic_project_page() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="\u9996\u9875",
    )
    search_provider = _SequentialOfficialRecordSearchProvider(
        [
            [
                TavilySearchResult(
                    title="\u5408\u80a5\u65b0\u80fd\u6e90\u6c7d\u8f66\u96f6\u90e8\u4ef6\u9879\u76ee\u5f00\u5de5",
                    url="https://www.hefei.gov.cn/project/nev-start.html",
                    content=(
                        "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                        "\u96f6\u90e8\u4ef6 \u9879\u76ee \u5f00\u5de5"
                    ),
                    score=0.93,
                    published_date="2026-04-01",
                ),
                TavilySearchResult(
                    title="\u5408\u80a5\u65b0\u80fd\u6e90\u6c7d\u8f66\u96f6\u90e8\u4ef6\u9879\u76ee\u4e2d\u6807\u5019\u9009\u4eba\u516c\u793a",
                    url="https://ggzy.hefei.gov.cn/jyxx/002001/002001004/20260401/abc.html",
                    content=(
                        "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                        "\u96f6\u90e8\u4ef6 \u9879\u76ee \u4e2d\u6807 "
                        "\u5019\u9009\u4eba \u516c\u793a"
                    ),
                    score=0.88,
                    published_date="2026-04-02",
                ),
            ]
        ]
    )
    extraction_provider = _FakeProjectExtractionProviderWithHintOnlyPage()
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_project_fallback_candidates=1,
    ).execute_task(
        _task(
            "project_transaction",
            include_domains=["hefei.gov.cn", "ggzy.hefei.gov.cn"],
            search_phrases=[
                "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 \u9879\u76ee \u62db\u6807 \u4e2d\u6807"
            ],
        )
    )

    fallback = result.metadata["project_search_fallback"]
    assert result.execution_state == "executed_with_evidence"
    assert extraction_provider.requests[0].inputs[0].url == (
        "https://ggzy.hefei.gov.cn/jyxx/002001/002001004/20260401/abc.html"
    )
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "accepted_project_search_fallback"
    )
    assert fallback["candidate_decisions"][0]["url"] == (
        "https://ggzy.hefei.gov.cn/jyxx/002001/002001004/20260401/abc.html"
    )


def test_project_evidence_does_not_promote_generic_policy_page_to_procurement() -> None:
    task = _task(
        "project_transaction",
        search_phrases=[
            "\u4e1c\u6570\u897f\u7b97 \u6570\u636e\u4e2d\u5fc3 \u62db\u6807 \u4e2d\u6807"
        ],
    )
    document = RawDocument(
        document_id="ndrc_project_context_doc",
        source_id="search_assisted_project_fallback",
        title="\u56fd\u5bb6\u53d1\u6539\u59d4\u65b0\u95fb\u53d1\u5e03\u4f1a",
        source_uri="https://www.ndrc.gov.cn/xwdt/wszb/10yxwfbh1/",
        raw_text=(
            "\u4e1c\u6570\u897f\u7b97 \u6570\u636e\u4e2d\u5fc3 \u9879\u76ee "
            "\u62db\u6807 \u91c7\u8d2d \u5efa\u8bbe \u653f\u7b56 \u60c5\u51b5"
        ),
    )

    quality = _direct_document_evidence_quality(
        task=task,
        source_id="search_assisted_project_fallback",
        document=document,
    )

    assert "project_list" in quality["source_classes"]
    assert "tender_or_procurement" not in quality["source_classes"]
    assert SourceFamilyBackbone.PUBLIC_RESOURCE_PROCUREMENT.value not in (
        quality["source_family_backbones"]
    )


def test_generic_flag_parent_document_is_not_local_claim_eligible() -> None:
    task = _task(
        "official_record",
        search_phrases=[
            "\u51c6\u683c\u5c14\u65d7 \u7164\u5316\u5de5 \u73af\u8bc4 \u516c\u793a"
        ],
    )
    document = RawDocument(
        document_id="nmg_parent_record_doc",
        source_id="search_assisted_official_record_fallback",
        title="\u5185\u8499\u53e4\u7164\u5316\u5de5\u9879\u76ee\u5ba1\u6279\u60c5\u51b5",
        source_uri="https://www.nmg.gov.cn/zwgk/project/202604/record.html",
        raw_text=(
            "\u5185\u8499\u53e4 \u51c6\u683c\u5c14\u65d7 \u7164\u5316\u5de5 "
            "\u9879\u76ee \u73af\u8bc4 \u5ba1\u6279 \u516c\u793a"
        ),
    )

    quality = _direct_document_evidence_quality(
        task=task,
        source_id="search_assisted_official_record_fallback",
        document=document,
    )

    assert quality["local_region_match_type"] == "parent_local"
    assert quality["parent_evidence_only"] is True
    assert quality["local_claim_allowed"] is False
    assert quality["administrative_level_match"] is False


def test_project_search_fallback_rejects_wrong_region_candidates() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="厦门税务系统中标公告",
    )
    search_provider = _FakeProjectSearchProvider(
        result=TavilySearchResult(
            title="海安市新能源充电桩项目施工中标候选人公示",
            url="https://www.ggzy.gov.cn/html/b/320000/project.html",
            content="海安 新能源 充电桩 项目 中标",
            score=0.8,
        )
    )
    extraction_provider = _FakeProjectExtractionProvider()
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(_task("project_transaction", search_phrases=["合肥 新能源汽车 招标 中标"]))

    assert result.execution_state == "executed_without_evidence"
    assert result.metadata["project_search_fallback"]["status"] == "no_accepted_candidates"
    assert (
        result.metadata["project_search_fallback"]["candidate_decisions"][0]["reason_code"]
        == "project_region_mismatch"
    )
    assert extraction_provider.requests == []


def test_project_search_fallback_accepts_child_local_project_candidate() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="\u9996\u9875",
    )
    search_provider = _FakeProjectSearchProvider(
        result=TavilySearchResult(
            title="\u5b89\u5fbd\u957f\u4e30\u63a8\u8fdb\u91cd\u70b9\u9879\u76ee\u5efa\u8bbe\u6295\u4ea7",
            url="https://www.ah.gov.cn/public/project/changfeng-nev.html",
            content=(
                "\u957f\u4e30 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                "\u91cd\u70b9\u9879\u76ee \u5f00\u5de5 \u6295\u4ea7"
            ),
            score=0.86,
        )
    )
    extraction_provider = _FakeProjectExtractionProviderWithHintOnlyPage()
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_project_fallback_candidates=1,
    ).execute_task(
        _task(
            "project_transaction",
            include_domains=["ah.gov.cn", "hefei.gov.cn"],
            search_phrases=[
                "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                "\u91cd\u70b9\u9879\u76ee \u9879\u76ee\u6e05\u5355"
            ],
        )
    )

    decision = result.metadata["project_search_fallback"]["candidate_decisions"][0]
    assert result.execution_state == "executed_with_evidence"
    assert decision["reason_code"] == "accepted_project_search_fallback"
    assert decision["local_region_match_type"] == "child_local"
    assert decision["parent_evidence_only"] is False
    assert decision["local_claim_allowed"] is True
    assert decision["fallback_level"] == "child_local"
    assert result.documents[0].metadata["evidence_quality"]["local_region_match_type"] == (
        "child_local"
    )
    assert result.documents[0].metadata["evidence_quality"]["parent_evidence_only"] is False
    assert result.documents[0].metadata["evidence_quality"]["local_claim_allowed"] is True


def test_project_search_fallback_rejects_non_project_articles() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="厦门税务系统中标公告",
    )
    search_provider = _FakeProjectSearchProvider(
        result=TavilySearchResult(
            title="十年奋进合肥产业发展纪实",
            url="https://cjjjd.ndrc.gov.cn/gongzuodongtai/anhui/example.htm",
            content="合肥 新能源汽车 采购 项目",
            score=0.8,
        )
    )
    extraction_provider = _FakeProjectExtractionProvider()
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(_task("project_transaction", search_phrases=["合肥 新能源汽车 采购 项目"]))

    assert result.execution_state == "executed_without_evidence"
    assert result.metadata["project_search_fallback"]["status"] == "no_accepted_candidates"
    assert (
        result.metadata["project_search_fallback"]["candidate_decisions"][0]["reason_code"]
        == "project_signal_missing"
    )
    assert extraction_provider.requests == []


def test_project_search_fallback_uses_candidate_hints_when_crawl_page_is_sparse() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="厦门税务系统中标公告",
    )
    search_provider = _FakeProjectSearchProvider(
        result=TavilySearchResult(
            title="天河区柯木塱村城中村改造项目 - 全国公共资源交易平台",
            url="https://www.ggzy.gov.cn/html/b/440000/0101/project.shtml",
            content="城中村改造 项目 开工 资金来源",
            score=0.88,
        )
    )
    extraction_provider = _FakeProjectExtractionProviderWithHintOnlyPage()
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(
        _task(
            "project_transaction",
            search_phrases=["全国 城中村改造 项目 开工 资金来源"],
        )
    )

    assert result.execution_state == "executed_with_evidence"
    assert result.document_count == 1
    assert result.evidence_count == 1
    assert result.metadata["project_search_fallback"]["status"] == "evidence_found"
    quality = result.documents[0].metadata["evidence_quality"]
    assert quality["proof_strength"] in {"strong", "usable"}
    assert quality["source_class_match"] is True
    assert quality["topic_match"] is True
    assert quality["region_match"] is True
    assert result.normalized_documents[0].metadata["evidence_quality"] == quality
    assert (
        result.metadata["project_search_fallback"]["evidence_quality_summary"][
            "accepted_document_count"
        ]
        == 1
    )


def test_project_search_fallback_marks_tender_procurement_source_class() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="首页",
    )
    search_provider = _FakeProjectSearchProvider(
        result=TavilySearchResult(
            title="合肥新能源汽车充电桩项目中标候选人公示",
            url="https://ggzy.hefei.gov.cn/project/nev-bid.html",
            content="合肥 新能源汽车 充电桩 项目 中标 候选人",
            score=0.91,
            published_date="2026-03-21",
        )
    )
    extraction_provider = _FakeProjectExtractionProvider()
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(
        _task(
            "project_transaction",
            include_domains=["ggzy.hefei.gov.cn", "ggzy.gov.cn"],
            search_phrases=["合肥 新能源汽车 招标 中标"],
        )
    )

    assert result.execution_state == "executed_with_evidence"
    assert result.documents[0].metadata["source_class"] == "project_list"
    assert result.documents[0].metadata["source_classes"] == [
        "project_list",
        "tender_or_procurement",
    ]
    assert result.documents[0].metadata["evidence_quality"]["source_family_backbones"] == [
        "public_resource_procurement",
        "project_filing_approval_key_project",
    ]
    assert result.normalized_documents[0].metadata["source_classes"] == [
        "project_list",
        "tender_or_procurement",
    ]


def test_project_search_fallback_accepts_public_resource_snippet_signals() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="棣栭〉",
    )
    search_provider = _FakeProjectSearchProvider(
        result=TavilySearchResult(
            title="全国公共资源交易平台",
            url="https://www.ggzy.gov.cn/information/deal/html/b/340100/202604/8f6c9a.html",
            content="合肥 新能源汽车 充电桩 项目 中标公告 采购人 公共资源交易",
            score=0.91,
            published_date="2026-04-15",
        )
    )
    extraction_provider = _FakeProjectExtractionProviderWithHintOnlyPage()
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(
        _task(
            "project_transaction",
            include_domains=["ggzy.gov.cn"],
            search_phrases=["合肥 新能源汽车 招标 中标"],
        )
    )

    assert result.execution_state == "executed_with_evidence"
    assert extraction_provider.requests
    assert result.metadata["project_search_fallback"]["candidate_decisions"][0][
        "decision"
    ] == "accept"
    assert result.normalized_documents[0].metadata["source_classes"] == [
        "project_list",
        "tender_or_procurement",
    ]


def test_project_search_fallback_rejects_public_resource_list_pages() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ggzy_trade_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="首页",
    )
    search_provider = _FakeProjectSearchProvider(
        result=TavilySearchResult(
            title="合肥公共资源交易中心交易信息",
            url="https://ggzy.hefei.gov.cn/jyxx/index.html",
            content="合肥 新能源汽车 项目 招标 中标 交易信息",
            score=0.84,
            published_date="2026-03-21",
        )
    )
    extraction_provider = _FakeProjectExtractionProvider()
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(
        _task(
            "project_transaction",
            include_domains=["ggzy.hefei.gov.cn"],
            search_phrases=["合肥 新能源汽车 招标 中标"],
        )
    )

    assert result.execution_state == "executed_without_evidence"
    assert result.metadata["project_search_fallback"]["candidate_decisions"][0][
        "reason_code"
    ] == "generic_project_navigation"
    assert extraction_provider.requests == []


def test_project_search_fallback_accepts_official_approval_snippet_signals() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="首页",
    )
    search_provider = _FakeProjectSearchProvider(
        result=TavilySearchResult(
            title="神木市发展改革和科技局预算公开目录",
            url="https://www.sxsm.gov.cn/zfxxgk/fdzdgknr/czxx/ysgk/fzgghkjj/202604/project-budget.html",
            content=(
                "神木 煤化工 项目备案 审批 重点项目 开工 投产 "
                "建设单位 陕煤 化工园区"
            ),
            score=0.88,
            published_date="2026-04-10",
        )
    )
    extraction_provider = _FakeProjectExtractionProviderWithHintOnlyPage()
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(
        _task(
            "project_transaction",
            include_domains=["sxsm.gov.cn"],
            search_phrases=["神木 煤化工 项目备案 审批"],
        )
    )

    assert result.execution_state == "executed_with_evidence"
    assert result.metadata["project_search_fallback"]["candidate_decisions"][0][
        "decision"
    ] == "accept"
    assert "project_list" in result.normalized_documents[0].metadata["source_classes"]


def test_project_search_fallback_rejects_broad_planning_without_project_signal() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="首页",
    )
    search_provider = _FakeProjectSearchProvider(
        result=TavilySearchResult(
            title="关于对《若羌县产业新城建设发展规划研究（2023—2030年）》公开征求意见",
            url="https://www.xjbz.gov.cn/xjbz/bzg/202306/planning-opinion.shtml",
            content="若羌 盐湖 产业 发展规划 交通 电力 公开征求意见",
            score=0.82,
            published_date="2023-06-15",
        )
    )
    extraction_provider = _FakeProjectExtractionProvider()
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(
        _task(
            "project_transaction",
            include_domains=["xjbz.gov.cn"],
            search_phrases=["若羌 盐湖 项目备案 审批"],
        )
    )

    assert result.execution_state == "executed_without_evidence"
    assert (
        result.metadata["project_search_fallback"]["candidate_decisions"][0][
            "reason_code"
        ]
        == "generic_project_planning_or_interpretation"
    )
    assert extraction_provider.requests == []


def test_project_search_fallback_rejects_broad_planning_even_with_project_terms() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="首页",
    )
    search_provider = _FakeProjectSearchProvider(
        result=TavilySearchResult(
            title="关于对《若羌县产业新城建设发展规划研究（2023—2030年）》公开征求意见",
            url="https://www.xjbz.gov.cn/xjbz/bzg/202306/planning-opinion.shtml",
            content="若羌 盐湖 重点项目 开工 投产 项目建设 产业化条件",
            score=0.83,
            published_date="2023-06-15",
        )
    )
    extraction_provider = _FakeProjectExtractionProvider()
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(
        _task(
            "project_transaction",
            include_domains=["xjbz.gov.cn"],
            search_phrases=["若羌 盐湖 重点项目 开工 投产"],
        )
    )

    assert result.execution_state == "executed_without_evidence"
    assert (
        result.metadata["project_search_fallback"]["candidate_decisions"][0][
            "reason_code"
        ]
        == "generic_project_planning_or_interpretation"
    )
    assert extraction_provider.requests == []


def test_project_search_fallback_rejects_policy_interpretation_pages_as_project_evidence() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="首页",
    )
    search_provider = _FakeProjectSearchProvider(
        result=TavilySearchResult(
            title="【专家观点】我国低空经济发展面临的问题与政策建议",
            url="https://www.ndrc.gov.cn/wsdwhfz/202412/t20241230_1395328.html",
            content="低空经济 基础设施建设 项目 试点 项目建设 政策建议",
            score=0.86,
            published_date="2024-12-30",
        )
    )
    extraction_provider = _FakeProjectExtractionProvider()
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(
        _task(
            "project_transaction",
            include_domains=["ndrc.gov.cn"],
            search_phrases=["全国 低空经济 基础设施建设 项目"],
        )
    )

    assert result.execution_state == "executed_without_evidence"
    assert (
        result.metadata["project_search_fallback"]["candidate_decisions"][0][
            "reason_code"
        ]
        == "generic_project_planning_or_interpretation"
    )
    assert extraction_provider.requests == []


def test_project_search_fallback_respects_search_credit_budget() -> None:
    ccgp = _FakeProfileAdapter(
        _profile(
            "cn_project_ccgp_procurement_v1",
            category=SourceCategory.PROJECT_SIGNAL,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.PROJECT_TRANSACTION,
        ),
        document_title="首页",
    )
    search_provider = _SequentialOfficialRecordSearchProvider(
        [
            [
                TavilySearchResult(
                    title="海安市新能源汽车充电桩项目中标候选人公示",
                    url="https://www.ggzy.gov.cn/html/b/320000/project-1.html",
                    content="海安 新能源汽车 充电桩 项目 中标",
                    score=0.80,
                )
            ],
            [
                TavilySearchResult(
                    title="芜湖市交通设施采购公告",
                    url="https://www.ggzy.gov.cn/html/b/340200/project-2.html",
                    content="芜湖 交通 采购 项目",
                    score=0.79,
                )
            ],
            [
                TavilySearchResult(
                    title="合肥新能源汽车零部件产业园重点项目开工",
                    url="https://ggzy.hefei.gov.cn/project-3.html",
                    content="合肥 新能源汽车 零部件 重点项目 开工 投产",
                    score=0.92,
                )
            ],
        ]
    )
    extraction_provider = _FakeProjectExtractionProvider()
    registry = _registry_with(ccgp)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        project_search_provider=search_provider,
        project_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_project_fallback_candidates=1,
        max_project_fallback_search_credits=2,
    ).execute_task(
        _task(
            "project_transaction",
            include_domains=["ggzy.hefei.gov.cn", "ggzy.gov.cn"],
            search_phrases=[
                "合肥 新能源汽车 项目清单",
                "合肥 新能源汽车 开工 投产",
                "合肥 新能源汽车 招标 中标",
            ],
        )
    )

    fallback = result.metadata["project_search_fallback"]
    assert len(search_provider.requests) == 2
    assert extraction_provider.requests == []
    assert result.execution_state == "executed_without_evidence"
    assert fallback["status"] == "search_credit_budget_exhausted"
    assert fallback["stop_reason"] == "search_credit_budget_exhausted"
    assert fallback["max_estimated_tavily_credits"] == 2
    assert fallback["budget_state"]["used_search_credits"] == 2
    assert fallback["budget_state"]["max_search_credits"] == 2


def test_data_metrics_lane_rejects_generic_stats_homepage_documents() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        enable_data_metrics_search_fallback=False,
    ).execute_task(_task("data_metrics", search_phrases=["全国 算力 统计 数据"]))

    assert result.execution_state == "executed_without_evidence"
    assert result.document_count == 0
    assert result.metadata["rejected_document_count"] == 1
    assert result.metadata["weak_document_rejections"][0]["reason_code"] == "generic_stats_homepage"


def test_data_metrics_lane_rejects_generic_stats_data_page_even_with_topic_terms() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="数据",
        source_uri="https://www.stats.gov.cn/sj/",
        raw_text=(
            "数据发布 低空经济 产业统计分类 市场规模 企业订单 "
            "能源供给 工业增加值 固定资产投资 服务业 数据解读"
        ),
    )
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        enable_data_metrics_search_fallback=False,
    ).execute_task(_task("data_metrics", search_phrases=["低空经济 产业统计分类 市场规模"]))

    assert result.execution_state == "executed_without_evidence"
    assert result.document_count == 0
    assert result.metadata["rejected_document_count"] == 1
    assert result.metadata["weak_document_rejections"][0]["reason_code"] == "generic_stats_homepage"


def test_data_metrics_lane_rejects_irrelevant_direct_documents() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="第139届广交会",
    )
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        enable_data_metrics_search_fallback=False,
    ).execute_task(_task("data_metrics", search_phrases=["合肥 新能源汽车 统计 数据"]))

    assert result.execution_state == "executed_without_evidence"
    assert result.document_count == 0
    assert result.metadata["rejected_document_count"] == 1
    assert result.metadata["weak_document_rejections"][0]["reason_code"] == (
        "data_metrics_relevance_mismatch"
    )
    quality = result.metadata["weak_document_rejections"][0]["evidence_quality"]
    assert quality["proof_strength"] == "weak"
    assert quality["topic_match"] is False
    assert quality["region_match"] is False


def test_data_metrics_lane_uses_search_fallback_after_direct_profiles_have_no_evidence() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider()
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(_task("data_metrics", search_phrases=["安徽 新能源汽车 统计 数据"]))

    assert result.execution_state == "executed_with_evidence"
    assert result.document_count == 1
    assert result.evidence_count == 1
    assert result.metadata["data_metrics_search_fallback"]["status"] == "evidence_found"
    assert search_provider.requests[0].search_depth == "basic"
    assert extraction_provider.requests[0].allow_supplemental_direct_keep is True


def test_data_metrics_search_fallback_accepts_exact_local_government_work_report() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="2024年神木市人民政府工作报告",
            url="https://www.sxsm.gov.cn/zfxxgk/fdzdgknr/gzbg/202404/t20240408.html",
            content="神木市 经济运行 煤炭产量 财政收入",
            score=0.86,
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            search_phrases=["全国 神木市煤炭和煤化工产业 统计 数据"],
        )
    )

    assert result.execution_state == "executed_with_evidence"
    assert result.metadata["data_metrics_search_fallback"]["status"] == "evidence_found"
    assert (
        result.metadata["data_metrics_search_fallback"]["candidate_decisions"][0]["reason_code"]
        == "accepted_data_metrics_search_fallback"
    )
    assert result.documents[0].metadata["source_class"] == "statistics"
    assert result.documents[0].metadata["source_classes"] == ["statistics"]
    assert result.normalized_documents[0].metadata["source_class"] == "statistics"
    assert result.normalized_documents[0].metadata["source_classes"] == ["statistics"]


def test_data_metrics_search_fallback_marks_parent_local_statistics_candidate() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="\u9655\u897f\u77012024\u5e74\u56fd\u6c11\u7ecf\u6d4e\u548c\u793e\u4f1a\u53d1\u5c55\u7edf\u8ba1\u516c\u62a5",
            url="https://www.shaanxi.gov.cn/xw/tjgb/2024.html",
            content=(
                "\u9655\u897f \u7edf\u8ba1\u516c\u62a5 "
                "\u7164\u70ad\u4ea7\u91cf \u5de5\u4e1a\u589e\u52a0\u503c "
                "\u8d22\u653f\u6536\u5165"
            ),
            score=0.82,
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["sxsm.gov.cn", "shaanxi.gov.cn", "tjj.shaanxi.gov.cn"],
            search_phrases=[
                "\u795e\u6728 \u7164\u70ad \u7164\u5316\u5de5 \u7edf\u8ba1\u516c\u62a5 \u8d22\u653f"
            ],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    decision = fallback["candidate_decisions"][0]
    assert result.execution_state == "executed_with_evidence"
    assert decision["reason_code"] == "accepted_data_metrics_search_fallback"
    assert decision["local_region_match_type"] == "parent_local"
    assert decision["parent_evidence_only"] is True
    assert decision["local_claim_allowed"] is False
    assert decision["fallback_level"] == "parent_official"
    assert result.documents[0].metadata["evidence_quality"]["local_region_match_type"] == (
        "parent_local"
    )
    assert result.documents[0].metadata["evidence_quality"]["parent_evidence_only"] is True
    assert result.documents[0].metadata["evidence_quality"]["local_claim_allowed"] is False
    assert result.documents[0].metadata["source_class"] == "statistics"
    assert result.documents[0].metadata["source_classes"] == ["statistics"]


def test_data_metrics_search_fallback_rejects_media_focus_pages_as_statistics() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="\u5185\u8499\u53e4\u7eff\u6c22\u7164\u5316\u5de5\u8fd0\u884c\u62a5\u544a",
            url="http://kjt.nmg.gov.cn/kjdt/mtjj/202602/t20260212_2862873.html",
            content=(
                "\u5185\u8499\u53e4 \u7eff\u7535 \u7eff\u6c22 \u7164\u5316\u5de5 "
                "\u8fd0\u884c \u4ea7\u91cf \u6570\u636e"
            ),
            score=0.80,
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["kjt.nmg.gov.cn", "tjj.nmg.gov.cn", "nmg.gov.cn"],
            search_phrases=[
                "\u5185\u8499\u53e4 \u7eff\u7535 \u7eff\u6c22 \u7164\u5316\u5de5 "
                "\u4ea7\u91cf \u6570\u636e"
            ],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert result.execution_state == "executed_without_evidence"
    assert extraction_provider.requests == []
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "data_metrics_source_role_mismatch"
    )


def test_data_metrics_search_fallback_rejects_media_focus_government_report_mirrors() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="\u5185\u8499\u53e4\u81ea\u6cbb\u533a\u653f\u5e9c\u5de5\u4f5c\u62a5\u544a",
            url="http://kjt.nmg.gov.cn/kjdt/mtjj/202602/t20260212_2862873.html",
            content=(
                "\u5185\u8499\u53e4 \u7eff\u7535 \u7eff\u6c22 \u7164\u5316\u5de5 "
                "\u8fd0\u884c \u4ea7\u91cf \u8d22\u653f\u6536\u5165"
            ),
            score=0.80,
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["kjt.nmg.gov.cn", "tjj.nmg.gov.cn", "nmg.gov.cn"],
            search_phrases=[
                "\u5185\u8499\u53e4 \u7eff\u7535 \u7eff\u6c22 \u7164\u5316\u5de5 "
                "\u4ea7\u91cf \u6570\u636e"
            ],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert result.execution_state == "executed_without_evidence"
    assert extraction_provider.requests == []
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "data_metrics_source_role_mismatch"
    )


def test_data_metrics_search_fallback_rejects_region_only_statistics_match() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title=(
                "\u7b2c\u4e8c\u6b21\u5185\u8499\u53e4R\uff06D"
                "\u8d44\u6e90\u6e05\u67e5\u4e3b\u8981\u6570\u636e\u516c\u62a5"
            ),
            url=(
                "https://www.stats.gov.cn/sj/tjgb/rdpcgb/dfpcgb/"
                "202302/t20230206_1902226.html"
            ),
            content=(
                "\u5185\u8499\u53e4 \u7814\u53d1 \u4eba\u5458 "
                "\u7ecf\u8d39 \u7edf\u8ba1\u516c\u62a5"
            ),
            score=0.90,
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["stats.gov.cn", "tj.nmg.gov.cn", "nyj.nmg.gov.cn"],
            search_phrases=[
                "\u5185\u8499\u53e4 \u7535\u529b\u8fd0\u884c \u53d1\u7535\u91cf \u7528\u7535\u91cf"
            ],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert result.execution_state == "executed_without_evidence"
    assert extraction_provider.requests == []
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "data_metrics_relevance_mismatch"
    )


def test_data_metrics_search_fallback_accepts_provincial_energy_operation_page() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="内蒙古自治区2025年3月电力运行情况",
            url="https://nyj.nmg.gov.cn/xxgk/ywxx/202504/t20250410.html",
            content="内蒙古 全社会用电量 发电量 新能源 发电 数据",
            score=0.88,
            published_date="2025-04-10",
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["nyj.nmg.gov.cn", "tjj.nmg.gov.cn", "nmg.gov.cn"],
            search_phrases=["内蒙古 绿电 绿氢 能源 用电量 数据"],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert result.execution_state == "executed_with_evidence"
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "accepted_data_metrics_search_fallback"
    )
    assert result.documents[0].metadata["source_class"] == "statistics"


def test_data_metrics_search_fallback_accepts_national_energy_power_usage_page() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="\u5168\u56fd\u7535\u529b\u5de5\u4e1a\u7edf\u8ba1\u6570\u636e",
            url="https://www.nea.gov.cn/2025-04/22/c_1310791123.htm",
            content=(
                "\u5168\u793e\u4f1a\u7528\u7535\u91cf \u6570\u636e\u4e2d\u5fc3 "
                "\u80fd\u8017 \u7b97\u529b \u7535\u529b\u4f9b\u9700"
            ),
            score=0.88,
            published_date="2025-04-22",
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["nea.gov.cn", "miit.gov.cn", "stats.gov.cn"],
            search_phrases=[
                "\u56fd\u5bb6\u80fd\u6e90\u5c40 \u6570\u636e\u4e2d\u5fc3 "
                "\u7528\u7535\u91cf \u80fd\u8017"
            ],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert result.execution_state == "executed_with_evidence"
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "accepted_data_metrics_search_fallback"
    )
    assert result.documents[0].metadata["source_class"] == "statistics"


def test_data_metrics_search_fallback_accepts_official_data_resource_survey_pdf() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="\u5168\u56fd\u6570\u636e\u8d44\u6e90\u8c03\u67e5\u62a5\u544a\uff082023\u5e74\uff09",
            url=(
                "https://www.nda.gov.cn/sjj/ywpd/sjzy/0830/"
                "ff808081-91bfe71b-0191-c0c89bbc-0030.pdf"
            ),
            content=(
                "\u7b97\u529b \u6570\u636e\u8d44\u6e90 "
                "\u5168\u56fd\u6570\u636e\u8d44\u6e90\u8c03\u67e5\u62a5\u544a"
            ),
            score=0.92,
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["nda.gov.cn", "stats.gov.cn"],
            search_phrases=[
                (
                    "\u56fd\u5bb6\u6570\u636e\u5c40 "
                    "\u5168\u56fd\u6570\u636e\u8d44\u6e90\u8c03\u67e5\u62a5\u544a "
                    "\u7b97\u529b"
                )
            ],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert result.execution_state == "executed_with_evidence"
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "accepted_data_metrics_pdf_fallback"
    )
    assert result.documents[0].metadata["source_class"] == "statistics"


def test_data_metrics_search_fallback_accepts_provincial_trade_statistics_page() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="广西2025年一季度外贸进出口运行情况",
            url="https://swt.gxzf.gov.cn/xxgk/sjfb/202504/t20250418.html",
            content="广西 东盟 口岸 进出口 出口 进口 数据",
            score=0.87,
            published_date="2025-04-18",
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["swt.gxzf.gov.cn", "gxzf.gov.cn"],
            search_phrases=["广西 东盟 跨境物流 进出口 数据"],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert result.execution_state == "executed_with_evidence"
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "accepted_data_metrics_search_fallback"
    )
    assert result.documents[0].metadata["source_class"] == "statistics"


def test_data_metrics_search_fallback_accepts_county_trade_export_statistics_page() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="义乌市2025年一季度小商品出口数据",
            url="https://swj.yw.gov.cn/xxgk/sjtj/202504/t20250420.html",
            content="义乌 小商品 跨境电商 出口 进口 物流 数据",
            score=0.86,
            published_date="2025-04-20",
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["swj.yw.gov.cn", "yw.gov.cn"],
            search_phrases=["义乌 跨境电商 小商品出口 海关 数据"],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert result.execution_state == "executed_with_evidence"
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "accepted_data_metrics_search_fallback"
    )
    assert result.documents[0].metadata["source_class"] == "statistics"


def test_data_metrics_search_fallback_accepts_official_statistical_classification_pdf() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="\u4f4e\u7a7a\u7ecf\u6d4e\u53ca\u5176\u6838\u5fc3\u4ea7\u4e1a\u7edf\u8ba1\u5206\u7c7b\uff08\u8bd5\u884c\uff09",
            url="https://www.ndrc.gov.cn/xwdt/tzgg/202512/P020251226697703940105.pdf",
            content=(
                "\u4f4e\u7a7a\u7ecf\u6d4e \u7edf\u8ba1\u5206\u7c7b "
                "\u4ea7\u4e1a\u5206\u7c7b \u6307\u6807"
            ),
            score=0.88,
            published_date="2025-12-26",
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["ndrc.gov.cn"],
            search_phrases=[
                "\u4f4e\u7a7a\u7ecf\u6d4e \u5e02\u573a\u89c4\u6a21 \u6570\u636e"
            ],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert result.execution_state == "executed_with_evidence"
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "accepted_data_metrics_pdf_fallback"
    )
    assert result.documents[0].metadata["source_class"] == "statistics"


def test_data_metrics_search_fallback_rejects_commerce_policy_news_as_statistics() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="浙江省商务厅支持外贸高质量发展政策解读",
            url="https://commerce.zj.gov.cn/xwdt/202504/t20250401.html",
            content="浙江 外贸 企业 政策 解读 支持措施",
            score=0.82,
            published_date="2025-04-01",
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["commerce.zj.gov.cn", "zj.gov.cn"],
            search_phrases=["浙江 外贸 出口 数据"],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert result.execution_state == "executed_without_evidence"
    assert extraction_provider.requests == []
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "data_metrics_source_role_mismatch"
    )


def test_data_metrics_search_fallback_accepts_statistics_bureau_pages() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="\u5e38\u5dde\u5e022024\u5e74\u56fd\u6c11\u7ecf\u6d4e\u548c\u793e\u4f1a\u53d1\u5c55\u7edf\u8ba1\u516c\u62a5",
            url="https://tjj.changzhou.gov.cn/html/tjj/2024/OEJQMFCO_0305/27901.html",
            content=(
                "\u5e38\u5dde \u7edf\u8ba1\u516c\u62a5 \u52a8\u529b\u7535\u6c60 "
                "\u5149\u4f0f \u6295\u8d44 \u4ea7\u91cf \u6570\u636e"
            ),
            score=0.86,
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["tjj.changzhou.gov.cn", "changzhou.gov.cn"],
            search_phrases=[
                "\u5e38\u5dde \u52a8\u529b\u7535\u6c60 \u5149\u4f0f "
                "\u7edf\u8ba1\u516c\u62a5 \u6295\u8d44 \u6570\u636e"
            ],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert result.execution_state == "executed_with_evidence"
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "accepted_data_metrics_search_fallback"
    )
    assert result.documents[0].metadata["source_class"] == "statistics"


def test_data_metrics_search_fallback_accepts_tj_statistics_subdomains() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="\u5185\u8499\u53e4\u4e3b\u8981\u7ecf\u6d4e\u6307\u6807\u6570\u636e",
            url="https://tj.nmg.gov.cn/tjyw/tjsj/2024.html",
            content=(
                "\u5185\u8499\u53e4 \u7edf\u8ba1 \u7eff\u7535 \u7eff\u6c22 "
                "\u7164\u5316\u5de5 \u4ea7\u91cf \u6295\u8d44 \u6570\u636e"
            ),
            score=0.87,
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["tj.nmg.gov.cn", "nmg.gov.cn"],
            search_phrases=[
                "\u5185\u8499\u53e4 \u7eff\u7535 \u7eff\u6c22 \u7164\u5316\u5de5 "
                "\u7edf\u8ba1 \u6570\u636e"
            ],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert result.execution_state == "executed_with_evidence"
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "accepted_data_metrics_search_fallback"
    )


def test_data_metrics_search_fallback_accepts_official_energy_operation_data_pages() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="\u5185\u8499\u53e4\u80fd\u6e90\u8fd0\u884c\u6708\u62a5\u6570\u636e",
            url="https://nyj.nmg.gov.cn/ywdt/nyyx/2024.html",
            content=(
                "\u5185\u8499\u53e4 \u7eff\u7535 \u7eff\u6c22 \u7164\u5316\u5de5 "
                "\u53d1\u7535\u91cf \u7528\u7535\u91cf \u4ea7\u91cf \u6570\u636e"
            ),
            score=0.88,
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["nyj.nmg.gov.cn", "tjj.nmg.gov.cn", "nmg.gov.cn"],
            search_phrases=[
                "\u5185\u8499\u53e4 \u7eff\u7535 \u7eff\u6c22 \u7164\u5316\u5de5 "
                "\u4ea7\u91cf \u6570\u636e"
            ],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert result.execution_state == "executed_with_evidence"
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "accepted_data_metrics_search_fallback"
    )
    assert result.documents[0].metadata["source_class"] == "statistics"


def test_data_metrics_search_fallback_does_not_count_file_download_as_evidence() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title=(
                "\u5b89\u5fbd\u7701\u65b0\u80fd\u6e90\u6c7d\u8f66"
                "\u4ea7\u91cf\u7edf\u8ba1\u6570\u636e\u8868"
            ),
            url="https://tjj.ah.gov.cn/tjsj/2024/nev-output.xlsx",
            content=(
                "\u5b89\u5fbd \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                "\u4ea7\u91cf \u7edf\u8ba1 \u6570\u636e"
            ),
            score=0.91,
            published_date="2026-03-01",
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["tjj.ah.gov.cn", "ah.gov.cn"],
            search_phrases=[
                (
                    "\u5b89\u5fbd \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                    "\u4ea7\u91cf \u7edf\u8ba1 \u6570\u636e"
                )
            ],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert extraction_provider.requests == []
    assert result.execution_state == "executed_without_evidence"
    assert result.document_count == 0
    assert fallback["status"] == "file_candidates_require_adapter"
    assert fallback["file_candidate_count"] == 1
    assert fallback["selected_candidate_count"] == 0
    assert fallback["candidate_decisions"][0]["decision"] == "reject"
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "data_metrics_file_requires_adapter"
    )
    assert fallback["candidate_decisions"][0]["file_candidate_kind"] == "xlsx"
    assert result.errors[0].detail["extraction_failure_class"] == "file_or_download"
    assert result.errors[0].detail["extraction_failure_stage"] == (
        "candidate_classification"
    )


def test_data_metrics_search_fallback_pdf_candidate_uses_static_pdf_extraction() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="\u5185\u8499\u53e4\u80fd\u6e90\u7edf\u8ba1\u6708\u62a5 PDF",
            url="https://tjj.nmg.gov.cn/tjsj/2026/energy-monthly.pdf",
            content="\u5185\u8499\u53e4 \u80fd\u6e90 \u7528\u7535\u91cf \u7edf\u8ba1",
            score=0.91,
            published_date="2026-03-01",
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    pdf_download_service = _FakeOfficialRecordPdfDownloadService()
    pdf_text_service = _FakeOfficialRecordPdfTextService(
        page_text=(
            "\u5185\u8499\u53e4 \u80fd\u6e90 \u7528\u7535\u91cf "
            "\u7edf\u8ba1 \u6708\u62a5 \u6570\u636e"
        )
    )
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        official_record_pdf_download_service=pdf_download_service,
        official_record_pdf_text_service=pdf_text_service,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["tjj.nmg.gov.cn", "nmg.gov.cn"],
            search_phrases=[
                "\u5185\u8499\u53e4 \u7eff\u7535 \u7eff\u6c22 \u80fd\u6e90 \u6570\u636e"
            ],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert result.execution_state == "executed_with_evidence"
    assert extraction_provider.requests == []
    assert pdf_download_service.calls
    assert pdf_text_service.calls
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "accepted_data_metrics_pdf_fallback"
    )
    assert fallback["pdf_extraction"]["succeeded"] == 1
    assert result.documents[0].metadata["source_class"] == "statistics"
    assert result.documents[0].metadata["from_pdf_attachment"] is True


def test_data_metrics_search_fallback_rejects_generic_yearbook_section_pdf() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title=(
                "[PDF] \u7b2c\u4e00\u90e8\u5206\u7279\u8f7d - "
                "\u829c\u6e56\u5e02\u7edf\u8ba1\u5c40"
            ),
            url=(
                "https://tjj.wuhu.gov.cn/zhsj/tjnj/"
                "%E8%8A%9C%E6%B9%96%E7%BB%9F%E8%AE%A1%E5%B9%B4%E9%89%B42025/"
                "files/1.pdf"
            ),
            content="\u829c\u6e56 \u7edf\u8ba1\u5e74\u9274 \u7b2c\u4e00\u90e8\u5206\u7279\u8f7d",
            score=0.91,
            published_date="2026-03-01",
        )
    )
    pdf_download_service = _FakeOfficialRecordPdfDownloadService()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=_FakeDataMetricsExtractionProviderWithHintOnlyPage(),
        official_record_pdf_download_service=pdf_download_service,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["tjj.wuhu.gov.cn"],
            search_phrases=[
                (
                    "\u5b89\u5fbd\u7701\u7edf\u8ba1\u5c40 "
                    "\u65b0\u80fd\u6e90\u6c7d\u8f66 \u7edf\u8ba1\u516c\u62a5"
                )
            ],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert result.execution_state == "executed_without_evidence"
    assert pdf_download_service.calls == []
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "generic_data_metrics_yearbook_file"
    )


def test_data_metrics_search_fallback_classifies_download_endpoint_as_file_candidate() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="\u5b89\u5fbd\u7701\u5de5\u4e1a\u8fd0\u884c\u7edf\u8ba1\u6570\u636e",
            url="https://tjj.ah.gov.cn/attachment/download?fileId=2024",
            content="\u5b89\u5fbd \u5de5\u4e1a\u8fd0\u884c \u7edf\u8ba1 \u6570\u636e",
            score=0.89,
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["tjj.ah.gov.cn", "ah.gov.cn"],
            search_phrases=["\u5b89\u5fbd \u5de5\u4e1a\u8fd0\u884c \u7edf\u8ba1 \u6570\u636e"],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert extraction_provider.requests == []
    assert fallback["file_candidate_count"] == 1
    assert fallback["file_candidate_kinds"] == {"download_endpoint": 1}
    assert fallback["candidate_decisions"][0]["file_candidate_kind"] == (
        "download_endpoint"
    )


def test_data_metrics_search_fallback_rejects_wrong_region_file_before_file_gate() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _FakeDataMetricsSearchProvider(
        result=TavilySearchResult(
            title="\u6c5f\u82cf\u7701\u65b0\u80fd\u6e90\u6c7d\u8f66\u4ea7\u91cf\u6570\u636e",
            url="https://tjj.js.gov.cn/tjsj/2024/nev-output.xlsx",
            content="\u6c5f\u82cf \u65b0\u80fd\u6e90\u6c7d\u8f66 \u4ea7\u91cf \u7edf\u8ba1",
            score=0.86,
        )
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
    ).execute_task(
        _task(
            "data_metrics",
            search_phrases=[
                (
                    "\u5b89\u5fbd \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                    "\u4ea7\u91cf \u7edf\u8ba1 \u6570\u636e"
                )
            ],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert extraction_provider.requests == []
    assert fallback["file_candidate_count"] == 0
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "data_metrics_region_mismatch"
    )


def test_data_metrics_lane_prefers_inner_mongolia_stats_profile_when_available() -> None:
    nmg_stats = _FakeProfileAdapter(
        _profile(
            "cn_data_nmg_stats_bulletin_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
            regional_level=RegionalLevel.PROVINCIAL,
        ),
        document_title="内蒙古 绿电 统计 数据",
    )
    national_stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        )
    )
    registry = _registry_with(nmg_stats, national_stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(_task("data_metrics", search_phrases=["内蒙古 绿电 统计 数据"]))

    assert result.execution_state == "executed_with_evidence"
    assert result.source_ids_selected == ["cn_data_nmg_stats_bulletin_v1"]
    assert nmg_stats.search_calls[0].query_context.regional_focus == ["内蒙古"]


def test_data_metrics_search_fallback_respects_search_credit_budget() -> None:
    stats = _FakeProfileAdapter(
        _profile(
            "cn_data_stats_national_v1",
            category=SourceCategory.MACRO_DATA,
            line_family=LineFamily.CROSS_DOMAIN,
            info_type=InfoType.INDUSTRY_NOTICE,
        ),
        document_title="EN",
    )
    search_provider = _SequentialOfficialRecordSearchProvider(
        [
            [
                TavilySearchResult(
                    title="芜湖市统计公报",
                    url="https://tjj.wuhu.gov.cn/data-1.html",
                    content="芜湖 统计公报 财政收入",
                    score=0.80,
                )
            ],
            [
                TavilySearchResult(
                    title="安徽省工业运行数据",
                    url="https://tjj.ah.gov.cn/data-2.html",
                    content="安徽 工业运行 数据",
                    score=0.79,
                )
            ],
            [
                TavilySearchResult(
                    title="合肥市新能源汽车产业财政支持和统计公报",
                    url="https://tjj.hefei.gov.cn/data-3.html",
                    content="合肥 新能源汽车 财政支持 补贴 统计公报",
                    score=0.92,
                )
            ],
        ]
    )
    extraction_provider = _FakeDataMetricsExtractionProviderWithHintOnlyPage()
    registry = _registry_with(stats)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        data_metrics_search_provider=search_provider,
        data_metrics_extraction_provider=extraction_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_data_metrics_fallback_candidates=1,
        max_data_metrics_fallback_search_credits=2,
    ).execute_task(
        _task(
            "data_metrics",
            include_domains=["tjj.hefei.gov.cn", "tjj.ah.gov.cn"],
            search_phrases=[
                "合肥 新能源汽车 统计公报 财政",
                "合肥 新能源汽车 财政资金 补贴",
                "合肥 新能源汽车 投资 数据",
            ],
        )
    )

    fallback = result.metadata["data_metrics_search_fallback"]
    assert len(search_provider.requests) == 2
    assert extraction_provider.requests == []
    assert result.execution_state == "executed_without_evidence"
    assert fallback["status"] == "search_credit_budget_exhausted"
    assert fallback["stop_reason"] == "search_credit_budget_exhausted"
    assert fallback["max_estimated_tavily_credits"] == 2
    assert fallback["budget_state"]["used_search_credits"] == 2
    assert fallback["budget_state"]["max_search_credits"] == 2


def test_official_record_lane_uses_search_fallback_without_direct_adapter() -> None:
    search_provider = _FakeOfficialRecordSearchProvider()
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage()

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        enable_official_record_pdf_fallback=False,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            search_phrases=["神木 煤化工 环评 公示"],
        )
    )

    assert result.execution_state == "executed_with_evidence"
    assert result.document_count == 1
    assert result.evidence_count == 1
    assert result.source_ids_selected == []
    assert result.metadata["official_record_search_fallback"]["status"] == "evidence_found"
    quality = result.documents[0].metadata["evidence_quality"]
    assert quality["source_class_match"] is True
    assert quality["topic_match"] is True
    assert quality["proof_strength"] in {"strong", "usable"}
    assert (
        result.metadata["official_record_search_fallback"]["evidence_quality_summary"][
            "accepted_document_count"
        ]
        == 1
    )
    assert (
        result.metadata["official_record_search_fallback"]["candidate_decisions"][0]["reason_code"]
        == "accepted_official_record_search_fallback"
    )
    assert search_provider.requests[0].search_depth == "basic"
    assert extraction_provider.requests[0].allow_supplemental_direct_keep is True


def test_official_record_lane_rejects_project_procurement_as_record_evidence() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title="神木煤化工项目中标公告",
            url="https://sxsm.gov.cn/ggzy/project-bid.html",
            content="神木 煤化工 项目 招标 中标",
            score=0.88,
            published_date="2026-03-11",
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage()

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        enable_official_record_pdf_fallback=False,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            search_phrases=["神木 煤化工 环评 公示"],
        )
    )

    assert result.execution_state == "executed_without_evidence"
    assert result.document_count == 0
    assert result.metadata["official_record_search_fallback"]["status"] == "no_accepted_candidates"
    assert (
        result.metadata["official_record_search_fallback"]["candidate_decisions"][0]["reason_code"]
        == "official_record_signal_missing"
    )
    assert extraction_provider.requests == []


def test_official_record_lane_accepts_exact_region_from_search_snippet() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title="巴州生态环境局环评科关于建设项目环境影响评价文件受理情况的公示",
            url="https://www.xjbz.gov.cn/xjbz/c101515/202507/record.html",
            content="国投新疆锂业有限公司 罗布泊盐湖老卤提锂综合利用扩能改造工程项目 若羌县",
            score=0.91,
            published_date="2025-07-15",
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage()

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        enable_official_record_pdf_fallback=False,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            search_phrases=["若羌 罗布泊 盐湖 环评 公示"],
        )
    )

    assert result.execution_state == "executed_with_evidence"
    assert result.document_count == 1
    assert (
        result.metadata["official_record_search_fallback"]["candidate_decisions"][0]["reason_code"]
        == "accepted_official_record_search_fallback"
    )


def test_official_record_search_fallback_skips_pdf_candidates_without_adapter() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        results=[
            TavilySearchResult(
                title="[PDF] 神木煤化工项目环境影响评价报告书",
                url="https://sthjt.shaanxi.gov.cn/sy/gs/202409/report.pdf",
                content="神木 煤化工 环境影响评价 报告书",
                score=0.94,
                published_date="2024-09-10",
            ),
            TavilySearchResult(
                title="神木煤化工项目环境影响评价公众参与公示",
                url="https://sthjt.shaanxi.gov.cn/sy/gs/202409/record.html",
                content="神木 煤化工 环评 公示",
                score=0.88,
                published_date="2024-09-11",
            ),
        ]
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage()

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        enable_official_record_pdf_fallback=False,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            search_phrases=["神木 煤化工 环境影响评价 报告书"],
        )
    )

    decisions = result.metadata["official_record_search_fallback"]["candidate_decisions"]
    assert decisions[0]["reason_code"] == "official_record_pdf_requires_adapter"
    assert decisions[1]["reason_code"] == "accepted_official_record_search_fallback"
    assert result.execution_state == "executed_with_evidence"
    assert extraction_provider.requests[0].inputs[0].url.endswith("record.html")


def test_official_record_search_fallback_does_not_treat_broad_gov_cn_as_local_match() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title="新能源汽车电池冷却零部件生产项目环境影响报告表的审批前公示",
            url="https://www.zongyang.gov.cn/openness/OpennessContent/show/1075883.html",
            content="枞阳县 新能源汽车 电池冷却 零部件 环境影响报告表 审批前公示",
            score=0.9,
            published_date="2026-02-01",
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage()

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["gov.cn", "sthjj.hefei.gov.cn", "zrzy.hefei.gov.cn"],
            search_phrases=["合肥 新能源汽车 环评 公示"],
        )
    )

    assert result.execution_state == "executed_without_evidence"
    assert (
        result.metadata["official_record_search_fallback"]["candidate_decisions"][0]["reason_code"]
        == "official_record_search_off_domain"
    )
    assert extraction_provider.requests == []


def test_official_record_lane_accepts_parent_department_local_title_match() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title="合肥：深挖盘存法理兼顾租让并举 - 安徽省自然资源厅",
            url="https://zrzyt.ah.gov.cn/public/21691/149015791.html",
            content="合肥 新能源汽车 土地 自然资源 存量项目 盘活",
            score=0.82,
            published_date="2025-12-01",
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage(
        raw_text="安徽省自然资源厅 合肥 新能源汽车 土地 自然资源 存量项目 盘活"
    )

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["zrzyt.ah.gov.cn", "zrzy.hefei.gov.cn"],
            search_phrases=["合肥市 新能源汽车 土地出让 自然资源"],
        )
    )

    decision = result.metadata["official_record_search_fallback"]["candidate_decisions"][0]
    assert result.execution_state == "executed_with_evidence"
    assert decision["reason_code"] == "accepted_official_record_search_fallback"
    assert result.documents[0].metadata["evidence_quality"]["local_region_match_type"] == (
        "parent_local"
    )
    assert result.documents[0].metadata["evidence_quality"]["parent_evidence_only"] is True
    assert result.documents[0].metadata["evidence_quality"]["local_claim_allowed"] is False


def test_official_record_lane_marks_regulatory_record_source_class() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title="合肥新能源汽车项目环境影响评价文件审批前公示",
            url="https://sthjj.hefei.gov.cn/public/record-approval.html",
            content="合肥 新能源汽车 环境影响评价 审批 公示",
            score=0.88,
            published_date="2026-01-12",
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage(
        raw_text="合肥 新能源汽车 环境影响评价 审批 公示 项目建设"
    )

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["sthjj.hefei.gov.cn", "zrzy.hefei.gov.cn"],
            search_phrases=["合肥 新能源汽车 环评 审批 公示"],
        )
    )

    assert result.execution_state == "executed_with_evidence"
    assert result.documents[0].metadata["source_class"] == "environmental_or_land_record"
    assert result.documents[0].metadata["source_classes"] == [
        "environmental_or_land_record",
        "regulatory_record",
    ]
    assert result.normalized_documents[0].metadata["source_classes"] == [
        "environmental_or_land_record",
        "regulatory_record",
    ]


def test_official_record_lane_accepts_national_scope_local_record_detail() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title=(
                "\u5173\u4e8e\u53d7\u7406\u90d1\u5dde\u822a\u7a7a\u6e2f\u533a"
                "\u7a7a\u6e2f\u667a\u6167\u57ce\u5e02\u7b97\u529b\u4e2d\u5fc3"
                "110\u5343\u4f0f\u7528\u6237\u63a5\u5165\u5de5\u7a0b"
                "\u73af\u5883\u5f71\u54cd\u8bc4\u4ef7\u6587\u4ef6"
                "\u7684\u516c\u793a"
            ),
            url="https://m.zzhkgq.gov.cn/2025/03-24/3486332.html",
            content=(
                "\u90d1\u5dde\u822a\u7a7a\u6e2f\u533a "
                "\u7b97\u529b\u4e2d\u5fc3 \u73af\u8bc4 "
                "\u53d7\u7406 \u516c\u793a"
            ),
            score=0.9,
            published_date="2025-03-24",
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage(
        raw_text=(
            "\u90d1\u5dde\u822a\u7a7a\u6e2f\u533a "
            "\u7a7a\u6e2f\u667a\u6167\u57ce\u5e02\u7b97\u529b\u4e2d\u5fc3 "
            "\u73af\u5883\u5f71\u54cd\u8bc4\u4ef7 \u53d7\u7406 \u516c\u793a"
        )
    )

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["gov.cn", "mee.gov.cn", "mnr.gov.cn", "ndrc.gov.cn"],
            search_phrases=[
                "\u5168\u56fd \u7b97\u529b \u73af\u8bc4 \u516c\u793a",
            ],
        )
    )

    decision = result.metadata["official_record_search_fallback"]["candidate_decisions"][0]
    assert result.execution_state == "executed_with_evidence"
    assert decision["reason_code"] == "accepted_official_record_search_fallback"
    assert result.documents[0].metadata["source_classes"] == [
        "environmental_or_land_record",
        "regulatory_record",
    ]


def test_official_record_lane_accepts_drc_regulatory_record_snippet() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title="\u751f\u6001\u6587\u660e-\u5df4\u5f66\u6dd6\u5c14\u5e02\u53d1\u6539\u59d4",
            url="https://fgw.bynr.gov.cn/stwm/202512/t20251218_734890.html",
            content=(
                "\u5185\u8499\u53e4 \u73b0\u4ee3\u7164\u5316\u5de5 "
                "\u8282\u80fd\u5ba1\u67e5 \u6279\u590d \u9879\u76ee"
            ),
            score=0.86,
            published_date="2025-12-18",
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage(
        raw_text=(
            "\u5185\u8499\u53e4 \u73b0\u4ee3\u7164\u5316\u5de5 "
            "\u8282\u80fd\u5ba1\u67e5 \u6279\u590d \u9879\u76ee"
        )
    )

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=[
                "gov.cn",
                "fgw.nmg.gov.cn",
                "nmg.gov.cn",
                "sthjt.nmg.gov.cn",
            ],
            search_phrases=[
                "\u5185\u8499\u53e4 \u73b0\u4ee3\u7164\u5316\u5de5 "
                "\u8282\u80fd\u5ba1\u67e5 \u6279\u590d",
            ],
        )
    )

    decision = result.metadata["official_record_search_fallback"]["candidate_decisions"][0]
    assert result.execution_state == "executed_with_evidence"
    assert decision["reason_code"] == "accepted_official_record_search_fallback"
    assert result.documents[0].metadata["source_classes"] == [
        "environmental_or_land_record",
        "regulatory_record",
    ]


def test_official_record_lane_accepts_region_matched_subprovincial_gov_domain() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title="鄂环审字〔2025〕36号 内蒙古煤基新材料项目环境影响评价批复",
            url="https://ordosdwgk.gov.cn/gk_128120/sthj/jsxmhjyxpj/202503/record.html",
            content="内蒙古 鄂尔多斯 煤基新材料 环境影响评价 批复",
            score=0.7,
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage(
        raw_text="内蒙古 鄂尔多斯 煤基新材料项目 环境影响评价 批复"
    )

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=[
                "fgw.nmg.gov.cn",
                "gov.cn",
                "nmg.gov.cn",
                "sthjt.nmg.gov.cn",
            ],
            search_phrases=[
                "内蒙古 绿氢 煤制烯烃 环评 公示",
                "内蒙古 煤基新材料 环境影响评价",
            ],
        )
    )

    assert result.execution_state == "executed_with_evidence"
    assert result.document_count == 1
    assert (
        result.metadata["official_record_search_fallback"]["candidate_decisions"][0][
            "reason_code"
        ]
        == "accepted_official_record_search_fallback"
    )


def test_official_record_lane_rejects_full_page_when_relevance_only_in_search_hint() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title="合肥生态环境建设项目公示",
            url="https://sthjj.hefei.gov.cn/zwgk/hpgs/149015791.html",
            content="合肥 新能源汽车 环评 公示 土地",
            score=0.87,
            published_date="2023-12-25",
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage(
        raw_text="合肥 自然资源 土地利用案例 低效用地再开发 项目收储 " * 20
    )

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["zrzyt.ah.gov.cn", "sthjj.hefei.gov.cn"],
            search_phrases=["合肥 新能源汽车 环评 公示"],
        )
    )

    assert result.execution_state == "executed_without_evidence"
    assert (
        result.metadata["official_record_search_fallback"]["weak_document_rejections"][0][
            "reason_code"
        ]
        == "official_record_relevance_mismatch"
    )


def test_official_record_lane_rejects_late_boilerplate_relevance_match() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title="合肥生态环境建设项目公示",
            url="https://sthjj.hefei.gov.cn/zwgk/hpgs/149015791.html",
            content="合肥 新能源汽车 土地出让 自然资源",
            score=0.87,
            published_date="2023-12-25",
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage(
        raw_text=("合肥 自然资源 土地利用案例 低效用地再开发 项目收储 " * 300)
        + " 相关新闻 新能源汽车"
    )

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["zrzyt.ah.gov.cn", "sthjj.hefei.gov.cn"],
            search_phrases=["合肥 新能源汽车 土地出让 自然资源"],
        )
    )

    assert result.execution_state == "executed_without_evidence"
    assert (
        result.metadata["official_record_search_fallback"]["weak_document_rejections"][0][
            "reason_code"
        ]
        == "official_record_relevance_mismatch"
    )


def test_official_record_lane_rejects_generic_case_page_without_record_subject() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title="合肥自然资源土地节约集约利用典型案例",
            url="https://zrzyt.ah.gov.cn/ztlm/stdjyjylyzhggsdgzzt/dxal/149015791.html",
            content="合肥 新能源汽车 土地出让 自然资源 典型案例",
            score=0.87,
            published_date="2023-12-25",
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage(
        raw_text=(
            "合肥 自然资源 土地节约集约利用 典型案例 "
            "新能源汽车产业项目用地需求 低效用地再开发 "
        )
        * 20
    )

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["zrzyt.ah.gov.cn", "sthjj.hefei.gov.cn"],
            search_phrases=["合肥 新能源汽车 土地出让 自然资源"],
        )
    )

    assert result.execution_state == "executed_without_evidence"
    assert extraction_provider.requests == []
    assert (
        result.metadata["official_record_search_fallback"]["candidate_decisions"][0]["reason_code"]
        == "generic_official_record_case_page"
    )


def test_official_record_search_rejects_generic_case_page_before_extraction() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title="\u5408\u80a5\u81ea\u7136\u8d44\u6e90\u571f\u5730\u8282\u7ea6\u96c6\u7ea6\u5229\u7528\u5178\u578b\u6848\u4f8b",
            url="https://zrzyt.ah.gov.cn/ztlm/stdjyjylyzhggsdgzzt/dxal/149015791.html",
            content=(
                "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                "\u571f\u5730\u51fa\u8ba9 \u81ea\u7136\u8d44\u6e90 "
                "\u5178\u578b\u6848\u4f8b"
            ),
            score=0.87,
            published_date="2023-12-25",
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage()

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["zrzyt.ah.gov.cn", "sthjj.hefei.gov.cn"],
            search_phrases=[
                "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                "\u571f\u5730\u51fa\u8ba9 \u81ea\u7136\u8d44\u6e90"
            ],
        )
    )

    fallback = result.metadata["official_record_search_fallback"]
    assert result.execution_state == "executed_without_evidence"
    assert extraction_provider.requests == []
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "generic_official_record_case_page"
    )


def test_official_record_search_rejects_site_search_pages_before_extraction() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title="\u667a\u80fd\u641c\u7d22-\u5b89\u5fbd\u7701\u53d1\u5c55\u548c\u6539\u9769\u59d4\u5458\u4f1a",
            url="https://fzggw.ah.gov.cn/site/search/49631471?keywords=test",
            content=(
                "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                "\u9879\u76ee\u5907\u6848 \u5ba1\u6279 \u516c\u793a"
            ),
            score=0.81,
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage()

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["gov.cn", "fgw.hefei.gov.cn", "fzggw.ah.gov.cn"],
            search_phrases=[
                "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                "\u9879\u76ee\u5907\u6848 \u5ba1\u6279"
            ],
        )
    )

    fallback = result.metadata["official_record_search_fallback"]
    assert result.execution_state == "executed_without_evidence"
    assert extraction_provider.requests == []
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "generic_official_record_navigation"
    )


def test_official_record_lane_rejects_unrelated_subprovincial_gov_domain() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title=(
                "嘉祥县人民政府 他山之石 "
                "合肥：极优服务、极简审批、极大保障深化营商环境改革创新模式"
            ),
            url="http://jiaxiang.gov.cn/art/2024/4/9/art_106987_2763430.html",
            content="合肥 新能源汽车 项目备案 审批",
            score=0.83,
            published_date="2024-04-09",
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage(
        raw_text="合肥 新能源汽车 项目备案 审批 公示 " * 20
    )

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["gov.cn", "zrzyt.ah.gov.cn", "sthjj.hefei.gov.cn"],
            search_phrases=["合肥市 新能源汽车 项目备案 审批"],
        )
    )

    fallback = result.metadata["official_record_search_fallback"]
    assert result.execution_state == "executed_without_evidence"
    assert extraction_provider.requests == []
    assert fallback["candidate_decisions"][0]["reason_code"] == "official_record_search_off_domain"


def test_official_record_search_rejects_external_local_gov_case_mentioning_target_region() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title=(
                "\u5609\u7965\u53bf\u4eba\u6c11\u653f\u5e9c \u4ed6\u5c71\u4e4b\u77f3 "
                "\u5408\u80a5\uff1a\u6781\u4f18\u670d\u52a1\u3001\u6781\u7b80"
                "\u5ba1\u6279\u3001\u6781\u5927\u4fdd\u969c"
            ),
            url="http://jiaxiang.gov.cn/art/2024/4/9/art_106987_2763430.html",
            content=(
                "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                "\u9879\u76ee\u5907\u6848 \u5ba1\u6279 \u516c\u793a"
            ),
            score=0.83,
            published_date="2024-04-09",
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage()

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["gov.cn", "fgw.hefei.gov.cn", "sthjj.hefei.gov.cn"],
            search_phrases=[
                "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                "\u9879\u76ee\u5907\u6848 \u5ba1\u6279"
            ],
        )
    )

    fallback = result.metadata["official_record_search_fallback"]
    assert result.execution_state == "executed_without_evidence"
    assert extraction_provider.requests == []
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "official_record_search_off_domain"
    )


def test_official_record_search_rejects_other_city_department_for_exact_city_task() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title="\u6c60\u5dde\u5e02\u751f\u6001\u73af\u5883\u5c40",
            url="https://sthjj.chizhou.gov.cn/News/show/762641.html",
            content=(
                "\u5408\u80a5\u5e02 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                "\u73af\u8bc4 \u516c\u793a \u9879\u76ee"
            ),
            score=0.82,
        )
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage()

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["gov.cn", "sthjj.hefei.gov.cn", "sthjt.ah.gov.cn"],
            search_phrases=[
                "\u5408\u80a5\u5e02 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
                "\u73af\u8bc4 \u516c\u793a"
            ],
        )
    )

    fallback = result.metadata["official_record_search_fallback"]
    assert result.execution_state == "executed_without_evidence"
    assert extraction_provider.requests == []
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "official_record_search_off_domain"
    )


def test_official_record_document_filter_rejects_unrelated_subprovincial_gov_domain() -> None:
    task = _task(
        "official_record",
        include_domains=["gov.cn", "zrzyt.ah.gov.cn", "sthjj.hefei.gov.cn"],
        search_phrases=[
            "\u5408\u80a5\u5e02 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
            "\u9879\u76ee\u5907\u6848 \u5ba1\u6279"
        ],
    )
    document = RawDocument(
        document_id="off_domain_record_doc",
        source_id="search_assisted_official_record_fallback",
        title="art_106987_2763430.html",
        source_uri="http://jiaxiang.gov.cn/art/2024/4/9/art_106987_2763430.html",
        raw_text=(
            "\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 "
            "\u9879\u76ee\u5907\u6848 \u5ba1\u6279 \u516c\u793a "
        )
        * 20,
        metadata={
            "title_hint": (
            "\u5609\u7965\u53bf\u4eba\u6c11\u653f\u5e9c \u4ed6\u5c71\u4e4b\u77f3 "
            "\u5408\u80a5\uff1a\u6781\u4f18\u670d\u52a1\u3001\u6781\u7b80"
            "\u5ba1\u6279\u3001\u6781\u5927\u4fdd\u969c"
            )
        },
    )

    assert _weak_direct_document_reason(task, document) == "official_record_domain_mismatch"


def test_official_record_lane_tries_third_phrase_when_first_two_have_no_candidates() -> None:
    search_provider = _SequentialOfficialRecordSearchProvider(
        [
            [
                TavilySearchResult(
                    title="[PDF] 叶城县锂辉石项目环境影响评价报告书",
                    url="https://www.kashi.gov.cn/files/yecheng-lithium.pdf",
                    content="叶城 锂辉石 环评 报告书",
                    score=0.92,
                )
            ],
            [
                TavilySearchResult(
                    title="[PDF] 西藏高纯锂盐生产线环境影响评价报告书",
                    url="https://ee.xizang.gov.cn/gsgg/lithium-salt.pdf",
                    content="西藏 锂盐 环境影响评价 报告书",
                    score=0.91,
                )
            ],
            [
                TavilySearchResult(
                    title="巴州生态环境局环评科关于建设项目环境影响评价文件受理情况的公示",
                    url="https://www.xjbz.gov.cn/xjbz/c101515/202507/record.html",
                    content="若羌 罗布泊盐湖 锂钾 项目 环境影响评价 公示",
                    score=0.88,
                )
            ],
        ]
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage()

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["xjbz.gov.cn", "mee.gov.cn"],
            search_phrases=[
                "若羌 罗布泊 盐湖 环评 公示",
                "若羌 盐湖锂钾 项目备案 环评",
                "若羌 锂钾 矿产资源 总体规划",
            ],
        )
    )

    assert len(search_provider.requests) == 3
    assert result.execution_state == "executed_with_evidence"
    assert result.document_count == 1
    decisions = result.metadata["official_record_search_fallback"]["candidate_decisions"]
    assert decisions[0]["reason_code"] == "official_record_search_off_domain"
    assert decisions[1]["reason_code"] == "official_record_search_off_domain"
    assert decisions[2]["reason_code"] == "accepted_official_record_search_fallback"


def test_official_record_search_fallback_respects_search_credit_budget() -> None:
    search_provider = _SequentialOfficialRecordSearchProvider(
        [
            [
                TavilySearchResult(
                    title="[PDF] 叶城县锂辉石项目环境影响评价报告书",
                    url="https://www.kashi.gov.cn/files/yecheng-lithium.pdf",
                    content="叶城 锂辉石 环评 报告书",
                    score=0.92,
                )
            ],
            [
                TavilySearchResult(
                    title="[PDF] 西藏高纯锂盐生产线环境影响评价报告书",
                    url="https://ee.xizang.gov.cn/gsgg/lithium-salt.pdf",
                    content="西藏 锂盐 环境影响评价 报告书",
                    score=0.91,
                )
            ],
            [
                TavilySearchResult(
                    title="巴州生态环境局环评科关于建设项目环境影响评价文件受理情况的公示",
                    url="https://www.xjbz.gov.cn/xjbz/c101515/202507/record.html",
                    content="若羌 罗布泊盐湖 锂钾 项目 环境影响评价 公示",
                    score=0.88,
                )
            ],
        ]
    )
    extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage()

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=extraction_provider,
        max_official_record_fallback_candidates=1,
        max_official_record_fallback_search_credits=2,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["xjbz.gov.cn", "mee.gov.cn"],
            search_phrases=[
                "若羌 罗布泊 盐湖 环评 公示",
                "若羌 盐湖锂钾 项目备案 环评",
                "若羌 锂钾 矿产资源 总体规划",
            ],
        )
    )

    fallback = result.metadata["official_record_search_fallback"]
    assert len(search_provider.requests) == 2
    assert extraction_provider.requests == []
    assert result.execution_state == "executed_without_evidence"
    assert fallback["status"] == "search_credit_budget_exhausted"
    assert fallback["stop_reason"] == "search_credit_budget_exhausted"
    assert fallback["max_estimated_tavily_credits"] == 2
    assert fallback["budget_state"]["used_search_credits"] == 2
    assert fallback["budget_state"]["max_search_credits"] == 2


def test_official_record_pdf_candidate_uses_static_pdf_extraction() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title=(
                "[PDF] \u82e5\u7f8c\u76d0\u6e56\u9502\u94be\u9879\u76ee"
                "\u73af\u5883\u5f71\u54cd\u8bc4\u4ef7\u62a5\u544a\u4e66"
            ),
            url="https://www.xjbz.gov.cn/files/ruoqiang-lithium-eia.pdf",
            content=(
                "\u82e5\u7f8c \u76d0\u6e56\u9502\u94be \u73af\u8bc4 "
                "\u73af\u5883\u5f71\u54cd\u8bc4\u4ef7 \u62a5\u544a\u4e66"
            ),
            score=0.9,
            published_date="2026-01-03",
        )
    )
    html_extraction_provider = _FakeOfficialRecordExtractionProviderWithHintOnlyPage()
    pdf_download_service = _FakeOfficialRecordPdfDownloadService()
    pdf_text_service = _FakeOfficialRecordPdfTextService()

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_extraction_provider=html_extraction_provider,
        official_record_pdf_download_service=pdf_download_service,
        official_record_pdf_text_service=pdf_text_service,
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["xjbz.gov.cn", "mee.gov.cn"],
            search_phrases=[
                (
                    "\u82e5\u7f8c \u76d0\u6e56\u9502\u94be "
                    "\u73af\u8bc4 \u516c\u793a"
                )
            ],
        )
    )

    fallback = result.metadata["official_record_search_fallback"]
    assert result.execution_state == "executed_with_evidence"
    assert html_extraction_provider.requests == []
    assert pdf_download_service.calls
    assert pdf_text_service.calls
    assert fallback["candidate_decisions"][0]["reason_code"] == (
        "accepted_official_record_pdf_fallback"
    )
    assert fallback["pdf_extraction"]["succeeded"] == 1
    assert result.documents[0].metadata["from_pdf_attachment"] is True
    assert result.evidence_items


def test_official_record_relevance_does_not_trust_discovery_query_only() -> None:
    task = _task(
        "official_record",
        include_domains=["sthjj.huhhot.gov.cn"],
        search_phrases=[
            (
                "\u5185\u8499\u53e4 \u7eff\u6c22 \u7164\u5236\u70ef\u70c3 "
                "\u73af\u8bc4 \u516c\u793a"
            )
        ],
    )
    unrelated_pdf_cover = RawDocument(
        document_id="official_record_unrelated_pdf_cover",
        source_id="search_assisted_official_record_fallback",
        title="\u73af\u5883\u5f71\u54cd\u62a5\u544a\u4e66",
        source_uri=(
            "http://sthjj.huhhot.gov.cn/ywgz/hjyxpj/xmslqk/202410/"
            "P020250304596707515162.pdf"
        ),
        raw_text=(
            "\u5185\u8499\u53e4\u5723\u9492\u79d1\u6280\u65b0\u80fd\u6e90"
            "\u6709\u9650\u8d23\u4efb\u516c\u53f8\u9502\u7535\u6b63\u6781"
            "\u6750\u6599\u9879\u76ee \u73af\u5883\u5f71\u54cd\u8bc4\u4ef7"
            "\u62a5\u544a\u4e66"
        ),
        metadata={
            "discovery_query": (
                "\u5185\u8499\u53e4 \u7eff\u6c22 \u7164\u5236\u70ef\u70c3 "
                "\u73af\u8bc4 \u516c\u793a"
            ),
            "source_class": "environmental_or_land_record",
        },
    )

    assert (
        _weak_direct_document_reason(task, unrelated_pdf_cover)
        == "official_record_relevance_mismatch"
    )


def test_official_record_pdf_failure_is_reported_as_evidence_gap() -> None:
    search_provider = _FakeOfficialRecordSearchProvider(
        result=TavilySearchResult(
            title=(
                "[PDF] \u82e5\u7f8c\u76d0\u6e56\u9502\u94be\u9879\u76ee"
                "\u73af\u5883\u5f71\u54cd\u8bc4\u4ef7\u62a5\u544a\u4e66"
            ),
            url="https://www.xjbz.gov.cn/files/ruoqiang-lithium-eia.pdf",
            content=(
                "\u82e5\u7f8c \u76d0\u6e56\u9502\u94be \u73af\u8bc4 "
                "\u73af\u5883\u5f71\u54cd\u8bc4\u4ef7 \u62a5\u544a\u4e66"
            ),
            score=0.9,
            published_date="2026-01-03",
        )
    )

    result = DirectStructuredLaneExecutor(
        source_registry=SourceRegistry(),
        official_record_search_provider=search_provider,
        official_record_pdf_download_service=_FailingOfficialRecordPdfDownloadService(),
        max_official_record_fallback_candidates=1,
    ).execute_task(
        _task(
            "official_record",
            include_domains=["xjbz.gov.cn", "mee.gov.cn"],
            search_phrases=[
                (
                    "\u82e5\u7f8c \u76d0\u6e56\u9502\u94be "
                    "\u73af\u8bc4 \u516c\u793a"
                )
            ],
        )
    )

    fallback = result.metadata["official_record_search_fallback"]
    assert result.execution_state == "executed_without_evidence"
    assert result.status == ToolStatus.PARTIAL
    assert fallback["status"] == "extracted_without_usable_evidence"
    assert fallback["pdf_extraction"]["failed"] == 1
    assert fallback["pdf_extraction"]["failure_classes"]["pdf_download_failed"] == 1
    assert result.errors[0].detail["extraction_failure_class"] == "pdf_or_download"


def test_disclosure_lane_rejects_generic_homepage_and_non_disclosure_pages() -> None:
    cninfo = _FakeProfileAdapter(
        _profile(
            "cn_exchange_cninfo_announcement_v1",
            category=SourceCategory.EXCHANGE_ANNOUNCEMENT,
            line_family=LineFamily.EXCHANGE,
            info_type=InfoType.REGULATORY_ANNOUNCEMENT,
        ),
        document_title="首页",
    )
    registry = _registry_with(cninfo)

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        enable_disclosure_api_fallback=False,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
    ).execute_task(_task("enterprise_disclosure", search_phrases=["算力 上市公司 公告"]))

    assert result.execution_state == "executed_without_evidence"
    assert result.document_count == 0
    assert result.metadata["missing_company_hint"] is False
    assert result.metadata["rejected_document_count"] == 1
    assert (
        result.metadata["weak_document_rejections"][0]["reason_code"]
        == "generic_disclosure_homepage"
    )


def test_direct_executor_records_missing_company_hint_for_disclosure_without_company() -> None:
    cninfo = _FakeProfileAdapter(
        _profile(
            "cn_exchange_cninfo_announcement_v1",
            category=SourceCategory.EXCHANGE_ANNOUNCEMENT,
            line_family=LineFamily.EXCHANGE,
            info_type=InfoType.REGULATORY_ANNOUNCEMENT,
        ),
        document_title="中信海直：低空经济业务公告",
    )
    registry = _registry_with(cninfo)

    result = DirectStructuredLaneExecutor(source_registry=registry).execute_task(
        _task(
            "enterprise_disclosure",
            search_phrases=["低空经济 上市公司 公告"],
        )
    )

    assert result.execution_state == "executed_with_evidence"
    assert result.source_ids_selected == ["cn_exchange_cninfo_announcement_v1"]
    assert result.metadata["missing_company_hint"] is False


def test_disclosure_lane_uses_direct_cninfo_fallback_after_generic_exchange_pages() -> None:
    cninfo = _FakeProfileAdapter(
        _profile(
            "cn_exchange_cninfo_announcement_v1",
            category=SourceCategory.EXCHANGE_ANNOUNCEMENT,
            line_family=LineFamily.EXCHANGE,
            info_type=InfoType.REGULATORY_ANNOUNCEMENT,
        ),
        document_title="首页",
    )
    registry = SourceRegistry()
    registry.register_profile(cninfo.profile, adapter=cninfo)
    fallback_provider = _FakeDisclosureApiProvider()

    result = DirectStructuredLaneExecutor(
        source_registry=registry,
        disclosure_api_provider=fallback_provider,
        max_profiles_per_lane=1,
        max_documents_per_profile=1,
        max_evidence_per_profile=1,
    ).execute_task(
        _task(
            "enterprise_disclosure",
            search_phrases=["低空经济 上市公司 公告"],
        )
    )

    assert fallback_provider.requests
    assert result.execution_state == "executed_with_evidence"
    assert result.document_count == 1
    assert result.evidence_count == 1
    assert result.metadata["disclosure_api_fallback"]["status"] == "evidence_found"
    assert result.metadata["disclosure_api_fallback"]["estimated_tavily_credits"] == 0


def test_direct_executor_returns_skipped_no_adapter_when_lane_has_no_available_profiles() -> None:
    result = DirectStructuredLaneExecutor(source_registry=SourceRegistry()).execute_task(
        _task("data_metrics")
    )

    assert result.execution_state == "skipped_no_adapter"
    assert result.source_ids_selected == []
    assert result.metadata["reason_code"] == "direct_adapter_not_available"
