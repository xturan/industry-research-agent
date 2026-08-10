"""Phase B.3.3 — Advisory Backfill Runner (independent harness).

Executes up to N rounds of targeted gap backfill for `unsatisfied` slots,
recorded into a RunEvaluationStore, WITHOUT touching the formal LangGraph
routing, Editor1, claim strength, or the final report.

Design (review 2026-08-04):

- ResearchGap (unsatisfied) may drive backfill; EvaluationGap (not_evaluable)
  is NEVER backfilled and never interpreted as "no evidence".
- Each round: re-derive current ResearchGaps from the latest CoverageSnapshot,
  propose deterministic SuggestedSearchActions, dedup already-executed queries,
  select within budget, create a new SearchTask (origin=gap_backfill), call the
  SearchExecutor, append a SearchEvent, build+append Evidence (Scheme B: each
  EvidenceUnit links back to its originating SearchEvent), recompute the
  CoverageSnapshot, and emit a SnapshotDiff.
- "有结果" != "有增益": provider results that only return already-known URLs,
  duplicate content, or no qualifying evidence are marked `no_new_evidence`.
- The store is cloned; the caller's store/state is never mutated.

search_executor / evidence_builder are injected Protocols so the harness is
deterministically testable with fakes and replaceable with the real AnySearch
provider + a content-presence evidence builder (scripts/b3_advisory_backfill.py).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

from packages.research_harness.eval_persistence import (
    RunEvaluationStore,
    build_evaluable_coverage_report,
)

# Reuse the same snapshot-recorder as the runner (coverage_report_v2 shape).
from packages.research_harness.evaluation_recorder import record_snapshot
from packages.research_harness.gap_retrieval import (
    ResearchGapRecord,
    SuggestedSearchAction,
    build_snapshot_diff,
    derive_gaps,
    propose_search_actions,
)

_OPEN_GAP_STATUSES = {"open", "action_proposed", "searching", "partially_resolved"}
_TERMINAL_ACTION_STATUSES = {"completed", "failed", "no_new_evidence", "cancelled"}


# ── domain records (JSON-serializable) ──────────────────────────────────────

@dataclass(frozen=True)
class BackfillSourceCandidate:
    source_id: str
    url: str
    title: str = ""
    content: str = ""
    source_family: str = ""
    is_primary_source: bool = False


@dataclass(frozen=True)
class BackfillEvidenceUnit:
    evidence_id: str
    source_id: str
    source_family: str
    supports_slot_ids: tuple[str, ...] = ()
    key_fields: dict[str, str] = field(default_factory=dict)  # field -> extracted value
    quoted_span: str = ""
    is_primary_source: bool = False
    content_cluster_id: str | None = None
    quote_verified: bool = False


@dataclass(frozen=True)
class BackfillSearchResult:
    query: str
    provider: str
    status: Literal["completed", "failed"]
    result_count: int
    candidates: tuple[BackfillSourceCandidate, ...] = ()
    failure_reason: str | None = None
    # B.3.3b explicit provider trace: configured_provider is what the policy
    # wanted, fallback_used/reason explain any silent-ish fallback.
    configured_provider: str = ""
    fallback_used: bool = False
    fallback_reason: str = ""


# ── injected protocols (real impl lives in advisory_backfill_live.py) ───────

class SearchExecutor(Protocol):
    def search(
        self,
        query: str,
        *,
        source_family: str | None = None,
        max_results: int = 5,
    ) -> BackfillSearchResult: ...


class EvidenceBuilder(Protocol):
    def build(
        self,
        *,
        query: str,
        slot: dict[str, Any],
        source_family: str | None,
        candidates: Sequence[BackfillSourceCandidate],
        search_event_id: str,
    ) -> list[BackfillEvidenceUnit]: ...


# ── round / run results ─────────────────────────────────────────────────────

@dataclass
class BackfillRoundResult:
    round_no: int
    executed_action_ids: list[str]
    executed_actions: list[dict[str, Any]]
    new_source_ids: list[str]
    new_evidence_ids: list[str]
    new_content_cluster_ids: list[str]
    search_event_ids: list[str]
    snapshot_before: dict[str, Any]
    snapshot_after: dict[str, Any]
    snapshot_diff: dict[str, Any]
    action_status_by_id: dict[str, str]
    gap_status_by_key: dict[str, str]
    stopped_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "round": self.round_no,
            "executed_action_ids": self.executed_action_ids,
            "executed_actions": self.executed_actions,
            "new_source_ids": self.new_source_ids,
            "new_evidence_ids": self.new_evidence_ids,
            "new_content_cluster_ids": self.new_content_cluster_ids,
            "search_event_ids": self.search_event_ids,
            "snapshot_before": self.snapshot_before,
            "snapshot_after": self.snapshot_after,
            "snapshot_diff": self.snapshot_diff,
            "action_status_by_id": self.action_status_by_id,
            "gap_status_by_key": self.gap_status_by_key,
            "stopped_reason": self.stopped_reason,
        }


@dataclass
class BackfillRunResult:
    run_id: str
    rounds: list[BackfillRoundResult]
    final_snapshot: dict[str, Any]
    final_store: RunEvaluationStore
    executed_action_ids: list[str]
    resolved_gap_keys: list[str]
    exhausted_gap_keys: list[str]
    stopped_reason: str
    stats: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "rounds": [r.to_dict() for r in self.rounds],
            "final_snapshot": self.final_snapshot,
            "executed_action_ids": self.executed_action_ids,
            "resolved_gap_keys": self.resolved_gap_keys,
            "exhausted_gap_keys": self.exhausted_gap_keys,
            "stopped_reason": self.stopped_reason,
            "stats": self.stats,
        }


# ── stable ids / helpers ────────────────────────────────────────────────────

def _stable(*parts: str) -> str:
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()[:12]


def _stable_task_id(run_id: str, round_no: int, action_id: str, query: str) -> str:
    return f"st:{run_id}:bg:{round_no}:{_stable(action_id, query)}"


def _stable_event_id(run_id: str, round_no: int, slot_id: str, query: str) -> str:
    return f"se:{run_id}:bg:{round_no}:{slot_id}:{_stable(query)}"


def _gap_key(gap: ResearchGapRecord) -> str:
    return f"{gap.slot_id}:{gap.gap_type}"


def _utc_now() -> str:
    try:
        return datetime.now(datetime.UTC).isoformat(timespec="seconds")
    except AttributeError:  # pragma: no cover - Python < 3.11 fallback
        return datetime.now(timezone.utc).isoformat(timespec="seconds")  # noqa: UP017


def _next_round_number(store: RunEvaluationStore) -> int:
    rounds = [int(t.get("round") or 1) for t in store.search_tasks.values()]
    return (max(rounds) + 1) if rounds else 1


def _known_source_ids(store: RunEvaluationStore) -> set[str]:
    known: set[str] = set()
    for ev in store.evidence_units.values():
        if ev.get("source_id"):
            known.add(str(ev["source_id"]))
    for e in store.search_events.values():
        for sid in e.get("accepted_source_ids", []):
            if sid:
                known.add(str(sid))
    return known


# ── recorders (append-only; SearchEvent is written once and never mutated) ──

def _record_backfill_task(
    store: RunEvaluationStore,
    action: SuggestedSearchAction,
    *,
    round_no: int,
    run_id: str,
) -> dict[str, Any]:
    task_id = _stable_task_id(run_id, round_no, action.action_id, action.query)
    store.record_search_task({
        "search_task_id": task_id,
        "run_id": run_id,
        "slot_ids": [action.slot_id],
        "query": action.query,
        "target_source_families": (
            [action.target_source_family] if action.target_source_family else []
        ),
        "required_fields": list(action.required_fields),
        "round": round_no,
        "status": "planned",
        "idempotency_key": task_id,
        "origin": "gap_backfill",
        "originating_gap_id": action.gap_id,
        "originating_action_id": action.action_id,
        "schema_version": "search_task_v1",
    })
    return store.search_tasks[task_id]


def _record_backfill_event(
    store: RunEvaluationStore,
    action: SuggestedSearchAction,
    *,
    task_id: str,
    event_id: str,
    round_no: int,
    run_id: str,
    result: BackfillSearchResult,
    new_candidates: Sequence[BackfillSourceCandidate],
    accepted_evidence_ids: Sequence[str] | None = None,
) -> None:
    accepted_evidence_ids = list(accepted_evidence_ids or [])
    store.record_search_event({
        "search_event_id": event_id,
        "search_task_id": task_id,
        "run_id": run_id,
        "slot_ids": [action.slot_id],
        "query": action.query,
        "source_family": action.target_source_family or "",
        "provider": result.provider,
        "status": result.status,
        "result_count": result.result_count,
        "accepted_source_count": len(new_candidates),
        "accepted_evidence_count": len(accepted_evidence_ids),
        "accepted_source_ids": [c.source_id for c in new_candidates],
        "accepted_evidence_ids": accepted_evidence_ids,
        "failure_reason": result.failure_reason,
        # B.3.3b explicit provider trace (no hidden fallback).
        "configured_provider": result.configured_provider or result.provider,
        "executed_provider": result.provider,
        "fallback_used": result.fallback_used,
        "fallback_reason": result.fallback_reason,
        "idempotency_key": event_id,
        "executed_at": _utc_now(),
        "schema_version": "search_event_v1",
    })


def _record_backfill_evidence(
    store: RunEvaluationStore,
    ev: BackfillEvidenceUnit,
    *,
    slot_id: str,
    search_event_id: str,
    run_id: str,
) -> None:
    store.record_evidence_unit({
        "evidence_id": ev.evidence_id,
        "run_id": run_id,
        "source_id": ev.source_id,
        "content_cluster_id": ev.content_cluster_id,
        "quoted_span": ev.quoted_span,
        "source_family": ev.source_family,
        "source_family_status": "classified" if ev.source_family else "unclassified",
        "is_primary_source": ev.is_primary_source,
        "supports_slot_ids": list(ev.supports_slot_ids) or [slot_id],
        # Scheme B: evidence links BACK to the search event that produced its source.
        "originating_search_event_ids": [search_event_id],
        "key_fields": {
            f: {"status": "present", "value": v}
            for f, v in ev.key_fields.items()
        },
        # Only an evidence unit with at least one detected field counts as a
        # completed extraction; empty-field units are dropped by the builder.
        "key_field_extraction_status": "completed" if ev.key_fields else "not_extracted",
        "quote_verification_status": "verified" if ev.quote_verified else "not_verified",
        "idempotency_key": f"ev:{ev.evidence_id}",
        "schema_version": "evidence_unit_v2",
    })


# ── main loop ───────────────────────────────────────────────────────────────

def run_advisory_backfill(
    *,
    store: RunEvaluationStore,
    current_snapshot: dict[str, Any],
    research_gaps: Sequence[ResearchGapRecord],
    proposed_actions: Sequence[SuggestedSearchAction],
    search_executor: SearchExecutor,
    evidence_builder: EvidenceBuilder,
    base_query: str,
    max_rounds: int = 2,
    max_actions_per_round: int = 3,
    max_actions_per_slot: int = 2,
    max_total_actions: int = 6,
    max_provider_failures: int = 2,
    round_start: int | None = None,
    is_degraded: Callable[[RunEvaluationStore], bool] | None = None,
) -> BackfillRunResult:
    """Run the advisory backfill loop (see module docstring for semantics).

    `is_degraded` defaults to `store.degraded`; inject a callable for tests that
    simulate persistence degradation mid-run.
    """
    work = store.copy()
    is_degraded = is_degraded or (lambda s: s.degraded)
    run_id = work.run_id or ""
    next_round = round_start or _next_round_number(work)

    # Seed executed-queries from every persisted event/task so a query that was
    # already executed (even with an empty event query) is never re-run.
    executed_queries: set[str] = {
        str(ev.get("query") or "").strip().lower()
        for ev in work.search_events.values()
        if str(ev.get("query") or "").strip()
    }
    executed_queries.update(
        str(t.get("query") or "").strip().lower()
        for t in work.search_tasks.values()
        if str(t.get("query") or "").strip()
    )

    action_status: dict[str, str] = {a.action_id: a.status for a in proposed_actions}
    gap_status: dict[str, str] = {_gap_key(g): g.status for g in research_gaps}

    total_executed = 0
    per_slot_no_gain: dict[str, int] = {}
    per_slot_actions: dict[str, int] = {}
    consecutive_provider_failures = 0
    known_source_ids = _known_source_ids(work)
    snapshot = dict(current_snapshot)
    if not snapshot.get("coverage_report_id"):
        snapshot["coverage_report_id"] = f"cr:{run_id}:r{next_round - 1}"

    rounds: list[BackfillRoundResult] = []
    executed_action_ids: list[str] = []
    resolved_gap_keys: list[str] = []
    exhausted_gap_keys: list[str] = []
    stop_reason: str | None = None

    for _round_index in range(max_rounds):
        # stop condition 6 (checked before any work in a round): degraded store
        # must not be trusted for further backfill.
        if is_degraded(work):
            stop_reason = "store_degraded"
            break

        # ── re-derive current gaps (never reuse stale actions) ──
        gaps, _egaps = derive_gaps(snapshot, work)
        open_gaps = [
            g for g in gaps
            if gap_status.get(_gap_key(g), g.status) in _OPEN_GAP_STATUSES
        ]
        if not open_gaps:
            # stop condition 1 + 7: all target gaps resolved (or only
            # EvaluationGaps remain) -> nothing left to backfill.
            stop_reason = "all_research_gaps_resolved"
            break

        gap_by_id = {g.gap_id: g for g in open_gaps}
        actions = propose_search_actions(
            open_gaps,
            work,
            base_query=base_query,
            executed_queries=executed_queries,
            max_per_slot=max_actions_per_slot,
        )
        actions = [
            a for a in actions
            if action_status.get(a.action_id, a.status) not in _TERMINAL_ACTION_STATUSES
        ]
        remaining_total = max_total_actions - total_executed
        # Cumulative per-slot cap (not just per propose call): a slot is searched
        # at most max_actions_per_slot times across the whole run.
        selected: list[SuggestedSearchAction] = []
        for a in actions:
            if per_slot_actions.get(a.slot_id, 0) >= max_actions_per_slot:
                continue
            if len(selected) >= min(max_actions_per_round, remaining_total):
                break
            selected.append(a)
            per_slot_actions[a.slot_id] = per_slot_actions.get(a.slot_id, 0) + 1
        if not selected:
            # stop condition 2: no new executable action.
            stop_reason = "no_new_executable_action"
            break

        before = dict(snapshot)
        round_new_source: list[str] = []
        round_new_evidence: list[str] = []
        round_new_cluster: list[str] = []
        round_event_ids: list[str] = []
        round_actions_meta: list[dict[str, Any]] = []
        slot_evidence_added: dict[str, int] = {}

        for action in selected:
            total_executed += 1
            executed_action_ids.append(action.action_id)
            action_status[action.action_id] = "approved"
            gap_key = _gap_key(gap_by_id[action.gap_id])
            if gap_status.get(gap_key, "open") in {"open", "action_proposed"}:
                gap_status[gap_key] = "action_proposed"

            task = _record_backfill_task(work, action, round_no=next_round, run_id=run_id)
            task_id = task["search_task_id"]
            task["status"] = "running"
            action_status[action.action_id] = "running"
            gap_status[gap_key] = "searching"

            result = search_executor.search(
                action.query,
                source_family=action.target_source_family,
                max_results=5,
            )
            executed_queries.add(action.query.strip().lower())

            # Only genuinely NEW candidates count as potential gain.
            new_candidates = [
                c for c in result.candidates
                if c.source_id not in known_source_ids
            ]

            event_id = _stable_event_id(run_id, next_round, action.slot_id, action.query)

            if result.status == "failed":
                task["status"] = "failed"
                task["completed_at"] = _utc_now()
                action_status[action.action_id] = "failed"
                consecutive_provider_failures += 1
                _record_backfill_event(
                    work, action, task_id=task_id, event_id=event_id, round_no=next_round,
                    run_id=run_id, result=result, new_candidates=[],
                )
                round_event_ids.append(event_id)
                round_actions_meta.append(_action_meta(
                    action, "failed", result, new_candidates=[], accepted_evidence_ids=[],
                ))
                if consecutive_provider_failures >= max_provider_failures:
                    # stop condition 8: provider consecutive failures.
                    stop_reason = "provider_consecutive_failure"
                    break
                continue

            consecutive_provider_failures = 0
            task["status"] = "completed"
            task["completed_at"] = _utc_now()

            ev_units = evidence_builder.build(
                query=action.query,
                slot=work.claim_slots.get(action.slot_id, {}),
                source_family=action.target_source_family,
                candidates=new_candidates,
                search_event_id=event_id,
            )
            accepted_evidence_ids: list[str] = []
            for ev in ev_units:
                _record_backfill_evidence(
                    work, ev, slot_id=action.slot_id, search_event_id=event_id, run_id=run_id,
                )
                round_new_evidence.append(ev.evidence_id)
                accepted_evidence_ids.append(ev.evidence_id)
                if ev.content_cluster_id and ev.content_cluster_id not in round_new_cluster:
                    round_new_cluster.append(ev.content_cluster_id)
                slot_evidence_added[action.slot_id] = slot_evidence_added.get(action.slot_id, 0) + 1

            for cand in new_candidates:
                known_source_ids.add(cand.source_id)
                if cand.source_id not in round_new_source:
                    round_new_source.append(cand.source_id)

            # SearchEvent is recorded ONCE (append-only), never mutated by later
            # evidence. Evidence links back via originating_search_event_ids.
            _record_backfill_event(
                work, action, task_id=task_id, event_id=event_id, round_no=next_round,
                run_id=run_id, result=result, new_candidates=new_candidates,
                accepted_evidence_ids=accepted_evidence_ids,
            )
            round_event_ids.append(event_id)

            outcome = "completed" if accepted_evidence_ids else "no_new_evidence"
            action_status[action.action_id] = outcome
            round_actions_meta.append(_action_meta(
                action, outcome, result,
                new_candidates=new_candidates, accepted_evidence_ids=accepted_evidence_ids,
            ))

        # ── recompute CoverageSnapshot + SnapshotDiff for this round ──
        after = build_evaluable_coverage_report(work)
        record_snapshot(work, after, round_no=next_round, run_id=run_id)

        gaps_after, _ = derive_gaps(after, work)
        keys_after = {_gap_key(g) for g in gaps_after}
        round_resolved = [
            key for key in (_gap_key(g) for g in open_gaps) if key not in keys_after
        ]
        resolved_gap_keys.extend(round_resolved)
        for key in round_resolved:
            gap_status[key] = "resolved"

        for key in keys_after:
            slot_id = key.split(":")[0]
            if gap_status.get(key, "open") == "resolved":
                continue
            if slot_evidence_added.get(slot_id, 0) > 0:
                gap_status[key] = "partially_resolved"

        diff = build_snapshot_diff(
            before,
            after,
            new_source_ids=round_new_source,
            new_evidence_ids=round_new_evidence,
            resolved_gap_ids=[
                g.gap_id for g in open_gaps if _gap_key(g) in round_resolved
            ],
            remaining_gap_ids=[g.gap_id for g in gaps_after],
        )

        no_gain_action_ids = {
            a["action_id"]
            for a in round_actions_meta if a["outcome"] == "no_new_evidence"
        }
        for action in selected:
            if action.action_id in no_gain_action_ids:
                per_slot_no_gain[action.slot_id] = per_slot_no_gain.get(action.slot_id, 0) + 1
            else:
                per_slot_no_gain[action.slot_id] = 0

        rounds.append(BackfillRoundResult(
            round_no=next_round,
            executed_action_ids=[a["action_id"] for a in round_actions_meta],
            executed_actions=round_actions_meta,
            new_source_ids=round_new_source,
            new_evidence_ids=round_new_evidence,
            new_content_cluster_ids=round_new_cluster,
            search_event_ids=round_event_ids,
            snapshot_before=before,
            snapshot_after=after,
            snapshot_diff=diff,
            action_status_by_id=dict(action_status),
            gap_status_by_key=dict(gap_status),
            stopped_reason=stop_reason,
        ))
        snapshot = after
        next_round += 1

        # ── remaining stop conditions ──
        if is_degraded(work):
            stop_reason = "store_degraded"
            break
        if any(v >= 2 for v in per_slot_no_gain.values()):
            # stop condition 5: same slot no_new_evidence twice in a row.
            stop_reason = "slot_no_new_evidence_exhausted"
            break
        if total_executed >= max_total_actions:
            # stop condition 4: total action budget.
            stop_reason = "action_budget_exhausted"
            break
        if stop_reason is not None:
            break

    if stop_reason is None:
        stop_reason = "max_rounds_reached"

    # Stop but unresolved -> mark ResearchGap exhausted (approved expression stays null).
    final_gaps, _ = derive_gaps(snapshot, work)
    for g in final_gaps:
        key = _gap_key(g)
        if gap_status.get(key, g.status) in _OPEN_GAP_STATUSES:
            gap_status[key] = "exhausted"
            if key not in exhausted_gap_keys:
                exhausted_gap_keys.append(key)

    new_sources_total = sorted({sid for r in rounds for sid in r.new_source_ids})
    new_evidence_total = sorted({eid for r in rounds for eid in r.new_evidence_ids})
    stats = {
        "rounds_executed": len(rounds),
        "actions_executed": total_executed,
        "new_sources_total": len(new_sources_total),
        "new_evidence_total": len(new_evidence_total),
        "resolved_slot_count": sum(
            1 for r in rounds for t in r.snapshot_diff.get("slot_transitions", {}).values()
            if t.get("after") == "satisfied"
        ),
        "exhausted_gap_count": len(exhausted_gap_keys),
        "no_new_evidence_action_count": sum(
            1 for r in rounds for a in r.executed_actions if a["outcome"] == "no_new_evidence"
        ),
        "failed_action_count": sum(
            1 for r in rounds for a in r.executed_actions if a["outcome"] == "failed"
        ),
        "query_repeat_count": 0,  # enforced by executed_queries dedup
        "approved_research_gap_expression_count": 0,  # never auto-approved
    }

    return BackfillRunResult(
        run_id=run_id,
        rounds=rounds,
        final_snapshot=dict(snapshot),
        final_store=work,
        executed_action_ids=executed_action_ids,
        resolved_gap_keys=resolved_gap_keys,
        exhausted_gap_keys=exhausted_gap_keys,
        stopped_reason=stop_reason,
        stats=stats,
    )


def _action_meta(
    action: SuggestedSearchAction,
    outcome: str,
    result: BackfillSearchResult,
    *,
    new_candidates: Sequence[BackfillSourceCandidate],
    accepted_evidence_ids: Sequence[str],
) -> dict[str, Any]:
    return {
        "action_id": action.action_id,
        "gap_id": action.gap_id,
        "slot_id": action.slot_id,
        "action_type": action.action_type,
        "query": action.query,
        "target_source_family": action.target_source_family,
        "outcome": outcome,
        "provider": result.provider,
        "provider_result_count": result.result_count,
        "new_source_count": len(new_candidates),
        "new_evidence_count": len(accepted_evidence_ids),
    }
