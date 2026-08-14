"""Phase C.1 — Claim-Constrained StructuredDraft (shadow) tests.

Covers the user's 10+ cases:
  input filtering 1-3, draft binding 4, validator integrity 5-6,
  writing boundary 7-10, plus readiness capping, blocked-section stance,
  and non-interference with the formal report.
"""

from __future__ import annotations

from dataclasses import replace

from packages.research_harness.eval_persistence import (
    RunEvaluationStore,
    build_evaluable_coverage_report,
)
from packages.research_harness.gap_retrieval import derive_gaps
from packages.research_harness.structured_draft import (
    DraftParagraph,
    build_structured_shadow_draft,
    compile_editor1_input,
    run_structured_shadow,
    validate_structured_draft,
)


def _store(*, critical_unsatisfied: bool = False) -> RunEvaluationStore:
    store = RunEvaluationStore("run")
    store.record_claim_slots([{
        "slot_id": "s1", "section_id": "sec", "criticality": "required",
        "min_evidence_items": 2, "min_raw_supporting_sources": 2,
        "field_requirements": {"mandatory": [], "any_of": ["operation_status"]},
        "source_obligations": {"required_families": ["government"],
                               "primary_source_required": True},
    }])
    store.record_search_event({
        "search_event_id": "se1", "run_id": "run", "slot_ids": ["s1"],
        "query": "q", "source_family": "government", "provider": "anysearch",
        "status": "completed", "result_count": 1, "accepted_source_ids": ["a"],
        "schema_version": "search_event_v1",
    })
    store.record_evidence_unit({
        "evidence_id": "ev1", "run_id": "run", "source_id": "a",
        "source_family": "government", "supports_slot_ids": ["s1"],
        "key_fields": {"operation_status": {"status": "present", "value": "投运"}},
        "key_field_extraction_status": "completed", "schema_version": "evidence_unit_v2",
    })
    store.record_evidence_unit({
        "evidence_id": "ev2", "run_id": "run", "source_id": "b",
        "source_family": "government", "supports_slot_ids": ["s1"],
        "key_fields": {"operation_status": {"status": "present", "value": "投运"}},
        "key_field_extraction_status": "completed", "schema_version": "evidence_unit_v2",
    })
    # orphan evidence referenced by nothing approved
    store.record_evidence_unit({
        "evidence_id": "ev_orphan", "run_id": "run", "source_id": "c",
        "source_family": "government", "supports_slot_ids": ["s1"],
        "key_fields": {"operation_status": {"status": "present", "value": "投运"}},
        "key_field_extraction_status": "completed", "schema_version": "evidence_unit_v2",
    })
    store.record_claim_card({
        "claim_id": "c1", "primary_slot_id": "s1", "slot_ids": ["s1"],
        "evidence_ids": ["ev1"], "claim_type": "factual",
        "epistemic_status": "supported", "assertion_level": "supported",
        "max_allowed_assertion_level": "supported",
        "approval_status": "approved", "limitations": ["未披露日均运营架次"],
        "text": "合肥低空物流项目已投入运营。",
        "idempotency_key": "claim:c1", "schema_version": "claim_card_v1",
    })
    store.record_claim_card({
        "claim_id": "c2", "primary_slot_id": "s1", "slot_ids": ["s1"],
        "evidence_ids": ["ev_orphan"], "claim_type": "factual",
        "epistemic_status": "unsupported", "assertion_level": "mentioned",
        "max_allowed_assertion_level": "observed",
        "approval_status": "pending", "limitations": [],
        "text": "合肥低空物流项目投资额约1.2亿元。",
        "idempotency_key": "claim:c2", "schema_version": "claim_card_v1",
    })
    store.record_claim_card({
        "claim_id": "c3", "primary_slot_id": "s1", "slot_ids": ["s1"],
        "evidence_ids": ["ev2"], "claim_type": "factual",
        "epistemic_status": "supported", "assertion_level": "supported",
        "max_allowed_assertion_level": "confirmed",
        "approval_status": "approved", "limitations": [],
        "text": "该项目已由官方渠道公示中标结果。",
        "idempotency_key": "claim:c3", "schema_version": "claim_card_v1",
    })
    return store


def _coverage_and_gaps(store):
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)
    return report, gaps


# ── 1-3. input filtering ────────────────────────────────────────────────────

def test_only_approved_claims_enter_editor1_input():
    store = _store()
    report, gaps = _coverage_and_gaps(store)
    ei = compile_editor1_input(store=store, coverage_report=report, research_gaps=gaps)
    ids = {c["claim_id"] for c in ei.approved_claim_cards}
    assert ids == {"c1", "c3"}  # c2 (pending) excluded


def test_non_approved_claims_are_filtered():
    store = _store()
    report, gaps = _coverage_and_gaps(store)
    ei = compile_editor1_input(store=store, coverage_report=report, research_gaps=gaps)
    assert all(c["approval_status"] == "approved" for c in ei.approved_claim_cards)


def test_evidence_not_referenced_by_approved_claims_excluded():
    store = _store()
    report, gaps = _coverage_and_gaps(store)
    ei = compile_editor1_input(store=store, coverage_report=report, research_gaps=gaps)
    referenced = {e["evidence_id"] for e in ei.referenced_evidence_units}
    # ev_orphan is only referenced by the pending claim c2 -> excluded
    assert referenced == {"ev1", "ev2"}
    assert "ev_orphan" not in referenced


# ── 4. paragraph binds claim + evidence ─────────────────────────────────────

def test_paragraph_binds_claim_and_evidence():
    store = _store()
    report, gaps = _coverage_and_gaps(store)
    ei = compile_editor1_input(store=store, coverage_report=report, research_gaps=gaps)
    draft = build_structured_shadow_draft(ei, run_id="run")
    factual = [p for s in draft.sections for p in s.paragraphs if p.paragraph_role == "factual"]
    assert factual
    for p in factual:
        assert p.claim_ids and p.evidence_ids
    # every referenced evidence belongs to the bound claim
    claim_map = {c["claim_id"]: set(c["evidence_ids"]) for c in ei.approved_claim_cards}
    for p in factual:
        for cid in p.claim_ids:
            assert set(p.evidence_ids) == claim_map[cid]


# ── 5-6. validator integrity ────────────────────────────────────────────────

def test_validator_rejects_unknown_claim_id():
    store = _store()
    report, gaps = _coverage_and_gaps(store)
    ei = compile_editor1_input(store=store, coverage_report=report, research_gaps=gaps)
    draft = build_structured_shadow_draft(ei, run_id="run")
    bad = replace(draft.sections[0],
                  paragraphs=(
                      DraftParagraph(
                          paragraph_id="p:bad", text="x", claim_ids=("nope",),
                          evidence_ids=("ev1",), assertion_level="observed",
                          paragraph_role="factual"),
                  ))
    validation = validate_structured_draft(
        replace(draft, sections=(bad,)),
        claim_cards=store.claim_cards, evidence_units=store.evidence_units,
        coverage_report=report,
    )
    assert not validation.passed
    assert any(i.code == "unknown_claim_id" for i in validation.issues)


def test_validator_rejects_claim_evidence_mismatch():
    store = _store()
    report, gaps = _coverage_and_gaps(store)
    ei = compile_editor1_input(store=store, coverage_report=report, research_gaps=gaps)
    draft = build_structured_shadow_draft(ei, run_id="run")
    # c1 references ev1; bind ev2 (belongs to c3) -> mismatch
    bad = replace(draft.sections[0],
                  paragraphs=(
                      DraftParagraph(
                          paragraph_id="p:bad", text="x", claim_ids=("c1",),
                          evidence_ids=("ev2",), assertion_level="supported",
                          paragraph_role="factual"),
                  ))
    validation = validate_structured_draft(
        replace(draft, sections=(bad,)),
        claim_cards=store.claim_cards, evidence_units=store.evidence_units,
        coverage_report=report,
    )
    assert not validation.passed
    assert any(i.code == "evidence_not_referenced_by_claim" for i in validation.issues)


# ── 7-10. writing boundary ──────────────────────────────────────────────────

def test_validator_rejects_assertion_escalation():
    store = _store()
    report, gaps = _coverage_and_gaps(store)
    ei = compile_editor1_input(store=store, coverage_report=report, research_gaps=gaps)
    draft = build_structured_shadow_draft(ei, run_id="run")
    # c1 max_allowed = supported -> escalate to confirmed
    bad = replace(draft.sections[0],
                  paragraphs=(
                      DraftParagraph(
                          paragraph_id="p:bad", text="x", claim_ids=("c1",),
                          evidence_ids=("ev1",), assertion_level="confirmed",
                          paragraph_role="factual"),
                  ))
    validation = validate_structured_draft(
        replace(draft, sections=(bad,)),
        claim_cards=store.claim_cards, evidence_units=store.evidence_units,
        coverage_report=report,
    )
    assert not validation.passed
    assert any(i.code == "assertion_level_exceeded" for i in validation.issues)


def test_validator_rejects_dropped_limitation():
    store = _store()
    report, gaps = _coverage_and_gaps(store)
    ei = compile_editor1_input(store=store, coverage_report=report, research_gaps=gaps)
    draft = build_structured_shadow_draft(ei, run_id="run")
    # c1 limitation dropped from paragraph
    bad = replace(draft.sections[0],
                  paragraphs=(
                      DraftParagraph(
                          paragraph_id="p:bad", text="x", claim_ids=("c1",),
                          evidence_ids=("ev1",), assertion_level="supported",
                          limitations=(), paragraph_role="factual"),
                  ))
    validation = validate_structured_draft(
        replace(draft, sections=(bad,)),
        claim_cards=store.claim_cards, evidence_units=store.evidence_units,
        coverage_report=report,
    )
    assert not validation.passed
    assert any(i.code == "limitation_not_preserved" for i in validation.issues)


def test_validator_rejects_blocked_unknown_strong_conclusion():
    store = _store()
    report, gaps = _coverage_and_gaps(store)
    ei = compile_editor1_input(store=store, coverage_report=report, research_gaps=gaps)
    draft = build_structured_shadow_draft(ei, run_id="run")
    # force the section to blocked but keep a factual supported paragraph
    blocked = replace(draft.sections[0], readiness_at_write="blocked",
                      paragraphs=(
                          DraftParagraph(
                              paragraph_id="p:bad", text="x", claim_ids=("c1",),
                              evidence_ids=("ev1",), assertion_level="supported",
                              paragraph_role="factual"),
                      ))
    validation = validate_structured_draft(
        replace(draft, sections=(blocked,)),
        claim_cards=store.claim_cards, evidence_units=store.evidence_units,
        coverage_report=report,
    )
    assert not validation.passed
    assert any(i.code == "blocked_unknown_strong_conclusion" for i in validation.issues)


def test_validator_rejects_gap_unapproved_negative_assertion():
    store = _store()
    report, gaps = _coverage_and_gaps(store)
    ei = compile_editor1_input(store=store, coverage_report=report, research_gaps=gaps)
    draft = build_structured_shadow_draft(ei, run_id="run")
    gap_para = DraftParagraph(
        paragraph_id="gap:sec:0", text="相关项目尚未形成收入。",
        claim_ids=(), evidence_ids=(), assertion_level="observed",
        paragraph_role="gap_descriptive",
    )
    bad = replace(draft.sections[0], paragraphs=(gap_para,))
    validation = validate_structured_draft(
        replace(draft, sections=(bad,)),
        claim_cards=store.claim_cards, evidence_units=store.evidence_units,
        coverage_report=report,
    )
    assert not validation.passed
    assert any(i.code == "gap_unapproved_negative_assertion" for i in validation.issues)


# ── readiness capping / blocked stance ──────────────────────────────────────

def test_shadow_editor_caps_assertion_by_readiness():
    store = _store()
    report, gaps = _coverage_and_gaps(store)
    ei = compile_editor1_input(store=store, coverage_report=report, research_gaps=gaps)
    draft = build_structured_shadow_draft(ei, run_id="run")
    # section sec is ready (all satisfied) -> c1 keeps supported
    factual = {
        p.claim_ids[0]: p.assertion_level
        for s in draft.sections for p in s.paragraphs if p.paragraph_role == "factual"
    }
    assert factual["c1"] == "supported"
    assert factual["c3"] == "supported"  # capped by claim max too


def test_blocked_section_produces_only_gap_paragraph():
    # A critical unsatisfied slot -> section blocked -> no factual paragraph.
    store = RunEvaluationStore("run")
    store.record_claim_slots([{
        "slot_id": "s1", "section_id": "sec", "criticality": "critical",
        "min_evidence_items": 2, "min_raw_supporting_sources": 2,
        "field_requirements": {"mandatory": [], "any_of": []},
        "source_obligations": {"required_families": ["government"],
                               "primary_source_required": True},
    }])
    store.record_search_event({
        "search_event_id": "se1", "run_id": "run", "slot_ids": ["s1"],
        "query": "q", "source_family": "government", "provider": "anysearch",
        "status": "completed", "result_count": 1, "accepted_source_ids": ["a"],
        "schema_version": "search_event_v1",
    })
    store.record_evidence_unit({
        "evidence_id": "ev1", "run_id": "run", "source_id": "a",
        "source_family": "government", "supports_slot_ids": ["s1"],
        "key_fields": {"operation_status": {"status": "present", "value": "投运"}},
        "key_field_extraction_status": "completed", "schema_version": "evidence_unit_v2",
    })
    store.record_claim_card({
        "claim_id": "c1", "primary_slot_id": "s1", "slot_ids": ["s1"],
        "evidence_ids": ["ev1"], "claim_type": "factual",
        "epistemic_status": "unsupported", "assertion_level": "mentioned",
        "max_allowed_assertion_level": "observed",
        "approval_status": "approved", "limitations": [],
        "text": "该项目处于早期阶段。",
        "idempotency_key": "claim:c1", "schema_version": "claim_card_v1",
    })
    report, gaps = _coverage_and_gaps(store)
    assert report["slot_reports"][0]["status"] == "unsatisfied"  # critical -> blocked
    ei = compile_editor1_input(store=store, coverage_report=report, research_gaps=gaps)
    draft = build_structured_shadow_draft(ei, run_id="run")
    assert draft.sections[0].readiness_at_write == "blocked"
    roles = {p.paragraph_role for p in draft.sections[0].paragraphs}
    assert roles == {"gap_descriptive"}
    # no factual paragraph -> the approved claim goes to unused
    assert "c1" in draft.unused_claim_ids


# ── non-interference ────────────────────────────────────────────────────────

def test_shadow_pipeline_does_not_touch_formal_report_or_store():
    store = _store()
    before = store.to_dict()
    report, gaps = _coverage_and_gaps(store)
    shadow = run_structured_shadow(
        store=store, coverage_report=report, research_gaps=gaps, run_id="run",
    )
    # store untouched (compiler/editor/validator are pure reads)
    assert store.to_dict() == before
    # shadow draft + validation produced, but nothing writes a formal report
    assert shadow["draft"]["schema_version"] == "structured_draft_v1"
    assert "sections" in shadow["draft"]
    assert shadow["validation"]["passed"] is True
    # approved input filtering recorded
    assert shadow["editor1_input"]["approved_claim_count"] == 2
    assert shadow["editor1_input"]["referenced_evidence_count"] == 2
