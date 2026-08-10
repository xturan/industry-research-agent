"""Phase B.3 — Gap Retrieval tests (B.3.1 derivation + B.3.2 action proposal).

Covers: gap-type derivation (evidence/field/family/primary), EvaluationGap for
not_evaluable (never a ResearchGap), deterministic action queries + dedup,
unsatisfied->satisfied snapshot diff, no-new-evidence exhaustion, and
non-interference (records are immutable; nothing mutates store/coverage).
"""

from __future__ import annotations

from packages.research_harness.eval_persistence import (
    RunEvaluationStore,
    build_evaluable_coverage_report,
)
from packages.research_harness.gap_retrieval import (
    build_snapshot_diff,
    derive_gaps,
    propose_search_actions,
)

MERGE_EVIDENCE = {
    "evidence_id": "ev", "run_id": "run", "source_id": "src",
    "source_family": "government", "source_family_status": "classified",
    "supports_slot_ids": ["project.operation_status"],
}


def _slot(**kw) -> dict:
    base = {
        "slot_id": "project.operation_status", "section_id": "s",
        "criticality": "required", "min_evidence_items": 2,
        "min_raw_supporting_sources": 2,
        "field_requirements": {
            "mandatory": ["operation_status", "operation_date"], "any_of": [],
        },
        "source_obligations": {
            "required_families": ["government"], "primary_source_required": True,
        },
    }
    base.update(kw)
    return base


def _ev(*, eid: str, sid: str, field_status: dict, extraction: str = "completed") -> dict:
    return {
        **MERGE_EVIDENCE,
        "evidence_id": eid, "source_id": sid,
        "key_fields": {
            k: {"status": v, "value": "x" if v == "present" else None}
            for k, v in field_status.items()
        },
        "key_field_extraction_status": extraction,
    }


def _store(slot=None, *, events=(), evidence=(), cards=()) -> RunEvaluationStore:
    store = RunEvaluationStore("run")
    store.record_claim_slots([slot or _slot()])
    for e in events:
        store.record_search_event(e)
    for ev in evidence:
        store.record_evidence_unit(ev)
    for c in cards:
        store.record_claim_card(c)
    return store


def _completed_event() -> dict:
    return {
        "search_event_id": "se_1", "run_id": "run",
        "slot_ids": ["project.operation_status"], "query": "q",
        "source_family": "government", "status": "completed",
    }


# ── 1-4. ResearchGap types (unsatisfied slots) ──────────────────────────────

def test_gap_evidence_count():
    store = _store(events=[_completed_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                     "operation_date": "present"}),
    ])
    report = build_evaluable_coverage_report(store)
    gaps, egaps = derive_gaps(report, store)
    assert report["slot_reports"][0]["status"] == "unsatisfied"
    assert any(g.gap_type == "evidence_count" for g in gaps)
    assert not egaps


def test_gap_mandatory_field_missing():
    store = _store(events=[_completed_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                     "operation_date": "not_found"}),
        _ev(eid="ev2", sid="b", field_status={"operation_status": "present",
                                     "operation_date": "not_found"}),
    ])
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)
    assert any(
        g.gap_type == "mandatory_field_missing"
        and g.missing_fields == ("operation_date",) for g in gaps
    )


def test_gap_source_family_missing():
    store = _store(events=[_completed_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                     "operation_date": "present"}),
    ])
    # force family mismatch: evidence family not in required_families
    for e in store.evidence_units.values():
        e["source_family"] = "commercial_media"  # noqa: E501
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)
    assert any(g.gap_type == "source_family_missing" for g in gaps)


def test_gap_primary_source_missing():
    store = _store(events=[_completed_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                     "operation_date": "present"}),
    ])
    for e in store.evidence_units.values():
        e["source_family"] = "commercial_media"  # noqa: E501
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)
    assert any(g.gap_type == "primary_source_missing" for g in gaps)


# ── 5. not_evaluable -> EvaluationGap, never ResearchGap ────────────────────

def test_not_evaluable_generates_evaluation_gap_only():
    store = _store(events=[], evidence=[])
    report = build_evaluable_coverage_report(store)
    gaps, egaps = derive_gaps(report, store)
    assert report["slot_reports"][0]["status"] == "not_evaluable"
    assert gaps == []
    assert len(egaps) == 1
    assert egaps[0].reason == "search_not_executed"
    assert egaps[0].suggested_repair_action == "execute_existing_task"


# ── 6-8. Action generation + dedup ──────────────────────────────────────────

def test_action_missing_field_query():
    store = _store(events=[_completed_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                     "operation_date": "not_found"}),
        _ev(eid="ev2", sid="b", field_status={"operation_status": "present",
                                     "operation_date": "not_found"}),
    ])
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)
    actions = propose_search_actions(gaps, store, base_query="合肥低空物流项目")
    assert actions
    field_actions = [a for a in actions if a.action_type == "search_missing_field"]
    assert field_actions
    assert "投运时间" in field_actions[0].query


def test_action_missing_family_query():
    store = _store(events=[_completed_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                     "operation_date": "present"}),
    ])
    for e in store.evidence_units.values():
        e["source_family"] = "commercial_media"  # noqa: E501
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)
    actions = propose_search_actions(gaps, store, base_query="合肥低空物流项目")
    fam_actions = [a for a in actions if a.action_type == "search_missing_source_family"]
    assert fam_actions
    assert fam_actions[0].target_source_family == "government"


def test_action_idempotent_dedup():
    store = _store(events=[_completed_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                     "operation_date": "not_found"}),
    ])
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)
    a1 = propose_search_actions(gaps, store, base_query="q")
    # same gaps, same store -> same action ids (idempotent)
    a2 = propose_search_actions(gaps, store, base_query="q")
    assert [x.action_id for x in a1] == [x.action_id for x in a2]
    # already-executed query is dropped
    executed = {x.query.lower() for x in a1}
    a3 = propose_search_actions(gaps, store, base_query="q", executed_queries=executed)
    assert a3 == []


# ── 9. unsatisfied -> satisfied snapshot diff ───────────────────────────────

def test_backfill_resolves_slot():
    store = _store(events=[_completed_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                     "operation_date": "present"}),
    ])
    before = build_evaluable_coverage_report(store)
    # backfill: add second evidence
    store.record_evidence_unit(_ev(
        eid="ev2", sid="b",
        field_status={"operation_status": "present", "operation_date": "present"},
    ))
    after = build_evaluable_coverage_report(store)
    assert before["slot_reports"][0]["status"] == "unsatisfied"
    assert after["slot_reports"][0]["status"] == "satisfied"
    diff = build_snapshot_diff(
        before, after, new_source_ids=["b"], new_evidence_ids=["ev2"],
        resolved_gap_ids=["gap:x"], remaining_gap_ids=[],
    )
    assert diff["slot_transitions"]["project.operation_status"]["after"] == "satisfied"
    assert diff["information_gain"]["new_evidence"] == 1


# ── 10. no-new-evidence exhaustion (no further actions) ─────────────────────

def test_no_new_evidence_yields_no_actions():
    store = _store(events=[_completed_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                     "operation_date": "not_found"}),
    ])
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)
    actions = propose_search_actions(gaps, store, base_query="q")
    # after a backfill that yields NO new evidence (all queries already executed)
    executed = {a.query.lower() for a in actions}
    again = propose_search_actions(gaps, store, base_query="q", executed_queries=executed)
    assert again == []


# ── non-interference: derive/propose never mutate store ─────────────────────

def test_gap_derivation_is_non_interfering():
    store = _store(events=[_completed_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                     "operation_date": "not_found"}),
    ])
    store_before = store.to_dict()
    report = build_evaluable_coverage_report(store)
    gaps, egaps = derive_gaps(report, store)
    propose_search_actions(gaps, store, base_query="q")
    assert store.to_dict() == store_before  # records immutable / store untouched
    # ResearchGap approved expression stays null (reportability not approved)
    for g in gaps:
        assert g.reportability_status == "not_reviewed"
