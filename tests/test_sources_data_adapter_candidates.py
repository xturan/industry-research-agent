from __future__ import annotations

import inspect

from packages.sources.data_adapter_candidates import (
    DataAccessMethod,
    DataAdapterCandidate,
    classify_data_adapter_candidate,
)


def test_national_customs_trade_data_is_direct_adapter_candidate() -> None:
    candidate = classify_data_adapter_candidate(
        source_name_or_type="General Administration of Customs Trade Data",
        source_class="trade_data",
        administrative_level="macro",
        affected_queries=["M08"],
    )

    assert candidate.recommended_access_method == (
        DataAccessMethod.DIRECT_STRUCTURED_ADAPTER_CANDIDATE
    )
    assert candidate.should_be_direct_adapter is True
    assert candidate.requires_new_adapter is True
    assert "customs" in candidate.tags


def test_county_statistics_yearbook_prefers_manual_source_profile() -> None:
    candidate = classify_data_adapter_candidate(
        source_name_or_type="Feixi county statistical bureau - county statistical yearbook",
        source_class="statistics",
        administrative_level="county",
        affected_queries=["K07"],
    )

    assert candidate.recommended_access_method == DataAccessMethod.MANUAL_SOURCE_PROFILE
    assert candidate.should_be_direct_adapter is False
    assert candidate.requires_new_source_registry_entry is True
    assert "city_county" in candidate.tags


def test_provincial_statistics_bulletin_prefers_existing_profile_update() -> None:
    candidate = classify_data_adapter_candidate(
        source_name_or_type="Anhui Statistics Bureau Data Bulletins",
        source_class="statistics",
        administrative_level="province",
        affected_queries=["P04"],
    )

    assert candidate.recommended_access_method == (
        DataAccessMethod.EXISTING_SOURCE_PROFILE_UPDATE
    )
    assert candidate.should_be_direct_adapter is False
    assert candidate.requires_new_source_registry_entry is False


def test_commerce_policy_page_stays_search_assisted_not_direct_data_adapter() -> None:
    candidate = classify_data_adapter_candidate(
        source_name_or_type="Zhejiang Commerce Department Policy",
        source_class="official_policy",
        administrative_level="province",
        affected_queries=["P03"],
    )

    assert candidate.recommended_access_method == DataAccessMethod.SEARCH_ASSISTED
    assert candidate.should_be_direct_adapter is False
    assert candidate.requires_new_adapter is False


def test_local_media_context_is_out_of_scope_for_direct_data_gate() -> None:
    candidate = classify_data_adapter_candidate(
        source_name_or_type="Local news media for satellite order context",
        source_class="media_context",
        administrative_level="city",
        affected_queries=["C09"],
    )

    assert candidate.recommended_access_method == DataAccessMethod.OUT_OF_SCOPE
    assert candidate.should_be_direct_adapter is False
    assert candidate.requires_new_adapter is False


def test_data_adapter_candidate_contract_is_not_query_id_specific() -> None:
    signature = inspect.signature(classify_data_adapter_candidate)

    assert "query_id" not in signature.parameters
    assert "case_id" not in signature.parameters
    assert set(DataAdapterCandidate.__annotations__) >= {
        "source_name_or_type",
        "source_class",
        "administrative_level",
        "recommended_access_method",
        "should_be_direct_adapter",
    }
