"""C.3.2 — Section–Claim Assignment tests.

12 cases: dedup, subsumption, multi-attribute, correct section, multi-slot,
required representative, optional background, conflict suppression,
satisfied-slot representative, suppressed reason, non-interference, ContextAudit.
"""

from __future__ import annotations

from packages.research_harness.eval_persistence import (
    RunEvaluationStore,
    build_evaluable_coverage_report,
)
from packages.research_harness.gap_retrieval import derive_gaps
from packages.research_harness.section_claim_assignment import (
    SectionClaimAssignment,
    assign_section_claims,
    build_context_audit,
)
from packages.research_harness.structured_draft import compile_editor1_input


def _slot(sid: str, section: str = "sec", criticality: str = "required") -> dict:
    return {
        "slot_id": sid, "section_id": section, "criticality": criticality,
        "min_evidence_items": 1, "min_raw_supporting_sources": 1,
        "field_requirements": {"mandatory": [], "any_of": ["operation_status"]},
        "source_obligations": {"required_families": ["government"],
                               "primary_source_required": True},
    }


def _store(slots: list[dict], claims: list[dict]) -> RunEvaluationStore:
    store = RunEvaluationStore("run")
    store.record_claim_slots(slots)
    for sid in {s["slot_id"] for s in slots}:
        store.record_search_event({
            "search_event_id": f"se_{sid}", "run_id": "run", "slot_ids": [sid],
            "query": sid, "source_family": "government", "provider": "anysearch",
            "status": "completed", "result_count": 1,
            "accepted_source_ids": [f"a_{sid}"], "schema_version": "search_event_v1",
        })
        store.record_evidence_unit({
            "evidence_id": f"ev_{sid}", "run_id": "run", "source_id": f"a_{sid}",
            "source_family": "government", "supports_slot_ids": [sid],
            "quoted_span": f"{sid}官方披露",
            "quote_verification_status": "verified",
            "key_fields": {"operation_status": {"status": "present", "value": "投运"}},
            "key_field_extraction_status": "completed",
            "schema_version": "evidence_unit_v2",
        })
    for c in claims:
        store.record_claim_card(c)
    return store


def _claim(sid: str, cid: str, text: str, *, slot_ids=None, epistemic="supported",
           max_allowed="3", extra=None) -> dict:
    base = {
        "claim_id": cid, "primary_slot_id": sid, "slot_ids": slot_ids or [sid],
        "evidence_ids": [f"ev_{sid}"], "claim_type": "factual",
        "epistemic_status": epistemic, "assertion_level": "supported",
        "max_allowed_assertion_level": max_allowed,
        "approval_status": "approved", "limitations": [], "text": text,
        "idempotency_key": f"claim:{cid}", "schema_version": "claim_card_v1",
    }
    if extra:
        base.update(extra)
    return base


def _assign(store: RunEvaluationStore) -> list[SectionClaimAssignment]:
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)
    ei = compile_editor1_input(store=store, coverage_report=report, research_gaps=gaps)
    return assign_section_claims(ei)


def _sec_assign(assignments, section: str) -> SectionClaimAssignment:
    return next(a for a in assignments if a.section_id == section)


# ── 1. same-fact same-slot dedup ────────────────────────────────────────────

def test_same_fact_same_slot_dedup():
    store = _store(
        [_slot("s1")],
        [_claim("s1", "c1", "项目已正式投运"),
         _claim("s1", "c2", "项目已经正式投运")],
    )
    a = _sec_assign(_assign(store), "sec")
    assert len(a.suppressed_claims) == 1
    assert a.suppressed_claims[0].reason in {"semantic_duplicate", "exact_duplicate"}
    assert len(a.required_claim_ids) + len(a.optional_claim_ids) == 1


# ── 2. more complete claim subsumes weaker one ──────────────────────────────

def test_more_complete_claim_subsumes_weaker():
    store = _store(
        [_slot("s1")],
        [_claim("s1", "c1", "项目已投运"),
         _claim("s1", "c2", "项目于2025年6月正式投运")],
    )
    a = _sec_assign(_assign(store), "sec")
    suppressed = {s.claim_id: s for s in a.suppressed_claims}
    assert "c1" in suppressed  # weaker one suppressed
    assert suppressed["c1"].reason == "subsumed"
    assert suppressed["c1"].suppressed_by_claim_id == "c2"


# ── 3. same entity different attribute kept ─────────────────────────────────

def test_same_entity_different_attribute_kept():
    store = _store(
        [_slot("s1"), _slot("s2")],
        [_claim("s1", "c1", "项目已投运"),
         _claim("s2", "c2", "项目中标公示")],
    )
    a = _sec_assign(_assign(store), "sec")
    # different slots/attributes -> both kept (not suppressed)
    assert a.suppressed_claims == ()
    assert {"c1", "c2"} <= set(a.required_claim_ids + a.optional_claim_ids)


# ── 4. claim assigned to the correct section ────────────────────────────────

def test_claim_assigned_to_correct_section():
    store = _store(
        [_slot("s1", section="secA"), _slot("s2", section="secB")],
        [_claim("s1", "c1", "项目已投运"),
         _claim("s2", "c2", "项目中标公示")],
    )
    assignments = _assign(store)
    secA = _sec_assign(assignments, "secA")
    secB = _sec_assign(assignments, "secB")
    assert "c1" in secA.required_claim_ids + secA.optional_claim_ids
    assert "c2" in secB.required_claim_ids + secB.optional_claim_ids
    assert "c1" not in secB.required_claim_ids + secB.optional_claim_ids


# ── 5. multi-slot claim may enter multiple sections ─────────────────────────

def test_multi_slot_claim_enters_multiple_sections():
    store = _store(
        [_slot("s1", section="secA"), _slot("s2", section="secB")],
        [_claim("s1", "c1", "项目已投运", slot_ids=["s1", "s2"])],
    )
    assignments = _assign(store)
    secA = _sec_assign(assignments, "secA")
    secB = _sec_assign(assignments, "secB")
    assert "c1" in secA.required_claim_ids + secA.optional_claim_ids
    assert "c1" in secB.required_claim_ids + secB.optional_claim_ids


# ── 6. critical slot representative is required ─────────────────────────────

def test_critical_slot_representative_is_required():
    store = _store(
        [_slot("s1", criticality="critical")],
        [_claim("s1", "c1", "项目已投运")],
    )
    a = _sec_assign(_assign(store), "sec")
    assert "c1" in a.required_claim_ids


# ── 7. background claim is optional ─────────────────────────────────────────

def test_background_claim_is_optional():
    # slot s2 unsatisfied (no search event) -> its representative stays optional
    store = RunEvaluationStore("run")
    store.record_claim_slots([_slot("s1", criticality="required")])
    store.record_search_event({
        "search_event_id": "se_s1", "run_id": "run", "slot_ids": ["s1"],
        "query": "s1", "source_family": "government", "provider": "anysearch",
        "status": "completed", "result_count": 1, "accepted_source_ids": ["a_s1"],
        "schema_version": "search_event_v1",
    })
    store.record_evidence_unit({
        "evidence_id": "ev_s1", "run_id": "run", "source_id": "a_s1",
        "source_family": "government", "supports_slot_ids": ["s1"],
        "quoted_span": "官方披露", "quote_verification_status": "verified",
        "key_fields": {}, "key_field_extraction_status": "completed",
        "schema_version": "evidence_unit_v2",
    })
    store.record_claim_card(_claim("s1", "c_required", "项目已投运"))
    # second claim, same slot, different status -> not deduped, and slot s1 has
    # only one required representative; the other becomes optional
    store.record_claim_card(_claim("s1", "c_other", "项目处于早期准备阶段"))
    a = _sec_assign(_assign(store), "sec")
    assert "c_required" in a.required_claim_ids
    assert "c_other" in a.optional_claim_ids


# ── 8. unresolved conflict suppressed ───────────────────────────────────────

def test_conflict_claim_suppressed():
    store = _store(
        [_slot("s1")],
        [_claim("s1", "c1", "项目已投运"),
         _claim("s1", "c_conflict", "项目已停摆", epistemic="contradicted")],
    )
    a = _sec_assign(_assign(store), "sec")
    suppressed = {s.claim_id: s for s in a.suppressed_claims}
    assert "c_conflict" in suppressed
    assert suppressed["c_conflict"].reason == "conflicting_claim"


# ── 9. every satisfied required slot has a representative ───────────────────

def test_satisfied_required_slot_has_representative():
    store = _store(
        [_slot("s1"), _slot("s2")],
        [_claim("s1", "c1", "项目已投运"),
         _claim("s2", "c2", "项目中标公示")],
    )
    a = _sec_assign(_assign(store), "sec")
    reps = a.slot_representatives
    assert "s1" in reps and "s2" in reps
    assert reps["s1"] in a.required_claim_ids
    assert reps["s2"] in a.required_claim_ids


# ── 10. suppressed claims carry a reason ────────────────────────────────────

def test_suppressed_claims_have_reason():
    store = _store(
        [_slot("s1")],
        [_claim("s1", "c1", "项目已正式投运"),
         _claim("s1", "c2", "项目已经正式投运")],
    )
    a = _sec_assign(_assign(store), "sec")
    assert a.suppressed_claims
    for s in a.suppressed_claims:
        assert s.reason  # controlled vocab, non-empty
        assert s.suppressed_by_claim_id


# ── 11. assignment does not mutate store ────────────────────────────────────

def test_assignment_does_not_mutate_store():
    store = _store(
        [_slot("s1")],
        [_claim("s1", "c1", "项目已投运"),
         _claim("s1", "c2", "项目已经正式投运")],
    )
    before = store.to_dict()
    _assign(store)
    assert store.to_dict() == before


# ── 12. ContextAudit statistics ─────────────────────────────────────────────

def test_context_audit_stats():
    store = _store(
        [_slot("s1"), _slot("s2")],
        [_claim("s1", "c1", "项目已投运", extra={"limitations": ["未披露日均架次"]}),
         _claim("s2", "c2", "项目中标公示")],
    )
    a = _sec_assign(_assign(store), "sec")
    referenced = {
        eid for cid in a.required_claim_ids + a.optional_claim_ids
        for eid in store.claim_cards[cid]["evidence_ids"]
    }
    audit = build_context_audit(
        a,
        evidence_units=store.evidence_units,
        referenced_evidence_ids=referenced,
        used_claim_ids=set(a.required_claim_ids + a.optional_claim_ids),
        claim_texts={cid: store.claim_cards[cid]["text"] for cid in store.claim_cards},
    )
    assert audit.claim_count_before_assignment >= 2
    assert audit.required_claim_count >= 1
    assert audit.suppressed_claim_count >= 0
    assert audit.provided_evidence_count == len(referenced)
    assert audit.estimated_context_tokens > 0
    assert audit.required_claim_usage_rate is not None
    # schema present
    assert audit.schema_version == "context_audit_v1"
