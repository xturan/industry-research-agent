"""Phase B.3 — Gap Retrieval (B.3.1 derivation + B.3.2 action proposal).

Semantic boundary (review 2026-08-04):

- **ResearchGap**: ONLY for `unsatisfied` slots — the system already searched and
  extracted, but evidence is still insufficient. May drive targeted backfill.
- **EvaluationGap**: for `not_evaluable` slots — the system did NOT complete the
  evaluation actions (search not run / extraction failed / link missing). Never
  turned into "未发现" conclusions.

B.3.1 derives ResearchGap/EvaluationGap from a CoverageSnapshot.
B.3.2 proposes deterministic SuggestedSearchActions (templates, no execution).

approved_report_expression stays null until search sufficiency is proven.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal

GapType = Literal[
    "evidence_count", "raw_source_count", "distinct_content_count",
    "mandatory_field_missing", "any_of_field_missing", "source_family_missing",
    "primary_source_missing", "contradiction_unresolved",
]
EvaluationReason = Literal[
    "search_not_executed", "search_failed", "field_extraction_not_run",
    "field_extraction_failed", "source_family_unclassified",
    "evidence_slot_link_missing", "persistence_degraded",
]
RepairAction = Literal[
    "execute_existing_task", "retry_search", "retry_extraction",
    "classify_source", "repair_slot_link", "manual_inspection",
]
ActionType = Literal[
    "search_missing_field", "search_missing_source_family", "search_primary_source",
    "increase_source_count", "resolve_contradiction",
]


@dataclass(frozen=True)
class ResearchGapRecord:
    gap_id: str
    run_id: str
    coverage_snapshot_id: str
    slot_id: str
    section_id: str = ""
    criticality: str = "required"
    gap_type: GapType = "evidence_count"
    missing_fields: tuple[str, ...] = ()
    missing_source_families: tuple[str, ...] = ()
    current_evidence_count: int = 0
    required_evidence_count: int | None = None
    current_source_count: int = 0
    required_source_count: int | None = None
    supporting_evidence_ids: tuple[str, ...] = ()
    completed_search_task_ids: tuple[str, ...] = ()
    reportability_status: Literal[
        "not_reviewed", "not_reportable", "reportable_with_limitation"
    ] = "not_reviewed"
    status: Literal[
        "open", "action_proposed", "searching", "partially_resolved",
        "resolved", "exhausted", "superseded",
    ] = "open"
    created_at: str = ""
    schema_version: str = "research_gap_v1"


@dataclass(frozen=True)
class EvaluationGapRecord:
    evaluation_gap_id: str
    run_id: str
    coverage_snapshot_id: str
    slot_id: str
    reason: EvaluationReason = "search_not_executed"
    related_search_task_ids: tuple[str, ...] = ()
    related_evidence_ids: tuple[str, ...] = ()
    suggested_repair_action: RepairAction = "execute_existing_task"
    status: Literal["open", "resolved", "ignored"] = "open"
    schema_version: str = "evaluation_gap_v1"


@dataclass(frozen=True)
class SuggestedSearchAction:
    action_id: str
    run_id: str
    gap_id: str
    slot_id: str
    action_type: ActionType = "increase_source_count"
    query: str = ""
    target_source_family: str | None = None
    required_fields: tuple[str, ...] = ()
    exclude_source_ids: tuple[str, ...] = ()
    exclude_canonical_urls: tuple[str, ...] = ()
    priority: int = 0
    expected_information_gain: float = 0.0
    search_round: int = 1
    budget_cost: int = 1
    status: Literal[
        "proposed", "approved", "running", "completed", "failed",
        "cancelled", "no_new_evidence",
    ] = "proposed"
    generation_reason: str = ""
    schema_version: str = "suggested_search_action_v1"


# ── deterministic query templates ───────────────────────────────────────────

_FIELD_QUERY_KEYWORD: dict[str, str] = {
    "operation_date": "投运时间",
    "operation_status": "投运状态",
    "project_name": "项目名称",
    "amount": "投资金额",
    "company": "公司",
    "stage": "建设阶段",
    "region": "区域",
    "time_ref": "时间",
}

_FAMILY_QUERY_KEYWORD: dict[str, str] = {
    "company_disclosure": "公告 订单 收入",
    "exchange_disclosure": "公告 订单 收入",
    "policy_document": "政策 文件",
    "local_official": "官方 动态",
    "tender_procurement": "招标 中标 项目",
    "official_statistics": "统计 数据",
    "industry_research": "行业 报告",
    "environmental_land": "环评 土地",
    "commercial_media": "媒体 报道",
}


def _stable_id(*parts: str) -> str:
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()[:12]


# ── B.3.1 gap derivation ────────────────────────────────────────────────────

def _supporting_evidence(store: Any, slot_id: str) -> list[dict]:
    return [
        e for e in store.evidence_units.values()
        if slot_id in e.get("supports_slot_ids", [])
    ]


def _derive_research_gaps(
    slot_report: dict, slot: dict, store: Any, snapshot_id: str,
) -> list[ResearchGapRecord]:
    slot_id = slot_report["slot_id"]
    supporting = _supporting_evidence(store, slot_id)
    ev_ids = tuple(e["evidence_id"] for e in supporting)
    reasons = slot_report.get("reasons", [])
    field_status = slot_report.get("field_status", {})
    current_ev = int(slot_report.get("evidence_count", len(supporting)))
    current_src = int(slot_report.get("raw_source_count", 0))
    min_evidence = int(slot.get("min_evidence_items") or 1)
    min_raw = int(slot.get("min_raw_supporting_sources") or min_evidence)
    required_families = list(slot.get("source_obligations", {}).get("required_families", []))
    primary_required = bool(slot.get("source_obligations", {}).get("primary_source_required"))

    gaps: list[ResearchGapRecord] = []
    run_id = str(getattr(store, "run_id", "") or "")

    def _mk(gap_type: GapType, **kw) -> ResearchGapRecord:
        return ResearchGapRecord(
            gap_id=f"gap:{_stable_id(snapshot_id, slot_id, gap_type)}",
            run_id=run_id, coverage_snapshot_id=snapshot_id, slot_id=slot_id,
            section_id=slot.get("section_id", ""), criticality=slot.get("criticality", "required"),
            current_evidence_count=current_ev, required_evidence_count=min_evidence,
            current_source_count=current_src, required_source_count=min_raw,
            supporting_evidence_ids=ev_ids, gap_type=gap_type, **kw,
        )

    if current_ev < min_evidence:
        gaps.append(_mk("evidence_count"))
    if current_src < min_raw:
        gaps.append(_mk("raw_source_count"))
    for f, st in field_status.items():
        if st == "unsatisfied":
            gaps.append(_mk("mandatory_field_missing", missing_fields=(f,)))
    if not slot_report.get("family_ok", True) and required_families:
        fams_seen = {e.get("source_family") for e in supporting}
        missing = [f for f in required_families if f not in fams_seen]
        if missing:
            gaps.append(_mk("source_family_missing", missing_source_families=tuple(missing)))
    if primary_required and not slot_report.get("family_ok", True):
        gaps.append(_mk("primary_source_missing"))
    if any("contradiction" in r for r in reasons):
        gaps.append(_mk("contradiction_unresolved"))
    return gaps


def _derive_evaluation_gap(
    slot_report: dict, slot: dict, store: Any, snapshot_id: str,
) -> EvaluationGapRecord:
    slot_id = slot_report["slot_id"]
    reasons = slot_report.get("reasons", [])
    run_id = str(getattr(store, "run_id", "") or "")
    if "no_search_event" in reasons:
        reason: EvaluationReason = "search_not_executed"
        repair: RepairAction = "execute_existing_task"
    elif "evidence_extraction_incomplete" in reasons:
        reason, repair = "field_extraction_not_run", "retry_extraction"
    else:
        reason, repair = "search_failed", "retry_search"
    related_ev = tuple(e["evidence_id"] for e in _supporting_evidence(store, slot_id))
    return EvaluationGapRecord(
        evaluation_gap_id=f"egap:{_stable_id(snapshot_id, slot_id, reason)}",
        run_id=run_id, coverage_snapshot_id=snapshot_id, slot_id=slot_id,
        reason=reason, suggested_repair_action=repair,
        related_evidence_ids=related_ev,
    )


def derive_gaps(
    coverage_report: dict, store: Any,
) -> tuple[list[ResearchGapRecord], list[EvaluationGapRecord]]:
    """Derive ResearchGaps (unsatisfied) + EvaluationGaps (not_evaluable)."""
    snapshot_id = (
        coverage_report.get("coverage_snapshot_id")
        or coverage_report.get("coverage_report_id")
        or f"cr:{getattr(store, 'run_id', '')}"
    )
    research_gaps: list[ResearchGapRecord] = []
    evaluation_gaps: list[EvaluationGapRecord] = []
    for slot_report in coverage_report.get("slot_reports", []):
        if not isinstance(slot_report, dict):
            continue
        slot = store.claim_slots.get(slot_report["slot_id"], {})
        if slot_report.get("status") == "unsatisfied":
            research_gaps.extend(_derive_research_gaps(slot_report, slot, store, snapshot_id))
        elif slot_report.get("status") == "not_evaluable":
            evaluation_gaps.append(_derive_evaluation_gap(slot_report, slot, store, snapshot_id))
    return research_gaps, evaluation_gaps


# ── B.3.2 action proposal (deterministic, NO execution) ─────────────────────

_PRIORITY_WEIGHTS = {
    "critical": 100, "required": 50,
    "mandatory_field_missing": 40, "primary_source_missing": 35,
    "source_family_missing": 30, "evidence_count": 15,
    "raw_source_count": 15, "contradiction_unresolved": 20,
    "duplicate_query_penalty": -50, "no_gain_penalty": -40,
}


def _query_for_gap(gap: ResearchGapRecord, base_query: str) -> tuple[ActionType, str, str | None]:
    if gap.gap_type == "mandatory_field_missing" and gap.missing_fields:
        f = gap.missing_fields[0]
        kw = _FIELD_QUERY_KEYWORD.get(f, f)
        return "search_missing_field", f"{base_query} {kw}", None
    if gap.gap_type == "source_family_missing" and gap.missing_source_families:
        fam = gap.missing_source_families[0]
        kw = _FAMILY_QUERY_KEYWORD.get(fam, fam)
        return "search_missing_source_family", f"{base_query} {kw}", fam
    if gap.gap_type == "primary_source_missing":
        return "search_primary_source", f"{base_query} 官方 原始来源", None
    if gap.gap_type == "contradiction_unresolved":
        return "resolve_contradiction", f"{base_query} 状态", None
    return "increase_source_count", f"{base_query} 官方 公告 项目", None


def propose_search_actions(
    research_gaps: list[ResearchGapRecord],
    store: Any,
    *,
    base_query: str,
    executed_queries: set[str] | None = None,
    max_per_slot: int = 2,
) -> list[SuggestedSearchAction]:
    """Deterministic action proposal + priority scoring + dedup (no execution).

    Duplicate queries already executed are dropped (duplicate_query_penalty).
    """
    executed_queries = executed_queries or {
        str(ev.get("query") or "").strip().lower()
        for ev in store.search_events.values()
    }
    run_id = str(getattr(store, "run_id", "") or "")
    actions: list[SuggestedSearchAction] = []
    seen_queries: set[str] = set()
    per_slot: dict[str, int] = {}

    for gap in research_gaps:
        if per_slot.get(gap.slot_id, 0) >= max_per_slot:
            continue
        action_type, query, target_family = _query_for_gap(gap, base_query)
        norm_q = query.strip().lower()
        if not norm_q or norm_q in executed_queries or norm_q in seen_queries:
            continue
        seen_queries.add(norm_q)
        per_slot[gap.slot_id] = per_slot.get(gap.slot_id, 0) + 1

        priority = (
            _PRIORITY_WEIGHTS.get(gap.criticality, 50)
            + _PRIORITY_WEIGHTS.get(gap.gap_type, 15)
        )
        action_id = f"act:{_stable_id(
            run_id, gap.slot_id, gap.gap_type, norm_q, target_family or '_'
        )}"
        generation_reason = (
            f"Slot {gap.slot_id} gap {gap.gap_type} "
            f"missing={','.join(gap.missing_fields or gap.missing_source_families) or 'coverage'}"
        )
        actions.append(SuggestedSearchAction(
            action_id=action_id,
            run_id=run_id, gap_id=gap.gap_id, slot_id=gap.slot_id,
            action_type=action_type, query=query, target_source_family=target_family,
            required_fields=gap.missing_fields, priority=priority,
            expected_information_gain=0.5, generation_reason=generation_reason,
        ))
    actions.sort(key=lambda a: -a.priority)
    return actions


# ── snapshot diff ───────────────────────────────────────────────────────────

def build_snapshot_diff(before: dict, after: dict, *, new_source_ids, new_evidence_ids,
                        resolved_gap_ids, remaining_gap_ids) -> dict:
    slot_before = {r["slot_id"]: r["status"] for r in before.get("slot_reports", [])}
    slot_after = {r["slot_id"]: r["status"] for r in after.get("slot_reports", [])}
    transitions = {}
    for sid in set(slot_before) | set(slot_after):
        if slot_before.get(sid) != slot_after.get(sid):
            transitions[sid] = {"before": slot_before.get(sid), "after": slot_after.get(sid)}
    return {
        "before_snapshot_id": before.get("coverage_report_id"),
        "after_snapshot_id": after.get("coverage_report_id"),
        "new_source_ids": list(new_source_ids),
        "new_evidence_ids": list(new_evidence_ids),
        "resolved_gap_ids": list(resolved_gap_ids),
        "remaining_gap_ids": list(remaining_gap_ids),
        "slot_transitions": transitions,
        "evaluation_completeness_before": before.get("evaluation_completeness", 0.0),
        "evaluation_completeness_after": after.get("evaluation_completeness", 0.0),
        "information_gain": {
            "new_sources": len(new_source_ids),
            "new_evidence": len(new_evidence_ids),
            "resolved_slots": sum(1 for t in transitions.values() if t["after"] == "satisfied"),
        },
    }
