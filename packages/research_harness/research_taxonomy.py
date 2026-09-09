"""Canonical research taxonomy — single source of truth for the industry-research
planning layer (Phase 1 refactor).

The old taxonomy mixed three abstraction levels (research dimension / evidence
source family / evidence purpose). This module defines the corrected hierarchy:

  first layer  : research dimension  (what question the report answers)
  second layer : source family       (where evidence comes from)
  third layer  : purpose             (what the evidence supports)

The slot mechanism keeps its `{dimension}.{source_family}.{purpose}` shape
(research_contract.py), so downstream (section_claim_assignment / structured_draft)
that key by section_id keep working unchanged.

Coverage / independence / authority / freshness rules are NOT here — they belong
to the sufficiency-gate phase (Phase 2).
"""

from __future__ import annotations

from typing import Any

from packages.sources.local_source_patterns import canonical_source_family

# ── First layer: 14 research dimensions (10 base + 4 conditional) ──────────

DIMENSIONS: dict[str, dict[str, Any]] = {
    "industry_scope": {
        "label": "产业定义与研究边界",
        "expected_section_heading": "产业定义与研究边界",
        "key_fields": ["scope_definition", "included_scope", "excluded_scope",
                       "statistical_scope", "region", "time_ref"],
        "search_key_fields": [
            "产业名称", "核心产品或服务", "纳入范围", "排除范围", "统计口径",
            "地域范围", "时间范围", "相邻产业", "概念来源",
        ],
        "source_priority": "research",
        "base_or_conditional": "base",
    },
    "policy_regulation": {
        "label": "政策与监管",
        "expected_section_heading": "政策与监管",
        "key_fields": ["policy_name", "issuing_body", "policy_tool",
                       "effective_date", "region", "time_ref"],
        "search_key_fields": [
            "政策名称", "发文机关", "发布日期", "生效日期", "有效期", "政策层级",
            "适用地域", "适用主体", "政策工具", "量化目标", "支持金额或补贴标准",
            "申报条件", "责任部门", "配套实施文件", "当前执行状态",
        ],
        "source_priority": "government",
        "base_or_conditional": "base",
    },
    "market_scale": {
        "label": "市场规模与增长",
        "expected_section_heading": "市场规模与增长",
        "key_fields": ["metric", "value", "unit", "region", "time_ref",
                       "growth_rate"],
        "search_key_fields": [
            "统计公报", "指标名称", "指标数值", "单位", "地域", "时间", "同比或复合增速",
            "基期", "统计范围", "数据口径", "数据来源", "是否预测值", "预测方法",
            "细分市场",
        ],
        "source_priority": "government",
        "base_or_conditional": "base",
    },
    "industry_chain": {
        "label": "产业链与价值链",
        "expected_section_heading": "产业链与价值链",
        "key_fields": ["chain_stage", "segment", "entity", "product", "value",
                       "region"],
        "search_key_fields": [
            "产业链环节", "子环节", "产品或服务", "代表企业", "核心能力",
            "上下游关系", "客户或供应商", "地域", "产能或供给能力", "收入来源",
            "价值量", "本地化程度", "时间",
        ],
        "source_priority": "research",
        "base_or_conditional": "base",
    },
    "supply_competition": {
        "label": "供给与竞争格局",
        "expected_section_heading": "供给与竞争格局",
        "key_fields": ["company", "product", "capacity", "market_share",
                       "revenue", "region"],
        "search_key_fields": [
            "企业名称", "企业类型", "产品", "市场定位", "技术路线", "产能",
            "产量", "订单", "客户", "市场份额", "收入", "毛利率", "资质",
            "竞争优势", "地域布局", "时间",
        ],
        "source_priority": "enterprise",
        "base_or_conditional": "base",
    },
    "demand_scenarios": {
        "label": "需求与应用场景",
        "expected_section_heading": "需求与应用场景",
        "key_fields": ["scenario", "demand_side", "paid", "stage", "amount",
                       "region", "time_ref"],
        "search_key_fields": [
            "场景名称", "需求方", "最终客户", "痛点", "替代方案", "使用频率",
            "订单量", "货运量", "合同金额", "是否付费", "是否试点", "采购周期",
            "时间", "地域",
        ],
        "source_priority": "mixed",
        "base_or_conditional": "base",
    },
    "technology_product": {
        "label": "技术路线与产品成熟度",
        "expected_section_heading": "技术路线与产品成熟度",
        "key_fields": ["product_model", "parameter", "maturity",
                       "certification_status", "cost"],
        "search_key_fields": [
            "技术路线", "产品型号", "核心参数", "载重", "航程", "续航",
            "安全冗余", "运行环境", "技术成熟度", "认证状态", "量产状态", "成本",
            "知识产权", "技术瓶颈", "时间",
        ],
        "source_priority": "research",
        "base_or_conditional": "base",
    },
    "project_execution": {
        "label": "项目落地与执行状态",
        "expected_section_heading": "项目落地与执行状态",
        "key_fields": ["project_name", "subject", "amount", "stage",
                       "tender_status", "region", "time_ref"],
        "search_key_fields": [
            "项目名称", "项目主体", "参与单位", "地域", "所属产业链环节",
            "建设内容", "投资金额", "资金来源", "建设规模", "产能", "开工时间",
            "计划完成时间", "当前阶段", "招标状态", "中标单位", "验收状态",
            "运营状态", "实际产出",
        ],
        "source_priority": "mixed",
        "base_or_conditional": "base",
    },
    "business_economics": {
        "label": "商业模式与产业经济性",
        "expected_section_heading": "商业模式与产业经济性",
        "key_fields": ["revenue_model", "price", "cost", "margin",
                       "utilization", "subsidy_dependency"],
        "search_key_fields": [
            "收费模式", "客户类型", "单价", "单次收入", "单次成本", "固定成本",
            "变动成本", "毛利率", "设备利用率", "盈亏平衡点", "补贴依赖",
            "回收周期", "替代方案成本", "时间",
        ],
        "source_priority": "enterprise",
        "base_or_conditional": "base",
    },
    "risk_constraints": {
        "label": "风险、约束与瓶颈",
        "expected_section_heading": "风险、约束与瓶颈",
        "key_fields": ["risk_type", "risk_object", "evidence", "impact",
                       "mitigation"],
        "search_key_fields": [
            "风险类型", "风险对象", "直接证据", "影响环节", "影响程度",
            "发生条件", "缓解措施", "时间", "地域",
        ],
        "source_priority": "research",
        "base_or_conditional": "base",
    },
    "company_fundamentals": {
        "label": "企业经营与财务",
        "expected_section_heading": "企业经营与财务",
        "key_fields": ["company", "segment_revenue", "margin", "orders",
                       "capex", "time_ref"],
        "search_key_fields": [
            "公司", "业务分部", "收入", "同比增速", "毛利率", "订单",
            "合同金额", "客户", "产能", "资本开支", "研发投入", "政府补助",
            "应收账款", "时间",
        ],
        "source_priority": "enterprise",
        "base_or_conditional": "conditional",
    },
    "capital_activity": {
        "label": "投融资与资本活动",
        "expected_section_heading": "投融资与资本活动",
        "key_fields": ["entity", "round", "amount", "valuation", "investor",
                       "time_ref"],
        "search_key_fields": [
            "融资主体", "融资轮次", "金额", "估值", "投资方", "资金用途",
            "并购标的", "产业基金", "政府引导基金", "时间",
        ],
        "source_priority": "enterprise",
        "base_or_conditional": "conditional",
    },
    "regional_benchmark": {
        "label": "区域比较与产业集群",
        "expected_section_heading": "区域比较与产业集群",
        "key_fields": ["benchmark_region", "metric", "value", "company_count",
                       "policy_intensity", "time_ref"],
        "search_key_fields": [
            "对标地区", "指标", "企业数量", "龙头企业", "项目数量",
            "产业链完整度", "政策强度", "融资规模", "产值", "应用场景",
            "人才基础", "时间",
        ],
        "source_priority": "government",
        "base_or_conditional": "conditional",
    },
    "outlook_drivers": {
        "label": "趋势判断与前景",
        "expected_section_heading": "趋势判断与前景",
        "key_fields": ["driver", "leading_indicator", "trigger", "constraint",
                       "time_horizon"],
        "search_key_fields": [
            "驱动因素", "领先指标", "触发条件", "制约条件", "时间区间",
            "情景假设", "乐观情景", "基准情景", "悲观情景", "证据来源",
        ],
        "source_priority": "research",
        "base_or_conditional": "conditional",
    },
}

BASE_DIMENSIONS: tuple[str, ...] = tuple(
    dim_id for dim_id, meta in DIMENSIONS.items()
    if meta["base_or_conditional"] == "base"
)
CONDITIONAL_DIMENSIONS: tuple[str, ...] = tuple(
    dim_id for dim_id, meta in DIMENSIONS.items()
    if meta["base_or_conditional"] == "conditional"
)

# Legacy dimension_type -> canonical dimension (compatibility layer). Old plan
# fixtures / persisted plans keep working; production emits the new values.
_LEGACY_DIMENSION_TO_CANONICAL: dict[str, str] = {
    "policy": "policy_regulation",
    "local_rollout": "project_execution",
    "execution": "project_execution",
    "disclosure": "company_fundamentals",
    "statistics": "market_scale",
    "industry": "industry_chain",
}


def canonicalize_dimension_type(dimension_type: str | None) -> str:
    """Map a (possibly legacy) dimension_type to a canonical research dimension.
    New values pass through unchanged; unknown/empty stay as-is."""
    key = str(dimension_type or "").strip()
    return _LEGACY_DIMENSION_TO_CANONICAL.get(key, key)


# ── Second layer: 15 canonical source families (+1 retained compat) ─────────

SOURCE_FAMILIES: frozenset[str] = frozenset({
    "policy_document",
    "local_official",
    "official_statistics",
    "tender_procurement",
    "exchange_disclosure",
    "company_disclosure",
    "company_material",
    "certification_database",
    "standard_document",
    "patent_database",
    "association_thinktank",
    "broker_research",
    "industry_research",
    "commercial_media",
    "operator_data",
    "environmental_land",  # retained for backward compatibility (old data/tests)
})

# Slot-purpose suffix (slot_id third segment) per source family.
SOURCE_FAMILY_PURPOSE: dict[str, str] = {
    "policy_document": "policy_basis",
    "local_official": "local_context",
    "official_statistics": "statistical_evidence",
    "tender_procurement": "tender_evidence",
    "exchange_disclosure": "disclosure_basis",
    "company_disclosure": "company_basis",
    "company_material": "company_material",
    "certification_database": "certification_evidence",
    "standard_document": "standard_basis",
    "patent_database": "patent_evidence",
    "association_thinktank": "thinktank_context",
    "broker_research": "broker_research",
    "industry_research": "industry_context",
    "commercial_media": "media_context",
    "operator_data": "operator_evidence",
    "environmental_land": "environmental_record",
}

# Context/supporting families -> optional slots.
CONTEXT_FAMILIES: frozenset[str] = frozenset({
    "local_official",
    "company_material",
    "association_thinktank",
    "broker_research",
    "industry_research",
    "commercial_media",
})

# Primary (most authoritative) source family per dimension -> primary_source_required hint.
DIMENSION_PRIMARY_FAMILY: dict[str, str] = {
    "industry_scope": "industry_research",
    "policy_regulation": "policy_document",
    "market_scale": "official_statistics",
    "industry_chain": "industry_research",
    "supply_competition": "exchange_disclosure",
    "demand_scenarios": "operator_data",
    "technology_product": "certification_database",
    "project_execution": "tender_procurement",
    "business_economics": "company_disclosure",
    "risk_constraints": "industry_research",
    "company_fundamentals": "exchange_disclosure",
    "capital_activity": "company_disclosure",
    "regional_benchmark": "official_statistics",
    "outlook_drivers": "industry_research",
}

SOURCE_FAMILY_LABELS: dict[str, str] = {
    "policy_document": "政策文件",
    "local_official": "地方官方动态",
    "official_statistics": "官方统计",
    "tender_procurement": "招投标交易",
    "exchange_disclosure": "交易所披露",
    "company_disclosure": "公司披露",
    "company_material": "公司资料",
    "certification_database": "认证数据库",
    "standard_document": "标准文件",
    "patent_database": "专利数据库",
    "association_thinktank": "行业协会与智库",
    "broker_research": "券商研报",
    "industry_research": "行业研究",
    "commercial_media": "商业媒体",
    "operator_data": "运营数据",
    "environmental_land": "环境与土地记录",
}


def slot_id(dimension_id: str, family: str) -> str:
    """Build a slot_id preserving the `{dimension}.{source_family}.{purpose}`
    shape. `family` is canonicalized so legacy strings resolve correctly."""
    fam = canonical_source_family(family)
    purpose = SOURCE_FAMILY_PURPOSE.get(fam, "evidence")
    return f"{dimension_id}.{fam}.{purpose}"
