from __future__ import annotations

from packages.sources.crawl4ai_extraction import (
    Crawl4AIExtractionRequest,
    Crawl4AIExtractionResponse,
)
from packages.sources.enums import (
    GovernanceAxis,
    InfoType,
    LineFamily,
    RegionalLevel,
    ToolErrorCode,
    ToolStatus,
)
from packages.sources.query_decomposition import QueryDecompositionTask
from packages.sources.schemas import DocumentSection, NormalizedDocument, RawDocument, ToolError
from packages.sources.search_assisted_domestic import (
    SEARCH_ASSISTED_SOURCE_ID,
    DomesticSearchAssistedResponse,
    SearchAssistedDomesticOrchestrator,
    convert_search_assisted_documents_to_evidence_items,
    convert_search_response_to_evidence_items,
)
from packages.sources.search_discovery import TavilySearchResponse, TavilySearchResult


class _FakeSearchAdapter:
    def __init__(self, responses: list[TavilySearchResponse]) -> None:
        self.responses = responses
        self.called = 0

    def search_task(self, task: QueryDecompositionTask) -> list[TavilySearchResponse]:
        del task
        self.called += 1
        return self.responses


class _FakeExtractionService:
    def __init__(self, response: Crawl4AIExtractionResponse) -> None:
        self.response = response
        self.calls: list[Crawl4AIExtractionRequest] = []

    def extract(self, request: Crawl4AIExtractionRequest) -> Crawl4AIExtractionResponse:
        self.calls.append(request)
        return self.response


class _SequencedSearchAdapter:
    def __init__(self, responses_by_call: list[list[TavilySearchResponse]]) -> None:
        self.responses_by_call = responses_by_call
        self.called = 0

    def search_task(self, task: QueryDecompositionTask) -> list[TavilySearchResponse]:
        del task
        index = min(self.called, len(self.responses_by_call) - 1)
        self.called += 1
        return self.responses_by_call[index]


def _build_task(
    *,
    task_id: str,
    task_family: str,
    execution_bucket: str = "search_assisted_sources",
    source_cluster: str = "central_policy_backbone",
    regional_level: RegionalLevel = RegionalLevel.NATIONAL,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    search_phrases: list[str] | None = None,
) -> QueryDecompositionTask:
    info_type = (
        InfoType.POLICY_NOTICE
        if task_family != "industry_topic"
        else InfoType.INDUSTRY_REPORT
    )
    return QueryDecompositionTask(
        task_id=task_id,
        task_family=task_family,
        tiaokuai_axis=GovernanceAxis.LINE,
        line_family=LineFamily.POLICY if task_family != "industry_topic" else LineFamily.INDUSTRY,
        regional_level=regional_level,
        info_type=info_type,
        execution_bucket=execution_bucket,
        source_cluster=source_cluster,
        include_domains=include_domains or [],
        exclude_domains=exclude_domains or [],
        search_phrases=search_phrases or ["low altitude economy policy"],
        evidence_goal="collect evidence",
        fallback_path="fallback-to-direct",
    )


def _build_extraction_success() -> Crawl4AIExtractionResponse:
    raw_document = RawDocument(
        document_id="doc_1",
        source_id="search_assisted_domestic",
        title="Policy page",
        source_uri="https://www.gov.cn/zhengce/content.html",
        raw_text="Policy body.",
    )
    normalized_document = NormalizedDocument(
        document_id="doc_1",
        source_id="search_assisted_domestic",
        title="Policy page",
        summary="Policy body.",
        sections=[
            DocumentSection(
                section_id="doc_1_sec_1",
                heading="Summary",
                text="Policy body.",
                order_index=0,
            )
        ],
    )
    return Crawl4AIExtractionResponse(
        status=ToolStatus.SUCCESS,
        documents=[raw_document],
        normalized_documents=[normalized_document],
        metadata={"requested": 1, "succeeded": 1, "failed": 0},
    )


def _build_extraction_empty() -> Crawl4AIExtractionResponse:
    return Crawl4AIExtractionResponse(
        status=ToolStatus.ERROR,
        documents=[],
        normalized_documents=[],
        metadata={"requested": 0, "succeeded": 0, "failed": 0},
    )


def _build_extraction_failures(urls: list[str]) -> Crawl4AIExtractionResponse:
    return Crawl4AIExtractionResponse(
        status=ToolStatus.ERROR,
        documents=[],
        normalized_documents=[],
        errors=[
            ToolError(
                code=ToolErrorCode.INTERNAL_ERROR,
                message="Blocked by anti-bot protection: minimal_text",
                retryable=True,
                detail={"url": url},
            )
            for url in urls
        ],
        metadata={
            "provider": "crawl4ai",
            "requested": len(urls),
            "succeeded": 0,
            "failed": len(urls),
        },
    )


def test_orchestrator_filters_off_domain_and_attachment_candidates() -> None:
    task = _build_task(
        task_id="policy_1",
        task_family="policy_direction",
        include_domains=["gov.cn"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="low altitude economy policy",
                results=[
                    TavilySearchResult(
                        title="off-domain",
                        url="https://example.com/policy.html",
                        content="off-domain",
                    ),
                    TavilySearchResult(
                        title="attachment",
                        url="https://www.gov.cn/files/policy.xlsx",
                        content="attachment",
                    ),
                    TavilySearchResult(
                        title="search page",
                        url="https://www.gov.cn/site/search/123?keywords=noise",
                        content="site search page",
                    ),
                    TavilySearchResult(
                        title="search subdomain",
                        url="https://so.gov.cn/s?qt=policy",
                        content="search subdomain page",
                    ),
                    TavilySearchResult(
                        title="official",
                        url="https://www.gov.cn/zhengce/content.html",
                        content="official page",
                    ),
                ],
            )
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())

    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )
    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.SUCCESS
    assert len(response.normalized_documents) == 1
    assert len(extraction_service.calls) == 1
    assert [item.url for item in extraction_service.calls[0].inputs] == [
        "https://www.gov.cn/zhengce/content.html"
    ]
    reason_codes = {item.reason_code for item in response.candidate_decisions}
    assert "off_domain_candidate" in reason_codes
    assert "attachment_first_candidate" in reason_codes
    assert "non_evidence_navigation_candidate" in reason_codes
    assert "accepted_official_or_allowlisted_domain" in reason_codes


def test_real_estate_policy_task_does_not_widen_to_all_gov_cn() -> None:
    task = _build_task(
        task_id="policy_real_estate_1",
        task_family="policy_direction",
        include_domains=["www.gov.cn", "mohurd.gov.cn", "ndrc.gov.cn", "stats.gov.cn"],
        search_phrases=["房地产 去库存 城中村改造 三大工程 住房城乡建设部"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="房地产 去库存 城中村改造 三大工程 住房城乡建设部",
                results=[
                    TavilySearchResult(
                        title="local housing page",
                        url="https://jw.shenyang.gov.cn/xwzx/policy.html",
                        content="房地产 去库存 城中村改造 三大工程",
                    ),
                    TavilySearchResult(
                        title="central housing page",
                        url="https://www.mohurd.gov.cn/gongkai/policy.html",
                        content="房地产 去库存 城中村改造 三大工程",
                    ),
                ],
            )
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.SUCCESS
    assert [item.url for item in extraction_service.calls[0].inputs] == [
        "https://www.mohurd.gov.cn/gongkai/policy.html"
    ]
    decisions_by_domain = {item.domain: item for item in response.candidate_decisions}
    assert decisions_by_domain["jw.shenyang.gov.cn"].decision == "reject"
    assert decisions_by_domain["jw.shenyang.gov.cn"].reason_code == "off_domain_candidate"


def test_real_estate_policy_task_strips_bare_gov_cn_to_prevent_local_leakage() -> None:
    task = _build_task(
        task_id="policy_real_estate_2",
        task_family="policy_direction",
        include_domains=["gov.cn", "www.gov.cn", "mohurd.gov.cn", "ndrc.gov.cn", "stats.gov.cn"],
        search_phrases=["房地产 去库存 城中村改造 三大工程 住房城乡建设部"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="房地产 去库存 城中村改造 三大工程 住房城乡建设部",
                results=[
                    TavilySearchResult(
                        title="local housing page",
                        url="https://www.hunan.gov.cn/topic/2025qglh/25lhgz/202503/t20250311_33607893.html",
                        content="房地产 去库存 城中村改造 三大工程",
                    ),
                    TavilySearchResult(
                        title="state council page",
                        url="https://www.gov.cn/zhengce/2025-06/01/content_xxxx.htm",
                        content="房地产 去库存 城中村改造 三大工程",
                    ),
                ],
            )
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.SUCCESS
    decisions_by_domain = {item.domain: item for item in response.candidate_decisions}
    assert decisions_by_domain["www.hunan.gov.cn"].decision == "reject"
    assert decisions_by_domain["www.hunan.gov.cn"].reason_code == "off_domain_candidate"
    assert [item.url for item in extraction_service.calls[0].inputs] == [
        "https://www.gov.cn/zhengce/2025-06/01/content_xxxx.htm"
    ]


def test_real_estate_policy_task_uses_official_seed_when_search_returns_no_central_hit() -> None:
    task = _build_task(
        task_id="policy_real_estate_seed",
        task_family="policy_direction",
        include_domains=["www.gov.cn", "mohurd.gov.cn", "ndrc.gov.cn", "stats.gov.cn"],
        search_phrases=["房地产 去库存 城中村改造 三大工程"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="房地产 去库存 城中村改造 三大工程",
                results=[
                    TavilySearchResult(
                        title="local housing page",
                        url="https://zjt.fujian.gov.cn/xxgk/gzdt/bmdt/noise.htm",
                        content="房地产 去库存 城中村改造 三大工程",
                    )
                ],
            )
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
        max_candidates=2,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.SUCCESS
    assert len(extraction_service.calls) == 1
    extracted_urls = [item.url for item in extraction_service.calls[0].inputs]
    assert extracted_urls == [
        "https://www.mohurd.gov.cn/xinwen/gzdt/art/2024/art_304_778875.html",
        (
            "https://www.mohurd.gov.cn/gongkai/zc/wjk/art/2025/"
            "art_2ab4d1ffd2aa4e91830f09715a659c6a.html"
        ),
    ]
    assert {item.discovery_provider for item in extraction_service.calls[0].inputs} == {
        "official_seed"
    }
    reason_codes = {item.reason_code for item in response.candidate_decisions}
    assert "off_domain_candidate" in reason_codes
    assert "accepted_official_seed_candidate" in reason_codes


def test_orchestrator_refuses_direct_structured_sources() -> None:
    task = _build_task(
        task_id="direct_1",
        task_family="enterprise_disclosure",
        execution_bucket="direct_structured_sources",
        source_cluster="official_disclosure_backbone",
    )
    search_adapter = _FakeSearchAdapter(responses=[])
    extraction_service = _FakeExtractionService(response=_build_extraction_success())

    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )
    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.ERROR
    assert response.errors
    assert response.errors[0].detail["reason_code"] == "direct_keep_boundary_violation"
    assert search_adapter.called == 0
    assert extraction_service.calls == []


def test_orchestrator_allows_city_and_park_fallback_discovery_tasks() -> None:
    local_tasks = [
        _build_task(
            task_id="city_1",
            task_family="local_rollout",
            regional_level=RegionalLevel.MUNICIPAL,
            source_cluster="province_or_city_backbone",
            include_domains=["sz.gov.cn", "gd.gov.cn"],
            search_phrases=["深圳 低空经济 政策"],
        ),
        _build_task(
            task_id="park_city_1",
            task_family="local_rollout",
            regional_level=RegionalLevel.MUNICIPAL,
            source_cluster="park_city_rollout_backbone",
            include_domains=["chengdu.gov.cn", "sc.gov.cn"],
            search_phrases=["成都 人工智能产业园区 政策 规划"],
        ),
    ]
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="fallback test",
                results=[
                    TavilySearchResult(
                        title="city official",
                        url="https://www.sz.gov.cn/zwgk/policy.html",
                        content="深圳低空经济政策",
                    ),
                    TavilySearchResult(
                        title="chengdu city official",
                        url="https://www.chengdu.gov.cn/zwgk/policy.html",
                        content="成都人工智能产业园区政策",
                    ),
                ],
            )
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )

    responses = [orchestrator.orchestrate_task(task) for task in local_tasks]

    assert [item.status for item in responses] == [ToolStatus.SUCCESS, ToolStatus.SUCCESS]
    assert responses[0].metadata["task_mode"] == "local_policy_city_county_fallback"
    assert responses[0].metadata["fallback_level"] == "exact_city"
    assert responses[0].metadata["local_claim_allowed"] is True
    assert responses[1].metadata["task_mode"] == "local_policy_city_county_fallback"
    assert responses[1].metadata["parent_evidence_only"] is True
    assert responses[1].metadata["local_claim_allowed"] is False
    assert responses[1].metadata["fallback_level"] == "city"
    assert search_adapter.called == 4
    assert len(extraction_service.calls) >= 2


def test_orchestrator_allows_local_rollout_generic_first_wave() -> None:
    task = _build_task(
        task_id="local_1",
        task_family="local_rollout",
        regional_level=RegionalLevel.PROVINCIAL,
        source_cluster="province_or_city_backbone",
        include_domains=["ah.gov.cn"],
        search_phrases=["anhui low altitude economy policy"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="anhui low altitude economy policy",
                results=[
                    TavilySearchResult(
                        title="provincial official",
                        url="https://www.ah.gov.cn/policy/article.html",
                        content="official local policy",
                    )
                ],
            )
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.SUCCESS
    assert response.metadata["task_mode"] == "local_policy_generic"
    assert len(extraction_service.calls) == 1
    assert response.documents[0].metadata["source_class"] == "local_government"
    assert response.documents[0].metadata["source_classes"] == [
        "local_government",
        "official_policy",
    ]
    assert response.normalized_documents[0].metadata["source_class"] == "local_government"
    assert response.normalized_documents[0].metadata["source_classes"] == [
        "local_government",
        "official_policy",
    ]


def test_orchestrator_allows_supplemental_association_topic_path() -> None:
    task = _build_task(
        task_id="industry_1",
        task_family="industry_topic",
        source_cluster="association_enhancement",
        include_domains=["caai.cn"],
        search_phrases=["low altitude economy association whitepaper"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="low altitude economy association whitepaper",
                results=[
                    TavilySearchResult(
                        title="supplemental",
                        url="https://www.caai.cn/whitepaper.html",
                        content="industry supplement",
                    ),
                    TavilySearchResult(
                        title="random cn",
                        url="https://noise.cn/report.html",
                        content="random cn should not pass supplemental allowlist",
                    ),
                    TavilySearchResult(
                        title="off-domain",
                        url="https://example.org/report.html",
                        content="noise",
                    ),
                ],
            )
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.SUCCESS
    assert response.metadata["task_mode"] == "supplemental_association_topic"
    assert len(extraction_service.calls) == 1
    assert [item.url for item in extraction_service.calls[0].inputs] == [
        "https://www.caai.cn/whitepaper.html"
    ]
    reason_codes = {item.reason_code for item in response.candidate_decisions}
    assert "off_domain_candidate" in reason_codes
    assert "accepted_official_or_allowlisted_domain" in reason_codes


def test_industry_topic_capacity_market_documents_expose_price_source_classes() -> None:
    task = _build_task(
        task_id="industry_capacity_1",
        task_family="industry_topic",
        source_cluster="association_enhancement",
        include_domains=["battery100.org"],
        search_phrases=["动力电池 产能 价格 最新 行业协会"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="动力电池 产能 价格 最新 行业协会",
                results=[
                    TavilySearchResult(
                        title="动力电池产业链价格与产能报告",
                        url="https://www.battery100.org/report.html",
                        content="行业协会发布动力电池价格、产能、出货量和市场数据。",
                    )
                ],
            )
        ]
    )
    raw_document = RawDocument(
        document_id="doc_industry_price",
        source_id="search_assisted_domestic",
        title="动力电池产业链价格与产能报告",
        source_uri="https://www.battery100.org/report.html",
        raw_text="行业协会发布动力电池价格、产能、出货量和市场数据。",
        metadata={
            "discovery_query": "动力电池 产能 价格 最新 行业协会",
            "final_url": "https://www.battery100.org/report.html",
        },
    )
    normalized_document = NormalizedDocument(
        document_id="doc_industry_price",
        source_id="search_assisted_domestic",
        title="动力电池产业链价格与产能报告",
        summary="行业协会发布动力电池价格、产能、出货量和市场数据。",
        sections=[
            DocumentSection(
                section_id="doc_industry_price_sec_1",
                heading="价格与产能",
                text="行业协会发布动力电池价格、产能、出货量和市场数据。",
                order_index=0,
            )
        ],
        metadata={
            "discovery_query": "动力电池 产能 价格 最新 行业协会",
            "final_url": "https://www.battery100.org/report.html",
        },
    )
    extraction_service = _FakeExtractionService(
        response=Crawl4AIExtractionResponse(
            status=ToolStatus.SUCCESS,
            documents=[raw_document],
            normalized_documents=[normalized_document],
            metadata={"requested": 1, "succeeded": 1, "failed": 0},
        )
    )
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )

    response = orchestrator.orchestrate_task(task)
    evidence_items = convert_search_response_to_evidence_items(task=task, response=response)

    assert response.status == ToolStatus.SUCCESS
    assert response.documents[0].metadata["source_classes"] == [
        "industry_report",
        "industry_association",
        "association_report",
        "price_data",
        "industry_price_capacity",
    ]
    assert response.documents[0].metadata["source_family_backbones"] == [
        "sector_quantitative_supplement_control"
    ]
    assert (
        response.documents[0].metadata["official_quantitative_obligation_satisfied"]
        is False
    )
    assert evidence_items[0].metadata["source_classes"] == [
        "industry_report",
        "industry_association",
        "association_report",
        "price_data",
        "industry_price_capacity",
    ]
    assert evidence_items[0].metadata["source_family_backbones"] == [
        "sector_quantitative_supplement_control"
    ]
    assert evidence_items[0].metadata["official_quantitative_obligation_satisfied"] is False


def test_industry_topic_rejects_generic_channel_pages() -> None:
    task = _build_task(
        task_id="industry_channel_1",
        task_family="industry_topic",
        source_cluster="association_enhancement",
        include_domains=["caam.org.cn"],
        search_phrases=["安徽 新能源汽车 行业协会 报告"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="安徽 新能源汽车 行业协会 报告",
                results=[
                    TavilySearchResult(
                        title="安徽新能源汽车产业链报告",
                        url="http://www.caam.org.cn/",
                        content="安徽新能源汽车产业链报告的协会首页入口。",
                    ),
                    TavilySearchResult(
                        title="行业政策",
                        url="http://www.caam.org.cn/hyzc",
                        content="中国汽车工业协会行业政策栏目，包含协会动态和导航入口。",
                    ),
                    TavilySearchResult(
                        title="安徽新能源汽车产业链报告",
                        url="http://www.caam.org.cn/chn/8/cate_82/con_5120764.html",
                        content="安徽新能源汽车产业链、销量、产量和供应链报告。",
                    ),
                ],
            )
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )

    response = orchestrator.orchestrate_task(task)

    decisions_by_url = {item.url: item for item in response.candidate_decisions}
    assert decisions_by_url["http://www.caam.org.cn/"].decision == "reject"
    assert (
        decisions_by_url["http://www.caam.org.cn/"].reason_code
        == "industry_topic_generic_channel_candidate"
    )
    assert decisions_by_url["http://www.caam.org.cn/hyzc"].decision == "reject"
    assert (
        decisions_by_url["http://www.caam.org.cn/hyzc"].reason_code
        == "industry_topic_generic_channel_candidate"
    )
    assert [item.url for item in extraction_service.calls[0].inputs] == [
        "http://www.caam.org.cn/chn/8/cate_82/con_5120764.html"
    ]


def test_orchestrator_q03_local_rollout_rejects_uav_domains() -> None:
    task = _build_task(
        task_id="q03_local_1",
        task_family="local_rollout",
        regional_level=RegionalLevel.PROVINCIAL,
        source_cluster="province_or_city_backbone",
        include_domains=["gd.gov.cn", "aopa.org.cn", "china-uav.cn"],
        search_phrases=["广东 人形机器人 产业 政策"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="广东 人形机器人 产业 政策",
                results=[
                    TavilySearchResult(
                        title="AOPA 低空经济论坛",
                        url="https://www.aopa.org.cn/forum.html",
                        content="通航 与 无人机 产业",
                    ),
                    TavilySearchResult(
                        title="UAV report",
                        url="https://www.china-uav.cn/report.html",
                        content="低空经济 产业政策",
                    ),
                    TavilySearchResult(
                        title="广东人形机器人产业政策",
                        url="https://www.gd.gov.cn/zwgk/policy.html",
                        content="广东 人形机器人 产业 发展",
                    ),
                ],
            )
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.SUCCESS
    assert len(extraction_service.calls) == 1
    assert [item.url for item in extraction_service.calls[0].inputs] == [
        "https://www.gd.gov.cn/zwgk/policy.html"
    ]
    rejected = {
        item.url: item.reason_code
        for item in response.candidate_decisions
        if item.decision == "reject"
    }
    assert rejected["https://www.aopa.org.cn/forum.html"] == "supplemental_used_in_primary_lane"
    assert rejected["https://www.china-uav.cn/report.html"] == "supplemental_used_in_primary_lane"


def test_orchestrator_city_fallback_records_gap_when_exact_local_missing() -> None:
    task = _build_task(
        task_id="city_gap_1",
        task_family="local_rollout",
        regional_level=RegionalLevel.MUNICIPAL,
        source_cluster="province_or_city_backbone",
        include_domains=["sz.gov.cn", "gd.gov.cn"],
        search_phrases=["深圳 低空经济 政策"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="深圳 低空经济 政策",
                results=[
                    TavilySearchResult(
                        title="广东省政策",
                        url="https://www.gd.gov.cn/zwgk/policy.html",
                        content="广东省低空经济政策",
                    )
                ],
            )
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.SUCCESS
    assert response.metadata["fallback_level"] == "province"
    assert response.metadata["parent_evidence_only"] is True
    assert response.metadata["local_claim_allowed"] is False
    assert response.metadata["coverage_gap_reason"] == "local_source_pending_exact_match"
    assert response.metadata["fallback_source"] == "www.gd.gov.cn"


def test_orchestrator_local_rollout_prefers_exact_city_candidate_before_province_fallback() -> None:
    task = _build_task(
        task_id="c01_local_budget_1",
        task_family="local_rollout",
        regional_level=RegionalLevel.MUNICIPAL,
        source_cluster="province_or_city_backbone",
        include_domains=["hefei.gov.cn", "gxj.hefei.gov.cn", "ah.gov.cn"],
        search_phrases=["合肥 新能源汽车 政策"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="合肥 新能源汽车 政策",
                results=[
                    TavilySearchResult(
                        title="安徽省新能源汽车产业发展",
                        url="https://www.ah.gov.cn/public/1681/565495721.html",
                        content="安徽 新能源汽车 政策",
                    ),
                    TavilySearchResult(
                        title="合肥市工业和信息化局：打造新能源汽车之都",
                        url="https://gxj.hefei.gov.cn/xxfb/tpxw/15234161.html",
                        content="合肥 新能源汽车 产业 集群",
                    ),
                ],
            )
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
        max_candidates=1,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.SUCCESS
    assert len(extraction_service.calls) == 1
    assert [item.url for item in extraction_service.calls[0].inputs] == [
        "https://gxj.hefei.gov.cn/xxfb/tpxw/15234161.html"
    ]
    accepted = [item for item in response.candidate_decisions if item.decision == "accept"]
    assert len(accepted) == 1
    assert accepted[0].reason_code == "accepted_exact_city_or_county_official"


def test_orchestrator_hefei_nev_local_rollout_uses_city_seed_before_province_noise() -> None:
    task = _build_task(
        task_id="c01_local_seed_1",
        task_family="local_rollout",
        regional_level=RegionalLevel.MUNICIPAL,
        source_cluster="province_or_city_backbone",
        include_domains=["hefei.gov.cn", "gxj.hefei.gov.cn", "ah.gov.cn"],
        search_phrases=["合肥 新能源汽车 政策"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="合肥 新能源汽车 政策",
                results=[
                    TavilySearchResult(
                        title="安徽新能源汽车产量增长",
                        url="https://www.ah.gov.cn/zwyw/mtjj/554155611.html",
                        content="合肥 新能源汽车 产业",
                        score=0.99,
                    ),
                    TavilySearchResult(
                        title="公众参与",
                        url="https://fzggw.ah.gov.cn/gzcy/index.html",
                        content="领导信箱 在线咨询 我要建议",
                        score=0.98,
                    ),
                ],
            )
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
        max_candidates=2,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.SUCCESS
    assert [item.url for item in extraction_service.calls[0].inputs] == [
        "https://gxj.hefei.gov.cn/gzdt/18799011.html",
        "https://gxj.hefei.gov.cn/gyjj/xqgy/18811887.html",
    ]
    assert {item.discovery_provider for item in extraction_service.calls[0].inputs} == {
        "official_seed"
    }
    reason_codes = {item.reason_code for item in response.candidate_decisions}
    assert "accepted_official_city_seed_candidate" in reason_codes
    assert "generic_navigation_index_page" in reason_codes


def test_orchestrator_uses_official_seed_fallback_when_city_seed_is_unextractable() -> None:
    task = _build_task(
        task_id="c01_local_seed_fallback_1",
        task_family="local_rollout",
        regional_level=RegionalLevel.MUNICIPAL,
        source_cluster="province_or_city_backbone",
        include_domains=["hefei.gov.cn", "gxj.hefei.gov.cn", "ah.gov.cn"],
        search_phrases=["\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 \u653f\u7b56"],
    )
    seed_url = "https://gxj.hefei.gov.cn/gzdt/18799011.html"
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 \u653f\u7b56",
                results=[],
            )
        ]
    )
    extraction_service = _FakeExtractionService(
        response=_build_extraction_failures([seed_url])
    )
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
        max_candidates=1,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.PARTIAL
    assert len(response.errors) == 1
    assert [document.source_uri for document in response.documents] == [seed_url]
    assert response.normalized_documents[0].metadata["provider"] == "official_seed_fallback"
    assert response.normalized_documents[0].metadata["extraction_fallback_reason"] == (
        "crawl4ai_seed_page_unextractable"
    )
    assert response.metadata["coverage_sufficient"] is True
    assert response.metadata["extraction"][0]["official_seed_fallback_succeeded"] == 1
    assert response.metadata["extraction"][0]["official_seed_fallback_urls"] == [seed_url]


def test_orchestrator_feixi_nev_local_rollout_uses_county_seed_before_parent_noise() -> None:
    task = _build_task(
        task_id="k07_local_seed_1",
        task_family="local_rollout",
        regional_level=RegionalLevel.MUNICIPAL,
        source_cluster="park_city_rollout_backbone",
        include_domains=["ahfeixi.gov.cn", "hefei.gov.cn", "gxj.hefei.gov.cn"],
        exclude_domains=["xf.ahfeixi.gov.cn"],
        search_phrases=[
            "\u80a5\u897f \u65b0\u80fd\u6e90\u6c7d\u8f66 "
            "\u4ea7\u4e1a\u96c6\u7fa4 \u5408\u80a5\u5e02\u5de5\u4e1a\u548c\u4fe1\u606f\u5316\u5c40"
        ],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="\u80a5\u897f \u65b0\u80fd\u6e90\u6c7d\u8f66 \u4ea7\u4e1a\u96c6\u7fa4",
                results=[
                    TavilySearchResult(
                        title="\u5408\u80a5\u65b0\u80fd\u6e90\u6c7d\u8f66\u4e4b\u90fd",
                        url="https://gxj.hefei.gov.cn/gzdt/18799011.html",
                        content="\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 \u4ea7\u4e1a\u94fe",
                        score=0.99,
                    )
                ],
            )
        ]
    )
    seed_url = "http://xf.ahfeixi.gov.cn/content/detail/689c0f232792eeb9ca4b6e0c.html"
    extraction_service = _FakeExtractionService(
        response=_build_extraction_failures([seed_url])
    )
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
        max_candidates=2,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.PARTIAL
    assert [item.url for item in extraction_service.calls[0].inputs] == [
        seed_url,
        "http://xf.ahfeixi.gov.cn/content/detail/68da37af2792ee7d817b23c6.html",
    ]
    assert response.metadata["fallback_level"] == "exact_park_or_county"
    assert response.metadata["parent_evidence_only"] is False
    assert response.metadata["local_claim_allowed"] is True
    assert response.metadata["coverage_sufficient"] is True
    assert response.normalized_documents[0].metadata["provider"] == "official_seed_fallback"
    assert response.normalized_documents[0].metadata["seed_excluded_domain_override"] is True
    assert response.normalized_documents[0].metadata["seed_exclusion_override_reason"] == (
        "verified_exact_local_seed_replaces_stale_search_discovery"
    )
    reason_codes = {item.reason_code for item in response.candidate_decisions}
    assert "accepted_official_county_seed_candidate" in reason_codes
    assert "region_mismatch" in reason_codes


def test_orchestrator_rejects_unsupported_coverage_lane() -> None:
    task = QueryDecompositionTask.model_construct(
        task_id="unsupported_1",
        task_family="media_news_context",
        tiaokuai_axis=GovernanceAxis.LINE,
        line_family=LineFamily.POLICY,
        regional_level=RegionalLevel.NATIONAL,
        info_type=InfoType.POLICY_NOTICE,
        execution_bucket="search_assisted_sources",
        source_cluster="media_news_context",
        source_strategy_hint="cn_media",
        include_domains=["gov.cn"],
        exclude_domains=[],
        search_phrases=["产业 新闻"],
        exact_phrases=[],
        negative_terms=[],
        evidence_goal="collect",
        fallback_path="fallback",
        priority=50,
        confidence=0.6,
    )
    search_adapter = _FakeSearchAdapter(responses=[])
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.ERROR
    assert response.errors[0].detail["reason_code"] == "coverage_lane_not_supported"
    assert search_adapter.called == 0
    assert extraction_service.calls == []


def test_orchestrator_rejects_non_provincial_local_rollout() -> None:
    task = _build_task(
        task_id="local_national_1",
        task_family="local_rollout",
        regional_level=RegionalLevel.NATIONAL,
        source_cluster="province_policy_backbone",
    )
    search_adapter = _FakeSearchAdapter(responses=[])
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.ERROR
    assert (
        response.errors[0].detail["reason_code"]
        == "local_rollout_requires_provincial_or_municipal_level"
    )
    assert search_adapter.called == 0
    assert extraction_service.calls == []


def test_orchestrator_exposes_search_errors_when_no_candidate_is_accepted() -> None:
    task = _build_task(
        task_id="policy_2",
        task_family="policy_direction",
        include_domains=["gov.cn"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.ERROR,
                query="low altitude economy policy",
                errors=[
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message="search unavailable",
                        retryable=True,
                    )
                ],
            )
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.ERROR
    assert response.errors
    assert extraction_service.calls == []


def test_multi_round_round1_stops_on_sufficient_required_lane() -> None:
    task = _build_task(
        task_id="round1_stop_1",
        task_family="policy_direction",
        include_domains=["gov.cn"],
        search_phrases=["policy p1", "policy p2", "policy p3"],
    )
    search_adapter = _SequencedSearchAdapter(
        responses_by_call=[
            [
                TavilySearchResponse(
                    status=ToolStatus.SUCCESS,
                    query="policy p1",
                    results=[
                        TavilySearchResult(
                            title="official",
                            url="https://www.gov.cn/zhengce/content.html",
                            content="official page",
                        )
                    ],
                    usage={
                        "provider": "tavily",
                        "endpoint": "https://api.tavily.com/search",
                        "search_depth": "basic",
                        "max_results": 5,
                        "estimated_credits": 1,
                        "result_count": 1,
                    },
                )
            ]
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.SUCCESS
    assert search_adapter.called == 1
    assert response.metadata["round_trace"][0]["round_index"] == 1
    assert response.metadata["round_trace"][0]["stop_reason"] == "required_lane_sufficient"
    assert response.metadata["coverage_sufficient"] is True


def test_multi_round_round2_runs_for_insufficient_required_lane_only() -> None:
    task = _build_task(
        task_id="round2_required_1",
        task_family="local_rollout",
        regional_level=RegionalLevel.MUNICIPAL,
        source_cluster="province_or_city_backbone",
        include_domains=["sz.gov.cn", "gd.gov.cn"],
        search_phrases=["深圳 低空经济 政策 p1", "深圳 低空经济 政策 p2", "深圳 低空经济 政策 p3"],
    )
    search_adapter = _SequencedSearchAdapter(
        responses_by_call=[
            [
                TavilySearchResponse(
                    status=ToolStatus.SUCCESS,
                    query="p1",
                    results=[
                        TavilySearchResult(
                            title="offdomain",
                            url="https://example.com/noise.html",
                            content="noise",
                        )
                    ],
                    usage={
                        "provider": "tavily",
                        "endpoint": "https://api.tavily.com/search",
                        "search_depth": "basic",
                        "max_results": 5,
                        "estimated_credits": 1,
                        "result_count": 1,
                    },
                )
            ],
            [
                TavilySearchResponse(
                    status=ToolStatus.SUCCESS,
                    query="p2",
                    results=[
                        TavilySearchResult(
                            title="official",
                            url="https://www.sz.gov.cn/zwgk/policy.html",
                            content="深圳低空经济政策",
                        )
                    ],
                    usage={
                        "provider": "tavily",
                        "endpoint": "https://api.tavily.com/search",
                        "search_depth": "basic",
                        "max_results": 5,
                        "estimated_credits": 1,
                        "result_count": 1,
                    },
                )
            ],
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.SUCCESS
    assert search_adapter.called == 2
    assert (
        response.metadata["round_trace"][0]["continue_reason"]
        == "required_lane_gap_needs_round2"
    )
    assert response.metadata["round_trace"][0]["domain_widening_blocked"] is True
    assert all(
        item.url != "https://example.com/noise.html"
        for item in extraction_service.calls[0].inputs
    )


def test_multi_round_round3_is_bounded_for_supplemental_lane() -> None:
    task = _build_task(
        task_id="round3_supp_1",
        task_family="industry_topic",
        source_cluster="association_enhancement",
        include_domains=["caai.cn"],
        regional_level=RegionalLevel.NATIONAL,
        search_phrases=["supp p1", "supp p2", "supp p3"],
    )
    search_adapter = _SequencedSearchAdapter(
        responses_by_call=[
            [
                TavilySearchResponse(
                    status=ToolStatus.SUCCESS,
                    query="supp p1",
                    results=[],
                    usage={
                        "provider": "tavily",
                        "endpoint": "https://api.tavily.com/search",
                        "search_depth": "basic",
                        "max_results": 5,
                        "estimated_credits": 1,
                        "result_count": 0,
                    },
                )
            ],
            [
                TavilySearchResponse(
                    status=ToolStatus.SUCCESS,
                    query="supp p3",
                    results=[
                        TavilySearchResult(
                            title="caai",
                            url="https://www.caai.cn/whitepaper.html",
                            content="industry supplement",
                        )
                    ],
                    usage={
                        "provider": "tavily",
                        "endpoint": "https://api.tavily.com/search",
                        "search_depth": "basic",
                        "max_results": 5,
                        "estimated_credits": 1,
                        "result_count": 1,
                    },
                )
            ],
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.SUCCESS
    assert search_adapter.called == 2
    assert (
        response.metadata["round_trace"][0]["continue_reason"]
        == "round3_supplemental_or_fallback"
    )
    assert response.metadata["round_trace"][1]["round_index"] == 3
    assert response.metadata["round_trace"][1]["budget"]["used_search_credits"] == 2


def test_multi_round_budget_exhaustion_emits_structured_gap() -> None:
    task = _build_task(
        task_id="budget_gap_1",
        task_family="local_rollout",
        regional_level=RegionalLevel.MUNICIPAL,
        source_cluster="province_or_city_backbone",
        include_domains=["sz.gov.cn", "gd.gov.cn"],
        search_phrases=["budget p1", "budget p2", "budget p3"],
    )
    search_adapter = _SequencedSearchAdapter(
        responses_by_call=[
            [
                TavilySearchResponse(
                    status=ToolStatus.SUCCESS,
                    query="budget p1",
                    results=[],
                    usage={
                        "provider": "tavily",
                        "endpoint": "https://api.tavily.com/search",
                        "search_depth": "basic",
                        "max_results": 5,
                        "estimated_credits": 1,
                        "result_count": 0,
                    },
                )
            ]
        ]
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_empty())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
        round_policy_overrides={"max_estimated_tavily_credits": 1},
    )

    response = orchestrator.orchestrate_task(task)

    assert search_adapter.called == 1
    assert response.metadata["coverage_sufficient"] is False
    assert response.metadata["coverage_gaps"]
    assert any(
        gap["reason_code"] == "budget_exhausted"
        for gap in response.metadata["coverage_gaps"]
    )
    assert response.metadata["budget_state"]["used_search_credits"] == 1


def test_convert_search_assisted_documents_to_evidence_items() -> None:
    task = _build_task(
        task_id="policy_convert_1",
        task_family="policy_direction",
    )
    raw_documents = [
        RawDocument(
            document_id="doc_convert_1",
            source_id=SEARCH_ASSISTED_SOURCE_ID,
            title="Policy detail",
            source_uri="https://www.gov.cn/policy/detail.html",
            raw_text="Detailed policy body.",
            metadata={"discovery_score": 0.88},
        )
    ]
    normalized_documents = [
        NormalizedDocument(
            document_id="doc_convert_1",
            source_id=SEARCH_ASSISTED_SOURCE_ID,
            title="Policy detail",
            summary="Policy summary",
            sections=[
                DocumentSection(
                    section_id="sec_1",
                    heading="Summary",
                    text="Section one content.",
                    order_index=0,
                ),
                DocumentSection(
                    section_id="sec_2",
                    heading="Signal",
                    text="Section two content.",
                    order_index=1,
                ),
            ],
            metadata={"final_url": "https://www.gov.cn/policy/detail.html"},
        )
    ]

    evidence_items = convert_search_assisted_documents_to_evidence_items(
        task=task,
        documents=raw_documents,
        normalized_documents=normalized_documents,
        max_items=5,
    )

    assert len(evidence_items) == 2
    first_item = evidence_items[0]
    assert first_item.source_id == SEARCH_ASSISTED_SOURCE_ID
    assert first_item.citation.document_id == "doc_convert_1"
    assert first_item.citation.locator.section_id == "sec_1"
    assert first_item.citation.source_uri == "https://www.gov.cn/policy/detail.html"
    assert first_item.citation.metadata["source_name"] == "Search Assisted Domestic"
    assert first_item.metadata["conversion_path"] == "search_assisted_domestic"
    assert 0.0 <= first_item.score <= 1.0


def test_convert_search_response_to_evidence_items_raw_fallback() -> None:
    task = _build_task(
        task_id="policy_convert_2",
        task_family="policy_direction",
    )
    response = DomesticSearchAssistedResponse(
        status=ToolStatus.SUCCESS,
        task_id=task.task_id,
        task_family=task.task_family,
        documents=[
            RawDocument(
                document_id="raw_only_1",
                source_id=SEARCH_ASSISTED_SOURCE_ID,
                title="Raw only page",
                source_uri="https://www.gov.cn/raw_only.html",
                raw_text="Raw-only body should still produce evidence.",
                metadata={"discovery_score": 0.7},
            )
        ],
        normalized_documents=[],
    )

    evidence_items = convert_search_response_to_evidence_items(
        task=task,
        response=response,
        max_items=3,
    )

    assert len(evidence_items) == 1
    item = evidence_items[0]
    assert item.citation.document_id == "raw_only_1"
    assert item.citation.source_uri == "https://www.gov.cn/raw_only.html"
    assert item.support_text.startswith("Raw-only body")
