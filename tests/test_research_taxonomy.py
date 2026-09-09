"""Tests for the canonical research taxonomy (research-taxonomy Phase 1).

Covers: 14 dimensions (10 base + 4 conditional), the 15+1 canonical source
families, legacy dimension_type canonicalization, old->new source-family alias
mapping, and the `{dimension}.{family}.{purpose}` slot_id shape.
"""

from __future__ import annotations

from packages.research_harness import research_taxonomy as rt
from packages.research_harness.caliber_expander import _normalize_intent_plan_structures
from packages.research_harness.plan_semantic import (
    SemanticSearchRound,
    _merge_dimension_plan,
)
from packages.sources.local_source_patterns import canonical_source_family


def test_dimension_taxonomy_has_14_base_and_conditional_split():
    assert len(rt.DIMENSIONS) == 14
    assert len(rt.BASE_DIMENSIONS) == 10
    assert len(rt.CONDITIONAL_DIMENSIONS) == 4
    assert set(rt.BASE_DIMENSIONS) | set(rt.CONDITIONAL_DIMENSIONS) == set(
        rt.DIMENSIONS
    )


def test_every_dimension_has_key_fields_and_primary_family():
    for dim_id, meta in rt.DIMENSIONS.items():
        assert meta["key_fields"], dim_id
        assert meta["expected_section_heading"], dim_id
        assert rt.DIMENSION_PRIMARY_FAMILY[dim_id], dim_id


def test_source_families_are_16_including_environmental_land_compat():
    assert len(rt.SOURCE_FAMILIES) == 16
    assert "environmental_land" in rt.SOURCE_FAMILIES  # retained compat


def test_every_canonical_family_has_purpose_and_label():
    for fam in rt.SOURCE_FAMILIES:
        assert rt.SOURCE_FAMILY_PURPOSE[fam], fam
        assert rt.SOURCE_FAMILY_LABELS[fam], fam


def test_legacy_dimension_types_canonicalize_to_new():
    assert rt.canonicalize_dimension_type("policy") == "policy_regulation"
    assert rt.canonicalize_dimension_type("execution") == "project_execution"
    assert rt.canonicalize_dimension_type("local_rollout") == "project_execution"
    assert rt.canonicalize_dimension_type("disclosure") == "company_fundamentals"
    assert rt.canonicalize_dimension_type("statistics") == "market_scale"
    assert rt.canonicalize_dimension_type("industry") == "industry_chain"
    # New values pass through unchanged.
    assert rt.canonicalize_dimension_type("industry_chain") == "industry_chain"
    assert rt.canonicalize_dimension_type("market_scale") == "market_scale"


def test_old_source_family_aliases_fold_to_new_canonical():
    assert canonical_source_family("official_policy") == "policy_document"
    assert canonical_source_family("official_news") == "local_official"
    assert canonical_source_family("local_government_notice") == "local_official"
    assert canonical_source_family("public_resource_transaction") == "tender_procurement"
    assert canonical_source_family("statistics_or_data_release") == "official_statistics"
    assert canonical_source_family("statistics") == "official_statistics"
    assert canonical_source_family("company_disclosure") == "company_disclosure"
    assert canonical_source_family("environmental_land") == "environmental_land"
    # Unknown falls back to the new default.
    assert canonical_source_family("") == "local_official"


def test_slot_id_shape_preserves_three_part_structure():
    assert rt.slot_id("industry_chain", "company_disclosure") == (
        "industry_chain.company_disclosure.company_basis"
    )
    # Legacy family resolves to the new canonical family in the slot_id.
    assert rt.slot_id("policy_regulation", "official_policy") == (
        "policy_regulation.policy_document.policy_basis"
    )


def test_context_families_are_optional():
    assert "industry_research" in rt.CONTEXT_FAMILIES
    assert "commercial_media" in rt.CONTEXT_FAMILIES
    assert "policy_document" not in rt.CONTEXT_FAMILIES
    assert "tender_procurement" not in rt.CONTEXT_FAMILIES


def test_merge_dimension_plan_forces_all_ten_base_dimensions():
    dims = _merge_dimension_plan(fallback=[], semantic=[], query_requirements={})
    types = {rt.canonicalize_dimension_type(d.get("dimension_type", "")) for d in dims}
    assert set(rt.BASE_DIMENSIONS) <= types
    # every injected dimension carries taxonomy key_fields
    for d in dims:
        dtype = rt.canonicalize_dimension_type(d.get("dimension_type", ""))
        assert d.get("key_fields") == rt.DIMENSIONS[dtype]["key_fields"], dtype


def test_normalize_intent_plan_injects_key_fields():
    raw = {
        "normalized_query": "湖南浏阳烟花产业发展",
        "dimension_plan": [
            {
                "dimension_id": "dim_market",
                "dimension_type": "market_scale",
                "research_question": "q",
                "why_it_matters": "w",
                "coverage_required": "c",
                "expected_section_heading": "市场规模与增长",
                "source_priority": "government",
                "source_families": ["official_statistics"],
                "caliber_terms": [],
            }
        ],
    }
    norm = _normalize_intent_plan_structures(raw)
    entry = norm["dimension_plan"][0]
    assert entry["key_fields"] == rt.DIMENSIONS["market_scale"]["key_fields"]


def test_every_dimension_has_chinese_search_key_fields():
    for dim_id, meta in rt.DIMENSIONS.items():
        skf = meta.get("search_key_fields")
        assert skf, dim_id
        assert all(
            any("\u4e00" <= c <= "\u9fff" for c in f) for f in skf
        ), f"{dim_id}: {skf}"


def test_normalize_intent_plan_injects_search_key_fields():
    raw = {
        "normalized_query": "湖南浏阳烟花产业发展",
        "dimension_plan": [
            {
                "dimension_id": "dim_chain",
                "dimension_type": "industry_chain",
                "research_question": "q",
                "why_it_matters": "w",
                "coverage_required": "c",
                "expected_section_heading": "产业链与价值链",
                "source_priority": "research",
                "source_families": ["industry_research"],
                "caliber_terms": [],
            }
        ],
    }
    norm = _normalize_intent_plan_structures(raw)
    entry = norm["dimension_plan"][0]
    # English key_fields (evidence validation) + Chinese search_key_fields (search).
    assert entry["key_fields"] == rt.DIMENSIONS["industry_chain"]["key_fields"]
    assert entry["search_key_fields"] == rt.DIMENSIONS["industry_chain"]["search_key_fields"]


def test_semantic_search_round_accepts_ten_rounds():
    # round_number cap raised from 6 to 10 for the broader search budget.
    round_10 = SemanticSearchRound(
        round_number=10,
        objective="第 10 轮",
        search_phrases=["a", "b", "c", "d", "e", "f"],
        include_domains=[],
        target_dimensions=[],
        expected_source_tier="B",
    )
    assert round_10.round_number == 10
