"""B.3.3b — Graph Advisory Node acceptance tests.

Covers the user's 8 graph-node acceptance cases:
  1. feature flag OFF -> node no-op, provider calls 0, main state unchanged
  2. shadow node success -> only advisory_backfill/advisory_backfill_status added
  3. node failure -> advisory_backfill_status=degraded, fail-open
  4. checkpoint idempotency -> stable action ids, no duplicate events/snapshots
  5. HUMAN_REVIEW termination -> tasks suspended, no ambiguous running
  6. state non-interference -> main namespaces hash-identical flag ON vs OFF
  7. provider fallback trace -> SearchEvent records configured/executed/fallback
  8. budget constraints -> max_rounds/max_total_actions/max_per_slot respected

Uses fake executor/builder (no network); graph-node structure is also asserted.
"""

from __future__ import annotations

from packages.research_harness import real_nodes
from packages.research_harness.advisory_backfill import (
    BackfillEvidenceUnit,
    BackfillSearchResult,
    BackfillSourceCandidate,
    run_advisory_backfill,
)
from packages.research_harness.eval_persistence import (
    RunEvaluationStore,
    build_evaluable_coverage_report,
)
from packages.research_harness.gap_retrieval import derive_gaps


def _store() -> RunEvaluationStore:
    store = RunEvaluationStore("run")
    store.record_claim_slots([{
        "slot_id": "s1", "section_id": "sec", "criticality": "required",
        "min_evidence_items": 2, "min_raw_supporting_sources": 2,
        "field_requirements": {"mandatory": ["operation_status"], "any_of": []},
        "source_obligations": {"required_families": ["government"],
                               "primary_source_required": True},
    }])
    store.record_search_event({
        "search_event_id": "se1", "run_id": "run", "slot_ids": ["s1"],
        "query": "q", "source_family": "government", "provider": "tavily",
        "status": "completed", "result_count": 1, "accepted_source_ids": ["a"],
        "schema_version": "search_event_v1",
    })
    store.record_search_task({
        "search_task_id": "t1", "run_id": "run", "slot_ids": ["s1"], "query": "q",
        "round": 1, "status": "planned", "schema_version": "search_task_v1",
    })
    store.record_evidence_unit({
        "evidence_id": "ev1", "run_id": "run", "source_id": "a",
        "source_family": "government", "supports_slot_ids": ["s1"],
        "key_fields": {"operation_status": {"status": "present", "value": "x"}},
        "key_field_extraction_status": "completed", "schema_version": "evidence_unit_v2",
    })
    return store


def _state(store=None) -> dict:
    store = store or _store()
    return {
        "query": "合肥低空物流", "run_id": "run",
        "evaluation_store": store.to_dict(),
        "sources": [{"source_id": "a", "source_family": "government"}],
        "evidence": [{"evidence_id": "ev1", "source_id": "a"}],
        "claims": [{"claim_id": "c1"}],
        "documents": [{"document_id": "d1"}],
        "approved_claims": [],
        "coverage_report": {"mode": "evaluable"},
        "final_report": {"report_markdown": "original"},
    }


class _FakeExecutor:
    def __init__(self, *, fail=False, fallback=False):
        self.calls: list[str] = []
        self._fail = fail
        self._fallback = fallback

    def search(self, query, *, source_family=None, max_results=5):
        self.calls.append(query)
        if self._fail:
            raise RuntimeError("provider down")
        return BackfillSearchResult(
            query=query, provider="tavily" if self._fallback else "anysearch",
            status="completed", result_count=1,
            candidates=(BackfillSourceCandidate(
                source_id="b", url="https://b", source_family="government"),),
            configured_provider="anysearch",
            fallback_used=self._fallback,
            fallback_reason="primary_provider_error" if self._fallback else "",
        )


class _FakeBuilder:
    def build(self, *, query, slot, source_family, candidates, search_event_id):
        return [
            BackfillEvidenceUnit(
                evidence_id="ev2", source_id=c.source_id, source_family="government",
                supports_slot_ids=("s1",), key_fields={"operation_status": "投运"},
                content_cluster_id="cl:b", quote_verified=True,
            )
            for c in candidates
        ]


def _hash(state: dict) -> dict:
    import hashlib
    import json

    out = {}
    for key in ("sources", "evidence", "claims", "documents", "approved_claims",
                "coverage_report", "final_report"):
        out[key] = hashlib.sha256(
            json.dumps(state.get(key), sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    return out


def _enable(executor=None, builder=None):
    real_nodes.set_advisory_backfill_override(enabled=True, mode="shadow")
    real_nodes.set_advisory_backfill_components(
        search_executor=executor or _FakeExecutor(),
        evidence_builder=builder or _FakeBuilder(),
    )


def _disable():
    real_nodes.set_advisory_backfill_override(enabled=None, mode=None)
    real_nodes.set_advisory_backfill_components(search_executor=None, evidence_builder=None)


# ── 1. flag OFF -> no-op ────────────────────────────────────────────────────

def test_flag_off_is_noop_and_provider_never_called():
    executor = _FakeExecutor()
    real_nodes.set_advisory_backfill_override(enabled=False, mode="shadow")
    real_nodes.set_advisory_backfill_components(search_executor=executor)
    state = _state()
    before = _hash(state)
    out = real_nodes.advisory_gap_backfill_provider_backed(state)
    assert out == {}
    assert executor.calls == []
    assert _hash(state) == before
    _disable()


# ── 2. shadow success adds only advisory namespaces ─────────────────────────

def test_shadow_success_adds_only_advisory_namespaces():
    _enable()
    state = _state()
    before = _hash(state)
    out = real_nodes.advisory_gap_backfill_provider_backed(state)
    assert out["advisory_backfill_status"] == "completed"
    assert "advisory_backfill" in out
    assert set(out.keys()) == {"advisory_backfill", "advisory_backfill_status"}
    assert out["advisory_backfill"]["resolved_gap_keys"]
    assert _hash(state) == before  # main namespaces untouched
    _disable()


# ── 3. node failure -> degraded, fail-open ──────────────────────────────────

def test_node_failure_degrades_fail_open():
    _enable(executor=_FakeExecutor(fail=True))
    state = _state()
    out = real_nodes.advisory_gap_backfill_provider_backed(state)
    assert out["advisory_backfill_status"] == "degraded"
    assert out["advisory_backfill_diagnostics"][0]["code"] == "ADVISORY_BACKFILL_FAILED"
    # fail-open: no error/block key is returned, main state untouched
    assert "error" not in out and "decision" not in out
    assert "advisory_backfill" not in out
    _disable()


# ── 4. checkpoint idempotency ───────────────────────────────────────────────

def test_repeat_node_run_is_idempotent():
    _enable()
    state = _state()
    out1 = real_nodes.advisory_gap_backfill_provider_backed(state)
    out2 = real_nodes.advisory_gap_backfill_provider_backed(state)
    assert out1 == out2  # same action ids, same events, same snapshot counts
    r1 = out1["advisory_backfill"]
    assert len(r1["executed_action_ids"]) == len(set(r1["executed_action_ids"]))
    _disable()


# ── 5. HUMAN_REVIEW termination suspends tasks ──────────────────────────────

def test_runner_termination_reason_maps_human_review_to_suspend():
    from packages.research_harness.runner import ResearchGraphRunner

    runner = object.__new__(ResearchGraphRunner)
    # HUMAN_REVIEW pending -> suspended (no running left ambiguous)
    state = {
        "decision": "HUMAN_REVIEW",
        "human_review": {"pending": True},
        "evaluation_store": _store().to_dict(),
    }
    assert runner._termination_reason(state) == "HUMAN_REVIEW"
    out = runner._finalize_evaluation(dict(state))
    store = RunEvaluationStore.from_dict(out["evaluation_store"])
    assert out["evaluation_termination_reason"] == "HUMAN_REVIEW"
    statuses = {t["status"] for t in store.search_tasks.values()}
    assert "running" not in statuses and "planned" not in statuses
    assert "suspended" in statuses

    # REPORT_COMPLETED closes tasks
    state2 = {"decision": "PASS", "human_review": None,
              "evaluation_store": _store().to_dict()}
    out2 = runner._finalize_evaluation(dict(state2))
    store2 = RunEvaluationStore.from_dict(out2["evaluation_store"])
    assert out2["evaluation_termination_reason"] == "REPORT_COMPLETED"
    assert all(t["status"] == "cancelled" for t in store2.search_tasks.values())

    # GRAPH_ERROR on error state
    state3 = {"error": {"message": "boom"}, "evaluation_store": _store().to_dict()}
    assert runner._termination_reason(state3) == "GRAPH_ERROR"


# ── 6. state non-interference (hash equality ON vs OFF) ─────────────────────

def test_state_non_interference_hashes_equal():
    off_state = _state()
    _disable()
    real_nodes.advisory_gap_backfill_provider_backed(off_state)
    off_hashes = _hash(off_state)

    on_state = _state()
    _enable()
    real_nodes.advisory_gap_backfill_provider_backed(on_state)
    on_hashes = _hash(on_state)

    assert on_hashes == off_hashes  # sources/evidence/claims/docs/report identical
    _disable()


# ── 7. provider fallback trace ──────────────────────────────────────────────

def test_provider_fallback_is_recorded_on_event():
    store = _store()
    snapshot = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(snapshot, store)
    executor = _FakeExecutor(fallback=True)
    result = run_advisory_backfill(
        store=store, current_snapshot=snapshot, research_gaps=gaps, proposed_actions=[],
        search_executor=executor, evidence_builder=_FakeBuilder(), base_query="q",
    )
    event_id = result.rounds[0].search_event_ids[0]
    event = result.final_store.search_events[event_id]
    assert event["configured_provider"] == "anysearch"
    assert event["executed_provider"] == "tavily"
    assert event["fallback_used"] is True
    assert event["fallback_reason"] == "primary_provider_error"


# ── 8. budget constraints respected ─────────────────────────────────────────

def test_budget_constraints_respected_in_run():
    # many gaps across 3 slots -> node's fixed budget (max_rounds=2,
    # max_total_actions=6, max_actions_per_slot=2) must hold.
    store = RunEvaluationStore("run")
    slots = []
    for i in range(3):
        sid = f"s{i}"
        slots.append({
            "slot_id": sid, "section_id": "sec", "criticality": "required",
            "min_evidence_items": 2, "min_raw_supporting_sources": 2,
            "field_requirements": {"mandatory": [f"f{i}"], "any_of": []},
            "source_obligations": {"required_families": ["government"],
                                   "primary_source_required": True},
        })
        store.record_search_event({
            "search_event_id": f"se{i}", "run_id": "run", "slot_ids": [sid],
            "query": f"q{i}", "source_family": "government", "provider": "tavily",
            "status": "completed", "result_count": 1,
            "accepted_source_ids": [f"a{i}"], "schema_version": "search_event_v1",
        })
        store.record_evidence_unit({
            "evidence_id": f"ev{i}", "run_id": "run", "source_id": f"a{i}",
            "source_family": "government", "supports_slot_ids": [sid],
            "key_fields": {f"f{i}": {"status": "present", "value": "x"}},
            "key_field_extraction_status": "completed",
            "schema_version": "evidence_unit_v2",
        })
    store.record_claim_slots(slots)

    snapshot = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(snapshot, store)
    result = run_advisory_backfill(
        store=store, current_snapshot=snapshot, research_gaps=gaps, proposed_actions=[],
        search_executor=_FakeExecutor(), evidence_builder=_FakeBuilder(), base_query="q",
        max_rounds=2, max_actions_per_round=3, max_actions_per_slot=2, max_total_actions=6,
    )
    assert len(result.rounds) <= 2
    assert result.stats["actions_executed"] <= 6
    per_slot = {}
    for r in result.rounds:
        for a in r.executed_actions:
            per_slot[a["slot_id"]] = per_slot.get(a["slot_id"], 0) + 1
    assert all(v <= 2 for v in per_slot.values())
    assert result.stats["query_repeat_count"] == 0


# ── structural: graph wiring is fixed (not a loop-control node) ─────────────

def test_graph_wiring_inserts_advisory_between_build_claims_and_editor1():
    from packages.research_harness.runner import ResearchGraphRunner

    runner = object.__new__(ResearchGraphRunner)
    seq = runner._next_node_after
    # build_claims -> advisory -> structured_shadow -> editor1 (fixed edges)
    assert seq(current_node="build_claims", state={}) == "advisory_gap_backfill"
    assert seq(current_node="advisory_gap_backfill", state={}) == "structured_shadow_editor1"
    assert seq(current_node="structured_shadow_editor1", state={}) == "editor1_draft"
    # neither advisory nor shadow is a loop-control node: no conditional route
    runtime = runner._runtime_nodes()
    assert "advisory_gap_backfill" in runtime
