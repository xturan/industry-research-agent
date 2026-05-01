from __future__ import annotations

import hashlib
import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 fallback

    class StrEnum(str, Enum):  # noqa: UP042
        pass


class CoverageLane(StrEnum):
    NATIONAL_POLICY_DIRECTION = "national_policy_direction"
    PROVINCIAL_POLICY_ROLLOUT = "provincial_policy_rollout"
    CITY_COUNTY_FALLBACK = "city_county_fallback"
    STATISTICS_OR_INDUSTRY_DATA = "statistics_or_industry_data"
    PROJECT_TRANSACTION = "project_transaction"
    ENTERPRISE_DISCLOSURE = "enterprise_disclosure"
    INDUSTRY_ASSOCIATION_SIGNAL = "industry_association_signal"
    PARK_ZONE_SIGNAL = "park_zone_signal"
    MEDIA_NEWS_CONTEXT = "media_news_context"


class SourceIntent(StrEnum):
    STATE_COUNCIL = "state_council"
    NATIONAL_DRC = "national_drc"
    NATIONAL_MIIT = "national_miit"
    NATIONAL_STATISTICS = "national_statistics"
    NATIONAL_CUSTOMS = "national_customs"
    NATIONAL_COMMERCE = "national_commerce"
    PROVINCE_GOVERNMENT = "province_government"
    PROVINCE_DRC = "province_drc"
    PROVINCE_INDUSTRY_DEPARTMENT = "province_industry_department"
    PROVINCE_STATISTICS = "province_statistics"
    PROVINCE_COMMERCE = "province_commerce"
    CITY_GOVERNMENT = "city_government"
    CITY_DRC = "city_drc"
    CITY_INDUSTRY_DEPARTMENT = "city_industry_department"
    CITY_STATISTICS = "city_statistics"
    PUBLIC_RESOURCE_TRADE = "public_resource_trade"
    GOVERNMENT_PROCUREMENT = "government_procurement"
    EXCHANGE_DISCLOSURE = "exchange_disclosure"
    THEME_ASSOCIATION = "theme_association"
    PARK_ZONE_OFFICIAL = "park_zone_official"
    OFFICIAL_MEDIA = "official_media"


class DomainStrategy(StrEnum):
    NATIONAL_OFFICIAL_DOMAINS_ONLY = "national_official_domains_only"
    REGION_OFFICIAL_DOMAINS_ONLY = "region_official_domains_only"
    DIRECT_STRUCTURED_ONLY = "direct_structured_only"
    THEME_SUPPLEMENTAL_DOMAINS_ONLY = "theme_supplemental_domains_only"
    FALLBACK_LADDER_OFFICIAL_FIRST = "fallback_ladder_official_first"
    MANUAL_OR_PLACEHOLDER = "manual_or_placeholder"


class ExecutionBucket(StrEnum):
    SEARCH_ASSISTED_SOURCES = "search_assisted_sources"
    DIRECT_STRUCTURED_SOURCES = "direct_structured_sources"
    PLACEHOLDER_OR_MANUAL_SOURCES = "placeholder_or_manual_sources"


class RegionFocus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=60)
    level: str = Field(min_length=1, max_length=40)
    parent: str | None = Field(default=None, max_length=60)


class LaneSuccessCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_accepted_documents: int = Field(default=1, ge=1, le=10)
    must_match_region: bool = True
    must_match_theme: bool = True
    must_match_source_role: bool = True
    require_exact_local_match: bool = False
    allow_parent_fallback: bool = True
    parent_fallback_requires_gap: bool = False


class CoverageLanePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lane_id: CoverageLane
    required: bool = True
    priority: int = Field(default=50, ge=1, le=100)
    source_intents: list[SourceIntent] = Field(default_factory=list)
    execution_bucket: ExecutionBucket
    domain_strategy: DomainStrategy
    search_phrases: list[str] = Field(default_factory=list)
    exact_phrases: list[str] = Field(default_factory=list)
    negative_terms: list[str] = Field(default_factory=list)
    allowed_domains: list[str] = Field(default_factory=list)
    evidence_obligations: list[str] = Field(default_factory=list)
    success_criteria: LaneSuccessCriteria
    fallback_ladder: list[str] = Field(default_factory=list)


class RoundPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_rounds: int = Field(default=3, ge=1, le=5)
    max_search_phrases_per_lane: int = Field(default=3, ge=1, le=5)
    max_candidates_per_lane: int = Field(default=3, ge=1, le=10)
    max_extractions_per_lane: int = Field(default=2, ge=1, le=5)
    max_estimated_tavily_credits: int = Field(default=12, ge=1, le=100)


class StopConditions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_lanes_attempted: bool = True
    stop_when_all_required_lanes_sufficient: bool = True
    stop_when_credit_budget_reached: bool = True
    stop_on_direct_keep_boundary_violation: bool = True
    stop_when_no_compatible_sources: bool = True


class PlannerMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planner_provider: str = Field(min_length=1, max_length=60)
    planner_model: str = Field(min_length=1, max_length=120)
    schema_version: str = Field(min_length=1, max_length=60)
    deterministic_fallback: bool = True
    repair_applied: bool = False
    supplemental_theme: str = Field(min_length=1, max_length=60)
    supplemental_domains: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CoverageGap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lane_id: CoverageLane
    reason_code: str = Field(min_length=1, max_length=80)
    required: bool = True
    fallback_level: str | None = Field(default=None, max_length=80)
    fallback_source: str | None = Field(default=None, max_length=120)
    parent_evidence_only: bool = False
    local_claim_allowed: bool = True
    notes: list[str] = Field(default_factory=list)


class RetrievalPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1, max_length=80)
    original_query: str = Field(min_length=1, max_length=800)
    normalized_theme: str = Field(min_length=1, max_length=120)
    theme_aliases: list[str] = Field(default_factory=list)
    regions: list[RegionFocus] = Field(default_factory=list)
    time_horizon: str = Field(min_length=1, max_length=80)
    user_intent: str = Field(min_length=1, max_length=200)
    coverage_lanes: list[CoverageLanePlan] = Field(default_factory=list)
    round_policy: RoundPolicy = Field(default_factory=RoundPolicy)
    stop_conditions: StopConditions = Field(default_factory=StopConditions)
    coverage_gaps: list[CoverageGap] = Field(default_factory=list)
    planner_metadata: PlannerMetadata


COVERAGE_LANE_V1: tuple[CoverageLane, ...] = (
    CoverageLane.NATIONAL_POLICY_DIRECTION,
    CoverageLane.PROVINCIAL_POLICY_ROLLOUT,
    CoverageLane.CITY_COUNTY_FALLBACK,
    CoverageLane.STATISTICS_OR_INDUSTRY_DATA,
    CoverageLane.PROJECT_TRANSACTION,
    CoverageLane.ENTERPRISE_DISCLOSURE,
    CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL,
    CoverageLane.PARK_ZONE_SIGNAL,
    CoverageLane.MEDIA_NEWS_CONTEXT,
)

TASK_FAMILY_TO_LANE: dict[str, CoverageLane] = {
    "policy_direction": CoverageLane.NATIONAL_POLICY_DIRECTION,
    "local_rollout": CoverageLane.CITY_COUNTY_FALLBACK,
    "industry_topic": CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL,
    "enterprise_disclosure": CoverageLane.ENTERPRISE_DISCLOSURE,
    "project_transaction": CoverageLane.PROJECT_TRANSACTION,
    "data_metrics": CoverageLane.STATISTICS_OR_INDUSTRY_DATA,
    "official_record": CoverageLane.PROJECT_TRANSACTION,
}

ROUND3_SUPPLEMENTAL_OR_FALLBACK_LANES: set[CoverageLane] = {
    CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL,
    CoverageLane.CITY_COUNTY_FALLBACK,
    CoverageLane.PARK_ZONE_SIGNAL,
    CoverageLane.MEDIA_NEWS_CONTEXT,
}

REGION_LEVEL_BY_NAME: dict[str, str] = {
    "全国": "national",
    "安徽": "provincial",
    "合肥": "municipal",
    "广东": "provincial",
    "深圳": "municipal",
    "江苏": "provincial",
    "成都": "municipal",
    "浙江": "provincial",
    "上海": "municipal",
    "苏州": "municipal",
    "常州": "municipal",
    "杭州": "municipal",
    "武汉": "municipal",
    "西安": "municipal",
    "山东": "provincial",
    "福建": "provincial",
    "河南": "provincial",
    "四川": "provincial",
    "海南": "provincial",
    "内蒙古": "provincial",
    "肥西": "county",
    "神木": "county",
    "若羌": "county",
}

PROVINCE_DISTRIBUTION_CITY_HINTS: dict[str, list[str]] = {
    "安徽": ["芜湖", "马鞍山", "安庆", "蚌埠"],
    "海南": ["海口", "三亚"],
}

THEME_ALIAS_MAP: dict[str, list[str]] = {
    "real_estate_demand": ["房地产", "城中村改造", "三大工程", "地方收储", "去库存"],
    "low_altitude_economy": ["低空经济", "通航", "低空飞行", "无人机"],
    "humanoid_robotics": ["人形机器人", "具身智能", "机器人产业"],
    "computing_infrastructure": ["算力基础设施", "算力", "智算中心", "数据中心"],
    "new_energy_vehicle": ["新能源汽车", "动力电池", "整车", "电池", "汽车零部件"],
    "photovoltaics": ["光伏产业链", "光伏", "新能源"],
    "green_hydrogen_coal_chemical": ["绿电", "绿氢", "煤化工", "现代煤化工"],
    "free_trade_port": ["自由贸易港", "海南自由贸易港"],
    "battery_swap": ["新能源汽车换电", "换电", "补能"],
    "unknown": [],
}

SUPPLEMENTAL_DOMAINS_BY_THEME: dict[str, list[str]] = {
    "real_estate_demand": [],
    "low_altitude_economy": ["aopa.org.cn", "china-uav.cn", "caai.cn"],
    "humanoid_robotics": ["caai.cn", "ccpit.org"],
    "computing_infrastructure": ["cndkw.com"],
    "new_energy_vehicle": [],
    "photovoltaics": ["ccpit.org"],
    "green_hydrogen_coal_chemical": [],
    "free_trade_port": [],
    "battery_swap": ["ccpit.org"],
    "unknown": [],
}

HUMANOID_NEGATIVE_TERMS = [
    "低空经济",
    "通航",
    "无人机",
    "UAV",
    "AOPA",
    "航空",
    "eVTOL",
]

CITY_OR_COUNTY_MARKERS = ("市", "区", "县", "园区", "开发区", "产业园", "高新区", "自贸区")

OFFICIAL_RECORD_DIRECT_KEYWORDS = (
    "环评",
    "环保",
    "生态环境",
    "土地",
    "土地出让",
    "自然资源",
    "能评",
    "能耗",
    "项目审批",
    "项目备案",
    "审批",
    "备案",
    "矿权",
)

OFFICIAL_RECORD_CONTEXT_KEYWORDS = (
    "煤化工",
    "现代煤化工",
    "绿氢",
    "盐湖",
    "锂钾",
    "风光资源",
    "新能源项目",
    "土地项目",
)

OFFICIAL_RECORD_PROJECT_KEYWORDS = (
    "项目",
    "资源",
    "消纳",
    "扩张",
    "建设",
    "投产",
)


def build_retrieval_plan(query: str) -> RetrievalPlan:
    return build_deterministic_retrieval_plan(query)


def build_deterministic_retrieval_plan(query: str) -> RetrievalPlan:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        raise ValueError("query must not be empty")

    theme_key, normalized_theme = _infer_theme(normalized_query)
    theme_aliases = _theme_aliases(theme_key, normalized_theme)
    regions = _extract_regions(normalized_query)
    supplemental_domains = SUPPLEMENTAL_DOMAINS_BY_THEME[theme_key]
    lanes = _select_lanes(
        normalized_query=normalized_query,
        theme=normalized_theme,
        theme_key=theme_key,
        regions=regions,
        supplemental_domains=supplemental_domains,
    )
    gaps = _build_initial_coverage_gaps(lanes, query=normalized_query)

    return RetrievalPlan(
        plan_id=f"ret_plan_{hashlib.sha1(normalized_query.encode('utf-8')).hexdigest()[:12]}",
        original_query=normalized_query,
        normalized_theme=normalized_theme,
        theme_aliases=theme_aliases,
        regions=regions or [RegionFocus(name="全国", level="national", parent=None)],
        time_horizon=_infer_time_horizon(normalized_query),
        user_intent=_infer_user_intent(normalized_query),
        coverage_lanes=lanes,
        round_policy=RoundPolicy(),
        stop_conditions=StopConditions(),
        coverage_gaps=gaps,
        planner_metadata=PlannerMetadata(
            planner_provider="deterministic",
            planner_model="offline_rules_v1",
            schema_version="retrieval_plan_v1",
            deterministic_fallback=True,
            repair_applied=False,
            supplemental_theme=theme_key,
            supplemental_domains=supplemental_domains,
            notes=[],
        ),
    )


def _select_lanes(
    *,
    normalized_query: str,
    theme: str,
    theme_key: str,
    regions: list[RegionFocus],
    supplemental_domains: list[str],
) -> list[CoverageLanePlan]:
    requested: list[tuple[CoverageLane, bool, int]] = []
    has_local_region = any(region.name != "全国" for region in regions)
    has_city_or_county = _has_city_or_county_or_park(normalized_query, regions)
    has_park = _has_any(normalized_query, ("园区", "开发区", "产业园", "高新区", "自贸区"))
    has_project = _has_any(
        normalized_query,
        (
            "项目",
            "招标",
            "中标",
            "采购",
            "落地",
            "机会",
            "基建",
            "开工",
            "投产",
            "产能",
            "备案",
            "投资",
        ),
    )
    has_data = _has_any(
        normalized_query,
        (
            "统计",
            "数据",
            "规模",
            "指标",
            "数量",
            "企业数",
            "企业数量",
            "出口",
            "价格",
            "财政",
            "产量",
            "能耗",
            "用工",
            "资源",
            "交通",
            "电力",
            "补贴",
            "土地",
        ),
    )
    has_trade = _has_trade_or_export_angle(normalized_query)
    has_policy = _has_any(normalized_query, ("政策", "规划", "方向", "趋势", "前景", "国家层面"))
    macro_to_local = _needs_macro_to_local_obligation(normalized_query, regions)
    supplemental_only = _is_supplemental_only_query(normalized_query)
    has_company = bool(_extract_company_hint(normalized_query))
    industrial_project_company_evidence = has_project and has_local_region and _has_any(
        normalized_query,
        ("产业", "扩张", "投资", "项目", "产能"),
    )
    explicit_disclosure_query = has_company or _has_any(
        normalized_query,
        (
            "上市公司",
            "公告",
            "披露",
            "年报",
            "企业公告",
            "公司公告",
        ),
    )
    enterprise_control_needed = explicit_disclosure_query or _has_any(
        normalized_query,
        (
            "企业收入",
            "企业订单",
            "企业投资",
            "企业证据",
        ),
    ) or (
        "企业" in normalized_query
        and _has_any(normalized_query, ("验证", "投资", "订单", "收入", "证据", "用工"))
    ) or industrial_project_company_evidence
    disclosure_query = explicit_disclosure_query

    if supplemental_only:
        requested.append((CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL, True, 80))
    elif disclosure_query:
        if macro_to_local:
            requested.append((CoverageLane.NATIONAL_POLICY_DIRECTION, True, 92))
            requested.append((CoverageLane.PROVINCIAL_POLICY_ROLLOUT, True, 88))
        requested.append((CoverageLane.ENTERPRISE_DISCLOSURE, True, 95))
        if has_project or macro_to_local:
            requested.append((CoverageLane.PROJECT_TRANSACTION, True, 90))
        if has_city_or_county and theme_key != "real_estate_demand":
            requested.append((CoverageLane.CITY_COUNTY_FALLBACK, True, 95))
        if has_local_region:
            requested.append((CoverageLane.PROVINCIAL_POLICY_ROLLOUT, False, 60))
        if has_data or has_trade:
            requested.append((CoverageLane.STATISTICS_OR_INDUSTRY_DATA, True, 85))
    else:
        if has_policy or not has_project:
            requested.append((CoverageLane.NATIONAL_POLICY_DIRECTION, True, 90))
        if has_local_region or macro_to_local:
            requested.append((CoverageLane.PROVINCIAL_POLICY_ROLLOUT, True, 95))
        if theme_key == "low_altitude_economy" and _has_any(
            normalized_query,
            ("地方试点", "试点地区", "地方落地"),
        ):
            requested.append((CoverageLane.PROVINCIAL_POLICY_ROLLOUT, True, 88))
        if has_city_or_county and theme_key != "real_estate_demand":
            requested.append((CoverageLane.CITY_COUNTY_FALLBACK, True, 95))
        if has_project or macro_to_local:
            requested.append((CoverageLane.PROJECT_TRANSACTION, True, 88))
        if has_data or has_trade or _should_force_data_lane_for_q03(normalized_query, theme_key):
            requested.append((CoverageLane.STATISTICS_OR_INDUSTRY_DATA, True, 85))
        if enterprise_control_needed:
            requested.append((CoverageLane.ENTERPRISE_DISCLOSURE, True, 85))
        if has_park:
            requested.append((CoverageLane.PARK_ZONE_SIGNAL, True, 92))
        if _has_any(normalized_query, ("协会", "白皮书", "论坛", "补充证据")):
            requested.append((CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL, True, 70))
        elif theme_key == "low_altitude_economy" and _has_any(
            normalized_query,
            ("规模化落地", "地方试点", "空域改革", "适航"),
        ):
            requested.append((CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL, True, 70))
        elif _has_any(normalized_query, ("产业", "趋势", "前景")):
            requested.append((CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL, False, 60))

    if not requested:
        requested.append((CoverageLane.NATIONAL_POLICY_DIRECTION, True, 80))

    deduped: dict[CoverageLane, tuple[bool, int]] = {}
    for lane_id, required, priority in requested:
        previous = deduped.get(lane_id)
        if previous is None:
            deduped[lane_id] = (required, priority)
            continue
        deduped[lane_id] = (previous[0] or required, max(previous[1], priority))

    ordered_lanes = [lane for lane in COVERAGE_LANE_V1 if lane in deduped]
    return [
        _with_evidence_obligations(
            _build_lane_plan(
                lane_id=lane_id,
                required=deduped[lane_id][0],
                priority=deduped[lane_id][1],
                query=normalized_query,
                theme=theme,
                theme_key=theme_key,
                regions=regions,
                supplemental_domains=supplemental_domains,
            ),
            query=normalized_query,
            regions=regions,
        )
        for lane_id in ordered_lanes
    ]


def _with_evidence_obligations(
    lane: CoverageLanePlan,
    *,
    query: str,
    regions: list[RegionFocus],
) -> CoverageLanePlan:
    return lane.model_copy(
        update={
            "evidence_obligations": _evidence_obligations_for_lane(
                lane.lane_id,
                query=query,
                regions=regions,
            )
        }
    )


def _evidence_obligations_for_lane(
    lane_id: CoverageLane,
    *,
    query: str,
    regions: list[RegionFocus],
) -> list[str]:
    level = _evidence_obligation_level(query=query, regions=regions)
    obligations = [f"administrative_granularity:{level}"]
    if level in {"city", "county"} and lane_id != CoverageLane.NATIONAL_POLICY_DIRECTION:
        obligations.append("exact_local_depth")
    if lane_id != CoverageLane.NATIONAL_POLICY_DIRECTION and _needs_multi_city_distribution(
        query,
        regions,
    ):
        obligations.append("multi_city_distribution")
    if lane_id != CoverageLane.NATIONAL_POLICY_DIRECTION and _needs_multi_sector_decomposition(
        query
    ):
        obligations.append("multi_sector_decomposition")
    if (
        lane_id == CoverageLane.STATISTICS_OR_INDUSTRY_DATA
        and _needs_quantitative_metric_evidence(query)
    ):
        obligations.append("quantitative_metric_evidence")
    if lane_id in {
        CoverageLane.PROVINCIAL_POLICY_ROLLOUT,
        CoverageLane.PROJECT_TRANSACTION,
        CoverageLane.STATISTICS_OR_INDUSTRY_DATA,
        CoverageLane.ENTERPRISE_DISCLOSURE,
    } and _needs_macro_to_local_obligation(query, regions):
        obligations.append("macro_to_local_obligation")
    return list(dict.fromkeys(obligations))


def _evidence_obligation_level(*, query: str, regions: list[RegionFocus]) -> str:
    primary_region = regions[0] if regions else None
    if (primary_region and primary_region.level == "county") or _has_any(query, ("县", "旗", "区")):
        return "county"
    if (primary_region and primary_region.level == "municipal") or (
        not regions and _has_any(query, ("市",))
    ):
        return "city"
    if primary_region and primary_region.level == "provincial":
        return "province"
    return "macro"


def _needs_multi_city_distribution(query: str, regions: list[RegionFocus]) -> bool:
    if _evidence_obligation_level(query=query, regions=regions) != "province":
        return False
    return _has_any(
        query,
        (
            "全省多地",
            "多地协同",
            "项目分布",
            "产业分布",
            "区域分布",
            "全省",
            "各地",
        ),
    )


def _needs_multi_sector_decomposition(query: str) -> bool:
    return len(_evidence_sector_terms(query)) >= 2


def _evidence_sector_terms(query: str) -> list[str]:
    sectors: list[str] = []
    for term in (
        "整车",
        "动力电池",
        "电池",
        "零部件",
        "光伏",
        "储能",
        "旅游",
        "医药",
        "航运",
        "数字贸易",
        "钢铁",
        "水泥",
        "家电",
        "工程机械",
        "绿电",
        "绿氢",
        "煤化工",
        "半导体",
        "商业航天",
        "卫星",
    ):
        if term in query and term not in sectors:
            sectors.append(term)
    return sectors


def _focused_evidence_sector_terms(query: str) -> list[str]:
    sectors = _evidence_sector_terms(query)
    if len(sectors) > 3 and _has_any(query, ("扩展到", "还是已经扩展", "是否已经扩展")):
        return sectors[-3:]
    return sectors


def _multi_city_distribution_search_phrases(
    *,
    lane_id: CoverageLane,
    theme: str,
    regions: list[RegionFocus],
    query: str,
) -> list[str]:
    if not _needs_multi_city_distribution(query, regions):
        return []
    region = _primary_region(regions)
    city_hints = PROVINCE_DISTRIBUTION_CITY_HINTS.get(region, [])
    if len(city_hints) < 2:
        return []
    first_city, second_city = city_hints[0], city_hints[1]
    if lane_id == CoverageLane.PROVINCIAL_POLICY_ROLLOUT:
        return [
            f"{region} {theme} 多地协同 产业链",
            f"{first_city} {theme} 产业 政策",
            f"{second_city} {theme} 产业 政策",
        ]
    if lane_id == CoverageLane.PROJECT_TRANSACTION:
        return [
            f"{first_city} {theme} 重点项目 开工 投产",
            f"{second_city} {theme} 公共资源交易 招标 中标",
            f"{region} {theme} 项目分布 重点项目",
        ]
    if lane_id == CoverageLane.STATISTICS_OR_INDUSTRY_DATA:
        return [
            f"{region} {theme} 统计 数据",
            f"{first_city} {theme} 产量 统计",
            f"{second_city} {theme} 统计公报",
        ]
    return []


def _multi_sector_search_phrases(
    *,
    lane_id: CoverageLane,
    theme: str,
    region: str,
    query: str,
) -> list[str]:
    sectors = _focused_evidence_sector_terms(query)
    if len(sectors) < 2:
        return []
    first = sectors[0]
    second = sectors[1]
    third = sectors[2] if len(sectors) > 2 else sectors[0]
    if lane_id == CoverageLane.PROVINCIAL_POLICY_ROLLOUT:
        return [
            f"{region} {first} 产业 政策",
            f"{region} {second} 产业 政策",
            f"{region} {third} 产业 政策",
        ]
    if lane_id == CoverageLane.PROJECT_TRANSACTION:
        return [
            f"{region} {first} 项目 重点项目 开工 投产 招标",
            f"{region} {second} 项目 重点项目 开工 投产 招标",
            f"{region} {third} 项目 采购 开工 投产",
        ]
    if lane_id == CoverageLane.STATISTICS_OR_INDUSTRY_DATA:
        return [
            f"{region} {' '.join(sectors[:3])} 统计 数据",
            f"{region} {first} 产量 价格 数据",
            f"{region} {second} 规模 数据",
        ]
    return []


def _needs_quantitative_metric_evidence(query: str) -> bool:
    return _has_any(
        query,
        (
            "统计",
            "数据",
            "指标",
            "规模",
            "产量",
            "销量",
            "价格",
            "市场价格",
            "成本",
            "需求",
            "资源",
            "交通",
            "电力",
            "财政",
            "补贴",
            "资金",
            "收入",
            "用工",
            "企业数量",
            "开工数据",
            "下游需求",
        ),
    )


def _needs_macro_to_local_obligation(query: str, regions: list[RegionFocus]) -> bool:
    has_local_region = any(region.name != "全国" for region in regions)
    if has_local_region:
        return False
    macro_scope = not regions or all(region.name == "全国" for region in regions) or _has_any(
        query,
        ("国家层面", "中央", "全国"),
    )
    if not macro_scope:
        return False
    asks_for_policy_to_real_world = _has_any(
        query,
        (
            "是否已经转化为",
            "是否能实质",
            "是否已经进入",
            "政策到",
            "政策落地",
            "规模化落地",
            "真实",
            "实际",
            "交叉验证",
            "验证",
        ),
    )
    requires_local_or_operational_evidence = _has_any(
        query,
        (
            "地方项目清单",
            "项目清单",
            "建设需求",
            "地方试点",
            "实际项目",
            "真实项目",
            "项目落地",
            "项目建设",
            "开工",
            "投产",
            "用电",
            "能耗",
            "成本",
            "约束",
            "资金来源",
            "企业订单",
            "企业公告",
            "企业收入",
            "下游需求",
        ),
    )
    return asks_for_policy_to_real_world and requires_local_or_operational_evidence


def _build_lane_plan(
    *,
    lane_id: CoverageLane,
    required: bool,
    priority: int,
    query: str,
    theme: str,
    theme_key: str,
    regions: list[RegionFocus],
    supplemental_domains: list[str],
) -> CoverageLanePlan:
    region = _primary_region(regions)
    negative_terms = HUMANOID_NEGATIVE_TERMS if theme_key == "humanoid_robotics" else []
    trade_angle = _has_trade_or_export_angle(query)
    macro_to_local = _needs_macro_to_local_obligation(query, regions)

    if lane_id == CoverageLane.NATIONAL_POLICY_DIRECTION:
        search_phrases = [
            f"{theme} 国家政策 规划",
            f"{theme} 指导意见",
            f"{theme} 部委 政策",
        ]
        fallback_ladder = [
            "state_council_portal",
            "national_drc",
            "national_miit",
        ]
        if theme_key == "real_estate_demand":
            search_phrases = [
                "房地产 去库存 城中村改造 三大工程 住房城乡建设部",
                "房地产 地方收储 政策 住房城乡建设部",
                "城中村改造 保障性住房 平急两用 资金来源",
            ]
            fallback_ladder = [
                "state_council_portal",
                "national_drc",
                "mohurd_policy",
                "national_statistics",
            ]
        return CoverageLanePlan(
            lane_id=lane_id,
            required=required,
            priority=priority,
            source_intents=[
                SourceIntent.STATE_COUNCIL,
                SourceIntent.NATIONAL_DRC,
                SourceIntent.NATIONAL_MIIT,
            ],
            execution_bucket=ExecutionBucket.SEARCH_ASSISTED_SOURCES,
            domain_strategy=DomainStrategy.NATIONAL_OFFICIAL_DOMAINS_ONLY,
            search_phrases=search_phrases,
            negative_terms=negative_terms,
            success_criteria=LaneSuccessCriteria(
                min_accepted_documents=1,
                must_match_region=False,
                must_match_theme=True,
                must_match_source_role=True,
            ),
            fallback_ladder=fallback_ladder,
        )

    if lane_id == CoverageLane.PROVINCIAL_POLICY_ROLLOUT:
        search_phrases = (
            _multi_city_distribution_search_phrases(
                lane_id=lane_id,
                theme=theme,
                regions=regions,
                query=query,
            )
            or _multi_sector_search_phrases(
                lane_id=lane_id,
                theme=theme,
                region=region,
                query=query,
            )
            or [
                f"{region} {theme} 政策",
                f"{region} {theme} 行动计划",
                f"{region} {theme} 试点",
            ]
        )
        if macro_to_local:
            search_phrases = [
                f"{theme} 地方项目清单 政策落地",
                f"{theme} 省市 重点项目 建设",
                f"{theme} 地方 用电 能耗 项目",
            ]
        return CoverageLanePlan(
            lane_id=lane_id,
            required=required,
            priority=priority,
            source_intents=[
                SourceIntent.PROVINCE_GOVERNMENT,
                SourceIntent.PROVINCE_DRC,
                SourceIntent.PROVINCE_INDUSTRY_DEPARTMENT,
            ],
            execution_bucket=ExecutionBucket.SEARCH_ASSISTED_SOURCES,
            domain_strategy=DomainStrategy.REGION_OFFICIAL_DOMAINS_ONLY,
            search_phrases=search_phrases,
            negative_terms=negative_terms,
            success_criteria=LaneSuccessCriteria(
                min_accepted_documents=1,
                must_match_region=not macro_to_local,
                must_match_theme=True,
                must_match_source_role=True,
            ),
            fallback_ladder=[
                "province_government_portal",
                "province_drc",
                "province_industry_department",
                "national_policy_direction",
            ],
        )

    if lane_id == CoverageLane.CITY_COUNTY_FALLBACK:
        return CoverageLanePlan(
            lane_id=lane_id,
            required=required,
            priority=priority,
            source_intents=[
                SourceIntent.CITY_GOVERNMENT,
                SourceIntent.CITY_DRC,
                SourceIntent.CITY_INDUSTRY_DEPARTMENT,
            ],
            execution_bucket=ExecutionBucket.SEARCH_ASSISTED_SOURCES,
            domain_strategy=DomainStrategy.FALLBACK_LADDER_OFFICIAL_FIRST,
            search_phrases=[
                f"{region} {theme} 地方政策",
                f"{region} {theme} 落地",
                f"{region} {theme} 试点项目",
            ],
            negative_terms=negative_terms,
            success_criteria=LaneSuccessCriteria(
                min_accepted_documents=1,
                must_match_region=True,
                must_match_theme=True,
                must_match_source_role=True,
                require_exact_local_match=True,
                allow_parent_fallback=True,
                parent_fallback_requires_gap=True,
            ),
            fallback_ladder=[
                "exact_city_county_or_park_official_domain",
                "city_government_portal",
                "city_drc_industry_science_statistics",
                "province_government_portal",
                "province_drc_industry_science_statistics",
                "national_official_or_structured_data",
            ],
        )

    if lane_id == CoverageLane.STATISTICS_OR_INDUSTRY_DATA:
        source_intents = [
            SourceIntent.NATIONAL_STATISTICS,
            SourceIntent.PROVINCE_STATISTICS,
            SourceIntent.CITY_STATISTICS,
        ]
        search_phrases = [
            f"{region} {theme} 统计数据",
            f"{region} {theme} 规模 企业数量",
            f"{region} {theme} 指标",
        ]
        fallback_ladder = [
            "national_statistics",
            "province_statistics",
            "city_statistics",
        ]
        obligation_phrases = (
            _multi_city_distribution_search_phrases(
                lane_id=lane_id,
                theme=theme,
                regions=regions,
                query=query,
            )
            or _multi_sector_search_phrases(
                lane_id=lane_id,
                theme=theme,
                region=region,
                query=query,
            )
        )
        if obligation_phrases and theme_key != "real_estate_demand":
            search_phrases = obligation_phrases
        if macro_to_local:
            search_phrases = [
                f"{theme} 用电 能耗 数据",
                f"{theme} 建设需求 统计",
                f"{theme} 地方项目 投资 数据",
            ]
        if theme_key == "real_estate_demand":
            search_phrases = [
                "房地产开发投资 新开工面积 销售面积 库存 国家统计局",
                "商品房销售面积 待售面积 房地产 国家统计局",
                "房屋新开工 竣工面积 统计数据",
            ]
        if trade_angle and not obligation_phrases:
            source_intents.extend(
                [
                    SourceIntent.NATIONAL_CUSTOMS,
                    SourceIntent.NATIONAL_COMMERCE,
                    SourceIntent.PROVINCE_COMMERCE,
                ]
            )
            search_phrases = [
                f"{region} {theme} 出口 贸易风险",
                f"{region} {theme} 海关 出口 数据",
                f"{region} {theme} 商务 外贸 政策",
            ]
            fallback_ladder.extend(
                [
                    "customs_trade_data",
                    "national_commerce",
                    "province_commerce",
                ]
            )
        return CoverageLanePlan(
            lane_id=lane_id,
            required=required,
            priority=priority,
            source_intents=source_intents,
            execution_bucket=ExecutionBucket.DIRECT_STRUCTURED_SOURCES,
            domain_strategy=DomainStrategy.DIRECT_STRUCTURED_ONLY,
            search_phrases=search_phrases,
            negative_terms=negative_terms,
            success_criteria=LaneSuccessCriteria(
                min_accepted_documents=1,
                must_match_region=True,
                must_match_theme=False,
                must_match_source_role=True,
            ),
            fallback_ladder=fallback_ladder,
        )

    if lane_id == CoverageLane.PROJECT_TRANSACTION:
        search_phrases = [
            f"{region} {theme} 招标 中标",
            f"{region} {theme} 采购 项目",
            f"{region} {theme} 项目 落地",
        ]
        obligation_phrases = (
            _multi_city_distribution_search_phrases(
                lane_id=lane_id,
                theme=theme,
                regions=regions,
                query=query,
            )
            or _multi_sector_search_phrases(
                lane_id=lane_id,
                theme=theme,
                region=region,
                query=query,
            )
        )
        if obligation_phrases and theme_key != "real_estate_demand":
            search_phrases = obligation_phrases
        if macro_to_local:
            search_phrases = [
                f"{theme} 地方项目清单 重点项目",
                f"{theme} 公共资源交易 招标 中标",
                f"{theme} 用电 能耗 建设需求 项目",
            ]
        if theme_key == "real_estate_demand":
            search_phrases = [
                "城中村改造 项目 开工 资金来源",
                "三大工程 保障性住房 平急两用 项目",
                "房地产 收储 项目 专项债",
            ]
        return CoverageLanePlan(
            lane_id=lane_id,
            required=required,
            priority=priority,
            source_intents=[
                SourceIntent.PUBLIC_RESOURCE_TRADE,
                SourceIntent.GOVERNMENT_PROCUREMENT,
                SourceIntent.NATIONAL_DRC,
            ],
            execution_bucket=ExecutionBucket.DIRECT_STRUCTURED_SOURCES,
            domain_strategy=DomainStrategy.DIRECT_STRUCTURED_ONLY,
            search_phrases=search_phrases,
            negative_terms=negative_terms,
            success_criteria=LaneSuccessCriteria(
                min_accepted_documents=1,
                must_match_region=True,
                must_match_theme=True,
                must_match_source_role=True,
            ),
            fallback_ladder=[
                "public_resource_trade",
                "government_procurement",
                "ndrc_project_signals",
            ],
        )

    if lane_id == CoverageLane.ENTERPRISE_DISCLOSURE:
        search_phrases = [
            f"{theme} 上市公司 公告",
            f"{theme} 项目 进展 披露",
            "年报 公告",
        ]
        if theme_key == "real_estate_demand":
            search_phrases = [
                "钢铁 水泥 家电 工程机械 房地产 需求 年报",
                "上市公司 房地产 下游需求 收入 披露",
                "房地产 开工 竣工 销售 企业收入 公告",
            ]
        return CoverageLanePlan(
            lane_id=lane_id,
            required=required,
            priority=priority,
            source_intents=[SourceIntent.EXCHANGE_DISCLOSURE],
            execution_bucket=ExecutionBucket.DIRECT_STRUCTURED_SOURCES,
            domain_strategy=DomainStrategy.DIRECT_STRUCTURED_ONLY,
            search_phrases=search_phrases,
            negative_terms=negative_terms,
            success_criteria=LaneSuccessCriteria(
                min_accepted_documents=1,
                must_match_region=False,
                must_match_theme=True,
                must_match_source_role=True,
            ),
            fallback_ladder=[
                "cninfo_disclosure",
                "sse_disclosure",
                "szse_disclosure",
            ],
        )

    if lane_id == CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL:
        return CoverageLanePlan(
            lane_id=lane_id,
            required=required,
            priority=priority,
            source_intents=[SourceIntent.THEME_ASSOCIATION],
            execution_bucket=ExecutionBucket.SEARCH_ASSISTED_SOURCES,
            domain_strategy=DomainStrategy.THEME_SUPPLEMENTAL_DOMAINS_ONLY,
            search_phrases=[
                f"{theme} 协会 白皮书",
                f"{theme} 论坛",
                f"{theme} 产业 报告",
            ],
            negative_terms=negative_terms,
            allowed_domains=supplemental_domains,
            success_criteria=LaneSuccessCriteria(
                min_accepted_documents=1,
                must_match_region=False,
                must_match_theme=True,
                must_match_source_role=True,
            ),
            fallback_ladder=[
                "theme_association_domains_only",
            ],
        )

    if lane_id == CoverageLane.PARK_ZONE_SIGNAL:
        return CoverageLanePlan(
            lane_id=lane_id,
            required=required,
            priority=priority,
            source_intents=[
                SourceIntent.PARK_ZONE_OFFICIAL,
                SourceIntent.CITY_GOVERNMENT,
                SourceIntent.PROVINCE_GOVERNMENT,
            ],
            execution_bucket=ExecutionBucket.SEARCH_ASSISTED_SOURCES,
            domain_strategy=DomainStrategy.FALLBACK_LADDER_OFFICIAL_FIRST,
            search_phrases=[
                f"{region} {theme} 园区 政策",
                f"{region} {theme} 开发区 项目",
                f"{region} {theme} 产业园 机会",
            ],
            negative_terms=negative_terms,
            success_criteria=LaneSuccessCriteria(
                min_accepted_documents=1,
                must_match_region=True,
                must_match_theme=True,
                must_match_source_role=True,
                require_exact_local_match=True,
                allow_parent_fallback=True,
                parent_fallback_requires_gap=True,
            ),
            fallback_ladder=[
                "park_zone_official_site",
                "city_government_portal",
                "province_government_portal",
                "national_policy_direction",
            ],
        )

    return CoverageLanePlan(
        lane_id=CoverageLane.MEDIA_NEWS_CONTEXT,
        required=required,
        priority=priority,
        source_intents=[SourceIntent.OFFICIAL_MEDIA],
        execution_bucket=ExecutionBucket.SEARCH_ASSISTED_SOURCES,
        domain_strategy=DomainStrategy.MANUAL_OR_PLACEHOLDER,
        search_phrases=[query, f"{theme} 背景", f"{theme} 新闻"],
        negative_terms=negative_terms,
        success_criteria=LaneSuccessCriteria(
            min_accepted_documents=1,
            must_match_region=False,
            must_match_theme=False,
            must_match_source_role=True,
        ),
        fallback_ladder=["official_media", "institutional_media"],
    )


def _build_initial_coverage_gaps(
    lanes: list[CoverageLanePlan],
    *,
    query: str,
) -> list[CoverageGap]:
    gaps: list[CoverageGap] = []
    for lane in lanes:
        if lane.lane_id in {CoverageLane.CITY_COUNTY_FALLBACK, CoverageLane.PARK_ZONE_SIGNAL}:
            gaps.append(
                CoverageGap(
                    lane_id=lane.lane_id,
                    reason_code="local_source_pending_exact_match",
                    required=lane.required,
                    fallback_level="exact_local_required",
                    fallback_source=lane.fallback_ladder[0] if lane.fallback_ladder else None,
                    parent_evidence_only=True,
                    local_claim_allowed=False,
                    notes=[
                        "parent evidence must not masquerade as city/county/park coverage",
                    ],
                )
            )
        if lane.required and lane.execution_bucket == ExecutionBucket.DIRECT_STRUCTURED_SOURCES:
            gaps.append(
                CoverageGap(
                    lane_id=lane.lane_id,
                    reason_code="direct_structured_primary_path_required",
                    required=True,
                    fallback_level="direct_structured_required",
                    fallback_source=lane.fallback_ladder[0] if lane.fallback_ladder else None,
                    parent_evidence_only=False,
                    local_claim_allowed=False,
                    notes=[
                        "direct structured lane is a protected control path, "
                        "not satisfied by Tavily search-assisted evidence",
                    ],
                )
            )
    if _needs_environmental_land_record_gap(query):
        gaps.insert(
            0,
            CoverageGap(
                lane_id=CoverageLane.PROJECT_TRANSACTION,
                reason_code="official_record_adapter_not_available",
                required=True,
                fallback_level="official_record_required",
                fallback_source="environmental_or_land_record",
                parent_evidence_only=False,
                local_claim_allowed=False,
                notes=[
                    "source_class:environmental_or_land_record",
                    "source_class:regulatory_record",
                    "expected_records:eia,natural_resources,land_transfer,project_filing",
                    "domestic official-record adapter is not available in v1",
                    "do not treat procurement/project evidence as environmental or land coverage",
                ],
            )
        )
    if _needs_employment_or_labor_gap(query):
        gaps.append(
            CoverageGap(
                lane_id=CoverageLane.STATISTICS_OR_INDUSTRY_DATA,
                reason_code="employment_or_labor_data_adapter_not_available",
                required=True,
                fallback_level="direct_structured_required",
                fallback_source="employment_or_labor_data",
                parent_evidence_only=False,
                local_claim_allowed=False,
                notes=[
                    "source_class:employment_or_labor_data",
                    "expected_records:employment,labor,use_data,workforce",
                    "domestic employment/use data adapter is not available in v1",
                    "do not treat local project or policy evidence as employment/use data coverage",
                ],
            )
        )
    return gaps


def _needs_environmental_land_record_gap(query: str) -> bool:
    if _has_any(query, OFFICIAL_RECORD_DIRECT_KEYWORDS):
        return True
    return _has_any(query, OFFICIAL_RECORD_CONTEXT_KEYWORDS) and _has_any(
        query,
        OFFICIAL_RECORD_PROJECT_KEYWORDS,
    )


def _needs_employment_or_labor_gap(query: str) -> bool:
    return _has_any(query, ("用工", "就业", "招聘", "劳动力", "员工", "岗位"))


def _theme_aliases(theme_key: str, normalized_theme: str) -> list[str]:
    aliases = THEME_ALIAS_MAP.get(theme_key, [])
    if normalized_theme not in aliases:
        aliases = [normalized_theme, *aliases]
    deduped: list[str] = []
    for alias in aliases:
        if alias and alias not in deduped:
            deduped.append(alias)
    return deduped


def _extract_regions(query: str) -> list[RegionFocus]:
    regions: list[RegionFocus] = []
    for name, level in REGION_LEVEL_BY_NAME.items():
        if name in query and name not in {region.name for region in regions}:
            parent = "全国" if name != "全国" else None
            regions.append(RegionFocus(name=name, level=level, parent=parent))
    if not regions and _has_any(query, ("国家层面", "中央", "全国")):
        regions.append(RegionFocus(name="全国", level="national", parent=None))
    return regions


def _primary_region(regions: list[RegionFocus]) -> str:
    if not regions:
        return "全国"
    return regions[0].name


def _infer_theme(query: str) -> tuple[str, str]:
    if _has_any(query, ("房地产", "城中村改造", "三大工程", "地方收储", "去库存")):
        return "real_estate_demand", "房地产"
    if _has_any(query, ("人形机器人", "具身智能")):
        return "humanoid_robotics", "人形机器人"
    if _has_any(query, ("低空经济", "通航", "无人机", "eVTOL")):
        return "low_altitude_economy", "低空经济"
    if _has_any(query, ("算力基础设施", "算力", "智算中心", "数据中心")):
        return "computing_infrastructure", "算力基础设施"
    if _has_any(query, ("新能源汽车", "动力电池", "整车", "汽车零部件")):
        return "new_energy_vehicle", "新能源汽车"
    if _has_any(query, ("光伏", "光伏产业链")):
        return "photovoltaics", "光伏产业链"
    if _has_any(query, ("绿电", "绿氢", "煤化工", "现代煤化工")):
        return "green_hydrogen_coal_chemical", "绿电绿氢煤化工"
    if _has_any(query, ("自由贸易港", "海南自由贸易港")):
        return "free_trade_port", "自由贸易港"
    if _has_any(query, ("换电", "新能源汽车换电")):
        return "battery_swap", "新能源汽车换电"

    cleaned = re.sub(r"[（）()，,。？?\s]+", " ", query)
    cleaned = re.sub(
        r"(政策|项目|方向|趋势|情况|信号|机会|白皮书|论坛|补充证据|有哪些|如何|什么)",
        " ",
        cleaned,
    )
    cleaned = _normalize_text(cleaned)
    return "unknown", cleaned[:30] if cleaned else query[:30]


def _infer_time_horizon(query: str) -> str:
    if _has_any(query, ("未来", "前景", "趋势", "方向")):
        return "future_outlook"
    if _has_any(query, ("最新", "当前", "目前")):
        return "latest_focus"
    return "unspecified"


def _infer_user_intent(query: str) -> str:
    if _has_any(query, ("公告", "披露", "上市公司")):
        return "disclosure_and_project_tracking"
    if _has_any(query, ("招标", "中标", "采购", "落地", "项目")):
        return "policy_and_project_rollout_assessment"
    if _has_any(query, ("白皮书", "论坛", "协会", "补充证据")):
        return "supplemental_signal_collection"
    return "policy_and_industry_signal_assessment"


def _should_force_data_lane_for_q03(query: str, theme_key: str) -> bool:
    return theme_key == "humanoid_robotics" and _has_any(query, ("政策", "项目", "落地"))


def _has_trade_or_export_angle(query: str) -> bool:
    return _has_any(
        query,
        ("出海", "贸易", "外贸", "出口", "海关", "关税", "反倾销", "贸易风险"),
    )


def _has_city_or_county_or_park(query: str, regions: list[RegionFocus]) -> bool:
    if _has_any(query, CITY_OR_COUNTY_MARKERS):
        return True
    return any(region.level in {"municipal", "county"} for region in regions)


def _extract_company_hint(query: str) -> str:
    ticker = re.search(r"\b(\d{6}\.(?:SZ|SH|BJ))\b", query, flags=re.IGNORECASE)
    if ticker:
        return ticker.group(1).upper()
    return ""


def _is_supplemental_only_query(query: str) -> bool:
    if not _has_any(query, ("协会", "白皮书", "论坛", "联盟", "展会")):
        return False
    return not _has_any(query, ("政策", "规划", "招标", "中标", "采购", "公告", "披露"))


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def lane_for_task_family(task_family: str) -> CoverageLane | None:
    return TASK_FAMILY_TO_LANE.get(task_family.strip().lower())


def is_supplemental_or_fallback_lane(lane_id: CoverageLane) -> bool:
    return lane_id in ROUND3_SUPPLEMENTAL_OR_FALLBACK_LANES


__all__ = [
    "CoverageGap",
    "CoverageLane",
    "CoverageLanePlan",
    "COVERAGE_LANE_V1",
    "DomainStrategy",
    "ExecutionBucket",
    "ROUND3_SUPPLEMENTAL_OR_FALLBACK_LANES",
    "TASK_FAMILY_TO_LANE",
    "LaneSuccessCriteria",
    "PlannerMetadata",
    "RegionFocus",
    "RetrievalPlan",
    "RoundPolicy",
    "SourceIntent",
    "StopConditions",
    "build_deterministic_retrieval_plan",
    "build_retrieval_plan",
    "is_supplemental_or_fallback_lane",
    "lane_for_task_family",
]
