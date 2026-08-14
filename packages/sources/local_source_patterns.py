from __future__ import annotations

import re
from typing import Any, Literal

LocalSourceClass = Literal[
    "local_government",
    "statistics",
    "energy_constraint_data",
    "trade_data",
    "project_public_resource",
    "environmental_or_land_record",
    "fiscal_local_government",
]

LocalEvidenceBackbone = Literal[
    "local_government",
    "project_public_resource",
    "statistics_fiscal",
    "environmental_land_record",
]

LocalRegionMatchType = Literal[
    "exact_local",
    "child_local",
    "parent_local",
    "unrelated_region",
    "unknown",
]

# ── ADR 0002: Unified source_family taxonomy ──
# Canonical 16-value source_family (research-taxonomy refactor Phase 1). All
# producers should normalize raw/legacy family strings through
# canonical_source_family() so read sites see a regular value. The old 8-value
# families are folded to their new equivalents (official_policy->policy_document,
# official_news->local_official, public_resource_transaction->tender_procurement,
# statistics->official_statistics); environmental_land is retained for backward
# compatibility. family maps both to source_role (credibility) and to
# LocalEvidenceBackbone (local targeting).
CanonicalSourceFamily = Literal[
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
    "environmental_land",
]

# Legacy / synonym string -> canonical family.
_FAMILY_ALIAS_TO_CANONICAL: dict[str, str] = {
    # policy_document (was official_policy)
    "official_policy": "policy_document",
    "provincial_policy": "policy_document",
    "policy": "policy_document",
    "financial_subsidy_notice": "policy_document",
    "policy_document": "policy_document",
    "policy_basis": "policy_document",
    # local_official (was official_news / local_government)
    "official_news": "local_official",
    "official_news_or_interpretation": "local_official",
    "local_government": "local_official",
    "local_government_notice": "local_official",
    "local_official": "local_official",
    # tender_procurement (was public_resource_transaction)
    "public_resource_transaction": "tender_procurement",
    "project_public_resource": "tender_procurement",
    "project_transaction": "tender_procurement",
    "project_list": "tender_procurement",
    "project_execution": "tender_procurement",
    "local_project_tender": "tender_procurement",
    "tender_or_procurement": "tender_procurement",
    "procurement": "tender_procurement",
    "tender_procurement": "tender_procurement",
    # exchange_disclosure (new)
    "exchange_disclosure": "exchange_disclosure",
    "exchange_announcement": "exchange_disclosure",
    "exchange_filing": "exchange_disclosure",
    # company_disclosure
    "company_disclosure": "company_disclosure",
    "disclosure": "company_disclosure",
    # company_material (new)
    "company_material": "company_material",
    "company_website": "company_material",
    "company_brochure": "company_material",
    # official_statistics (was statistics)
    "statistics": "official_statistics",
    "statistics_or_data": "official_statistics",
    "statistics_or_data_release": "official_statistics",
    "statistics_corroboration": "official_statistics",
    "statistics_fiscal": "official_statistics",
    "industry_data": "official_statistics",
    "trade_data": "official_statistics",
    "energy_constraint_data": "official_statistics",
    "official_statistics": "official_statistics",
    "statistical_bulletin": "official_statistics",
    # certification_database (new)
    "certification_database": "certification_database",
    "certification": "certification_database",
    "airworthiness_certification": "certification_database",
    # standard_document (new)
    "standard_document": "standard_document",
    "standard": "standard_document",
    "industry_standard": "standard_document",
    # patent_database (new)
    "patent_database": "patent_database",
    "patent": "patent_database",
    # association_thinktank (new)
    "association_thinktank": "association_thinktank",
    "industry_association": "association_thinktank",
    "thinktank": "association_thinktank",
    # broker_research (new)
    "broker_research": "broker_research",
    "broker_report": "broker_research",
    "sell_side_research": "broker_research",
    # industry_research
    "industry_research": "industry_research",
    "industry_association_context": "industry_research",
    "industry_report": "industry_research",
    "industry_topic": "industry_research",
    "research_or_think_tank_context": "industry_research",
    # commercial_media
    "commercial_media": "commercial_media",
    "commercial_media_context": "commercial_media",
    "media": "commercial_media",
    "aggregator": "commercial_media",
    "aggregator_or_unknown": "commercial_media",
    # operator_data (new)
    "operator_data": "operator_data",
    "operator_platform": "operator_data",
    "operations_data": "operator_data",
    # environmental_land (retained)
    "environmental_land": "environmental_land",
    "environmental_land_record": "environmental_land",
    "environmental_or_land_record": "environmental_land",
    "environmental_record": "environmental_land",
}

_FAMILY_TO_BACKBONE: dict[str, str | None] = {
    "policy_document": "local_government",
    "local_official": "local_government",
    "official_statistics": "statistics_fiscal",
    "tender_procurement": "project_public_resource",
    "exchange_disclosure": None,
    "company_disclosure": None,
    "company_material": None,
    "certification_database": None,
    "standard_document": None,
    "patent_database": None,
    "association_thinktank": None,
    "broker_research": None,
    "industry_research": None,
    "commercial_media": None,
    "operator_data": None,
    "environmental_land": "environmental_land_record",
}

_FAMILY_TO_ROLE: dict[str, str] = {
    "policy_document": "official_policy_original",
    "local_official": "official_news_or_interpretation",
    "official_statistics": "statistics_or_data_release",
    "tender_procurement": "public_resource_transaction",
    "exchange_disclosure": "exchange_disclosure",
    "company_disclosure": "company_disclosure",
    "company_material": "company_material",
    "certification_database": "certification_database",
    "standard_document": "standard_document",
    "patent_database": "patent_database",
    "association_thinktank": "industry_association_context",
    "broker_research": "broker_research",
    "industry_research": "industry_association_context",
    "commercial_media": "commercial_media_context",
    "operator_data": "operator_data",
    "environmental_land": "statistics_or_data_release",
}

_DEFAULT_CANONICAL_FAMILY = "local_official"


def canonical_source_family(raw: str | None) -> str:
    """ADR 0002: normalize a raw/legacy source_family string to one of the 16
    canonical values. Unknown/empty falls back to a conservative default."""
    if not raw:
        return _DEFAULT_CANONICAL_FAMILY
    key = str(raw).strip().lower()
    if key in _FAMILY_ALIAS_TO_CANONICAL:
        return _FAMILY_ALIAS_TO_CANONICAL[key]
    return _DEFAULT_CANONICAL_FAMILY


def family_to_backbone(family: str | None) -> str | None:
    """Map a (canonical or legacy) family to its LocalEvidenceBackbone, or None
    when the family has no local-targeting backbone (disclosure/research/media)."""
    return _FAMILY_TO_BACKBONE.get(canonical_source_family(family))


def family_to_role(family: str | None) -> str:
    """Map a (canonical or legacy) family to its source_role."""
    return _FAMILY_TO_ROLE.get(canonical_source_family(family), "aggregator_or_unknown")


_GENERIC_LOCAL_REGION_STOP_TERMS = {
    "\u4e0a\u5e02",
    "\u57ce\u5e02",
    "\u53bf\u57df",
    "\u5730\u533a",
    "\u56ed\u533a",
    "\u5f00\u53d1\u533a",
    "\u4ea7\u4e1a\u56ed\u533a",
    "\u9ad8\u65b0\u533a",
    "\u81ea\u8d38\u533a",
}
_GENERIC_LOCAL_REGION_BLOCKED_FRAGMENTS = (
    "\u5730\u65b9",
    "\u5e02\u573a",
    "\u533a\u5206",
    "\u653f\u7b56",
    "\u8d44\u91d1",
)
_GENERIC_LOCAL_REGION_BLOCKED_PREFIXES = (
    "\u8bf7",
    "\u662f\u5426",
    "\u80fd\u5426",
)
_GENERIC_LOCAL_REGION_BLOCKED_CANONICAL_SUFFIXES = (
    "\u548c",
    "\u4e0e",
    "\u53ca",
    "\u6216",
)
_GENERIC_LOCAL_REGION_SUFFIXES = ("\u5e02", "\u53bf", "\u533a", "\u65d7")

_BACKBONE_TO_LOCAL_SOURCE_CLASSES: dict[
    LocalEvidenceBackbone,
    tuple[LocalSourceClass, ...],
] = {
    "local_government": ("local_government",),
    "project_public_resource": ("project_public_resource",),
    "statistics_fiscal": ("statistics", "energy_constraint_data", "trade_data"),
    "environmental_land_record": ("environmental_or_land_record",),
}

_SOURCE_CLASS_TO_BACKBONE: dict[str, LocalEvidenceBackbone] = {
    "local_government": "local_government",
    "official_policy": "local_government",
    "provincial_policy": "local_government",
    "financial_subsidy_notice": "local_government",
    "project_list": "project_public_resource",
    "project_transaction": "project_public_resource",
    "local_project_tender": "project_public_resource",
    "tender_or_procurement": "project_public_resource",
    "procurement": "project_public_resource",
    "statistics": "statistics_fiscal",
    "trade_data": "statistics_fiscal",
    "energy_constraint_data": "statistics_fiscal",
    "industry_report": "statistics_fiscal",
    "market_price_data": "statistics_fiscal",
    "environmental_or_land_record": "environmental_land_record",
    "environmental_record": "environmental_land_record",
    "official_record": "environmental_land_record",
    "regulatory_record": "environmental_land_record",
    "land_record": "environmental_land_record",
}

_PARENT_REGION_BY_LOCAL: dict[str, str] = {
    "深圳": "广东",
    "苏州": "江苏",
    "常州": "江苏",
    "合肥": "安徽",
    "肥西": "合肥",
    "西安": "陕西",
    "神木": "陕西",
    "若羌": "新疆",
    "成都": "四川",
    "武汉": "湖北",
    "杭州": "浙江",
    "上海": "上海",
}

_KNOWN_CHILD_REGION_ALIASES_BY_PARENT: dict[str, tuple[str, ...]] = {
    "\u5408\u80a5": (
        "\u957f\u4e30",
        "\u80a5\u4e1c",
        "\u5e90\u6c5f",
        "\u5de2\u6e56",
        "\u5305\u6cb3",
        "\u8700\u5c71",
        "\u5e90\u9633",
        "\u7476\u6d77",
        "\u80a5\u897f",
    ),
    "\u9655\u897f": ("\u795e\u6728",),
}

_LOCAL_SOURCE_DOMAINS: dict[str, dict[LocalSourceClass, tuple[str, ...]]] = {
    "安徽": {
        "local_government": ("ah.gov.cn", "fzggw.ah.gov.cn", "jx.ah.gov.cn"),
        "statistics": ("tjj.ah.gov.cn",),
        "project_public_resource": ("ggzy.ah.gov.cn", "fzggw.ah.gov.cn"),
        "environmental_or_land_record": ("sthjt.ah.gov.cn", "zrzyt.ah.gov.cn"),
        "fiscal_local_government": ("czt.ah.gov.cn", "ah.gov.cn"),
    },
    "合肥": {
        "local_government": ("hefei.gov.cn", "fgw.hefei.gov.cn", "gxj.hefei.gov.cn"),
        "statistics": ("tjj.hefei.gov.cn",),
        "project_public_resource": ("ggzy.hefei.gov.cn", "fgw.hefei.gov.cn"),
        "environmental_or_land_record": ("sthjj.hefei.gov.cn", "zrzy.hefei.gov.cn"),
        "fiscal_local_government": ("czj.hefei.gov.cn", "hefei.gov.cn"),
    },
    "肥西": {
        "local_government": ("ahfeixi.gov.cn",),
        "statistics": ("ahfeixi.gov.cn",),
        "project_public_resource": ("ahfeixi.gov.cn",),
        "environmental_or_land_record": ("ahfeixi.gov.cn",),
        "fiscal_local_government": ("ahfeixi.gov.cn",),
    },
    "广东": {
        "local_government": ("gd.gov.cn", "drc.gd.gov.cn", "gdii.gd.gov.cn"),
        "statistics": ("stats.gd.gov.cn",),
        "project_public_resource": ("gdggzy.org.cn", "drc.gd.gov.cn"),
        "environmental_or_land_record": ("gdee.gd.gov.cn", "nr.gd.gov.cn"),
        "fiscal_local_government": ("czt.gd.gov.cn", "gd.gov.cn"),
    },
    "深圳": {
        "local_government": ("sz.gov.cn", "gxj.sz.gov.cn"),
        "statistics": ("tjj.sz.gov.cn",),
        "project_public_resource": ("szggzy.com", "sz.gov.cn"),
        "environmental_or_land_record": ("meeb.sz.gov.cn", "pnr.sz.gov.cn"),
        "fiscal_local_government": ("czj.sz.gov.cn", "sz.gov.cn"),
    },
    "江苏": {
        "local_government": ("jiangsu.gov.cn", "fzggw.jiangsu.gov.cn", "gxt.jiangsu.gov.cn"),
        "statistics": ("tj.jiangsu.gov.cn",),
        "project_public_resource": ("jsggzy.jszwfw.gov.cn", "fzggw.jiangsu.gov.cn"),
        "environmental_or_land_record": ("sthjt.jiangsu.gov.cn", "zrzy.jiangsu.gov.cn"),
        "fiscal_local_government": ("czt.jiangsu.gov.cn", "jiangsu.gov.cn"),
    },
    "苏州": {
        "local_government": ("suzhou.gov.cn", "fgw.suzhou.gov.cn"),
        "statistics": ("tjj.suzhou.gov.cn",),
        "project_public_resource": ("szzyjy.com.cn", "suzhou.gov.cn"),
        "environmental_or_land_record": ("sthjj.suzhou.gov.cn", "zrzy.jiangsu.gov.cn"),
        "fiscal_local_government": ("czju.suzhou.gov.cn", "suzhou.gov.cn"),
    },
    "常州": {
        "local_government": ("changzhou.gov.cn", "fgw.changzhou.gov.cn", "gxj.changzhou.gov.cn"),
        "statistics": ("tjj.changzhou.gov.cn",),
        "project_public_resource": ("ggzy.xzsp.changzhou.gov.cn", "changzhou.gov.cn"),
        "environmental_or_land_record": ("sthjj.changzhou.gov.cn", "zrzy.jiangsu.gov.cn"),
        "fiscal_local_government": ("czj.changzhou.gov.cn", "changzhou.gov.cn"),
    },
    "陕西": {
        "local_government": ("shaanxi.gov.cn", "sndrc.shaanxi.gov.cn", "kjt.shaanxi.gov.cn"),
        "statistics": ("tjj.shaanxi.gov.cn",),
        "project_public_resource": ("sxggzyjy.cn", "sndrc.shaanxi.gov.cn"),
        "environmental_or_land_record": ("sthjt.shaanxi.gov.cn", "zrzyt.shaanxi.gov.cn"),
        "fiscal_local_government": ("czt.shaanxi.gov.cn", "shaanxi.gov.cn"),
    },
    "西安": {
        "local_government": (
            "xa.gov.cn",
            "xadrc.xa.gov.cn",
            "xakj.xa.gov.cn",
            "xcaib.xa.gov.cn",
        ),
        "statistics": ("tjj.xa.gov.cn",),
        "project_public_resource": ("sxggzyjy.cn", "xa.gov.cn", "xcaib.xa.gov.cn"),
        "environmental_or_land_record": ("xaepb.xa.gov.cn", "zygh.xa.gov.cn"),
        "fiscal_local_government": ("xaczj.xa.gov.cn", "xa.gov.cn"),
    },
    "神木": {
        "local_government": ("sxsm.gov.cn",),
        "statistics": ("sxsm.gov.cn",),
        "project_public_resource": ("sxsm.gov.cn", "sxggzyjy.cn"),
        "environmental_or_land_record": ("sxsm.gov.cn",),
        "fiscal_local_government": ("sxsm.gov.cn",),
    },
    "新疆": {
        "local_government": ("xinjiang.gov.cn",),
        "statistics": ("tjj.xinjiang.gov.cn",),
        "project_public_resource": ("ggzy.xinjiang.gov.cn",),
        "environmental_or_land_record": ("sthjt.xinjiang.gov.cn", "zrzyt.xinjiang.gov.cn"),
        "fiscal_local_government": ("czt.xinjiang.gov.cn", "xinjiang.gov.cn"),
    },
    "若羌": {
        "local_government": ("xjrq.gov.cn", "xjbz.gov.cn"),
        "statistics": ("xjrq.gov.cn", "xjbz.gov.cn"),
        "project_public_resource": ("xjrq.gov.cn", "xjbz.gov.cn"),
        "environmental_or_land_record": ("xjrq.gov.cn", "xjbz.gov.cn"),
        "fiscal_local_government": ("xjrq.gov.cn", "xjbz.gov.cn"),
    },
    "内蒙古": {
        "local_government": ("nmg.gov.cn", "fgw.nmg.gov.cn", "gxt.nmg.gov.cn"),
        "statistics": ("tj.nmg.gov.cn",),
        "energy_constraint_data": ("nyj.nmg.gov.cn", "fgw.nmg.gov.cn"),
        "project_public_resource": ("ggzyjy.nmg.gov.cn", "fgw.nmg.gov.cn"),
        "environmental_or_land_record": ("sthjt.nmg.gov.cn", "zrzy.nmg.gov.cn"),
        "fiscal_local_government": ("czt.nmg.gov.cn", "nmg.gov.cn"),
    },
    "海南": {
        "local_government": ("hainan.gov.cn", "plan.hainan.gov.cn", "iithainan.gov.cn"),
        "statistics": ("stats.hainan.gov.cn",),
        "project_public_resource": ("zw.hainan.gov.cn", "hainan.gov.cn"),
        "environmental_or_land_record": ("hnsthb.hainan.gov.cn", "lr.hainan.gov.cn"),
        "fiscal_local_government": ("mof.hainan.gov.cn", "hainan.gov.cn"),
    },
}


def local_source_domains_for_regions(
    regions: list[str],
    source_class: LocalSourceClass,
    *,
    include_parent: bool = True,
    include_fiscal: bool = False,
) -> list[str]:
    domains: list[str] = []
    for region in regions:
        for resolved_region in _resolve_region_chain(region, include_parent=include_parent):
            domains.extend(_LOCAL_SOURCE_DOMAINS.get(resolved_region, {}).get(source_class, ()))
            if include_fiscal:
                domains.extend(
                    _LOCAL_SOURCE_DOMAINS.get(resolved_region, {}).get(
                        "fiscal_local_government",
                        (),
                    )
                )
    return _dedupe(domains)


def generic_local_region_terms(text: str) -> list[str]:
    terms: list[str] = []
    for match in re.finditer(
        r"([\u4e00-\u9fff]{1,8}?[\u5e02\u53bf\u533a\u65d7])",
        text,
    ):
        candidate = _trim_generic_region_candidate(match.group(1).strip())
        if not candidate or _is_generic_local_region_stop_term(candidate):
            continue
        canonical = _canonical_region_term(candidate)
        if len(canonical) < 2:
            continue
        if _is_generic_local_region_stop_term(canonical):
            continue
        if canonical in _all_known_regions():
            continue
        if canonical not in terms:
            terms.append(canonical)
    return terms


def is_generic_exact_local_region(region: str) -> bool:
    canonical = _canonical_region_term(region)
    if not canonical or canonical == "\u5168\u56fd":
        return False
    return canonical not in _all_known_regions()


def local_evidence_backbone_for_source_class(
    source_class: str,
) -> LocalEvidenceBackbone | None:
    normalized = source_class.strip().lower()
    if not normalized:
        return None
    if normalized in _SOURCE_CLASS_TO_BACKBONE:
        return _SOURCE_CLASS_TO_BACKBONE[normalized]
    for source_class_key, backbone in _SOURCE_CLASS_TO_BACKBONE.items():
        if source_class_key in normalized:
            return backbone
    return None


def local_source_domains_for_backbones(
    regions: list[str],
    backbones: list[LocalEvidenceBackbone],
    *,
    include_parent: bool = True,
    include_fiscal: bool = False,
) -> list[str]:
    domains: list[str] = []
    for backbone in backbones:
        source_classes = list(_BACKBONE_TO_LOCAL_SOURCE_CLASSES.get(backbone, ()))
        if include_fiscal and backbone in {"local_government", "statistics_fiscal"}:
            source_classes.append("fiscal_local_government")
        for source_class in source_classes:
            domains.extend(
                local_source_domains_for_regions(
                    regions,
                    source_class,
                    include_parent=include_parent,
                    include_fiscal=False,
                )
            )
    return _dedupe(domains)


def local_source_region_for_domain(domain: str) -> str | None:
    normalized = domain.strip().lower()
    if not normalized:
        return None
    for region, domain_groups in _LOCAL_SOURCE_DOMAINS.items():
        for domains in domain_groups.values():
            for candidate in domains:
                if normalized == candidate or normalized.endswith(f".{candidate}"):
                    return region
    return None


def local_source_domain_region_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for region, domain_groups in _LOCAL_SOURCE_DOMAINS.items():
        for domains in domain_groups.values():
            for domain in domains:
                mapping.setdefault(domain, region)
    return mapping


def classify_local_region_match(
    expected_regions: list[str],
    candidate_text: str,
    *,
    candidate_domain: str | None = None,
) -> dict[str, Any]:
    normalized_expected = [
        _canonical_region_term(region)
        for region in expected_regions
        if _canonical_region_term(region)
    ]
    if not normalized_expected:
        return _local_region_match_payload("unknown", normalized_expected)

    normalized_text = candidate_text.strip().lower()
    domain_region = local_source_region_for_domain(candidate_domain or "")
    evidence_regions: list[str] = []
    if domain_region:
        evidence_regions.append(domain_region)
    for region in _all_known_regions():
        if _region_in_text(region, normalized_text):
            evidence_regions.append(region)
    evidence_regions = _dedupe_region_terms(evidence_regions)

    for expected_region in normalized_expected:
        if _region_matches(expected_region, normalized_text, evidence_regions) and not (
            domain_region and _is_broader_domain_region(domain_region, expected_region)
        ):
            return _local_region_match_payload(
                "exact_local",
                normalized_expected,
                expected_region=expected_region,
                matched_region=expected_region,
                candidate_domain_region=domain_region,
            )

    for expected_region in normalized_expected:
        if (
            domain_region
            and _is_broader_domain_region(domain_region, expected_region)
            and _region_matches(expected_region, normalized_text, evidence_regions)
        ):
            return _local_region_match_payload(
                "parent_local",
                normalized_expected,
                expected_region=expected_region,
                matched_region=domain_region,
                candidate_domain_region=domain_region,
            )

    for expected_region in normalized_expected:
        for child_region in _child_regions_for_parent(expected_region):
            if _region_matches(child_region, normalized_text, evidence_regions):
                return _local_region_match_payload(
                    "child_local",
                    normalized_expected,
                    expected_region=expected_region,
                    matched_region=child_region,
                    candidate_domain_region=domain_region,
                )

    for expected_region in normalized_expected:
        for parent_region in _resolve_region_chain(expected_region, include_parent=True)[1:]:
            if _region_matches(parent_region, normalized_text, evidence_regions):
                return _local_region_match_payload(
                    "parent_local",
                    normalized_expected,
                    expected_region=expected_region,
                    matched_region=parent_region,
                    candidate_domain_region=domain_region,
                )

    if evidence_regions:
        return _local_region_match_payload(
            "unrelated_region",
            normalized_expected,
            matched_region=evidence_regions[0],
            candidate_domain_region=domain_region,
        )
    return _local_region_match_payload(
        "unknown",
        normalized_expected,
        candidate_domain_region=domain_region,
    )


def all_local_source_pattern_domains() -> list[str]:
    domains: list[str] = []
    for domain_groups in _LOCAL_SOURCE_DOMAINS.values():
        for group_domains in domain_groups.values():
            domains.extend(group_domains)
    return _dedupe(domains)


def _resolve_region_chain(region: str, *, include_parent: bool) -> list[str]:
    chain = [region]
    if not include_parent:
        return chain
    current = region
    seen = {region}
    while True:
        parent = _PARENT_REGION_BY_LOCAL.get(current)
        if not parent or parent in seen:
            break
        chain.append(parent)
        seen.add(parent)
        current = parent
    return chain


def _is_parent_region(candidate_parent: str, child_region: str) -> bool:
    return candidate_parent in _resolve_region_chain(child_region, include_parent=True)[1:]


def _is_broader_domain_region(candidate_domain_region: str, expected_region: str) -> bool:
    if not candidate_domain_region or candidate_domain_region == expected_region:
        return False
    if _is_parent_region(candidate_domain_region, expected_region):
        return True
    if expected_region in _child_regions_for_parent(candidate_domain_region):
        return True
    return is_generic_exact_local_region(expected_region) and (
        candidate_domain_region in _all_known_regions()
    )


def _local_region_match_payload(
    match_type: LocalRegionMatchType,
    expected_regions: list[str],
    *,
    expected_region: str | None = None,
    matched_region: str | None = None,
    candidate_domain_region: str | None = None,
) -> dict[str, Any]:
    return {
        "match_type": match_type,
        "expected_regions": expected_regions,
        "expected_region": expected_region,
        "matched_region": matched_region,
        "candidate_domain_region": candidate_domain_region,
    }


def _canonical_region_term(region: str) -> str:
    normalized = region.strip()
    administrative_suffixes = (
        "\u7701",
        "\u5e02",
        "\u53bf",
        "\u533a",
        "\u65d7",
    )
    if len(normalized) > 2 and normalized.endswith(administrative_suffixes):
        return normalized[:-1]
    return normalized


def _is_generic_local_region_stop_term(candidate: str) -> bool:
    if candidate in _GENERIC_LOCAL_REGION_STOP_TERMS:
        return True
    if any(fragment in candidate for fragment in _GENERIC_LOCAL_REGION_BLOCKED_FRAGMENTS):
        return True
    if any(candidate.startswith(prefix) for prefix in _GENERIC_LOCAL_REGION_BLOCKED_PREFIXES):
        return True
    if any(
        candidate.endswith(suffix)
        for suffix in _GENERIC_LOCAL_REGION_BLOCKED_CANONICAL_SUFFIXES
    ):
        return True
    return any(candidate.endswith(stop) for stop in _GENERIC_LOCAL_REGION_STOP_TERMS)


def _trim_generic_region_candidate(candidate: str) -> str:
    for separator in (
        "\u3001",
        "\uff0c",
        ",",
        ";",
        "\uff1b",
        "\u548c",
        "\u4e0e",
        "\u53ca",
        "\u6216",
    ):
        if separator in candidate:
            candidate = candidate.rsplit(separator, 1)[-1].strip()
    return candidate


def _child_regions_for_parent(parent_region: str) -> list[str]:
    children: list[str] = list(_KNOWN_CHILD_REGION_ALIASES_BY_PARENT.get(parent_region, ()))
    children.extend(
        local_region
        for local_region, known_parent in _PARENT_REGION_BY_LOCAL.items()
        if known_parent == parent_region
    )
    return _dedupe_region_terms(children)


def _all_known_regions() -> list[str]:
    regions: list[str] = []
    regions.extend(_LOCAL_SOURCE_DOMAINS.keys())
    regions.extend(_PARENT_REGION_BY_LOCAL.keys())
    regions.extend(_PARENT_REGION_BY_LOCAL.values())
    for parent_region, child_regions in _KNOWN_CHILD_REGION_ALIASES_BY_PARENT.items():
        regions.append(parent_region)
        regions.extend(child_regions)
    return _dedupe_region_terms(regions)


def _region_matches(region: str, text: str, evidence_regions: list[str]) -> bool:
    return region in evidence_regions or _region_in_text(region, text)


def _region_in_text(region: str, text: str) -> bool:
    return any(alias.lower() in text for alias in _region_aliases(region))


def _region_aliases(region: str) -> tuple[str, ...]:
    canonical = _canonical_region_term(region)
    aliases = [
        canonical,
        f"{canonical}\u7701",
        f"{canonical}\u5e02",
        f"{canonical}\u53bf",
        f"{canonical}\u533a",
        f"{canonical}\u65d7",
    ]
    return tuple(_dedupe_region_terms(aliases))


def _dedupe_region_terms(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        normalized = _canonical_region_term(value)
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        normalized = value.strip().lower()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped
