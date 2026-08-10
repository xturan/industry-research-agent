"""Phase B.2 — Evaluability Persistence.

Goal: a new run's CoverageReport must no longer be dominated by not_evaluable
because the runner only persisted raw state. This module defines the minimal
structured records the runner must persist so the system can distinguish:

- no search happened                  -> not_evaluable
- searched but no qualifying evidence -> unsatisfied
- searched, evidence insufficient     -> unsatisfied
- evidence satisfies requirements     -> satisfied

Append-only per-run store: ClaimSlot / SearchTask / SearchEvent / EvidenceUnit
(key_fields status) / ClaimCard (slot links). Coverage snapshots are immutable
per round.

Decision policy (this phase):
- Gate count         = raw_supporting_source_count
- exact_duplicate_adjusted = deterministic reference (usable)
- likely_reprint_adjusted  = advisory only (warning, never gate)
- independent_source_count = not computed
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

KeyFieldStatus = Literal[
    "present", "not_found", "not_applicable", "extraction_failed", "not_extracted"
]
SearchTaskStatus = Literal[
    "planned", "running", "completed", "failed", "cancelled", "budget_exhausted",
    "superseded", "suspended",
]
SearchEventStatus = Literal["completed", "failed"]


# ── 1. ResearchContract / ClaimSlot ─────────────────────────────────────────

class FieldRequirements(BaseModel):
    mandatory: list[str] = Field(default_factory=list)
    any_of: list[str] = Field(default_factory=list)


class SourceObligations(BaseModel):
    required_families: list[str] = Field(default_factory=list)
    primary_source_required: bool = False


class ClaimSlotRecord(BaseModel):
    slot_id: str
    section_id: str = ""
    description: str = ""
    criticality: Literal["critical", "required", "optional"] = "required"
    min_evidence_items: int = 1
    min_raw_supporting_sources: int | None = None
    min_distinct_content_sources: int | None = None
    min_independent_sources: int | None = None  # null until Source Independence
    field_requirements: FieldRequirements = Field(default_factory=FieldRequirements)
    source_obligations: SourceObligations = Field(default_factory=SourceObligations)
    max_assertion_level: str = "fact_confirmed"
    schema_version: str = "claim_slot_v1"


# ── 2. SearchTask (plan) / 3. SearchEvent (execution) ───────────────────────

class SearchTaskRecord(BaseModel):
    search_task_id: str
    run_id: str = ""
    slot_ids: list[str] = Field(default_factory=list)
    query: str = ""
    target_source_families: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    round: int = 1
    status: SearchTaskStatus = "planned"
    idempotency_key: str = ""
    created_at: str = ""
    completed_at: str | None = None
    # B.3.3 gap-backfill provenance: origin = "plan" (normal plan.search_rounds)
    # or "gap_backfill" (advisory backfill action). originating_* trace the
    # ResearchGap / SuggestedSearchAction that created this task.
    origin: Literal["plan", "gap_backfill"] = "plan"
    originating_gap_id: str = ""
    originating_action_id: str = ""
    # B.3.3b termination reasons (set by finalize_evaluation_run):
    # cancelled_reason / superseded_reason / suspended_reason.
    cancelled_reason: str | None = None
    superseded_reason: str | None = None
    suspended_reason: str | None = None
    schema_version: str = "search_task_v1"


class SearchEventRecord(BaseModel):
    search_event_id: str
    search_task_id: str = ""
    run_id: str = ""
    slot_ids: list[str] = Field(default_factory=list)
    query: str = ""
    source_family: str = ""
    provider: str = ""
    status: SearchEventStatus = "completed"
    result_count: int = 0
    accepted_source_count: int = 0
    accepted_evidence_count: int = 0
    accepted_source_ids: list[str] = Field(default_factory=list)
    accepted_evidence_ids: list[str] = Field(default_factory=list)
    failure_reason: str | None = None
    idempotency_key: str = ""
    executed_at: str = ""
    # B.3.3b explicit provider trace: configured_provider is what the policy
    # wanted, executed_provider is what actually answered, fallback_used/reason
    # explain any silent-ish fallback (e.g. anysearch -> tavily).
    configured_provider: str = ""
    executed_provider: str = ""
    fallback_used: bool = False
    fallback_reason: str = ""
    schema_version: str = "search_event_v1"


# ── 4. EvidenceUnit (key_fields extraction status) ──────────────────────────

class KeyFieldValue(BaseModel):
    status: KeyFieldStatus = "not_extracted"
    value: Any = None


class EvidenceUnitRecord(BaseModel):
    evidence_id: str
    run_id: str = ""
    source_id: str = ""
    content_cluster_id: str | None = None
    quoted_span: str = ""
    raw_start_offset: int | None = None
    raw_end_offset: int | None = None
    source_family: str = ""
    source_family_status: Literal["classified", "unclassified"] = "unclassified"
    is_primary_source: bool = False
    supports_slot_ids: list[str] = Field(default_factory=list)
    supports_claim_ids: list[str] = Field(default_factory=list)
    # Scheme B (review): evidence links BACK to the search event(s) that produced
    # its source. SearchEvent keeps accepted_source_ids and is never mutated when
    # evidence arrives later (append-only).
    originating_search_event_ids: list[str] = Field(default_factory=list)
    key_fields: dict[str, KeyFieldValue] = Field(default_factory=dict)
    key_field_extraction_status: Literal[
        "completed", "not_extracted", "extraction_failed"
    ] = "not_extracted"
    quote_verification_status: Literal["verified", "not_verified"] = "not_verified"
    idempotency_key: str = ""
    created_at: str = ""
    schema_version: str = "evidence_unit_v2"


# ── 5. ClaimCard + mapping ──────────────────────────────────────────────────

class ClaimCardRecord(BaseModel):
    claim_id: str
    primary_slot_id: str = ""
    slot_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    claim_type: str = "factual"
    epistemic_status: str = "unsupported"
    assertion_level: str = "mention_only"
    max_allowed_assertion_level: str = "mention_only"
    approval_status: Literal["approved", "rejected", "pending"] = "pending"
    limitations: list[str] = Field(default_factory=list)
    # C.1: the claim's prose (needed by the structured shadow editor).
    text: str = ""
    idempotency_key: str = ""
    created_at: str = ""
    schema_version: str = "claim_card_v1"


# ── Coverage Snapshot ───────────────────────────────────────────────────────

class CoverageSnapshot(BaseModel):
    coverage_report_id: str
    run_id: str = ""
    calculation_round: int = 1
    slot_reports: list[dict[str, Any]] = Field(default_factory=list)
    report_readiness: str = "unknown"
    evaluation_completeness: float = 0.0
    required_slot_count: int = 0
    evaluable_required_slot_count: int = 0
    not_evaluable_required_slot_count: int = 0
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    source_count_policy: dict[str, str] = Field(
        default_factory=lambda: {
            "gate_count": "raw_supporting_source_count",
            "exact_duplicate_adjusted": "deterministic_reference",
            "likely_reprint_adjusted": "advisory_only",
        }
    )
    computed_at: str = ""
    schema_version: str = "coverage_report_v2"


# ── Append-only per-run store ───────────────────────────────────────────────

class RunEvaluationStore:
    """Append-only per-run store of evaluation-relevant records.

    Idempotency: records are keyed by their stable ID. Re-recording the same ID
    with identical content is ignored (node retries); same ID with DIFFERENT
    content is recorded as an IDEMPOTENCY_CONFLICT diagnostic (not silently
    merged). Coverage counts always use unique IDs, never raw list length.
    """

    def __init__(self, run_id: str = "") -> None:
        self.run_id = run_id
        self.claim_slots: dict[str, dict[str, Any]] = {}
        self.search_tasks: dict[str, dict[str, Any]] = {}
        self.search_events: dict[str, dict[str, Any]] = {}
        self.evidence_units: dict[str, dict[str, Any]] = {}
        self.claim_cards: dict[str, dict[str, Any]] = {}
        self.snapshots: list[dict[str, Any]] = []
        self.idempotency_conflicts: list[dict[str, Any]] = []
        # True when persistence degraded (write failures); a degraded store must
        # not be trusted for further backfill (B.3.3 stop condition).
        self.degraded = False

    def copy(self) -> RunEvaluationStore:
        """Deep-copy via serialization (caller's store is never mutated)."""
        return RunEvaluationStore.from_dict(self.to_dict())

    # ── serialization (LangGraph checkpoint) ──
    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "claim_slots": self.claim_slots,
            "search_tasks": self.search_tasks,
            "search_events": self.search_events,
            "evidence_units": self.evidence_units,
            "claim_cards": self.claim_cards,
            "snapshots": self.snapshots,
            "idempotency_conflicts": self.idempotency_conflicts,
            "degraded": self.degraded,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RunEvaluationStore:
        store = cls((data or {}).get("run_id", ""))
        if not data:
            return store
        store.claim_slots = dict(data.get("claim_slots", {}))
        # Backfill new SearchTask provenance + reason fields for stores persisted
        # before those fields existed, so idempotent re-record of the same task
        # (e.g. build_evidence re-run on a resumed round) does not surface a
        # spurious IDEMPOTENCY_CONFLICT.
        store.search_tasks = {
            tid: {
                "origin": "plan",
                "originating_gap_id": "",
                "originating_action_id": "",
                "cancelled_reason": None,
                "superseded_reason": None,
                "suspended_reason": None,
                **dict(task),
            }
            for tid, task in (data.get("search_tasks") or {}).items()
        }
        # Backfill provider-fallback trace fields for older SearchEvents.
        store.search_events = {
            eid: {
                "configured_provider": "",
                "executed_provider": "",
                "fallback_used": False,
                "fallback_reason": "",
                **dict(event),
            }
            for eid, event in (data.get("search_events") or {}).items()
        }
        store.evidence_units = dict(data.get("evidence_units", {}))
        # Backfill claim text for stores persisted before C.1.
        store.claim_cards = {
            cid: {"text": "", **dict(card)}
            for cid, card in (data.get("claim_cards") or {}).items()
        }
        store.snapshots = list(data.get("snapshots", []))
        store.idempotency_conflicts = list(data.get("idempotency_conflicts", []))
        store.degraded = bool(data.get("degraded", False))
        return store

    # ── idempotent append helpers ──
    def _append_dedup(self, container: dict[str, dict[str, Any]], record_id: str,
                      rec: dict[str, Any], kind: str) -> bool:
        if record_id in container:
            if container[record_id] == rec:
                return False  # identical retry -> ignore
            self.idempotency_conflicts.append(
                {"record_id": record_id, "kind": kind, "diagnostic": "IDEMPOTENCY_CONFLICT"}
            )
            return False
        container[record_id] = rec
        return True

    def record_claim_slots(self, slots: list[dict[str, Any]]) -> None:
        for s in slots:
            rec = ClaimSlotRecord(**s).model_dump()
            self._append_dedup(self.claim_slots, rec["slot_id"], rec, "claim_slot")

    def record_search_task(self, task: dict[str, Any]) -> None:
        rec = SearchTaskRecord(**task).model_dump()
        self._append_dedup(self.search_tasks, rec["search_task_id"], rec, "search_task")

    def record_search_event(
        self, event: dict[str, Any], on_duplicate: str = "ignore_identical"
    ) -> None:
        rec = SearchEventRecord(**event).model_dump()
        self._append_dedup(self.search_events, rec["search_event_id"], rec, "search_event")

    def record_evidence_unit(self, ev: dict[str, Any]) -> None:
        rec = EvidenceUnitRecord(**ev).model_dump()
        self._append_dedup(self.evidence_units, rec["evidence_id"], rec, "evidence_unit")

    def record_claim_card(self, card: dict[str, Any]) -> None:
        rec = ClaimCardRecord(**card).model_dump()
        self._append_dedup(self.claim_cards, rec["claim_id"], rec, "claim_card")

    def snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        rec = CoverageSnapshot(**snapshot).model_dump()
        self.snapshots.append(rec)
        return rec

    def evaluation_link_diagnostics(self) -> dict[str, Any]:
        """Completeness rates for the 7 required link dimensions."""
        ev_ids = set(self.evidence_units)
        claim_ids = set(self.claim_cards)
        slot_ids = set(self.claim_slots)
        claim_slot_rate = len(claim_ids) / len(slot_ids) if slot_ids else 1.0
        task_terminal = sum(
            1 for t in self.search_tasks.values()
            if t.get("status") in {"completed", "failed", "cancelled", "budget_exhausted"}
        )
        task_rate = task_terminal / max(1, len(self.search_tasks))
        # SearchEvent recording denominator = ACTUAL provider invocations
        # (tasks that reached a terminal executed state), NOT all planned tasks.
        executed_tasks = sum(
            1 for t in self.search_tasks.values()
            if t.get("status") in {"completed", "failed"}
        )
        ev_linked = sum(1 for e in self.evidence_units.values() if e.get("supports_slot_ids"))
        ev_link_rate = ev_linked / max(1, len(ev_ids))
        claim_ev_linked = sum(1 for c in self.claim_cards.values() if c.get("evidence_ids"))
        claim_ev_link = claim_ev_linked / max(1, len(claim_ids))
        return {
            "claim_slot_trace_rate": round(claim_slot_rate, 4),
            "search_task_terminal_rate": round(task_rate, 4),
            "search_event_recording_rate": round(
                min(1.0, len(self.search_events) / max(1, executed_tasks)), 4
            ),
            "evidence_field_status_rate": round(
                sum(1 for e in self.evidence_units.values()
                    if e.get("key_field_extraction_status") != "not_extracted")
                / max(1, len(ev_ids)),
                4,
            ),
            "evidence_to_slot_link_rate": round(ev_link_rate, 4),
            "claim_to_evidence_link_rate": round(claim_ev_link, 4),
        }


# ── Three-state evaluator (consumes the store) ──────────────────────────────

def _field_satisfaction(ev: dict[str, Any], field: str) -> str:
    """present -> satisfied-gate; not_found -> unsatisfied-gate; else not_evaluable."""
    kv = ev.get("key_fields", {}).get(field, {})
    status = kv.get("status", "not_extracted")
    if status == "present":
        return "satisfied"
    if status in {"not_found", "not_applicable"}:
        return "unsatisfied"
    return "not_evaluable"  # not_extracted / extraction_failed


def evaluate_slot(slot: dict[str, Any], events: list[dict], evidence: list[dict]) -> dict:
    slot_id = slot["slot_id"]
    min_evidence = int(slot.get("min_evidence_items") or 1)
    min_raw = int(slot.get("min_raw_supporting_sources") or min_evidence)
    mandatory = list(slot.get("field_requirements", {}).get("mandatory", []))
    required_families = list(slot.get("source_obligations", {}).get("required_families", []))

    searched_events = [e for e in events if e.get("status") == "completed"]
    searched = len(searched_events) > 0
    if not searched:
        return {"slot_id": slot_id, "status": "not_evaluable",
                "reasons": ["no_search_event"], "evidence_count": 0, "raw_source_count": 0}

    # Searched but NO qualifying evidence -> unsatisfied (searched, nothing
    # found), never not_evaluable.
    if not evidence:
        return {"slot_id": slot_id, "status": "unsatisfied",
                "reasons": ["no_qualifying_evidence"], "evidence_count": 0, "raw_source_count": 0}

    # extraction completeness: evaluable as soon as AT LEAST ONE supporting
    # evidence has completed extraction (fields are aggregated across evidence).
    # Evidence that was not extracted simply does not contribute — it does not
    # make the slot not_evaluable (real runs include background evidence).
    extractions = [e.get("key_field_extraction_status") for e in evidence]
    extraction_done = any(x == "completed" for x in extractions) if extractions else False
    if not extraction_done:
        return {"slot_id": slot_id, "status": "not_evaluable",
                "reasons": ["evidence_extraction_incomplete"], "evidence_count": len(evidence),
                "raw_source_count": len({e.get("source_id") for e in evidence})}

    # field gates (mandatory): aggregate across evidence
    field_status = {}
    for f in mandatory:
        statuses = [_field_satisfaction(e, f) for e in evidence]
        if any(s == "satisfied" for s in statuses):
            field_status[f] = "satisfied"
        elif all(s == "unsatisfied" for s in statuses) and statuses:
            field_status[f] = "unsatisfied"
        else:
            field_status[f] = "not_evaluable"

    evidence_count = len(evidence)
    raw_count = len({e.get("source_id") for e in evidence})
    families_seen = {e.get("source_family") for e in evidence}
    family_ok = not required_families or any(f in families_seen for f in required_families)

    if any(v == "not_evaluable" for v in field_status.values()):
        return {"slot_id": slot_id, "status": "not_evaluable",
                "reasons": ["mandatory_field_not_extracted"], "field_status": field_status,
                "evidence_count": evidence_count, "raw_source_count": raw_count}

    missing = [f for f, v in field_status.items() if v == "unsatisfied"]
    satisfied = (
        evidence_count >= min_evidence
        and raw_count >= min_raw
        and not missing
        and family_ok
    )
    return {
        "slot_id": slot_id,
        "status": "satisfied" if satisfied else "unsatisfied",
        "reasons": [] if satisfied else (missing or ["below_threshold"]),
        "field_status": field_status,
        "evidence_count": evidence_count,
        "raw_source_count": raw_count,
        "family_ok": family_ok,
    }


def build_evaluable_coverage_report(store: RunEvaluationStore) -> dict:
    """Three-state CoverageReport from the persisted store.

    readiness:
    - any critical/required slot not_evaluable -> unknown (do not fake-ready)
    - any critical slot unsatisfied -> blocked
    - any required slot unsatisfied -> partial
    - all satisfied -> ready
    """
    required_slots = {
        sid: s for sid, s in store.claim_slots.items()
        if s.get("criticality") != "optional"
    }
    slot_reports = []
    for sid, slot in required_slots.items():
        events = [e for e in store.search_events.values() if sid in e.get("slot_ids", [])]
        evidence = [
            e for e in store.evidence_units.values()
            if sid in e.get("supports_slot_ids", [])
        ]
        slot_reports.append(evaluate_slot(slot, events, evidence))

    required_count = len(required_slots)
    evaluable = [r for r in slot_reports if r["status"] != "not_evaluable"]
    not_evaluable = required_count - len(evaluable)
    completeness = len(evaluable) / required_count if required_count else 0.0

    critical = [
        r for r in slot_reports
        if required_slots[r["slot_id"]]["criticality"] == "critical"
    ]
    if any(r["status"] == "not_evaluable" for r in critical):
        readiness = "unknown"
    elif any(r["status"] == "not_evaluable" for r in slot_reports):
        readiness = "unknown"
    elif any(r["status"] == "unsatisfied" for r in critical):
        readiness = "blocked"
    elif any(r["status"] == "unsatisfied" for r in slot_reports):
        readiness = "partial"
    else:
        readiness = "ready"

    return {
        "mode": "evaluable",
        "readiness": readiness,
        "evaluation_completeness": round(completeness, 4),
        "coverage_among_evaluable": round(
            sum(1 for r in evaluable if r["status"] == "satisfied") / max(1, len(evaluable)), 4
        ),
        "required_slot_count": required_count,
        "evaluable_required_slot_count": len(evaluable),
        "not_evaluable_required_slot_count": not_evaluable,
        "slot_reports": slot_reports,
        "schema_version": "coverage_report_v2",
    }


def build_runtime_coverage_report(
    *,
    run_id: str,
    evaluation_store: RunEvaluationStore | None,
    legacy_state: dict[str, Any],
    mode: Literal["evaluable_persistence", "legacy_shadow"],
    degraded: bool = False,
) -> dict[str, Any]:
    """Explicit two-mode Coverage entry point.

    - evaluable_persistence: reads ONLY the RunEvaluationStore; missing data is
      honestly not_evaluable, never back-filled from legacy_state.
    - legacy_shadow: original build_shadow_coverage_report (historical replay).

    New runs MUST use evaluable_persistence (no implicit switch). When
    `degraded` is true (store write failure), readiness is capped at "unknown" —
    a degraded run must never report ready.
    """
    if mode == "evaluable_persistence":
        report: dict[str, Any]
        if evaluation_store is None or not evaluation_store.claim_slots:
            report = {
                "readiness": "unknown",
                "evaluation_completeness": 0.0,
                "required_slot_count": 0,
                "evaluable_required_slot_count": 0,
                "not_evaluable_required_slot_count": 0,
                "slot_reports": [],
                "reasons": ["no_evaluation_store"],
            }
        else:
            report = build_evaluable_coverage_report(evaluation_store)
        if degraded and report.get("readiness") == "ready":
            report["readiness"] = "unknown"
            report["reasons"] = list(report.get("reasons", [])) + [
                "evaluation_persistence_degraded"
            ]
        report["coverage_input_source"] = "evaluable_persistence"
        report["coverage_schema_version"] = "coverage_report_v2"
        report["legacy_fallback_used"] = False
        report["mode"] = "evaluable_persistence"
        return report
    if mode == "legacy_shadow":
        from packages.research_harness.sufficiency_gate import build_shadow_coverage_report

        report = build_shadow_coverage_report(legacy_state)
        report["coverage_input_source"] = "legacy_shadow"
        report["coverage_schema_version"] = report.get("report_version", "coverage_report_v1")
        report["legacy_fallback_used"] = True
        report["mode"] = "legacy_shadow"
        return report
    raise ValueError(f"unknown coverage mode: {mode}")
