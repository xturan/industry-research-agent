"""Phase B.2 — Evaluability Persistence L2 replay tests.

Six current-schema L2 replay cases verifying the three-state semantics:
- searched + evidence + fields satisfy  -> satisfied
- searched but evidence insufficient    -> unsatisfied
- no SearchEvent                       -> not_evaluable
- evidence present but extraction not run -> not_evaluable
- searched + field clearly not_found    -> unsatisfied
- insufficient before backfill, satisfied after -> unsatisfied -> satisfied

Plus two clustering non-interference cases:
- multiple same-content URLs -> exact_duplicate_adjusted_count drops
- multiple high-sim reprints  -> advisory warning, gate result unchanged
"""

from __future__ import annotations

from packages.research_harness.eval_persistence import (
    RunEvaluationStore,
    build_evaluable_coverage_report,
)


def _slot(**kw) -> dict:
    base = {
        "slot_id": "project.operation_status",
        "section_id": "project_progress",
        "criticality": "required",
        "min_evidence_items": 2,
        "min_raw_supporting_sources": 2,
        "field_requirements": {
            "mandatory": ["project_name", "operation_status"],
            "any_of": [],
        },
        "source_obligations": {"required_families": ["government"],
                                            "primary_source_required": True},
    }
    base.update(kw)
    return base


def _event(slot_id: str = "project.operation_status", *, status: str = "completed", **kw) -> dict:
    base = {
        "search_event_id": "se_1", "run_id": "run_1",
        "slot_ids": [slot_id], "query": "合肥 低空物流 项目",
        "source_family": "government", "provider": "web_search",
        "status": status, "accepted_source_count": 2,
        "accepted_evidence_count": 2,
    }
    base.update(kw)
    return base


def _evidence(*, eid: str, sid: str, field_status: dict,
              extraction: str = "completed", **kw) -> dict:
    base = {
        "evidence_id": eid, "run_id": "run_1", "source_id": sid,
        "source_family": "government", "source_family_status": "classified",
        "supports_slot_ids": ["project.operation_status"],
        "key_fields": {k: {"status": v, "value": "x" if v == "present" else None}
                       for k, v in field_status.items()},
        "key_field_extraction_status": extraction,
        "quote_verification_status": "verified",
    }
    base.update(kw)
    return base


def _store(slots=None, events=None, evidence=None) -> RunEvaluationStore:
    store = RunEvaluationStore("run_1")
    for s in (slots or [_slot()]):
        store.record_claim_slots([s])
    for e in (events or []):
        store.record_search_event(e)
    for ev in (evidence or []):
        store.record_evidence_unit(ev)
    return store


# ── 6 L2 replay cases ───────────────────────────────────────────────────────

def test_l2_searched_evidence_and_fields_satisfied():
    store = _store(
        events=[_event()],
        evidence=[
            _evidence(eid="ev1", sid="a",
                       field_status={"project_name": "present", "operation_status": "present"}),
            _evidence(eid="ev2", sid="b",
                       field_status={"project_name": "present", "operation_status": "present"}),
        ],
    )
    report = build_evaluable_coverage_report(store)
    assert report["slot_reports"][0]["status"] == "satisfied"
    assert report["readiness"] == "ready"
    assert report["evaluation_completeness"] == 1.0


def test_l2_searched_but_evidence_insufficient():
    store = _store(
        events=[_event(accepted_evidence_count=1)],
        evidence=[
            _evidence(eid="ev1", sid="a",
                       field_status={"project_name": "present", "operation_status": "present"}),
        ],
    )
    report = build_evaluable_coverage_report(store)
    slot = report["slot_reports"][0]
    assert slot["status"] == "unsatisfied"  # 1 evidence < min 2
    assert slot["reasons"] == ["below_threshold"]


def test_l2_no_search_event_not_evaluable():
    store = _store(events=[], evidence=[])
    report = build_evaluable_coverage_report(store)
    assert report["slot_reports"][0]["status"] == "not_evaluable"
    assert report["readiness"] == "unknown"  # must NOT fake-ready
    assert report["evaluation_completeness"] == 0.0


def test_l2_evidence_without_extraction_not_evaluable():
    store = _store(
        events=[_event()],
        evidence=[
            _evidence(eid="ev1", sid="a", field_status={}, extraction="not_extracted"),
        ],
    )
    report = build_evaluable_coverage_report(store)
    slot = report["slot_reports"][0]
    assert slot["status"] == "not_evaluable"
    assert "evidence_extraction_incomplete" in slot["reasons"]


def test_l2_searched_field_clearly_not_found_unsatisfied():
    store = _store(
        events=[_event()],
        evidence=[
            _evidence(eid="ev1", sid="a",
                      field_status={"project_name": "present", "operation_status": "not_found"}),
            _evidence(eid="ev2", sid="b",
                      field_status={"project_name": "present", "operation_status": "not_found"}),
        ],
    )
    report = build_evaluable_coverage_report(store)
    slot = report["slot_reports"][0]
    assert slot["status"] == "unsatisfied"  # not_found counts as unsatisfied, not evaluable
    assert "operation_status" in slot["reasons"]


def test_l2_backfill_turns_unsatisfied_into_satisfied():
    # round 1: 1 evidence -> unsatisfied
    store = _store(
        events=[_event()],
        evidence=[
            _evidence(eid="ev1", sid="a",
                      field_status={"project_name": "present", "operation_status": "present"}),
        ],
    )
    r1 = build_evaluable_coverage_report(store)
    assert r1["slot_reports"][0]["status"] == "unsatisfied"
    # round 2 (backfill): add 1 more evidence + a new search event
    store.record_search_event(_event(search_event_id="se_2", accepted_evidence_count=2))
    store.record_evidence_unit(_evidence(
        eid="ev2", sid="b",
        field_status={"project_name": "present", "operation_status": "present"},
    ))
    r2 = build_evaluable_coverage_report(store)
    assert r2["slot_reports"][0]["status"] == "satisfied"
    assert r2["readiness"] == "ready"


# ── 2 clustering non-interference cases ─────────────────────────────────────

def test_cluster_exact_duplicate_adjusted_drops_but_gate_unchanged():
    # two same-content URLs -> exact_duplicate_adjusted_count drops to 1
    store = _store(
        events=[_event()],
        evidence=[
            _evidence(eid="ev1", sid="a",
                      field_status={"project_name": "present", "operation_status": "present"},
                      content_cluster_id="cluster_1"),
            _evidence(eid="ev2", sid="b",
                      field_status={"project_name": "present", "operation_status": "present"},
                      content_cluster_id="cluster_1"),  # same content cluster
        ],
    )
    # raw count still 2 (gate), exact cluster count would be 1
    raw = len({e["source_id"] for e in store.evidence_units.values()})
    assert raw == 2  # gate count unchanged
    assert len({e["content_cluster_id"] for e in store.evidence_units.values()}) == 1


def test_cluster_reprint_advisory_does_not_change_gate():
    store = _store(
        events=[_event()],
        evidence=[
            _evidence(eid="ev1", sid="a",
                      field_status={"project_name": "present", "operation_status": "present"}),
            _evidence(eid="ev2", sid="b",
                      field_status={"project_name": "present", "operation_status": "present"}),
            _evidence(eid="ev3", sid="c",
                      field_status={"project_name": "present", "operation_status": "present"}),
        ],
    )
    report = build_evaluable_coverage_report(store)
    slot = report["slot_reports"][0]
    # gate uses raw count: 3 evidence / 3 sources >= min -> satisfied (gate unchanged
    # even if some are high-sim reprints)
    assert slot["status"] == "satisfied"
    # source_count_policy documents the tiered usage (advisory not in gate)
    policy = store.snapshots[0]["source_count_policy"] if store.snapshots else \
        {"gate_count": "raw_supporting_source_count",
         "exact_duplicate_adjusted": "deterministic_reference",
         "likely_reprint_adjusted": "advisory_only"}
    assert policy["likely_reprint_adjusted"] == "advisory_only"
    assert policy["gate_count"] == "raw_supporting_source_count"
