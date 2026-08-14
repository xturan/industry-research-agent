from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from urllib.parse import urlparse

_CENTRAL_OFFICIAL_DOMAINS = {
    "www.gov.cn",
    "gov.cn",
    "ndrc.gov.cn",
    "miit.gov.cn",
    "most.gov.cn",
    "mofcom.gov.cn",
    "stats.gov.cn",
    "customs.gov.cn",
    "samr.gov.cn",
    "mof.gov.cn",
}
_PUBLIC_RESOURCE_MARKERS = ("ggzy", "ccgp", "zfcg", "ggzyjy", "cebpubservice")
_DISCLOSURE_DOMAINS = {"cninfo.com.cn", "sse.com.cn", "szse.cn", "hkexnews.hk"}
_ASSOCIATION_MARKERS = (
    "caam.org.cn",
    "caai.cn",
    "chinapv.org.cn",
    "aopa.org.cn",
    "cansi.org.cn",
)
_THINK_TANK_MARKERS = ("cass.cn", "sic.gov.cn", "ccid", "research", "thinktank")
_COMMERCIAL_MARKERS = (
    "163.com",
    "sohu.com",
    "sina.com.cn",
    "qq.com",
    "ifeng.com",
    "eastmoney.com",
    "10jqka.com.cn",
    "baijiahao.baidu.com",
)
# 权威媒体/央媒（news.cn 新华网、people.com.cn 人民网等）：可信但不是 gov.cn 官方，
# 归 official_news_or_interpretation 而非 aggregator_or_unknown（避免低质聚合误判）。
_AUTHORITATIVE_MEDIA_MARKERS = (
    "news.cn",
    "xinhuanet.com",
    "people.com.cn",
    "cctv.com",
    "gmw.cn",
    "ce.cn",
    "chinanews.com.cn",
)
_POLICY_TERMS = (
    "policy",
    "notice",
    "regulation",
    "规划",
    "政策",
    "通知",
    "意见",
    "办法",
    "方案",
    "措施",
    "行动计划",
    "实施细则",
)
_PROCUREMENT_TERMS = (
    "招标",
    "中标",
    "采购",
    "成交",
    "交易",
    "公共资源",
    "tender",
    "procurement",
    "bid",
)
_STATISTICS_TERMS = (
    "统计",
    "公报",
    "数据",
    "年鉴",
    "运行情况",
    "statistic",
    "statistics",
    "data",
)
_DISCLOSURE_TERMS = ("公告", "年报", "半年报", "季报", "披露", "disclosure", "annual report")
_REGULATORY_TERMS = ("监管", "处罚", "许可", "备案", "审批", "环评", "用地", "regulatory")
_NEWS_PATH_MARKERS = ("/xwzx/", "/zwdt/", "/mtjj/", "/xwfb/", "/news/")
_FORMAL_URL_MARKERS = (
    "/zwgk/",
    "/zfxxgk/",
    "/xxgk/",
    "/gkmlpt/",
    "/content/",
    "/post_",
    "/public/",
    "/detail/",
    "/tzgg/",
)
_DOC_NUMBER_RE = re.compile(
    r"(?:[A-Za-z]{1,8}\[\d{4}\]\d+|[\u4e00-\u9fff]{1,12}[〔\[]\d{4}[〕\]]\d+号)"
)
_FULL_DATE_PATTERNS = (
    re.compile(r"(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])"),
    re.compile(r"(20\d{2})年(0?[1-9]|1[0-2])月(0?[1-9]|[12]\d|3[01])日"),
)
_COMPACT_DATE_RE = re.compile(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])([0-2]\d|3[01])(?!\d)")
_YEAR_RE = re.compile(r"(?<!\d)(20[0-3]\d)(?!\d)")


@dataclass(frozen=True)
class FreshnessAssessment:
    score: float
    label: str
    publication_date: str | None
    date_source: str
    age_days: int | None
    validity_status: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class QueryRelevanceAssessment:
    score: float
    label: str
    signals: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SourceQualityV2:
    """精简后的 source 质量分：credibility_score 为唯一综合分，tier 由其派生。

    移除的冗余字段：publisher_authority / auditability（折叠进 credibility 权重）、
    credibility_label（= credibility_label() 直接可算）、reason（仅调试用字符串）。
    子对象 freshness/query_relevance 保留完整字段（下游 agents/retrieval_bridge 消费）。
    """

    tier: str
    source_role: str
    freshness: FreshnessAssessment
    query_relevance: QueryRelevanceAssessment
    credibility_score: float
    usage_role: str
    not_sufficient_for: list[str]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["freshness"] = self.freshness.to_dict()
        data["query_relevance"] = self.query_relevance.to_dict()
        return data


def _tier_from_credibility(score: float) -> str:
    """从 credibility_score 派生 tier（≥0.72=A, ≥0.55=B, ≥0.35=C, else D）。

    修复原实现 tier 是计划常量回灌（expected_source_tier 原样输出，D 档永不出现）；
    现在 tier 是 credibility 的派生标签，低分源自然产生 C/D。
    """
    if score >= 0.72:
        return "A"
    if score >= 0.55:
        return "B"
    if score >= 0.35:
        return "C"
    return "D"


def assess_source_quality_v2(
    *,
    query: str,
    domain: str,
    url: str,
    title: str,
    snippet: str = "",
    extracted_text: str = "",
    source_family: str | None = None,
    published_date: str | None = None,
    discovered_by_phrase: str | None = None,
    expanded_terms: list[str] | None = None,
    as_of_date: date | None = None,
) -> SourceQualityV2:
    """评分单个 source。tier 不再作为输入（它是计划期望值，非测量值）；
    credibility_score 是唯一综合分，tier 由其派生，避免计划 tier 通胀评分。"""
    normalized_domain = _normalize_domain(domain, url)
    source_role = classify_source_role(
        normalized_domain,
        url,
        title,
        source_family=source_family,
    )
    # publisher_authority / auditability 折叠进 credibility 权重（不独立暴露）
    publisher_authority = score_publisher_authority(
        normalized_domain,
        source_role,
    )
    auditability = score_auditability(
        normalized_domain,
        url,
        title,
        extracted_text=extracted_text,
        published_date=published_date,
        source_role=source_role,
    )
    freshness = score_freshness(
        title=title,
        url=url,
        published_date=published_date,
        extracted_text=extracted_text,
        source_role=source_role,
        query=query,
        as_of_date=as_of_date,
    )
    query_relevance = score_query_relevance(
        query=query,
        expanded_terms=expanded_terms or [],
        discovered_by_phrase=discovered_by_phrase or "",
        title=title,
        snippet=snippet,
        extracted_text=extracted_text,
        source_role=source_role,
    )
    credibility_score = _score_credibility(
        source_role=source_role,
        publisher_authority=publisher_authority,
        auditability=auditability,
        freshness=freshness,
        query_relevance=query_relevance,
    )
    usage_role = derive_usage_role(
        source_role=source_role,
        auditability=auditability,
        freshness=freshness,
        query_relevance=query_relevance,
        credibility_score=credibility_score,
    )
    not_sufficient_for = _not_sufficient_for(source_role, freshness)
    return SourceQualityV2(
        tier=_tier_from_credibility(credibility_score),
        source_role=source_role,
        freshness=freshness,
        query_relevance=query_relevance,
        credibility_score=credibility_score,
        usage_role=usage_role,
        not_sufficient_for=not_sufficient_for,
    )


def classify_source_role(
    domain: str,
    url: str,
    title: str,
    *,
    source_family: str | None = None,
) -> str:
    text = f"{url} {title} {source_family or ''}".lower()
    domain = domain.lower()
    source_family_text = (source_family or "").lower()

    if source_family_text:
        if "procurement" in source_family_text or "tender" in source_family_text:
            return "public_resource_transaction"
        if "statistics" in source_family_text or "data" in source_family_text:
            return "statistics_or_data_release"
        if "disclosure" in source_family_text:
            return "company_disclosure"
        if "regulatory" in source_family_text:
            return "official_notice_or_rule"

    if any(marker in domain for marker in _PUBLIC_RESOURCE_MARKERS):
        return "public_resource_transaction"
    if domain in _DISCLOSURE_DOMAINS or any(
        domain.endswith(f".{d}") for d in _DISCLOSURE_DOMAINS
    ):
        return "company_disclosure"
    officialish_domain = domain.endswith(".gov.cn") or domain in _CENTRAL_OFFICIAL_DOMAINS
    if "stats.gov.cn" in domain or "customs.gov.cn" in domain or (
        officialish_domain and _contains_any(text, _STATISTICS_TERMS)
    ):
        return "statistics_or_data_release"
    if domain.endswith(".gov.cn") or domain in _CENTRAL_OFFICIAL_DOMAINS:
        if url.lower().endswith(".pdf") or _contains_any(text, _POLICY_TERMS):
            return "official_policy_original"
        if _contains_any(text, _REGULATORY_TERMS):
            return "official_notice_or_rule"
        if any(marker in url.lower() for marker in _NEWS_PATH_MARKERS):
            return "official_news_or_interpretation"
        return "official_notice_or_rule"
    if any(marker in domain for marker in _ASSOCIATION_MARKERS):
        return "industry_association_context"
    if any(marker in domain for marker in _THINK_TANK_MARKERS):
        return "research_or_think_tank_context"
    if any(marker in domain for marker in _AUTHORITATIVE_MEDIA_MARKERS):
        return "official_news_or_interpretation"
    if any(marker in domain for marker in _COMMERCIAL_MARKERS):
        return "commercial_media_context"
    return "aggregator_or_unknown"


def score_publisher_authority(domain: str, source_role: str) -> float:
    if domain in _CENTRAL_OFFICIAL_DOMAINS or any(
        domain.endswith(f".{d}") for d in _CENTRAL_OFFICIAL_DOMAINS
    ):
        score = 0.98
    elif domain.endswith(".gov.cn"):
        score = 0.90
    elif source_role == "company_disclosure":
        score = 0.86
    elif source_role == "public_resource_transaction":
        score = 0.82
    elif source_role == "statistics_or_data_release":
        score = 0.88
    elif source_role == "industry_association_context":
        score = 0.58
    elif source_role == "research_or_think_tank_context":
        score = 0.55
    elif source_role == "official_news_or_interpretation":
        score = 0.68
    elif source_role == "commercial_media_context":
        score = 0.38
    else:
        score = 0.30

    return _round_score(score)


def score_auditability(
    domain: str,
    url: str,
    title: str,
    *,
    extracted_text: str = "",
    published_date: str | None = None,
    source_role: str = "aggregator_or_unknown",
) -> float:
    url_lower = url.lower()
    text = f"{title}\n{url}\n{extracted_text[:2000]}"
    score = 0.15

    if url_lower.startswith("https://"):
        score += 0.10
    if domain.endswith(".gov.cn") or source_role in {
        "public_resource_transaction",
        "company_disclosure",
        "statistics_or_data_release",
    }:
        score += 0.25
    if any(marker in url_lower for marker in _FORMAL_URL_MARKERS):
        score += 0.15
    if url_lower.endswith(".pdf") or any(
        suffix in url_lower for suffix in (".doc", ".docx", ".xls", ".xlsx")
    ):
        score += 0.15
    if published_date or _extract_best_date(url, "url") or _extract_best_date(title, "title"):
        score += 0.10
    if _DOC_NUMBER_RE.search(text):
        score += 0.10
    if title.strip():
        score += 0.05

    if source_role in {"commercial_media_context", "aggregator_or_unknown"}:
        score = min(score, 0.62)
    return _round_score(score)


def score_freshness(
    *,
    title: str,
    url: str,
    published_date: str | None,
    extracted_text: str,
    source_role: str,
    query: str = "",
    as_of_date: date | None = None,
) -> FreshnessAssessment:
    as_of_date = as_of_date or date.today()
    source_date, date_source = _select_source_date(
        title=title,
        url=url,
        published_date=published_date,
        extracted_text=extracted_text,
    )
    if source_date is None:
        score = 0.45 if _is_formal_role(source_role) else 0.35
        status = "needs_validity_check" if _is_formal_role(source_role) else "unknown"
        return FreshnessAssessment(
            score=_round_score(score),
            label="unknown_date",
            publication_date=None,
            date_source="unknown",
            age_days=None,
            validity_status=status,
            notes="No reliable publication date found; keep as a source-layer uncertainty.",
        )

    age_days = max((as_of_date - source_date).days, 0)
    query_years = _years_from_text(query)
    query_mentions_recent = _contains_any(
        query.lower(),
        ("最新", "近期", "recent", "current", "2026"),
    )

    if source_role in {"official_policy_original", "official_notice_or_rule"}:
        score, label, status = _freshness_for_policy(age_days)
    elif source_role == "public_resource_transaction":
        score, label, status = _freshness_for_transaction(age_days, query_mentions_recent)
    elif source_role in {"statistics_or_data_release", "company_disclosure"}:
        score, label, status = _freshness_for_periodic_source(age_days)
    else:
        score, label, status = _freshness_for_context_source(age_days, query_mentions_recent)

    if query_years and source_date.year in query_years:
        score = min(score + 0.08, 0.98)
        if label in {"acceptable", "historical"}:
            label = "acceptable"
        status = "matches_query_period"

    return FreshnessAssessment(
        score=_round_score(score),
        label=label,
        publication_date=source_date.isoformat(),
        date_source=date_source,
        age_days=age_days,
        validity_status=status,
        notes=_freshness_notes(source_role, label, date_source),
    )


def score_query_relevance(
    *,
    query: str,
    expanded_terms: list[str],
    discovered_by_phrase: str,
    title: str,
    snippet: str,
    extracted_text: str,
    source_role: str,
) -> QueryRelevanceAssessment:
    title_snippet = f"{title}\n{snippet}".lower()
    body = (extracted_text or "").lower()
    combined = f"{title_snippet}\n{body}"
    terms = _candidate_terms(query, expanded_terms, discovered_by_phrase)

    query_phrase_match = any(term in combined for term in terms)
    title_snippet_match = any(term in title_snippet for term in terms)
    extracted_text_match = bool(body) and any(term in body for term in terms)
    source_family_match = _source_family_matches_query(query, discovered_by_phrase, source_role)
    discovered_phrase_high_intent = _is_high_intent_phrase(discovered_by_phrase)

    score = 0.20
    if query_phrase_match:
        score += 0.20
    if title_snippet_match:
        score += 0.20
    if extracted_text_match:
        score += 0.25
    if source_family_match:
        score += 0.20
    if discovered_phrase_high_intent:
        score += 0.08
    if not source_family_match and _has_specific_family_intent(query, discovered_by_phrase):
        score = min(score, 0.68)
    if not terms and source_role in {
        "official_policy_original",
        "official_notice_or_rule",
        "statistics_or_data_release",
    }:
        score = max(score, 0.42)

    score = _round_score(min(score, 1.0))
    return QueryRelevanceAssessment(
        score=score,
        label=_relevance_label(score),
        signals={
            "query_phrase_match": query_phrase_match,
            "title_snippet_match": title_snippet_match,
            "extracted_text_match": extracted_text_match,
            "source_family_match": source_family_match,
            "discovered_by_phrase": discovered_by_phrase or "",
            "discovered_phrase_high_intent": discovered_phrase_high_intent,
        },
    )


def derive_usage_role(
    *,
    source_role: str,
    auditability: float,
    freshness: FreshnessAssessment,
    query_relevance: QueryRelevanceAssessment,
    credibility_score: float,
) -> str:
    """判定 source 的用途角色。tier 不再参与（它由 credibility_score 派生，直接用
    credibility 阈值判别更直接）。低分源自然降级，不再被计划 tier 抬举。"""
    if credibility_score < 0.35 or auditability < 0.35 or query_relevance.score < 0.30:
        return "exclude_from_primary_evidence"
    if source_role in {"commercial_media_context", "aggregator_or_unknown"}:
        return "context_only"
    if not bool(query_relevance.signals.get("source_family_match", True)):
        if query_relevance.score >= 0.42:
            return "supporting_evidence_candidate"
        return "context_only"
    if freshness.label == "historical" and source_role == "commercial_media_context":
        return "context_only"
    if credibility_score >= 0.72 and query_relevance.score >= 0.55:
        return "primary_evidence_candidate"
    if query_relevance.score >= 0.42:
        return "supporting_evidence_candidate"
    return "context_only"


def _score_credibility(
    *,
    source_role: str,
    publisher_authority: float,
    auditability: float,
    freshness: FreshnessAssessment,
    query_relevance: QueryRelevanceAssessment,
) -> float:
    score = (
        publisher_authority * 0.42
        + auditability * 0.26
        + freshness.score * 0.20
        + query_relevance.score * 0.12
    )
    if auditability < 0.45:
        score = min(score, 0.62)
    if query_relevance.score < 0.35:
        score = min(score, 0.58)
    if freshness.label == "historical" and source_role not in {
        "official_policy_original",
        "official_notice_or_rule",
    }:
        score = min(score, 0.56)
    if source_role in {"commercial_media_context", "aggregator_or_unknown"}:
        score = min(score, 0.48)
    return _round_score(score)


def _select_source_date(
    *,
    title: str,
    url: str,
    published_date: str | None,
    extracted_text: str,
) -> tuple[date | None, str]:
    candidates = [
        (published_date or "", "search_result_published_date"),
        (url, "url_date_or_year"),
        (title, "title_date_or_year"),
        ((extracted_text or "")[:4000], "extracted_text_date_or_year"),
    ]
    for value, source in candidates:
        parsed = _extract_best_date(value, source)
        if parsed is not None:
            return parsed, source
    return None, "unknown"


def _extract_best_date(value: str, source: str) -> date | None:
    if not value:
        return None
    text = str(value)
    parsed = _parse_iso_like_date(text)
    if parsed is not None:
        return parsed
    if source == "url_date_or_year":
        compact = _COMPACT_DATE_RE.search(text)
        if compact:
            return _safe_date(int(compact.group(1)), int(compact.group(2)), int(compact.group(3)))
    years = _years_from_text(text)
    if years:
        return date(max(years), 12, 31)
    return None


def _parse_iso_like_date(value: str) -> date | None:
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for pattern in _FULL_DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            return _safe_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _years_from_text(text: str) -> set[int]:
    return {int(match.group(1)) for match in _YEAR_RE.finditer(text or "")}


def _freshness_for_policy(age_days: int) -> tuple[float, str, str]:
    if age_days <= 730:
        return 0.90, "fresh", "likely_current"
    if age_days <= 1825:
        return 0.74, "acceptable", "likely_current"
    return 0.58, "needs_validity_check", "needs_validity_check"


def _freshness_for_transaction(
    age_days: int,
    query_mentions_recent: bool,
) -> tuple[float, str, str]:
    if age_days <= 365:
        return 0.88, "fresh", "current_or_recent_record"
    if age_days <= 1095 and not query_mentions_recent:
        return 0.56, "historical", "historical_record"
    return 0.36, "historical", "historical_record"


def _freshness_for_periodic_source(age_days: int) -> tuple[float, str, str]:
    if age_days <= 540:
        return 0.86, "fresh", "likely_current"
    if age_days <= 1095:
        return 0.66, "acceptable", "usable_but_not_newest"
    return 0.45, "historical", "historical_record"


def _freshness_for_context_source(
    age_days: int,
    query_mentions_recent: bool,
) -> tuple[float, str, str]:
    if age_days <= 180:
        return 0.80, "fresh", "current_or_recent_context"
    if age_days <= 730 and not query_mentions_recent:
        return 0.55, "acceptable", "usable_context"
    return 0.30, "historical", "historical_context"


def _freshness_notes(source_role: str, label: str, date_source: str) -> str:
    if label == "needs_validity_check":
        return "Formal source is old enough that validity should be checked before strong use."
    if source_role == "public_resource_transaction" and label == "historical":
        return (
            "Transaction/procurement records remain useful for history, "
            "not current opportunity claims."
        )
    if date_source == "search_result_published_date":
        return (
            "Date came from search metadata and should be treated as the first "
            "source-layer signal."
        )
    return "Freshness is inferred from visible source metadata and should be audited if critical."


def _source_family_matches_query(query: str, phrase: str, source_role: str) -> bool:
    intent_text = f"{query} {phrase}".lower()
    if _contains_any(intent_text, _PROCUREMENT_TERMS):
        return source_role == "public_resource_transaction"
    if _contains_any(intent_text, _STATISTICS_TERMS):
        return source_role == "statistics_or_data_release"
    if _contains_any(intent_text, _DISCLOSURE_TERMS):
        return source_role == "company_disclosure"
    if _contains_any(intent_text, _REGULATORY_TERMS):
        return source_role in {"official_notice_or_rule", "official_policy_original"}
    if _contains_any(intent_text, _POLICY_TERMS):
        return source_role in {
            "official_policy_original",
            "official_notice_or_rule",
            "official_news_or_interpretation",
        }
    return source_role not in {"commercial_media_context", "aggregator_or_unknown"}


def _candidate_terms(query: str, expanded_terms: list[str], discovered_by_phrase: str) -> list[str]:
    raw_terms = [query, discovered_by_phrase, *expanded_terms]
    terms: list[str] = []
    for raw in raw_terms:
        text = str(raw or "").strip().lower()
        if not text:
            continue
        terms.append(text)
        for token in re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]{3,}", text):
            terms.append(token)
    deduped: list[str] = []
    for term in terms:
        if term not in deduped and len(term) >= 2:
            deduped.append(term)
    return deduped[:40]


def _is_high_intent_phrase(phrase: str) -> bool:
    return _contains_any(
        phrase.lower(),
        _POLICY_TERMS
        + _PROCUREMENT_TERMS
        + _STATISTICS_TERMS
        + _DISCLOSURE_TERMS
        + _REGULATORY_TERMS,
    )


def _has_specific_family_intent(query: str, phrase: str) -> bool:
    intent_text = f"{query} {phrase}".lower()
    return _contains_any(
        intent_text,
        _PROCUREMENT_TERMS + _STATISTICS_TERMS + _DISCLOSURE_TERMS + _REGULATORY_TERMS,
    )


def _not_sufficient_for(source_role: str, freshness: FreshnessAssessment) -> list[str]:
    if source_role in {
        "official_policy_original",
        "official_notice_or_rule",
        "official_news_or_interpretation",
    }:
        items = [
            "winning bid evidence",
            "company revenue confirmation",
            "production capacity confirmation",
        ]
        if freshness.label == "needs_validity_check":
            items.append("current validity without follow-up check")
        return items
    if source_role == "public_resource_transaction":
        items = ["broad policy direction", "company revenue confirmation"]
        if freshness.label == "historical":
            items.append("current procurement opportunity")
        return items
    if source_role == "statistics_or_data_release":
        return [
            "individual project confirmation",
            "winning bid evidence",
            "company-specific revenue confirmation",
        ]
    if source_role == "company_disclosure":
        return ["government policy validity", "non-disclosed procurement awards"]
    if source_role == "industry_association_context":
        return ["primary official evidence", "transaction confirmation", "revenue confirmation"]
    return [
        "primary evidence without verification",
        "official policy text",
        "transaction confirmation",
    ]


def _relevance_label(score: float) -> str:
    if score >= 0.75:
        return "highly_related"
    if score >= 0.55:
        return "related"
    if score >= 0.35:
        return "weakly_related"
    return "off_topic"


def _is_formal_role(source_role: str) -> bool:
    return source_role in {
        "official_policy_original",
        "official_notice_or_rule",
        "statistics_or_data_release",
        "company_disclosure",
        "public_resource_transaction",
    }


def _normalize_domain(domain: str, url: str) -> str:
    if domain:
        return domain.lower().strip()
    try:
        return urlparse(url).netloc.lower()
    except ValueError:
        return ""


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term.lower() in text for term in terms)


def _round_score(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)
