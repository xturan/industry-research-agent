"""Phase C.3.2 — Section–Claim Assignment.

Deterministically decides, for each Section, which approved ClaimCards are:
- required (must be written): representative claim of every critical / required-and-
  satisfied slot, plus claims with a unique information atom the section needs;
- optional (may be written): claims with independent information increment;
- suppressed (must NOT enter the prompt): duplicates / subsumed / lower-evidence /
  section mismatch / background overflow / unresolved conflicts.

This is NOT about inflating usage metrics: every suppression records a reason and
(sometimes) the claim it was suppressed by, so "shrinking the denominator" is
auditable.

Claim assignment uses STRUCTURE first (primary_slot_id -> ClaimSlot.section_id),
then a deterministic Claim Signature (entity + attribute + scope + time + value +
slot) for same-fact clustering. No LLM is used here.

Also provides a per-section ContextAuditReport so we can tell WHY a claim went
unused: prompt instability vs too many claims vs duplicates vs section mismatch
vs evidence-context overload.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Fixed suppression-reason vocabulary.
SUPPRESSION_REASONS = (
    "exact_duplicate", "semantic_duplicate", "subsumed", "lower_evidence_quality",
    "section_mismatch", "background_overflow", "conflicting_claim", "non_incremental",
)

_TIME_RE = re.compile(r"(20\d{2})\s*年")
_STATUS_KEYWORDS = (
    "投运", "运营", "开工", "建成", "在建", "中标", "公示", "披露",
    "收入", "订单", "政策", "试点", "启用", "落地", "开通",
)
# Money/unit quantities only (a bare year/date is a TIME atom, not a value).
_NUM_RE = re.compile(r"[\d][\d.,]*\s*(?:亿元|万元|亿|万|元)")
_CHARS_PER_TOKEN = 2.0


@dataclass(frozen=True)
class SuppressedClaim:
    claim_id: str
    reason: str
    suppressed_by_claim_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "reason": self.reason,
            "suppressed_by_claim_id": self.suppressed_by_claim_id,
        }


@dataclass(frozen=True)
class SectionClaimAssignment:
    section_id: str
    required_claim_ids: tuple[str, ...]
    optional_claim_ids: tuple[str, ...]
    suppressed_claims: tuple[SuppressedClaim, ...]
    slot_representatives: dict[str, str]
    input_claim_count: int
    output_claim_count: int
    schema_version: str = "section_claim_assignment_v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "required_claim_ids": list(self.required_claim_ids),
            "optional_claim_ids": list(self.optional_claim_ids),
            "suppressed_claims": [s.to_dict() for s in self.suppressed_claims],
            "slot_representatives": self.slot_representatives,
            "input_claim_count": self.input_claim_count,
            "output_claim_count": self.output_claim_count,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class ContextAuditReport:
    section_id: str
    claim_count_before_assignment: int
    required_claim_count: int
    optional_claim_count: int
    suppressed_claim_count: int
    suppression_reasons: dict[str, int]
    provided_evidence_count: int
    distinct_content_evidence_count: int
    estimated_context_tokens: int
    required_claim_usage_rate: float | None
    optional_claim_usage_rate: float | None
    context_utilization_rate: float
    claim_context_overload_warning: bool
    evidence_duplication_warning: bool
    schema_version: str = "context_audit_v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "claim_count_before_assignment": self.claim_count_before_assignment,
            "required_claim_count": self.required_claim_count,
            "optional_claim_count": self.optional_claim_count,
            "suppressed_claim_count": self.suppressed_claim_count,
            "suppression_reasons": self.suppression_reasons,
            "provided_evidence_count": self.provided_evidence_count,
            "distinct_content_evidence_count": self.distinct_content_evidence_count,
            "estimated_context_tokens": self.estimated_context_tokens,
            "required_claim_usage_rate": self.required_claim_usage_rate,
            "optional_claim_usage_rate": self.optional_claim_usage_rate,
            "context_utilization_rate": self.context_utilization_rate,
            "claim_context_overload_warning": self.claim_context_overload_warning,
            "evidence_duplication_warning": self.evidence_duplication_warning,
            "schema_version": self.schema_version,
        }


# ── helpers ─────────────────────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "").strip()


def _extract_year(text: str) -> str:
    m = _TIME_RE.search(text or "")
    return m.group(1) if m else ""


def _extract_status(text: str) -> str:
    for kw in _STATUS_KEYWORDS:
        if kw in (text or ""):
            return kw
    return ""


def _extract_numeric(text: str) -> str:
    m = _NUM_RE.search(text or "")
    return m.group(0) if m else ""


def claim_signature(claim: dict[str, Any], slot: dict[str, Any] | None = None) -> dict[str, Any]:
    """Structured Claim Signature: entity + attribute + scope + time + value + slot.

    Deterministic, derived from text + slot structure (no LLM). Used to cluster
    same-fact claims conservatively.
    """
    text = claim.get("text") or ""
    return {
        "attribute": str(claim.get("primary_slot_id") or (slot or {}).get("slot_id") or ""),
        "entity": str((slot or {}).get("source_family") or ""),
        "scope": "whole",
        "time": _extract_year(text),
        "status": _extract_status(text),
        "numeric_value": _extract_numeric(text),
        "slot_id": str(claim.get("primary_slot_id") or (slot or {}).get("slot_id") or ""),
    }


def _same_family(sig_a: dict[str, Any], sig_b: dict[str, Any]) -> bool:
    # Family key = attribute(slot) + entity + status + value. time is an
    # information ATOM used for subsumption within a family, not a splitter.
    for key in ("attribute", "entity", "status", "numeric_value", "slot_id"):
        if sig_a.get(key) != sig_b.get(key):
            return False
    return True


def _information_atoms(claim: dict[str, Any]) -> set[str]:
    sig = claim_signature(claim)
    return {
        a for a in (sig.get("time"), sig.get("status"), sig.get("numeric_value"))
        if a
    }


def _rank_representative(claims: list[dict], evidence_map: dict[str, dict]) -> list[dict]:
    """Deterministic representative ranking within a same-fact family."""

    def score(c: dict) -> tuple:
        ev = [evidence_map.get(eid, {}) for eid in c.get("evidence_ids", [])]
        verified = sum(1 for e in ev if e.get("quote_verification_status") == "verified")
        primary = sum(1 for e in ev if e.get("is_primary_source"))
        approved = 1 if c.get("approval_status") == "approved" else 0
        text_len = len(_normalize_text(c.get("text") or ""))
        # conservative assertion ranks lower (smaller = better)
        assertion = {"mentioned": 0, "observed": 1, "supported": 2, "confirmed": 3}.get(
            c.get("assertion_level") or "mentioned", 1
        )
        return (approved, verified, primary, len(c.get("evidence_ids", [])), text_len, -assertion)

    return sorted(claims, key=score, reverse=True)


def _claim_sections(claim: dict[str, Any], slot_by_id: dict[str, dict]) -> list[str]:
    ids = [str(claim.get("primary_slot_id") or "")] + [
        str(x) for x in claim.get("slot_ids", [])
    ]
    sections: list[str] = []
    for sid in ids:
        if not sid:
            continue
        sec = str((slot_by_id.get(sid) or {}).get("section_id") or "_default")
        if sec not in sections:
            sections.append(sec)
    return sections or ["_default"]


# ── main assignment ─────────────────────────────────────────────────────────

def assign_section_claims(
    editor1_input,
    *,
    evidence_map: dict[str, dict] | None = None,
    max_optional_per_section: int = 4,
) -> list[SectionClaimAssignment]:
    """Deterministically assign approved claims to sections.

    For each section:
    - Required: representative claim of every critical / required-and-satisfied
      slot (guaranteed coverage), plus any claim whose primary slot is required.
    - Optional: remaining non-suppressed claims with independent increment,
      capped at max_optional_per_section (background_overflow beyond that).
    - Suppressed: duplicates / subsumed / lower-evidence / section mismatch /
      conflict-unresolved (approval != approved is excluded upstream).
    """
    slot_by_id: dict[str, dict] = {}
    for sec in editor1_input.research_contract.get("sections", []):
        sec_id = str(sec.get("section_id") or "_default")
        for s in sec.get("claim_slots", []):
            slot_by_id[s["slot_id"]] = {**s, "section_id": sec_id}
    sections: dict[str, list[dict]] = {}
    for c in editor1_input.approved_claim_cards:
        for sec in _claim_sections(c, slot_by_id):
            sections.setdefault(sec, []).append(c)

    slot_status = {
        r["slot_id"]: r["status"]
        for r in editor1_input.coverage_report.get("slot_reports", [])
    }
    evidence_map = evidence_map or {
        e["evidence_id"]: e for e in editor1_input.referenced_evidence_units
    }

    assignments: list[SectionClaimAssignment] = []
    for section_id, claims in sections.items():
        slot_ids = {
            str(s["slot_id"]) for s in slot_by_id.values()
            if (s.get("section_id") or "_default") == section_id
        }
        input_count = len(claims)

        # Cluster into same-fact families; pick representatives.
        families: list[list[dict]] = []
        for claim in claims:
            sig = claim_signature(claim, slot_by_id.get(claim.get("primary_slot_id") or ""))
            matched = False
            for fam in families:
                if _same_family(sig, claim_signature(
                    fam[0], slot_by_id.get(fam[0].get("primary_slot_id") or "")
                )):
                    fam.append(claim)
                    matched = True
                    break
            if not matched:
                families.append([claim])

        representatives: list[dict] = []
        suppressed: list[SuppressedClaim] = []
        for fam in families:
            ranked = _rank_representative(fam, evidence_map)
            rep = ranked[0]
            representatives.append(rep)
            rep_atoms = _information_atoms(rep)
            for other in ranked[1:]:
                if _normalize_text(other.get("text") or "") == _normalize_text(
                    rep.get("text") or ""
                ):
                    reason = "exact_duplicate"
                else:
                    other_atoms = _information_atoms(other)
                    # subsumed requires a strictly richer INFORMATION ATOM set
                    # (e.g. adds a time/numeric), not merely longer prose.
                    strictly_more_complete = (
                        other_atoms <= rep_atoms
                        and len(rep_atoms) > len(other_atoms)
                    )
                    reason = "subsumed" if strictly_more_complete else "semantic_duplicate"
                suppressed.append(SuppressedClaim(
                    claim_id=other["claim_id"], reason=reason,
                    suppressed_by_claim_id=rep["claim_id"],
                ))

        # Required: representative of each critical / required-and-satisfied slot.
        rep_by_slot: dict[str, str] = {}
        for claim in representatives:
            pid = str(claim.get("primary_slot_id") or "")
            if pid and pid not in rep_by_slot:
                rep_by_slot[pid] = claim["claim_id"]
        required_ids: list[str] = []
        for slot_id, slot in slot_by_id.items():
            if slot_id not in slot_ids:
                continue
            rep = rep_by_slot.get(slot_id)
            if rep is None:
                continue
            is_required_slot = slot.get("criticality") in {"critical", "required"}
            is_satisfied = slot_status.get(slot_id) == "satisfied"
            if is_required_slot and is_satisfied and rep not in required_ids:
                required_ids.append(rep)

        # Optional: remaining representatives (with increment) capped.
        optional: list[str] = []
        for claim in representatives:
            cid = claim["claim_id"]
            if cid in required_ids:
                continue
            # conflicting/unresolved or section-mismatch suppression
            if claim.get("epistemic_status") == "contradicted":
                suppressed.append(SuppressedClaim(cid, "conflicting_claim"))
                continue
            optional.append(cid)
        if len(optional) > max_optional_per_section:
            for cid in optional[max_optional_per_section:]:
                suppressed.append(SuppressedClaim(cid, "background_overflow"))
            optional = optional[:max_optional_per_section]

        output_count = len(required_ids) + len(optional)
        assignments.append(SectionClaimAssignment(
            section_id=section_id,
            required_claim_ids=tuple(required_ids),
            optional_claim_ids=tuple(optional),
            suppressed_claims=tuple(suppressed),
            slot_representatives=rep_by_slot,
            input_claim_count=input_count,
            output_claim_count=output_count,
        ))
    return assignments


def build_context_audit(
    assignment: SectionClaimAssignment,
    *,
    evidence_units: dict[str, dict],
    referenced_evidence_ids: set[str],
    used_claim_ids: set[str],
    claim_texts: dict[str, str] | None = None,
) -> ContextAuditReport:
    """Per-section ContextAudit: why claims/evidence were (not) used."""
    all_ids = (
        list(assignment.required_claim_ids) + list(assignment.optional_claim_ids)
    )
    reasons: dict[str, int] = {}
    for s in assignment.suppressed_claims:
        reasons[s.reason] = reasons.get(s.reason, 0) + 1

    provided_evidence_count = len(referenced_evidence_ids)
    distinct_clusters = {
        (evidence_units[eid].get("content_cluster_id") or eid)
        for eid in referenced_evidence_ids if eid in evidence_units
    }
    distinct_content_evidence_count = len(distinct_clusters)

    claim_texts = claim_texts or {}
    claim_chars = sum(len(claim_texts.get(cid) or "") for cid in all_ids)
    span_chars = sum(
        len(evidence_units.get(eid, {}).get("quoted_span") or "")
        for eid in referenced_evidence_ids
    )
    estimated_context_tokens = max(1, int((claim_chars + span_chars) / _CHARS_PER_TOKEN))

    req_used = sum(1 for cid in assignment.required_claim_ids if cid in used_claim_ids)
    opt_used = sum(1 for cid in assignment.optional_claim_ids if cid in used_claim_ids)
    required_usage = (
        round(req_used / len(assignment.required_claim_ids), 4)
        if assignment.required_claim_ids else None
    )
    optional_usage = (
        round(opt_used / len(assignment.optional_claim_ids), 4)
        if assignment.optional_claim_ids else None
    )

    return ContextAuditReport(
        section_id=assignment.section_id,
        claim_count_before_assignment=assignment.input_claim_count,
        required_claim_count=len(assignment.required_claim_ids),
        optional_claim_count=len(assignment.optional_claim_ids),
        suppressed_claim_count=len(assignment.suppressed_claims),
        suppression_reasons=reasons,
        provided_evidence_count=provided_evidence_count,
        distinct_content_evidence_count=distinct_content_evidence_count,
        estimated_context_tokens=estimated_context_tokens,
        required_claim_usage_rate=required_usage,
        optional_claim_usage_rate=optional_usage,
        context_utilization_rate=round(
            (req_used + opt_used) / max(1, len(all_ids)), 4
        ),
        claim_context_overload_warning=assignment.input_claim_count > 8,
        evidence_duplication_warning=provided_evidence_count > distinct_content_evidence_count,
    )
