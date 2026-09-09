"""Phase B.3.3 — Advisory Backfill Runner tests.

Mechanics-only (no live provider): fake SearchExecutor / EvidenceBuilder drive
the deterministic loop. Covers the B.3.3 stop conditions, status transitions,
SnapshotDiff, Scheme-B evidence links, and non-interference.

See user acceptance list (12 cases) mapped to test names below.
"""

from __future__ import annotations

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


def _slot(**kw) -> dict:
    base = {
        "slot_id": "s1", "section_id": "sec", "criticality": "required",
        "min_evidence_items": 2, "min_raw_supporting_sources": 2,
        "field_requirements": {
            "mandatory": ["operation_status", "operation_date"], "any_of": [],
        },
        "source_obligations": {
            "required_families": ["government"], "primary_source_required": True,
        },
    }
    base.update(kw)
    return base


def _ev(*, eid: str, sid: str, field_status: dict, family: str = "government") -> dict:
    return {
        "evidence_id": eid, "run_id": "run", "source_id": sid,
        "source_family": family, "source_family_status": "classified",
        "supports_slot_ids": ["s1"],
        "key_fields": {
            k: {"status": v, "value": "x" if v == "present" else None}
            for k, v in field_status.items()
        },
        "key_field_extraction_status": "completed",
        "schema_version": "evidence_unit_v2",
    }


def _event(slot_id: str = "s1", eid: str = "se1") -> dict:
    return {
        "search_event_id": eid, "run_id": "run", "slot_ids": [slot_id],
        "query": "q", "source_family": "government", "provider": "tavily",
        "status": "completed", "result_count": 1, "accepted_source_ids": ["a"],
        "schema_version": "search_event_v1",
    }


def _store(slot=None, *, events=(), evidence=()) -> RunEvaluationStore:
    store = RunEvaluationStore("run")
    store.record_claim_slots([slot or _slot()])
    for e in events:
        store.record_search_event(e)
    for ev in evidence:
        store.record_evidence_unit(ev)
    return store


def _cand(sid: str, url: str | None = None, family: str = "government",
          content: str = "合肥低空物流项目已正式投运 中标公示") -> BackfillSourceCandidate:
    return BackfillSourceCandidate(
        source_id=sid, url=url or f"https://{sid}", content=content,
        source_family=family,
    )


def _ev_unit(sid: str, *, search_event_id: str, fields: dict | None = None,
             family: str = "government") -> BackfillEvidenceUnit:
    return BackfillEvidenceUnit(
        evidence_id=f"ev:{sid}",
        source_id=sid,
        source_family=family,
        supports_slot_ids=("s1",),
        key_fields=fields or {"operation_status": "x", "operation_date": "2025-06"},
        quoted_span="已正式投运",
        is_primary_source=True,
        content_cluster_id=f"cl:{sid}",
        quote_verified=True,
    )


class FakeExecutor:
    def __init__(self, *, candidates=(), fail_queries=()):
        self.candidates = tuple(candidates)
        self.fail_queries = set(fail_queries)
        self.calls: list[str] = []

    def search(self, query, *, source_family=None, max_results=5):
        self.calls.append(query)
        if query in self.fail_queries:
            return BackfillSearchResult(
                query=query, provider="fake", status="failed", result_count=0,
                failure_reason="boom",
            )
        return BackfillSearchResult(
            query=query, provider="fake", status="completed",
            result_count=len(self.candidates), candidates=self.candidates,
        )


class FakeBuilder:
    def __init__(self, *, per_source: dict[str, list[BackfillEvidenceUnit]] | None = None):
        self.per_source = per_source or {}
        self.calls: list[tuple[str, str]] = []

    def build(self, *, query, slot, source_family, candidates, search_event_id):
        self.calls.append((query, search_event_id))
        out: list[BackfillEvidenceUnit] = []
        for c in candidates:
            for ev in self.per_source.get(c.source_id, []):
                out.append(ev)
        return out


def _one_new_evidence_builder(search_event_id_ref=None) -> FakeBuilder:
    """Builder that yields one evidence for source 'b' and nothing for others."""
    def _build(**kw):
        if kw.get("search_event_id") and search_event_id_ref is not None:
            search_event_id_ref.append(kw["search_event_id"])
        return [_ev_unit("b", search_event_id=kw["search_event_id"])]

    builder = FakeBuilder()
    builder.build = _build
    return builder


# ── 1. gap backfill resolves unsatisfied -> satisfied ───────────────────────

def test_backfill_resolves_unsatisfied_slot():
    store = _store(events=[_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                              "operation_date": "present"}),
    ])
    before = build_evaluable_coverage_report(store)
    gaps, egaps = derive_gaps(before, store)
    assert before["slot_reports"][0]["status"] == "unsatisfied"
    assert not egaps

    result = run_advisory_backfill(
        store=store, current_snapshot=before, research_gaps=gaps, proposed_actions=[],
        search_executor=FakeExecutor(candidates=[_cand("b")]),
        evidence_builder=_one_new_evidence_builder(),
        base_query="合肥低空物流项目",
    )
    assert result.final_snapshot["slot_reports"][0]["status"] == "satisfied"
    assert result.resolved_gap_keys == ["s1:evidence_count", "s1:raw_source_count"]
    assert result.stats["resolved_slot_count"] == 1
    # both gap types resolved; nothing exhausted
    assert result.exhausted_gap_keys == []


# ── 2. returning an old URL -> action is no_new_evidence ────────────────────

def test_old_url_yields_no_new_evidence():
    store = _store(events=[_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                              "operation_date": "present"}),
    ])
    before = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(before, store)
    # executor returns only the ALREADY-KNOWN source 'a'
    result = run_advisory_backfill(
        store=store, current_snapshot=before, research_gaps=gaps, proposed_actions=[],
        search_executor=FakeExecutor(candidates=[_cand("a")]),
        evidence_builder=FakeBuilder(),
        base_query="q",
    )
    round_actions = result.rounds[0].executed_actions
    assert round_actions and round_actions[0]["outcome"] == "no_new_evidence"
    assert result.stats["no_new_evidence_action_count"] == 1
    assert result.stats["new_evidence_total"] == 0
    # slot stays unsatisfied, NOT not_evaluable
    assert result.final_snapshot["slot_reports"][0]["status"] == "unsatisfied"
    assert result.exhausted_gap_keys  # unresolved at stop -> exhausted


# ── 3. new source but NO qualifying evidence is NOT gain ────────────────────

def test_new_source_without_qualifying_evidence_is_not_gain():
    store = _store(events=[_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                              "operation_date": "present"}),
    ])
    before = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(before, store)
    # new candidate 'b' returned, but the builder produces no qualifying evidence
    result = run_advisory_backfill(
        store=store, current_snapshot=before, research_gaps=gaps, proposed_actions=[],
        search_executor=FakeExecutor(candidates=[_cand("b")]),
        evidence_builder=FakeBuilder(),
        base_query="q",
    )
    round_actions = result.rounds[0].executed_actions
    meta = round_actions[0]
    assert meta["new_source_count"] == 1       # provider returned a new URL
    assert meta["new_evidence_count"] == 0     # but it was not gain
    assert meta["outcome"] == "no_new_evidence"
    assert result.stats["new_evidence_total"] == 0


# ── 4. same query is never re-executed ──────────────────────────────────────

def test_same_query_never_re_executed():
    store = _store(events=[_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                              "operation_date": "present"}),
    ])
    before = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(before, store)
    executor = FakeExecutor(candidates=[_cand("b")])
    builder = FakeBuilder(per_source={"b": [_ev_unit("b", search_event_id="ev:se")]})
    run_advisory_backfill(
        store=store, current_snapshot=before, research_gaps=gaps, proposed_actions=[],
        search_executor=executor, evidence_builder=builder, base_query="q",
        max_rounds=5,
    )
    assert len(executor.calls) == len(set(executor.calls))
    assert result_query_counts_leq_one(executor.calls)


def result_query_counts_leq_one(calls: list[str]) -> bool:
    counts: dict[str, int] = {}
    for c in calls:
        counts[c] = counts.get(c, 0) + 1
    return all(v <= 1 for v in counts.values())


# ── 5. one slot is searched at most max_actions_per_slot times ──────────────

def test_slot_respects_max_actions_per_slot():
    slot = _slot(
        min_evidence_items=2, min_raw_supporting_sources=2,
        field_requirements={"mandatory": ["operation_date"], "any_of": []},
    )
    store = _store(slot=slot, events=[_event()], evidence=[
        # family mismatch + missing operation_date -> family + field + count gaps
        _ev(eid="ev1", sid="a",
            field_status={"operation_status": "present", "operation_date": "not_found"},
            family="commercial_media"),
    ])
    before = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(before, store)
    assert len(gaps) >= 3  # evidence_count, mandatory_field_missing, source_family_missing

    executor = FakeExecutor(candidates=[_cand("b")])
    result = run_advisory_backfill(
        store=store, current_snapshot=before, research_gaps=gaps, proposed_actions=[],
        search_executor=executor, evidence_builder=FakeBuilder(), base_query="q",
        max_actions_per_slot=2, max_actions_per_round=3, max_total_actions=6, max_rounds=3,
    )
    slot_action_count = sum(
        1 for r in result.rounds for a in r.executed_actions if a["slot_id"] == "s1"
    )
    assert slot_action_count <= 2
    assert len(executor.calls) == slot_action_count


# ── 6. two no-gain rounds -> gap exhausted ──────────────────────────────────

def test_two_no_gain_rounds_exhausts_gap():
    slot = _slot(
        min_evidence_items=2, min_raw_supporting_sources=2,
        field_requirements={"mandatory": ["operation_date"], "any_of": []},
    )
    store = _store(slot=slot, events=[_event()], evidence=[
        _ev(eid="ev1", sid="a",
            field_status={"operation_status": "present", "operation_date": "not_found"},
            family="commercial_media"),
    ])
    before = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(before, store)
    # every search returns an already-known source -> every action is no gain;
    # the slot has >=2 distinct queries, so the loop runs 2 rounds.
    result = run_advisory_backfill(
        store=store, current_snapshot=before, research_gaps=gaps, proposed_actions=[],
        search_executor=FakeExecutor(candidates=[_cand("a")]),
        evidence_builder=FakeBuilder(), base_query="q",
        max_actions_per_slot=2, max_actions_per_round=1, max_total_actions=6, max_rounds=3,
    )
    assert result.stopped_reason == "slot_no_new_evidence_exhausted"
    assert len(result.rounds) == 2
    assert result.exhausted_gap_keys  # all still-open gaps marked exhausted
    assert "s1:mandatory_field_missing" in result.exhausted_gap_keys


# ── 7. provider failure -> SearchEvent failed + action failed ───────────────

def test_provider_failure_marks_event_failed_and_stops():
    store = _store(events=[_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                              "operation_date": "present"}),
    ])
    before = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(before, store)
    result = run_advisory_backfill(
        store=store, current_snapshot=before, research_gaps=gaps, proposed_actions=[],
        search_executor=FakeExecutor(candidates=[_cand("b")], fail_queries={"q 官方 公告 项目"}),
        evidence_builder=FakeBuilder(), base_query="q",
        max_provider_failures=1, max_actions_per_round=3,
    )
    round_actions = result.rounds[0].executed_actions
    assert round_actions[0]["outcome"] == "failed"
    event_id = result.rounds[0].search_event_ids[0]
    event = result.final_store.search_events[event_id]
    assert event["status"] == "failed"
    assert event["failure_reason"] == "boom"
    # provider consecutive failure reached -> immediate stop
    assert result.stopped_reason == "provider_consecutive_failure"
    # the failed task is terminal
    task = next(iter(result.final_store.search_tasks.values()))
    assert task["status"] == "failed"


# ── 8. degraded store stops immediately ─────────────────────────────────────

def test_degraded_store_stops_immediately():
    store = _store(events=[_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                              "operation_date": "present"}),
    ])
    before = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(before, store)
    result = run_advisory_backfill(
        store=store, current_snapshot=before, research_gaps=gaps, proposed_actions=[],
        search_executor=FakeExecutor(candidates=[_cand("b")]),
        evidence_builder=_one_new_evidence_builder(), base_query="q",
        is_degraded=lambda s: True,
    )
    assert result.stopped_reason == "store_degraded"
    assert result.rounds == []
    assert result.executed_action_ids == []


# ── 9. evidence binds originating_search_event_ids (Scheme B) ───────────────

def test_evidence_binds_originating_search_event_ids():
    store = _store(events=[_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                              "operation_date": "present"}),
    ])
    before = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(before, store)
    result = run_advisory_backfill(
        store=store, current_snapshot=before, research_gaps=gaps, proposed_actions=[],
        search_executor=FakeExecutor(candidates=[_cand("b")]),
        evidence_builder=_one_new_evidence_builder(), base_query="q",
    )
    event_id = result.rounds[0].search_event_ids[0]
    new_evidence = [
        e for e in result.final_store.evidence_units.values()
        if e["evidence_id"].startswith("ev:")
    ]
    assert new_evidence
    for ev in new_evidence:
        assert ev["originating_search_event_ids"] == [event_id]
    # the SearchEvent carries accepted_evidence_ids and is NOT mutated later
    event = result.final_store.search_events[event_id]
    assert set(event["accepted_evidence_ids"]) == {e["evidence_id"] for e in new_evidence}


# ── 10. snapshots are immutable per round ───────────────────────────────────

def test_snapshots_immutable_per_round():
    store = _store(events=[_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                              "operation_date": "present"}),
    ])
    before = build_evaluable_coverage_report(store)
    before_copy = json_copy(before)
    gaps, _ = derive_gaps(before, store)
    result = run_advisory_backfill(
        store=store, current_snapshot=before, research_gaps=gaps, proposed_actions=[],
        search_executor=FakeExecutor(candidates=[_cand("b")]),
        evidence_builder=_one_new_evidence_builder(), base_query="q",
        max_rounds=3, max_actions_per_round=1, max_total_actions=6,
    )
    # caller's snapshot dict is not mutated
    assert before == before_copy
    # one CoverageSnapshot appended per executed round
    snapshots = result.final_store.snapshots
    assert len(snapshots) == len(result.rounds)
    assert len({s["coverage_report_id"] for s in snapshots}) == len(snapshots)
    # the "before" of round N+1 is exactly round N's "after" (no in-place edit)
    for i in range(1, len(result.rounds)):
        assert result.rounds[i].snapshot_before == result.rounds[i - 1].snapshot_after


def json_copy(obj):
    import copy

    return copy.deepcopy(obj)


# ── 11. resolved gap's old action is never re-executed ──────────────────────

def test_resolved_gap_old_action_not_reexecuted():
    # Two slots with DIFFERENT mandatory fields -> distinct action queries.
    # s1 resolves in round 1; round 2 must only target s2 (s1's old action must
    # not run again).
    s1 = _slot(
        field_requirements={"mandatory": ["operation_date"], "any_of": []},
    )
    s2 = _slot(
        slot_id="s2",
        field_requirements={"mandatory": ["operation_status"], "any_of": []},
    )
    store = RunEvaluationStore("run")
    store.record_claim_slots([s1, s2])
    store.record_search_event(_event())
    store.record_search_event(_event(slot_id="s2", eid="se2"))
    store.record_evidence_unit(_ev(eid="ev1", sid="a", field_status={
        "operation_status": "present", "operation_date": "not_found"}))
    store.record_evidence_unit(_ev(eid="ev2", sid="a", field_status={
        "operation_status": "not_found", "operation_date": "present"}))
    store.evidence_units["ev2"]["supports_slot_ids"] = ["s2"]

    before = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(before, store)
    assert "s1:mandatory_field_missing" in {f"{g.slot_id}:{g.gap_type}" for g in gaps}
    assert "s2:mandatory_field_missing" in {f"{g.slot_id}:{g.gap_type}" for g in gaps}

    class TwoSlotExecutor(FakeExecutor):
        def search(self, query, *, source_family=None, max_results=5):
            self.calls.append(query)
            # s1's field query resolves; everything else returns an old URL
            if "投运时间" in query:
                return BackfillSearchResult(
                    query=query, provider="fake", status="completed", result_count=1,
                    candidates=(_cand("b"),),
                )
            return BackfillSearchResult(
                query=query, provider="fake", status="completed", result_count=1,
                candidates=(_cand("a"),),
            )

    executor = TwoSlotExecutor()

    class TwoSlotBuilder(FakeBuilder):
        def build(self, *, query, slot, source_family, candidates, search_event_id):
            self.calls.append((query, search_event_id))
            if "投运时间" in query:
                return [_ev_unit("b", search_event_id=search_event_id)]
            return []

    builder = TwoSlotBuilder()
    result = run_advisory_backfill(
        store=store, current_snapshot=before, research_gaps=gaps, proposed_actions=[],
        search_executor=executor, evidence_builder=builder, base_query="q",
        max_actions_per_round=2, max_actions_per_slot=2, max_total_actions=6, max_rounds=3,
    )
    s1_executions = [q for q in executor.calls if "投运时间" in q]
    assert len(s1_executions) == 1  # old action for resolved slot runs exactly once
    assert "s1:mandatory_field_missing" in result.resolved_gap_keys
    assert result.final_snapshot["slot_reports"][0]["status"] == "satisfied"
    # s2's old action (投运状态) is not re-run either once its round is spent
    s2_executions = [q for q in executor.calls if "投运状态" in q]
    assert len(s2_executions) <= 2  # at most max_actions_per_slot


# ── 12. non-interference: caller store + claims + report untouched ──────────

def test_non_interference_caller_store_untouched():
    store = _store(events=[_event()], evidence=[
        _ev(eid="ev1", sid="a", field_status={"operation_status": "present",
                                              "operation_date": "present"}),
    ])
    store.record_claim_card({
        "claim_id": "c1", "primary_slot_id": "s1", "slot_ids": ["s1"],
        "evidence_ids": ["ev1"], "claim_type": "factual",
        "epistemic_status": "supported", "assertion_level": "fact_confirmed",
        "max_allowed_assertion_level": "fact_confirmed", "approval_status": "pending",
        "idempotency_key": "claim:c1", "schema_version": "claim_card_v1",
    })
    before = store.to_dict()
    snapshot_before = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(snapshot_before, store)
    result = run_advisory_backfill(
        store=store, current_snapshot=snapshot_before, research_gaps=gaps, proposed_actions=[],
        search_executor=FakeExecutor(candidates=[_cand("b")]),
        evidence_builder=_one_new_evidence_builder(), base_query="q",
    )
    # caller's store is byte-for-byte unchanged (harness works on a clone)
    assert store.to_dict() == before
    # claims/cards carried in the store are preserved verbatim in the clone
    assert result.final_store.claim_cards == before["claim_cards"]
    # no ResearchGap expression was auto-approved anywhere in the flow
    assert result.stats["approved_research_gap_expression_count"] == 0
    # the original snapshot dict was not mutated
    assert snapshot_before["slot_reports"][0]["status"] == "unsatisfied"
