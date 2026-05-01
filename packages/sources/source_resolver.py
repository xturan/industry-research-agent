from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.sources.enums import RegionalLevel
from packages.sources.local_source_patterns import (
    generic_local_region_terms,
    is_generic_exact_local_region,
    local_source_domain_region_map,
)
from packages.sources.query_decomposition import (
    DIRECT_KEEP_TASK_FAMILIES,
    EXACT_LOCAL_ENTITY_DOMAIN_MAP,
    SUPPLEMENTAL_ALLOWED_DOMAINS,
    QueryDecompositionTask,
)

SUPPLEMENTAL_DOMAINS = set(SUPPLEMENTAL_ALLOWED_DOMAINS)

_PARENT_REGION_BY_CITY = {
    "深圳": "广东",
    "成都": "四川",
    "上海": "上海",
    "苏州": "江苏",
    "常州": "江苏",
    "杭州": "浙江",
    "武汉": "湖北",
    "合肥": "安徽",
    "肥西": "安徽",
    "神木": "陕西",
    "若羌": "新疆",
}

_PARK_COUNTY_MARKERS = ("园区", "开发区", "产业园", "高新区", "自贸区", "县", "区")

_REGION_DOMAIN_TO_NAME = {
    "ah.gov.cn": "安徽",
    "fzggw.ah.gov.cn": "安徽",
    "jx.ah.gov.cn": "安徽",
    "tjj.ah.gov.cn": "安徽",
    "kjt.ah.gov.cn": "安徽",
    "commerce.ah.gov.cn": "安徽",
    "hefei.gov.cn": "合肥",
    "fgw.hefei.gov.cn": "合肥",
    "gxj.hefei.gov.cn": "合肥",
    "jxj.hefei.gov.cn": "合肥",
    "tjj.hefei.gov.cn": "合肥",
    "xf.ahfeixi.gov.cn": "肥西",
    "gd.gov.cn": "广东",
    "drc.gd.gov.cn": "广东",
    "gdii.gd.gov.cn": "广东",
    "stats.gd.gov.cn": "广东",
    "gdstc.gd.gov.cn": "广东",
    "com.gd.gov.cn": "广东",
    "sz.gov.cn": "深圳",
    "gxj.sz.gov.cn": "深圳",
    "jiangsu.gov.cn": "江苏",
    "fzggw.jiangsu.gov.cn": "江苏",
    "gxt.jiangsu.gov.cn": "江苏",
    "tj.jiangsu.gov.cn": "江苏",
    "kxjst.jiangsu.gov.cn": "江苏",
    "doc.jiangsu.gov.cn": "江苏",
    "chengdu.gov.cn": "成都",
    "jxj.chengdu.gov.cn": "成都",
    "zj.gov.cn": "浙江",
    "fzggw.zj.gov.cn": "浙江",
    "jxt.zj.gov.cn": "浙江",
    "tjj.zj.gov.cn": "浙江",
    "kjt.zj.gov.cn": "浙江",
    "zcom.zj.gov.cn": "浙江",
    "shanghai.gov.cn": "上海",
    "fgw.sh.gov.cn": "上海",
    "sheitc.sh.gov.cn": "上海",
    "tjj.sh.gov.cn": "上海",
    "stcsm.sh.gov.cn": "上海",
    "sww.sh.gov.cn": "上海",
    "suzhou.gov.cn": "苏州",
    "fgw.suzhou.gov.cn": "苏州",
    "changzhou.gov.cn": "常州",
    "fgw.changzhou.gov.cn": "常州",
    "gxj.changzhou.gov.cn": "常州",
    "hangzhou.gov.cn": "杭州",
    "fgw.hangzhou.gov.cn": "杭州",
    "wuhan.gov.cn": "武汉",
    "gxj.wuhan.gov.cn": "武汉",
    "shandong.gov.cn": "山东",
    "gxt.shandong.gov.cn": "山东",
    "fujian.gov.cn": "福建",
    "fgw.fujian.gov.cn": "福建",
    "henan.gov.cn": "河南",
    "gxt.henan.gov.cn": "河南",
    "sc.gov.cn": "四川",
    "fgw.sc.gov.cn": "四川",
    "jxt.sc.gov.cn": "四川",
    "tjj.sc.gov.cn": "四川",
    "kjt.sc.gov.cn": "四川",
    "swt.sc.gov.cn": "四川",
    "ahfeixi.gov.cn": "肥西",
    "sxsm.gov.cn": "神木",
    "xjrq.gov.cn": "若羌",
    "hainan.gov.cn": "海南",
    "plan.hainan.gov.cn": "海南",
    "iithainan.gov.cn": "海南",
    "nmg.gov.cn": "内蒙古",
    "fgw.nmg.gov.cn": "内蒙古",
    "gxt.nmg.gov.cn": "内蒙古",
    "tj.nmg.gov.cn": "内蒙古",
    **local_source_domain_region_map(),
}

_KNOWN_REGION_MARKERS = tuple(sorted(set(_REGION_DOMAIN_TO_NAME.values())))

_THEME_ALIASES = {
    "real_estate_demand": ("房地产", "城中村改造", "三大工程", "地方收储", "去库存"),
    "humanoid_robotics": ("人形机器人", "具身智能", "机器人"),
    "low_altitude_economy": ("低空经济", "通航", "无人机", "uav", "evtol"),
    "computing_infrastructure": ("算力基础设施", "算力", "智算中心", "数据中心"),
    "photovoltaics": ("光伏", "光伏产业链"),
    "battery_swap": ("换电", "新能源汽车换电"),
}

_NEGATIVE_TERMS_BY_THEME = {
    "humanoid_robotics": ("低空经济", "通航", "无人机", "uav", "aopa", "evtol"),
}

_REAL_ESTATE_CENTRAL_POLICY_DOMAINS = (
    "www.gov.cn",
    "mohurd.gov.cn",
    "ndrc.gov.cn",
    "stats.gov.cn",
)
_GENERIC_NAVIGATION_TOKENS = (
    "公众参与",
    "领导信箱",
    "在线咨询",
    "我要建议",
    "互动交流",
    "网站地图",
    "首页",
    "gzcy",
)
_GENERIC_NAVIGATION_PATHS = (
    "/index.html",
    "/index.htm",
    "/gzcy/index.html",
    "/gzcy/index.htm",
)

_CENTRAL_OR_NATIONAL_POLICY_DOMAINS = (
    "www.gov.cn",
    "ndrc.gov.cn",
    "miit.gov.cn",
    "most.gov.cn",
    "stats.gov.cn",
    "mohurd.gov.cn",
    "caac.gov.cn",
    "mee.gov.cn",
    "mnr.gov.cn",
    "mot.gov.cn",
    "mof.gov.cn",
    "mofcom.gov.cn",
    "customs.gov.cn",
)

_ROUND3_SUPPLEMENTAL_OR_FALLBACK_TASK_FAMILIES = {
    "industry_topic",
    "local_rollout",
}


class CandidateCompatibilityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["accept", "reject"]
    reason_code: str = Field(min_length=1, max_length=120)
    reason_message: str = Field(min_length=1, max_length=500)


def evaluate_candidate_compatibility(
    *,
    task: QueryDecompositionTask,
    query: str,
    url: str,
    domain: str | None,
    title: str | None,
    snippet: str | None,
    allowed_domains: set[str],
) -> CandidateCompatibilityDecision:
    if task.task_family in DIRECT_KEEP_TASK_FAMILIES:
        return _reject(
            "direct_keep_boundary_violation",
            "Direct structured task families cannot use search-assisted primary execution.",
        )

    if task.task_family not in {"policy_direction", "local_rollout", "industry_topic"}:
        return _reject(
            "coverage_lane_not_supported",
            f"Task family {task.task_family} is not supported in first-wave search-assisted lane.",
        )

    if not _is_domain_allowed(domain, allowed_domains):
        return _reject(
            "off_domain_candidate",
            "Candidate domain is outside the allowed domain boundary.",
        )

    role = _classify_domain_role(domain)
    if task.task_family in {"policy_direction", "local_rollout"}:
        if role == "supplemental":
            return _reject(
                "supplemental_used_in_primary_lane",
                "Supplemental domains cannot be used in primary policy/local lanes.",
            )
        if role != "official":
            return _reject(
                "source_role_mismatch",
                "Source role is incompatible with primary policy/local lanes.",
            )
    elif task.task_family == "industry_topic" and role != "supplemental":
        return _reject(
            "source_role_mismatch",
            "Industry-topic lane accepts only supplemental/theme domains.",
        )

    region_markers = _extract_region_markers(task)
    local_fallback_level: str | None = None
    if task.task_family == "local_rollout" and region_markers:
        local_fallback_level = _resolve_local_fallback_level(
            task=task,
            region_markers=region_markers,
            domain=domain,
            title=title,
            snippet=snippet,
        )
        if local_fallback_level is None:
            return _reject(
                "region_mismatch",
                "Candidate does not match required local region focus.",
            )
        if _is_generic_navigation_index_candidate(
            url=url,
            title=title,
            snippet=snippet,
        ):
            return _reject(
                "generic_navigation_index_page",
                "Generic navigation/index page cannot be treated as local rollout evidence.",
            )

    if task.task_family == "policy_direction":
        exact_local_markers = _extract_exact_local_markers_from_query(query)
        if exact_local_markers and not _policy_candidate_matches_exact_local_focus(
            exact_local_markers,
            domain=domain,
            title=title,
            snippet=snippet,
        ):
            return _reject(
                "region_mismatch",
                "Candidate does not match the exact local focus required by the query.",
            )

    theme_key = _infer_theme_key(query=query, task=task)
    aliases = _theme_aliases(theme_key)
    text_blob = _candidate_text_blob(url=url, title=title, snippet=snippet)
    theme_hit = _contains_any(text_blob, aliases) if aliases else False

    negative_terms = _collect_negative_terms(task, theme_key)
    if negative_terms and _contains_any(text_blob, negative_terms) and not theme_hit:
        return _reject(
            "negative_term_mismatch",
            "Candidate is dominated by negative terms that conflict with the task theme.",
        )

    if aliases and task.task_family in {"policy_direction", "local_rollout", "industry_topic"}:
        if not theme_hit:
            return _reject(
                "domain_topic_mismatch",
                "Candidate text does not match task theme aliases.",
            )
    if (
        task.task_family == "policy_direction"
        and theme_key == "real_estate_demand"
        and not _is_real_estate_central_policy_domain(domain)
    ):
        return _reject(
            "national_policy_non_central_domain",
            "Real-estate macro policy lane accepts only central domains "
            "(State Council/MOHURD/NDRC/NBS).",
        )

    if task.task_family == "local_rollout":
        reason_code = _local_accept_reason_code(local_fallback_level)
        reason_message = "Local rollout candidate accepted under city/county fallback rules."
    else:
        reason_code = "accepted_official_or_allowlisted_domain"
        reason_message = "Candidate accepted after compatibility checks."

    return CandidateCompatibilityDecision(
        decision="accept",
        reason_code=reason_code,
        reason_message=reason_message,
    )


def _reject(reason_code: str, reason_message: str) -> CandidateCompatibilityDecision:
    return CandidateCompatibilityDecision(
        decision="reject",
        reason_code=reason_code,
        reason_message=reason_message,
    )


def _is_domain_allowed(domain: str | None, allowed_domains: set[str]) -> bool:
    if not domain:
        return False
    for allowed in allowed_domains:
        candidate = allowed.strip().lower()
        if not candidate:
            continue
        if domain == candidate or domain.endswith(f".{candidate}"):
            return True
    return False


def _classify_domain_role(domain: str | None) -> Literal["official", "supplemental", "other"]:
    if not domain:
        return "other"
    if any(domain == item or domain.endswith(f".{item}") for item in SUPPLEMENTAL_DOMAINS):
        return "supplemental"
    if domain.endswith(".gov.cn") or domain == "gov.cn":
        return "official"
    return "other"


def _extract_region_markers(task: QueryDecompositionTask) -> set[str]:
    phrase_markers: set[str] = set()
    for phrase in task.search_phrases:
        first_token = phrase.strip().split(" ", 1)[0].strip()
        if first_token in _KNOWN_REGION_MARKERS:
            phrase_markers.add(first_token)
            continue
        for region in generic_local_region_terms(phrase):
            phrase_markers.add(region)
        if _requires_exact_local_depth(task) and _looks_like_exact_local_marker(
            first_token,
        ):
            phrase_markers.add(first_token)
        for region in _KNOWN_REGION_MARKERS:
            if region in phrase:
                phrase_markers.add(region)
    if phrase_markers:
        return _prune_parent_region_markers(phrase_markers)

    domain_markers: set[str] = set()
    for domain in task.include_domains:
        normalized = domain.strip().lower()
        if not normalized:
            continue
        for mapped_domain, region_name in _REGION_DOMAIN_TO_NAME.items():
            if normalized == mapped_domain or normalized.endswith(f".{mapped_domain}"):
                domain_markers.add(region_name)
    return _prune_parent_region_markers(domain_markers)


def _extract_exact_local_markers_from_query(query: str) -> set[str]:
    markers = set(generic_local_region_terms(query))
    for region in _PARENT_REGION_BY_CITY:
        if region in query and region != _PARENT_REGION_BY_CITY.get(region):
            markers.add(region)
    return _prune_parent_region_markers(markers)


def _requires_exact_local_depth(task: QueryDecompositionTask) -> bool:
    return "exact_local_depth" in task.evidence_obligations


def _looks_like_exact_local_marker(value: str) -> bool:
    return bool(value) and 2 <= len(value) <= 8 and value not in {
        "全国",
        "中国",
        "政策",
        "项目",
        "产业",
    }


def _resolve_local_fallback_level(
    *,
    task: QueryDecompositionTask,
    region_markers: set[str],
    domain: str | None,
    title: str | None,
    snippet: str | None,
) -> str | None:
    if not region_markers:
        return "exact_city"

    normalized_domain = domain.lower() if domain else ""
    content = f"{title or ''} {snippet or ''}"
    candidate_region = _region_from_domain(normalized_domain)
    is_park_or_county_query = _is_park_or_county_query(task)
    has_park_or_county_marker = _contains_any(content, _PARK_COUNTY_MARKERS)
    allow_parent_fallback = (
        task.regional_level == RegionalLevel.MUNICIPAL or is_park_or_county_query
    )

    if (
        is_park_or_county_query
        and candidate_region in region_markers
        and _is_exact_local_entity_domain(normalized_domain, candidate_region)
    ):
        return "exact_park_or_county"

    if (
        is_park_or_county_query
        and candidate_region in region_markers
        and _is_park_or_county_domain(normalized_domain)
    ):
        return "exact_park_or_county"

    if (
        is_park_or_county_query
        and has_park_or_county_marker
        and _is_park_or_county_domain(normalized_domain)
    ):
        if candidate_region in region_markers or any(
            region in content for region in region_markers
        ):
            return "exact_park_or_county"

    if candidate_region in region_markers:
        return "parent_city" if is_park_or_county_query else "exact_city"

    if any(region in content for region in region_markers):
        if is_park_or_county_query:
            return "parent_city"
        if candidate_region is None:
            return "exact_city"
        for marker in region_markers:
            if _PARENT_REGION_BY_CITY.get(marker) == candidate_region:
                return "province"
        return None

    if allow_parent_fallback:
        if (
            _requires_exact_local_depth(task)
            and candidate_region is None
            and any(is_generic_exact_local_region(marker) for marker in region_markers)
        ):
            return None
        for marker in region_markers:
            parent = _PARENT_REGION_BY_CITY.get(marker)
            if not parent:
                continue
            if candidate_region == parent or parent in content:
                return "province"

        if candidate_region is None and (
            normalized_domain.endswith(".gov.cn") or normalized_domain == "gov.cn"
        ):
            return "national"

    return None


def _policy_candidate_matches_exact_local_focus(
    region_markers: set[str],
    *,
    domain: str | None,
    title: str | None,
    snippet: str | None,
) -> bool:
    if not region_markers:
        return True
    normalized_domain = domain.lower() if domain else ""
    if _is_central_or_national_policy_domain(normalized_domain):
        return True

    content = f"{title or ''} {snippet or ''}"
    candidate_region = _region_from_domain(normalized_domain)
    if candidate_region in region_markers:
        return True
    if any(region in content for region in region_markers):
        return True

    for marker in region_markers:
        parent = _PARENT_REGION_BY_CITY.get(marker)
        if not parent:
            continue
        if candidate_region == parent:
            return True
        if parent in content and candidate_region is None:
            return True
    return False


def _is_central_or_national_policy_domain(domain: str) -> bool:
    if domain == "gov.cn":
        return True
    return any(
        domain == central_domain or domain.endswith(f".{central_domain}")
        for central_domain in _CENTRAL_OR_NATIONAL_POLICY_DOMAINS
    )


def _region_from_domain(domain: str) -> str | None:
    if not domain:
        return None
    for mapped_domain, region_name in _REGION_DOMAIN_TO_NAME.items():
        if domain == mapped_domain or domain.endswith(f".{mapped_domain}"):
            return region_name
    return None


def _is_park_or_county_query(task: QueryDecompositionTask) -> bool:
    if "park" in task.source_cluster.lower():
        return True
    for phrase in task.search_phrases:
        if _contains_any(phrase, _PARK_COUNTY_MARKERS):
            return True
    return False


def _is_park_or_county_domain(domain: str) -> bool:
    if not domain:
        return False
    markers = ("park", "zone", "sipac", "ftz", "ahfeixi")
    return any(marker in domain for marker in markers)


def _is_exact_local_entity_domain(domain: str, region: str | None) -> bool:
    if not domain or not region:
        return False
    for mapped_domain in EXACT_LOCAL_ENTITY_DOMAIN_MAP.get(region, []):
        normalized = mapped_domain.lower()
        if domain == normalized or domain.endswith(f".{normalized}"):
            return True
    return False


def _prune_parent_region_markers(markers: set[str]) -> set[str]:
    pruned = set(markers)
    for city, parent in _PARENT_REGION_BY_CITY.items():
        if parent == city:
            continue
        if city in pruned and parent in pruned:
            pruned.remove(parent)
    return pruned


def _local_accept_reason_code(level: str | None) -> str:
    if level == "exact_park_or_county":
        return "accepted_exact_park_or_county_official"
    if level == "exact_city":
        return "accepted_exact_city_or_county_official"
    if level == "parent_city":
        return "accepted_parent_city_official_fallback"
    if level == "province":
        return "accepted_parent_province_official_fallback"
    if level == "national":
        return "accepted_parent_national_official_fallback"
    return "accepted_official_or_allowlisted_domain"


def _matches_region(
    region_markers: set[str],
    *,
    domain: str | None,
    title: str | None,
    snippet: str | None,
) -> bool:
    if not region_markers:
        return True
    if domain:
        for mapped_domain, region_name in _REGION_DOMAIN_TO_NAME.items():
            if (domain == mapped_domain or domain.endswith(f".{mapped_domain}")) and (
                region_name in region_markers
            ):
                return True
    content = f"{title or ''} {snippet or ''}"
    return any(region in content for region in region_markers)


def _infer_theme_key(*, query: str, task: QueryDecompositionTask) -> str:
    if task.task_family == "industry_topic":
        return _infer_theme_key_from_text(query)
    text = _candidate_text_blob(url="", title=query, snippet=" ".join(task.search_phrases))
    return _infer_theme_key_from_text(text)


def _infer_theme_key_from_text(text: str) -> str:
    if _contains_any(text, _THEME_ALIASES["humanoid_robotics"]):
        return "humanoid_robotics"
    if _contains_any(text, _THEME_ALIASES["low_altitude_economy"]):
        return "low_altitude_economy"
    if _contains_any(text, _THEME_ALIASES["computing_infrastructure"]):
        return "computing_infrastructure"
    if _contains_any(text, _THEME_ALIASES["photovoltaics"]):
        return "photovoltaics"
    if _contains_any(text, _THEME_ALIASES["battery_swap"]):
        return "battery_swap"
    if _contains_any(text, _THEME_ALIASES["real_estate_demand"]):
        return "real_estate_demand"
    return "unknown"


def _theme_aliases(theme_key: str) -> tuple[str, ...]:
    return _THEME_ALIASES.get(theme_key, ())


def _is_real_estate_central_policy_domain(domain: str | None) -> bool:
    if not domain:
        return False
    normalized = domain.strip().lower()
    return any(
        normalized == central_domain or normalized.endswith(f".{central_domain}")
        for central_domain in _REAL_ESTATE_CENTRAL_POLICY_DOMAINS
    )


def _collect_negative_terms(task: QueryDecompositionTask, theme_key: str) -> tuple[str, ...]:
    if task.negative_terms:
        return tuple(term.lower() for term in task.negative_terms if term.strip())
    return _NEGATIVE_TERMS_BY_THEME.get(theme_key, ())


def _is_generic_navigation_index_candidate(
    *,
    url: str,
    title: str | None,
    snippet: str | None,
) -> bool:
    lowered_url = url.lower()
    if not any(
        lowered_url.endswith(marker) or marker in lowered_url
        for marker in _GENERIC_NAVIGATION_PATHS
    ):
        return False
    text = f"{title or ''} {snippet or ''} {url}".lower()
    return any(token.lower() in text for token in _GENERIC_NAVIGATION_TOKENS)


def _candidate_text_blob(*, url: str, title: str | None, snippet: str | None) -> str:
    return f"{url} {title or ''} {snippet or ''}".lower()


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(token.lower() in lowered for token in tokens)


def is_supplemental_or_fallback_task_family(task_family: str) -> bool:
    return task_family.strip().lower() in _ROUND3_SUPPLEMENTAL_OR_FALLBACK_TASK_FAMILIES


__all__ = [
    "CandidateCompatibilityDecision",
    "SUPPLEMENTAL_DOMAINS",
    "evaluate_candidate_compatibility",
    "is_supplemental_or_fallback_task_family",
]


