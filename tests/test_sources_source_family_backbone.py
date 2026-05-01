from __future__ import annotations

import inspect

from packages.sources.source_family_backbone import (
    SourceFamilyBackbone,
    official_quantitative_obligation_satisfied,
    source_family_backbones_for_source_classes,
    source_family_contracts,
)


def test_source_family_contract_exposes_phase0_families() -> None:
    family_ids = {contract.family for contract in source_family_contracts()}

    assert family_ids >= {
        SourceFamilyBackbone.CITY_COUNTY_FALLBACK_TRANSPARENCY,
        SourceFamilyBackbone.PUBLIC_RESOURCE_PROCUREMENT,
        SourceFamilyBackbone.PROJECT_FILING_APPROVAL_KEY_PROJECT,
        SourceFamilyBackbone.LOCAL_STATISTICS_FISCAL,
        SourceFamilyBackbone.ENVIRONMENTAL_LAND_NATURAL_RESOURCE,
        SourceFamilyBackbone.EXTRACTION_PDF_QUALITY_GATE,
    }


def test_source_family_selection_uses_source_classes_and_local_obligations() -> None:
    families = source_family_backbones_for_source_classes(
        [
            "tender_or_procurement",
            "project_list",
            "statistics",
            "environmental_or_land_record",
        ],
        evidence_obligations=["exact_local_depth", "administrative_granularity:county"],
        regional_level="county",
    )

    assert families[:4] == [
        SourceFamilyBackbone.CITY_COUNTY_FALLBACK_TRANSPARENCY,
        SourceFamilyBackbone.PUBLIC_RESOURCE_PROCUREMENT,
        SourceFamilyBackbone.PROJECT_FILING_APPROVAL_KEY_PROJECT,
        SourceFamilyBackbone.LOCAL_STATISTICS_FISCAL,
    ]
    assert SourceFamilyBackbone.ENVIRONMENTAL_LAND_NATURAL_RESOURCE in families


def test_source_family_selection_is_not_query_id_specific() -> None:
    signature = inspect.signature(source_family_backbones_for_source_classes)
    assert "query_id" not in signature.parameters
    assert "case_id" not in signature.parameters

    common_source_classes = [
        "tender_or_procurement",
        "project_list",
        "statistics",
    ]
    hefei_families = source_family_backbones_for_source_classes(
        common_source_classes,
        evidence_obligations=["administrative_granularity:city", "exact_local_depth"],
        regional_level="city",
    )
    feixi_families = source_family_backbones_for_source_classes(
        common_source_classes,
        evidence_obligations=["administrative_granularity:county", "exact_local_depth"],
        regional_level="county",
    )

    assert hefei_families == feixi_families


def test_procurement_and_project_backbones_remain_distinct() -> None:
    procurement_only = source_family_backbones_for_source_classes(["tender_or_procurement"])
    project_only = source_family_backbones_for_source_classes(["project_list"])

    assert procurement_only == [SourceFamilyBackbone.PUBLIC_RESOURCE_PROCUREMENT]
    assert project_only == [SourceFamilyBackbone.PROJECT_FILING_APPROVAL_KEY_PROJECT]


def test_industry_association_and_report_sources_are_supplemental_only() -> None:
    families = source_family_backbones_for_source_classes(
        ["industry_association", "industry_report"]
    )

    assert families == [SourceFamilyBackbone.SECTOR_QUANTITATIVE_SUPPLEMENT_CONTROL]


def test_industry_supplement_does_not_satisfy_official_quantitative_obligation() -> None:
    assert official_quantitative_obligation_satisfied(["industry_report"]) is False
    assert official_quantitative_obligation_satisfied(["industry_association"]) is False
    assert official_quantitative_obligation_satisfied(["third_party_context"]) is False


def test_official_statistics_with_industry_report_keeps_supplement_separate() -> None:
    families = source_family_backbones_for_source_classes(
        ["statistics", "industry_report"],
        evidence_obligations=["official_quantitative_required"],
        regional_level="province",
    )

    assert SourceFamilyBackbone.LOCAL_STATISTICS_FISCAL in families
    assert SourceFamilyBackbone.SECTOR_QUANTITATIVE_SUPPLEMENT_CONTROL in families
    assert official_quantitative_obligation_satisfied(
        ["statistics", "industry_report"]
    ) is True
