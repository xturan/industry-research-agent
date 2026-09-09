# ruff: noqa: E501
"""C.3.3 — Constrained Synthesis Layer tests.

16 cases: trigger compiler (1-6), synthesis validator closures (7-12),
evidence-gap builder (13-14), integration non-interference (15-16).
"""

from __future__ import annotations

from types import SimpleNamespace

from packages.research_harness.constrained_synthesis import (
    LLMSynthesisParagraph,
    SynthesisContract,
    SynthesisIssue,
    SynthesisTriggerInput,
    _extract_regions,
    _is_implementation,
    _is_policy,
    _is_scenario,
    _shares_theme,
    _year,
    build_claim_semantic_basis,
    build_evidence_gap_paragraph,
    compile_report_synthesis_triggers,
    compile_synthesis_triggers,
    select_semantic_evidence,
    validate_synthesis_paragraph,
)
from packages.research_harness.eval_persistence import (
    RunEvaluationStore,
    build_evaluable_coverage_report,
)
from packages.research_harness.gap_retrieval import derive_gaps
from packages.research_harness.structured_compare import run_structured_compare


def _claim(cid, text, *, slot="s1", family="policy_document", evidence=("ev1",),
           max_allowed="3", limitations=(), primary=None) -> dict:
    return {
        "claim_id": cid, "primary_slot_id": primary or slot, "slot_ids": [slot],
        "evidence_ids": list(evidence), "claim_type": "factual",
        "epistemic_status": "supported", "assertion_level": "supported",
        "max_allowed_assertion_level": max_allowed,
        "approval_status": "approved", "limitations": list(limitations), "text": text,
    }


def _slot(sid, family="policy_document", section="sec") -> dict:
    return {"slot_id": sid, "section_id": section, "source_family": family,
            "criticality": "required"}


def _ev(eid, family, cluster, span="") -> dict:
    return {"evidence_id": eid, "source_family": family, "content_cluster_id": cluster,
            "quoted_span": span, "quote_verification_status": "verified"}


def _trigger(claims, slots, evidence):
    slot_by_claim = {}
    for c in claims:
        slot_by_claim[c["claim_id"]] = slots.get(c["primary_slot_id"], {})
    return SynthesisTriggerInput(
        section_id="sec", claims=tuple(claims),
        slot_by_claim=slot_by_claim, evidence_map=evidence,
    )


# ── 1-6. Trigger Compiler ───────────────────────────────────────────────────

def test_policy_plus_implementation_triggers_transmission():
    slots = {"s1": _slot("s1", "policy_document"), "s2": _slot("s2", "tender_procurement")}
    ev = {"ev1": _ev("ev1", "policy_document", "c1"), "ev2": _ev("ev2", "tender_procurement", "c2")}
    t = _trigger([
        _claim("c_policy", "省级方案提出发展低空物流应用", slot="s1", evidence=("ev1",)),
        _claim("c_impl", "当地已开通跨城低空货运航线", slot="s2", evidence=("ev2",),
               family="tender_procurement"),
    ], slots, ev)
    contracts = compile_synthesis_triggers(t)
    assert any(c.synthesis_type == "policy_to_implementation" for c in contracts)
    c = next(c for c in contracts if c.synthesis_type == "policy_to_implementation")
    assert c.allowed_inference_code == "policy_direction_has_observed_implementation"


def test_only_policy_claim_does_not_trigger():
    slots = {"s1": _slot("s1", "policy_document")}
    t = _trigger([_claim("c1", "省级方案提出发展低空物流应用", slot="s1")], slots, {})
    assert compile_synthesis_triggers(t) == []


def test_single_project_claim_does_not_trigger_stage():
    slots = {"s1": _slot("s1", "tender_procurement")}
    t = _trigger([
        _claim("c1", "项目已正式投运", slot="s1", family="tender_procurement",
               evidence=()),
    ], slots, {})
    assert compile_synthesis_triggers(t) == []


def test_operation_scenario_limitation_triggers_stage():
    slots = {"s1": _slot("s1", "tender_procurement"),
             "s2": _slot("s2", "tender_procurement"),
             "s3": _slot("s3", "company_disclosure")}
    t = _trigger([
        _claim("c_op", "项目已正式投运", slot="s1", family="tender_procurement",
               evidence=()),
        _claim("c_sc", "已形成跨城物流应用场景", slot="s2", family="tender_procurement",
               evidence=()),
        _claim("c_lim", "尚未披露稳定运营频次和订单规模", slot="s3",
               family="company_disclosure", evidence=(), limitations=["尚未披露稳定运营频次"]),
    ], slots, {})
    contracts = compile_synthesis_triggers(t)
    c = next((c for c in contracts if c.synthesis_type == "implementation_to_stage"), None)
    assert c is not None
    assert c.max_assertion_level == "observed"
    assert "尚未披露稳定运营频次" in c.required_limitations


def test_different_family_and_cluster_triggers_corroboration():
    slots = {"s1": _slot("s1", "tender_procurement"),
             "s2": _slot("s2", "company_disclosure")}
    ev = {"ev1": _ev("ev1", "tender_procurement", "cluster_a", "正式投运"),
          "ev2": _ev("ev2", "company_disclosure", "cluster_b", "参与建设")}
    t = _trigger([
        _claim("c_a", "项目正式投运", slot="s1", evidence=("ev1",),
               family="tender_procurement", primary="s1"),
        _claim("c_b", "公司披露参与项目建设", slot="s1", evidence=("ev2",),
               family="company_disclosure", primary="s1"),
    ], slots, ev)
    contracts = compile_synthesis_triggers(t)
    assert any(c.synthesis_type == "cross_source_corroboration" for c in contracts)


def test_same_reprint_does_not_trigger_corroboration():
    slots = {"s1": _slot("s1", "tender_procurement"),
             "s2": _slot("s2", "company_disclosure")}
    ev = {"ev1": _ev("ev1", "tender_procurement", "same_cluster", "正式投运"),
          "ev2": _ev("ev2", "company_disclosure", "same_cluster", "参与建设")}
    t = _trigger([
        _claim("c_a", "项目正式投运", slot="s1", evidence=("ev1",),
               family="tender_procurement", primary="s1"),
        _claim("c_b", "公司披露参与项目", slot="s1", evidence=("ev2",),
               family="company_disclosure", primary="s1"),
    ], slots, ev)
    contracts = compile_synthesis_triggers(t)
    assert not any(c.synthesis_type == "cross_source_corroboration" for c in contracts)


# ── fixture for validator tests ─────────────────────────────────────────────

_CONTRACT = SynthesisContract(
    synthesis_id="syn_sec_0", section_id="sec", target_section_id="sec",
    synthesis_type="implementation_to_stage",
    required_claim_ids=("c1", "c2"), allowed_evidence_ids=("ev1", "ev2"),
    allowed_inference_code="evidence_of_initial_implementation",
    max_assertion_level="observed", required_limitations=("尚未披露稳定运营频次",),
    forbidden_conclusions=("规模化商业运营",), trigger_reasons=("operation_status_present",),
)

_CLAIM_CARDS = {
    "c1": _claim("c1", "项目已正式投运", limitations=["尚未披露稳定运营频次"]),
    "c2": _claim("c2", "已形成跨城应用场景", slot="s2", family="tender_procurement"),
}
_EVIDENCE = {
    "ev1": _ev("ev1", "tender_procurement", "c_a", "2025年6月正式投运"),
    "ev2": _ev("ev2", "company_disclosure", "c_b", "跨城场景政府披露"),
}


def _valid_draft() -> LLMSynthesisParagraph:
    return LLMSynthesisParagraph(
        paragraph_role="synthesis", synthesis_id="syn_sec_0",
        text="现有证据说明相关应用已进入具体落地阶段。",
        claim_ids=["c1", "c2"], evidence_ids=["ev1", "ev2"],
        assertion_level="observed", limitations=["尚未披露稳定运营频次"],
        numeric_mentions=[],
    )


def _validate(draft) -> list[SynthesisIssue]:
    return validate_synthesis_paragraph(
        draft, contract=_CONTRACT, claim_cards=_CLAIM_CARDS, evidence_units=_EVIDENCE)


# ── 7-12. Validator closures ────────────────────────────────────────────────

def test_synthesis_claim_outside_contract_rejected():
    d = _valid_draft().model_copy(update={"claim_ids": ["c1", "c_unknown"]})
    codes = {i.code for i in _validate(d)}
    assert "synthesis_claim_outside_contract" in codes


def test_synthesis_evidence_outside_contract_rejected():
    d = _valid_draft().model_copy(update={"evidence_ids": ["ev1", "ev_unknown"]})
    codes = {i.code for i in _validate(d)}
    assert "synthesis_evidence_outside_contract" in codes


def test_synthesis_new_entity_rejected():
    d = _valid_draft().model_copy(update={"text": "某科技公司已参与项目落地。"})
    codes = {i.code for i in _validate(d)}
    assert "unsupported_synthesis_entity" in codes


def test_synthesis_new_numeric_rejected():
    d = _valid_draft().model_copy(update={"numeric_mentions": [{"text": "9999亿元", "evidence_id": "ev1"}]})
    codes = {i.code for i in _validate(d)}
    assert "unsupported_numeric_mention" in codes


def test_synthesis_assertion_escalation_rejected():
    d = _valid_draft().model_copy(update={"assertion_level": "confirmed"})
    codes = {i.code for i in _validate(d)}
    assert "synthesis_assertion_exceeded" in codes


def test_synthesis_limitation_dropped_rejected():
    d = _valid_draft().model_copy(update={"limitations": []})
    codes = {i.code for i in _validate(d)}
    assert "synthesis_limitation_missing" in codes


# ── 13-14. Evidence Gap Paragraph Builder ───────────────────────────────────

def test_gap_paragraph_contains_missing_fields_and_searched_scope():
    gap = build_evidence_gap_paragraph(
        section_id="company_revenue", gap_ids=["gap_01", "gap_02"],
        searched_source_families=["company_disclosure", "exchange_announcement"],
        missing_fields=["project_revenue", "order_amount"],
        missing_source_families=[], available_partial_claim_ids=["claim_macro"],
    )
    assert "company_disclosure" in gap.text
    assert "project_revenue" in gap.text
    assert "order_amount" in gap.text
    assert "无法判断" in gap.text
    assert "行业政策和宏观市场背景" in gap.text


def test_gap_paragraph_avoids_negative_assertions():
    gap = build_evidence_gap_paragraph(
        section_id="s", gap_ids=["g"], searched_source_families=["company_disclosure"],
        missing_fields=["project_revenue"], missing_source_families=[],
        available_partial_claim_ids=[],
    )
    for forbidden in ("没有", "未形成", "不存在", "尚未形成"):
        assert forbidden not in gap.text


# ── 15-16. Integration non-interference ─────────────────────────────────────

def _integration_store() -> RunEvaluationStore:
    store = RunEvaluationStore("run")
    store.record_claim_slots([_slot("s1", "policy_document"), _slot("s2", "tender_procurement")])
    for sid in ("s1", "s2"):
        store.record_search_event({
            "search_event_id": f"se_{sid}", "run_id": "run", "slot_ids": [sid],
            "query": sid, "source_family": "policy_document" if sid == "s1" else "tender_procurement",
            "provider": "anysearch", "status": "completed", "result_count": 1,
            "accepted_source_ids": [f"a_{sid}"], "schema_version": "search_event_v1",
        })
    store.record_evidence_unit({
        "evidence_id": "ev1", "run_id": "run", "source_id": "a_s1",
        "source_family": "policy_document", "supports_slot_ids": ["s1"],
        "quoted_span": "省级方案提出发展低空物流应用", "quote_verification_status": "verified",
        "key_fields": {}, "key_field_extraction_status": "completed",
        "schema_version": "evidence_unit_v2",
    })
    store.record_evidence_unit({
        "evidence_id": "ev2", "run_id": "run", "source_id": "a_s2",
        "source_family": "tender_procurement", "supports_slot_ids": ["s2"],
        "quoted_span": "跨城货运航线已开通", "quote_verification_status": "verified",
        "key_fields": {}, "key_field_extraction_status": "completed",
        "schema_version": "evidence_unit_v2",
    })
    store.record_claim_card(_claim("c_policy", "省级方案提出发展低空物流应用", slot="s1",
                                  evidence=("ev1",), family="policy_document"))
    store.record_claim_card(_claim("c_impl", "当地已开通跨城低空货运航线", slot="s2",
                                   evidence=("ev2",), family="tender_procurement"))
    return store


class _RoutingLLM:
    """Returns a valid factual section OR a valid synthesis paragraph."""

    def __call__(self, system, user):
        if "synthesis_type" in user:
            return {
                "paragraph_role": "synthesis", "synthesis_id": "syn_sec_0",
                "text": "政策提出的低空物流应用方向已在跨城货运航线中出现具体落地案例。",
                "claim_ids": ["c_policy", "c_impl"],
                "evidence_ids": ["ev1", "ev2"],
                "assertion_level": "supported", "limitations": [], "numeric_mentions": [],
            }
        return {
            "section_id": "sec", "title": "项目",
            "paragraphs": [{
                "paragraph_role": "factual", "text": "项目已进入落地阶段。",
                "claim_ids": ["c_policy"], "evidence_ids": ["ev1"],
                "assertion_level": "supported", "limitations": [], "numeric_mentions": [],
            }],
        }


def test_synthesis_failure_does_not_affect_factual_paragraphs():
    store = _integration_store()
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)
    result = run_structured_compare(
        store=store, coverage_report=report, research_gaps=gaps,
        legacy_markdown="政策与落地。", llm_call=_RoutingLLM(), run_id="syn_integ",
        use_fewshot=False, use_synthesis=True,
    )
    draft = result["draft"]
    factual = [p for s in draft["sections"] for p in s["paragraphs"] if p["paragraph_role"] == "factual"]
    synthesis = [p for s in draft["sections"] for p in s["paragraphs"] if p["paragraph_role"] == "synthesis"]
    assert factual  # factual preserved
    assert synthesis  # synthesis appended
    assert result["synthesis_meta"]  # synthesis meta recorded


def test_legacy_formal_output_unchanged_with_synthesis():
    store = _integration_store()
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)
    legacy = "政策与落地。"
    result = run_structured_compare(
        store=store, coverage_report=report, research_gaps=gaps,
        legacy_markdown=legacy, llm_call=_RoutingLLM(), run_id="syn_integ2",
        use_fewshot=False, use_synthesis=True,
    )
    assert result["legacy_markdown"] == legacy  # formal unchanged
    assert result["mode"] == "structured_compare"


# ── C.3.3.1 cross-section report-level trigger tests ────────────────────────

def _si(section_id: str, claims: list, readiness: str = "ready"):
    return SimpleNamespace(section_id=section_id, readiness=readiness, claim_cards=claims)


def _report_triggers(section_inputs, slot_by_id, evidence):
    return compile_report_synthesis_triggers(
        section_inputs, slot_by_id=slot_by_id, evidence_map=evidence)


def _slots_for(*pairs):
    return {sid: _slot(sid, family) for sid, family in pairs}


def _c(cid, text, *, slot, family, evidence=("ev1",), limitations=()):
    return _claim(cid, text, slot=slot, family=family, evidence=evidence,
                  limitations=list(limitations), primary=slot)


def test_province_policy_plus_city_impl_same_theme_triggers():
    ev = {"ev1": _ev("ev1", "policy_document", "c1", "安徽政策"), "ev2": _ev("ev2", "tender_procurement", "c2", "合肥项目")}
    slots = _slots_for(("p", "policy_document"), ("b", "tender_procurement"))
    sis = [
        _si("sec_policy", [_c("c_policy", "安徽省2024年提出发展低空物流应用", slot="p", family="policy_document", evidence=("ev1",))]),
        _si("sec_build", [_c("c_impl", "合肥已开通跨城低空货运航线", slot="b", family="tender_procurement", evidence=("ev2",))]),
    ]
    contracts = _report_triggers(sis, slots, ev)
    cross = [c for c in contracts if c.synthesis_type == "policy_to_implementation" and c.section_id == "_report"]
    assert len(cross) == 1
    assert cross[0].target_section_id == "sec_build"
    assert set(cross[0].required_claim_ids) == {"c_policy", "c_impl"}
    assert cross[0].allowed_inference_code == "policy_direction_has_observed_implementation"


def test_different_region_does_not_trigger():
    ev = {"ev1": _ev("ev1", "policy_document", "c1", "广东政策"), "ev2": _ev("ev2", "tender_procurement", "c2", "合肥项目")}
    slots = _slots_for(("p", "policy_document"), ("b", "tender_procurement"))
    sis = [
        _si("sec_policy", [_c("c_policy", "广东省提出发展低空物流应用", slot="p", family="policy_document", evidence=("ev1",))]),
        _si("sec_build", [_c("c_impl", "合肥已开通跨城低空货运航线", slot="b", family="tender_procurement", evidence=("ev2",))]),
    ]
    contracts = _report_triggers(sis, slots, ev)
    assert not any(c.synthesis_type == "policy_to_implementation" and c.section_id == "_report" for c in contracts)


def test_policy_after_impl_only_alignment():
    ev = {"ev1": _ev("ev1", "policy_document", "c1", "政策"), "ev2": _ev("ev2", "tender_procurement", "c2", "项目")}
    slots = _slots_for(("p", "policy_document"), ("b", "tender_procurement"))
    sis = [
        _si("sec_policy", [_c("c_policy", "安徽省2025年提出发展低空物流应用", slot="p", family="policy_document", evidence=("ev1",))]),
        _si("sec_build", [_c("c_impl", "合肥2024年已开通跨城低空货运航线", slot="b", family="tender_procurement", evidence=("ev2",))]),
    ]
    contracts = _report_triggers(sis, slots, ev)
    cross = [c for c in contracts if c.synthesis_type == "policy_to_implementation" and c.section_id == "_report"]
    assert cross and cross[0].allowed_inference_code == "policy_direction_aligned_with_existing"


def test_different_theme_does_not_trigger():
    ev = {"ev1": _ev("ev1", "policy_document", "c1", "政策"), "ev2": _ev("ev2", "tender_procurement", "c2", "项目")}
    slots = _slots_for(("p", "policy_document"), ("b", "tender_procurement"))
    sis = [
        _si("sec_policy", [_c("c_policy", "建设低空制造产业园", slot="p", family="policy_document", evidence=("ev1",))]),
        _si("sec_build", [_c("c_impl", "开展消防无人机救援", slot="b", family="tender_procurement", evidence=("ev2",))]),
    ]
    contracts = _report_triggers(sis, slots, ev)
    assert not any(c.synthesis_type == "policy_to_implementation" and c.section_id == "_report" for c in contracts)


def test_cross_section_claims_in_same_contract():
    ev = {"ev1": _ev("ev1", "policy_document", "c1", "政策"), "ev2": _ev("ev2", "tender_procurement", "c2", "项目")}
    slots = _slots_for(("p", "policy_document"), ("b", "tender_procurement"))
    sis = [
        _si("sec_policy", [_c("c_policy", "安徽提出发展低空物流应用", slot="p", family="policy_document", evidence=("ev1",))]),
        _si("sec_build", [_c("c_impl", "合肥已开通跨城低空货运航线", slot="b", family="tender_procurement", evidence=("ev2",))]),
    ]
    contracts = _report_triggers(sis, slots, ev)
    cross = [c for c in contracts if c.section_id == "_report"][0]
    # claims from two different sections, evidence allowed = both claims' evidence
    assert cross.required_claim_ids == ("c_policy", "c_impl")
    assert set(cross.allowed_evidence_ids) == {"ev1", "ev2"}


def test_cross_section_contract_allows_only_original_claims():
    ev = {"ev1": _ev("ev1", "policy_document", "c1", "政策"), "ev2": _ev("ev2", "tender_procurement", "c2", "项目")}
    slots = _slots_for(("p", "policy_document"), ("b", "tender_procurement"))
    sis = [
        _si("sec_policy", [_c("c_policy", "安徽提出发展低空物流应用", slot="p", family="policy_document", evidence=("ev1",))]),
        _si("sec_build", [_c("c_impl", "合肥已开通跨城低空货运航线", slot="b", family="tender_procurement", evidence=("ev2",))]),
    ]
    contracts = _report_triggers(sis, slots, ev)
    cross = [c for c in contracts if c.section_id == "_report"][0]
    # validator still enforces closure
    from packages.research_harness.constrained_synthesis import LLMSynthesisParagraph
    bad = LLMSynthesisParagraph(
        paragraph_role="synthesis", synthesis_id=cross.synthesis_id, text="x",
        claim_ids=["c_policy", "c_unknown"], evidence_ids=["ev1"],
        assertion_level="observed", limitations=[], numeric_mentions=[],
    )
    issues = validate_synthesis_paragraph(
        bad, contract=cross, claim_cards={c["claim_id"]: c for s in sis for c in s.claim_cards},
        evidence_units=ev)
    assert any(i.code == "synthesis_claim_outside_contract" for i in issues)


def test_synthesis_inserted_into_target_section():
    ev = {"ev1": _ev("ev1", "policy_document", "c1", "政策"), "ev2": _ev("ev2", "tender_procurement", "c2", "项目")}
    slots = _slots_for(("p", "policy_document"), ("b", "tender_procurement"))
    sis = [
        _si("sec_policy", [_c("c_policy", "安徽提出发展低空物流应用", slot="p", family="policy_document", evidence=("ev1",))]),
        _si("sec_build", [_c("c_impl", "合肥已开通跨城低空货运航线", slot="b", family="tender_procurement", evidence=("ev2",))]),
    ]
    contracts = _report_triggers(sis, slots, ev)
    cross = [c for c in contracts if c.section_id == "_report"][0]
    assert cross.target_section_id == "sec_build"  # NOT sec_policy


def test_no_duplicate_cross_section_contract_for_same_pair():
    ev = {"ev1": _ev("ev1", "policy_document", "c1", "政策"), "ev2": _ev("ev2", "tender_procurement", "c2", "项目")}
    slots = _slots_for(("p", "policy_document"), ("b", "tender_procurement"))
    sis = [
        _si("sec_policy", [_c("c_policy", "安徽提出发展低空物流应用", slot="p", family="policy_document", evidence=("ev1",))]),
        _si("sec_build", [_c("c_impl", "合肥已开通跨城低空货运航线", slot="b", family="tender_procurement", evidence=("ev2",))]),
    ]
    contracts = _report_triggers(sis, slots, ev)
    cross = [c for c in contracts if c.section_id == "_report"]
    assert len(cross) == 1  # single policy x single impl -> exactly one contract


def test_cross_section_synthesis_leaves_legacy_unchanged():
    store = _integration_store()
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)
    legacy = "政策与落地。"
    result = run_structured_compare(
        store=store, coverage_report=report, research_gaps=gaps,
        legacy_markdown=legacy, llm_call=_RoutingLLM(), run_id="xs_integ",
        use_fewshot=False, use_synthesis=True,
    )
    assert result["legacy_markdown"] == legacy
    assert result["mode"] == "structured_compare"


# ── C.3.3.3 Claim Semantic Basis Fallback tests ─────────────────────────────

def _no_text_claim(cid, evidence, family="tender_procurement"):
    return _claim(cid, "", slot="s1", family=family, evidence=evidence,
                  primary="s1", max_allowed="3")


def _verified_ev(eid, span, cluster="cl", family="tender_procurement",
                 verified=True, slot="s1"):
    e = _ev(eid, family, cluster, span)
    e["quote_verification_status"] = "verified" if verified else "not_verified"
    e["supports_slot_ids"] = [slot]
    return e


# 1. non-empty claim text is used as-is
def test_non_empty_claim_text_used_as_is():
    claim = _claim("c1", "项目已投运")
    basis = build_claim_semantic_basis(claim, {"ev1": _verified_ev("ev1", "其他内容")})
    assert basis.source == "claim_text"
    assert basis.fallback_used is False
    assert basis.text == "项目已投运"


# 2. empty text + verified evidence -> fallback
def test_empty_text_with_verified_evidence_falls_back():
    claim = _no_text_claim("c1", ["ev1"])
    ev = {"ev1": _verified_ev("ev1", "跨城货运航线正式启用")}
    basis = build_claim_semantic_basis(claim, ev)
    assert basis.source == "verified_evidence_fallback"
    assert basis.fallback_used is True
    assert "航线" in basis.text
    assert "CLAIM_TEXT_EMPTY_USING_VERIFIED_EVIDENCE" in basis.diagnostics


# 3. unverified evidence not used
def test_unverified_evidence_not_used():
    claim = _no_text_claim("c1", ["ev1"])
    ev = {"ev1": _verified_ev("ev1", "跨城货运航线正式启用", verified=False)}
    basis = build_claim_semantic_basis(claim, ev)
    assert basis.text == ""
    assert basis.fallback_used is False


# 4. evidence not in claim.evidence_ids not read
def test_evidence_outside_claim_not_read():
    claim = _no_text_claim("c1", ["ev1"])
    ev = {"ev1": _verified_ev("ev1", "航线A"), "ev_other": _verified_ev("ev_other", "航线B")}
    basis = build_claim_semantic_basis(claim, ev)
    assert basis.evidence_ids == ("ev1",)


# 5. max 2 evidence selected
def test_max_two_evidence_selected():
    claim = _no_text_claim("c1", ["ev1", "ev2", "ev3"])
    ev = {f"ev{i}": _verified_ev(f"ev{i}", f"航线{i}", cluster=f"cl{i}") for i in range(1, 4)}
    selected = select_semantic_evidence(claim, list(ev.values()), max_items=2)
    assert len(selected) == 2


# 6. same content cluster deduped
def test_same_content_cluster_dedup():
    claim = _no_text_claim("c1", ["ev1", "ev2"])
    ev = {"ev1": _verified_ev("ev1", "航线A", cluster="same"),
          "ev2": _verified_ev("ev2", "航线B", cluster="same")}
    selected = select_semantic_evidence(claim, list(ev.values()), max_items=2)
    assert len(selected) == 1


# 7-9. empty claim text + evidence fallback drives trigger detection
def test_evidence_fallback_detects_implementation():
    slots = {"s1": _slot("s1", "tender_procurement")}
    ev = {"ev1": _verified_ev("ev1", "合肥跨城低空货运航线正式启用")}
    c = _no_text_claim("c1", ["ev1"])
    basis = build_claim_semantic_basis(c, ev)
    trig = SynthesisTriggerInput(
        section_id="sec", claims=(c,), slot_by_claim={"c1": slots["s1"]},
        evidence_map=ev, semantic_basis={"c1": basis},
    )
    assert _is_implementation(trig, c) is True


def test_evidence_fallback_detects_policy():
    slots = {"s1": _slot("s1", "policy_document")}
    ev = {"ev1": _verified_ev("ev1", "省级方案提出发展低空物流应用", family="policy_document")}
    c = _no_text_claim("c_policy", ["ev1"], family="policy_document")
    basis = build_claim_semantic_basis(c, ev)
    trig = SynthesisTriggerInput(
        section_id="sec", claims=(c,), slot_by_claim={"c_policy": slots["s1"]},
        evidence_map=ev, semantic_basis={"c_policy": basis},
    )
    assert _is_policy(trig, c) is True


def test_evidence_fallback_detects_scenario():
    slots = {"s1": _slot("s1", "tender_procurement")}
    ev = {"ev1": _verified_ev("ev1", "政务应用航线及无人机场景已落地")}
    c = _no_text_claim("c_sc", ["ev1"])
    basis = build_claim_semantic_basis(c, ev)
    trig = SynthesisTriggerInput(
        section_id="sec", claims=(c,), slot_by_claim={"c_sc": slots["s1"]},
        evidence_map=ev, semantic_basis={"c_sc": basis},
    )
    assert _is_scenario(trig, c) is True


# 10. fallback extracts region / theme / time
def test_fallback_extracts_region_theme_time():
    ev = {"ev1": _verified_ev("ev1", "安徽省2024年提出发展低空物流应用", family="policy_document")}
    c = _no_text_claim("c_policy", ["ev1"], family="policy_document")
    basis = build_claim_semantic_basis(c, ev)
    assert "安徽" in _extract_regions(basis.text)
    assert _shares_theme(basis.text, "合肥已开通低空货运航线")
    assert _year(basis.text) == 2024


# 11. background evidence must not trigger implementation (non-impl slot + no keyword)
def test_background_evidence_not_implementation():
    slots = {"s1": _slot("s1", "industry_research")}
    # background: generic industry description without impl keyword
    ev = {"ev1": _verified_ev("ev1", "低空经济是战略性新兴产业，政策持续支持")}
    c = _no_text_claim("c1", ["ev1"], family="industry_research")
    basis = build_claim_semantic_basis(c, ev)
    trig = SynthesisTriggerInput(
        section_id="sec", claims=(c,), slot_by_claim={"c1": slots["s1"]},
        evidence_map=ev, semantic_basis={"c1": basis},
    )
    # non-impl family + fallback text has no impl keyword -> not implementation
    assert _is_implementation(trig, c) is False


# 12. advisory shadow evidence not in fallback
def test_backfill_shadow_evidence_not_in_fallback():
    claim = _no_text_claim("c1", ["ev1"])
    # shadow store evidence is not in evidence_by_id passed to the basis
    basis = build_claim_semantic_basis(claim, {"ev1": _verified_ev("ev1", "真实航线")})
    assert "shadow" not in basis.text
    assert basis.evidence_ids == ("ev1",)


# 13. fallback does not mutate the original claim card
def test_fallback_does_not_mutate_claim():
    claim = _no_text_claim("c1", ["ev1"])
    before = dict(claim)
    build_claim_semantic_basis(claim, {"ev1": _verified_ev("ev1", "航线")})
    assert claim == before


# 14. synthesis contract closure unchanged with fallback
def test_fallback_contract_closure_unchanged():
    ev = {"ev1": _verified_ev("ev1", "合肥已开通跨城低空货运航线"),
          "ev2": _verified_ev("ev2", "安徽省方案提出发展低空物流应用", family="policy_document")}
    sis = [
        _si("sec_policy", [_no_text_claim("c_policy", ["ev2"], family="policy_document")]),
        _si("sec_build", [_no_text_claim("c_impl", ["ev1"])]),
    ]
    # need slot map keyed by slot_id with families
    slot_map = {"p": _slot("p", "policy_document"), "b": _slot("b", "tender_procurement")}
    contracts = compile_report_synthesis_triggers(sis, slot_by_id=slot_map, evidence_map=ev)
    cross = [c for c in contracts if c.section_id == "_report"]
    assert cross and set(cross[0].required_claim_ids) == {"c_policy", "c_impl"}
    assert set(cross[0].allowed_evidence_ids) == {"ev1", "ev2"}


# 15. legacy formal output unchanged with fallback path
def test_legacy_unchanged_with_fallback():
    store = _integration_store()
    # clear claim texts to force fallback
    for c in store.claim_cards.values():
        c["text"] = ""
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)
    legacy = "政策与落地。"
    result = run_structured_compare(
        store=store, coverage_report=report, research_gaps=gaps,
        legacy_markdown=legacy, llm_call=_RoutingLLM(), run_id="fb_integ",
        use_fewshot=False, use_synthesis=True,
    )
    assert result["legacy_markdown"] == legacy
    assert result["mode"] == "structured_compare"


# 16. new store with claim text behaves same as before fix
def test_claim_text_priority_preserves_old_behavior():
    claim = _claim("c1", "项目已正式投运")
    ev = {"ev1": _verified_ev("ev1", "完全不同的内容")}
    basis = build_claim_semantic_basis(claim, ev)
    assert basis.source == "claim_text"
    assert basis.text == "项目已正式投运"
    assert basis.evidence_ids == ()


# ── C.3.3.4 negation-aware forbidden + number whitelist ─────────────────────

def _valid_fb_draft(text=None, numbers=None):
    return LLMSynthesisParagraph(
        paragraph_role="synthesis", synthesis_id="syn_sec_0",
        text=text or "现有证据说明相关应用已进入具体落地阶段。",
        claim_ids=["c1", "c2"], evidence_ids=["ev1", "ev2"],
        assertion_level="observed", limitations=["尚未披露稳定运营频次"],
        numeric_mentions=numbers or [],
    )


def test_negated_boundary_statement_is_allowed():
    # ev1 span has "2025年6月正式投运" -> allowed number "2025"
    draft = _valid_fb_draft(text="现有证据尚不足以判断其是否已经进入规模化商业运营阶段。")
    codes = {i.code for i in _validate(draft)}
    assert "positive_forbidden_assertion" not in codes  # negated boundary allowed


def test_positive_forbidden_assertion_flagged():
    draft = _valid_fb_draft(text="相关产业已经进入规模化商业运营阶段，形成成熟产业。")
    codes = {i.code for i in _validate(draft)}
    assert "positive_forbidden_assertion" in codes


def test_unsupported_number_in_body_flagged():
    draft = _valid_fb_draft(text="相关应用已落地，市场将达9999亿元。")
    codes = {i.code for i in _validate(draft)}
    assert "unsupported_numeric_mention" in codes


def test_allowed_number_passes():
    # ev1 span "2025年6月正式投运" -> "2025" is allowed
    draft = _valid_fb_draft(text="相关应用在2025年已进入具体落地阶段。",
                            numbers=[{"text": "2025", "evidence_id": "ev1"}])
    codes = {i.code for i in _validate(draft)}
    assert "unsupported_numeric_mention" not in codes


def test_forensics_captured_on_validation_failure():
    from packages.research_harness.constrained_synthesis import generate_synthesis_paragraph

    def bad_llm(system, user):
        return {
            "paragraph_role": "synthesis", "synthesis_id": "syn_sec_0",
            "text": "产业已进入规模化商业运营，市场将达9999亿元。",
            "claim_ids": ["c1", "c2"], "evidence_ids": ["ev1", "ev2"],
            "assertion_level": "observed", "limitations": [],
            "numeric_mentions": [{"text": "9999亿元", "evidence_id": "ev1"}],
        }

    _, status, _, forensics = generate_synthesis_paragraph(
        _CONTRACT, bad_llm, claim_cards=_CLAIM_CARDS, evidence_units=_EVIDENCE,
        max_retries=1)
    assert status == "validation_failed"
    assert forensics
    assert any(a.get("validation_issues") for a in forensics)
    # structured retry feedback references the issues
    assert any(a.get("raw_llm_output") for a in forensics)
