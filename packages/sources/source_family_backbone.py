from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 fallback

    class StrEnum(str, Enum):  # noqa: UP042
        pass


class SourceFamilyBackbone(StrEnum):
    CITY_COUNTY_FALLBACK_TRANSPARENCY = "city_county_fallback_transparency"
    PUBLIC_RESOURCE_PROCUREMENT = "public_resource_procurement"
    PROJECT_FILING_APPROVAL_KEY_PROJECT = "project_filing_approval_key_project"
    LOCAL_STATISTICS_FISCAL = "local_statistics_fiscal"
    SECTOR_QUANTITATIVE_SUPPLEMENT_CONTROL = (
        "sector_quantitative_supplement_control"
    )
    ENVIRONMENTAL_LAND_NATURAL_RESOURCE = "environmental_land_natural_resource"
    EXTRACTION_PDF_QUALITY_GATE = "extraction_pdf_quality_gate"


@dataclass(frozen=True)
class SourceFamilyContract:
    family: SourceFamilyBackbone
    source_classes: tuple[str, ...]
    obligation_markers: tuple[str, ...] = ()
    regional_levels: tuple[str, ...] = ()


_CONTRACTS: tuple[SourceFamilyContract, ...] = (
    SourceFamilyContract(
        family=SourceFamilyBackbone.CITY_COUNTY_FALLBACK_TRANSPARENCY,
        source_classes=(
            "local_government",
            "statistics",
            "project_list",
            "tender_or_procurement",
            "environmental_or_land_record",
        ),
        obligation_markers=(
            "exact_local_depth",
            "administrative_granularity:city",
            "administrative_granularity:county",
        ),
        regional_levels=("city", "county", "municipal"),
    ),
    SourceFamilyContract(
        family=SourceFamilyBackbone.PUBLIC_RESOURCE_PROCUREMENT,
        source_classes=(
            "tender_or_procurement",
            "procurement",
            "government_procurement",
            "public_resource_trade",
            "local_project_tender",
        ),
    ),
    SourceFamilyContract(
        family=SourceFamilyBackbone.PROJECT_FILING_APPROVAL_KEY_PROJECT,
        source_classes=(
            "project_list",
            "project_transaction",
            "project_filing",
            "project_approval",
            "key_project",
        ),
    ),
    SourceFamilyContract(
        family=SourceFamilyBackbone.LOCAL_STATISTICS_FISCAL,
        source_classes=(
            "statistics",
            "local_government",
            "local_fund",
            "labor_statistics",
            "employment_or_labor_data",
            "industry_specific_statistics",
            "fiscal_local_government",
            "trade_data",
        ),
    ),
    SourceFamilyContract(
        family=SourceFamilyBackbone.SECTOR_QUANTITATIVE_SUPPLEMENT_CONTROL,
        source_classes=(
            "industry_association",
            "industry_report",
            "association_signal",
            "industry_whitepaper",
            "third_party_context",
        ),
        obligation_markers=(
            "sector_quantitative_supplement",
            "supplemental_context_only",
        ),
    ),
    SourceFamilyContract(
        family=SourceFamilyBackbone.ENVIRONMENTAL_LAND_NATURAL_RESOURCE,
        source_classes=(
            "environmental_or_land_record",
            "environmental_record",
            "land_record",
            "natural_resource_record",
            "planning_permit",
            "energy_saving_review",
            "regulatory_record",
            "official_record",
        ),
    ),
    SourceFamilyContract(
        family=SourceFamilyBackbone.EXTRACTION_PDF_QUALITY_GATE,
        source_classes=(
            "pdf_backed_evidence",
            "attachment_backed_evidence",
            "zero_text_candidate",
            "binary_extraction",
        ),
        obligation_markers=(
            "extraction_quality_required",
            "pdf_text_required",
        ),
    ),
)
_OFFICIAL_QUANTITATIVE_SOURCE_CLASSES = {
    "statistics",
    "trade_data",
    "production_data",
    "city_level_fiscal_data",
    "fiscal_local_government",
    "project_list",
    "tender_or_procurement",
    "company_disclosure",
    "environmental_or_land_record",
    "regulatory_record",
}

_FAMILY_ORDER: tuple[SourceFamilyBackbone, ...] = tuple(contract.family for contract in _CONTRACTS)


def source_family_contracts() -> tuple[SourceFamilyContract, ...]:
    return _CONTRACTS


def source_family_backbones_for_source_classes(
    source_classes: Iterable[str],
    *,
    evidence_obligations: Iterable[str] = (),
    regional_level: str | None = None,
) -> list[SourceFamilyBackbone]:
    normalized_classes = {_normalize_token(item) for item in source_classes}
    normalized_classes.discard("")
    normalized_obligations = {_normalize_token(item) for item in evidence_obligations}
    normalized_obligations.discard("")
    normalized_level = _normalize_token(regional_level or "")

    selected: set[SourceFamilyBackbone] = set()
    for contract in _CONTRACTS:
        if _contract_matches(
            contract,
            source_classes=normalized_classes,
            evidence_obligations=normalized_obligations,
            regional_level=normalized_level,
        ):
            selected.add(contract.family)
    return [family for family in _FAMILY_ORDER if family in selected]


def official_quantitative_obligation_satisfied(
    source_classes: Iterable[str],
) -> bool:
    normalized_classes = {_normalize_token(item) for item in source_classes}
    normalized_classes.discard("")
    return any(
        _token_matches(required_class, normalized_classes)
        for required_class in _OFFICIAL_QUANTITATIVE_SOURCE_CLASSES
    )


def _contract_matches(
    contract: SourceFamilyContract,
    *,
    source_classes: set[str],
    evidence_obligations: set[str],
    regional_level: str,
) -> bool:
    if contract.family == SourceFamilyBackbone.CITY_COUNTY_FALLBACK_TRANSPARENCY:
        return bool(
            any(marker in evidence_obligations for marker in contract.obligation_markers)
            or (regional_level and regional_level in contract.regional_levels)
        )
    if any(
        _token_matches(source_class, source_classes)
        for source_class in contract.source_classes
    ):
        return True
    if any(marker in evidence_obligations for marker in contract.obligation_markers):
        return True
    return bool(regional_level and regional_level in contract.regional_levels)


def _token_matches(pattern: str, candidates: set[str]) -> bool:
    normalized_pattern = _normalize_token(pattern)
    return any(
        candidate == normalized_pattern or normalized_pattern in candidate
        for candidate in candidates
    )


def _normalize_token(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


__all__ = [
    "SourceFamilyBackbone",
    "SourceFamilyContract",
    "official_quantitative_obligation_satisfied",
    "source_family_backbones_for_source_classes",
    "source_family_contracts",
]
