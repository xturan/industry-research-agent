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


# ---------------------------------------------------------------------------
# Phase 1 — public_resource_procurement backbone tests
# ---------------------------------------------------------------------------


def test_procurement_family_contract_includes_procurement_source_classes() -> None:
    """Verify PUBLIC_RESOURCE_PROCUREMENT contract covers all procurement source classes."""
    contracts = source_family_contracts()
    procurement_contract = next(
        c for c in contracts
        if c.family == SourceFamilyBackbone.PUBLIC_RESOURCE_PROCUREMENT
    )
    expected_classes = {
        "tender_or_procurement",
        "procurement",
        "government_procurement",
        "public_resource_trade",
        "local_project_tender",
    }
    assert set(procurement_contract.source_classes) == expected_classes


def test_procurement_source_classes_map_to_public_resource_backbone() -> None:
    """Each procurement source class selects only PUBLIC_RESOURCE_PROCUREMENT."""
    procurement_classes = [
        "tender_or_procurement",
        "procurement",
        "government_procurement",
        "public_resource_trade",
        "local_project_tender",
    ]
    for source_class in procurement_classes:
        families = source_family_backbones_for_source_classes([source_class])
        assert families == [SourceFamilyBackbone.PUBLIC_RESOURCE_PROCUREMENT], (
            f"{source_class} should map to PUBLIC_RESOURCE_PROCUREMENT, got {families}"
        )


def test_procurement_project_distinction_preserved() -> None:
    """tender_or_procurement ≠ project_list: the two must stay in separate backbones."""
    procurement = source_family_backbones_for_source_classes(["tender_or_procurement"])
    project = source_family_backbones_for_source_classes(["project_list"])
    both = source_family_backbones_for_source_classes(
        ["tender_or_procurement", "project_list"]
    )

    assert procurement == [SourceFamilyBackbone.PUBLIC_RESOURCE_PROCUREMENT]
    assert project == [SourceFamilyBackbone.PROJECT_FILING_APPROVAL_KEY_PROJECT]
    assert len(both) == 2
    assert SourceFamilyBackbone.PUBLIC_RESOURCE_PROCUREMENT in both
    assert SourceFamilyBackbone.PROJECT_FILING_APPROVAL_KEY_PROJECT in both


def test_procurement_family_activated_by_obligation_without_source_class() -> None:
    """PUBLIC_RESOURCE_PROCUREMENT is NOT selected when no procurement source class present,
    even with local obligations — it should only be selected by source class match."""
    families = source_family_backbones_for_source_classes(
        ["statistics"],
        evidence_obligations=["exact_local_depth", "administrative_granularity:city"],
        regional_level="city",
    )
    assert SourceFamilyBackbone.PUBLIC_RESOURCE_PROCUREMENT not in families


def test_generic_policy_source_classes_do_not_trigger_procurement() -> None:
    """Generic policy classes (official_policy, provincial_policy) should NOT
    select PUBLIC_RESOURCE_PROCUREMENT."""
    generic_policy_classes = [
        "official_policy",
        "provincial_policy",
        "financial_subsidy_notice",
        "local_government",
    ]
    for source_class in generic_policy_classes:
        families = source_family_backbones_for_source_classes([source_class])
        assert SourceFamilyBackbone.PUBLIC_RESOURCE_PROCUREMENT not in families, (
            f"{source_class} should NOT trigger PUBLIC_RESOURCE_PROCUREMENT"
        )
