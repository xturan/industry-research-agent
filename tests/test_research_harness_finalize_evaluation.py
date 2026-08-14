"""B.3.3b — central run-termination semantics (finalize_evaluation_run).

Verifies that SearchTask run-close is independent of finalize_report and covers
every termination path (REPORT_COMPLETED / HUMAN_REVIEW / BUDGET_EXHAUSTED /
PROVIDER_FAILED / GRAPH_ERROR / USER_CANCELLED), with HUMAN_REVIEW treated as a
suspend (resumable), never a cancel.
"""

from __future__ import annotations

import pytest

from packages.research_harness.eval_persistence import RunEvaluationStore
from packages.research_harness.evaluation_recorder import (
    TERMINATION_REASONS,
    finalize_evaluation_run,
    resume_suspended_tasks,
)


def _store(*statuses: str) -> RunEvaluationStore:
    store = RunEvaluationStore("run")
    for i, status in enumerate(statuses, start=1):
        store.record_search_task({
            "search_task_id": f"t{i}", "run_id": "run", "query": f"q{i}",
            "round": i, "status": status, "schema_version": "search_task_v1",
        })
    return store


def _statuses(store: RunEvaluationStore) -> dict[str, str]:
    return {t["search_task_id"]: t["status"] for t in store.search_tasks.values()}


# ── terminal paths close planned/running ────────────────────────────────────

def test_report_completed_closes_planned_running():
    store = _store("planned", "running", "completed", "failed")
    finalize_evaluation_run(store, termination_reason="REPORT_COMPLETED")
    assert _statuses(store) == {"t1": "cancelled", "t2": "cancelled",
                                "t3": "completed", "t4": "failed"}
    assert store.search_tasks["t1"]["cancelled_reason"] == "run_close_planned_not_executed"


@pytest.mark.parametrize("reason,expected_cancel_reason", [
    ("BUDGET_EXHAUSTED", "budget_exhausted"),
    ("PROVIDER_FAILED", "provider_failed"),
    ("GRAPH_ERROR", "graph_error"),
    ("USER_CANCELLED", "user_cancelled"),
])
def test_terminal_reasons_map_to_cancel_reason(reason, expected_cancel_reason):
    store = _store("planned", "running")
    finalize_evaluation_run(store, termination_reason=reason)
    assert all(t["status"] == "cancelled" for t in store.search_tasks.values())
    assert all(t["cancelled_reason"] == expected_cancel_reason
               for t in store.search_tasks.values())


# ── HUMAN_REVIEW is a suspend, not a cancel ─────────────────────────────────

def test_human_review_suspends_not_cancels():
    store = _store("planned", "running", "completed")
    finalize_evaluation_run(store, termination_reason="HUMAN_REVIEW")
    statuses = _statuses(store)
    assert statuses["t1"] == "suspended"
    assert statuses["t2"] == "suspended"
    assert statuses["t3"] == "completed"  # untouched
    assert store.search_tasks["t1"]["suspended_reason"] == "suspended_for_human_review"
    # no semantically-ambiguous running/planned task is left behind
    assert not {s for s in statuses.values()} & {"planned", "running"}


def test_resume_suspended_tasks_reopens_to_planned():
    store = _store("planned", "running", "completed")
    finalize_evaluation_run(store, termination_reason="HUMAN_REVIEW")
    resume_suspended_tasks(store)
    statuses = _statuses(store)
    assert statuses["t1"] == "planned"
    assert statuses["t2"] == "planned"
    assert statuses["t3"] == "completed"
    assert store.search_tasks["t1"].get("suspended_reason") is None


# ── scoping + validation ────────────────────────────────────────────────────

def test_round_id_scoping_closes_only_that_round():
    store = _store("planned", "running", "planned")
    # force rounds 1,2,3 (helper sets round == index)
    for i, t in enumerate(store.search_tasks.values(), start=1):
        t["round"] = i
    finalize_evaluation_run(store, termination_reason="REPORT_COMPLETED", round_id=1)
    statuses = _statuses(store)
    assert statuses["t1"] == "cancelled"
    assert statuses["t2"] == "running"
    assert statuses["t3"] == "planned"


def test_exclude_task_ids_leaves_task_untouched():
    store = _store("planned", "running")
    finalize_evaluation_run(store, termination_reason="REPORT_COMPLETED",
                            exclude_task_ids={"t2"})
    assert store.search_tasks["t1"]["status"] == "cancelled"
    assert store.search_tasks["t2"]["status"] == "running"


def test_unknown_termination_reason_raises():
    with pytest.raises(ValueError):
        finalize_evaluation_run(_store("planned"), termination_reason="NOPE")


def test_all_termination_reasons_are_declared():
    assert TERMINATION_REASONS == {
        "REPORT_COMPLETED", "HUMAN_REVIEW", "BUDGET_EXHAUSTED",
        "PROVIDER_FAILED", "GRAPH_ERROR", "USER_CANCELLED",
    }
