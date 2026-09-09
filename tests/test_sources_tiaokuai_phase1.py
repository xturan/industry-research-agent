from __future__ import annotations

from packages.sources.enums import (
    GovernanceAxis,
    InfoType,
    LineFamily,
    PublisherType,
    RegionalLevel,
    SourceRole,
)
from packages.sources.profiles import build_domestic_source_profiles
from packages.sources.registry import build_default_source_registry


def test_domestic_profiles_have_tiaokuai_fields() -> None:
    profiles = {profile.source_id: profile for profile in build_domestic_source_profiles()}
    assert profiles["cn_policy_generic"].governance_axis == GovernanceAxis.LINE
    assert profiles["cn_policy_generic"].line_family == LineFamily.POLICY
    assert profiles["cn_policy_generic"].regional_level == RegionalLevel.NATIONAL
    assert profiles["cn_policy_generic"].info_type == InfoType.POLICY_NOTICE
    assert profiles["cn_policy_generic"].publisher_type == PublisherType.MINISTRY
    assert profiles["cn_policy_generic"].source_role == SourceRole.PRIMARY

    assert profiles["cn_policy_ndrc_tzgg_v1"].governance_axis == GovernanceAxis.LINE
    assert profiles["cn_policy_ndrc_tzgg_v1"].line_family == LineFamily.POLICY
    assert profiles["cn_policy_ndrc_tzgg_v1"].publisher_type == PublisherType.MINISTRY

    assert profiles["cn_exchange_announcement_generic"].governance_axis == GovernanceAxis.LINE
    assert profiles["cn_exchange_announcement_generic"].line_family == LineFamily.EXCHANGE
    assert (
        profiles["cn_exchange_announcement_generic"].info_type
        == InfoType.REGULATORY_ANNOUNCEMENT
    )
    assert profiles["cn_exchange_announcement_generic"].publisher_type == PublisherType.EXCHANGE

    assert profiles["cn_exchange_szse_notice_v1"].governance_axis == GovernanceAxis.LINE
    assert profiles["cn_exchange_szse_notice_v1"].line_family == LineFamily.EXCHANGE
    assert profiles["cn_exchange_szse_notice_v1"].regional_level == RegionalLevel.NATIONAL

    assert profiles["cn_industry_association_generic"].governance_axis == GovernanceAxis.BLOCK
    assert profiles["cn_industry_association_generic"].line_family == LineFamily.INDUSTRY
    assert profiles["cn_industry_association_generic"].regional_level == RegionalLevel.CROSS_REGION
    assert profiles["cn_industry_association_generic"].info_type == InfoType.INDUSTRY_REPORT
    assert profiles["cn_industry_association_generic"].publisher_type == PublisherType.ASSOCIATION
    assert profiles["cn_industry_association_generic"].source_role == SourceRole.SUPPLEMENTAL


def test_default_registry_preserves_tiaokuai_metadata() -> None:
    registry = build_default_source_registry()
    policy_profile = registry.get_profile("cn_policy_ndrc_tzgg_v1", enabled_only=False)
    assert policy_profile is not None
    assert policy_profile.governance_axis == GovernanceAxis.LINE
    assert policy_profile.line_family == LineFamily.POLICY
    assert policy_profile.info_type == InfoType.POLICY_NOTICE
