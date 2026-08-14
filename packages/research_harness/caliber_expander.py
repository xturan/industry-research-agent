"""Search Caliber Expansion — two-layer LLM + deterministic guard.

Per PRD v0.1:
  Layer 1 (Intent Planner):    query → intent_plan
  Layer 2 (Search Phrase Builder): query + intent_plan → search_plan
  Deterministic Guard:         search_plan → final_search_plan + review

Does NOT execute searches. Does NOT maintain industry-specific slot libraries.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.core.config import get_settings
from packages.providers import DeepSeekProviderClient, ProviderConfigError
from packages.providers.base import JsonProviderClient
from packages.research_harness import research_taxonomy
from packages.research_harness.plan_semantic import (
    SemanticDimensionPlanEntry,
    SemanticQueryRequirements,
    SemanticResearchDimension,
    SemanticSourceObligation,
)

# ── Pydantic Schemas (matching PRD section 9.3 & 10.3) ────────────────────


class UserGoal(BaseModel):
    """PRD 9.3: user_goal"""
    model_config = ConfigDict(extra="forbid")

    goal_type: str = Field(default="evidence_verification", max_length=60)
    goal_description: str = Field(default="", max_length=400)
    is_evidence_verification: bool = True
    is_location_sensitive: bool = False
    is_time_sensitive: bool = False


class ExplicitConstraints(BaseModel):
    """PRD 9.3: explicit_constraints"""
    model_config = ConfigDict(extra="forbid")

    time: list[str] = Field(default_factory=list, max_length=4)
    locations: list[str] = Field(default_factory=list, max_length=6)
    companies: list[str] = Field(default_factory=list, max_length=6)
    industries_or_topics: list[str] = Field(default_factory=list, max_length=8)
    required_source_style: list[str] = Field(default_factory=list, max_length=8)


class QueryLevel(BaseModel):
    """PRD 9.3: query_levels item"""
    model_config = ConfigDict(extra="forbid")

    level: str = Field(min_length=1, max_length=40)
    priority: str = Field(default="medium", max_length=20)
    reason: str = Field(default="", max_length=300)


class EvidenceNeed(BaseModel):
    """PRD 9.3: evidence_needs item — four-class status.

    required = must be searched now
    optional = search if budget/quality allows
    deferred = record for later, don't search now
    skip = explicitly excluded
    """
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    status: str = Field(default="required", max_length=20)  # required|optional|deferred|skip
    priority: str = Field(default="medium", max_length=20)   # high|medium|low
    why_needed: str = Field(default="", max_length=400)
    what_to_verify: str = Field(default="", max_length=400)
    suggested_caliber_terms: list[str] = Field(default_factory=list, max_length=8)
    source_type_preference: list[str] = Field(default_factory=list, max_length=8)
    noise_risk: str = Field(default="medium", max_length=20)  # low|medium|high


class ExpansionPolicy(BaseModel):
    """PRD 9.3: expansion_policy"""
    model_config = ConfigDict(extra="forbid")

    should_expand_topic_terms: bool = True
    should_expand_location_levels: bool = False
    should_expand_company_terms: bool = False
    should_expand_project_terms: bool = True
    expansion_limits: str = Field(default="", max_length=500)


class SearchBudgetAdvice(BaseModel):
    """PRD 9.3: search_budget_advice"""
    model_config = ConfigDict(extra="forbid")

    recommended_rounds: int = Field(default=3, ge=1, le=12)
    recommended_phrases_per_round: int = Field(default=4, ge=1, le=8)
    must_cover_original_query: bool = True
    original_query_anchor_ratio: str = Field(default="20%-30%", max_length=20)


class IntentPlan(BaseModel):
    """PRD 9.3: full Layer 1 output."""
    model_config = ConfigDict(extra="forbid")

    normalized_query: str = Field(min_length=1, max_length=500)
    user_goal: UserGoal = Field(default_factory=UserGoal)
    explicit_constraints: ExplicitConstraints = Field(default_factory=ExplicitConstraints)
    query_levels: list[QueryLevel] = Field(default_factory=list, max_length=8)
    evidence_needs: list[EvidenceNeed] = Field(default_factory=list, max_length=10)
    expansion_policy: ExpansionPolicy = Field(default_factory=ExpansionPolicy)
    search_budget_advice: SearchBudgetAdvice = Field(default_factory=SearchBudgetAdvice)
    caliber_notes: list[str] = Field(default_factory=list, max_length=8)
    research_dimensions: list[SemanticResearchDimension] = Field(
        default_factory=list, max_length=8
    )
    dimension_plan: list[SemanticDimensionPlanEntry] = Field(
        default_factory=list, max_length=8
    )
    source_obligations: list[SemanticSourceObligation] = Field(
        default_factory=list, max_length=8
    )
    query_requirements: SemanticQueryRequirements = Field(
        default_factory=SemanticQueryRequirements
    )


# ── Search Plan Schemas (PRD 10.3) ──


class SearchStrategySummary(BaseModel):
    """PRD 10.3: search_strategy_summary"""
    model_config = ConfigDict(extra="forbid")

    original_query: str = Field(min_length=1, max_length=500)
    normalized_query: str = Field(default="", max_length=500)
    total_rounds: int = Field(default=1, ge=1, le=12)
    total_phrases: int = Field(default=0, ge=0, le=80)
    anchor_phrase_count: int = Field(default=0, ge=0, le=10)
    non_anchor_phrase_count: int = Field(default=0, ge=0, le=75)


class AnchorPhrase(BaseModel):
    """PRD 10.3: anchor_phrases item"""
    model_config = ConfigDict(extra="forbid")

    phrase: str = Field(min_length=1, max_length=300)
    anchor_type: str = Field(min_length=1, max_length=40)  # original_query|normalized_query
    reason: str = Field(default="", max_length=300)


class SearchPhrase(BaseModel):
    """PRD 10.3: search_phrases item within a group"""
    model_config = ConfigDict(extra="forbid")

    phrase: str = Field(min_length=1, max_length=200)
    phrase_type: str = Field(default="", max_length=60)
    intent: str = Field(default="", max_length=400)
    reason: str = Field(default="", max_length=400)


class SearchGroup(BaseModel):
    """PRD 10.3: search_groups item"""
    model_config = ConfigDict(extra="forbid")

    group_id: str = Field(min_length=1, max_length=20)
    group_name: str = Field(default="", max_length=80)
    dominant_intent: str = Field(default="", max_length=400)
    target_evidence_need: str = Field(default="", max_length=80)
    priority: str = Field(default="medium", max_length=20)
    target_level: str = Field(default="", max_length=120)
    source_type_preference: list[str] = Field(default_factory=list, max_length=8)
    search_phrases: list[SearchPhrase] = Field(default_factory=list, max_length=8)


class DeferredSearchIdea(BaseModel):
    """PRD 10.3: deferred_search_ideas item"""
    model_config = ConfigDict(extra="forbid")

    evidence_need: str = Field(min_length=1, max_length=80)
    defer_reason: str = Field(default="", max_length=400)
    possible_future_phrases: list[str] = Field(default_factory=list, max_length=6)


class QualityChecks(BaseModel):
    """PRD 10.3: quality_checks"""
    model_config = ConfigDict(extra="forbid")

    has_original_query_anchor: bool = False
    has_normalized_query_anchor: bool = False
    avoids_suffix_only_variants: bool = False
    each_group_has_single_dominant_intent: bool = False
    does_not_expand_all_possible_directions: bool = False


class SearchPlan(BaseModel):
    """PRD 10.3: full Layer 2 output."""
    model_config = ConfigDict(extra="forbid")

    search_strategy_summary: SearchStrategySummary = Field(
        default_factory=SearchStrategySummary
    )
    anchor_phrases: list[AnchorPhrase] = Field(default_factory=list, max_length=6)
    search_groups: list[SearchGroup] = Field(default_factory=list, max_length=12)
    deferred_search_ideas: list[DeferredSearchIdea] = Field(
        default_factory=list, max_length=8
    )
    quality_checks: QualityChecks = Field(default_factory=QualityChecks)


# ── Final Output ──


@dataclass(slots=True)
class CaliberExpansionResult:
    query: str
    normalized_query: str
    intent_plan: dict[str, Any]
    search_plan: dict[str, Any]
    final_search_plan: dict[str, Any]
    filtered_out: list[dict[str, str]] = field(default_factory=list)
    guard_review: dict[str, Any] = field(default_factory=dict)
    fallback_used: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Prompts ────────────────────────────────────────────────────────────────

INTENT_PLANNER_SYSTEM = (
    "你是一个研究查询意图识别专家。你的唯一职责是理解用户要研究什么，"
    "不生成搜索词，不回答问题，不虚构事实。\n\n"
    "判断规则：\n"
    "1. 识别查询主题、地点、时间、企业、行业、源类型等显式约束\n"
    "2. 判断查询涉及的层级：国家/省/市/县区/行业/企业/项目/数据/披露\n"
    "3. 判断需要哪些证据面向，并标记为 required/optional/deferred/skip\n"
    "   - required: 查询明确要求的方向，必须搜索\n"
    "   - optional: 查询暗示但未强制，预算允许时搜索\n"
    "   - deferred: 可能需要但不紧急，记录但不执行\n"
    "   - skip: 与查询无关或不建议展开\n"
    "4. 判断扩展策略：是否展开主题词、地域层级、公司名、项目名\n"
    "5. 给出搜索预算建议\n"
    "6. 输出研究结构：research_dimensions/dimension_plan/source_obligations/"
    "query_requirements。\n"
    "7. dimension_type 用以下产业调研维度。一般产业调研必须覆盖全部 10 个基础维度"
    "（每个都要进入 dimension_plan，研究问题/覆盖要求按该维度具体化）；"
    "条件维度按查询意图追加:\n"
    "   基础(必须全部输出): industry_scope(产业定义边界)/policy_regulation(政策与监管)/"
    "market_scale(市场规模与增长)/industry_chain(产业链与价值链)/"
    "supply_competition(供给与竞争格局)/demand_scenarios(需求与应用场景)/"
    "technology_product(技术路线与产品成熟度)/project_execution(项目落地与执行)/"
    "business_economics(商业模式与产业经济性)/risk_constraints(风险约束与瓶颈)\n"
    "   条件(按意图追加): company_fundamentals(企业经营财务, "
    "查询涉年报/披露/上市公司/重点企业时启用)/"
    "capital_activity(投融资, 涉融资/投资/并购/基金时启用)/"
    "regional_benchmark(区域比较, 地方产业调研默认启用)/"
    "outlook_drivers(趋势前景, 涉前景/趋势/预测/展望时启用)\n\n"
    "输出严格 JSON。"
)

INTENT_PLANNER_USER_TEMPLATE = (
    "分析以下研究查询的意图:\n"
    "Query: {query}\n\n"
    "返回 JSON，包含: normalized_query, user_goal, explicit_constraints, "
    "query_levels, evidence_needs, expansion_policy, search_budget_advice, "
    "caliber_notes, research_dimensions, dimension_plan, source_obligations, "
    "query_requirements\n\n"
    "每个 evidence_need 必须包含 name/status/priority/why_needed/"
    "what_to_verify/suggested_caliber_terms/source_type_preference/noise_risk\n\n"
    "研究结构字段（高保真，字段名必须完全一致）:\n"
    "- research_dimensions: 每项含 dimension_id/label/description/caliber_terms/"
    "source_priority\n"
    "- dimension_plan: 每项必须完整填写 dimension_id/dimension_type/"
    "research_question/why_it_matters/coverage_required/expected_section_heading/"
    "source_priority/source_families/caliber_terms；"
    "必须覆盖全部 10 个基础维度，条件维度按意图追加\n"
    "- source_obligations: 每项含 obligation_id/source_family/required_for/"
    "min_required_evidence（必须是 1-5 的整数，默认 1）；"
    "默认保留 official_policy 基线义务\n"
    "- query_requirements: 含 needs_company_disclosure(bool)/target_location(str|null)/"
    "is_location_sensitive(bool)\n"
    "- dimension_type 用产业调研维度: 基础维度(默认进入) industry_scope/"
    "policy_regulation/market_scale/industry_chain/supply_competition/"
    "demand_scenarios/technology_product/project_execution/business_economics/"
    "risk_constraints；条件维度(按意图启用) company_fundamentals(涉年报/披露/"
    "上市公司/重点企业)/capital_activity(涉融资/投资/并购/基金)/"
    "regional_benchmark(地方产业调研默认启用)/outlook_drivers(涉前景/趋势/预测)\n"
    "- source_families 用来源族: policy_document/local_official/official_statistics/"
    "tender_procurement/exchange_disclosure/company_disclosure/company_material/"
    "certification_database/standard_document/patent_database/association_thinktank/"
    "broker_research/industry_research/commercial_media/operator_data\n\n"
    "关键：\n"
    "- 包含\"年报/披露/上市公司\"→ 企业披露 required，needs_company_disclosure=true\n"
    "- 包含\"政策/方案/规划/通知/措施\"→ 政策 required\n"
    "- 包含\"项目/公示/招标/中标/采购\"→ 项目 required\n"
    "- 包含\"数据/统计/规模/产量\"→ 数据 required\n"
    "- 仅当查询明确要求特定城市/地区证据时，才设置 target_location 与 "
    "is_location_sensitive=true\n"
    "- 避免在 coverage_required/research_question 中使用模糊量词（some/several/a few）\n"
    "- status 必须是 required/optional/deferred/skip 之一\n"
    "- priority 必须是 high/medium/low 之一\n"
    "- noise_risk 必须是 low/medium/high 之一\n\n"
    "Replan 上下文（如提供则用于强化下一轮结构，否则忽略）:\n"
    "{replan_request_json}\n\n"
    "Summary 记忆（仅用于反复出现的主题/证据缺口/偏好，不作为事实证据）:\n"
    "{summary_memory_json}"
)

SEARCH_BUILDER_SYSTEM = (
    "你是一个搜索词构建专家。根据原始查询和意图识别结果，构建高质量的搜索词。\n\n"
    "核心规则：\n"
    "1. 保留 2 条 anchor 搜索词（原始 query + normalized query）\n"
    "2. 每个 required evidence_need 构建一个独立搜索组\n"
    "3. 每个搜索组只有一个主检索意图\n"
    "4. 搜索词不能是原 query 加单个后缀（如\"+政策\"、\"+通知\"）\n"
    "5. 搜索词应短、明确、可执行（3-8 个语义单元）\n"
    "6. optional evidence_need 在预算允许时构建搜索组\n"
    "7. deferred 不执行，写入 deferred_search_ideas\n\n"
    "8. Phase A3: 每个搜索组必须绑定 required_source_family 和 include_domains\n"
    "9. Phase 1.5: 每个搜索组必须生成 4-5 条短语，针对其维度在 intent_plan.dimension_plan "
    "中的 search_key_fields（该维度的中文关键字段清单，若无则用 key_fields）逐条构造检索词——"
    "把字段转成具体检索表述（如产业链的\"产业链环节\"→上游/中游/下游、\"代表企业\"→龙头企业/企业名单、"
    "\"客户或供应商\"→供应商/客户、\"产能或供给能力\"→产能/产量、\"收入来源\"→收入/营收、"
    "\"价值量\"→附加值/利润；市场规模的\"指标数值\"→亿元/万元、\"同比或复合增速\"→增长率/同比；"
    "政策的\"政策工具\"→补贴/基金/示范区/采购等）。每个搜索组尽量覆盖该维度多个核心字段"
    "（如产业链需同时覆盖 环节/代表企业/上下游/地域/产能/价值量），"
    "严禁只搜维度名（如只搜\"市场规模\"而不搜\"产值/增长率\"），严禁少于 4 条。\n"
    "10. Phase 1.5b: 必须为 intent_plan.dimension_plan 中的**每个维度**各生成一个 "
    "search_group，group 数量必须 ≥ dimension_plan 维度数量；每个 group 的 "
    "target_evidence_need 精确指向对应维度（用 dimension_id），不要遗漏任何维度。\n\n"
    "维度 → 源族 → 域名约束映射表：\n"
    "- 政策监管(policy_regulation) → policy_document → gov.cn\n"
    "- 市场规模(market_scale) → official_statistics → stats.gov.cn\n"
    "- 项目执行(project_execution) → tender_procurement → ggzy.gov.cn, ccgp.gov.cn\n"
    "- 产业链(industry_chain) → industry_research → (无限制)\n"
    "- 企业经营财务(company_fundamentals) → exchange_disclosure → cninfo.com.cn\n"
    "- 供需竞争(supply_competition) → exchange_disclosure → cninfo.com.cn\n"
    "- 需求场景(demand_scenarios) → operator_data → (无限制)\n"
    "- 技术产品(technology_product) → certification_database → (无限制)\n"
    "- 风险瓶颈(risk_constraints) → industry_research → (无限制)\n\n"
    "政策类 search_phrase 模板: {地点} {主题} {文种} [{年份}]\n"
    "项目类 search_phrase 模板: {地点} {主题} {项目动作}\n"
    "披露类 search_phrase 模板: {平台/渠道} {主题} {披露文种} [{地点}]\n\n"
    "输出严格 JSON。"
)

SEARCH_BUILDER_USER_TEMPLATE = (
    "原始查询: {original_query}\n\n"
    "意图识别结果:\n{intent_plan_json}\n\n"
    "返回 JSON，包含: search_strategy_summary, anchor_phrases, search_groups, "
    "deferred_search_ideas, quality_checks\n\n"
    "anchor_phrases 必须包含至少 2 条:\n"
    "- 1 条 original_query anchor（保留用户原始表达）\n"
    "- 1 条 normalized_query anchor（保留核心主题+地点+证据要求）\n\n"
    "每个 search_group 包含:\n"
    "- group_id (G1/G2/...), group_name, dominant_intent, target_evidence_need\n"
    "  (target_evidence_need 建议用 intent_plan.dimension_plan 里的 dimension_id，"
    "如 \"dim_policy\"/\"dim_chain\"，便于精确对齐维度)\n"
    "- priority, target_level, source_type_preference\n"
    "- search_phrases: 每条含 phrase/ phrase_type/ intent/ reason\n"
    "- Phase A3 新增:\n"
    "  - required_source_family: 见维度映射表（如 policy_document）\n"
    "  - include_domains: 见维度映射表（如 [\"gov.cn\"]，无约束时为空数组）\n\n"
    "关键字段驱动: 意图识别结果里每个 dimension_plan 条目带有 **search_key_fields**"
    "（该维度的中文关键字段清单，若无则用 key_fields）。每个 search_group 必须生成 **4-5 条短语**，"
    "按它对应维度的 search_key_fields 逐条构造检索词，把字段转成具体检索表述"
    "（如产业链的\"代表企业\"→龙头企业/企业名单、\"上下游关系\"→供应商/客户、\"产能或供给能力\"→产能/产量、"
    "\"价值量\"→附加值/利润；市场规模的\"指标数值\"→亿元/万元、\"同比或复合增速\"→增长率/同比），"
    "尽量覆盖该维度多个核心字段（如产业链覆盖 环节/代表企业/上下游/地域/产能/价值量），"
    "严禁只搜维度名，严禁少于 4 条。\n\n"
    "phrase_type 用: level_action/ evidence_specific/ caliber_expansion/ "
    "source_channel/ platform_specific\n\n"
    "关键限制:\n"
    "- 不要生成原 query + 政策/通知/公告/项目/实施方案/年报/披露/官方来源\n"
    "- 每个 search_group 的短语都围绕同一个 dominant_intent\n"
    "- 每个 search_group 必须填写 required_source_family 和 include_domains\n"
    "- **必须为 intent_plan.dimension_plan 中的每个维度各建一个 search_group，"
    "组数 ≥ 维度数，不得遗漏任何维度**\n"
    "- deferred_search_ideas 只写 name/defer_reason/possible_future_phrases\n"
    "- quality_checks 必须填写"
)


# ── Deterministic Guard ────────────────────────────────────────────────────

_RAW_QUERY_SUFFIX_PATTERNS = frozenset({
    "政策", "通知", "公告", "项目", "实施方案", "年报", "披露", "官方来源",
    "方案", "规划", "措施", "办法", "行动计划", "意见", "报告", "数据",
})

_DETERMINISTIC_KEYWORDS: dict[str, list[str]] = {
    "企业披露": ["年报", "披露", "上市公司", "公告", "巨潮资讯", "交易所", "定期报告"],
    "地方政策": ["政策", "方案", "规划", "通知", "措施", "行动计划", "意见", "办法"],
    "项目公示": ["项目", "公示", "招标", "中标", "采购", "公共资源交易"],
    "行业数据": ["数据", "统计", "规模", "产量", "销量", "运行情况"],
}

# Deterministic fallback: evidence-need name -> research structure template.
# Used by _build_fallback_intent_plan to emit research_dimensions / dimension_plan
# / source_obligations when the LLM intent planner is unavailable.
_DIMENSION_TEMPLATES: dict[str, dict[str, Any]] = {
    "地方政策": {
        "dimension_id": "d_policy", "dimension_type": "policy_regulation",
        "source_family": "policy_document", "label": "政策与监管维度",
        "expected_section_heading": "政策与监管", "source_priority": "government",
        "obligation_id": "obl_policy_primary",
        "why_it_matters": "官方政策是报告审计可溯源的基线依据",
        "coverage_required": "收集至少 1 条官方政策原文或权威解读",
    },
    "企业披露": {
        "dimension_id": "d_company_fundamentals",
        "dimension_type": "company_fundamentals",
        "source_family": "exchange_disclosure", "label": "企业经营与财务维度",
        "expected_section_heading": "企业经营与财务", "source_priority": "enterprise",
        "obligation_id": "obl_exchange_disclosure",
        "why_it_matters": "年报与交易所披露验证企业侧表述与数据",
        "coverage_required": "收集至少 1 条年报/公告/交易所披露证据",
    },
    "项目公示": {
        "dimension_id": "d_execution", "dimension_type": "project_execution",
        "source_family": "tender_procurement", "label": "项目执行维度",
        "expected_section_heading": "项目落地与执行状态", "source_priority": "mixed",
        "obligation_id": "obl_execution_award",
        "why_it_matters": "项目公示/中标证明从规划到落地的执行进展",
        "coverage_required": "收集至少 1 条招标/中标/公共资源交易证据",
    },
    "行业数据": {
        "dimension_id": "d_market_scale", "dimension_type": "market_scale",
        "source_family": "official_statistics", "label": "市场规模与增长维度",
        "expected_section_heading": "市场规模与增长", "source_priority": "government",
        "obligation_id": "obl_statistics_data",
        "why_it_matters": "统计公报与行业数据量化产业规模与趋势",
        "coverage_required": "收集至少 1 条官方统计/行业数据证据",
    },
    "综合政策": {
        "dimension_id": "d_policy", "dimension_type": "policy_regulation",
        "source_family": "policy_document", "label": "政策与监管维度",
        "expected_section_heading": "政策与监管", "source_priority": "government",
        "obligation_id": "obl_policy_primary",
        "why_it_matters": "官方政策是报告审计可溯源的基线依据",
        "coverage_required": "收集至少 1 条官方政策原文或权威解读",
    },
}


def _caliber_guard(
    search_plan: dict[str, Any],
    query: str,
    normalized_query: str,
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, Any]]:
    """Deterministic guard: filter, validate, return final_search_plan + review."""

    filtered_out: list[dict[str, str]] = []
    review: dict[str, Any] = {
        "guard_version": "v0.1",
        "suffix_filtered": 0,
        "overlap_filtered": 0,
        "dedup_removed": 0,
        "anchor_coverage_ok": False,
        "group_intent_ok": True,
        "warnings": [],
    }

    # --- 11.3 Shallow suffix filter ---
    _filter_suffix_variants(search_plan, query, review, filtered_out)

    # --- 11.4 Long overlap filter ---
    _filter_long_overlaps(search_plan, query, review, filtered_out)

    # --- Dedup ---
    _dedup_phrases(search_plan, review, filtered_out)

    # --- 11.2 Anchor coverage ---
    _check_anchor_coverage(search_plan, query, normalized_query, review)

    # --- 11.6 Group intent validator ---
    _validate_group_intents(search_plan, review)

    # --- Recompute counts ---
    _recompute_summary(search_plan)

    # --- Update quality_checks ---
    qc = search_plan.get("quality_checks", {})
    if isinstance(qc, dict):
        qc["avoids_suffix_only_variants"] = review["suffix_filtered"] == 0
        qc["has_original_query_anchor"] = review["anchor_coverage_ok"]

    return search_plan, filtered_out, review


def _is_suffix_only(phrase: str, query: str) -> bool:
    """Check if phrase is original_query + a single suffix token.

    Only triggers when phrase starts with the full query AND the remainder
    is a known shallow suffix (政策, 通知, 公告, etc.).
    """
    pq = phrase.strip()
    qq = query.strip()
    if not pq.startswith(qq):
        return False
    remainder = pq[len(qq):].strip()
    if not remainder:
        return True  # exact duplicate
    return remainder in _RAW_QUERY_SUFFIX_PATTERNS


def _filter_suffix_variants(
    plan: dict[str, Any],
    query: str,
    review: dict[str, Any],
    filtered_out: list[dict[str, str]],
) -> None:
    groups = list(plan.get("search_groups", []))
    for group in groups:
        if not isinstance(group, dict):
            continue
        phrases = list(group.get("search_phrases", []))
        kept = []
        for ph in phrases:
            if isinstance(ph, dict) and _is_suffix_only(str(ph.get("phrase", "")), query):
                review["suffix_filtered"] += 1
                filtered_out.append({
                    "phrase": str(ph.get("phrase", "")),
                    "reason": "suffix_only_variant",
                    "group": str(group.get("group_id", "?")),
                })
            else:
                kept.append(ph)
        group["search_phrases"] = kept
    plan["search_groups"] = [g for g in groups if len(list(g.get("search_phrases", []))) > 0]


def _filter_long_overlaps(
    plan: dict[str, Any],
    query: str,
    review: dict[str, Any],
    filtered_out: list[dict[str, str]],
    max_overlap_chars: int = 14,
) -> None:
    groups = list(plan.get("search_groups", []))
    for group in groups:
        if not isinstance(group, dict):
            continue
        phrases = list(group.get("search_phrases", []))
        kept = []
        for ph in phrases:
            if not isinstance(ph, dict):
                kept.append(ph)
                continue
            p_str = str(ph.get("phrase", ""))
            is_anchor = str(ph.get("phrase_type", "")).startswith("anchor")
            if is_anchor:
                kept.append(ph)
                continue
            if _longest_common_substring_len(p_str, query) > max_overlap_chars:
                review["overlap_filtered"] += 1
                filtered_out.append({
                    "phrase": p_str,
                    "reason": "long_overlap",
                    "group": str(group.get("group_id", "?")),
                })
            else:
                kept.append(ph)
        group["search_phrases"] = kept
    plan["search_groups"] = [g for g in groups if len(list(g.get("search_phrases", []))) > 0]


def _longest_common_substring_len(a: str, b: str) -> int:
    """Simple LCS length for Chinese text overlap detection."""
    a_chars = list(a.replace(" ", ""))
    b_chars = list(b.replace(" ", ""))
    if not a_chars or not b_chars:
        return 0
    m, n = len(a_chars), len(b_chars)
    curr = [0] * (n + 1)
    best = 0
    for i in range(m):
        prev = curr[:]
        for j in range(n):
            if a_chars[i] == b_chars[j]:
                curr[j + 1] = prev[j] + 1
                best = max(best, curr[j + 1])
            else:
                curr[j + 1] = 0
    return best


def _dedup_phrases(
    plan: dict[str, Any],
    review: dict[str, Any],
    filtered_out: list[dict[str, str]],
) -> None:
    seen: set[str] = set()
    groups = list(plan.get("search_groups", []))
    for group in groups:
        if not isinstance(group, dict):
            continue
        phrases = list(group.get("search_phrases", []))
        kept = []
        for ph in phrases:
            if not isinstance(ph, dict):
                kept.append(ph)
                continue
            p_str = str(ph.get("phrase", "")).strip().lower()
            if p_str and p_str not in seen:
                seen.add(p_str)
                kept.append(ph)
            elif p_str:
                review["dedup_removed"] += 1
                filtered_out.append({
                    "phrase": str(ph.get("phrase", "")),
                    "reason": "duplicate",
                    "group": str(group.get("group_id", "?")),
                })
        group["search_phrases"] = kept


def _check_anchor_coverage(
    plan: dict[str, Any],
    query: str,
    normalized_query: str,
    review: dict[str, Any],
) -> None:
    anchor_phrases = list(plan.get("anchor_phrases", []))
    total = _count_all_phrases(plan)
    anchor_count = len(anchor_phrases)

    # PRD 11.2: at least 2, ratio <= 30%
    if anchor_count < 2:
        if anchor_count == 0:
            # Auto-inject missing anchors
            plan.setdefault("anchor_phrases", [])
            if isinstance(plan["anchor_phrases"], list):
                plan["anchor_phrases"].insert(0, {
                    "phrase": query,
                    "anchor_type": "original_query",
                    "reason": "自动注入: 保留用户原始表达",
                })
                anchor_count += 1
        if anchor_count < 2 and normalized_query and normalized_query != query:
            if isinstance(plan.get("anchor_phrases"), list):
                plan["anchor_phrases"].append({
                    "phrase": normalized_query,
                    "anchor_type": "normalized_query",
                    "reason": "自动注入: 保留核心主题+地点+证据要求",
                })
                anchor_count += 1

    review["anchor_phrase_count"] = anchor_count
    review["total_phrases"] = total
    if total > 0:
        ratio = anchor_count / max(total, 1)
        review["anchor_ratio"] = round(ratio, 3)
        review["anchor_coverage_ok"] = ratio <= 0.30 and anchor_count >= 1
        if ratio > 0.30:
            review["warnings"].append(f"anchor比例{ratio:.0%}超过30%上限")
    else:
        # Only anchors exist — that's fine for empty plans
        review["anchor_coverage_ok"] = anchor_count >= 1 if total == 0 else False


def _validate_group_intents(
    plan: dict[str, Any],
    review: dict[str, Any],
) -> None:
    """Check each search group has a single dominant intent.

    Only flags when ≥3 DIFFERENT evidence-type keywords appear together,
    indicating the group mixes unrelated retrieval intents (e.g. policy +
    project + disclosure in one phrase). Domain-specific co-occurrences
    like 年报+披露+上市公司 in a disclosure group are not flagged.
    """
    # Evidence type families — keywords within the same family are natural co-occurrence
    _disclosure_family = {"年报", "披露", "上市公司", "公告", "年度报告", "定期报告", "投资者关系"}
    _project_family = {"项目", "公示", "招标", "中标", "采购", "公共资源交易"}
    _policy_family = {"政策", "方案", "规划", "通知", "措施", "行动计划", "意见", "办法"}

    groups = list(plan.get("search_groups", []))
    for group in groups:
        if not isinstance(group, dict):
            continue
        # Collect all keywords from phrases in this group
        all_kw = set()
        for ph in group.get("search_phrases", []):
            if not isinstance(ph, dict):
                continue
            phrase = str(ph.get("phrase", ""))
            intent = str(ph.get("intent", ""))
            combined = phrase + intent
            for kw in _disclosure_family | _project_family | _policy_family:
                if kw in combined:
                    all_kw.add(kw)

        # Count how many different families are hit
        families_hit = 0
        if all_kw & _disclosure_family:
            families_hit += 1
        if all_kw & _project_family:
            families_hit += 1
        if all_kw & _policy_family:
            families_hit += 1

        if families_hit >= 3:
            review["group_intent_ok"] = False
            review["warnings"].append(
                f"组{group.get('group_id','?')}中搜索词跨3个证据类型族"
                f"(政策/项目/披露)，检索意图不清晰"
            )
        elif families_hit == 2 and all_kw & _disclosure_family and all_kw & _project_family:
            # Mixed disclosure + project in one group is suspicious
            review["group_intent_ok"] = False
            review["warnings"].append(
                f"组{group.get('group_id','?')}中搜索词混合企业披露和项目执行两类不同意图"
            )


def _count_all_phrases(plan: dict[str, Any]) -> int:
    count = len(list(plan.get("anchor_phrases", [])))
    for g in plan.get("search_groups", []):
        if isinstance(g, dict):
            count += len(list(g.get("search_phrases", [])))
    return count


def _recompute_summary(plan: dict[str, Any]) -> None:
    summary = plan.get("search_strategy_summary", {})
    if not isinstance(summary, dict):
        return
    anchor_count = len(list(plan.get("anchor_phrases", [])))
    non_anchor = _count_all_phrases(plan) - anchor_count
    group_count = len(list(plan.get("search_groups", [])))
    summary["anchor_phrase_count"] = anchor_count
    summary["non_anchor_phrase_count"] = non_anchor
    summary["total_phrases"] = anchor_count + non_anchor
    summary["total_rounds"] = max(1, group_count)


# ── Fallback Logic ────────────────────────────────────────────────────────


def _build_fallback_intent_plan(query: str) -> dict[str, Any]:
    """PRD 15.1: deterministic keyword-trigger fallback for Layer 1."""
    evidence_needs = []
    for name, keywords in _DETERMINISTIC_KEYWORDS.items():
        if any(kw in query for kw in keywords):
            evidence_needs.append({
                "name": name,
                "status": "required",
                "priority": "high",
                "why_needed": f"query包含{name}相关关键词",
                "what_to_verify": f"验证{name}相关证据",
                "suggested_caliber_terms": [],
                "source_type_preference": [],
                "noise_risk": "medium",
            })

    # If nothing detected, add a generic policy need
    if not evidence_needs:
        evidence_needs.append({
            "name": "综合政策",
            "status": "required",
            "priority": "medium",
            "why_needed": "默认搜索: query未明确指定证据类型",
            "what_to_verify": "检索相关政策、项目和企业信息",
            "suggested_caliber_terms": ["政策", "项目", "数据"],
            "source_type_preference": ["政府网站", "交易所"],
            "noise_risk": "high",
        })

    # ── Structure: derive research_dimensions / dimension_plan / source_obligations
    #    from the triggered evidence needs (deterministic fallback). ──
    dimensions: list[dict[str, Any]] = []
    dimension_plan: list[dict[str, Any]] = []
    obligations: list[dict[str, Any]] = []
    seen_dim: set[str] = set()
    for en in evidence_needs:
        name = str(en.get("name", ""))
        tpl = _DIMENSION_TEMPLATES.get(name)
        if tpl is None or tpl["dimension_id"] in seen_dim:
            continue
        seen_dim.add(tpl["dimension_id"])
        dim_id = tpl["dimension_id"]
        dimensions.append({
            "dimension_id": dim_id,
            "label": tpl["label"],
            "description": f"围绕{name}检索并核验证据",
            "caliber_terms": [query, f"{query} {name}"],
            "source_priority": tpl["source_priority"],
        })
        dimension_plan.append({
            "dimension_id": dim_id,
            "dimension_type": tpl["dimension_type"],
            "research_question": f"{query} 的{name}证据是什么？",
            "why_it_matters": tpl["why_it_matters"],
            "coverage_required": tpl["coverage_required"],
            "expected_section_heading": tpl["expected_section_heading"],
            "source_priority": tpl["source_priority"],
            "source_families": [tpl["source_family"]],
            "caliber_terms": [query, f"{query} {name}"],
        })
        obligations.append({
            "obligation_id": tpl["obligation_id"],
            "source_family": tpl["source_family"],
            "required_for": f"{name}证据",
            "min_required_evidence": 1,
        })

    # Guarantee >= 2 dimensions and a policy baseline (runner/editor invariants).
    if "d_policy" not in seen_dim:
        policy_tpl = _DIMENSION_TEMPLATES["综合政策"]
        seen_dim.add("d_policy")
        dimensions.append({
            "dimension_id": "d_policy", "label": policy_tpl["label"],
            "description": "围绕综合政策检索并核验证据",
            "caliber_terms": [query, f"{query} 政策"],
            "source_priority": policy_tpl["source_priority"],
        })
        dimension_plan.append({
            "dimension_id": "d_policy", "dimension_type": "policy_regulation",
            "research_question": f"{query} 的政策依据是什么？",
            "why_it_matters": policy_tpl["why_it_matters"],
            "coverage_required": policy_tpl["coverage_required"],
            "expected_section_heading": policy_tpl["expected_section_heading"],
            "source_priority": policy_tpl["source_priority"],
            "source_families": ["policy_document"],
            "caliber_terms": [query, f"{query} 政策"],
        })
        obligations.append({
            "obligation_id": "obl_policy_primary", "source_family": "policy_document",
            "required_for": "综合政策证据", "min_required_evidence": 1,
        })
    if len(dimension_plan) < 2 and "d_market_scale" not in seen_dim:
        stats_tpl = _DIMENSION_TEMPLATES["行业数据"]
        seen_dim.add("d_market_scale")
        dimensions.append({
            "dimension_id": "d_market_scale", "label": stats_tpl["label"],
            "description": "围绕行业数据检索并核验证据",
            "caliber_terms": [query, f"{query} 数据"],
            "source_priority": stats_tpl["source_priority"],
        })
        dimension_plan.append({
            "dimension_id": "d_market_scale", "dimension_type": "market_scale",
            "research_question": f"{query} 的行业统计数据是什么？",
            "why_it_matters": stats_tpl["why_it_matters"],
            "coverage_required": stats_tpl["coverage_required"],
            "expected_section_heading": stats_tpl["expected_section_heading"],
            "source_priority": stats_tpl["source_priority"],
            "source_families": ["official_statistics"],
            "caliber_terms": [query, f"{query} 数据"],
        })
        obligations.append({
            "obligation_id": "obl_statistics_data",
            "source_family": "official_statistics",
            "required_for": "行业数据证据", "min_required_evidence": 1,
        })

    locations = _extract_locations_from_query(query)
    query_requirements = {
        "needs_company_disclosure": any(
            kw in query for kw in ("年报", "披露", "上市公司", "公告", "交易所", "定期报告")
        ),
        "target_location": locations[0] if locations else None,
        "is_location_sensitive": bool(locations),
    }

    return {
        "normalized_query": query.strip(),
        "user_goal": {
            "goal_type": "evidence_verification",
            "goal_description": f"核查{query[:40]}的相关证据",
            "is_evidence_verification": True,
            "is_location_sensitive": bool(
                re.search(r"[\u4e00-\u9fff]{2}(?:市|省|区|县|街道|镇)", query)
            ),
            "is_time_sensitive": bool(re.search(r"20\d{2}", query)),
        },
        "explicit_constraints": {
            "time": re.findall(r"(20[2-9]\d)", query),
            "locations": _extract_locations_from_query(query),
            "companies": [],
            "industries_or_topics": _extract_topics_from_query(query),
            "required_source_style": [],
        },
        "query_levels": [],
        "evidence_needs": evidence_needs,
        "expansion_policy": {
            "should_expand_topic_terms": True,
            "should_expand_location_levels": False,
            "should_expand_company_terms": False,
            "should_expand_project_terms": True,
            "expansion_limits": "规则兜底: 仅基于关键词触发",
        },
        "search_budget_advice": {
            "recommended_rounds": min(3, max(1, len(evidence_needs))),
            "recommended_phrases_per_round": 4,
            "must_cover_original_query": True,
            "original_query_anchor_ratio": "20%-30%",
        },
        "caliber_notes": [
            "fallback_used: 规则触发, 非LLM生成",
            "fallback_structure: 维度/义务/查询要求由规则生成",
            "建议人工审阅证据面向是否完整",
        ],
        "research_dimensions": dimensions,
        "dimension_plan": dimension_plan,
        "source_obligations": obligations,
        "query_requirements": query_requirements,
    }


def _build_fallback_search_plan(
    query: str, intent_plan: dict[str, Any]
) -> dict[str, Any]:
    """PRD 15.2: template-based fallback for Layer 2."""
    normalized = str(intent_plan.get("normalized_query", query))
    evidence_needs = list(intent_plan.get("evidence_needs", []))

    # Anchor phrases
    anchor_phrases = [
        {"phrase": query, "anchor_type": "original_query", "reason": "兜底: 保留原始查询"},
    ]
    if normalized and normalized != query:
        anchor_phrases.append({
            "phrase": normalized, "anchor_type": "normalized_query",
            "reason": "兜底: 保留标准化查询",
        })

    # Build search groups from required evidence_needs via templates
    # Phase A3: each template group maps to source_family + domains
    templates: dict[str, dict[str, Any]] = {
        "地方政策": {
            "phrases": [
                "{地点} {主题} 工作方案 {年份}",
                "{地点} {主题} 实施方案",
                "{地点} {主题} 政策措施",
                "{地点} {主题} 行动计划",
            ],
            "required_source_family": "policy_document",
            "include_domains": ["gov.cn"],
        },
        "项目公示": {
            "phrases": [
                "{地点} {主题} 项目公示",
                "{地点} {主题} 公共资源交易",
                "{地点} {主题} 招标 中标",
                "{地点} {主题} 政府采购",
            ],
            "required_source_family": "tender_procurement",
            "include_domains": ["ggzy.gov.cn", "ccgp.gov.cn"],
        },
        "企业披露": {
            "phrases": [
                "巨潮资讯 {主题} 年度报告 {地点}",
                "cninfo {主题} 年报 {地点}",
                "{地点} {主题} 上市公司 年报",
                "上交所 {主题} 年度报告 {地点}",
            ],
            "required_source_family": "exchange_disclosure",
            "include_domains": ["cninfo.com.cn"],
        },
        "行业数据": {
            "phrases": [
                "{地点} {主题} 统计数据",
                "{地点} {主题} 产业规模",
                "{地点} {主题} 发展报告",
                "{地点} {主题} 运行情况",
            ],
            "required_source_family": "official_statistics",
            "include_domains": ["stats.gov.cn"],
        },
    }

    search_groups = []
    for i, en in enumerate([e for e in evidence_needs
                             if isinstance(e, dict)
                             and str(e.get("status", "")) == "required"], start=1):
        name = str(en.get("name", ""))
        tpl = templates.get(name, {
            "phrases": ["{地点} {主题} 政策 {年份}"],
            "required_source_family": "policy_document",
            "include_domains": [],
        })
        # Extract topic term from intent_plan, fall back to first 6 chars of query
        topic = _extract_topic_from_intent(intent_plan, query)
        phrases = []
        for tpl_text in tpl["phrases"]:
            phrase = (
                tpl_text.replace("{地点}", "")
                .replace("{主题}", topic)
                .replace("{年份}", "2025")
                .strip()
            )
            phrases.append({
                "phrase": phrase,
                "phrase_type": "template_fallback",
                "intent": f"兜底: {str(en.get('what_to_verify', ''))}",
                "reason": f"规则模板生成: {name}",
            })
        search_groups.append({
            "group_id": f"G{i}",
            "group_name": f"{name}搜索组",
            "dominant_intent": f"兜底: 检索{name}",
            "target_evidence_need": name,
            "priority": str(en.get("priority", "medium")),
            "target_level": "",
            "source_type_preference": list(en.get("source_type_preference", [])),
            "required_source_family": tpl["required_source_family"],
            "include_domains": tpl["include_domains"],
            "search_phrases": phrases,
        })

    return {
        "search_strategy_summary": {
            "original_query": query,
            "normalized_query": normalized,
            "total_rounds": max(1, len(search_groups)),
            "total_phrases": len(anchor_phrases) + sum(
                len(list(g.get("search_phrases", []))) for g in search_groups
            ),
            "anchor_phrase_count": len(anchor_phrases),
            "non_anchor_phrase_count": sum(
                len(list(g.get("search_phrases", []))) for g in search_groups
            ),
        },
        "anchor_phrases": anchor_phrases,
        "search_groups": search_groups,
        "deferred_search_ideas": [],
        "quality_checks": {
            "has_original_query_anchor": True,
            "has_normalized_query_anchor": len(anchor_phrases) >= 2,
            "avoids_suffix_only_variants": True,
            "each_group_has_single_dominant_intent": True,
            "does_not_expand_all_possible_directions": True,
        },
    }


# ── Main Entry Point ───────────────────────────────────────────────────────


def expand_caliber(
    *,
    query: str,
    client: JsonProviderClient | None = None,
    replan_request: dict[str, Any] | None = None,
    summary_memory: dict[str, Any] | None = None,
) -> CaliberExpansionResult:
    """PRD section 8: two-layer LLM + deterministic guard.

    Returns CaliberExpansionResult with intent_plan, search_plan, final_search_plan,
    and guard review metadata. Since the research-planning refactor, the intent
    planner (layer 1) is also the producer of the research structure
    (research_dimensions / dimension_plan / source_obligations / query_requirements),
    so the downstream build_semantic_plan no longer needs a separate big call.
    """
    settings = get_settings()
    fallback_used = False
    metadata: dict[str, Any] = {}

    # ── Try to get a client ──
    if client is None:
        if not settings.deepseek_api_key:
            return _full_fallback_result(query, metadata, "no_api_key")
        try:
            # The intent planner (layer 1) now also emits the research structure
            # (research_dimensions / dimension_plan / source_obligations /
            # query_requirements), so it needs a generous output budget. A higher
            # max_tokens is only a safety ceiling — cost is incurred only for what
            # the model actually emits, and the search builder (layer 2) typically
            # stops well below it. The low global deepseek_max_tokens (1200) was
            # tuned for the old single-call planner and truncates the new
            # structure-bearing intent output (ProviderParseError -> silent
            # deterministic fallback).
            client = DeepSeekProviderClient(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                model=settings.deepseek_research_model,
                timeout_seconds=min(settings.deepseek_timeout_seconds, 60),
                max_retries=1,
                max_tokens=min(max(settings.deepseek_max_tokens, 5000), 8000),
                store_reasoning_content=False,
            )
        except ProviderConfigError:
            return _full_fallback_result(query, metadata, "provider_config_error")

    # ── Layer 1: Intent Planner ──
    intent_plan = _run_intent_planner(
        query, client, metadata, settings,
        replan_request=replan_request, summary_memory=summary_memory,
    )
    if intent_plan is None:
        fallback_used = True
        intent_plan = _build_fallback_intent_plan(query)
        metadata["layer1_mode"] = "deterministic_fallback"
    else:
        metadata["layer1_mode"] = "llm"

    normalized_query = str(intent_plan.get("normalized_query", query))

    # ── Layer 2: Search Phrase Builder ──
    search_plan = _run_search_builder(query, intent_plan, client, metadata, settings)
    if search_plan is None:
        fallback_used = True
        search_plan = _build_fallback_search_plan(query, intent_plan)
        metadata["layer2_mode"] = "deterministic_fallback"
    else:
        metadata["layer2_mode"] = "llm"

    # ── Post-process: align deferred items and anchor fields ──
    _align_deferred_fields(search_plan)
    _align_anchor_fields(search_plan)

    # ── Guard ──
    final_plan, filtered_out, guard_review = _caliber_guard(
        dict(search_plan), query, normalized_query,
    )

    return CaliberExpansionResult(
        query=query,
        normalized_query=normalized_query,
        intent_plan=dict(intent_plan),
        search_plan=dict(search_plan),
        final_search_plan=final_plan,
        filtered_out=filtered_out,
        guard_review=guard_review,
        fallback_used=fallback_used,
        metadata=metadata,
    )


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if value is None or str(value).strip() in ("", "未指定", "unspecified"):
        return []
    return [str(value).strip()]


def _source_priority_label(families: Any) -> str:
    """Derive a short source_priority label from a source-family list. The LLM
    sometimes fills source_priority with the source-family list; map it back to
    a short taxonomy-grade label."""
    fam = str(families[0]) if isinstance(families, list) and families else str(families or "")
    if fam in ("policy_document", "local_official", "official_statistics"):
        return "government"
    if fam in ("company_disclosure", "exchange_disclosure", "company_material", "operator_data"):
        return "enterprise"
    if fam in ("industry_research", "association_thinktank", "broker_research"):
        return "research"
    return "mixed"


def _normalize_intent_plan_structures(data: dict[str, Any]) -> dict[str, Any]:
    """Map the intent planner's free-form JSON onto the IntentPlan schema shapes.

    The LLM often emits convenient-but-mismatched shapes (user_goal as a string,
    explicit_constraints with location/industry keys, source_priority as a list,
    caliber_notes as a dict, ...). Normalizing keeps the rich structure AND makes
    IntentPlan validation pass, so build_semantic_plan no longer silently falls
    back to the deterministic plan on schema_validation_failed.
    """
    d = dict(data)
    query_text = str(d.get("normalized_query") or "")
    # user_goal: str -> dict; non-dict -> default
    ug = d.get("user_goal")
    if isinstance(ug, str):
        d["user_goal"] = {
            "goal_type": "evidence_verification",
            "goal_description": ug[:400],
            "is_evidence_verification": True,
            "is_location_sensitive": bool(_extract_locations_from_query(query_text)),
            "is_time_sensitive": bool(re.search(r"20\d{2}", query_text)),
        }
    elif not isinstance(ug, dict):
        d["user_goal"] = {
            "goal_type": "evidence_verification",
            "goal_description": f"核查{query_text[:40]}的相关证据",
            "is_evidence_verification": True,
            "is_location_sensitive": bool(_extract_locations_from_query(query_text)),
            "is_time_sensitive": bool(re.search(r"20\d{2}", query_text)),
        }
    # explicit_constraints: map LLM keys (location/industry/enterprise/source_type)
    # to schema keys (time/locations/companies/industries_or_topics/required_source_style).
    ec = d.get("explicit_constraints")
    if isinstance(ec, dict):
        loc = str(ec.get("location") or "").strip()
        ind = _as_list(ec.get("industry") or ec.get("industries_or_topics"))
        t = _as_list(ec.get("time"))
        d["explicit_constraints"] = {
            "time": t[:4],
            "locations": [loc] if loc else _as_list(ec.get("locations")),
            "companies": _as_list(ec.get("enterprise") or ec.get("companies")),
            "industries_or_topics": ind,
            "required_source_style": _as_list(
                ec.get("source_type") or ec.get("required_source_style")
            ),
        }
    elif not isinstance(ec, dict):
        d["explicit_constraints"] = {
            "time": [],
            "locations": _extract_locations_from_query(query_text),
            "companies": [],
            "industries_or_topics": _extract_topics_from_query(query_text),
            "required_source_style": [],
        }
    # query_levels: str item -> dict item; non-list -> default
    ql = d.get("query_levels")
    if isinstance(ql, list):
        d["query_levels"] = [
            {"level": str(item), "priority": "medium", "reason": ""}
            if isinstance(item, str)
            else item
            for item in ql
        ][:8]
    elif not isinstance(ql, list):
        d["query_levels"] = []
    # expansion_policy: map expand_* -> should_expand_*; non-dict -> default
    ep = d.get("expansion_policy")
    if isinstance(ep, dict):
        d["expansion_policy"] = {
            "should_expand_topic_terms": bool(
                ep.get("expand_topic") or ep.get("expand_industry")
                or ep.get("should_expand_topic_terms", True)
            ),
            "should_expand_location_levels": bool(
                ep.get("expand_location") or ep.get("should_expand_location_levels", False)
            ),
            "should_expand_company_terms": bool(
                ep.get("expand_company") or ep.get("should_expand_company_terms", False)
            ),
            "should_expand_project_terms": bool(
                ep.get("expand_project") or ep.get("should_expand_project_terms", True)
            ),
            "expansion_limits": str(
                ep.get("notes") or ep.get("expansion_limits") or ""
            )[:500],
        }
    elif not isinstance(ep, dict):
        d["expansion_policy"] = {
            "should_expand_topic_terms": True,
            "should_expand_location_levels": bool(_extract_locations_from_query(query_text)),
            "should_expand_company_terms": False,
            "should_expand_project_terms": True,
            "expansion_limits": "",
        }
    # search_budget_advice: map total_queries/distribution -> recommended_rounds/phrases;
    # non-dict -> default
    sb = d.get("search_budget_advice")
    if isinstance(sb, dict):
        dist = sb.get("distribution") or {}
        if isinstance(dist, dict) and dist:
            recommended_rounds = min(6, max(1, len(dist)))
        else:
            recommended_rounds = min(6, max(1, int(sb.get("recommended_rounds") or 3)))
        d["search_budget_advice"] = {
            "recommended_rounds": recommended_rounds,
            "recommended_phrases_per_round": min(
                8, max(1, int(sb.get("recommended_phrases_per_round") or 4))
            ),
            "must_cover_original_query": bool(
                sb.get("must_cover_original_query", True)
            ),
            "original_query_anchor_ratio": str(
                sb.get("original_query_anchor_ratio") or "20%-30%"
            )[:20],
        }
    elif not isinstance(sb, dict):
        d["search_budget_advice"] = {
            "recommended_rounds": 3,
            "recommended_phrases_per_round": 4,
            "must_cover_original_query": True,
            "original_query_anchor_ratio": "20%-30%",
        }
    # caliber_notes: dict -> list[str]; str -> [str]; non-list -> []
    cn = d.get("caliber_notes")
    if isinstance(cn, dict):
        d["caliber_notes"] = [
            f"{k}: {v}" for k, v in cn.items() if str(v).strip()
        ][:8]
    elif isinstance(cn, str):
        d["caliber_notes"] = [cn[:400]]
    elif not isinstance(cn, list):
        d["caliber_notes"] = []
    # evidence_needs: ensure each item is a dict with valid enum values
    en = d.get("evidence_needs")
    if isinstance(en, list):
        normalized_en: list[dict[str, Any]] = []
        for item in en:
            if isinstance(item, str):
                normalized_en.append({
                    "name": item[:80],
                    "status": "required",
                    "priority": "medium",
                    "why_needed": "",
                    "what_to_verify": "",
                    "suggested_caliber_terms": [],
                    "source_type_preference": [],
                    "noise_risk": "medium",
                })
            elif isinstance(item, dict):
                entry = dict(item)
                if entry.get("status") not in ("required", "optional", "deferred", "skip"):
                    entry["status"] = "required"
                if entry.get("priority") not in ("high", "medium", "low"):
                    entry["priority"] = "medium"
                if entry.get("noise_risk") not in ("low", "medium", "high"):
                    entry["noise_risk"] = "medium"
                normalized_en.append(entry)
        d["evidence_needs"] = normalized_en[:10]
    # source_priority: list -> short label (research_dimensions + dimension_plan)
    for key in ("research_dimensions", "dimension_plan"):
        items = d.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    sp = item.get("source_priority")
                    if isinstance(sp, list):
                        item["source_priority"] = _source_priority_label(sp)
    # Inject taxonomy key_fields (English, evidence validation) and
    # search_key_fields (Chinese, search-phrase construction) into dimension_plan
    # entries so the search builder can build field-targeted phrases.
    dp = d.get("dimension_plan")
    if isinstance(dp, list):
        for item in dp:
            if not isinstance(item, dict):
                continue
            dtype = research_taxonomy.canonicalize_dimension_type(
                str(item.get("dimension_type") or "")
            )
            meta = research_taxonomy.DIMENSIONS.get(dtype, {})
            if not (isinstance(item.get("key_fields"), list) and item["key_fields"]):
                kf = list(meta.get("key_fields", []))
                if kf:
                    item["key_fields"] = kf
            skf = list(meta.get("search_key_fields", []))
            if skf:
                item["search_key_fields"] = skf
    return d


def _run_intent_planner(
    query: str,
    client: JsonProviderClient,
    metadata: dict[str, Any],
    settings: Any,
    replan_request: dict[str, Any] | None = None,
    summary_memory: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Run Layer 1 LLM call. Returns None on failure.

    Layer 1 now also produces the research structure (research_dimensions /
    dimension_plan / source_obligations / query_requirements). If the LLM omits
    any of them, an always-on additive floor fills the gap from the deterministic
    fallback so the downstream plan never loses structure.
    """
    try:
        user_prompt = INTENT_PLANNER_USER_TEMPLATE.format(
            query=query,
            replan_request_json=json.dumps(
                replan_request or {}, ensure_ascii=False, indent=2
            ),
            summary_memory_json=json.dumps(
                summary_memory or {}, ensure_ascii=False, indent=2
            ),
        )
        response = client.generate_json(
            system_prompt=INTENT_PLANNER_SYSTEM,
            user_prompt=user_prompt,
            model=settings.deepseek_research_model,
            enable_thinking=False,
        )
        data = dict(response.json_data)
        if not data:
            return None
        # Normalize the free-form LLM output onto the schema shapes so the rich
        # structure survives IntentPlan validation and build_semantic_plan does
        # not fall back to the deterministic plan.
        data = _normalize_intent_plan_structures(data)
        # Validate via Pydantic
        try:
            IntentPlan(**data)
        except ValidationError:
            # Try repair: if evidence_needs missing, inject from fallback
            fallback = _build_fallback_intent_plan(query)
            if not data.get("evidence_needs"):
                data["evidence_needs"] = fallback.get("evidence_needs", [])
            if not data.get("user_goal"):
                data["user_goal"] = fallback["user_goal"]
        # Always-on additive floor for the research structure fields.
        fallback = _build_fallback_intent_plan(query)
        for key in ("research_dimensions", "dimension_plan", "source_obligations"):
            raw = data.get(key)
            if not (isinstance(raw, list) and raw):
                data[key] = list(fallback.get(key, []) or [])
        qr = data.get("query_requirements")
        if not (isinstance(qr, dict) and qr):
            data["query_requirements"] = dict(fallback.get("query_requirements", {}) or {})
        metadata["intent_model"] = response.model
        metadata["intent_provider"] = response.provider
        return data
    except Exception:
        return None


def _run_search_builder(
    query: str,
    intent_plan: dict[str, Any],
    client: JsonProviderClient,
    metadata: dict[str, Any],
    settings: Any,
) -> dict[str, Any] | None:
    """Run Layer 2 LLM call. Returns None on failure.

    Uses a higher temperature / top_p / presence_penalty than the default so the
    search phrases are more diverse and cover more of each dimension's key fields
    (empirically: temp=0.9, top_p=1.0, presence_penalty=0.8 yields +1 phrase per
    group vs the deterministic default, while keeping full source-family coverage).
    """
    try:
        response = client.generate_json(
            system_prompt=SEARCH_BUILDER_SYSTEM,
            user_prompt=SEARCH_BUILDER_USER_TEMPLATE.format(
                original_query=query,
                intent_plan_json=json.dumps(intent_plan, ensure_ascii=False, indent=2),
            ),
            model=settings.deepseek_research_model,
            enable_thinking=False,
            temperature=0.9,
            top_p=1.0,
            presence_penalty=0.8,
        )
        data = dict(response.json_data)
        if not data:
            return None
        # Truncation detection: LLM output must have search_groups or anchor_phrases
        if not data.get("search_groups") and not data.get("anchor_phrases"):
            return None
        try:
            SearchPlan(**data)
        except ValidationError:
            pass  # Best-effort; guard will fix structure
        metadata["search_model"] = response.model
        metadata["search_provider"] = response.provider
        return data
    except Exception:
        return None


def _align_deferred_fields(plan: dict[str, Any]) -> None:
    """Align deferred item field names to canonical form.

    Canonical keys: evidence_need, defer_reason, possible_future_phrases.
    """
    deferred = list(plan.get("deferred_search_ideas", []))
    if not deferred:
        return
    aligned = []
    for item in deferred:
        if not isinstance(item, dict):
            continue
        aligned.append({
            "evidence_need": str(
                item.get("evidence_need")
                or item.get("name")
                or item.get("target_evidence_need")
                or ""
            ),
            "defer_reason": str(
                item.get("defer_reason")
                or item.get("reason")
                or item.get("why_deferred")
                or ""
            ),
            "possible_future_phrases": list(
                item.get("possible_future_phrases")
                or item.get("search_phrases")
                or item.get("phrases")
                or []
            ),
        })
    plan["deferred_search_ideas"] = aligned


def _align_anchor_fields(plan: dict[str, Any]) -> None:
    """Ensure each anchor phrase has required fields: phrase/anchor_type/reason."""
    anchors = list(plan.get("anchor_phrases", []))
    aligned = []
    for i, a in enumerate(anchors):
        if not isinstance(a, dict):
            continue
        anchor_type = str(a.get("anchor_type") or a.get("phrase_type") or "")
        if not anchor_type:
            anchor_type = "original_query" if i == 0 else "normalized_query"
        aligned.append({
            "phrase": str(a.get("phrase", "")),
            "anchor_type": anchor_type,
            "reason": str(a.get("reason") or a.get("intent") or f"锚点{i+1}"),
        })
    plan["anchor_phrases"] = aligned


def _extract_locations_from_query(query: str) -> list[str]:
    """Extract Chinese location names from query."""
    pattern = r"([\u4e00-\u9fff]{2,4})(?:市|省|区|县|街道|镇|新区|开发区)"
    return [m[0] + m[1] for m in re.findall(pattern, query)[:4]]


def _extract_topics_from_query(query: str) -> list[str]:
    """Extract likely industry/topic keywords from query.

    Heuristic: identify 2-4 character noun phrases that are NOT locations, times,
    or evidence-type keywords. This is a best-effort short topic list for templates.
    """
    # Common evidence keywords to exclude
    evidence_kw = {
        "政策", "项目", "年报", "披露", "数据", "规划", "通知", "公告",
        "方案", "措施", "招标", "中标", "采购", "公示", "统计",
        "上市公司", "官方来源", "产能置换", "实施方案", "行动计划",
        "公共资源交易", "年度报告", "定期报告", "投资者关系",
    }
    # Remove locations, numbers, evidence keywords
    cleaned = query
    for loc in _extract_locations_from_query(query):
        cleaned = cleaned.replace(loc, " ")
    for ek in evidence_kw:
        cleaned = cleaned.replace(ek, " ")
    for num in re.findall(r"\d+年|\d+", cleaned):
        cleaned = cleaned.replace(num, " ")
    # Take remaining meaningful chunks
    chunks = [c.strip() for c in re.split(r"\s+", cleaned) if len(c.strip()) >= 2]
    return chunks[:4]


def _extract_topic_from_intent(intent_plan: dict[str, Any], query: str) -> str:
    """Extract a short topic keyword from intent_plan or query for template use."""
    # Try explicit_constraints first
    ec = intent_plan.get("explicit_constraints", {})
    if isinstance(ec, dict):
        industries = list(ec.get("industries_or_topics", []))
        if industries:
            return str(industries[0])[:12]
    # Try normalized_query
    nq = str(intent_plan.get("normalized_query", ""))
    if nq and len(nq) < 30:
        return nq[:12]
    # Fallback: first 6 chars of query (a short topic keyword)
    return query[:6]


def _full_fallback_result(
    query: str, metadata: dict[str, Any], reason: str
) -> CaliberExpansionResult:
    """Complete fallback path (no LLM at all)."""
    metadata["mode"] = "full_fallback"
    metadata["reason"] = reason
    intent_plan = _build_fallback_intent_plan(query)
    normalized = str(intent_plan.get("normalized_query", query))
    search_plan = _build_fallback_search_plan(query, intent_plan)
    final_plan, filtered_out, guard_review = _caliber_guard(
        dict(search_plan), query, normalized,
    )
    return CaliberExpansionResult(
        query=query,
        normalized_query=normalized,
        intent_plan=dict(intent_plan),
        search_plan=dict(search_plan),
        final_search_plan=final_plan,
        filtered_out=filtered_out,
        guard_review=guard_review,
        fallback_used=True,
        metadata=metadata,
    )
