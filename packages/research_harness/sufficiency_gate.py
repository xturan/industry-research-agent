"""Phase B.1 — Shadow CoverageReport Integration (research-contract-refactor).

Computes a DUAL-TRACK (raw vs duplicate-adjusted) coverage report over
ResearchContract + Evidence + Claims + ResearchGaps + shadow source clustering.

THREE-STATE SEMANTICS (review 2026-08-04): satisfied / unsatisfied / not_evaluable.
- Historical checkpoints that lack structured key fields or search_events must
  report not_evaluable, never false.
- Readiness gains an "unknown" state; not_evaluable slots are NOT counted into
  coverage=0 (coverage denominator = evaluable slots only).

HARD BOUNDARIES: SHADOW ONLY. Computes / records / compares / exposes
would_block potential. NEVER blocks Editor1, triggers backfill, downgrades
claims, approves writing expressions, changes routing, or alters the final
report. Content cluster is only a distinct-content PROXY, never true
independent-source independence.

Legacy `build_shadow_sufficiency_report(*, contract, evidence, claims, sources)`
is kept as a thin compatibility wrapper over the same core.
"""

from __future__ import annotations

from typing import Any

from packages.research_harness.research_contract import CONTRACT_VERSION, compile_research_contract
from packages.research_harness.source_cluster import cluster_sources

REPORT_VERSION = "coverage_report_v1"
_CONFLICT_MARKERS = ["矛盾", "冲突", "不一致", "存疑", "contradict"]
SAT = "satisfied"
UNSAT = "unsatisfied"
NE = "not_evaluable"


def _canonical_family(raw: Any) -> str:
    from packages.sources.local_source_patterns import canonical_source_family
    return canonical_source_family(raw)


def _evidence_families(ev: dict, src_family_by_id: dict[str, str]) -> set[str]:
    fams: set[str] = set()
    for sid in [ev.get("source_id")] + list(ev.get("source_ids", []) or []):
        if sid and str(sid) in src_family_by_id:
            fams.add(src_family_by_id[str(sid)])
    if not fams and ev.get("source_family"):
        fams.add(_canonical_family(ev.get("source_family")))
    return fams


def _slot_evidence(
    slot: dict,
    evidence: list[dict],
    src_family_by_id: dict[str, str],
) -> list[dict]:
    slot_family = slot["source_family"]
    return [e for e in evidence if slot_family in _evidence_families(e, src_family_by_id)]


def _contradiction_status(
    slot: dict, evidence: list[dict], src_family_by_id: dict[str, str]
) -> str:
    slot_ev = _slot_evidence(slot, evidence, src_family_by_id)
    if not slot_ev:
        return NE  # no evidence -> cannot assess contradiction
    lims = [
        str(lim)
        for e in slot_ev
        for lim in e.get("limitations", [])
        if isinstance(lim, str)
    ]
    return "unresolved" if any(m in "".join(lims) for m in _CONFLICT_MARKERS) else "none"


def _field_requirements_status(
    slot: dict, evidence: list[dict], src_family_by_id: dict[str, str]
) -> str:
    """Three-state field-requirements gate.

    - no key_fields declared -> satisfied
    - evidence schema does NOT carry any declared key field -> not_evaluable
    - fields carried but values missing / failing mandatory+any_of -> unsatisfied
    - fields carried and satisfied -> satisfied
    """
    slot_ev = _slot_evidence(slot, evidence, src_family_by_id)
    key_fields = [k for k in slot.get("key_fields", []) if k]
    if not key_fields:
        return SAT
    if not slot_ev:
        return NE
    carried = {k for ev in slot_ev for k in key_fields if k in ev}
    if not carried:
        return NE  # schema does not carry any declared key field
    present = {k for k in carried if any(ev.get(k) for ev in slot_ev if k in ev)}

    field_requirements = slot.get("field_requirements")
    mode = str(slot.get("field_validation_mode") or "legacy_any_key_field")
    if isinstance(field_requirements, dict) and mode == "strict":
        mandatory = [str(f) for f in field_requirements.get("mandatory_fields", []) if f]
        any_of = [str(f) for f in field_requirements.get("any_of_fields", []) if f]
        try:
            min_opt = int(field_requirements.get("minimum_optional_fields", 0))
        except (TypeError, ValueError):
            min_opt = 0
        if mandatory and not all(k in present for k in mandatory):
            return UNSAT
        present_any = sum(1 for k in any_of if k in present)
        return SAT if present_any >= max(0, min_opt) else UNSAT
    return SAT if present else UNSAT


def _distinct_content_count(source_ids: list[str], cluster_output: dict) -> int:
    source_to_cluster = {
        str(sid): c["content_cluster_id"]
        for c in cluster_output.get("clusters", [])
        for sid in c.get("source_ids", [])
    }
    return len({source_to_cluster[sid] for sid in source_ids if sid in source_to_cluster})


def _claim_slot_ids(
    claim: dict, contract: dict, evidence_map: dict, src_family_by_id: dict[str, str]
) -> list[str]:
    slots = [s for sec in contract.get("sections", []) for s in sec.get("claim_slots", [])]
    slot_ids: list[str] = []
    raw_required = claim.get("required_source_family")
    for slot in slots:
        slot_family = slot["source_family"]
        if raw_required and _canonical_family(raw_required) == slot_family:
            slot_ids.append(slot["slot_id"])
            continue
        for eid in claim.get("evidence_ids", []):
            ev = evidence_map.get(str(eid))
            if ev and slot_family in _evidence_families(ev, src_family_by_id):
                slot_ids.append(slot["slot_id"])
                break
    return slot_ids


def _search_execution(slot: dict, search_events: list[dict], plan: dict) -> dict:
    rounds = list(plan.get("search_rounds", []) or []) if isinstance(plan, dict) else []
    executed = len(search_events) if isinstance(search_events, list) else 0
    successful = sum(1 for ev in search_events if not ev.get("error"))
    searched_families: set[str] = set()
    completed_rounds: set[str] = set()
    for ev in search_events:
        fam = ev.get("target_source_family") or ev.get("source_family")
        if fam:
            searched_families.add(_canonical_family(fam))
        rnd = ev.get("round") or ev.get("round_number")
        if rnd is not None:
            completed_rounds.add(str(rnd))
    slot_family = slot["source_family"]
    if executed == 0:
        sufficiency = NE  # no search record -> cannot conclude absence
    elif slot_family in searched_families:
        sufficiency = SAT  # this family was searched
    else:
        sufficiency = NE  # searched but not this family -> cannot conclude
    return {
        "planned_task_count": len(rounds),
        "executed_task_count": executed,
        "successful_task_count": successful,
        "failed_task_count": executed - successful,
        "searched_source_families": sorted(searched_families),
        "pending_high_priority_tasks": 0,
        "search_rounds_completed": len(completed_rounds),
        "stop_reason": "no_search_record" if executed == 0 else "search_executed",
        "search_sufficiency_status": sufficiency,
    }


def _family_compliance_status(
    *,
    slot_family: str,
    evidence_count: int,
    search: dict,
) -> str:
    """Three-state family compliance: satisfied if evidence exists; unsatisfied
    only when the family was actually searched and no evidence found; else
    not_evaluable (can't conclude absence without a search record)."""
    if evidence_count > 0:
        return SAT
    if search["search_sufficiency_status"] == SAT:
        return UNSAT  # searched this family, no evidence
    return NE


def _count_status(ok: bool, search_sufficiency: str) -> str:
    """Three-state count gate: a sub-threshold count is only truly unsatisfied
    when the family was actually searched; without a search record it is
    not_evaluable (we cannot tell "not found" from "never searched")."""
    if ok:
        return SAT
    if search_sufficiency == SAT:
        return UNSAT
    return NE


def _slot_status(gate_statuses: list[str]) -> str:
    """Three-state slot status from a list of three-state gates."""
    if any(g == UNSAT for g in gate_statuses):
        return UNSAT
    if any(g == NE for g in gate_statuses):
        return NE
    return SAT


def _slot_report(
    slot: dict,
    *,
    contract: dict,
    evidence: list[dict],
    claims: list[dict],
    sources: list[dict],
    src_family_by_id: dict[str, str],
    cluster_output: dict,
    search_events: list[dict],
    plan: dict,
) -> dict:
    slot_family = slot["source_family"]
    slot_ev = _slot_evidence(slot, evidence, src_family_by_id)
    supporting_evidence_ids = [e["evidence_id"] for e in slot_ev if e.get("evidence_id")]
    supporting_source_ids = [
        s["source_id"] for s in sources
        if isinstance(s, dict) and s.get("source_id")
        and _canonical_family(s.get("source_family")) == slot_family
    ]
    for ev in slot_ev:
        for sid in [ev.get("source_id")] + list(ev.get("source_ids", []) or []):
            if sid and str(sid) not in supporting_source_ids:
                supporting_source_ids.append(str(sid))

    evidence_count = len(set(supporting_evidence_ids))
    raw_count = len(set(supporting_source_ids))
    distinct_count = _distinct_content_count(list(set(supporting_source_ids)), cluster_output)

    evidence_map = {str(e.get("evidence_id")): e for e in evidence}
    claim_ids: list[str] = []
    for claim in claims:
        if slot["slot_id"] in _claim_slot_ids(claim, contract, evidence_map, src_family_by_id):
            claim_ids.append(str(claim.get("claim_id")))

    # ── separate count thresholds (review 2026-08-04: never reuse one min for
    #    both evidence-items and source counts) ──
    min_evidence_items = int(slot.get("min_evidence") or 1)
    min_raw_sources = int(slot.get("min_raw_supporting_sources") or min_evidence_items)
    min_distinct_sources = int(slot.get("min_distinct_content_sources") or min_evidence_items)
    min_independent_sources = slot.get("min_independent_sources")

    search = _search_execution(slot, search_events, plan)
    family_compliance = _family_compliance_status(
        slot_family=slot_family, evidence_count=evidence_count, search=search
    )
    primary_satisfied = (
        SAT if not slot.get("primary_source_required") else family_compliance
    )
    field_status = _field_requirements_status(slot, evidence, src_family_by_id)
    contradiction = _contradiction_status(slot, evidence, src_family_by_id)
    contradiction_gate = (
        SAT if contradiction == "none" else UNSAT if contradiction == "unresolved" else NE
    )

    search_suff = search["search_sufficiency_status"]
    count_raw_ok = bool(evidence_count >= min_evidence_items and raw_count >= min_raw_sources)
    count_dup_ok = bool(
        evidence_count >= min_evidence_items and distinct_count >= min_distinct_sources
    )
    count_raw_status = _count_status(count_raw_ok, search_suff)
    count_dup_status = _count_status(count_dup_ok, search_suff)

    # Deterministic exact-duplicate dedup: collapse sources in exact-content-hash
    # clusters (safe for the formal path). Reprint merges stay counted separately.
    supporting_set = set(supporting_source_ids)
    exact_dedup_removed = 0
    for cluster in cluster_output.get("clusters", []):
        if "exact_content_hash" not in cluster.get("duplicate_reason", []):
            continue
        members_in_slot = [s for s in cluster.get("source_ids", []) if s in supporting_set]
        if len(members_in_slot) > 1:
            exact_dedup_removed += len(members_in_slot) - 1
    exact_adjusted_count = max(0, raw_count - exact_dedup_removed)

    raw_status = _slot_status(
        [count_raw_status, family_compliance, primary_satisfied, field_status, contradiction_gate]
    )
    dup_status = _slot_status(
        [count_dup_status, family_compliance, primary_satisfied, field_status, contradiction_gate]
    )
    if raw_status == SAT and dup_status == UNSAT:
        transition = "satisfied_to_unsatisfied"
    elif raw_status == UNSAT and dup_status == SAT:
        transition = "unsatisfied_to_satisfied"
    elif raw_status == NE or dup_status == NE:
        transition = "not_evaluable"
    else:
        transition = "stable"

    blocking_reasons: list[str] = []
    if distinct_count < min_distinct_sources:
        blocking_reasons.append(
            f"distinct supporting content count {distinct_count} "
            f"is below required count {min_distinct_sources}"
        )
    if family_compliance == UNSAT:
        blocking_reasons.append(f"searched {slot_family} but no evidence found")
    if field_status == UNSAT:
        blocking_reasons.append("field requirements not satisfied")
    if contradiction == "unresolved":
        blocking_reasons.append("unresolved contradiction among evidence")

    return {
        "slot_id": slot["slot_id"],
        "section_id": slot["section_id"],
        "priority": slot.get("required", "required"),
        "source_family": slot_family,
        "required_source_families": [slot_family],
        "supporting_evidence_count": evidence_count,
        "supporting_claim_count": len(set(claim_ids)),
        "raw_supporting_source_count": raw_count,
        # Tiered counting (A2 freeze, 2026-08-04):
        # - exact_duplicate_adjusted_count : DETERMINISTIC dedup (same content
        #   hash / canonical URL) — usable by the formal path.
        # - likely_reprint_adjusted_count  : additionally collapses high-conf
        #   reprints — ADVISORY ONLY (warning), never drives the gate.
        # - distinct_supporting_content_count : all-merges distinct (shadow).
        "exact_duplicate_adjusted_count": exact_adjusted_count,
        "likely_reprint_adjusted_count": distinct_count,
        "distinct_supporting_content_count": distinct_count,
        "min_evidence_items": min_evidence_items,
        "min_raw_supporting_sources": min_raw_sources,
        "min_distinct_content_sources": min_distinct_sources,
        "min_independent_sources": min_independent_sources,
        "source_family_compliance": family_compliance,
        "primary_source_required": bool(slot.get("primary_source_required")),
        "primary_source_satisfied": primary_satisfied,
        "field_requirements_satisfied": field_status,
        "contradiction_status": contradiction,
        "independence_requirement_status": NE,
        "content_distinctness_proxy_satisfied": (
            SAT if distinct_count >= min_distinct_sources else UNSAT
        ),
        "search_sufficiency_status": search["search_sufficiency_status"],
        "raw_status": raw_status,
        "duplicate_adjusted_status": dup_status,
        "transition": transition,
        "affected_claim_ids": list(dict.fromkeys(claim_ids)),
        "blocking_reasons": blocking_reasons,
        "search_execution": search,
    }


def _section_readiness(
    section: dict, slot_rows: list[dict], *, critical_gate_enabled: bool
) -> dict:
    sec_slots = [r for r in slot_rows if r["section_id"] == section["section_id"]]
    non_optional = [r for r in sec_slots if r["priority"] != "optional"]

    def _track_status(key: str) -> str:
        statuses = [r[key] for r in non_optional]
        critical_unsat = [
            r for r in sec_slots
            if r["priority"] == "critical" and r[key] == UNSAT
        ]
        if critical_gate_enabled and critical_unsat:
            return "blocked"
        if not statuses:
            return "unknown"
        if all(s == SAT for s in statuses):
            return "ready"
        if any(s == UNSAT for s in statuses):
            return "partial"
        if any(s == NE for s in statuses):
            return "unknown"
        return "partial"

    raw = _track_status("raw_status")
    dup = _track_status("duplicate_adjusted_status")
    transition = "stable" if raw == dup else f"{raw}_to_{dup}"
    return {
        "section_id": section["section_id"],
        "title": section.get("title", ""),
        "raw_status": raw,
        "duplicate_adjusted_status": dup,
        "transition": transition,
        "blocking_reasons": [
            b
            for r in non_optional if r["duplicate_adjusted_status"] == UNSAT
            for b in r["blocking_reasons"]
        ][:6],
    }


def _research_gap_shadow_eligibility(gap: dict, contract: dict, search_events: list[dict]) -> dict:
    gap = dict(gap)
    searched_families = {
        _canonical_family(ev.get("target_source_family") or ev.get("source_family"))
        for ev in search_events
        if ev.get("target_source_family") or ev.get("source_family")
    }
    executed = len(search_events)
    slot_family = _canonical_family(gap.get("source_family"))
    all_searched = executed > 0 and (not slot_family or slot_family in searched_families)
    if all_searched:
        gap["shadow_reportability"] = "eligible_if_enabled"
        gap["shadow_report_expression"] = (
            f"经已执行的官方政策、地方政府及相关公开来源检索，"
            f"目前未发现可核验的{slot_family}材料"
        )
        gap["shadow_approval_reasons"] = [
            "all required source families searched",
            "search executed",
            "no pending high-priority search task",
        ]
    else:
        gap["shadow_reportability"] = NE
        gap["shadow_report_expression"] = ""
        gap["shadow_approval_reasons"] = []
    gap["approved_report_expression"] = None  # never approved in shadow
    return gap


def _coverage_stats(slot_rows: list[dict], key: str) -> dict:
    rows = [r for r in slot_rows if r["priority"] != "optional"]
    satisfied = sum(1 for r in rows if r[key] == SAT)
    insufficient = sum(1 for r in rows if r[key] == UNSAT)
    not_evaluable = sum(1 for r in rows if r[key] == NE)
    evaluable = satisfied + insufficient
    return {
        "satisfied_slot_count": satisfied,
        "insufficient_slot_count": insufficient,
        "not_evaluable_slot_count": not_evaluable,
        "evaluable_slot_count": evaluable,
        "coverage": round(satisfied / max(1, evaluable), 4),
    }


def build_shadow_coverage_report(
    state: dict[str, Any], *, cluster_threshold: float = 0.90
) -> dict[str, Any]:
    """Build the full dual-track Shadow CoverageReport from a graph state.

    cluster_threshold controls the auto-merge similarity used for the
    duplicate_adjusted track. "raw" track always uses raw_supporting_source_count
    (threshold-independent). blocking-rule hits are aggregated from candidates.
    """
    plan = state.get("plan")
    injected = state.get("contract")
    if isinstance(injected, dict) and injected.get("sections"):
        contract = injected
    else:
        contract = compile_research_contract(plan) if isinstance(plan, dict) else {}
    evidence = [e for e in (state.get("evidence") or []) if isinstance(e, dict)]
    claims = [c for c in (state.get("claims") or []) if isinstance(c, dict)]
    sources = [s for s in (state.get("sources") or []) if isinstance(s, dict)]
    search_events = [e for e in (state.get("search_events") or []) if isinstance(e, dict)]
    research_gaps = [g for g in (state.get("research_gaps") or []) if isinstance(g, dict)]

    if not contract.get("sections"):
        return {
            "report_version": REPORT_VERSION,
            "mode": "shadow",
            "shadow_only": True,
            "status": "no_contract",
            "contract_id": None,
            "clustering_version": "source_cluster_v1",
        }

    cluster_output = cluster_sources(sources, high_threshold=cluster_threshold)
    src_family_by_id = {
        str(s["source_id"]): _canonical_family(s.get("source_family"))
        for s in sources if s.get("source_id")
    }

    all_slots = [s for sec in contract.get("sections", []) for s in sec.get("claim_slots", [])]
    critical_slots = [s for s in all_slots if s.get("required") == "critical"]
    critical_gate_enabled = bool(critical_slots)

    slot_rows = [
        _slot_report(
            slot,
            contract=contract,
            evidence=evidence,
            claims=claims,
            sources=sources,
            src_family_by_id=src_family_by_id,
            cluster_output=cluster_output,
            search_events=search_events,
            plan=plan,
        )
        for slot in all_slots
    ]

    sections = [
        _section_readiness(sec, slot_rows, critical_gate_enabled=critical_gate_enabled)
        for sec in contract.get("sections", [])
    ]

    raw_stats = _coverage_stats(slot_rows, "raw_status")
    dup_stats = _coverage_stats(slot_rows, "duplicate_adjusted_status")

    def _report_readiness(section_status_key: str) -> str:
        statuses = [s[section_status_key] for s in sections]
        if any(s == "blocked" for s in statuses):
            return "blocked"
        if any(s == "partial" for s in statuses):
            return "partial"
        if any(s == "unknown" for s in statuses):
            return "unknown"
        return "ready" if statuses and all(s == "ready" for s in statuses) else "partial"

    raw_ready = len([s for s in sections if s["raw_status"] == "ready"])
    dup_ready = len([s for s in sections if s["duplicate_adjusted_status"] == "ready"])
    would_block_raw = critical_gate_enabled and any(
        r["priority"] == "critical" and r["raw_status"] == UNSAT for r in slot_rows
    )
    would_block_dup = critical_gate_enabled and any(
        r["priority"] == "critical" and r["duplicate_adjusted_status"] == UNSAT for r in slot_rows
    )
    if not critical_gate_enabled:
        would_block_raw = would_block_dup = False

    upgraded_gaps = [
        _research_gap_shadow_eligibility(g, contract, search_events)
        for g in research_gaps
    ]
    warnings = list(contract.get("contract_warnings", []))

    # Advisory: high-confidence reprints (likely same content origin) — NEVER a
    # gate input, only a warning so reviewers know raw source count may overstate
    # independent support.
    for row in slot_rows:
        raw = row.get("raw_supporting_source_count", 0)
        likely = row.get("likely_reprint_adjusted_count", raw)
        if likely < raw:
            warnings.append({
                "code": "SOURCE_SUPPORT_MAY_SHARE_SAME_CONTENT_ORIGIN",
                "slot_id": row["slot_id"],
                "raw_source_count": raw,
                "likely_distinct_content_count": likely,
            })

    # blocking-rule hits aggregated from candidates, counting ONLY the 3
    # precision-guard rules (not generic similarity labels).
    _BLOCKING_RULES = {"critical_fact_conflict", "summary_or_excerpt", "document_type_incompatible"}
    blocking_hits: dict[str, int] = {}
    for c in cluster_output.get("candidates", []):
        for reason in c.get("duplicate_reason", []):
            if reason in _BLOCKING_RULES:
                blocking_hits[reason] = blocking_hits.get(reason, 0) + 1

    report = {
        "report_version": REPORT_VERSION,
        "mode": "shadow",
        "shadow_only": True,
        "contract_id": contract.get("contract_version", CONTRACT_VERSION),
        "clustering_version": cluster_output.get("clustering_version", "source_cluster_v1"),
        "critical_gate": {
            "enabled": critical_gate_enabled,
            "reason": None if critical_gate_enabled else "NO_CRITICAL_SLOT_DECLARED",
        },
        "summary": {
            "raw_required_slot_coverage": raw_stats["coverage"],
            "duplicate_adjusted_required_slot_coverage": dup_stats["coverage"],
            "raw_satisfied_slot_count": raw_stats["satisfied_slot_count"],
            "raw_insufficient_slot_count": raw_stats["insufficient_slot_count"],
            "raw_not_evaluable_slot_count": raw_stats["not_evaluable_slot_count"],
            "duplicate_adjusted_satisfied_slot_count": dup_stats["satisfied_slot_count"],
            "duplicate_adjusted_insufficient_slot_count": dup_stats["insufficient_slot_count"],
            "duplicate_adjusted_not_evaluable_slot_count": dup_stats["not_evaluable_slot_count"],
            "raw_ready_section_count": raw_ready,
            "duplicate_adjusted_ready_section_count": dup_ready,
            "would_block_if_raw_enabled": would_block_raw,
            "would_block_if_duplicate_adjusted_enabled": would_block_dup,
            "raw_readiness": _report_readiness("raw_status"),
            "duplicate_adjusted_readiness": _report_readiness("duplicate_adjusted_status"),
            "would_change_decision": would_block_raw != would_block_dup,
        },
        "sections": sections,
        "slots": slot_rows,
        "research_gaps": upgraded_gaps,
        "warnings": warnings,
        "blocking_rule_hits": blocking_hits,
        "auto_merge_threshold": cluster_threshold,
        # ── legacy-compat aliases ──
        "contract_warnings": warnings,
        "critical_gate_enabled": critical_gate_enabled,
        "section_readiness": sections,
        "slot_counts": slot_rows,
        "report_ready_raw": (
            raw_stats["satisfied_slot_count"] == raw_stats["evaluable_slot_count"]
            and raw_stats["evaluable_slot_count"] > 0
        ),
        "report_ready_shadow": (
            dup_stats["satisfied_slot_count"] == dup_stats["evaluable_slot_count"]
            and dup_stats["evaluable_slot_count"] > 0
        ),
        "note": (
            "shadow only - computes/records/compares; never blocks Editor1, "
            "never triggers backfill, never changes claim strength, never "
            "approves writing expressions, never changes the final report"
        ),
    }
    return report


def build_shadow_sufficiency_report(
    *,
    contract: dict[str, Any],
    evidence: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Legacy compatibility wrapper over build_shadow_coverage_report."""
    state = {
        "plan": None,
        "contract": contract,
        "evidence": evidence,
        "claims": claims,
        "sources": sources,
        "search_events": [],
        "research_gaps": [],
    }
    return build_shadow_coverage_report(state)
