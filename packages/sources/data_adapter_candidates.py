from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 fallback

    class StrEnum(str, Enum):  # noqa: UP042
        pass


class DataAccessMethod(StrEnum):
    SEARCH_ASSISTED = "search_assisted"
    EXISTING_SOURCE_PROFILE_UPDATE = "existing_source_profile_update"
    MANUAL_SOURCE_PROFILE = "manual_source_profile"
    DIRECT_STRUCTURED_ADAPTER_CANDIDATE = "direct_structured_adapter_candidate"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True)
class DataAdapterCandidate:
    source_name_or_type: str
    source_class: str
    administrative_level: str
    affected_queries: tuple[str, ...] = ()
    recommended_access_method: DataAccessMethod = DataAccessMethod.SEARCH_ASSISTED
    should_be_direct_adapter: bool = False
    requires_new_adapter: bool = False
    requires_new_source_registry_entry: bool = False
    integration_complexity: str = "low"
    expected_coverage_gain: str = "medium"
    estimated_cost_impact: str = "neutral"
    tags: tuple[str, ...] = field(default_factory=tuple)
    reason: str = ""


_LOCAL_LEVELS = {"city", "county", "district", "banner", "municipal"}
_PROVINCIAL_LEVELS = {"province", "provincial"}
_NATIONAL_LEVELS = {"macro", "national", "country"}
_DATA_CLASSES = {
    "statistics",
    "trade_data",
    "city_level_fiscal_data",
    "production_data",
    "industry_specific_statistics",
    "fiscal_local_government",
}
_OUT_OF_SCOPE_CLASSES = {
    "media_context",
    "third_party_context",
    "industry_report",
    "industry_association",
}


def classify_data_adapter_candidate(
    *,
    source_name_or_type: str,
    source_class: str,
    administrative_level: str,
    affected_queries: list[str] | tuple[str, ...] = (),
) -> DataAdapterCandidate:
    normalized_name = _normalize(source_name_or_type)
    normalized_class = _normalize(source_class)
    normalized_level = _normalize(administrative_level)
    query_tuple = tuple(str(item).strip() for item in affected_queries if str(item).strip())

    if normalized_class in _OUT_OF_SCOPE_CLASSES or _contains_any(
        normalized_name,
        ("media", "news", "daily", "press", "local news", "媒体", "新闻"),
    ):
        return _candidate(
            source_name_or_type=source_name_or_type,
            source_class=source_class,
            administrative_level=administrative_level,
            affected_queries=query_tuple,
            method=DataAccessMethod.OUT_OF_SCOPE,
            tags=("weak_context",),
            reason="Weak context sources should not become direct structured data adapters.",
        )

    if normalized_class == "official_policy":
        return _candidate(
            source_name_or_type=source_name_or_type,
            source_class=source_class,
            administrative_level=administrative_level,
            affected_queries=query_tuple,
            method=DataAccessMethod.SEARCH_ASSISTED,
            tags=("policy_context",),
            reason="Policy pages remain search-assisted unless they expose stable structured data.",
        )

    if _is_national_structured_data_source(normalized_name, normalized_class, normalized_level):
        return _candidate(
            source_name_or_type=source_name_or_type,
            source_class=source_class,
            administrative_level=administrative_level,
            affected_queries=query_tuple,
            method=DataAccessMethod.DIRECT_STRUCTURED_ADAPTER_CANDIDATE,
            should_be_direct_adapter=True,
            requires_new_adapter=True,
            integration_complexity="medium",
            expected_coverage_gain="high",
            estimated_cost_impact="lower",
            tags=_tags_for_data_source(normalized_name, normalized_class, normalized_level),
            reason=(
                "Stable national structured data sources are better handled by "
                "direct adapters than repeated search discovery."
            ),
        )

    if normalized_level in _PROVINCIAL_LEVELS and _is_data_source(
        normalized_name, normalized_class
    ):
        return _candidate(
            source_name_or_type=source_name_or_type,
            source_class=source_class,
            administrative_level=administrative_level,
            affected_queries=query_tuple,
            method=DataAccessMethod.EXISTING_SOURCE_PROFILE_UPDATE,
            expected_coverage_gain="medium",
            tags=_tags_for_data_source(normalized_name, normalized_class, normalized_level),
            reason=(
                "Provincial statistics and commerce sources already have reusable "
                "profile patterns; update or add profiles before building adapters."
            ),
        )

    if normalized_level in _LOCAL_LEVELS and _is_data_source(
        normalized_name, normalized_class
    ):
        return _candidate(
            source_name_or_type=source_name_or_type,
            source_class=source_class,
            administrative_level=administrative_level,
            affected_queries=query_tuple,
            method=DataAccessMethod.MANUAL_SOURCE_PROFILE,
            requires_new_source_registry_entry=True,
            integration_complexity="low",
            expected_coverage_gain="medium",
            estimated_cost_impact="lower",
            tags=_tags_for_data_source(normalized_name, normalized_class, normalized_level),
            reason=(
                "City/county data sources are too heterogeneous for a direct adapter "
                "first; add source profiles and site-search patterns before adapter work."
            ),
        )

    return _candidate(
        source_name_or_type=source_name_or_type,
        source_class=source_class,
        administrative_level=administrative_level,
        affected_queries=query_tuple,
        method=DataAccessMethod.SEARCH_ASSISTED,
        tags=_tags_for_data_source(normalized_name, normalized_class, normalized_level),
        reason=(
            "Default to search-assisted discovery until stable structure or repeated "
            "failures justify a profile or adapter."
        ),
    )


def _candidate(
    *,
    source_name_or_type: str,
    source_class: str,
    administrative_level: str,
    affected_queries: tuple[str, ...],
    method: DataAccessMethod,
    should_be_direct_adapter: bool = False,
    requires_new_adapter: bool = False,
    requires_new_source_registry_entry: bool = False,
    integration_complexity: str = "low",
    expected_coverage_gain: str = "medium",
    estimated_cost_impact: str = "neutral",
    tags: tuple[str, ...] = (),
    reason: str,
) -> DataAdapterCandidate:
    return DataAdapterCandidate(
        source_name_or_type=source_name_or_type,
        source_class=source_class,
        administrative_level=administrative_level,
        affected_queries=affected_queries,
        recommended_access_method=method,
        should_be_direct_adapter=should_be_direct_adapter,
        requires_new_adapter=requires_new_adapter,
        requires_new_source_registry_entry=requires_new_source_registry_entry,
        integration_complexity=integration_complexity,
        expected_coverage_gain=expected_coverage_gain,
        estimated_cost_impact=estimated_cost_impact,
        tags=tags,
        reason=reason,
    )


def _is_national_structured_data_source(
    normalized_name: str,
    normalized_class: str,
    normalized_level: str,
) -> bool:
    if normalized_level not in _NATIONAL_LEVELS:
        return False
    if normalized_class in {"trade_data", "statistics"} and _contains_any(
        normalized_name,
        ("customs", "statistics", "stats", "海关", "统计局", "统计"),
    ):
        return True
    return False


def _is_data_source(normalized_name: str, normalized_class: str) -> bool:
    if normalized_class in _DATA_CLASSES:
        return True
    return _contains_any(
        normalized_name,
        (
            "statistics",
            "statistical",
            "stats",
            "yearbook",
            "bulletin",
            "budget",
            "fiscal",
            "customs",
            "commerce",
            "trade",
            "import",
            "export",
            "energy",
            "electricity",
            "power",
            "port",
            "logistics",
            "统计",
            "年鉴",
            "公报",
            "财政",
            "预算",
            "决算",
            "海关",
            "商务",
            "进出口",
            "能源",
            "用电",
            "电力",
            "口岸",
            "港口",
            "物流",
        ),
    )


def _tags_for_data_source(
    normalized_name: str,
    normalized_class: str,
    normalized_level: str,
) -> tuple[str, ...]:
    tags: list[str] = []
    if normalized_level in _LOCAL_LEVELS:
        tags.append("city_county")
    elif normalized_level in _PROVINCIAL_LEVELS:
        tags.append("provincial")
    elif normalized_level in _NATIONAL_LEVELS:
        tags.append("national")
    if normalized_class:
        tags.append(normalized_class)
    if _contains_any(normalized_name, ("customs", "海关")):
        tags.append("customs")
    if _contains_any(normalized_name, ("commerce", "trade", "import", "export", "商务", "进出口")):
        tags.append("trade")
    if _contains_any(normalized_name, ("energy", "electricity", "power", "能源", "电力", "用电")):
        tags.append("energy")
    if _contains_any(normalized_name, ("budget", "fiscal", "财政", "预算", "决算")):
        tags.append("fiscal")
    return _unique_strings(tags)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _normalize(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _unique_strings(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return tuple(unique)


__all__ = [
    "DataAccessMethod",
    "DataAdapterCandidate",
    "classify_data_adapter_candidate",
]
