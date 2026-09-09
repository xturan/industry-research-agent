from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.sources.enums import GovernanceAxis, InfoType, LineFamily, RegionalLevel
from packages.sources.local_source_patterns import (
    LocalEvidenceBackbone,
    all_local_source_pattern_domains,
    generic_local_region_terms,
    is_generic_exact_local_region,
    local_source_domains_for_backbones,
)

ALLOWED_EXECUTION_BUCKETS = {
    "search_assisted_sources",
    "direct_structured_sources",
    "placeholder_or_manual_sources",
}

ALLOWED_TASK_FAMILIES = {
    "policy_direction",
    "local_rollout",
    "project_transaction",
    "enterprise_disclosure",
    "industry_topic",
    "data_metrics",
    "official_record",
}

DIRECT_KEEP_TASK_FAMILIES = {
    "project_transaction",
    "enterprise_disclosure",
    "data_metrics",
    "official_record",
}

DIRECT_KEEP_SOURCE_CLUSTERS = {
    "official_disclosure_backbone",
    "project_transaction_backbone",
    "official_record_backbone",
    "structured_data_backbone",
    "credit_gsxt_backbone",
    "judicial_backbone",
}

MAX_SEARCH_PHRASES_PER_TASK = 3
MAX_EXACT_PHRASES_PER_TASK = 4
_LOCAL_ADMIN_SUFFIXES = ("\u5e02", "\u53bf", "\u533a", "\u65d7")

EXACT_LOCAL_FIRST_LOCAL_ROLLOUT_THEMES = {
    "商业航天",
}

SUPPLEMENTAL_ALLOWED_DOMAINS = {
    "caai.cn",
    "caam.org.cn",
    "battery100.org",
    "chinapv.org.cn",
    "cndkw.com",
    "china-uav.cn",
    "aopa.org.cn",
    "ccpit.org",
    "hiac.org.cn",
    "hiipb.com",
}

AVIATION_REGULATOR_DOMAINS = {
    "caac.gov.cn",
}

HOUSING_POLICY_DOMAINS = {
    "www.gov.cn",
    "ndrc.gov.cn",
    "mohurd.gov.cn",
    "stats.gov.cn",
}

OFFICIAL_RECORD_DOMAINS = {
    "gov.cn",
    "mee.gov.cn",
    "mnr.gov.cn",
    "ndrc.gov.cn",
}

QUERY_DECOMPOSITION_PROMPT_TEMPLATE = """
You are decomposing a research query for a source-driven industry intelligence system.

Rules:
- Do not answer the query.
- Produce search tasks only.
- Preserve line/block/mixed tiaokuai decomposition.
- Use only allowed axis, line_family, regional_level, info_type, and execution_bucket values.
- Keep direct structured sources direct.
- Produce at most 3 search phrases per task.
- Mark missing source coverage explicitly.

Input:
{query}

Known source taxonomy:
{source_taxonomy_summary}

Allowed domains by source cluster:
{domain_allowlist}

Return JSON matching the documented decomposition output shape.
"""

REGION_DOMAIN_MAP: dict[str, list[str]] = {
    "安徽": [
        "ah.gov.cn",
        "fzggw.ah.gov.cn",
        "jx.ah.gov.cn",
        "tjj.ah.gov.cn",
        "kjt.ah.gov.cn",
        "commerce.ah.gov.cn",
    ],
    "芜湖": ["wuhu.gov.cn", "jxj.wuhu.gov.cn", "fgw.wuhu.gov.cn"],
    "马鞍山": ["mas.gov.cn", "jxj.mas.gov.cn", "fgw.mas.gov.cn"],
    "安庆": ["anqing.gov.cn", "jxj.anqing.gov.cn", "fgw.anqing.gov.cn"],
    "蚌埠": ["bengbu.gov.cn", "jxj.bengbu.gov.cn", "fgw.bengbu.gov.cn"],
    "合肥": [
        "hefei.gov.cn",
        "fgw.hefei.gov.cn",
        "gxj.hefei.gov.cn",
        "jxj.hefei.gov.cn",
        "tjj.hefei.gov.cn",
    ],
    "广东": [
        "gd.gov.cn",
        "drc.gd.gov.cn",
        "gdii.gd.gov.cn",
        "stats.gd.gov.cn",
        "gdstc.gd.gov.cn",
        "com.gd.gov.cn",
    ],
    "深圳": ["sz.gov.cn", "gxj.sz.gov.cn"],
    "江苏": [
        "jiangsu.gov.cn",
        "fzggw.jiangsu.gov.cn",
        "gxt.jiangsu.gov.cn",
        "tj.jiangsu.gov.cn",
        "kxjst.jiangsu.gov.cn",
        "doc.jiangsu.gov.cn",
    ],
    "成都": ["chengdu.gov.cn", "jxj.chengdu.gov.cn"],
    "浙江": [
        "zj.gov.cn",
        "fzggw.zj.gov.cn",
        "jxt.zj.gov.cn",
        "tjj.zj.gov.cn",
        "kjt.zj.gov.cn",
        "zcom.zj.gov.cn",
    ],
    "上海": [
        "shanghai.gov.cn",
        "fgw.sh.gov.cn",
        "sheitc.sh.gov.cn",
        "tjj.sh.gov.cn",
        "stcsm.sh.gov.cn",
        "sww.sh.gov.cn",
    ],
    "苏州": ["suzhou.gov.cn", "fgw.suzhou.gov.cn"],
    "常州": ["changzhou.gov.cn", "fgw.changzhou.gov.cn", "gxj.changzhou.gov.cn"],
    "陕西": ["shaanxi.gov.cn", "sndrc.shaanxi.gov.cn", "kjt.shaanxi.gov.cn"],
    "西安": ["xa.gov.cn", "xadrc.xa.gov.cn", "xakj.xa.gov.cn"],
    "杭州": ["hangzhou.gov.cn", "fgw.hangzhou.gov.cn"],
    "武汉": ["wuhan.gov.cn", "gxj.wuhan.gov.cn"],
    "山东": ["shandong.gov.cn", "gxt.shandong.gov.cn"],
    "福建": ["fujian.gov.cn", "fgw.fujian.gov.cn"],
    "河南": ["henan.gov.cn", "gxt.henan.gov.cn"],
    "四川": [
        "sc.gov.cn",
        "fgw.sc.gov.cn",
        "jxt.sc.gov.cn",
        "tjj.sc.gov.cn",
        "kjt.sc.gov.cn",
        "swt.sc.gov.cn",
    ],
    "海南": ["hainan.gov.cn", "plan.hainan.gov.cn", "iithainan.gov.cn"],
    "海口": ["haikou.gov.cn", "fgw.haikou.gov.cn"],
    "三亚": ["sanya.gov.cn", "fgw.sanya.gov.cn"],
    "内蒙古": ["nmg.gov.cn", "fgw.nmg.gov.cn", "gxt.nmg.gov.cn", "tj.nmg.gov.cn"],
}

OFFICIAL_RECORD_REGION_DOMAIN_MAP: dict[str, list[str]] = {
    "安徽": ["sthjt.ah.gov.cn", "zrzyt.ah.gov.cn"],
    "合肥": ["sthjj.hefei.gov.cn", "zrzy.hefei.gov.cn"],
    "内蒙古": ["sthjt.nmg.gov.cn", "zrzy.nmg.gov.cn"],
    "陕西": ["sthjt.shaanxi.gov.cn", "zrzyt.shaanxi.gov.cn", "sndrc.shaanxi.gov.cn"],
    "神木": ["sxsm.gov.cn", "sthjt.shaanxi.gov.cn", "zrzyt.shaanxi.gov.cn", "sndrc.shaanxi.gov.cn"],
    "新疆": ["sthjt.xinjiang.gov.cn", "zrzyt.xinjiang.gov.cn"],
    "若羌": ["xjrq.gov.cn", "xjbz.gov.cn", "sthjt.xinjiang.gov.cn", "zrzyt.xinjiang.gov.cn"],
}

MUNICIPAL_REGIONS = {"深圳", "成都", "上海", "苏州", "常州", "杭州", "武汉", "合肥", "西安"}
PARENT_REGION_BY_MUNICIPAL: dict[str, str] = {
    "深圳": "广东",
    "成都": "四川",
    "上海": "上海",
    "苏州": "江苏",
    "常州": "江苏",
    "杭州": "浙江",
    "武汉": "湖北",
    "合肥": "安徽",
    "西安": "陕西",
}

PROVINCE_DISTRIBUTION_CITY_HINTS: dict[str, list[str]] = {
    "安徽": ["芜湖", "马鞍山", "安庆", "蚌埠"],
    "海南": ["海口", "三亚"],
}
EXACT_LOCAL_ENTITY_DOMAIN_MAP: dict[str, list[str]] = {
    # Exact local discovery hints are not maintained source profiles. They only
    # preserve official-domain-first search targets when the user explicitly
    # names a city/county/park entity.
    "苏州工业园区": ["sipac.gov.cn"],
    "肥西": ["ahfeixi.gov.cn"],
    "神木": ["sxsm.gov.cn"],
    "若羌": ["xjrq.gov.cn"],
}
EXACT_LOCAL_ENTITY_EXCLUDE_DOMAIN_MAP: dict[str, list[str]] = {
    # Feixi Pioneer pages are search-indexed but currently return stale
    # 404/minimal-text responses, exhausting K07's candidate budget.
    "肥西": ["xf.ahfeixi.gov.cn"],
}

GLOBAL_ALLOWED_DOMAINS = {
    "gov.cn",
    "ndrc.gov.cn",
    "miit.gov.cn",
    "most.gov.cn",
    "mofcom.gov.cn",
    "mohurd.gov.cn",
    "www.gov.cn",
    "cninfo.com.cn",
    "sse.com.cn",
    "szse.cn",
    "bse.cn",
    "neeq.com.cn",
    "ccgp.gov.cn",
    "ggzy.gov.cn",
    "stats.gov.cn",
    "customs.gov.cn",
    *OFFICIAL_RECORD_DOMAINS,
    *AVIATION_REGULATOR_DOMAINS,
    *SUPPLEMENTAL_ALLOWED_DOMAINS,
    *{domain for domains in REGION_DOMAIN_MAP.values() for domain in domains},
    *{domain for domains in OFFICIAL_RECORD_REGION_DOMAIN_MAP.values() for domain in domains},
    *{domain for domains in EXACT_LOCAL_ENTITY_DOMAIN_MAP.values() for domain in domains},
    *all_local_source_pattern_domains(),
}

SOURCE_STRATEGY_HINTS = {
    "policy_direction": "cn_policy_first_v2",
    "local_rollout": "cn_local_rollout_v2",
    "project_transaction": "cn_project_signal",
    "enterprise_disclosure": "cn_disclosure_first_v2",
    "industry_topic": "cn_industry_signal_v2",
    "data_metrics": "cn_structured_data_v1",
    "official_record": "cn_official_record_v1",
}

FAMILY_DEFAULTS: dict[str, dict[str, Any]] = {
    "policy_direction": {
        "tiaokuai_axis": GovernanceAxis.LINE,
        "line_family": LineFamily.POLICY,
        "regional_level": RegionalLevel.NATIONAL,
        "info_type": InfoType.POLICY_NOTICE,
        "execution_bucket": "search_assisted_sources",
        "source_cluster": "central_policy_backbone",
        "include_domains": ["gov.cn", "ndrc.gov.cn", "miit.gov.cn", "most.gov.cn"],
        "evidence_goal": "Find national policy framing and official direction.",
        "fallback_path": "Use policy direct profiles where available.",
        "priority": 90,
    },
    "local_rollout": {
        "tiaokuai_axis": GovernanceAxis.BLOCK,
        "line_family": LineFamily.POLICY,
        "regional_level": RegionalLevel.PROVINCIAL,
        "info_type": InfoType.POLICY_NOTICE,
        "execution_bucket": "search_assisted_sources",
        "source_cluster": "province_or_city_backbone",
        "include_domains": [],
        "evidence_goal": "Find local policy rollout, pilots, and implementation signals.",
        "fallback_path": "Use provincial/city DRC or MIIT profiles when available.",
        "priority": 95,
    },
    "project_transaction": {
        "tiaokuai_axis": GovernanceAxis.MIXED,
        "line_family": LineFamily.CROSS_DOMAIN,
        "regional_level": RegionalLevel.CROSS_REGION,
        "info_type": InfoType.PROJECT_TRANSACTION,
        "execution_bucket": "direct_structured_sources",
        "source_cluster": "project_transaction_backbone",
        "include_domains": ["ccgp.gov.cn", "ggzy.gov.cn", "ndrc.gov.cn"],
        "evidence_goal": "Find procurement, public-resource trading, and approval evidence.",
        "fallback_path": "Keep direct query platforms primary; search is supplement only.",
        "priority": 80,
    },
    "enterprise_disclosure": {
        "tiaokuai_axis": GovernanceAxis.MIXED,
        "line_family": LineFamily.EXCHANGE,
        "regional_level": RegionalLevel.CROSS_REGION,
        "info_type": InfoType.REGULATORY_ANNOUNCEMENT,
        "execution_bucket": "direct_structured_sources",
        "source_cluster": "official_disclosure_backbone",
        "include_domains": ["cninfo.com.cn", "sse.com.cn", "szse.cn", "bse.cn"],
        "evidence_goal": "Find listed-company disclosure and official announcement signals.",
        "fallback_path": "Use direct disclosure adapters first; search only supplements IR pages.",
        "priority": 85,
    },
    "industry_topic": {
        "tiaokuai_axis": GovernanceAxis.LINE,
        "line_family": LineFamily.INDUSTRY,
        "regional_level": RegionalLevel.NATIONAL,
        "info_type": InfoType.INDUSTRY_REPORT,
        "execution_bucket": "search_assisted_sources",
        "source_cluster": "association_enhancement",
        "include_domains": [],
        "evidence_goal": "Find association, whitepaper, forum, and topic-platform supplements.",
        "fallback_path": "Treat industry sources as supplemental evidence only.",
        "priority": 60,
    },
    "data_metrics": {
        "tiaokuai_axis": GovernanceAxis.LINE,
        "line_family": LineFamily.CROSS_DOMAIN,
        "regional_level": RegionalLevel.CROSS_REGION,
        "info_type": InfoType.INDUSTRY_NOTICE,
        "execution_bucket": "direct_structured_sources",
        "source_cluster": "structured_data_backbone",
        "include_domains": ["stats.gov.cn", "customs.gov.cn", "mofcom.gov.cn", "ndrc.gov.cn"],
        "evidence_goal": "Find statistics and indicator snapshots for quantitative claims.",
        "fallback_path": "Use structured indicator sources as primary path.",
        "priority": 70,
    },
    "official_record": {
        "tiaokuai_axis": GovernanceAxis.MIXED,
        "line_family": LineFamily.CROSS_DOMAIN,
        "regional_level": RegionalLevel.CROSS_REGION,
        "info_type": InfoType.REGULATORY_ANNOUNCEMENT,
        "execution_bucket": "direct_structured_sources",
        "source_cluster": "official_record_backbone",
        "include_domains": sorted(OFFICIAL_RECORD_DOMAINS),
        "evidence_goal": (
            "Find environmental, land, filing, approval, permit, and regulatory records."
        ),
        "fallback_path": (
            "Use official-record search fallback first; promote stable sources to direct adapters."
        ),
        "priority": 78,
    },
}

THEME_PATTERNS = (
    "房地产",
    "低空经济",
    "人形机器人",
    "新能源汽车",
    "动力电池",
    "新能源汽车换电",
    "换电",
    "光伏产业链",
    "光伏",
    "人工智能产业园区",
    "人工智能",
    "算力基础设施",
    "算力",
    "商业航天",
    "硬科技",
    "现代煤化工",
    "煤化工",
    "绿氢",
    "盐湖",
    "锂钾",
    "白皮书",
)

NEGATIVE_TERMS_BY_THEME: dict[str, list[str]] = {
    "人形机器人": ["低空经济", "通航", "无人机", "UAV", "AOPA", "eVTOL"],
    "具身智能": ["低空经济", "通航", "无人机", "UAV", "AOPA", "eVTOL"],
}

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

OFFICIAL_RECORD_FORMAL_REGION_TERMS: dict[str, str] = {
    "安徽": "安徽省",
    "广东": "广东省",
    "江苏": "江苏省",
    "浙江": "浙江省",
    "山东": "山东省",
    "福建": "福建省",
    "河南": "河南省",
    "四川": "四川省",
    "海南": "海南省",
    "内蒙古": "内蒙古自治区",
    "陕西": "陕西省",
    "新疆": "新疆维吾尔自治区",
    "合肥": "合肥市",
    "深圳": "深圳市",
    "苏州": "苏州市",
    "常州": "常州市",
    "西安": "西安市",
    "神木": "神木市",
    "肥西": "肥西县",
    "若羌": "若羌县",
}


class QueryDecompositionTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, max_length=80)
    task_family: str = Field(min_length=1, max_length=40)
    tiaokuai_axis: GovernanceAxis
    line_family: LineFamily
    regional_level: RegionalLevel
    info_type: InfoType
    execution_bucket: str = Field(min_length=1, max_length=40)
    source_cluster: str = Field(min_length=1, max_length=80)
    source_strategy_hint: str | None = Field(default=None, max_length=80)
    include_domains: list[str] = Field(default_factory=list)
    exclude_domains: list[str] = Field(default_factory=list)
    search_phrases: list[str] = Field(default_factory=list)
    exact_phrases: list[str] = Field(default_factory=list)
    negative_terms: list[str] = Field(default_factory=list)
    evidence_obligations: list[str] = Field(default_factory=list)
    evidence_goal: str = Field(min_length=1, max_length=400)
    fallback_path: str = Field(min_length=1, max_length=400)
    priority: int = Field(default=50, ge=1, le=100)
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)

    @field_validator("task_family")
    @classmethod
    def validate_task_family(cls, value: str) -> str:
        if value not in ALLOWED_TASK_FAMILIES:
            raise ValueError(f"unsupported task_family: {value}")
        return value

    @field_validator("execution_bucket")
    @classmethod
    def validate_execution_bucket(cls, value: str) -> str:
        if value not in ALLOWED_EXECUTION_BUCKETS:
            raise ValueError(f"unsupported execution_bucket: {value}")
        return value

    @field_validator("search_phrases")
    @classmethod
    def validate_search_phrase_count(cls, value: list[str]) -> list[str]:
        if len(value) > MAX_SEARCH_PHRASES_PER_TASK:
            raise ValueError("search_phrases must contain at most 3 phrases")
        return value

    @model_validator(mode="after")
    def validate_direct_keep_bucket(self) -> QueryDecompositionTask:
        if (
            self.task_family in DIRECT_KEEP_TASK_FAMILIES
            or self.source_cluster in DIRECT_KEEP_SOURCE_CLUSTERS
        ) and self.execution_bucket != "direct_structured_sources":
            raise ValueError("direct-keep task families must use direct_structured_sources")
        return self


class QueryDecomposition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_query: str = Field(min_length=1, max_length=800)
    normalized_theme: str = Field(min_length=1, max_length=120)
    regional_focus: list[str] = Field(default_factory=list)
    time_horizon: str = Field(min_length=1, max_length=80)
    user_intent: str = Field(min_length=1, max_length=200)
    decomposition_tasks: list[QueryDecompositionTask] = Field(default_factory=list)
    unsupported_or_missing_sources: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def get_query_decomposition_prompt_template() -> str:
    return QUERY_DECOMPOSITION_PROMPT_TEMPLATE


def build_query_decomposition_prompt(
    query: str,
    *,
    source_taxonomy_summary: str,
    domain_allowlist: str,
) -> str:
    return QUERY_DECOMPOSITION_PROMPT_TEMPLATE.format(
        query=normalize_text(query),
        source_taxonomy_summary=source_taxonomy_summary.strip(),
        domain_allowlist=domain_allowlist.strip(),
    )


def decompose_query(query: str) -> QueryDecomposition:
    normalized_query = normalize_text(query)
    if not normalized_query:
        raise ValueError("query must not be empty")

    theme = extract_theme(normalized_query)
    regions = extract_regions(normalized_query)
    company_hint = extract_company_hint(normalized_query)
    task_families = select_task_families(normalized_query, regions, company_hint)

    tasks = [
        build_task_candidate(
            task_family=task_family,
            task_index=index,
            query=normalized_query,
            theme=theme,
            regions=regions,
            company_hint=company_hint,
        )
        for index, task_family in enumerate(task_families, start=1)
    ]

    return repair_query_decomposition(
        {
            "original_query": normalized_query,
            "normalized_theme": theme,
            "regional_focus": regions,
            "time_horizon": infer_time_horizon(normalized_query),
            "user_intent": infer_user_intent(normalized_query),
            "decomposition_tasks": tasks,
            "unsupported_or_missing_sources": build_missing_source_notes(normalized_query),
            "notes": [],
        }
    )


def build_retrieval_plan(query: str):
    from packages.sources.retrieval_plan import build_retrieval_plan as _build_retrieval_plan

    return _build_retrieval_plan(query)


def build_deterministic_retrieval_plan(query: str):
    from packages.sources.retrieval_plan import (
        build_deterministic_retrieval_plan as _build_deterministic,
    )

    return _build_deterministic(query)


def repair_query_decomposition(
    candidate: QueryDecomposition | Mapping[str, Any],
) -> QueryDecomposition:
    payload = (
        candidate.model_dump()
        if isinstance(candidate, QueryDecomposition)
        else dict(candidate)
    )
    original_query = normalize_text(str(payload.get("original_query") or ""))
    if not original_query:
        raise ValueError("original_query is required")

    normalized_theme = normalize_text(str(payload.get("normalized_theme") or ""))
    if not normalized_theme:
        normalized_theme = extract_theme(original_query)

    regional_focus = normalize_regions(payload.get("regional_focus")) or extract_regions(
        original_query
    )
    notes = collect_string_list(payload.get("notes"))
    if not regional_focus and has_any(original_query, ("地方", "省", "市", "园区", "落地", "试点")):
        regional_focus = ["全国"]
        notes.append("missing_region_repaired_to_national")

    raw_tasks = payload.get("decomposition_tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raw_tasks = [
            build_task_candidate(
                task_family="policy_direction",
                task_index=1,
                query=original_query,
                theme=normalized_theme,
                regions=regional_focus,
                company_hint=extract_company_hint(original_query),
            )
        ]
        notes.append("fallback_task_inserted")

    repaired_tasks: list[QueryDecompositionTask] = []
    for index, raw_task in enumerate(raw_tasks, start=1):
        if isinstance(raw_task, BaseModel):
            task_payload = raw_task.model_dump()
        elif isinstance(raw_task, Mapping):
            task_payload = dict(raw_task)
        else:
            continue
        repaired, task_notes = repair_task_candidate(
            task_payload=task_payload,
            task_index=index,
            theme=normalized_theme,
            regions=regional_focus,
            query=original_query,
        )
        repaired_tasks.append(repaired)
        notes.extend(task_notes)

    if not repaired_tasks:
        fallback = build_task_candidate(
            task_family="policy_direction",
            task_index=1,
            query=original_query,
            theme=normalized_theme,
            regions=regional_focus,
            company_hint=extract_company_hint(original_query),
        )
        repaired, task_notes = repair_task_candidate(
            task_payload=fallback,
            task_index=1,
            theme=normalized_theme,
            regions=regional_focus,
            query=original_query,
        )
        repaired_tasks.append(repaired)
        notes.extend([*task_notes, "fallback_task_inserted"])

    return QueryDecomposition(
        original_query=original_query,
        normalized_theme=normalized_theme,
        regional_focus=regional_focus,
        time_horizon=normalize_text(str(payload.get("time_horizon") or ""))
        or infer_time_horizon(original_query),
        user_intent=normalize_text(str(payload.get("user_intent") or ""))
        or infer_user_intent(original_query),
        decomposition_tasks=repaired_tasks,
        unsupported_or_missing_sources=collect_string_list(
            payload.get("unsupported_or_missing_sources")
        ),
        notes=sorted(set(notes)),
    )


def repair_task_candidate(
    *,
    task_payload: dict[str, Any],
    task_index: int,
    theme: str,
    regions: list[str],
    query: str,
) -> tuple[QueryDecompositionTask, list[str]]:
    notes: list[str] = []
    task_family = normalize_text(str(task_payload.get("task_family") or "")).lower()
    if task_family not in ALLOWED_TASK_FAMILIES:
        task_family = "industry_topic"
        notes.append(f"task_{task_index}_task_family_repaired")

    defaults = FAMILY_DEFAULTS[task_family]
    execution_bucket = normalize_text(str(task_payload.get("execution_bucket") or ""))
    if execution_bucket not in ALLOWED_EXECUTION_BUCKETS:
        execution_bucket = defaults["execution_bucket"]
        notes.append(f"task_{task_index}_execution_bucket_repaired")
    if task_family in DIRECT_KEEP_TASK_FAMILIES and execution_bucket != "direct_structured_sources":
        execution_bucket = "direct_structured_sources"
        notes.append(f"task_{task_index}_direct_source_preserved")

    regional_level_default = infer_regional_level(task_family, regions, defaults["regional_level"])
    if task_family == "local_rollout" and needs_macro_to_local_obligation(query, regions):
        regional_level_default = RegionalLevel.PROVINCIAL
    include_domains = repair_domains(
        task_payload.get("include_domains"),
        defaults["include_domains"],
    )
    generic_exact_local_domains = generic_exact_local_domain_seeds(regions)
    if task_family == "local_rollout":
        include_domains = repair_domains(
            [
                *include_domains,
                *domains_for_regions(regions),
                *domains_for_exact_local_entities(query),
                *generic_exact_local_domains,
            ],
            [],
        )
        if should_prefer_exact_local_first_domains(
            task_family=task_family,
            theme=theme,
            regions=regions,
            query=query,
        ):
            include_domains = remove_parent_region_domains(include_domains, regions)
    if task_family == "enterprise_disclosure":
        include_domains = sorted(set([*include_domains, "cninfo.com.cn", "sse.com.cn", "szse.cn"]))
    if task_family == "project_transaction":
        include_domains = sorted(
            set(
                [
                    *include_domains,
                    *generic_exact_local_domains,
                    "ccgp.gov.cn",
                    "ggzy.gov.cn",
                ]
            )
        )
    if task_family == "official_record":
        include_domains = sorted(
            set(
                [
                    *include_domains,
                    *OFFICIAL_RECORD_DOMAINS,
                    *official_record_domains_for_regions(regions),
                    *domains_for_regions(regions),
                    *domains_for_exact_local_entities(query),
                    *generic_exact_local_domains,
                ]
            )
        )
    if task_family == "data_metrics":
        include_domains = repair_domains([*include_domains, *generic_exact_local_domains], [])
    if task_family == "industry_topic":
        include_domains = repair_domains(
            [*include_domains, *supplemental_domains_for_theme(theme)],
            [],
        )
    exclude_domains = repair_domains(task_payload.get("exclude_domains"), [])
    if task_family == "local_rollout":
        exclude_domains = sorted(
            set(
                [
                    *exclude_domains,
                    *exclude_domains_for_exact_local_entities(query),
                ]
            )
        )

    phrases = repair_search_phrases(
        task_payload.get("search_phrases"),
        task_family=task_family,
        theme=theme,
        regions=regions,
        query=query,
        company_hint=extract_company_hint(query),
    )
    phrases = ensure_region_in_phrases(
        phrases,
        task_family=task_family,
        regions=regions,
        query=query,
        notes=notes,
        task_index=task_index,
    )

    merged_negative_terms = collect_string_list(task_payload.get("negative_terms"))
    if not merged_negative_terms:
        merged_negative_terms = default_negative_terms(task_family=task_family, theme=theme)

    evidence_obligations = collect_string_list(task_payload.get("evidence_obligations"))
    if not evidence_obligations:
        evidence_obligations = evidence_obligations_for_task(
            task_family=task_family,
            query=query,
            regions=regions,
        )

    exact_phrases = collect_string_list(task_payload.get("exact_phrases"))
    if not exact_phrases:
        exact_phrases = default_exact_phrases(task_family=task_family, theme=theme)

    task = QueryDecompositionTask(
        task_id=normalize_text(str(task_payload.get("task_id") or ""))
        or f"{task_family}_{task_index}",
        task_family=task_family,
        tiaokuai_axis=coerce_enum(
            task_payload.get("tiaokuai_axis"),
            GovernanceAxis,
            defaults["tiaokuai_axis"],
            notes,
            f"task_{task_index}_tiaokuai_axis_repaired",
        ),
        line_family=coerce_enum(
            task_payload.get("line_family"),
            LineFamily,
            defaults["line_family"],
            notes,
            f"task_{task_index}_line_family_repaired",
        ),
        regional_level=coerce_enum(
            task_payload.get("regional_level"),
            RegionalLevel,
            regional_level_default,
            notes,
            f"task_{task_index}_regional_level_repaired",
        ),
        info_type=coerce_enum(
            task_payload.get("info_type"),
            InfoType,
            defaults["info_type"],
            notes,
            f"task_{task_index}_info_type_repaired",
        ),
        execution_bucket=execution_bucket,
        source_cluster=normalize_text(str(task_payload.get("source_cluster") or ""))
        or defaults["source_cluster"],
        source_strategy_hint=normalize_text(str(task_payload.get("source_strategy_hint") or ""))
        or SOURCE_STRATEGY_HINTS[task_family],
        include_domains=repair_domains(include_domains, []),
        exclude_domains=exclude_domains,
        search_phrases=phrases,
        exact_phrases=exact_phrases[:MAX_EXACT_PHRASES_PER_TASK],
        negative_terms=merged_negative_terms,
        evidence_obligations=evidence_obligations,
        evidence_goal=normalize_text(str(task_payload.get("evidence_goal") or ""))
        or defaults["evidence_goal"],
        fallback_path=normalize_text(str(task_payload.get("fallback_path") or ""))
        or defaults["fallback_path"],
        priority=clamp_int(task_payload.get("priority"), default=defaults["priority"]),
        confidence=clamp_float(task_payload.get("confidence"), default=0.75),
    )
    return task, notes


def build_task_candidate(
    *,
    task_family: str,
    task_index: int,
    query: str,
    theme: str,
    regions: list[str],
    company_hint: str,
) -> dict[str, Any]:
    defaults = FAMILY_DEFAULTS[task_family]
    source_cluster = defaults["source_cluster"]
    if task_family == "local_rollout" and is_park_city_holdout_query(query, regions):
        source_cluster = "park_city_rollout_backbone"
    return {
        "task_id": f"{task_family}_{task_index}",
        "task_family": task_family,
        "tiaokuai_axis": defaults["tiaokuai_axis"],
        "line_family": defaults["line_family"],
        "regional_level": (
            RegionalLevel.PROVINCIAL
            if task_family == "local_rollout"
            and needs_macro_to_local_obligation(query, regions)
            else infer_regional_level(task_family, regions, defaults["regional_level"])
        ),
        "info_type": defaults["info_type"],
        "execution_bucket": defaults["execution_bucket"],
        "source_cluster": source_cluster,
        "source_strategy_hint": SOURCE_STRATEGY_HINTS[task_family],
        "include_domains": domains_for_task(
            task_family,
            regions,
            theme,
            query=query,
        ),
        "exclude_domains": exclude_domains_for_task(task_family, query=query),
        "search_phrases": default_search_phrases(
            task_family=task_family,
            theme=theme,
            regions=regions,
            query=query,
            company_hint=company_hint,
        ),
        "exact_phrases": default_exact_phrases(task_family=task_family, theme=theme),
        "negative_terms": default_negative_terms(task_family=task_family, theme=theme),
        "evidence_obligations": evidence_obligations_for_task(
            task_family=task_family,
            query=query,
            regions=regions,
        ),
        "evidence_goal": defaults["evidence_goal"],
        "fallback_path": defaults["fallback_path"],
        "priority": defaults["priority"],
        "confidence": 0.75,
    }


def evidence_obligations_for_task(
    *,
    task_family: str,
    query: str,
    regions: list[str],
) -> list[str]:
    level = evidence_obligation_level(query=query, regions=regions)
    obligations = [f"administrative_granularity:{level}"]
    if level in {"city", "county"} and task_family != "policy_direction":
        obligations.append("exact_local_depth")
    if task_family != "policy_direction" and needs_multi_city_distribution(query, regions):
        obligations.append("multi_city_distribution")
    if task_family != "policy_direction" and needs_multi_sector_decomposition(query):
        obligations.append("multi_sector_decomposition")
    if task_family == "data_metrics" and needs_quantitative_metric_evidence(query):
        obligations.append("quantitative_metric_evidence")
    if task_family in {
        "local_rollout",
        "project_transaction",
        "data_metrics",
        "enterprise_disclosure",
    } and needs_macro_to_local_obligation(query, regions):
        obligations.append("macro_to_local_obligation")
    return list(dict.fromkeys(obligations))


def evidence_obligation_level(*, query: str, regions: list[str]) -> str:
    primary_region = regions[0] if regions else ""
    if primary_region in EXACT_LOCAL_ENTITY_DOMAIN_MAP or _query_names_region_with_suffix(
        query,
        primary_region,
        ("\u53bf", "\u65d7", "\u533a"),
    ):
        return "county"
    if (
        primary_region in MUNICIPAL_REGIONS
        or _query_names_region_with_suffix(query, primary_region, ("\u5e02",))
        or (
            is_generic_exact_local_region(primary_region)
            and not _query_names_region_with_suffix(
                query,
                primary_region,
                ("\u53bf", "\u65d7", "\u533a"),
            )
        )
    ) or (
        not regions and has_any(query, ("市",))
    ):
        return "city"
    if regions and regions != ["全国"]:
        return "province"
    return "macro"


def _query_names_region_with_suffix(
    query: str,
    region: str,
    suffixes: tuple[str, ...],
) -> bool:
    if not region:
        return False
    if region.endswith(suffixes):
        return True
    base = region
    for suffix in _LOCAL_ADMIN_SUFFIXES:
        if len(base) > 2 and base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return any(f"{base}{suffix}" in query for suffix in suffixes)


def needs_multi_city_distribution(query: str, regions: list[str]) -> bool:
    if evidence_obligation_level(query=query, regions=regions) != "province":
        return False
    return has_any(
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


def needs_multi_sector_decomposition(query: str) -> bool:
    return len(evidence_sector_terms(query)) >= 2


def evidence_sector_terms(query: str) -> list[str]:
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


def needs_quantitative_metric_evidence(query: str) -> bool:
    return has_any(
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


def needs_macro_to_local_obligation(query: str, regions: list[str]) -> bool:
    local_regions = [region for region in regions if region != "全国"]
    if local_regions:
        return False
    macro_scope = not regions or regions == ["全国"] or has_any(
        query,
        ("国家层面", "中央", "全国"),
    )
    if not macro_scope:
        return False
    asks_for_policy_to_real_world = has_any(
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
    requires_local_or_operational_evidence = has_any(
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


def select_task_families(query: str, regions: list[str], company_hint: str) -> list[str]:
    if is_disclosure_direct_keep_query(query, company_hint):
        families = []
        if should_preserve_local_rollout_with_direct_keep(query, regions):
            families.append("local_rollout")
        families.append("enterprise_disclosure")
        if has_any(
            query,
            (
                "项目",
                "进展",
                "合作",
                "开工",
                "投产",
                "资金来源",
                "项目备案",
                "土地项目",
            ),
        ):
            families.append("project_transaction")
        if needs_statistics_lane(query):
            families.append("data_metrics")
        if needs_industry_capacity_market_lane(query):
            families.append("industry_topic")
        if needs_environmental_land_record_support(query):
            families.append("official_record")
        return families

    if is_project_query_direct_keep_query(query):
        families = ["project_transaction"]
        if needs_environmental_land_record_support(query):
            families.append("official_record")
        return families

    if is_structured_data_direct_keep_query(query):
        families = ["data_metrics"]
        if needs_environmental_land_record_support(query):
            families.append("official_record")
        return families

    if is_park_city_holdout_query(query, regions):
        if park_city_holdout_needs_direct_controls(query):
            families = ["local_rollout"]
            if has_any(
                query,
                ("项目集群", "真实项目", "土地", "开工", "投产", "招标", "中标", "采购"),
            ):
                families.append("project_transaction")
            if has_any(query, ("企业", "企业公告", "上市公司", "公告", "披露")):
                families.append("enterprise_disclosure")
            if needs_statistics_lane(query):
                families.append("data_metrics")
            if needs_environmental_land_record_support(query):
                families.append("official_record")
            return families
        return ["local_rollout"]

    if is_supplemental_only_query(query):
        return ["industry_topic"]

    families: list[str] = []
    national_only = regions == ["全国"] or has_any(query, ("国家层面", "中央", "全国"))
    local_regions = [region for region in regions if region != "全国"]
    real_estate_macro = is_real_estate_macro_query(query, regions)
    macro_to_local = needs_macro_to_local_obligation(query, regions)

    if has_any(query, ("政策", "规划", "趋势", "前景", "未来", "国家层面", "方向")):
        families.append("policy_direction")
    if (macro_to_local and not real_estate_macro) or (not real_estate_macro and (
        local_regions
        or (
            not national_only
            and has_any(query, ("地方", "省", "市", "园区", "落地", "试点"))
        )
        or (
            has_any(query, ("低空经济", "通航", "无人机", "eVTOL"))
            and has_any(query, ("地方试点", "试点地区", "地方落地"))
        )
    )):
        families.append("local_rollout")
    explicit_project_evidence_requested = has_any(
        query,
        (
            "地方项目清单",
            "项目清单",
            "真实项目",
            "建设需求",
            "基础设施建设",
            "低空基础设施",
            "项目落地",
            "项目建设",
            "地方试点",
            "规模化落地",
            "开工",
            "投产",
            "资金来源",
            "项目备案",
            "土地项目",
        ),
    )
    if (not national_only or explicit_project_evidence_requested) and has_any(
        query,
        (
            "项目",
            "招标",
            "中标",
            "采购",
            "落地",
            "机会",
            "基础设施",
            "前景",
            "开工",
            "投产",
            "资金来源",
            "项目备案",
            "土地项目",
        ),
    ):
        families.append("project_transaction")
    if (
        company_hint
        or has_any(query, ("上市公司", "公告", "披露", "年报", "中信海直", "000099"))
        or (not national_only and has_any(query, ("低空经济", "前景", "未来")))
        or needs_sector_disclosure_lane(query)
        or has_any(
            query,
            (
                "企业收入",
                "企业订单",
                "企业投资",
                "企业证据",
                "下游需求",
                "地方基金",
            ),
        )
        or (
            bool(local_regions)
            and has_any(query, ("企业", "下游", "消纳", "项目审批", "订单"))
        )
    ):
        families.append("enterprise_disclosure")
    if (
        has_any(query, ("协会", "白皮书", "论坛", "产业", "趋势", "前景", "补充证据"))
        or needs_industry_capacity_market_lane(query)
    ) or (
        has_any(query, ("低空经济", "通航", "无人机", "eVTOL"))
        and has_any(query, ("规模化落地", "地方试点", "空域改革", "适航"))
    ):
        families.append("industry_topic")
    if needs_statistics_lane(query):
        families.append("data_metrics")
    if needs_environmental_land_record_support(query):
        families.append("official_record")

    if not families:
        families.append("policy_direction")
    if "policy_direction" not in families and not company_hint:
        families.insert(0, "policy_direction")
    if "industry_topic" not in families and has_any(query, ("前景", "趋势", "产业")):
        families.append("industry_topic")

    ordered: list[str] = []
    for family in families:
        if family in ALLOWED_TASK_FAMILIES and family not in ordered:
            ordered.append(family)
    return ordered


def needs_sector_disclosure_lane(query: str) -> bool:
    return has_any(
        query,
        (
            "整车",
            "动力电池",
            "汽车零部件",
            "零部件",
            "龙头带动",
            "供应链",
            "产能",
            "煤炭",
            "煤化工",
            "绿氢",
            "绿电",
            "盐湖",
            "锂钾",
            "算力",
            "数据中心",
            "IDC",
            "商业航天",
            "硬科技",
        ),
    )


def needs_industry_capacity_market_lane(query: str) -> bool:
    return has_any(
        query,
        (
            "市场价格",
            "价格周期",
            "产能集中",
            "产能过剩",
            "产能风险",
            "装机量",
            "销量",
            "出货量",
        ),
    )


def should_preserve_local_rollout_with_direct_keep(query: str, regions: list[str]) -> bool:
    local_regions = [region for region in regions if region != "全国"]
    if not local_regions:
        return False
    return has_any(
        query,
        (
            "地方",
            "市",
            "县",
            "区",
            "园区",
            "产业集群",
            "地方扶持",
            "财政",
            "土地",
            "开工",
            "投产",
            "产能",
            "供应链",
            "政策",
            "项目",
            "招商",
            "落地",
        ),
    )


def is_disclosure_direct_keep_query(query: str, company_hint: str) -> bool:
    if company_hint:
        return has_any(query, ("公告", "披露", "年报", "项目", "进展", "低空经济"))
    return has_any(query, ("上市公司", "公告", "披露", "年报")) and not has_any(
        query,
        ("政策", "规划", "前景", "未来", "趋势", "方向", "协会", "白皮书", "论坛"),
    )


def is_project_query_direct_keep_query(query: str) -> bool:
    if not has_any(query, ("招标", "中标", "采购", "政府采购", "公共资源交易")):
        return False
    return not has_any(query, ("政策", "规划", "前景", "未来", "趋势", "方向", "信号"))


def is_structured_data_direct_keep_query(query: str) -> bool:
    data_markers = ("数据", "统计", "指标", "装机", "发电量", "出口", "价格")
    source_markers = ("国家统计局", "统计局", "海关", "国家能源局", "能源局")
    return has_any(query, data_markers) and has_any(query, source_markers)


def needs_statistics_lane(query: str) -> bool:
    return has_any(
        query,
        (
            "统计",
            "指标",
            "规模",
            "数据",
            "出口",
            "价格",
            "产能",
            "市场价格",
            "产量",
            "销量",
            "用电",
            "能耗",
            "财政",
            "收入",
            "投资",
            "补贴",
            "项目分布",
            "成本",
            "资源",
            "交通",
            "电力",
            "财政依赖",
            "用工",
            "产值",
            "增加值",
            "销售面积",
            "库存",
            "发电量",
            "装机",
        ),
    )


def is_park_city_holdout_query(query: str, regions: list[str]) -> bool:
    if has_any(query, ("园区", "开发区", "产业园", "自贸区")):
        return True
    return bool(set(regions) & MUNICIPAL_REGIONS) and has_any(query, ("机会", "园区"))


def park_city_holdout_needs_direct_controls(query: str) -> bool:
    return has_any(
        query,
        (
            "项目集群",
            "真实项目",
            "土地",
            "开工",
            "投产",
            "招标",
            "中标",
            "采购",
            "企业",
            "企业公告",
            "上市公司",
            "公告",
            "披露",
            "数据",
            "统计",
            "指标",
            "规模",
            "价格",
            "产能",
            "用工",
        ),
    )


def is_supplemental_only_query(query: str) -> bool:
    supplemental_markers = ("协会", "白皮书", "论坛", "联盟", "展会")
    if not has_any(query, supplemental_markers):
        return False
    return not has_any(query, ("政策", "规划", "招标", "中标", "采购", "公告", "披露"))


def is_real_estate_macro_query(query: str, regions: list[str]) -> bool:
    if any(region != "全国" for region in regions):
        return False
    return has_any(query, ("房地产", "城中村改造", "三大工程", "地方收储", "去库存"))


def default_search_phrases(
    *,
    task_family: str,
    theme: str,
    regions: list[str],
    query: str,
    company_hint: str,
) -> list[str]:
    region = regions[0] if regions else "全国"
    if task_family == "policy_direction":
        if theme == "低空经济":
            return [
                "低空经济 空域改革 民航局",
                "低空经济 适航审定 民航局",
                "低空经济 飞行服务保障体系 监管",
            ]
        if theme == "房地产":
            return [
                "site:mohurd.gov.cn 房地产 去库存 城中村改造 三大工程",
                "site:www.gov.cn 国务院 城中村改造 三大工程 保障性住房 平急两用",
                "site:ndrc.gov.cn 房地产 去库存 地方收储 资金来源",
            ]
        return [
            f"{theme} 政策 规划",
            f"{theme} 发展 指导意见",
            f"{theme} 试点 示范 政策",
        ]
    if task_family == "local_rollout":
        exact_entity_phrases = exact_local_entity_search_phrases(
            query=query,
            theme=theme,
            region=region,
        )
        if exact_entity_phrases:
            return exact_entity_phrases
        distribution_phrases = multi_city_distribution_search_phrases(
            task_family=task_family,
            theme=theme,
            regions=regions,
            query=query,
        )
        if distribution_phrases:
            return distribution_phrases
        if needs_macro_to_local_obligation(query, regions) and theme not in {
            "低空经济",
            "房地产",
        }:
            return [
                f"{theme} 地方项目清单 政策落地",
                f"{theme} 省市 重点项目 建设",
                f"{theme} 地方 用电 能耗 项目",
            ]
        if theme == "商业航天":
            return [
                f"{region} 国家民用航天产业基地 商业航天 政策",
                f"{region} 国家民用航天产业基地 商业航天 项目",
                f"{region} 商业航天 地方基金 高校 院所",
            ]
        if has_any(query, ("高校", "院所", "地方基金", "研发到订单")):
            return [
                f"{region} {theme} 地方基金",
                f"{region} {theme} 高校 院所",
                f"{region} {theme} 卫星 发射 项目",
            ]
        sector_phrases = multi_sector_search_phrases(
            task_family=task_family,
            theme=theme,
            region=region,
            query=query,
        )
        if sector_phrases:
            return sector_phrases
        if theme == "低空经济":
            return [
                "低空经济 地方试点 民航局",
                "低空经济 试点示范 地方 政策",
                "低空经济 低空飞行服务保障 地方",
            ]
        return [
            f"{region} {theme} 政策 规划",
            f"{region} {theme} 试点 项目",
            f"{region} {theme} 产业 发展",
        ]
    if task_family == "project_transaction":
        distribution_phrases = multi_city_distribution_search_phrases(
            task_family=task_family,
            theme=theme,
            regions=regions,
            query=query,
        )
        if distribution_phrases:
            return distribution_phrases
        if needs_macro_to_local_obligation(query, regions) and theme not in {
            "低空经济",
            "房地产",
        }:
            return [
                f"{theme} 地方项目清单 重点项目",
                f"{theme} 公共资源交易 招标 中标",
                f"{theme} 用电 能耗 建设需求 项目",
            ]
        sector_phrases = multi_sector_search_phrases(
            task_family=task_family,
            theme=theme,
            region=region,
            query=query,
        )
        if sector_phrases and theme not in {"房地产", "商业航天"}:
            return sector_phrases
        if theme == "低空经济":
            return [
                f"{region} 低空经济 基础设施建设 项目",
                f"{region} 低空经济 公共资源交易 招标 中标",
                f"{region} 低空经济 地方试点 项目",
            ]
        if theme == "房地产":
            return [
                "城中村改造 项目 开工 资金来源",
                "城中村改造 公共资源交易 招标 中标 项目",
                "三大工程 保障性住房 平急两用 项目",
            ]
        if has_any(
            query,
            (
                "项目备案",
                "项目审批",
                "审批",
                "备案",
                "产业化条件",
                "实际产业化",
            ),
        ):
            return [
                f"{region} {theme} 项目备案 审批",
                f"{region} {theme} 重点项目 开工 投产",
                f"{region} {theme} 公共资源交易 招标 中标",
            ]
        if has_any(
            query,
            (
                "项目清单",
                "重点项目",
                "项目集群",
                "开工",
                "投产",
                "土地项目",
                "项目分布",
                "新增产能",
            ),
        ):
            return [
                f"{region} {theme} 重点项目 开工 投产",
                f"{region} {theme} 公共资源交易 招标 中标",
                f"{region} {theme} 项目清单",
            ]
        if "项目" in query and has_any(
            query,
            (
                "环评",
                "能耗",
                "企业投资",
                "财政依赖",
                "资源",
                "交通",
                "电力",
            ),
        ):
            return [
                f"{region} {theme} 重点项目 开工 投产",
                f"{region} {theme} 项目备案 审批",
                f"{region} {theme} 公共资源交易 招标 中标",
            ]
        return [
            f"{region} {theme} 公共资源交易 招标 中标",
            f"{region} {theme} 政府采购 项目",
            f"{region} {theme} 基础设施 项目",
        ]
    if task_family == "enterprise_disclosure":
        if theme == "房地产" and not company_hint:
            return [
                "钢铁 水泥 家电 工程机械 房地产 需求 年报",
                "上市公司 房地产 下游需求 收入 披露",
                "房地产 开工 竣工 销售 企业收入 公告",
            ]
        regional_phrases = regional_enterprise_disclosure_search_phrases(
            query=query,
            theme=theme,
            region=region,
            company_hint=company_hint,
        )
        if regional_phrases:
            return regional_phrases
        company = company_hint or f"{theme} 上市公司"
        return [
            f"{company} 公告",
            f"{company} 披露",
            f"{company} 项目 进展",
        ]
    if task_family == "industry_topic":
        if needs_industry_capacity_market_lane(query):
            if "动力电池" in query and "光伏" in query:
                return [
                    "动力电池 产能 价格 最新 行业协会",
                    "光伏 产能 价格 最新 行业协会",
                    "动力电池 光伏 产能过剩 报告",
                ]
            return [
                f"{theme} 产能 价格 最新 行业协会",
                f"{theme} 产能过剩 报告",
                f"{theme} 市场价格 数据",
            ]
        if region != "全国":
            sector_phrases = regional_industry_topic_search_phrases(
                query=query,
                theme=theme,
                region=region,
            )
            if sector_phrases:
                return sector_phrases
        if theme == "低空经济":
            return [
                "低空经济 协会 白皮书 报告",
                "低空经济 行业协会 论坛",
                "低空经济 产业 报告",
            ]
        if theme in {"算力基础设施", "算力"}:
            return [
                "算力 基础设施 白皮书 产业 报告",
                "算力 基础设施 论坛 报告",
                "算力 行业 白皮书",
            ]
        return [f"{theme} 白皮书 产业链", f"{theme} 协会 报告", f"{theme} 论坛 趋势"]
    if task_family == "data_metrics":
        stats_agency = statistics_agency_term(region)
        finance_agency = finance_agency_term(region)
        distribution_phrases = multi_city_distribution_search_phrases(
            task_family=task_family,
            theme=theme,
            regions=regions,
            query=query,
        )
        if distribution_phrases:
            return distribution_phrases
        if is_compute_power_data_metrics_query(query=query, theme=theme):
            return [
                "国家数据局 全国数据资源调查报告 算力",
                "国家能源局 全国电力工业统计数据 用电量",
                "工业和信息化部 绿色数据中心 能效",
            ]
        if is_low_altitude_official_statistics_query(query=query, theme=theme):
            return [
                "低空经济 产业统计分类 国家统计局",
                "低空经济 市场规模 数据",
                "低空经济 企业订单 数据",
            ]
        if is_inner_mongolia_energy_data_metrics_query(query=query, regions=regions):
            return [
                "内蒙古自治区能源局 电力运行 发电量 用电量",
                "内蒙古 绿电 绿氢 煤化工 能耗 消纳 数据",
                "内蒙古自治区统计局 能源 统计公报",
            ]
        if needs_macro_to_local_obligation(query, regions) and theme not in {
            "低空经济",
            "房地产",
        }:
            return [
                f"{theme} 用电 能耗 数据",
                f"{theme} 建设需求 统计",
                f"{theme} 地方项目 投资 数据",
            ]
        if theme != "房地产" and has_any(
            query,
            ("财政", "补贴", "专项资金", "财政支持", "资金来源", "税收"),
        ):
            return [
                f"{stats_agency} {theme} 统计公报",
                f"{region} {theme} 财政资金 补贴",
                f"{finance_agency} {theme} 财政资金 补贴",
            ]
        sector_phrases = multi_sector_search_phrases(
            task_family=task_family,
            theme=theme,
            region=region,
            query=query,
        )
        if sector_phrases and theme != "房地产":
            if region != "全国":
                return [f"{stats_agency} {theme} 统计公报", *sector_phrases]
            return sector_phrases
        if theme == "低空经济" and has_any(query, ("规模化", "企业订单", "规模化落地")):
            return [
                "低空经济 市场规模 数据",
                "低空经济 基础设施 统计",
                "低空经济 企业订单 数据",
            ]
        if theme == "房地产":
            return [
                "房地产开发投资 新开工面积 销售面积 库存 国家统计局",
                "商品房销售面积 待售面积 房地产 国家统计局",
                "房屋新开工 竣工面积 统计数据",
            ]
        return [
            f"{stats_agency} {theme} 统计 数据",
            f"{region} {theme} 指标 规模",
            f"{region} {theme} 出口 价格",
        ]
    if task_family == "official_record":
        record_region = official_record_formal_region_term(region)
        if theme == "房地产":
            return [
                "城中村改造 环评 公示",
                "城中村改造 土地出让 自然资源",
                "三大工程 项目备案 审批",
            ]
        if "若羌" in query and has_any(query, ("盐湖", "锂钾", "罗布泊")):
            return [
                "若羌 罗布泊 盐湖 环评 公示",
                "若羌 盐湖锂钾 项目备案 环评",
                "若羌 锂钾 矿产资源 总体规划",
            ]
        if "神木" in query and "煤化工" in query:
            return [
                "神木 煤化工 环境影响评价 报告书",
                "神木 兰炭 煤化工 环评 公示",
                "神木 煤化工 节能审查 批复",
            ]
        if "内蒙古" in query and has_any(query, ("绿氢", "现代煤化工", "煤化工")):
            return [
                "内蒙古 绿氢 煤制烯烃 环评 公示",
                "内蒙古 煤基新材料 环境影响评价",
                "内蒙古 现代煤化工 节能审查 批复",
            ]
        return [
            f"{record_region} {theme} 环评 公示",
            f"{record_region} {theme} 土地出让 自然资源",
            f"{record_region} {theme} 项目备案 审批",
        ]
    return [query]


def is_compute_power_data_metrics_query(*, query: str, theme: str) -> bool:
    return theme in {"算力", "算力基础设施"} and has_any(
        query,
        (
            "东数西算",
            "全国一体化算力",
            "算力网络",
            "数据中心",
            "用电",
            "能耗",
            "绿色数据中心",
        ),
    )


def is_low_altitude_official_statistics_query(*, query: str, theme: str) -> bool:
    return theme == "低空经济" and has_any(
        query,
        (
            "规模化",
            "规模化落地",
            "空域改革",
            "适航",
            "地方试点",
            "企业订单",
            "市场规模",
        ),
    )


def is_inner_mongolia_energy_data_metrics_query(*, query: str, regions: list[str]) -> bool:
    return "内蒙古" in regions and has_any(
        query,
        (
            "绿电",
            "绿氢",
            "煤化工",
            "现代煤化工",
            "消纳",
            "用电价格",
            "风光资源",
        ),
    )


def multi_city_distribution_search_phrases(
    *,
    task_family: str,
    theme: str,
    regions: list[str],
    query: str,
) -> list[str]:
    if not needs_multi_city_distribution(query, regions):
        return []
    region = regions[0] if regions else "全国"
    city_hints = PROVINCE_DISTRIBUTION_CITY_HINTS.get(region, [])
    if len(city_hints) < 2:
        return []
    first_city, second_city = city_hints[0], city_hints[1]
    if task_family == "local_rollout":
        return [
            f"{region} {theme} 多地协同 产业链",
            f"{first_city} {theme} 产业 政策",
            f"{second_city} {theme} 产业 政策",
        ]
    if task_family == "project_transaction":
        return [
            f"{first_city} {theme} 重点项目 开工 投产",
            f"{second_city} {theme} 公共资源交易 招标 中标",
            f"{region} {theme} 项目分布 重点项目",
        ]
    if task_family == "data_metrics":
        return [
            f"{statistics_agency_term(region)} {theme} 统计公报",
            f"{statistics_agency_term(first_city)} {theme} 产量 统计",
            f"{statistics_agency_term(second_city)} {theme} 统计公报",
        ]
    return []


def multi_sector_search_phrases(
    *,
    task_family: str,
    theme: str,
    region: str,
    query: str,
) -> list[str]:
    sectors = focused_evidence_sector_terms(query)
    if len(sectors) < 2:
        return []
    first = sectors[0]
    second = sectors[1]
    third = sectors[2] if len(sectors) > 2 else sectors[0]
    if task_family == "local_rollout":
        return [
            f"{region} {first} 产业 政策",
            f"{region} {second} 产业 政策",
            f"{region} {third} 产业 政策",
        ]
    if task_family == "project_transaction":
        if region in MUNICIPAL_REGIONS or any(
            entity in query for entity in EXACT_LOCAL_ENTITY_DOMAIN_MAP
        ):
            return [
                f"{region} {first} 项目 重点项目 开工 投产 招标",
                f"{region} {theme} 公共资源交易 招标 中标",
                f"{region} {second} 项目 采购 开工 投产",
            ]
        return [
            f"{region} {first} 项目 重点项目 开工 投产 招标",
            f"{region} {second} 项目 重点项目 开工 投产 招标",
            f"{region} {third} 项目 采购 开工 投产",
        ]
    if task_family == "data_metrics":
        return [
            f"{region} {' '.join(sectors[:3])} 统计 数据",
            f"{region} {first} 产量 价格 数据",
            f"{region} {second} 规模 数据",
        ]
    return []


def focused_evidence_sector_terms(query: str) -> list[str]:
    sectors = evidence_sector_terms(query)
    if len(sectors) > 3 and has_any(query, ("扩展到", "还是已经扩展", "是否已经扩展")):
        return sectors[-3:]
    return sectors


def regional_industry_topic_search_phrases(
    *,
    query: str,
    theme: str,
    region: str,
) -> list[str]:
    if theme in {"自由贸易港", "海南自由贸易港"} and has_any(
        query,
        ("旅游", "医药", "航运", "数字贸易", "实体项目", "产业投资"),
    ):
        return [
            f"{region} {theme} 医药 航运 数字贸易 投资 报告",
            f"{region} {theme} 旅游 医药 航运 数字贸易 项目",
            f"{theme} 产业投资 协会 报告",
        ]
    if has_any(
        query,
        (
            "产业链",
            "供应链",
            "整车",
            "电池",
            "零部件",
            "龙头",
            "协同",
            "产业集群",
            "产业分布",
            "项目分布",
        ),
    ):
        return [
            f"{region} {theme} 产业链 报告",
            f"{region} {theme} 行业协会 报告",
            f"{region} {theme} 产量 销量 数据",
        ]
    return []


def regional_enterprise_disclosure_search_phrases(
    *,
    query: str,
    theme: str,
    region: str,
    company_hint: str,
) -> list[str]:
    if company_hint or region == "全国":
        return []
    sectors = disclosure_sector_terms_from_query(query, theme)
    subject = " ".join([region, *sectors]) if sectors else f"{region} {theme}".strip()
    if not subject or subject == region:
        return []
    return [
        f"{subject} 上市公司 公告",
        f"{subject} 上市公司 披露",
        f"{subject} 上市公司 项目 进展",
    ]


def disclosure_sector_terms_from_query(query: str, theme: str) -> list[str]:
    terms: list[str] = []
    for term in (
        "新能源汽车",
        "动力电池",
        "光伏",
        "储能",
        "半导体",
        "算力",
        "数据中心",
        "商业航天",
        "卫星",
        "煤化工",
        "绿氢",
        "医药",
        "航运",
        "数字贸易",
        "旅游",
        "自由贸易港",
    ):
        if term in query and term not in terms:
            terms.append(term)
    if not terms and theme:
        terms.append(theme)
    if theme and theme in terms and terms[0] != theme:
        terms = [theme, *[term for term in terms if term != theme]]
    elif theme and theme not in terms:
        terms.insert(0, theme)
    return terms[:4]


def repair_search_phrases(
    raw_phrases: Any,
    *,
    task_family: str,
    theme: str,
    regions: list[str],
    query: str,
    company_hint: str,
) -> list[str]:
    values = collect_string_list(raw_phrases)
    if not values:
        values = default_search_phrases(
            task_family=task_family,
            theme=theme,
            regions=regions,
            query=query,
            company_hint=company_hint,
        )
    exact_entity_phrases = exact_local_entity_search_phrases(
        query=query,
        theme=theme,
        region=regions[0] if regions else "全国",
    )
    if task_family == "local_rollout" and exact_entity_phrases:
        values = [*exact_entity_phrases, *values]
    deduped: list[str] = []
    for phrase in values:
        if phrase not in deduped:
            deduped.append(phrase)
    return deduped[:MAX_SEARCH_PHRASES_PER_TASK]


def default_exact_phrases(*, task_family: str, theme: str) -> list[str]:
    return []


def ensure_region_in_phrases(
    phrases: list[str],
    *,
    task_family: str,
    regions: list[str],
    query: str,
    notes: list[str],
    task_index: int,
) -> list[str]:
    regional_phrase_families = {"local_rollout", "project_transaction", "official_record"}
    if task_family not in regional_phrase_families or not regions:
        return phrases
    if task_family in {
        "local_rollout",
        "project_transaction",
    } and needs_macro_to_local_obligation(query, regions):
        return phrases
    if task_family == "local_rollout" and any(
        entity in phrase
        for entity in EXACT_LOCAL_ENTITY_DOMAIN_MAP
        for phrase in phrases
    ):
        return phrases
    region = regions[0]
    if all(region not in phrase for phrase in phrases):
        notes.append(f"task_{task_index}_region_prefixed")
        return [f"{region} {phrase}" for phrase in phrases[:MAX_SEARCH_PHRASES_PER_TASK]]
    return phrases


def extract_theme(query: str) -> str:
    for pattern in THEME_PATTERNS:
        if pattern in query:
            return pattern
    cleaned = query
    for region in REGION_DOMAIN_MAP:
        cleaned = cleaned.replace(region, " ")
    cleaned = re.sub(r"[（）()，,。？?]", " ", cleaned)
    cleaned = re.sub(
        r"(未来|前景|如何|有哪些|政策|项目|公告|方向|趋势|情况|信号|机会|国家层面|在|的)",
        " ",
        cleaned,
    )
    parts = [part for part in cleaned.split() if part]
    return parts[0][:30] if parts else query[:30]


def extract_regions(query: str) -> list[str]:
    regions: list[str] = []
    for entity in EXACT_LOCAL_ENTITY_DOMAIN_MAP:
        if entity in query and entity not in regions:
            regions.append(entity)
    for region in REGION_DOMAIN_MAP:
        if region in query and region not in regions:
            regions.append(region)
    for region in generic_local_region_terms(query):
        if region not in regions:
            regions.append(region)
    if not regions and has_any(query, ("国家层面", "全国", "中央")):
        regions.append("全国")
    return regions


def extract_company_hint(query: str) -> str:
    ticker = re.search(r"\b(\d{6}\.(?:SZ|SH|BJ))\b", query, flags=re.IGNORECASE)
    if ticker:
        code = ticker.group(1).upper()
        prefix = query[: ticker.start()].strip(" （(")
        company_match = re.search(r"([\u4e00-\u9fa5]{2,12})$", prefix)
        if company_match:
            return f"{company_match.group(1)} {code}"
        return code
    if "中信海直" in query:
        return "中信海直 000099.SZ"
    company = re.search(r"([\u4e00-\u9fa5]{2,12})(?:股份|集团|公司)", query)
    return company.group(1) if company else ""


def infer_time_horizon(query: str) -> str:
    if has_any(query, ("未来", "前景", "趋势", "方向")):
        return "future_outlook"
    if has_any(query, ("最新", "当前", "目前")):
        return "latest_focus"
    return "unspecified"


def infer_user_intent(query: str) -> str:
    if has_any(query, ("公告", "披露", "上市公司")):
        return "find disclosure and project evidence"
    if has_any(query, ("招标", "中标", "项目", "采购")):
        return "assess project rollout with structured signals"
    return "assess policy direction and industry signals"


def build_missing_source_notes(query: str) -> list[str]:
    notes: list[str] = []
    if has_any(query, ("低空经济", "通航", "无人机", "eVTOL")):
        notes.append(
            "Aviation-specific regulator/source family may be needed for "
            "low-altitude economy topics."
        )
    if needs_environmental_land_record_support(query):
        notes.append(
            "Environmental/land/regulatory records may require dedicated EIA, "
            "natural-resources, land-transfer, or project-filing adapters."
        )
    if has_any(query, ("信用", "GSXT", "司法")):
        notes.append(
            "Credit, GSXT, and judicial paths require special direct/manual source handling."
        )
    return notes


def needs_environmental_land_record_support(query: str) -> bool:
    if has_any(query, OFFICIAL_RECORD_DIRECT_KEYWORDS):
        return True
    return has_any(query, OFFICIAL_RECORD_CONTEXT_KEYWORDS) and has_any(
        query,
        OFFICIAL_RECORD_PROJECT_KEYWORDS,
    )


def official_record_formal_region_term(region: str) -> str:
    normalized = region.strip()
    if not normalized:
        return region
    if normalized in OFFICIAL_RECORD_FORMAL_REGION_TERMS:
        return OFFICIAL_RECORD_FORMAL_REGION_TERMS[normalized]
    if normalized.endswith(("省", "市", "县", "区", "旗", "盟", "州")):
        return normalized
    return normalized


def statistics_agency_term(region: str) -> str:
    normalized = region.strip()
    if normalized == "全国":
        return "国家统计局"
    formal_region = official_record_formal_region_term(normalized)
    return f"{formal_region}统计局"


def finance_agency_term(region: str) -> str:
    normalized = region.strip()
    if normalized == "全国":
        return "财政部"
    formal_region = official_record_formal_region_term(normalized)
    if formal_region.endswith(("省", "自治区")):
        return f"{formal_region}财政厅"
    return f"{formal_region}财政局"


def infer_regional_level(
    task_family: str,
    regions: list[str],
    default: RegionalLevel,
) -> RegionalLevel:
    if task_family == "policy_direction":
        return RegionalLevel.NATIONAL
    if not regions:
        return default
    if any(region in EXACT_LOCAL_ENTITY_DOMAIN_MAP for region in regions):
        return RegionalLevel.MUNICIPAL
    if any(region in MUNICIPAL_REGIONS for region in regions):
        return RegionalLevel.MUNICIPAL
    if any(is_generic_exact_local_region(region) for region in regions):
        return RegionalLevel.MUNICIPAL
    if regions == ["全国"]:
        return RegionalLevel.NATIONAL
    return RegionalLevel.PROVINCIAL


def domains_for_task(
    task_family: str,
    regions: list[str],
    theme: str,
    *,
    query: str = "",
) -> list[str]:
    domains = list(FAMILY_DEFAULTS[task_family]["include_domains"])
    generic_exact_local_domains = generic_exact_local_domain_seeds(regions)
    if task_family == "policy_direction" and theme == "低空经济":
        domains.extend(AVIATION_REGULATOR_DOMAINS)
    if task_family == "policy_direction" and theme == "房地产":
        domains = list(HOUSING_POLICY_DOMAINS)
    if task_family == "data_metrics" and theme == "房地产":
        domains = ["stats.gov.cn", "ndrc.gov.cn"]
    if task_family == "data_metrics":
        if is_compute_power_data_metrics_query(query=query, theme=theme):
            domains.extend(["nda.gov.cn", "nea.gov.cn", "miit.gov.cn"])
        if is_low_altitude_official_statistics_query(query=query, theme=theme):
            domains.extend(["stats.gov.cn", "ndrc.gov.cn", "caac.gov.cn"])
        local_backbone_domains = local_domains_for_task_backbones(
            task_family,
            regions,
            query=query,
        )
        domains = [
            *domains_for_exact_local_entities(query),
            *generic_exact_local_domains,
            *domains_for_distribution_city_hints(regions, query),
            *local_backbone_domains,
            *domains_for_regions(regions),
            *domains,
        ]
    if task_family == "official_record":
        domains.extend(OFFICIAL_RECORD_DOMAINS)
        domains.extend(official_record_domains_for_regions(regions))
        domains.extend(domains_for_regions(regions))
        domains.extend(domains_for_exact_local_entities(query))
        domains.extend(generic_exact_local_domains)
        domains.extend(local_domains_for_task_backbones(task_family, regions, query=query))
    if task_family == "local_rollout":
        if needs_macro_to_local_obligation(query, regions):
            domains.extend(["gov.cn", "ndrc.gov.cn", "miit.gov.cn"])
        if theme == "低空经济":
            domains.extend(["gov.cn", *AVIATION_REGULATOR_DOMAINS])
        exact_local_domains = domains_for_exact_local_entities(query)
        distribution_city_domains = domains_for_distribution_city_hints(regions, query)
        domains.extend(generic_exact_local_domains)
        domains.extend(domains_for_regions(regions))
        exact_local_first = should_prefer_exact_local_first_domains(
            task_family=task_family,
            theme=theme,
            regions=regions,
            query=query,
        )
        domains.extend(
            local_domains_for_task_backbones(
                task_family,
                regions,
                query=query,
                include_parent=not exact_local_first,
            )
        )
        if not exact_local_first:
            parent_regions = parent_regions_for_fallback(regions)
            if parent_regions:
                domains.extend(domains_for_regions(parent_regions))
        domains.extend(distribution_city_domains)
        domains.extend(exact_local_domains)
    if task_family == "project_transaction":
        domains.extend(domains_for_regions(regions))
        domains.extend(domains_for_exact_local_entities(query))
        domains.extend(generic_exact_local_domains)
        domains.extend(domains_for_distribution_city_hints(regions, query))
        domains.extend(local_domains_for_task_backbones(task_family, regions, query=query))
    if task_family == "industry_topic":
        domains.extend(supplemental_domains_for_theme(theme))
    return repair_domains(domains, [])


def local_evidence_backbones_for_task(task_family: str) -> list[LocalEvidenceBackbone]:
    if task_family == "local_rollout":
        return ["local_government"]
    if task_family == "project_transaction":
        return ["project_public_resource"]
    if task_family == "data_metrics":
        return ["statistics_fiscal"]
    if task_family == "official_record":
        return ["environmental_land_record"]
    return []


def generic_exact_local_domain_seeds(regions: list[str]) -> list[str]:
    if any(is_generic_exact_local_region(region) for region in regions):
        return ["gov.cn"]
    return []


def local_domains_for_task_backbones(
    task_family: str,
    regions: list[str],
    *,
    query: str = "",
    include_parent: bool = True,
) -> list[str]:
    include_fiscal = has_any(
        query,
        ("财政", "收入", "补贴", "资金", "投资", "用工", "财政依赖"),
    )
    return local_source_domains_for_backbones(
        regions,
        local_evidence_backbones_for_task(task_family),
        include_parent=include_parent,
        include_fiscal=include_fiscal,
    )


def supplemental_domains_for_theme(theme: str) -> list[str]:
    if theme == "低空经济":
        return ["caai.cn", "aopa.org.cn", "china-uav.cn"]
    if theme in {"人形机器人", "具身智能"}:
        return ["caai.cn", "ccpit.org"]
    if theme in {"算力基础设施", "算力"}:
        return ["cndkw.com"]
    if theme in {"动力电池", "动力电池产业链"}:
        return ["battery100.org", "caam.org.cn", "chinapv.org.cn", "ccpit.org"]
    if theme in {"新能源汽车", "新能源汽车产业链", "新能源汽车换电", "换电"}:
        return ["caam.org.cn", "battery100.org", "ccpit.org"]
    if theme in {"光伏产业链", "光伏"}:
        return ["chinapv.org.cn", "ccpit.org"]
    if theme in {"自由贸易港", "海南自由贸易港"}:
        return ["hiipb.com", "hiac.org.cn"]
    if theme in {"锂电", "储能", "储能产业链"}:
        return ["battery100.org", "ccpit.org"]
    if theme:
        return ["ccpit.org"]
    return []


def default_negative_terms(*, task_family: str, theme: str) -> list[str]:
    if task_family not in {"policy_direction", "local_rollout", "data_metrics"}:
        return []
    return NEGATIVE_TERMS_BY_THEME.get(theme, [])


def domains_for_regions(regions: list[str]) -> list[str]:
    domains: list[str] = []
    for region in regions:
        domains.extend(REGION_DOMAIN_MAP.get(region, []))
    return domains


def domains_for_distribution_city_hints(regions: list[str], query: str) -> list[str]:
    if not needs_multi_city_distribution(query, regions):
        return []
    domains: list[str] = []
    for region in regions[:1]:
        for city in PROVINCE_DISTRIBUTION_CITY_HINTS.get(region, []):
            domains.extend(REGION_DOMAIN_MAP.get(city, []))
    return domains


def official_record_domains_for_regions(regions: list[str]) -> list[str]:
    domains: list[str] = []
    for region in regions:
        domains.extend(OFFICIAL_RECORD_REGION_DOMAIN_MAP.get(region, []))
        parent = PARENT_REGION_BY_MUNICIPAL.get(region)
        if parent:
            domains.extend(OFFICIAL_RECORD_REGION_DOMAIN_MAP.get(parent, []))
    return domains


def domains_for_exact_local_entities(query: str) -> list[str]:
    domains: list[str] = []
    for entity, entity_domains in EXACT_LOCAL_ENTITY_DOMAIN_MAP.items():
        if entity in query:
            domains.extend(entity_domains)
    return domains


def exclude_domains_for_task(task_family: str, *, query: str = "") -> list[str]:
    if task_family != "local_rollout":
        return []
    return repair_domains(exclude_domains_for_exact_local_entities(query), [])


def exclude_domains_for_exact_local_entities(query: str) -> list[str]:
    domains: list[str] = []
    for entity, entity_domains in EXACT_LOCAL_ENTITY_EXCLUDE_DOMAIN_MAP.items():
        if entity in query:
            domains.extend(entity_domains)
    return domains


def should_skip_parent_region_domains_for_exact_local(
    query: str,
    *,
    regions: list[str] | None = None,
) -> bool:
    candidate_regions = regions or []
    for region in candidate_regions:
        if _is_park_or_zone_region(region):
            continue
        if region in EXACT_LOCAL_ENTITY_DOMAIN_MAP:
            return True
        if _query_names_region_with_suffix(query, region, ("\u53bf", "\u65d7")):
            return True
    return any(
        entity in query and not _is_park_or_zone_region(entity)
        for entity in EXACT_LOCAL_ENTITY_DOMAIN_MAP
    )


def should_prefer_exact_local_first_domains(
    *,
    task_family: str,
    theme: str,
    regions: list[str],
    query: str,
) -> bool:
    if task_family != "local_rollout":
        return False
    if should_skip_parent_region_domains_for_exact_local(query, regions=regions):
        return True
    if not any(region in MUNICIPAL_REGIONS for region in regions):
        return False
    return theme in EXACT_LOCAL_FIRST_LOCAL_ROLLOUT_THEMES


def _is_park_or_zone_region(region: str) -> bool:
    return any(
        term in region
        for term in (
            "\u56ed\u533a",
            "\u5f00\u53d1\u533a",
            "\u9ad8\u65b0\u533a",
            "\u65b0\u533a",
            "\u81ea\u8d38\u533a",
        )
    )


def remove_parent_region_domains(domains: list[str], regions: list[str]) -> list[str]:
    parent_domains = set(domains_for_regions(parent_regions_for_fallback(regions)))
    if not parent_domains:
        return domains
    return [domain for domain in domains if domain not in parent_domains]


def exact_local_entity_search_phrases(
    *,
    query: str,
    theme: str,
    region: str,
) -> list[str]:
    phrases: list[str] = []
    for entity in EXACT_LOCAL_ENTITY_DOMAIN_MAP:
        if entity not in query:
            continue
        if entity == "肥西" and theme == "新能源汽车":
            phrases.extend(
                [
                    "肥西 新能源汽车 产业集群 合肥市工业和信息化局",
                    "肥西 新能源汽车 项目 园区",
                    "肥西 新能源汽车 土地 用工",
                ]
            )
            continue
        phrases.extend(
            [
                f"{entity} {theme} 政策",
                f"{entity} {theme} 项目",
                f"{region} {theme} 园区 政策",
            ]
        )
    return phrases[:MAX_SEARCH_PHRASES_PER_TASK]


def parent_regions_for_fallback(regions: list[str]) -> list[str]:
    parents: list[str] = []
    for region in regions:
        parent = PARENT_REGION_BY_MUNICIPAL.get(region)
        if parent and parent not in parents:
            parents.append(parent)
    return parents


def repair_domains(raw_domains: Any, defaults: list[str]) -> list[str]:
    candidates = raw_domains if isinstance(raw_domains, list) else defaults
    values: list[str] = []
    for value in candidates:
        if not isinstance(value, str):
            continue
        domain = value.strip().lower()
        if domain and is_allowed_domain(domain):
            values.append(domain)
    if not values:
        values = [domain for domain in defaults if is_allowed_domain(domain)]
    return list(dict.fromkeys(values))


def is_allowed_domain(domain: str) -> bool:
    return domain in GLOBAL_ALLOWED_DOMAINS or domain.endswith(".gov.cn")


def normalize_regions(raw_regions: Any) -> list[str]:
    if not isinstance(raw_regions, list):
        return []
    normalized: list[str] = []
    for value in raw_regions:
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        if candidate and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def collect_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            normalized = normalize_text(item)
            if normalized:
                result.append(normalized)
    return result


def coerce_enum(
    value: Any,
    enum_cls: type[GovernanceAxis] | type[LineFamily] | type[RegionalLevel] | type[InfoType],
    default: GovernanceAxis | LineFamily | RegionalLevel | InfoType,
    notes: list[str],
    note: str,
) -> GovernanceAxis | LineFamily | RegionalLevel | InfoType:
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        for item in enum_cls:
            if item.value == normalized:
                return item
    notes.append(note)
    return default


def clamp_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, 1), 100)


def clamp_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, 0.0), 1.0)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


__all__ = [
    "ALLOWED_EXECUTION_BUCKETS",
    "ALLOWED_TASK_FAMILIES",
    "DIRECT_KEEP_SOURCE_CLUSTERS",
    "DIRECT_KEEP_TASK_FAMILIES",
    "MAX_SEARCH_PHRASES_PER_TASK",
    "QUERY_DECOMPOSITION_PROMPT_TEMPLATE",
    "QueryDecomposition",
    "QueryDecompositionTask",
    "build_query_decomposition_prompt",
    "decompose_query",
    "build_retrieval_plan",
    "build_deterministic_retrieval_plan",
    "get_query_decomposition_prompt_template",
    "repair_query_decomposition",
]
