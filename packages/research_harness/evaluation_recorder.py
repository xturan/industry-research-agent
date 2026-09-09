"""Phase B.2 — Runner Integration: evaluation recording helpers.

Pure functions that populate a RunEvaluationStore from graph state/result, so
the LangGraph wrapper nodes (real_nodes) can record ClaimSlots / SearchEvents /
EvidenceUnits / ClaimCards without touching bytecode internals.

All recording is fail-open: a write error sets evaluation_persistence_status =
"degraded" but never blocks the research run.
"""

from __future__ import annotations

import hashlib
from typing import Any

from packages.research_harness.eval_persistence import RunEvaluationStore

_KNOWN_KEY_FIELDS = (
    "project_name", "company", "amount", "stage", "region",
    "time_ref", "policy_tool", "subject", "operation_status", "operation_date",
)

_EVALUATION_SCHEMA = "evaluation_persistence_v1"


def ensure_store(state: dict[str, Any], result: dict[str, Any]) -> RunEvaluationStore:
    """Load (or create) the store from state, and mark persistence active."""
    data = state.get("evaluation_store")
    store = RunEvaluationStore.from_dict(data) if isinstance(data, dict) else RunEvaluationStore()
    if not store.run_id:
        store.run_id = str(state.get("run_id") or "")
    result["evaluation_persistence_status"] = "active"
    result["evaluation_persistence_schema"] = _EVALUATION_SCHEMA
    return store


def write_store(state: dict[str, Any], result: dict[str, Any], store: RunEvaluationStore,
                *, degraded_reason: str | None = None) -> None:
    """Write the store back to result; degrade visibly on failure."""
    result["evaluation_store"] = store.to_dict()
    if degraded_reason:
        result["evaluation_persistence_status"] = "degraded"
        result["evaluation_persistence_diagnostic"] = degraded_reason
    else:
        result["evaluation_persistence_status"] = "active"
    # Store write failures must not block the run (fail-open).
    result.setdefault("evaluation_persistence_fail_open", True)


def stable_search_event_id(*, run_id: str, round_no: int, slot_id: str, query: str) -> str:
    digest = hashlib.md5((query or "").strip().lower().encode("utf-8")).hexdigest()[:8]
    return f"se:{run_id}:r{round_no}:{slot_id}:{digest}"


def stable_search_task_id(*, run_id: str, round_no: int, slot_id: str, query: str) -> str:
    digest = hashlib.md5((query or "").strip().lower().encode("utf-8")).hexdigest()[:8]
    return f"st:{run_id}:r{round_no}:{slot_id}:{digest}"


def record_claim_slots(store: RunEvaluationStore, plan: dict[str, Any]) -> None:
    """Record final compiled ClaimSlots from the ResearchContract."""
    from packages.research_harness.research_contract import compile_research_contract

    contract = compile_research_contract(plan)
    slots = []
    for sec in contract.get("sections", []):
        for s in sec.get("claim_slots", []):
            slots.append({
                "slot_id": s["slot_id"],
                "section_id": s["section_id"],
                "description": s.get("research_question") or s.get("coverage_required") or "",
                "criticality": s.get("required", "required"),
                "min_evidence_items": s.get("min_evidence", 1),
                "min_raw_supporting_sources": None,
                "min_distinct_content_sources": None,
                "min_independent_sources": None,
                "field_requirements": {
                    "mandatory": list(s.get("field_requirements", {}).get("mandatory_fields", [])),
                    "any_of": list(s.get("field_requirements", {}).get("any_of_fields", [])),
                },
                "source_obligations": {
                    "required_families": [s.get("source_family")],
                    "primary_source_required": bool(s.get("primary_source_required")),
                },
                "max_assertion_level": "fact_confirmed",
                "schema_version": "claim_slot_v1",
            })
    store.record_claim_slots(slots)


def record_search_tasks(store: RunEvaluationStore, plan: dict[str, Any], run_id: str) -> None:
    """Record PLANNED SearchTasks from plan.search_rounds BEFORE execution.

    Must run before search executes (collect node), so planned-but-never-run
    tasks are not lost and the planned->running->completed/failed chain is
    complete. Never derive SearchTasks from search results.
    """
    for rnd in plan.get("search_rounds") or []:
        if not isinstance(rnd, dict):
            continue
        round_no = int(rnd.get("round_number") or 1)
        phrases = [str(p) for p in rnd.get("search_phrases", []) if str(p).strip()]
        target_slots = [str(x) for x in rnd.get("target_dimensions", []) if str(x).strip()]
        if not phrases:
            continue
        for phrase in phrases[:1]:
            tid = stable_search_task_id(
                run_id=run_id, round_no=round_no,
                slot_id="|".join(target_slots) or "_", query=phrase,
            )
            store.record_search_task({
                "search_task_id": tid,
                "run_id": run_id,
                "slot_ids": target_slots,
                "query": phrase,
                "target_source_families": [],
                "required_fields": [],
                "round": round_no,
                "status": "planned",
                "idempotency_key": tid,
                "origin": "plan",
                "originating_gap_id": "",
                "originating_action_id": "",
                "schema_version": "search_task_v1",
            })


def mark_search_tasks_terminal(
    store: RunEvaluationStore, state: dict[str, Any], run_id: str,
) -> None:
    """Set SearchTask terminal status from actual execution.

    Tasks are planned per plan.search_rounds (dimension ids); execution events
    carry round numbers. Match by round: a task whose round executed at least
    one search event is completed; a round with only failures marks the task
    failed. Tasks in rounds with no events stay planned (never ran).
    """
    executed_rounds: set[int] = set()
    failed_rounds: set[int] = set()
    for ev in state.get("search_events") or []:
        if not isinstance(ev, dict):
            continue
        rnd = int(ev.get("round") or ev.get("round_number") or 1)
        if ev.get("error"):
            failed_rounds.add(rnd)
        else:
            executed_rounds.add(rnd)
    for task in store.search_tasks.values():
        t_rnd = int(task.get("round") or 1)
        if t_rnd in failed_rounds:
            task["status"] = "failed"
        elif t_rnd in executed_rounds:
            task["status"] = "completed"


def close_search_tasks(
    store: RunEvaluationStore,
    *,
    round_id: int | None = None,
    exclude_task_ids: set[str] | None = None,
    reason: str = "run_close_planned_not_executed",
) -> None:
    """Close planned/running SearchTasks as cancelled (with reason).

    Scoping (prevents premature global close):
    - round_id: only tasks whose round == round_id are closed (None = all rounds).
    - exclude_task_ids: task ids left untouched (None = no exclusions).

    Run-close semantics: no task may stay planned/running forever. Tasks never
    executed are explicitly closed as cancelled (with reason), so downstream can
    distinguish "omitted by accident" from "deliberately abandoned".
    Budget-exhausted/superseded can be set by callers with a reason.

    Lifecycle: build_claims may re-run each round after Evidence updates, so it
    must NOT close all planned/running tasks (a still-pending backfill task
    would be cancelled before it reaches the provider). Close per-round (a
    round that is done executing) or at run-close (all remaining).
    """
    exclude_task_ids = exclude_task_ids or set()
    for task in store.search_tasks.values():
        if task.get("status") not in {"planned", "running"}:
            continue
        if round_id is not None and int(task.get("round") or 1) != round_id:
            continue
        if task.get("search_task_id") in exclude_task_ids:
            continue
        task["status"] = "cancelled"
        task["cancelled_reason"] = reason


# ── B.3.3b central run-termination semantics ────────────────────────────────

#: Termination reasons for a research run (set independently of report
#: generation). Human Review is a *pause* (tasks suspended, resumable); every
#: other reason is a *terminal close*.
TERMINATION_REASONS = {
    "REPORT_COMPLETED",
    "HUMAN_REVIEW",
    "BUDGET_EXHAUSTED",
    "PROVIDER_FAILED",
    "GRAPH_ERROR",
    "USER_CANCELLED",
}

_TERMINAL_CLOSE_REASON: dict[str, str] = {
    "REPORT_COMPLETED": "run_close_planned_not_executed",
    "BUDGET_EXHAUSTED": "budget_exhausted",
    "PROVIDER_FAILED": "provider_failed",
    "GRAPH_ERROR": "graph_error",
    "USER_CANCELLED": "user_cancelled",
}


def _suspend_tasks(
    store: RunEvaluationStore,
    *,
    round_id: int | None,
    exclude_task_ids: set[str] | None,
    reason: str = "suspended_for_human_review",
) -> None:
    exclude_task_ids = exclude_task_ids or set()
    for task in store.search_tasks.values():
        if task.get("status") not in {"planned", "running"}:
            continue
        if round_id is not None and int(task.get("round") or 1) != round_id:
            continue
        if task.get("search_task_id") in exclude_task_ids:
            continue
        task["status"] = "suspended"
        task["suspended_reason"] = reason


def finalize_evaluation_run(
    store: RunEvaluationStore,
    *,
    termination_reason: str,
    round_id: int | None = None,
    exclude_task_ids: set[str] | None = None,
) -> None:
    """Run-close semantics for ALL termination paths, independent of report
    generation.

    - HUMAN_REVIEW is a PAUSE: planned/running tasks become `suspended`
      (resumable via resume_suspended_tasks), never cancelled.
    - Every other reason closes remaining planned/running tasks as `cancelled`
      with a reason mapped from the termination reason.

    This is the single place the runner closes SearchTasks at the end of a run,
    so `finalize_report` is NOT required to run for tasks to be closed.
    """
    if termination_reason not in TERMINATION_REASONS:
        raise ValueError(f"unknown termination_reason: {termination_reason!r}")
    if termination_reason == "HUMAN_REVIEW":
        _suspend_tasks(store, round_id=round_id, exclude_task_ids=exclude_task_ids)
        return
    close_search_tasks(
        store,
        round_id=round_id,
        exclude_task_ids=exclude_task_ids,
        reason=_TERMINAL_CLOSE_REASON.get(termination_reason, "run_close_planned_not_executed"),
    )


def resume_suspended_tasks(store: RunEvaluationStore) -> None:
    """Re-open `suspended` tasks to `planned` when a paused run resumes."""
    for task in store.search_tasks.values():
        if task.get("status") == "suspended":
            task["status"] = "planned"
            task.pop("suspended_reason", None)


def record_search_events(
    store: RunEvaluationStore, state: dict[str, Any], run_id: str,
    slot_by_family: dict[str, str] | None = None,
) -> None:
    """Record actual search execution from state.search_events (deduped, stable id).

    slot_by_family maps canonical source_family -> slot_id so a search event
    with only a source_family can still be attributed to the right slot (real
    graph search events may not carry slot_ids/query).
    """
    slot_by_family = slot_by_family or {}
    for ev in state.get("search_events") or []:
        if not isinstance(ev, dict):
            continue
        family = str(ev.get("source_family") or ev.get("target_source_family") or "")
        slot_ids = [str(x) for x in ev.get("slot_ids", []) if str(x).strip()]
        if not slot_ids and family and family in slot_by_family:
            slot_ids = list(slot_by_family[family])
        query = str(
            ev.get("query") or ev.get("phrase") or ev.get("_gap_phrase")
            or ev.get("round_objective") or ""
        )
        round_no = int(ev.get("round") or ev.get("round_number") or 1)
        sid = stable_search_event_id(
            run_id=run_id, round_no=round_no,
            slot_id="|".join(slot_ids) or "_", query=query,
        )
        status = "failed" if ev.get("error") else "completed"
        accepted_sources = [str(x) for x in ev.get("accepted_source_ids", [])] or []
        store.record_search_event({
            "search_event_id": sid,
            "run_id": run_id,
            "slot_ids": slot_ids,
            "query": query,
            "source_family": family,
            "provider": str(ev.get("provider") or "web_search"),
            "status": status,
            "result_count": int(ev.get("result_count") or 0),
            "accepted_source_count": len(accepted_sources),
            "accepted_evidence_count": int(ev.get("accepted_evidence_count") or 0),
            "accepted_source_ids": accepted_sources,
            "failure_reason": str(ev.get("error") or "")[:200] if ev.get("error") else None,
            "idempotency_key": sid,
            "schema_version": "search_event_v1",
        })


def _field_status(evidence: dict[str, Any], field: str) -> dict[str, Any]:
    if field in evidence:
        value = evidence.get(field)
        status = "present" if value not in (None, "", []) else "not_found"
        return {"status": status, "value": value if status == "present" else None}
    return {"status": "not_extracted", "value": None}


def record_evidence_units(
    store: RunEvaluationStore, evidence: list[dict[str, Any]],
    sources: list[dict[str, Any]], contract: dict[str, Any], run_id: str,
) -> None:
    """Record EvidenceUnitRecords with key_field status + family->slot links."""
    src_family = {str(s.get("source_id")): str(s.get("source_family") or "") for s in sources}
    slot_by_family: dict[str, list[str]] = {}
    for sec in contract.get("sections", []):
        for s in sec.get("claim_slots", []):
            slot_by_family.setdefault(s.get("source_family"), []).append(s["slot_id"])
    for ev in evidence:
        if not isinstance(ev, dict) or not ev.get("evidence_id"):
            continue
        family = str(ev.get("source_family") or src_family.get(str(ev.get("source_id")), ""))
        supports_slots = list(slot_by_family.get(family, []))
        key_fields = {
            f: _field_status(ev, f)
            for f in _KNOWN_KEY_FIELDS if f in ev or f in ("operation_status", "operation_date")
        }
        store.record_evidence_unit({
            "evidence_id": str(ev["evidence_id"]),
            "run_id": run_id,
            "source_id": str(ev.get("source_id") or ""),
            "content_cluster_id": ev.get("content_cluster_id"),
            "quoted_span": str(ev.get("quoted_span") or ""),
            "source_family": family,
            "source_family_status": "classified" if family else "unclassified",
            "is_primary_source": str(ev.get("support_type") or "").startswith("primary"),
            "supports_slot_ids": supports_slots,
            "key_fields": key_fields,
            "key_field_extraction_status": (
                "completed"
                if any(kv.get("status") != "not_extracted" for kv in key_fields.values())
                else "not_extracted"
            ),
            "quote_verification_status": (
                "verified" if ev.get("quote_verified") else "not_verified"
            ),
            "idempotency_key": f"ev:{ev['evidence_id']}",
            "schema_version": "evidence_unit_v2",
        })


def record_claim_cards(
    store: RunEvaluationStore, claims: list[dict[str, Any]], run_id: str,
) -> None:
    """Record ClaimCardRecords with explicit slot + evidence links."""
    for claim in claims:
        if not isinstance(claim, dict) or not claim.get("claim_id"):
            continue
        slot_ids = [str(x) for x in claim.get("slot_ids", [])] or (
            [str(claim["primary_slot_id"])] if claim.get("primary_slot_id") else []
        )
        primary_slot = str(claim.get("primary_slot_id") or (slot_ids[0] if slot_ids else ""))
        store.record_claim_card({
            "claim_id": str(claim["claim_id"]),
            "primary_slot_id": primary_slot,
            "slot_ids": slot_ids,
            "evidence_ids": [str(x) for x in claim.get("evidence_ids", [])],
            "claim_type": str(claim.get("claim_type") or "factual"),
            "epistemic_status": str(claim.get("epistemic_status") or "unsupported"),
            "assertion_level": str(claim.get("assertion_level_label") or "mention_only"),
            "max_allowed_assertion_level": str(claim.get("max_assertion_level") or "mention_only"),
            "approval_status": "approved" if claim.get("supported") else "pending",
            "limitations": list(claim.get("limitations", [])),
            # C.1: persist the claim prose so the structured shadow editor can
            # build paragraphs that explicitly bind claim_ids + evidence_ids.
            "text": str(claim.get("text") or claim.get("claim_text") or ""),
            "idempotency_key": f"claim:{claim['claim_id']}",
            "schema_version": "claim_card_v1",
        })


def record_snapshot(
    store: RunEvaluationStore, report: dict[str, Any], *, round_no: int, run_id: str,
) -> dict[str, Any]:
    """Append an immutable CoverageSnapshot for a round."""
    return store.snapshot({
        "coverage_report_id": f"cr:{run_id}:r{round_no}",
        "run_id": run_id,
        "calculation_round": round_no,
        "slot_reports": report.get("slot_reports", []),
        "report_readiness": report.get("readiness", "unknown"),
        "evaluation_completeness": report.get("evaluation_completeness", 0.0),
        "required_slot_count": report.get("required_slot_count", 0),
        "evaluable_required_slot_count": report.get("evaluable_required_slot_count", 0),
        "not_evaluable_required_slot_count": report.get("not_evaluable_required_slot_count", 0),
        "warnings": report.get("warnings", []),
        "schema_version": "coverage_report_v2",
    })
