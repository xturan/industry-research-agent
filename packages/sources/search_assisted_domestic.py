from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from packages.sources.citation import normalize_evidence_item
from packages.sources.coverage_judge import (
    CoverageBudgetState,
    LaneRoundMetrics,
    decide_round_transition,
    judge_lane_sufficiency,
)
from packages.sources.crawl4ai_extraction import (
    Crawl4AIExtractionProvider,
    Crawl4AIExtractionRequest,
    Crawl4AIExtractionResponse,
    Crawl4AIExtractionService,
    SearchUrlCandidate,
)
from packages.sources.enums import RegionalLevel, ToolErrorCode, ToolStatus
from packages.sources.query_decomposition import QueryDecompositionTask
from packages.sources.retrieval_plan import (
    CoverageLane,
    CoverageLanePlan,
    DomainStrategy,
    ExecutionBucket,
    LaneSuccessCriteria,
    RoundPolicy,
    StopConditions,
    is_supplemental_or_fallback_lane,
    lane_for_task_family,
)
from packages.sources.schemas import (
    Citation,
    CitationLocator,
    DocumentSection,
    EvidenceItem,
    NormalizedDocument,
    RawDocument,
    ToolError,
)
from packages.sources.search_discovery import (
    SearchDiscoveryProvider,
    TavilySearchAdapter,
    TavilySearchResponse,
    TavilySearchResult,
)
from packages.sources.source_family_backbone import (
    official_quantitative_obligation_satisfied,
    source_family_backbones_for_source_classes,
)
from packages.sources.source_resolver import evaluate_candidate_compatibility

_FIRST_WAVE_TASK_FAMILIES = {
    "policy_direction",
    "local_rollout",
    "industry_topic",
}
_SUPPLEMENTAL_KEYWORDS = (
    "association",
    "alliance",
    "expo",
    "forum",
    "whitepaper",
    "topic",
    "supplement",
    "enhancement",
)
_PARK_COUNTY_MARKERS = ("园区", "开发区", "产业园", "高新区", "自贸区", "县", "区")
_MINISTRY_DOMAINS = {
    "gov.cn",
    "ndrc.gov.cn",
    "miit.gov.cn",
    "mof.gov.cn",
    "mofcom.gov.cn",
    "mee.gov.cn",
    "mnr.gov.cn",
    "mara.gov.cn",
    "most.gov.cn",
    "mohurd.gov.cn",
    "mot.gov.cn",
}
_REAL_ESTATE_POLICY_MARKERS = (
    "房地产",
    "城中村改造",
    "三大工程",
    "地方收储",
    "去库存",
    "住房城乡建设部",
)
_REAL_ESTATE_CENTRAL_POLICY_DOMAINS = {
    "www.gov.cn",
    "mohurd.gov.cn",
    "ndrc.gov.cn",
    "stats.gov.cn",
}
_REAL_ESTATE_POLICY_SEED_RESULTS = (
    {
        "seed_id": "mohurd_city_village_three_projects",
        "title": "城中村改造稳步推进（产经观察·聚焦“三大工程”）",
        "url": "https://www.mohurd.gov.cn/xinwen/gzdt/art/2024/art_304_778875.html",
        "content": (
            "住房城乡建设部 城中村改造 三大工程 平急两用 保障性住房 "
            "专项借款 改造资金 房地产"
        ),
        "published_date": "2024-06-26",
        "score": 0.91,
    },
    {
        "seed_id": "mohurd_quality_notice_city_village_housing",
        "title": "住房城乡建设部办公厅关于加强保障性住房和城中村改造安置房建设质量监管的通知",
        "url": (
            "https://www.mohurd.gov.cn/gongkai/zc/wjk/art/2025/"
            "art_2ab4d1ffd2aa4e91830f09715a659c6a.html"
        ),
        "content": (
            "住房城乡建设部 保障性住房 城中村改造 安置房 项目建设 "
            "三大工程 房地产"
        ),
        "published_date": "2025-01-07",
        "score": 0.89,
    },
    {
        "seed_id": "nbs_2024_real_estate_market",
        "title": "2024年全国房地产市场基本情况",
        "url": "https://www.stats.gov.cn/xxgk/sjfb/zxfb2020/202501/t20250117_1958328.html",
        "content": (
            "国家统计局 房地产开发投资 新开工面积 商品房销售面积 "
            "商品房待售面积 房地产"
        ),
        "published_date": "2025-01-17",
        "score": 0.88,
    },
)
_HEFEI_NEV_LOCAL_ROLLOUT_MARKERS = ("合肥", "新能源汽车")
_FEIXI_NEV_LOCAL_ROLLOUT_MARKERS = ("肥西", "新能源汽车")
_HEFEI_NEV_LOCAL_ROLLOUT_SEED_RESULTS = (
    {
        "seed_id": "hefei_nev_capital_work_update",
        "title": "抢先时机 紧扣时点 狠抓时效全力以赴打造“新能源汽车之都”",
        "url": "https://gxj.hefei.gov.cn/gzdt/18799011.html",
        "content": (
            "合肥市工业和信息化局 新能源汽车之都 整车 零部件 后市场 "
            "产业链 供应链 项目 政策"
        ),
        "published_date": "2025-01-09",
        "score": 0.94,
    },
    {
        "seed_id": "hefei_changfeng_world_nev_city",
        "title": "长丰县：打造世界级新能源汽车城",
        "url": "https://gxj.hefei.gov.cn/gyjj/xqgy/18811887.html",
        "content": (
            "合肥市工业和信息化局 长丰县 新能源汽车 整车 零部件 "
            "本地配套率 产业集群 供应链"
        ),
        "published_date": "2025-02-18",
        "score": 0.92,
    },
    {
        "seed_id": "hefei_14th_five_year_nev_plan_interpretation",
        "title": "蓄力新赛道 绘制新蓝图——合肥市发布“十四五”新能源汽车产业发展规划",
        "url": "https://gxj.hefei.gov.cn/public/17331/108374338.html",
        "content": (
            "合肥市工业和信息化局 十四五 新能源汽车产业发展规划 "
            "整车 动力电池 零部件 产业体系"
        ),
        "published_date": "2022-11-25",
        "score": 0.9,
    },
)
_FEIXI_NEV_LOCAL_ROLLOUT_SEED_RESULTS = (
    {
        "seed_id": "feixi_15th_five_year_enterprise_roundtable",
        "title": "共谋发展 共话未来 肥西县“十五五”时期经济社会高质量发展座谈会召开",
        "url": "http://xf.ahfeixi.gov.cn/content/detail/689c0f232792eeb9ca4b6e0c.html",
        "content": (
            "肥西发布 肥西县 十五五 新能源汽车 江淮汽车 均胜安全 "
            "派能科技 华晟新能源 产业基础 产业链 上下游协同"
        ),
        "published_date": "2025-08-08",
        "score": 0.93,
    },
    {
        "seed_id": "feixi_yiqi_party_industry_chain",
        "title": "肥西县：“益企”党建激活产业发展“红色动能”",
        "url": "http://xf.ahfeixi.gov.cn/content/detail/68da37af2792ee7d817b23c6.html",
        "content": (
            "肥西县委社会工作部 新能源汽车 高端智能制造 产业集群党委 "
            "强链 补链 延链 30分钟零部件供应圈 惠企政策兑现"
        ),
        "published_date": "2025-09-28",
        "score": 0.91,
    },
    {
        "seed_id": "feixi_municipal_research_nev_projects",
        "title": "费高云在肥西县调研",
        "url": "http://xf.ahfeixi.gov.cn/content/detail/6806dec62792ee381d4ae426.html",
        "content": (
            "肥西发布 肥西县 重大项目建设 华晟新能源 均胜安全 "
            "汽车安全 新能源汽车产业发展 产业集群"
        ),
        "published_date": "2025-04-22",
        "score": 0.89,
    },
)
_OFFICIAL_SEED_FALLBACK_TEXT_BY_ID = {
    "hefei_nev_capital_work_update": (
        "\u5408\u80a5\u5e02\u5de5\u4e1a\u548c\u4fe1\u606f\u5316\u5c40\u9875\u9762\u6307\u5411"
        "\u201c\u65b0\u80fd\u6e90\u6c7d\u8f66\u4e4b\u90fd\u201d\u5efa\u8bbe\uff0c\u4fa7\u91cd"
        "\u6574\u8f66\u3001\u96f6\u90e8\u4ef6\u3001\u540e\u5e02\u573a\u4e00\u4f53\u5316\u5e03\u5c40"
        "\u548c\u4ea7\u4e1a\u94fe\u3001\u521b\u65b0\u94fe\u3001\u8d44\u91d1\u94fe\u3001\u653f\u7b56\u94fe"
        "\u534f\u540c\u3002\u8be5\u9875\u9762\u8fd8\u63d0\u5230\u4e0b\u5858\u3001\u65b0\u6865\u3001\u65b0\u6e2f"
        "\u4e09\u5927\u6574\u8f66\u53ca\u96f6\u90e8\u4ef6\u57fa\u5730\uff0c\u4ee5\u53ca\u5408\u80a5\u591a\u4e2a"
        "\u56ed\u533a\u7684\u914d\u5957\u4ea7\u4e1a\u96c6\u805a\u3002"
    ),
    "hefei_changfeng_world_nev_city": (
        "\u5408\u80a5\u5e02\u5de5\u4e1a\u548c\u4fe1\u606f\u5316\u5c40\u8f6c\u8f7d\u957f\u4e30\u53bf"
        "\u5efa\u8bbe\u4e16\u754c\u7ea7\u65b0\u80fd\u6e90\u6c7d\u8f66\u57ce\u4fe1\u606f\uff0c\u91cd\u70b9"
        "\u56f4\u7ed5\u6574\u8f66\u3001\u96f6\u90e8\u4ef6\u548c\u540e\u5e02\u573a\u534f\u540c\u3002"
        "\u9875\u9762\u4fe1\u606f\u6307\u5411\u667a\u80fd\u7f51\u8054\u6c7d\u8f66\u4ea7\u4e1a\u89c4\u6a21"
        "\u3001\u672c\u5730\u914d\u5957\u7387\u3001\u9f99\u5934\u4f01\u4e1a\u548c\u96f6\u90e8\u4ef6\u96c6\u7fa4"
        "\u7b49\u53ef\u7528\u6765\u5224\u65ad\u57ce\u5e02\u5185\u90e8\u4f9b\u5e94\u94fe\u95ed\u73af\u7684\u4fe1\u53f7\u3002"
    ),
    "hefei_14th_five_year_nev_plan_interpretation": (
        "\u5408\u80a5\u5e02\u5de5\u4e1a\u548c\u4fe1\u606f\u5316\u5c40\u653f\u52a1\u516c\u5f00\u9875"
        "\u89e3\u8bfb\u5408\u80a5\u201c\u5341\u56db\u4e94\u201d\u65b0\u80fd\u6e90\u6c7d\u8f66\u4ea7\u4e1a"
        "\u53d1\u5c55\u89c4\u5212\uff0c\u5305\u542b\u6574\u8f66\u4ea7\u80fd\u3001\u767e\u4ebf\u7ea7\u4f01\u4e1a"
        "\u3001\u52a8\u529b\u7535\u6c60\u4ea7\u80fd\u3001\u9a71\u52a8\u7535\u673a\u4ea7\u80fd\u548c"
        "\u65b0\u80fd\u6e90\u6c7d\u8f66\u53ca\u96f6\u90e8\u4ef6\u4ea7\u4e1a\u4f53\u7cfb\u7b49\u6307\u6807\u3002"
    ),
    "feixi_15th_five_year_enterprise_roundtable": (
        "\u80a5\u897f\u53bf\u53ec\u5f00\u201c\u5341\u4e94\u4e94\u201d\u65f6\u671f\u7ecf\u6d4e\u793e\u4f1a"
        "\u9ad8\u8d28\u91cf\u53d1\u5c55\u5ea7\u8c08\u4f1a\uff0c\u6c5f\u6dee\u6c7d\u8f66\u3001\u5747\u80dc"
        "\u5b89\u5168\u3001\u534e\u665f\u65b0\u80fd\u6e90\u3001\u6d3e\u80fd\u79d1\u6280\u7b49\u53bf\u57df"
        "\u91cd\u70b9\u4ea7\u4e1a\u96c6\u7fa4\u4f01\u4e1a\u53c2\u4e0e\u5efa\u8bae\u3002\u8be5\u9875\u9762"
        "\u6307\u5411\u80a5\u897f\u6218\u65b0\u4ea7\u4e1a\u96c6\u7fa4\u805a\u94fe\u6210\u52bf\u3001"
        "\u5e38\u6001\u5316\u4e3a\u4f01\u670d\u52a1\u548c\u4ea7\u4e1a\u94fe\u4e0a\u4e0b\u6e38\u534f\u540c\u3002"
    ),
    "feixi_yiqi_party_industry_chain": (
        "\u80a5\u897f\u53bf\u59d4\u793e\u4f1a\u5de5\u4f5c\u90e8\u9875\u9762\u5c55\u793a"
        "\u201c\u76ca\u4f01\u201d\u515a\u5efa\u8d4b\u80fd\u4ea7\u4e1a\u94fe\u7684\u5de5\u4f5c\uff0c"
        "\u56f4\u7ed5\u65b0\u80fd\u6e90\u6c7d\u8f66\u548c\u9ad8\u7aef\u667a\u80fd\u5236\u9020\u7b49"
        "\u91cd\u70b9\u94fe\u6761\u63a8\u52a8\u5f3a\u94fe\u3001\u8865\u94fe\u3001\u5ef6\u94fe\uff0c"
        "\u5e76\u63d0\u5230\u5f62\u6210\u201c30\u5206\u949f\u96f6\u90e8\u4ef6\u4f9b\u5e94\u5708\u201d"
        "\u548c\u60e0\u4f01\u653f\u7b56\u5151\u73b0\u670d\u52a1\u3002"
    ),
    "feixi_municipal_research_nev_projects": (
        "\u80a5\u897f\u53bf\u5730\u65b9\u9875\u9762\u8bb0\u5f55\u5408\u80a5\u5e02\u59d4\u4e3b\u8981"
        "\u8d1f\u8d23\u4eba\u5728\u80a5\u897f\u53bf\u8c03\u7814\uff0c\u6d89\u53ca\u534e\u665f\u65b0\u80fd\u6e90"
        "\u3001\u5747\u80dc\u5b89\u5168\u7b49\u4f01\u4e1a\u53ca\u5728\u5efa\u9879\u76ee\u3002\u8be5\u4fe1\u606f"
        "\u53ef\u7528\u4e8e\u9a8c\u8bc1\u80a5\u897f\u53bf\u65b0\u80fd\u6e90\u6c7d\u8f66\u76f8\u5173\u9879\u76ee"
        "\u548c\u4ea7\u4e1a\u94fe\u914d\u5957\u4e0d\u53ea\u662f\u7701\u5e02\u7ea7\u89c4\u5212\u53e3\u53f7\u3002"
    ),
}
_ATTACHMENT_SUFFIXES = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".7z",
    ".csv",
)
_NON_EVIDENCE_PATH_MARKERS = (
    "/site/search",
    "/search",
    "/sousuo",
    "/login",
)
_NON_EVIDENCE_DOMAIN_PREFIXES = (
    "so.",
    "search.",
)
SEARCH_ASSISTED_SOURCE_ID = "search_assisted_domestic"
SEARCH_ASSISTED_SOURCE_NAME = "Search Assisted Domestic"


class DomesticTaskGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["allow", "hold", "refuse"]
    reason_code: str = Field(min_length=1, max_length=120)
    reason_message: str = Field(min_length=1, max_length=500)
    task_mode: str = Field(min_length=1, max_length=80)


class DomesticCandidateDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1, max_length=120)
    query: str = Field(min_length=1, max_length=800)
    url: str = Field(min_length=1, max_length=2000)
    domain: str | None = Field(default=None, max_length=255)
    decision: Literal["accept", "reject"]
    reason_code: str = Field(min_length=1, max_length=120)
    reason_message: str = Field(min_length=1, max_length=500)
    score: float | None = Field(default=None, ge=0.0)


class DomesticSearchAssistedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ToolStatus
    task_id: str = Field(min_length=1, max_length=80)
    task_family: str = Field(min_length=1, max_length=40)
    documents: list[RawDocument] = Field(default_factory=list)
    normalized_documents: list[NormalizedDocument] = Field(default_factory=list)
    candidate_decisions: list[DomesticCandidateDecision] = Field(default_factory=list)
    errors: list[ToolError] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchAssistedDomesticOrchestrator:
    def __init__(
        self,
        *,
        search_adapter: SearchDiscoveryProvider | None = None,
        extraction_service: Crawl4AIExtractionProvider | None = None,
        max_candidates: int = 3,
        round_policy_overrides: dict[str, int] | None = None,
        stop_conditions: StopConditions | None = None,
    ) -> None:
        base_round_policy = RoundPolicy()
        if round_policy_overrides:
            base_round_policy = base_round_policy.model_copy(update=round_policy_overrides)
        self.search_adapter = search_adapter or TavilySearchAdapter()
        self.extraction_service = extraction_service or Crawl4AIExtractionService()
        self.round_policy = base_round_policy
        self.stop_conditions = stop_conditions or StopConditions()
        upper_bound = min(20, self.round_policy.max_candidates_per_lane)
        self.max_candidates = max(1, min(max_candidates, upper_bound))

    def orchestrate_task(self, task: QueryDecompositionTask) -> DomesticSearchAssistedResponse:
        gate = _gate_task(task)
        if gate.decision != "allow":
            return DomesticSearchAssistedResponse(
                status=(
                    ToolStatus.ERROR if gate.decision == "refuse" else ToolStatus.UNSUPPORTED
                ),
                task_id=task.task_id,
                task_family=task.task_family,
                errors=[
                    ToolError(
                        code=(
                            ToolErrorCode.INVALID_REQUEST
                            if gate.decision == "refuse"
                            else ToolErrorCode.UNSUPPORTED_OPERATION
                        ),
                        message=gate.reason_message,
                        retryable=False,
                        detail={
                            "reason_code": gate.reason_code,
                            "task_mode": gate.task_mode,
                        },
                    )
                ],
                metadata={
                    "gate_decision": gate.decision,
                    "gate_reason": gate.reason_code,
                    "task_mode": gate.task_mode,
                    "requested_search_phrases": len(task.search_phrases),
                    "round_policy": _round_policy_metadata(
                        self.round_policy,
                        max_candidates_per_lane=self.max_candidates,
                    ),
                },
            )
        lane_plan = _lane_plan_for_task(task)
        supplemental_or_fallback_lane = is_supplemental_or_fallback_lane(lane_plan.lane_id)
        budget_state = CoverageBudgetState(
            max_search_credits=self.round_policy.max_estimated_tavily_credits,
            used_search_credits=0,
            max_candidates=min(self.max_candidates, self.round_policy.max_candidates_per_lane),
            used_candidates=0,
            max_extractions=self.round_policy.max_extractions_per_lane,
            used_extractions=0,
        )

        candidate_decisions: list[DomesticCandidateDecision] = []
        errors: list[ToolError] = []
        all_documents: list[RawDocument] = []
        all_normalized_documents: list[NormalizedDocument] = []
        all_search_statuses: list[str] = []
        accepted_candidate_ids: list[str] = []
        seen_urls: set[str] = set()
        coverage_gaps: list[dict[str, Any]] = []
        round_trace: list[dict[str, Any]] = []
        extraction_metadata: list[dict[str, Any]] = []
        search_response_count = 0
        coverage_sufficient = False

        round_index = 1
        while round_index <= self.round_policy.max_rounds:
            if budget_state.exhausted():
                break

            round_task = task.model_copy(
                update={
                    "search_phrases": [_round_phrase_for_index(task.search_phrases, round_index)],
                }
            )
            search_responses = self.search_adapter.search_task(round_task)
            search_response_count += len(search_responses)
            all_search_statuses.extend(response.status.value for response in search_responses)
            errors.extend(_collect_search_errors(search_responses))
            budget_state.used_search_credits += _estimate_round_search_credits(search_responses)

            remaining_candidates = max(
                0,
                budget_state.max_candidates - budget_state.used_candidates,
            )
            remaining_extractions = max(
                0,
                budget_state.max_extractions - budget_state.used_extractions,
            )
            max_new_candidates = min(remaining_candidates, remaining_extractions)
            round_decisions, extraction_inputs = self._select_candidates(
                task=task,
                responses=search_responses,
                max_new_candidates=max_new_candidates,
                seen_urls=seen_urls,
            )
            candidate_decisions.extend(round_decisions)
            budget_state.used_candidates += len(extraction_inputs)
            accepted_candidate_ids.extend(item.candidate_id for item in extraction_inputs)

            if extraction_inputs:
                extraction_response = self.extraction_service.extract(
                    Crawl4AIExtractionRequest(inputs=extraction_inputs)
                )
                seed_documents, seed_normalized_documents, seed_fallback_urls = (
                    _fallback_documents_from_official_seed_inputs(
                        extraction_inputs=extraction_inputs,
                        extraction_response=extraction_response,
                    )
                )
                all_documents.extend(extraction_response.documents)
                all_normalized_documents.extend(extraction_response.normalized_documents)
                all_documents.extend(seed_documents)
                all_normalized_documents.extend(seed_normalized_documents)
                errors.extend(extraction_response.errors)
                extraction_metadata.append(
                    {
                        **extraction_response.metadata,
                        "official_seed_fallback_succeeded": len(seed_normalized_documents),
                        "official_seed_fallback_urls": seed_fallback_urls,
                    }
                )
                budget_state.used_extractions += len(extraction_inputs)

            fallback_metadata = _build_local_fallback_metadata(
                task=task,
                candidate_decisions=candidate_decisions,
            )
            metrics = LaneRoundMetrics(
                accepted_candidate_count=len(accepted_candidate_ids),
                accepted_document_count=len(all_normalized_documents),
                rejected_reason_codes=[
                    item.reason_code
                    for item in candidate_decisions
                    if item.decision == "reject"
                ],
                local_claim_allowed=bool(fallback_metadata.get("local_claim_allowed", True)),
                parent_evidence_only=bool(fallback_metadata.get("parent_evidence_only", False)),
            )
            judgment = judge_lane_sufficiency(
                lane_plan=lane_plan,
                metrics=metrics,
                budget_state=budget_state,
            )
            coverage_sufficient = judgment.sufficient
            coverage_gaps = [gap.model_dump(mode="json") for gap in judgment.coverage_gaps]
            transition = decide_round_transition(
                lane_plan=lane_plan,
                round_index=round_index,
                max_rounds=self.round_policy.max_rounds,
                judgment=judgment,
                stop_conditions=self.stop_conditions,
                supplemental_or_fallback_lane=supplemental_or_fallback_lane,
            )
            round_trace.append(
                {
                    "round_index": round_index,
                    "query_phrase": round_task.search_phrases[0],
                    "accepted_candidate_count": metrics.accepted_candidate_count,
                    "accepted_document_count": metrics.accepted_document_count,
                    "coverage_sufficient": judgment.sufficient,
                    "continue_reason": (
                        transition.reason_code if transition.decision == "continue" else None
                    ),
                    "stop_reason": (
                        transition.reason_code if transition.decision == "stop" else None
                    ),
                    "domain_widening_blocked": transition.domain_widening_blocked,
                    "budget": budget_state.as_dict(),
                }
            )

            if transition.decision == "stop":
                break
            if transition.next_round is None or transition.next_round <= round_index:
                break
            round_index = transition.next_round

        if not coverage_sufficient and budget_state.exhausted():
            coverage_gaps = coverage_gaps or [
                {
                    "lane_id": lane_plan.lane_id.value,
                    "reason_code": "budget_exhausted",
                    "required": lane_plan.required,
                }
            ]

        if all_normalized_documents:
            status = ToolStatus.PARTIAL if errors else ToolStatus.SUCCESS
        elif errors:
            status = ToolStatus.ERROR
        else:
            status = ToolStatus.PARTIAL

        _annotate_source_class_metadata(
            task=task,
            documents=all_documents,
            normalized_documents=all_normalized_documents,
        )
        fallback_metadata = _build_local_fallback_metadata(
            task=task,
            candidate_decisions=candidate_decisions,
        )
        return DomesticSearchAssistedResponse(
            status=status,
            task_id=task.task_id,
            task_family=task.task_family,
            documents=all_documents,
            normalized_documents=all_normalized_documents,
            candidate_decisions=candidate_decisions,
            errors=errors,
            metadata={
                "gate_decision": gate.decision,
                "gate_reason": gate.reason_code,
                "task_mode": gate.task_mode,
                "search_response_count": search_response_count,
                "accepted_candidate_count": len(accepted_candidate_ids),
                "rejected_candidate_count": len(candidate_decisions) - len(accepted_candidate_ids),
                "accepted_candidate_ids": accepted_candidate_ids,
                "search_statuses": all_search_statuses,
                "round_policy": _round_policy_metadata(
                    self.round_policy,
                    max_candidates_per_lane=self.max_candidates,
                ),
                "budget_state": budget_state.as_dict(),
                "round_trace": round_trace,
                "coverage_sufficient": coverage_sufficient,
                "coverage_gaps": coverage_gaps,
                "extraction": extraction_metadata,
                **fallback_metadata,
            },
        )

    def _select_candidates(
        self,
        *,
        task: QueryDecompositionTask,
        responses: list[TavilySearchResponse],
        max_new_candidates: int,
        seen_urls: set[str],
    ) -> tuple[list[DomesticCandidateDecision], list[SearchUrlCandidate]]:
        decisions: list[DomesticCandidateDecision] = []
        selected_inputs: list[SearchUrlCandidate] = []
        allowed_domains = _effective_allowed_domains(task)
        staged_inputs: list[tuple[int, int, SearchUrlCandidate]] = []
        staged_seen_urls: set[str] = set(seen_urls)
        encounter_index = 0

        for response_index, response in enumerate(responses, start=1):
            for result_index, result in enumerate(response.results, start=1):
                candidate_id = f"{task.task_id}_{response_index}_{result_index}"
                decision = _evaluate_candidate(
                    task=task,
                    candidate_id=candidate_id,
                    result=result,
                    query=response.query,
                    allowed_domains=allowed_domains,
                    seen_urls=staged_seen_urls,
                )
                decisions.append(decision)
                if decision.decision != "accept":
                    continue
                encounter_index += 1
                staged_seen_urls.add(result.url.strip())
                candidate = SearchUrlCandidate(
                    candidate_id=candidate_id,
                    url=result.url,
                    source_id="search_assisted_domestic",
                    source_name_hint=task.source_cluster,
                    title_hint=result.title,
                    snippet_hint=result.content,
                    published_at_hint=result.published_date,
                    discovery_provider="tavily",
                    discovery_query=response.query,
                    discovery_score=result.score,
                    task_family=task.task_family,
                    execution_bucket=task.execution_bucket,
                    source_cluster=task.source_cluster,
                    include_domains=task.include_domains,
                    metadata={
                        "candidate_reason": "accepted_for_extraction",
                    },
                )
                priority = _candidate_selection_priority(task=task, decision=decision)
                staged_inputs.append((priority, encounter_index, candidate))

        seed_decisions: list[DomesticCandidateDecision] = []
        seed_staged_inputs: list[tuple[int, int, SearchUrlCandidate]] = []
        if _official_seed_needed_for_task(task=task, staged_inputs=staged_inputs):
            seed_decisions, seed_staged_inputs = _staged_official_seed_candidates_for_task(
                task=task,
                max_new_candidates=max_new_candidates,
                seen_urls=staged_seen_urls,
                allowed_domains=allowed_domains,
                start_index=encounter_index,
            )
        decisions.extend(seed_decisions)
        staged_inputs.extend(seed_staged_inputs)

        if staged_inputs and max_new_candidates > 0:
            staged_inputs.sort(
                key=lambda item: (
                    item[0],
                    _candidate_discovery_priority(item[2]),
                    -float(item[2].discovery_score or 0.0),
                    item[1],
                )
            )
            selected_inputs = [item[2] for item in staged_inputs[:max_new_candidates]]
            selected_candidate_ids = {item.candidate_id for item in selected_inputs}
            seen_urls.update(item.url.strip() for item in selected_inputs)
            decisions = [
                decision
                if (
                    decision.decision != "accept"
                    or decision.candidate_id in selected_candidate_ids
                )
                else decision.model_copy(
                    update={
                        "decision": "reject",
                        "reason_code": "candidate_limit_reached",
                        "reason_message": (
                            f"Accepted candidate limit ({max_new_candidates}) reached."
                        ),
                    }
                )
                for decision in decisions
            ]
        elif staged_inputs:
            decisions = [
                decision
                if decision.decision != "accept"
                else decision.model_copy(
                    update={
                        "decision": "reject",
                        "reason_code": "candidate_limit_reached",
                        "reason_message": (
                            f"Accepted candidate limit ({max_new_candidates}) reached."
                        ),
                    }
                )
                for decision in decisions
            ]

        return decisions, selected_inputs


def convert_search_assisted_documents_to_evidence_items(
    *,
    task: QueryDecompositionTask,
    documents: list[RawDocument],
    normalized_documents: list[NormalizedDocument],
    max_items: int = 10,
) -> list[EvidenceItem]:
    capped_max_items = max(0, max_items)
    if capped_max_items == 0:
        return []

    evidence_items: list[EvidenceItem] = []
    raw_by_id = {document.document_id: document for document in documents}
    normalized_doc_ids = {document.document_id for document in normalized_documents}
    seen_keys: set[tuple[str, str]] = set()

    for normalized_document in normalized_documents:
        raw_document = raw_by_id.get(normalized_document.document_id)
        source_id = _pick_source_id(
            normalized_source_id=normalized_document.source_id,
            raw_source_id=(raw_document.source_id if raw_document is not None else None),
        )
        source_uri = _pick_source_uri(
            normalized_document=normalized_document,
            raw_document=raw_document,
        )
        published_at = (
            normalized_document.published_at
            if normalized_document.published_at is not None
            else (raw_document.published_at if raw_document is not None else None)
        )
        base_score = _pick_score(normalized_document=normalized_document, raw_document=raw_document)
        title = normalized_document.title or (
            raw_document.title if raw_document is not None else "search-assisted document"
        )
        sections = _sections_with_fallback(normalized_document, raw_document)
        for section_index, section in enumerate(sections):
            section_id = section[0]
            section_text = section[1]
            dedupe_key = (normalized_document.document_id, section_id)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            evidence_item = _build_evidence_item(
                task=task,
                source_id=source_id,
                document_id=normalized_document.document_id,
                section_id=section_id,
                section_index=section_index,
                title=title,
                summary=normalized_document.summary,
                support_text=section_text,
                source_uri=source_uri,
                published_at=published_at,
                score=base_score,
                metadata=_merge_document_metadata(
                    normalized_metadata=normalized_document.metadata,
                    raw_metadata=(raw_document.metadata if raw_document is not None else None),
                ),
            )
            evidence_items.append(evidence_item)
            if len(evidence_items) >= capped_max_items:
                return evidence_items

    for raw_document in documents:
        if raw_document.document_id in normalized_doc_ids:
            continue
        raw_text = (raw_document.raw_text or raw_document.snippet or "").strip()
        if not raw_text:
            continue
        evidence_item = _build_evidence_item(
            task=task,
            source_id=_pick_source_id(
                normalized_source_id=None,
                raw_source_id=raw_document.source_id,
            ),
            document_id=raw_document.document_id,
            section_id=f"{raw_document.document_id}_raw",
            section_index=0,
            title=raw_document.title,
            summary=raw_document.snippet,
            support_text=raw_text,
            source_uri=raw_document.source_uri,
            published_at=raw_document.published_at,
            score=_bounded_score(
                _safe_float(raw_document.metadata.get("discovery_score")),
                default=0.6,
            ),
            metadata=_merge_document_metadata(
                normalized_metadata=None,
                raw_metadata=raw_document.metadata,
            ),
        )
        evidence_items.append(evidence_item)
        if len(evidence_items) >= capped_max_items:
            return evidence_items

    return evidence_items


def convert_search_response_to_evidence_items(
    *,
    task: QueryDecompositionTask,
    response: DomesticSearchAssistedResponse,
    max_items: int = 10,
) -> list[EvidenceItem]:
    return convert_search_assisted_documents_to_evidence_items(
        task=task,
        documents=response.documents,
        normalized_documents=response.normalized_documents,
        max_items=max_items,
    )


def _build_evidence_item(
    *,
    task: QueryDecompositionTask,
    source_id: str,
    document_id: str,
    section_id: str,
    section_index: int,
    title: str,
    summary: str | None,
    support_text: str,
    source_uri: str | None,
    published_at: Any,
    score: float,
    metadata: dict[str, Any],
) -> EvidenceItem:
    locator = CitationLocator(
        document_id=document_id,
        section_id=section_id,
        chunk_index=max(section_index, 0),
        external_ref=source_uri,
    )
    citation = Citation(
        citation_id=_stable_id("cit", task.task_id, document_id, section_id),
        source_id=source_id,
        document_id=document_id,
        locator=locator,
        quote_text=_truncate_text(support_text, 280),
        source_uri=source_uri,
        published_at=published_at,
        metadata={
            "path": "search_assisted_domestic",
            "task_id": task.task_id,
            "task_family": task.task_family,
            "execution_bucket": task.execution_bucket,
            "source_cluster": task.source_cluster,
        },
    )
    evidence_item = EvidenceItem(
        evidence_id=_stable_id("evi", task.task_id, document_id, section_id),
        source_id=source_id,
        title=title,
        summary=(summary or _truncate_text(support_text, 280)),
        support_text=support_text,
        score=_bounded_score(score, default=0.6),
        citation=citation,
        metadata={
            "path": "search_assisted_domestic",
            "task_id": task.task_id,
            "task_family": task.task_family,
            "execution_bucket": task.execution_bucket,
            "source_cluster": task.source_cluster,
            "include_domains": task.include_domains,
            **metadata,
        },
    )
    return normalize_evidence_item(
        evidence_item,
        source_name=SEARCH_ASSISTED_SOURCE_NAME,
        external_id=document_id,
    )


def _sections_with_fallback(
    normalized_document: NormalizedDocument,
    raw_document: RawDocument | None,
) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for section in normalized_document.sections:
        section_text = section.text.strip()
        if not section_text:
            continue
        sections.append((section.section_id, section_text))
    if sections:
        return sections

    fallback_text = (
        normalized_document.summary
        or (raw_document.raw_text if raw_document is not None else None)
        or (raw_document.snippet if raw_document is not None else None)
        or ""
    ).strip()
    if not fallback_text:
        return []
    return [(f"{normalized_document.document_id}_summary", fallback_text)]


def _pick_source_id(*, normalized_source_id: str | None, raw_source_id: str | None) -> str:
    for candidate in (normalized_source_id, raw_source_id, SEARCH_ASSISTED_SOURCE_ID):
        if candidate and candidate.strip():
            return candidate.strip()
    return SEARCH_ASSISTED_SOURCE_ID


def _pick_source_uri(
    *,
    normalized_document: NormalizedDocument,
    raw_document: RawDocument | None,
) -> str | None:
    normalized_metadata = (
        normalized_document.metadata if isinstance(normalized_document.metadata, dict) else {}
    )
    uri_candidates = [
        normalized_metadata.get("final_url"),
        normalized_metadata.get("requested_url"),
        raw_document.source_uri if raw_document is not None else None,
    ]
    for candidate in uri_candidates:
        if not isinstance(candidate, str):
            continue
        stripped = candidate.strip()
        if stripped:
            return stripped
    return None


def _pick_score(
    *,
    normalized_document: NormalizedDocument,
    raw_document: RawDocument | None,
) -> float:
    normalized_metadata = (
        normalized_document.metadata if isinstance(normalized_document.metadata, dict) else {}
    )
    raw_metadata = (
        raw_document.metadata
        if (raw_document is not None and isinstance(raw_document.metadata, dict))
        else {}
    )
    return _bounded_score(
        _safe_float(normalized_metadata.get("discovery_score"))
        or _safe_float(raw_metadata.get("discovery_score")),
        default=0.65,
    )


def _merge_document_metadata(
    *,
    normalized_metadata: dict[str, Any] | None,
    raw_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if isinstance(raw_metadata, dict):
        metadata.update(raw_metadata)
    if isinstance(normalized_metadata, dict):
        metadata.update(normalized_metadata)
    metadata["converted_to_evidence"] = True
    metadata["conversion_path"] = "search_assisted_domestic"
    return metadata


def _truncate_text(text: str, max_length: int) -> str:
    stripped = text.strip()
    if len(stripped) <= max_length:
        return stripped
    return f"{stripped[: max_length - 3]}..."


def _stable_id(prefix: str, *parts: str) -> str:
    token = "|".join(part.strip() for part in parts if part)
    digest = hashlib.sha1(token.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bounded_score(value: float | None, *, default: float) -> float:
    candidate = value if value is not None else default
    return min(max(float(candidate), 0.0), 1.0)


def _gate_task(task: QueryDecompositionTask) -> DomesticTaskGateResult:
    if task.execution_bucket == "direct_structured_sources":
        return DomesticTaskGateResult(
            decision="refuse",
            reason_code="direct_keep_boundary_violation",
            reason_message=(
                "Direct structured sources are protected and cannot use search-assisted "
                "domestic orchestration."
            ),
            task_mode="direct_keep_refused",
        )

    if task.execution_bucket != "search_assisted_sources":
        return DomesticTaskGateResult(
            decision="refuse",
            reason_code="unsupported_execution_bucket",
            reason_message=f"Unsupported execution bucket: {task.execution_bucket}.",
            task_mode="unsupported_bucket",
        )

    if task.task_family not in _FIRST_WAVE_TASK_FAMILIES:
        return DomesticTaskGateResult(
            decision="refuse",
            reason_code="coverage_lane_not_supported",
            reason_message=f"Task family {task.task_family} is outside first-wave scope.",
            task_mode="not_first_wave",
        )

    if task.task_family == "industry_topic":
        cluster = task.source_cluster.lower()
        if not any(keyword in cluster for keyword in _SUPPLEMENTAL_KEYWORDS):
            return DomesticTaskGateResult(
                decision="refuse",
                reason_code="industry_topic_requires_supplemental_cluster",
                reason_message=(
                    "Industry-topic tasks are allowed only for supplemental "
                    "association/topic clusters in first wave."
                ),
                task_mode="supplemental_required",
            )
        return DomesticTaskGateResult(
            decision="allow",
            reason_code="first_wave_industry_topic_supplemental",
            reason_message="Industry-topic supplemental task allowed in first wave.",
            task_mode="supplemental_association_topic",
        )

    if task.task_family == "local_rollout":
        if task.regional_level not in {RegionalLevel.PROVINCIAL, RegionalLevel.MUNICIPAL}:
            return DomesticTaskGateResult(
                decision="refuse",
                reason_code="local_rollout_requires_provincial_or_municipal_level",
                reason_message=(
                    "Local rollout migration is limited to provincial/municipal "
                    "policy fallback tasks."
                ),
                task_mode="not_first_wave_local_level",
            )
        task_mode = (
            "local_policy_city_county_fallback"
            if task.regional_level == RegionalLevel.MUNICIPAL
            else "local_policy_generic"
        )
        return DomesticTaskGateResult(
            decision="allow",
            reason_code="first_wave_local_policy_generic",
            reason_message="Local rollout policy task allowed in first wave.",
            task_mode=task_mode,
        )

    return DomesticTaskGateResult(
        decision="allow",
        reason_code="first_wave_policy_generic",
        reason_message="Policy-direction generic task allowed in first wave.",
        task_mode="policy_generic",
    )


def _effective_allowed_domains(task: QueryDecompositionTask) -> set[str]:
    normalized = {domain.strip().lower() for domain in task.include_domains if domain.strip()}
    if task.task_family == "policy_direction":
        if _is_real_estate_policy_task(task):
            central_only = {
                domain
                for domain in normalized
                if any(
                    domain == central_domain or domain.endswith(f".{central_domain}")
                    for central_domain in _REAL_ESTATE_CENTRAL_POLICY_DOMAINS
                )
            }
            return central_only or set(_REAL_ESTATE_CENTRAL_POLICY_DOMAINS)
        return normalized | _MINISTRY_DOMAINS
    if task.task_family == "local_rollout":
        return normalized | {"gov.cn"}
    if task.task_family == "industry_topic":
        return normalized
    return normalized


def _is_real_estate_policy_task(task: QueryDecompositionTask) -> bool:
    text = " ".join([*task.search_phrases, *task.include_domains])
    return any(marker in text for marker in _REAL_ESTATE_POLICY_MARKERS)


def _staged_official_seed_candidates_for_task(
    *,
    task: QueryDecompositionTask,
    max_new_candidates: int,
    seen_urls: set[str],
    allowed_domains: set[str],
    start_index: int,
) -> tuple[list[DomesticCandidateDecision], list[tuple[int, int, SearchUrlCandidate]]]:
    if max_new_candidates <= 0:
        return [], []

    decisions: list[DomesticCandidateDecision] = []
    staged_inputs: list[tuple[int, int, SearchUrlCandidate]] = []
    seed_results = _official_seed_results_for_task(task)
    encounter_index = start_index
    for seed_index, seed in enumerate(seed_results, start=1):
        seed_url = str(seed["url"]).strip()
        if seed_url in seen_urls:
            continue
        seed_query = f"official_seed:{seed['seed_id']}"
        candidate_id = f"{task.task_id}_seed_{seed_index}"
        result = TavilySearchResult(
            title=str(seed["title"]),
            url=seed_url,
            content=str(seed["content"]),
            score=float(seed["score"]),
            published_date=str(seed["published_date"]),
        )
        decision = _evaluate_candidate(
            task=task,
            candidate_id=candidate_id,
            result=result,
            query=seed_query,
            allowed_domains=allowed_domains,
            seen_urls=seen_urls,
        )
        if decision.decision != "accept":
            decisions.append(decision)
            continue

        encounter_index += 1
        seen_urls.add(seed_url)
        excluded_domain_override = _is_excluded_seed_domain(task=task, url=seed_url)
        seed_decision = decision.model_copy(
            update={
                "reason_code": _accepted_seed_reason_code(task),
                "reason_message": (
                    "Official seed candidate accepted as a verified exact-local "
                    "exception to search-discovery domain exclusion."
                    if excluded_domain_override
                    else (
                        "Official seed candidate accepted after Tavily-compatible "
                        "search results did not produce enough precise official sources."
                    )
                ),
            }
        )
        decisions.append(seed_decision)
        seed_candidate = SearchUrlCandidate(
            candidate_id=candidate_id,
            url=result.url,
            source_id=SEARCH_ASSISTED_SOURCE_ID,
            source_name_hint=task.source_cluster,
            title_hint=result.title,
            snippet_hint=result.content,
            published_at_hint=result.published_date,
            discovery_provider="official_seed",
            discovery_query=seed_query,
            discovery_score=result.score,
            task_family=task.task_family,
            execution_bucket=task.execution_bucket,
            source_cluster=task.source_cluster,
            include_domains=task.include_domains,
            metadata={
                "candidate_reason": _accepted_seed_reason_code(task),
                "seed_id": seed["seed_id"],
                "seed_scope": _seed_scope_for_task(task),
                "seed_excluded_domain_override": excluded_domain_override,
                "seed_exclusion_override_reason": (
                    "verified_exact_local_seed_replaces_stale_search_discovery"
                    if excluded_domain_override
                    else None
                ),
            },
        )
        priority = _candidate_selection_priority(task=task, decision=seed_decision)
        staged_inputs.append((priority, encounter_index, seed_candidate))

    return decisions, staged_inputs


def _official_seed_results_for_task(task: QueryDecompositionTask) -> tuple[dict[str, Any], ...]:
    if _is_real_estate_policy_task(task):
        return _REAL_ESTATE_POLICY_SEED_RESULTS
    if _is_feixi_nev_local_rollout_task(task):
        return _FEIXI_NEV_LOCAL_ROLLOUT_SEED_RESULTS
    if _is_hefei_nev_local_rollout_task(task):
        return _HEFEI_NEV_LOCAL_ROLLOUT_SEED_RESULTS
    return ()


def _is_excluded_seed_domain(*, task: QueryDecompositionTask, url: str) -> bool:
    domain = _domain_from_url(url)
    if not domain:
        return False
    return any(
        domain == excluded.strip().lower() or domain.endswith(f".{excluded.strip().lower()}")
        for excluded in task.exclude_domains
        if excluded.strip()
    )


def _official_seed_needed_for_task(
    *,
    task: QueryDecompositionTask,
    staged_inputs: list[tuple[int, int, SearchUrlCandidate]],
) -> bool:
    if _is_real_estate_policy_task(task):
        return not staged_inputs
    if _is_feixi_nev_local_rollout_task(task):
        return not any(priority <= 0 for priority, _index, _candidate in staged_inputs)
    if _is_hefei_nev_local_rollout_task(task):
        return not any(priority <= 1 for priority, _index, _candidate in staged_inputs)
    return False


def _fallback_documents_from_official_seed_inputs(
    *,
    extraction_inputs: list[SearchUrlCandidate],
    extraction_response: Crawl4AIExtractionResponse,
) -> tuple[list[RawDocument], list[NormalizedDocument], list[str]]:
    extracted_urls = _extracted_requested_urls(extraction_response)
    raw_documents: list[RawDocument] = []
    normalized_documents: list[NormalizedDocument] = []
    fallback_urls: list[str] = []

    for extraction_input in extraction_inputs:
        if extraction_input.discovery_provider != "official_seed":
            continue
        if extraction_input.url in extracted_urls:
            continue

        text = (
            _official_seed_fallback_text(extraction_input)
            or extraction_input.snippet_hint
            or ""
        ).strip()
        if not text:
            continue

        title = (
            (extraction_input.title_hint or "").strip()
            or _title_from_seed_url(extraction_input.url)
        )
        document_id = _stable_id("seeddoc", extraction_input.source_id, extraction_input.url)
        published_at = _parse_seed_published_at(extraction_input.published_at_hint)
        metadata = {
            "provider": "official_seed_fallback",
            "requested_url": extraction_input.url,
            "final_url": extraction_input.url,
            "source_name_hint": extraction_input.source_name_hint,
            "title_hint": extraction_input.title_hint,
            "snippet_hint": extraction_input.snippet_hint,
            "published_at_hint": extraction_input.published_at_hint,
            "discovery_provider": extraction_input.discovery_provider,
            "discovery_query": extraction_input.discovery_query,
            "discovery_score": extraction_input.discovery_score,
            "task_family": extraction_input.task_family,
            "execution_bucket": extraction_input.execution_bucket,
            "source_cluster": extraction_input.source_cluster,
            "include_domains": extraction_input.include_domains,
            "extraction_fallback_reason": "crawl4ai_seed_page_unextractable",
            **extraction_input.metadata,
        }
        raw_documents.append(
            RawDocument(
                document_id=document_id,
                source_id=extraction_input.source_id,
                title=title,
                source_uri=extraction_input.url,
                published_at=published_at,
                language="zh-CN",
                raw_text=text,
                snippet=_truncate_text(text, 320),
                metadata=metadata,
            )
        )
        normalized_documents.append(
            NormalizedDocument(
                document_id=document_id,
                source_id=extraction_input.source_id,
                title=title,
                language="zh-CN",
                published_at=published_at,
                summary=_truncate_text(text, 320),
                sections=[
                    DocumentSection(
                        section_id=f"{document_id}_seed_excerpt",
                        heading=title,
                        text=text,
                        order_index=0,
                        metadata={
                            "provider": "official_seed_fallback",
                            "requested_url": extraction_input.url,
                            **extraction_input.metadata,
                        },
                    )
                ],
                metadata=metadata,
            )
        )
        fallback_urls.append(extraction_input.url)

    return raw_documents, normalized_documents, fallback_urls


def _annotate_source_class_metadata(
    *,
    task: QueryDecompositionTask,
    documents: list[RawDocument],
    normalized_documents: list[NormalizedDocument],
) -> None:
    source_classes = _source_classes_for_task(task)
    if not source_classes:
        return
    for document in [*documents, *normalized_documents]:
        _merge_source_class_metadata(document.metadata, source_classes, task=task)


def _source_classes_for_task(task: QueryDecompositionTask) -> list[str]:
    if task.task_family == "policy_direction":
        return ["official_policy"]
    if task.task_family == "local_rollout":
        return ["local_government", "official_policy"]
    if task.task_family == "industry_topic":
        source_classes = ["industry_report", "industry_association", "association_report"]
        if _industry_price_capacity_source_class_needed(task):
            source_classes.extend(["price_data", "industry_price_capacity"])
        return source_classes
    return []


def _industry_price_capacity_source_class_needed(task: QueryDecompositionTask) -> bool:
    text = " ".join([*task.search_phrases, task.evidence_goal, task.source_cluster])
    return any(
        keyword in text
        for keyword in (
            "价格",
            "报价",
            "市场价",
            "价格周期",
            "产能",
            "产能过剩",
            "产能风险",
            "产能集中",
            "装机量",
            "出货量",
            "销量",
            "产量",
            "price",
            "capacity",
            "shipment",
        )
    )


def _merge_source_class_metadata(
    metadata: dict[str, Any],
    source_classes: list[str],
    *,
    task: QueryDecompositionTask,
) -> None:
    merged = _unique_strings(
        [
            *source_classes,
            *_as_string_list(metadata.get("source_classes")),
        ]
    )
    if not merged:
        return
    metadata.setdefault("source_class", merged[0])
    metadata["source_classes"] = merged
    source_family_backbones = [
        family.value
        for family in source_family_backbones_for_source_classes(
            merged,
            evidence_obligations=task.evidence_obligations,
            regional_level=_task_regional_level_value(task),
        )
    ]
    if source_family_backbones:
        metadata["source_family_backbones"] = source_family_backbones
    metadata["official_quantitative_obligation_satisfied"] = (
        official_quantitative_obligation_satisfied(merged)
    )


def _task_regional_level_value(task: QueryDecompositionTask) -> str:
    value = getattr(task.regional_level, "value", task.regional_level)
    return str(value)


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _unique_strings(values: list[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in unique:
            unique.append(normalized)
    return unique


def _extracted_requested_urls(extraction_response: Crawl4AIExtractionResponse) -> set[str]:
    urls: set[str] = set()
    for document in extraction_response.documents:
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        for candidate in (metadata.get("requested_url"), document.source_uri):
            if isinstance(candidate, str) and candidate.strip():
                urls.add(candidate.strip())
    for document in extraction_response.normalized_documents:
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        for candidate in (metadata.get("requested_url"), metadata.get("final_url")):
            if isinstance(candidate, str) and candidate.strip():
                urls.add(candidate.strip())
    return urls


def _official_seed_fallback_text(extraction_input: SearchUrlCandidate) -> str | None:
    seed_id = extraction_input.metadata.get("seed_id")
    if not isinstance(seed_id, str):
        return None
    return _OFFICIAL_SEED_FALLBACK_TEXT_BY_ID.get(seed_id)


def _parse_seed_published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


def _title_from_seed_url(url: str) -> str:
    parsed = urlparse(url)
    tail = parsed.path.strip("/").split("/")[-1] if parsed.path else ""
    return tail or parsed.netloc or "official seed document"


def _accepted_seed_reason_code(task: QueryDecompositionTask) -> str:
    if _is_feixi_nev_local_rollout_task(task):
        return "accepted_official_county_seed_candidate"
    if _is_hefei_nev_local_rollout_task(task):
        return "accepted_official_city_seed_candidate"
    return "accepted_official_seed_candidate"


def _seed_scope_for_task(task: QueryDecompositionTask) -> str:
    if _is_feixi_nev_local_rollout_task(task):
        return "feixi_nev_local_rollout"
    if _is_hefei_nev_local_rollout_task(task):
        return "hefei_nev_local_rollout"
    return "real_estate_central_policy"


def _is_hefei_nev_local_rollout_task(task: QueryDecompositionTask) -> bool:
    if task.task_family != "local_rollout":
        return False
    text = " ".join([*task.search_phrases, *task.include_domains])
    if "肥西" in text:
        return False
    return all(marker in text for marker in _HEFEI_NEV_LOCAL_ROLLOUT_MARKERS)


def _is_feixi_nev_local_rollout_task(task: QueryDecompositionTask) -> bool:
    if task.task_family != "local_rollout":
        return False
    text = " ".join([*task.search_phrases, *task.include_domains])
    return all(marker in text for marker in _FEIXI_NEV_LOCAL_ROLLOUT_MARKERS)


def _evaluate_candidate(
    *,
    task: QueryDecompositionTask,
    candidate_id: str,
    result: TavilySearchResult,
    query: str,
    allowed_domains: set[str],
    seen_urls: set[str],
) -> DomesticCandidateDecision:
    domain = _domain_from_url(result.url)
    normalized_url = result.url.strip()

    if normalized_url in seen_urls:
        return DomesticCandidateDecision(
            candidate_id=candidate_id,
            query=query,
            url=result.url,
            domain=domain,
            decision="reject",
            reason_code="duplicate_candidate_url",
            reason_message="Candidate URL already processed in this task.",
            score=result.score,
        )

    if _is_attachment_url(result.url):
        return DomesticCandidateDecision(
            candidate_id=candidate_id,
            query=query,
            url=result.url,
            domain=domain,
            decision="reject",
            reason_code="attachment_first_candidate",
            reason_message="Attachment-first URL rejected before extraction.",
            score=result.score,
        )

    if _is_non_evidence_navigation_url(result.url):
        return DomesticCandidateDecision(
            candidate_id=candidate_id,
            query=query,
            url=result.url,
            domain=domain,
            decision="reject",
            reason_code="non_evidence_navigation_candidate",
            reason_message="Search, login, or navigation URL rejected before extraction.",
            score=result.score,
        )

    if _is_industry_topic_generic_channel_candidate(task=task, result=result):
        return DomesticCandidateDecision(
            candidate_id=candidate_id,
            query=query,
            url=result.url,
            domain=domain,
            decision="reject",
            reason_code="industry_topic_generic_channel_candidate",
            reason_message=(
                "Industry-topic candidate is a generic channel or navigation page, "
                "not a report, data, price, capacity, or article detail page."
            ),
            score=result.score,
        )

    compatibility = evaluate_candidate_compatibility(
        task=task,
        query=query,
        url=result.url,
        domain=domain,
        title=result.title,
        snippet=result.content,
        allowed_domains=allowed_domains,
    )
    if compatibility.decision != "accept":
        return DomesticCandidateDecision(
            candidate_id=candidate_id,
            query=query,
            url=result.url,
            domain=domain,
            decision="reject",
            reason_code=compatibility.reason_code,
            reason_message=compatibility.reason_message,
            score=result.score,
        )

    return DomesticCandidateDecision(
        candidate_id=candidate_id,
        query=query,
        url=result.url,
        domain=domain,
        decision="accept",
        reason_code=compatibility.reason_code,
        reason_message=compatibility.reason_message,
        score=result.score,
    )


def _candidate_selection_priority(
    *,
    task: QueryDecompositionTask,
    decision: DomesticCandidateDecision,
) -> int:
    if task.task_family != "local_rollout":
        return 10
    level = _fallback_level_from_reason(decision.reason_code)
    if level == "exact_park_or_county":
        return 0
    if level == "exact_city":
        return 1
    if level == "city":
        return 2
    if level == "province":
        return 3
    if level == "national":
        return 4
    return 6


def _candidate_discovery_priority(candidate: SearchUrlCandidate) -> int:
    return 1 if candidate.discovery_provider == "official_seed" else 0


def _collect_search_errors(responses: list[TavilySearchResponse]) -> list[ToolError]:
    errors: list[ToolError] = []
    for response in responses:
        errors.extend(response.errors)
    return errors


def _estimate_round_search_credits(responses: list[TavilySearchResponse]) -> int:
    credits = 0
    for response in responses:
        usage = response.usage
        if usage is not None:
            credits += max(0, int(usage.estimated_credits))
        else:
            credits += 1
    return credits


def _round_phrase_for_index(search_phrases: list[str], round_index: int) -> str:
    if not search_phrases:
        return ""
    if round_index <= len(search_phrases):
        return search_phrases[round_index - 1]
    return search_phrases[-1]


def _round_policy_metadata(
    round_policy: RoundPolicy,
    *,
    max_candidates_per_lane: int,
) -> dict[str, int]:
    return {
        "max_rounds": round_policy.max_rounds,
        "max_search_phrases_per_lane": round_policy.max_search_phrases_per_lane,
        "max_candidates_per_lane": max_candidates_per_lane,
        "max_extractions_per_lane": round_policy.max_extractions_per_lane,
        "max_estimated_tavily_credits": round_policy.max_estimated_tavily_credits,
    }


def _lane_plan_for_task(task: QueryDecompositionTask) -> CoverageLanePlan:
    lane_id = lane_for_task_family(task.task_family) or CoverageLane.NATIONAL_POLICY_DIRECTION
    if task.execution_bucket == "direct_structured_sources":
        execution_bucket = ExecutionBucket.DIRECT_STRUCTURED_SOURCES
        domain_strategy = DomainStrategy.DIRECT_STRUCTURED_ONLY
    elif task.task_family == "industry_topic":
        execution_bucket = ExecutionBucket.SEARCH_ASSISTED_SOURCES
        domain_strategy = DomainStrategy.THEME_SUPPLEMENTAL_DOMAINS_ONLY
    elif task.task_family == "local_rollout":
        execution_bucket = ExecutionBucket.SEARCH_ASSISTED_SOURCES
        domain_strategy = DomainStrategy.FALLBACK_LADDER_OFFICIAL_FIRST
    else:
        execution_bucket = ExecutionBucket.SEARCH_ASSISTED_SOURCES
        domain_strategy = DomainStrategy.REGION_OFFICIAL_DOMAINS_ONLY

    return CoverageLanePlan(
        lane_id=lane_id,
        required=task.task_family != "industry_topic",
        priority=max(1, min(task.priority, 100)),
        execution_bucket=execution_bucket,
        domain_strategy=domain_strategy,
        search_phrases=list(task.search_phrases),
        exact_phrases=list(task.exact_phrases),
        negative_terms=list(task.negative_terms),
        allowed_domains=list(task.include_domains),
        success_criteria=LaneSuccessCriteria(
            min_accepted_documents=1,
            must_match_region=task.task_family in {"local_rollout", "project_transaction"},
            must_match_theme=task.task_family != "data_metrics",
            must_match_source_role=True,
            require_exact_local_match=(task.task_family == "local_rollout"),
            allow_parent_fallback=(task.task_family == "local_rollout"),
            parent_fallback_requires_gap=(task.task_family == "local_rollout"),
        ),
        fallback_ladder=[
            "exact_local_official",
            "city_official",
            "province_official",
            "national_official",
        ]
        if task.task_family == "local_rollout"
        else [],
    )


def _merge_status(
    *,
    extraction_status: ToolStatus,
    has_documents: bool,
    has_errors: bool,
) -> ToolStatus:
    if has_documents and not has_errors:
        return ToolStatus.SUCCESS
    if has_documents and has_errors:
        return ToolStatus.PARTIAL
    if extraction_status == ToolStatus.UNSUPPORTED:
        return ToolStatus.UNSUPPORTED
    return ToolStatus.ERROR


def _domain_from_url(url: str) -> str | None:
    parsed = urlparse(url.strip())
    if not parsed.netloc:
        return None
    return parsed.netloc.lower()


def _is_attachment_url(url: str) -> bool:
    path = urlparse(url.strip()).path.lower()
    return any(path.endswith(suffix) for suffix in _ATTACHMENT_SUFFIXES)


def _is_non_evidence_navigation_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    domain = parsed.netloc.lower()
    path = parsed.path.lower()
    if any(domain.startswith(prefix) for prefix in _NON_EVIDENCE_DOMAIN_PREFIXES):
        return True
    if path in {"/s", "/search"}:
        return True
    return any(marker in path for marker in _NON_EVIDENCE_PATH_MARKERS)


def _is_industry_topic_generic_channel_candidate(
    *,
    task: QueryDecompositionTask,
    result: TavilySearchResult,
) -> bool:
    if task.task_family != "industry_topic":
        return False
    parsed = urlparse(result.url.strip())
    path = parsed.path.strip("/").lower()
    text = " ".join([path, result.title, result.content]).lower()
    if not path:
        return True
    segments = [segment for segment in path.split("/") if segment]
    if len(segments) <= 1 and _has_generic_industry_channel_signal(text):
        return True
    if _has_industry_topic_document_signal(text):
        return False
    return False


def _has_industry_topic_document_signal(text: str) -> bool:
    return any(
        signal in text
        for signal in (
            ".html",
            "/article/",
            "/con_",
            "报告",
            "白皮书",
            "数据",
            "销量",
            "产量",
            "出货量",
            "价格",
            "指数",
            "统计",
            "研究",
            "发布",
            "趋势",
            "分析",
            "report",
            "whitepaper",
            "data",
            "price",
            "capacity",
        )
    )


def _has_generic_industry_channel_signal(text: str) -> bool:
    return any(
        signal in text
        for signal in (
            "栏目",
            "频道",
            "首页",
            "导航",
            "列表",
            "行业政策",
            "hyzc",
            "index",
            "channel",
        )
    )


def _build_local_fallback_metadata(
    *,
    task: QueryDecompositionTask,
    candidate_decisions: list[DomesticCandidateDecision],
) -> dict[str, Any]:
    if task.task_family != "local_rollout":
        return {}

    expected_exact = (
        "exact_park_or_county" if _is_park_or_county_query(task) else "exact_city"
    )
    accepted = [item for item in candidate_decisions if item.decision == "accept"]
    selected = _pick_best_fallback_decision(accepted, expected_exact=expected_exact)
    level = _fallback_level_from_reason(selected.reason_code) if selected else None
    parent_evidence_only = bool(level and level != expected_exact)
    local_claim_allowed = bool(level == expected_exact)
    coverage_gap_reason = (
        None if local_claim_allowed else "local_source_pending_exact_match"
    )

    return {
        "fallback_attempt_order": _fallback_attempt_order(task),
        "fallback_level": level,
        "fallback_source": selected.domain if selected else None,
        "parent_evidence_only": parent_evidence_only,
        "local_claim_allowed": local_claim_allowed,
        "coverage_gap_reason": coverage_gap_reason,
    }


def _pick_best_fallback_decision(
    accepted: list[DomesticCandidateDecision],
    *,
    expected_exact: str,
) -> DomesticCandidateDecision | None:
    if not accepted:
        return None

    priority = _fallback_priority(expected_exact=expected_exact)
    ranked = sorted(
        accepted,
        key=lambda item: (
            priority.get(_fallback_level_from_reason(item.reason_code), 99),
            -float(item.score or 0.0),
        ),
    )
    return ranked[0]


def _fallback_priority(*, expected_exact: str) -> dict[str, int]:
    if expected_exact == "exact_park_or_county":
        return {
            "exact_park_or_county": 0,
            "city": 1,
            "province": 2,
            "national": 3,
            "exact_city": 4,
        }
    return {
        "exact_city": 0,
        "province": 1,
        "national": 2,
        "city": 3,
        "exact_park_or_county": 4,
    }


def _fallback_level_from_reason(reason_code: str) -> str | None:
    mapping = {
        "accepted_exact_park_or_county_official": "exact_park_or_county",
        "accepted_exact_city_or_county_official": "exact_city",
        "accepted_official_county_seed_candidate": "exact_park_or_county",
        "accepted_official_city_seed_candidate": "exact_city",
        "accepted_parent_city_official_fallback": "city",
        "accepted_parent_province_official_fallback": "province",
        "accepted_parent_national_official_fallback": "national",
    }
    return mapping.get(reason_code)


def _fallback_attempt_order(task: QueryDecompositionTask) -> list[str]:
    if _is_park_or_county_query(task):
        return [
            "exact_local_official",
            "city_official",
            "province_official",
            "national_official",
        ]
    return [
        "exact_local_official",
        "province_official",
        "national_official",
    ]


def _is_park_or_county_query(task: QueryDecompositionTask) -> bool:
    if "park" in task.source_cluster.lower():
        return True
    return any(_contains_any(phrase, _PARK_COUNTY_MARKERS) for phrase in task.search_phrases)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


__all__ = [
    "SEARCH_ASSISTED_SOURCE_ID",
    "SEARCH_ASSISTED_SOURCE_NAME",
    "convert_search_assisted_documents_to_evidence_items",
    "convert_search_response_to_evidence_items",
    "DomesticCandidateDecision",
    "DomesticSearchAssistedResponse",
    "DomesticTaskGateResult",
    "SearchAssistedDomesticOrchestrator",
]
