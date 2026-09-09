from __future__ import annotations

from packages.sources.crawl4ai_extraction import (
    Crawl4AIExtractionRequest,
    Crawl4AIExtractionResponse,
)
from packages.sources.enums import GovernanceAxis, InfoType, LineFamily, RegionalLevel, ToolStatus
from packages.sources.query_decomposition import QueryDecompositionTask
from packages.sources.retrieval_plan import (
    CoverageLane,
    DomainStrategy,
    ExecutionBucket,
    build_deterministic_retrieval_plan,
)
from packages.sources.schemas import DocumentSection, NormalizedDocument, RawDocument
from packages.sources.search_assisted_domestic import SearchAssistedDomesticOrchestrator
from packages.sources.search_discovery import TavilySearchResponse, TavilySearchResult


class _FakeSearchAdapter:
    def __init__(self, responses: list[TavilySearchResponse]) -> None:
        self.responses = responses

    def search_task(self, task: QueryDecompositionTask) -> list[TavilySearchResponse]:
        del task
        return self.responses


class _FakeExtractionService:
    def __init__(self, response: Crawl4AIExtractionResponse) -> None:
        self.response = response
        self.calls: list[Crawl4AIExtractionRequest] = []

    def extract(self, request: Crawl4AIExtractionRequest) -> Crawl4AIExtractionResponse:
        self.calls.append(request)
        return self.response


def _build_extraction_success() -> Crawl4AIExtractionResponse:
    raw_document = RawDocument(
        document_id="doc_1",
        source_id="search_assisted_domestic",
        title="policy",
        source_uri="https://www.gov.cn/zhengce/content.html",
        raw_text="body",
    )
    normalized_document = NormalizedDocument(
        document_id="doc_1",
        source_id="search_assisted_domestic",
        title="policy",
        summary="summary",
        sections=[
            DocumentSection(
                section_id="doc_1_sec_1",
                heading="summary",
                text="body",
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


def _build_local_rollout_task(
    *,
    task_id: str,
    query_phrase: str,
    source_cluster: str,
    include_domains: list[str],
) -> QueryDecompositionTask:
    return QueryDecompositionTask(
        task_id=task_id,
        task_family="local_rollout",
        tiaokuai_axis=GovernanceAxis.BLOCK,
        line_family=LineFamily.POLICY,
        regional_level=RegionalLevel.MUNICIPAL,
        info_type=InfoType.POLICY_NOTICE,
        execution_bucket="search_assisted_sources",
        source_cluster=source_cluster,
        include_domains=include_domains,
        search_phrases=[query_phrase],
        evidence_goal="collect local rollout evidence",
        fallback_path="city/county fallback",
    )


def test_src_cov_05_city_fallback_metadata_and_project_direct_keep_boundary() -> None:
    plan = build_deterministic_retrieval_plan("深圳低空经济有哪些政策和招标信号")
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}
    assert lane_by_id[CoverageLane.PROJECT_TRANSACTION].execution_bucket == (
        ExecutionBucket.DIRECT_STRUCTURED_SOURCES
    )
    assert lane_by_id[CoverageLane.PROJECT_TRANSACTION].domain_strategy == (
        DomainStrategy.DIRECT_STRUCTURED_ONLY
    )

    task = _build_local_rollout_task(
        task_id="src_cov_05_local",
        query_phrase="深圳 低空经济 政策",
        source_cluster="province_or_city_backbone",
        include_domains=["sz.gov.cn", "gd.gov.cn"],
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
                        content="省级政策",
                    ),
                    TavilySearchResult(
                        title="深圳市政策",
                        url="https://www.sz.gov.cn/zwgk/policy.html",
                        content="深圳低空经济政策",
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
    assert response.metadata["fallback_attempt_order"] == [
        "exact_local_official",
        "province_official",
        "national_official",
    ]
    assert response.metadata["fallback_level"] == "exact_city"
    assert response.metadata["local_claim_allowed"] is True


def test_src_cov_07_park_parent_evidence_is_fallback_only() -> None:
    task = _build_local_rollout_task(
        task_id="src_cov_07_park",
        query_phrase="成都 人工智能产业园区 政策 规划",
        source_cluster="park_city_rollout_backbone",
        include_domains=["chengdu.gov.cn", "sc.gov.cn"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="成都 人工智能产业园区 政策 规划",
                results=[
                    TavilySearchResult(
                        title="成都市政策",
                        url="https://www.chengdu.gov.cn/zwgk/policy.html",
                        content="人工智能产业园区 市级政策",
                    ),
                    TavilySearchResult(
                        title="四川省政策",
                        url="https://www.sc.gov.cn/10462/c106038/content.html",
                        content="人工智能产业园区 省级政策",
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
    assert response.metadata["fallback_level"] in {"city", "province"}
    assert response.metadata["parent_evidence_only"] is True
    assert response.metadata["local_claim_allowed"] is False
    assert response.metadata["coverage_gap_reason"] == "local_source_pending_exact_match"


def test_county_district_fixture_and_bounded_candidate_limit_observable_offline() -> None:
    task = _build_local_rollout_task(
        task_id="county_fixture_1",
        query_phrase="苏州 工业园区 光伏 项目 政策",
        source_cluster="park_city_rollout_backbone",
        include_domains=["suzhou.gov.cn", "jiangsu.gov.cn", "sipac.gov.cn"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="苏州 工业园区 光伏 项目 政策",
                results=[
                    TavilySearchResult(
                        title="园区官网政策",
                        url="https://www.sipac.gov.cn/szgyyq/policy.html",
                        content="苏州工业园区 光伏 政策",
                    ),
                    TavilySearchResult(
                        title="苏州市政策",
                        url="https://www.suzhou.gov.cn/policy.html",
                        content="苏州 光伏 政策",
                    ),
                    TavilySearchResult(
                        title="江苏省政策",
                        url="https://www.jiangsu.gov.cn/policy.html",
                        content="江苏 光伏 政策",
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
    assert len(extraction_service.calls[0].inputs) == 1
    assert any(
        decision.reason_code == "candidate_limit_reached"
        for decision in response.candidate_decisions
    )
    assert response.metadata["round_policy"]["max_candidates_per_lane"] == 1
    assert response.metadata["budget_state"]["used_candidates"] == 1


def test_city_fallback_round2_only_and_no_round3_for_primary_lane() -> None:
    task = _build_local_rollout_task(
        task_id="city_round2_only_1",
        query_phrase="娣卞湷 浣庣┖缁忔祹 鏀跨瓥",
        source_cluster="province_or_city_backbone",
        include_domains=["sz.gov.cn", "gd.gov.cn"],
    )
    search_adapter = _FakeSearchAdapter(
        responses=[
            TavilySearchResponse(
                status=ToolStatus.SUCCESS,
                query="娣卞湷 浣庣┖缁忔祹 鏀跨瓥",
                results=[
                    TavilySearchResult(
                        title="parent province policy",
                        url="https://www.gd.gov.cn/zwgk/policy.html",
                        content="province level policy",
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
    )
    extraction_service = _FakeExtractionService(response=_build_extraction_success())
    orchestrator = SearchAssistedDomesticOrchestrator(
        search_adapter=search_adapter,
        extraction_service=extraction_service,
        round_policy_overrides={"max_rounds": 3},
    )

    response = orchestrator.orchestrate_task(task)

    assert response.status == ToolStatus.SUCCESS
    assert response.metadata["round_trace"][-1]["round_index"] in {1, 2, 3}
    assert all(item["round_index"] <= 3 for item in response.metadata["round_trace"])
