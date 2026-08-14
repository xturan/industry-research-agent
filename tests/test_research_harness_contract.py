"""Focused unit tests for the Research Contract Compiler
(research-contract-refactor Phase A).

`compile_research_contract` deterministically derives a ResearchContract v1
from the existing semantic plan (dimension_plan + evidence_requirement_spec)
without touching the Planner. These tests pin the derivation rules:

- primary family for a dimension_type -> critical slot
- context families (media/research/news) -> optional
- everything else in source_families -> required
- family aliases normalize to the 8-value canonical taxonomy
- min_evidence honors the strongest obligation for that family
- empty/invalid plans degrade to an empty contract (never raise)
"""

from packages.research_harness.real_nodes import (
    _annotate_draft_paragraph_mapping,
    _backfill_claim_slot_ids,
    _build_research_gaps,
    _claim_covers_slot,
    _extract_cited_evidence_ids,
    _find_claim_gap_slots,
    _slot_evidence_count,
    _slot_evidence_satisfies_fields,
)
from packages.research_harness.research_contract import (
    CONTRACT_VERSION,
    compile_research_contract,
)


def _sample_plan(**overrides) -> dict:
    plan = {
        "normalized_query": "合肥低空经济产业发展情况",
        "dimension_plan": [
            {
                "dimension_id": "dim_policy",
                "dimension_type": "policy_regulation",
                "research_question": "合肥低空经济政策与地方落地进展如何？",
                "why_it_matters": "判断政策到项目传导链条",
                "coverage_required": "覆盖政策原文与地方实施方案",
                "expected_section_heading": "政策主线与地方落地",
                "source_priority": "B",
                "source_families": [
                    "policy_document",
                    "local_official",
                    "tender_procurement",
                ],
                "caliber_terms": ["低空经济", "eVTOL"],
            },
            {
                "dimension_id": "dim_disclosure",
                "dimension_type": "company_fundamentals",
                "research_question": "哪些上市公司披露了低空经济业务？",
                "why_it_matters": "识别产业链公司",
                "coverage_required": "覆盖上市公司公告与年报",
                "expected_section_heading": "公司披露",
                "source_priority": "B",
                "source_families": ["company_disclosure", "industry_research"],
                "caliber_terms": ["低空经济"],
            },
        ],
        "source_obligations": [
            {
                "obligation_id": "obl_policy",
                "source_family": "policy_document",
                "required_for": "政策基线",
                "min_required_evidence": 3,
            },
            {
                "obligation_id": "obl_disclosure",
                "source_family": "company_disclosure",
                "required_for": "公司披露",
                "min_required_evidence": 2,
            },
        ],
        "query_requirements": {
            "needs_company_disclosure": True,
            "target_location": "合肥",
            "is_location_sensitive": True,
        },
    }
    plan.update(overrides)
    return plan


def test_compile_emits_contract_shape():
    contract = compile_research_contract(_sample_plan())
    assert contract["contract_version"] == CONTRACT_VERSION
    assert contract["normalized_query"] == "合肥低空经济产业发展情况"
    assert len(contract["sections"]) == 2
    assert contract["meta"]["section_count"] == 2


def test_primary_family_is_required_by_default_not_critical():
    # Priority must NOT be derived from source_family: a primary family is
    # `required` by default and only becomes `critical` when explicitly declared.
    contract = compile_research_contract(_sample_plan())
    policy_section = contract["sections"][0]
    by_family = {s["source_family"]: s for s in policy_section["claim_slots"]}
    assert by_family["policy_document"]["required"] == "required"
    assert by_family["tender_procurement"]["required"] == "required"
    assert by_family["local_official"]["required"] == "optional"
    assert by_family["policy_document"]["primary_source_required"] is True


def test_context_family_is_optional_even_when_only_family():
    plan = _sample_plan()
    plan["dimension_plan"][1]["source_families"] = [
        "industry_research",
        "company_disclosure",
    ]
    contract = compile_research_contract(plan)
    disclosure_section = contract["sections"][1]
    by_family = {s["source_family"]: s for s in disclosure_section["claim_slots"]}
    assert by_family["company_disclosure"]["required"] == "required"
    assert by_family["industry_research"]["required"] == "optional"


def test_explicit_critical_slots_override_by_slot_id():
    plan = _sample_plan()
    plan["critical_slots"] = ["dim_policy.policy_document.policy_basis"]
    contract = compile_research_contract(plan)
    policy_section = contract["sections"][0]
    by_family = {s["source_family"]: s for s in policy_section["claim_slots"]}
    assert by_family["policy_document"]["required"] == "critical"
    assert by_family["tender_procurement"]["required"] == "required"


def test_no_critical_slot_declared_warning():
    contract = compile_research_contract(_sample_plan())
    codes = [w["code"] for w in contract["contract_warnings"]]
    assert "NO_CRITICAL_SLOT_DECLARED" in codes
    warning = next(
        w for w in contract["contract_warnings"]
        if w["code"] == "NO_CRITICAL_SLOT_DECLARED"
    )
    assert warning["severity"] == "warning"


def test_critical_slot_declared_suppresses_warning():
    plan = _sample_plan()
    plan["critical_slots"] = ["dim_policy.policy_document.policy_basis"]
    contract = compile_research_contract(plan)
    codes = [w["code"] for w in contract["contract_warnings"]]
    assert "NO_CRITICAL_SLOT_DECLARED" not in codes


def test_explicit_critical_slots_override_by_pair():
    plan = _sample_plan()
    plan["critical_slots"] = [
        {"section_id": "dim_disclosure", "source_family": "company_disclosure"}
    ]
    contract = compile_research_contract(plan)
    disclosure_section = contract["sections"][1]
    by_family = {s["source_family"]: s for s in disclosure_section["claim_slots"]}
    assert by_family["company_disclosure"]["required"] == "critical"
    # the policy section stays required
    policy_section = contract["sections"][0]
    assert policy_section["claim_slots"][0]["required"] == "required"


def test_family_alias_normalized_to_canonical():
    plan = _sample_plan()
    plan["dimension_plan"][0]["source_families"] = [
        "provincial_policy",
        "tender_or_procurement",
    ]
    contract = compile_research_contract(plan)
    policy_section = contract["sections"][0]
    families = {s["source_family"] for s in policy_section["claim_slots"]}
    assert "policy_document" in families
    assert "tender_procurement" in families
    assert "provincial_policy" not in families


def test_min_evidence_honors_strongest_obligation():
    plan = _sample_plan()
    contract = compile_research_contract(plan)
    policy_section = contract["sections"][0]
    by_family = {s["source_family"]: s for s in policy_section["claim_slots"]}
    assert by_family["policy_document"]["min_evidence"] == 3
    assert by_family["tender_procurement"]["min_evidence"] >= 2


def test_slot_id_is_stable_and_human_readable():
    contract = compile_research_contract(_sample_plan())
    slot_ids = [
        s["slot_id"] for sec in contract["sections"] for s in sec["claim_slots"]
    ]
    assert "dim_policy.policy_document.policy_basis" in slot_ids
    assert "dim_policy.tender_procurement.tender_evidence" in slot_ids
    assert "dim_disclosure.company_disclosure.company_basis" in slot_ids


def test_writing_policy_constants():
    contract = compile_research_contract(_sample_plan())
    assert contract["writing_policy"]["default_max_assertion_level"] == 3
    assert contract["writing_policy"]["critical_slot_missing_mode"] == "evidence_gap_only"
    # global editorial rules are not duplicated onto every claim card
    global_rules = contract["writing_policy"]["global_editorial_rules"]
    assert global_rules["new_numeric_fact_requires_evidence"] is True


def test_deterministic_same_input_same_output():
    plan = _sample_plan()
    assert compile_research_contract(plan) == compile_research_contract(plan)


def test_empty_plan_degrades_gracefully():
    contract = compile_research_contract({})
    assert contract["contract_version"] == CONTRACT_VERSION
    assert contract["sections"] == []
    assert contract["meta"]["slot_count"] == 0


def test_invalid_plan_does_not_raise():
    contract = compile_research_contract(None)
    assert contract["sections"] == []
    contract = compile_research_contract("not a dict")
    assert contract["sections"] == []


# ── slot-driven Claim Expander helpers ──────────────────────────────────────

def _slot(plan, section_index: int, family: str) -> dict:
    contract = compile_research_contract(plan)
    sec = contract["sections"][section_index]
    return next(s for s in sec["claim_slots"] if s["source_family"] == family)


def _ev(evidence_id: str, family: str) -> dict:
    return {
        "evidence_id": evidence_id,
        "source_id": f"src_{evidence_id}",
        "source_family": family,
        "summary": f"summary {evidence_id}",
        "support_strength": 0.7,
        "limitations": [],
    }


def _family_map_for(*evidence: dict) -> dict:
    out = {}
    for e in evidence:
        sid = str(e.get("source_id") or "")
        if sid:
            out[sid] = str(e.get("source_family") or "")
    return out


def _src_family_map(*, official=1, transaction=0, disclosure=0) -> dict:
    out = {}
    for i in range(official):
        out[f"src_e{i + 1}"] = "policy_document"
    for i in range(transaction):
        out[f"src_t{i + 1}"] = "tender_procurement"
    for i in range(disclosure):
        out[f"src_d{i + 1}"] = "company_disclosure"
    return out


def test_slot_evidence_count_matches_family_via_source_id():
    plan = _sample_plan()
    slot = _slot(plan, 0, "policy_document")
    evidence = [
        {"evidence_id": "e1", "source_id": "src_e1"},
        {"evidence_id": "e2", "source_id": "src_e2"},
        {"evidence_id": "e3", "source_id": "src_t1"},
    ]
    src_family_by_id = _src_family_map(official=2, transaction=1)
    assert _slot_evidence_count(slot, evidence, src_family_by_id) == 2


def test_slot_evidence_count_falls_back_to_inline_family():
    plan = _sample_plan()
    slot = _slot(plan, 0, "policy_document")
    evidence = [{"evidence_id": "e1", "source_family": "policy_document"}]
    assert _slot_evidence_count(slot, evidence, {}) == 1


def _fielded_ev(evidence_id: str, family: str, **fields) -> dict:
    ev = _ev(evidence_id, family)
    ev.update(fields)
    return ev


def test_find_claim_gap_slots_detects_uncovered_satisfied_slot():
    plan = _sample_plan()
    contract = compile_research_contract(plan)
    slot = _slot(plan, 0, "policy_document")
    # policy_document min_evidence=3 + a key field present (region), no claim yet
    evidence = [
        _fielded_ev("e1", "policy_document", region="合肥"),
        _fielded_ev("e2", "policy_document", region="合肥"),
        _fielded_ev("e3", "policy_document", region="合肥"),
    ]
    claims = [
        {"claim_id": "c1", "text": "某条不相关断言", "evidence_ids": [],
         "required_source_family": "company_disclosure"}
    ]
    evidence_map = {str(e["evidence_id"]): e for e in evidence}
    src_family_by_id = _family_map_for(*evidence)
    gaps = _find_claim_gap_slots(
        contract=contract, claims=claims, evidence=evidence, evidence_map=evidence_map,
        src_family_by_id=src_family_by_id,
    )
    gap_ids = [s["slot_id"] for s in gaps]
    assert slot["slot_id"] in gap_ids


def test_find_claim_gap_slots_requires_key_field_present():
    # enough evidence but zero key fields -> NOT a claim gap (missing-fields gate)
    plan = _sample_plan()
    contract = compile_research_contract(plan)
    slot = _slot(plan, 0, "policy_document")
    evidence = [
        _ev("e1", "policy_document"),
        _ev("e2", "policy_document"),
        _ev("e3", "policy_document"),
    ]
    evidence_map = {str(e["evidence_id"]): e for e in evidence}
    src_family_by_id = _family_map_for(*evidence)
    gaps = _find_claim_gap_slots(
        contract=contract, claims=[], evidence=evidence, evidence_map=evidence_map,
        src_family_by_id=src_family_by_id,
    )
    assert all(s["slot_id"] != slot["slot_id"] for s in gaps)


def test_field_requirements_strict_mandatory_gate():
    plan = _sample_plan()
    plan["field_requirements"] = {
        "dim_policy": {
            "mandatory_fields": ["project_name", "operation_status"],
            "any_of_fields": ["activation_date", "operator"],
            "minimum_optional_fields": 1,
        }
    }
    slot = _slot(plan, 0, "policy_document")
    assert slot["field_validation_mode"] == "strict"
    req = slot["field_requirements"]["mandatory_fields"]
    assert req == ["project_name", "operation_status"]

    # mandatory satisfied + 1 any_of -> pass
    good = [_fielded_ev("e1", "policy_document", project_name="合肥低空项目",
                        operation_status="已投运", activation_date="2025-09-01")]
    assert _slot_evidence_satisfies_fields(slot, good, {}) is True
    # mandatory missing -> fail
    bad = [_fielded_ev("e2", "policy_document", activation_date="2025-09-01")]
    assert _slot_evidence_satisfies_fields(slot, bad, {}) is False


def test_field_requirements_legacy_fallback_mode():
    plan = _sample_plan()
    slot = _slot(plan, 0, "policy_document")
    assert slot["field_validation_mode"] == "legacy_any_key_field"
    # at least one key field (region) present -> pass
    ev1 = _fielded_ev("e1", "policy_document", region="合肥")
    assert _slot_evidence_satisfies_fields(slot, [ev1], {}) is True
    # zero key fields -> fail
    assert _slot_evidence_satisfies_fields(slot, [_ev("e2", "policy_document")], {}) is False


def test_find_claim_gap_slots_skips_contradictory_slot():
    plan = _sample_plan()
    contract = compile_research_contract(plan)
    slot = _slot(plan, 0, "policy_document")
    evidence = [
        _fielded_ev("e1", "policy_document", region="合肥",
                     limitations=["不同口径数据存在矛盾，状态不一致"]),
        _fielded_ev("e2", "policy_document", region="合肥"),
        _fielded_ev("e3", "policy_document", region="合肥"),
    ]
    evidence_map = {str(e["evidence_id"]): e for e in evidence}
    src_family_by_id = _family_map_for(*evidence)
    gaps = _find_claim_gap_slots(
        contract=contract, claims=[], evidence=evidence, evidence_map=evidence_map,
        src_family_by_id=src_family_by_id,
    )
    # contradiction -> becomes a ResearchGap, not a claim-gap slot
    assert all(s["slot_id"] != slot["slot_id"] for s in gaps)


def test_find_claim_gap_slots_ignores_covered_slot():
    plan = _sample_plan()
    contract = compile_research_contract(plan)
    slot = _slot(plan, 0, "policy_document")
    evidence = [_ev("e1", "policy_document")] * 3
    evidence_map = {str(e["evidence_id"]): e for e in evidence}
    src_family_by_id = _family_map_for(*evidence)
    claims = [
        {"claim_id": "c1", "text": "覆盖政策断言", "evidence_ids": ["e1"],
         "required_source_family": "policy_document"}
    ]
    assert _claim_covers_slot(
        claim=claims[0], slot=slot, evidence_map=evidence_map,
        src_family_by_id=src_family_by_id,
    ) is True
    gaps = _find_claim_gap_slots(
        contract=contract, claims=claims, evidence=evidence, evidence_map=evidence_map,
        src_family_by_id=src_family_by_id,
    )
    assert all(s["slot_id"] != slot["slot_id"] for s in gaps)


def test_find_claim_gap_slots_ignores_unsatisfied_slot():
    plan = _sample_plan()
    contract = compile_research_contract(plan)
    # policy_document min_evidence=3, only 1 evidence -> not a claim gap
    evidence = [_ev("e1", "policy_document")]
    evidence_map = {str(e["evidence_id"]): e for e in evidence}
    src_family_by_id = _family_map_for(*evidence)
    gaps = _find_claim_gap_slots(
        contract=contract, claims=[], evidence=evidence, evidence_map=evidence_map,
        src_family_by_id=src_family_by_id,
    )
    slot = _slot(plan, 0, "policy_document")
    assert all(s["slot_id"] != slot["slot_id"] for s in gaps)


def test_backfill_claim_slot_ids_assigns_slot_from_required_family():
    plan = _sample_plan()
    contract = compile_research_contract(plan)
    claim = {
        "claim_id": "c1",
        "text": "合肥发布了低空经济支持政策",
        "required_source_family": "policy_document",
        "evidence_ids": ["e1"],
    }
    evidence = [_ev("e1", "policy_document")]
    evidence_map = {str(e["evidence_id"]): e for e in evidence}
    src_family_by_id = _family_map_for(*evidence)
    _backfill_claim_slot_ids(
        claims=[claim], contract=contract, evidence_map=evidence_map,
        src_family_by_id=src_family_by_id,
    )
    assert claim["slot_id"] == "dim_policy.policy_document.policy_basis"


def test_backfill_claim_slot_ids_assigns_slot_via_linked_evidence_family():
    plan = _sample_plan()
    contract = compile_research_contract(plan)
    # required_source_family empty, but linked evidence resolves to policy_document
    claim = {
        "claim_id": "c1",
        "text": "合肥发布了低空经济支持政策",
        "required_source_family": "",
        "evidence_ids": ["e1"],
    }
    evidence = [_ev("e1", "policy_document")]
    evidence_map = {str(e["evidence_id"]): e for e in evidence}
    src_family_by_id = _family_map_for(*evidence)
    _backfill_claim_slot_ids(
        claims=[claim], contract=contract, evidence_map=evidence_map,
        src_family_by_id=src_family_by_id,
    )
    assert claim["slot_id"] == "dim_policy.policy_document.policy_basis"


def test_backfill_claim_slot_ids_multi_slot():
    plan = _sample_plan()
    contract = compile_research_contract(plan)
    # a claim linking evidence from two families covers two slots
    claim = {
        "claim_id": "c1",
        "text": "合肥发布政策并推动项目落地",
        "required_source_family": "",
        "evidence_ids": ["e1", "e2"],
    }
    evidence = [
        _ev("e1", "policy_document"),
        _ev("e2", "tender_procurement"),
    ]
    evidence_map = {str(e["evidence_id"]): e for e in evidence}
    src_family_by_id = _family_map_for(*evidence)
    _backfill_claim_slot_ids(
        claims=[claim], contract=contract, evidence_map=evidence_map,
        src_family_by_id=src_family_by_id,
    )
    assert len(claim["slot_ids"]) == 2
    assert "dim_policy.policy_document.policy_basis" in claim["slot_ids"]
    assert "dim_policy.tender_procurement.tender_evidence" in claim["slot_ids"]
    # primary is the highest-priority slot (both required here; tie-break by order)
    assert claim["primary_slot_id"] == claim["slot_ids"][0]
    assert claim["slot_id"] == claim["primary_slot_id"]


def test_backfill_claim_slot_ids_keeps_explicit_slot_id():
    plan = _sample_plan()
    contract = compile_research_contract(plan)
    claim = {
        "claim_id": "c1",
        "text": "某断言",
        "slot_id": "custom.slot.1",
        "required_source_family": "",
        "evidence_ids": [],
    }
    evidence_map: dict = {}
    _backfill_claim_slot_ids(
        claims=[claim], contract=contract, evidence_map=evidence_map, src_family_by_id={}
    )
    assert claim["slot_id"] == "custom.slot.1"


# ── StructuredDraft paragraph mapping ───────────────────────────────────────

def test_extract_cited_evidence_ids_ignores_markdown_links():
    text = "合肥政策支持低空经济 [ev_1]。参见 [来源](https://example.com)。另有 [ev_2] 佐证。"
    assert _extract_cited_evidence_ids(text) == ["ev_1", "ev_2"]


def test_explicit_paragraph_markers_are_formal_mapping():
    sections = [
        {
            "section_id": "sec_1",
            "title": "政策主线",
            "markdown_body": (
                "<!-- paragraph_id: p_001 -->\n"
                "<!-- claim_ids: c1, c4 -->\n"
                "<!-- evidence_ids: ev_1, ev_7 -->\n"
                "合肥发布低空经济支持政策。"
            ),
            "paragraphs": [],
        }
    ]
    claims = [
        {"claim_id": "c1", "text": "合肥发布低空经济支持政策", "evidence_ids": ["ev_1"]},
        {"claim_id": "c2", "text": "完全无关断言", "evidence_ids": ["ev_9"]},
    ]
    evidence = [{"evidence_id": "ev_1"}, {"evidence_id": "ev_7"}, {"evidence_id": "ev_9"}]
    mapping = _annotate_draft_paragraph_mapping(
        sections=sections, claims=claims, evidence=evidence
    )
    para = mapping["sections"][0]["paragraphs"][0]
    assert para["paragraph_id"] == "p_001"
    assert para["claim_ids"] == ["c1", "c4"]
    assert para["evidence_ids"] == ["ev_1", "ev_7"]
    assert para["mapping_source"] == "editor_explicit"
    assert para["mapping_confidence"] == 1.0
    # markers are stripped from visible text
    assert "<!--" not in para["text"]
    # c2 is unused even though the body mentions ev_9 nowhere
    assert mapping["unused_claim_ids"] == ["c2"]


def test_explicit_mapping_is_validated_against_existing_ids():
    sections = [
        {
            "section_id": "sec_1",
            "title": "政策主线",
            "markdown_body": (
                "<!-- claim_ids: c1, ghost_claim -->\n"
                "<!-- evidence_ids: ev_1, ghost_ev -->\n"
                "合肥发布低空经济支持政策。"
            ),
            "paragraphs": [],
        }
    ]
    claims = [{"claim_id": "c1", "text": "合肥发布低空经济支持政策", "evidence_ids": ["ev_1"]}]
    evidence = [{"evidence_id": "ev_1"}]
    mapping = _annotate_draft_paragraph_mapping(
        sections=sections, claims=claims, evidence=evidence
    )
    para = mapping["sections"][0]["paragraphs"][0]
    assert para["mapping_source"] == "editor_explicit"
    # explicit != correct: ghost ids must be flagged
    assert para["mapping_validated"] is False
    assert any("ghost_claim" in issue for issue in para["mapping_issues"])
    assert any("ghost_ev" in issue for issue in para["mapping_issues"])


def test_explicit_mapping_flags_foreign_evidence_not_in_claim_support():
    sections = [
        {
            "section_id": "sec_1",
            "title": "政策主线",
            "markdown_body": (
                "<!-- claim_ids: c1 -->\n"
                "<!-- evidence_ids: ev_1, ev_9 -->\n"
                "合肥发布低空经济支持政策。"
            ),
            "paragraphs": [],
        }
    ]
    claims = [{"claim_id": "c1", "text": "合肥发布低空经济支持政策", "evidence_ids": ["ev_1"]}]
    evidence = [{"evidence_id": "ev_1"}, {"evidence_id": "ev_9"}]
    mapping = _annotate_draft_paragraph_mapping(
        sections=sections, claims=claims, evidence=evidence
    )
    para = mapping["sections"][0]["paragraphs"][0]
    assert para["mapping_validated"] is False
    assert any("ev_9" in issue and "support" in issue for issue in para["mapping_issues"])


def test_valid_explicit_mapping_validates_true():
    sections = [
        {
            "section_id": "sec_1",
            "title": "政策主线",
            "markdown_body": (
                "<!-- claim_ids: c1 -->\n"
                "<!-- evidence_ids: ev_1 -->\n"
                "合肥发布低空经济支持政策。"
            ),
            "paragraphs": [],
        }
    ]
    claims = [{"claim_id": "c1", "text": "合肥发布低空经济支持政策", "evidence_ids": ["ev_1"]}]
    evidence = [{"evidence_id": "ev_1"}]
    mapping = _annotate_draft_paragraph_mapping(
        sections=sections, claims=claims, evidence=evidence
    )
    para = mapping["sections"][0]["paragraphs"][0]
    assert para["mapping_validated"] is True
    assert para["mapping_issues"] == []


def test_heuristic_mapping_is_flagged_low_confidence():
    sections = [
        {
            "section_id": "sec_1",
            "title": "政策主线",
            "markdown_body": "合肥发布低空经济支持政策 [ev_1]。",
            "paragraphs": [],
        }
    ]
    claims = [{"claim_id": "c1", "text": "合肥发布低空经济支持政策", "evidence_ids": ["ev_1"]}]
    evidence = [{"evidence_id": "ev_1"}]
    mapping = _annotate_draft_paragraph_mapping(
        sections=sections, claims=claims, evidence=evidence
    )
    para = mapping["sections"][0]["paragraphs"][0]
    assert para["mapping_source"] == "heuristic"
    assert para["mapping_confidence"] < 1.0
    assert "c1" in para["claim_ids"]


def test_paragraph_mapping_binds_evidence_and_claims():
    sections = [
        {
            "section_id": "sec_1",
            "title": "政策主线",
            "markdown_body": "合肥发布低空经济支持政策 [ev_1]，并推动项目落地 [ev_2]。",
            "paragraphs": [],
        }
    ]
    claims = [
        {"claim_id": "c1", "text": "合肥发布低空经济支持政策", "evidence_ids": ["ev_1"]},
        {"claim_id": "c2", "text": "项目加速落地", "evidence_ids": ["ev_2"]},
        {"claim_id": "c3", "text": "完全未使用的断言", "evidence_ids": ["ev_9"]},
    ]
    evidence = [
        {"evidence_id": "ev_1"},
        {"evidence_id": "ev_2"},
        {"evidence_id": "ev_9"},
    ]
    mapping = _annotate_draft_paragraph_mapping(
        sections=sections, claims=claims, evidence=evidence
    )
    para = mapping["sections"][0]["paragraphs"][0]
    assert "ev_1" in para["evidence_ids"]
    assert "ev_2" in para["evidence_ids"]
    assert "c1" in para["claim_ids"]
    assert "c2" in para["claim_ids"]
    assert "c3" not in para["claim_ids"]
    assert mapping["unused_claim_ids"] == ["c3"]


def test_paragraph_mapping_links_claim_text_without_citation():
    sections = [
        {
            "section_id": "sec_1",
            "title": "结论",
            "markdown_body": "综合来看，合肥低空经济产业规模处于全国前列。",
            "paragraphs": [],
        }
    ]
    claims = [{"claim_id": "c1", "text": "合肥低空经济产业规模处于全国前列", "evidence_ids": []}]
    mapping = _annotate_draft_paragraph_mapping(
        sections=sections, claims=claims, evidence=[]
    )
    assert "c1" in mapping["sections"][0]["paragraphs"][0]["claim_ids"]
    assert mapping["unused_claim_ids"] == []


def test_research_gap_no_reliable_evidence():
    plan = _sample_plan()
    contract = compile_research_contract(plan)
    # no evidence at all -> every slot is no_reliable_evidence
    gaps = _build_research_gaps(
        contract=contract, evidence=[], src_family_by_id={}
    )
    slot_ids = {g["slot_id"] for g in gaps}
    assert "dim_policy.policy_document.policy_basis" in slot_ids
    gap = next(g for g in gaps if g["slot_id"] == "dim_policy.policy_document.policy_basis")
    assert gap["gap_type"] == "no_reliable_evidence"
    assert gap["reportability"] == "pending_coverage_review"
    assert gap["approved_report_expression"] is None
    # candidate is scoped to COLLECTED evidence, not "公开渠道暂未发现"
    assert "当前已收集证据中未包含" in gap["candidate_report_expression"]
    assert "公开渠道暂未发现" not in gap["candidate_report_expression"]


def test_research_gap_missing_fields_when_evidence_has_no_key_fields():
    plan = _sample_plan()
    contract = compile_research_contract(plan)
    # execution slot needs amount/stage etc.; evidence provides none of them
    evidence = [_ev("e1", "tender_procurement")]
    src_family_by_id = _family_map_for(*evidence)
    gaps = _build_research_gaps(
        contract=contract, evidence=evidence, src_family_by_id=src_family_by_id
    )
    gap = next(
        g for g in gaps
        if g["slot_id"] == "dim_policy.tender_procurement.tender_evidence"
    )
    assert gap["gap_type"] == "missing_fields"
    assert gap["missing_fields"]


def test_research_gap_contradiction_from_conflicting_limitations():
    plan = _sample_plan()
    contract = compile_research_contract(plan)
    evidence = [
        {
            "evidence_id": "e1",
            "source_id": "src_e1",
            "source_family": "policy_document",
            "limitations": ["不同口径数据存在矛盾，签约状态不一致"],
        }
    ]
    src_family_by_id = _family_map_for(*evidence)
    gaps = _build_research_gaps(
        contract=contract, evidence=evidence, src_family_by_id=src_family_by_id
    )
    gap = next(g for g in gaps if g["gap_type"] == "contradiction")
    assert gap["slot_id"] == "dim_policy.policy_document.policy_basis"
    assert "不一致表述" in gap["candidate_report_expression"]


def test_research_gap_not_generated_for_satisfied_slot():
    plan = _sample_plan()
    contract = compile_research_contract(plan)
    # statistics slot: give full evidence with all key fields
    evidence = [
        {
            "evidence_id": "e1",
            "source_id": "src_s1",
            "source_family": "statistics",
            "metric": "GDP",
            "value": "8%",
            "region": "合肥",
            "time_ref": "2023",
        }
    ]
    src_family_by_id = {"src_s1": "statistics"}
    gaps = _build_research_gaps(
        contract=contract, evidence=evidence, src_family_by_id=src_family_by_id
    )
    stats_gaps = [g for g in gaps if "statistics" in g["slot_id"]]
    assert stats_gaps == []


def test_paragraph_mapping_preserves_existing_paragraphs():
    sections = [
        {
            "section_id": "sec_1",
            "title": "政策主线",
            "markdown_body": "正文 [ev_1]",
            "paragraphs": [
                {"paragraph_id": "sec_1.p1", "text": "已有段落 [ev_1]", "claim_ids": ["c1"]}
            ],
        }
    ]
    claims = [{"claim_id": "c1", "text": "已有断言", "evidence_ids": ["ev_1"]}]
    evidence = [{"evidence_id": "ev_1"}]
    mapping = _annotate_draft_paragraph_mapping(
        sections=sections, claims=claims, evidence=evidence
    )
    para = mapping["sections"][0]["paragraphs"][0]
    assert para["paragraph_id"] == "sec_1.p1"
    assert "ev_1" in para["evidence_ids"]
    assert "c1" in para["claim_ids"]
