"""Phase C.1 — Claim-Constrained StructuredDraft (shadow).

Goal: constrain Editor1's writing boundary using ClaimCard + CoverageReport +
ResearchGap. This module is a Structured SHADOW — it builds a deterministic
StructuredDraft alongside the existing Markdown report, without replacing the
formal output or blocking anything.

Scope (C.1.1 - C.1.4 only):
- C.1.1 StructuredDraft schema (frozen dataclasses).
- C.1.2 Editor1Input compiler: ONLY `approved` ClaimCards enter; Evidence is
  trimmed to what approved claims reference.
- C.1.3 Structured Shadow Editor1: section-by-section deterministic assembly.
- C.1.4 Deterministic Draft Validator.

Not in scope (deferred): replacing formal Markdown, Editor2 rewrite, Verifier
deletion, Gate blocking, gap-expression auto-approval, backfill evidence
entering formal Editor1, LLM repair loops.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from packages.research_harness.eval_persistence import RunEvaluationStore

AssertionLevel = Literal["mentioned", "observed", "supported", "confirmed"]
SectionReadiness = Literal["ready", "partial", "blocked", "unknown"]
ParagraphRole = Literal["factual", "gap_descriptive", "transition", "synthesis"]

ASSERTION_LEVELS: tuple[str, ...] = ("mentioned", "observed", "supported", "confirmed")
ASSERTION_RANK: dict[str, int] = {level: i for i, level in enumerate(ASSERTION_LEVELS)}

# Section readiness -> the strongest assertion a paragraph may carry.
READINESS_MAX_ASSERTION: dict[str, str] = {
    "ready": "confirmed",
    "partial": "supported",
    "blocked": "observed",
    "unknown": "observed",
}
# Section readiness -> allowed paragraph roles.
READINESS_ALLOWED_ROLES: dict[str, set[str]] = {
    "ready": {"factual", "transition"},
    "partial": {"factual", "transition"},
    "blocked": {"gap_descriptive"},
    "unknown": {"gap_descriptive"},
}

DEFAULT_WRITING_POLICY: dict[str, Any] = {
    "assertion_levels": list(ASSERTION_LEVELS),
    "gap_unapproved_fallback_text": "现有证据不足以确认该项信息。",
}

# Gap-unapproved negative assertions that must NEVER be auto-produced.
_GAP_NEGATIVE_PHRASES = (
    "尚未形成",
    "没有发生",
    "没有形成",
    "不存在",
    "并未",
    "未发生",
    "没有项目",
    "没有收入",
    "没有政策",
)


# ── C.1.1 Schema (frozen dataclasses) ───────────────────────────────────────

@dataclass(frozen=True)
class DraftParagraph:
    paragraph_id: str
    text: str
    claim_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    assertion_level: AssertionLevel = "mentioned"
    limitations: tuple[str, ...] = ()
    paragraph_role: ParagraphRole = "factual"
    # Optional explicit numeric mentions; validated against claim/evidence spans.
    numeric_mentions: tuple[str, ...] = ()
    # C.3.3 constrained synthesis: id of the SynthesisContract this paragraph
    # expresses (empty for plain factual / gap paragraphs).
    synthesis_id: str = ""


@dataclass(frozen=True)
class DraftSection:
    section_id: str
    title: str
    readiness_at_write: SectionReadiness = "unknown"
    paragraphs: tuple[DraftParagraph, ...] = ()


@dataclass(frozen=True)
class StructuredDraft:
    draft_id: str
    run_id: str
    draft_version: int
    report_title: str
    sections: tuple[DraftSection, ...] = ()
    unused_claim_ids: tuple[str, ...] = ()
    unresolved_gap_ids: tuple[str, ...] = ()
    schema_version: str = "structured_draft_v1"


@dataclass(frozen=True)
class SectionConstraint:
    section_id: str
    readiness: SectionReadiness = "unknown"
    slot_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Editor1Input:
    research_contract: dict[str, Any]
    approved_claim_cards: tuple[dict[str, Any], ...]
    referenced_evidence_units: tuple[dict[str, Any], ...]
    coverage_report: dict[str, Any]
    section_constraints: tuple[SectionConstraint, ...]
    unresolved_research_gaps: tuple[dict[str, Any], ...]
    writing_policy: dict[str, Any]


@dataclass(frozen=True)
class DraftValidationIssue:
    code: str
    severity: Literal["error", "warning"]
    message: str
    section_id: str = ""
    paragraph_id: str = ""
    target_id: str = ""


@dataclass(frozen=True)
class DraftValidationReport:
    draft_id: str
    passed: bool
    issues: tuple[DraftValidationIssue, ...]
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft_id": self.draft_id,
            "passed": self.passed,
            "issues": [i.__dict__ for i in self.issues],
            "metrics": self.metrics,
        }


# ── helpers ─────────────────────────────────────────────────────────────────

def _contract_sections(contract: dict[str, Any]) -> list[dict[str, Any]]:
    sections = contract.get("sections")
    if isinstance(sections, list):
        return [s for s in sections if isinstance(s, dict)]
    # fallback: single synthetic section
    return [{"section_id": "_default", "title": "报告", "claim_slots": []}]


def _section_readiness(slots_with_reports: Sequence[tuple[dict, dict]]) -> SectionReadiness:
    if not slots_with_reports:
        return "unknown"
    statuses = [r["status"] for _, r in slots_with_reports]
    if any(s == "not_evaluable" for s in statuses):
        return "unknown"
    unsatisfied = [slot for slot, r in slots_with_reports if r["status"] == "unsatisfied"]
    if unsatisfied and any(slot.get("criticality") == "critical" for slot in unsatisfied):
        return "blocked"
    if unsatisfied:
        return "partial"
    return "ready"


def _cap_assertion(level: str, *caps: str | None) -> AssertionLevel:
    rank = ASSERTION_RANK
    ranks = [rank.get(level, 0)]
    for cap in caps:
        if cap and cap in rank:
            ranks.append(rank[cap])
    return ASSERTION_LEVELS[min(ranks)]  # type: ignore[return-value]


def _claim_section(claim: dict[str, Any], constraints: dict[str, SectionConstraint],
                   claim_slots: dict[str, dict]) -> str:
    primary = str(claim.get("primary_slot_id") or "")
    for cid, constraint in constraints.items():
        if primary in constraint.slot_ids:
            return cid
    # fallback: slot's own section_id
    if primary and primary in claim_slots:
        return str(claim_slots[primary].get("section_id") or "_default")
    return "_default"


def _factual_paragraph(
    claim: dict[str, Any], *, paragraph_id: str, max_assertion: str,
) -> DraftParagraph:
    claim_assertion = str(claim.get("assertion_level") or "mentioned")
    max_allowed = str(claim.get("max_allowed_assertion_level") or "mentioned")
    capped = _cap_assertion(claim_assertion, max_allowed, max_assertion)
    text = str(claim.get("text") or "").strip()
    if not text:
        text = f"公开资料显示，{claim.get('claim_id')} 相关事项见已核验材料。"
    return DraftParagraph(
        paragraph_id=paragraph_id,
        text=text,
        claim_ids=(str(claim["claim_id"]),),
        evidence_ids=tuple(str(eid) for eid in claim.get("evidence_ids", []) if eid),
        assertion_level=capped,
        limitations=tuple(claim.get("limitations") or []),
        paragraph_role="factual",
    )


def _gap_paragraph(section_id: str, *, paragraph_id: str, gaps: Sequence[dict]) -> DraftParagraph:
    return DraftParagraph(
        paragraph_id=paragraph_id,
        text=DEFAULT_WRITING_POLICY["gap_unapproved_fallback_text"],
        claim_ids=(),
        evidence_ids=(),
        assertion_level="observed",
        paragraph_role="gap_descriptive",
    )


# ── stable IDs (checkpoint-idempotent, no uuid4 randomness) ─────────────────

def _coverage_snapshot_id(coverage_report: dict[str, Any]) -> str:
    return str(
        coverage_report.get("coverage_report_id")
        or coverage_report.get("coverage_snapshot_id")
        or "cr"
    )


def stable_draft_id(
    *,
    run_id: str,
    draft_version: int,
    claim_ids: Sequence[str],
    coverage_snapshot_id: str,
) -> str:
    import hashlib

    payload = "|".join([
        run_id or "", str(draft_version),
        ",".join(sorted(claim_ids)),
        coverage_snapshot_id,
    ])
    return f"sd:{hashlib.md5(payload.encode('utf-8')).hexdigest()[:12]}"


def stable_paragraph_id(*, draft_id: str, section_id: str, index: int) -> str:
    import hashlib

    payload = f"{draft_id}|{section_id}|{index}"
    return f"p:{hashlib.md5(payload.encode('utf-8')).hexdigest()[:12]}"


# ── C.1.2 Editor1Input Compiler ─────────────────────────────────────────────

def _build_section_constraints(
    store: RunEvaluationStore, coverage_report: dict[str, Any],
) -> tuple[SectionConstraint, ...]:
    slot_reports = {r["slot_id"]: r for r in coverage_report.get("slot_reports", [])}
    grouped: dict[str, dict[str, Any]] = {}
    for slot in store.claim_slots.values():
        sid = str(slot.get("section_id") or "_default")
        entry = grouped.setdefault(sid, {"section_id": sid, "slot_ids": [], "reports": []})
        entry["slot_ids"].append(slot["slot_id"])
        if slot["slot_id"] in slot_reports:
            entry["reports"].append((slot, slot_reports[slot["slot_id"]]))
    constraints = []
    for sid, entry in grouped.items():
        constraints.append(SectionConstraint(
            section_id=sid,
            readiness=_section_readiness(entry["reports"]),
            slot_ids=tuple(entry["slot_ids"]),
        ))
    return tuple(constraints)


# ── assertion vocabulary normalization ──────────────────────────────────────

# Phase A ClaimCards persist assertion levels in their own vocabulary
# (assertion_level_label + numeric max_assertion_level 1..4). C.1/C.3 use the
# 4-level enum [mentioned, observed, supported, confirmed]. This adapter maps
# the persisted vocabulary into the C.1 enum so the validator is consistent.
_ASSERTION_NORMALIZE: dict[str, str] = {
    "mention_only": "mentioned",
    "mention": "mentioned",
    "observed": "observed",
    "supported": "supported",
    "pattern_supported": "supported",
    "confirmed": "confirmed",
    "fact_confirmed": "confirmed",
    "strong_conclusion": "confirmed",
    "1": "mentioned",
    "2": "observed",
    "3": "supported",
    "4": "confirmed",
}


def normalize_assertion_level(value: Any) -> str:
    key = str(value or "").strip().lower()
    return _ASSERTION_NORMALIZE.get(key, "mentioned")


def normalize_claim_assertion(claim: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized copy of a claim card with C.1-enum assertion fields."""
    normalized = dict(claim)
    normalized["assertion_level"] = normalize_assertion_level(
        claim.get("assertion_level") or claim.get("assertion_level_label")
    )
    normalized["max_allowed_assertion_level"] = normalize_assertion_level(
        claim.get("max_allowed_assertion_level") or claim.get("max_assertion_level")
    )
    return normalized


def compile_editor1_input(
    *,
    store: RunEvaluationStore,
    coverage_report: dict[str, Any],
    research_gaps: Sequence[Any],
    contract: dict[str, Any] | None = None,
    writing_policy: dict[str, Any] | None = None,
) -> Editor1Input:
    """Build the constrained Editor1 input (shadow).

    Filtering rules:
    - ONLY `approval_status == "approved"` ClaimCards enter.
    - Evidence is trimmed to what approved claims actually reference
      (ClaimCard.evidence_ids -> referenced EvidenceUnit).
    """
    approved = [
        normalize_claim_assertion(c)
        for c in store.claim_cards.values()
        if c.get("approval_status") == "approved"
    ]
    referenced_evidence_ids = {
        eid for c in approved for eid in c.get("evidence_ids", []) if eid
    }
    referenced_evidence = [
        e for eid, e in store.evidence_units.items() if eid in referenced_evidence_ids
    ]

    if contract is None:
        contract = {"sections": _contract_sections_from_store(store)}

    return Editor1Input(
        research_contract=contract,
        approved_claim_cards=tuple(approved),
        referenced_evidence_units=tuple(referenced_evidence),
        coverage_report=coverage_report,
        section_constraints=_build_section_constraints(store, coverage_report),
        unresolved_research_gaps=tuple(_gap_asdict(g) for g in research_gaps),
        writing_policy=writing_policy or DEFAULT_WRITING_POLICY,
    )


def _contract_sections_from_store(store: RunEvaluationStore) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for slot in store.claim_slots.values():
        sid = str(slot.get("section_id") or "_default")
        entry = grouped.setdefault(sid, {"section_id": sid, "title": sid, "claim_slots": []})
        entry["claim_slots"].append(slot)
    return list(grouped.values())


def _gap_asdict(gap: Any) -> dict[str, Any]:
    if hasattr(gap, "__dict__"):
        return dict(gap.__dict__)
    return dict(gap)


# ── C.1.3 Structured Shadow Editor1 (deterministic, section-by-section) ─────

def build_structured_shadow_draft(
    editor1_input: Editor1Input,
    *,
    run_id: str = "",
    draft_id: str | None = None,
    draft_version: int = 1,
) -> StructuredDraft:
    """Deterministic section-by-section shadow draft.

    For each contract section:
    - blocked/unknown -> only a gap_descriptive paragraph (no strong conclusion).
    - ready/partial  -> one factual paragraph per approved claim, capped by both
      the claim's max_allowed_assertion_level and the section readiness.
    """
    sections = _contract_sections(editor1_input.research_contract)
    constraints = {c.section_id: c for c in editor1_input.section_constraints}
    claim_slots = {}  # compiler carries contract; fall back to approved claim slots

    # Group approved claims by section.
    section_claims: dict[str, list[dict]] = {}
    for claim in editor1_input.approved_claim_cards:
        sid = _claim_section(claim, constraints, claim_slots)
        section_claims.setdefault(sid, []).append(claim)

    # Stable, content-derived draft_id (no uuid4 randomness) for checkpoint
    # idempotency and OFF/ON comparability.
    approved_claim_ids = [str(c["claim_id"]) for c in editor1_input.approved_claim_cards]
    coverage_snapshot_id = _coverage_snapshot_id(editor1_input.coverage_report)
    resolved_draft_id = draft_id or stable_draft_id(
        run_id=run_id,
        draft_version=draft_version,
        claim_ids=approved_claim_ids,
        coverage_snapshot_id=coverage_snapshot_id,
    )

    out_sections: list[DraftSection] = []
    used_claim_ids: set[str] = set()
    for sec in sections:
        sid = str(sec.get("section_id") or "_default")
        title = str(sec.get("title") or sid)
        constraint = constraints.get(sid, SectionConstraint(section_id=sid))
        readiness = constraint.readiness
        claims = section_claims.get(sid, [])
        allowed_roles = READINESS_ALLOWED_ROLES.get(readiness, {"gap_descriptive"})
        max_assertion = READINESS_MAX_ASSERTION.get(readiness, "observed")

        paragraphs: list[DraftParagraph] = []
        if "factual" not in allowed_roles:
            # blocked/unknown: describe evidence gap only.
            paragraphs.append(_gap_paragraph(
                sid, paragraph_id=stable_paragraph_id(
                    draft_id=resolved_draft_id, section_id=sid, index=0),
                gaps=editor1_input.unresolved_research_gaps,
            ))
        else:
            for idx, claim in enumerate(claims):
                paragraphs.append(_factual_paragraph(
                    claim,
                    paragraph_id=stable_paragraph_id(
                        draft_id=resolved_draft_id, section_id=sid, index=idx),
                    max_assertion=max_assertion,
                ))
                used_claim_ids.add(str(claim["claim_id"]))

        out_sections.append(DraftSection(
            section_id=sid, title=title,
            readiness_at_write=readiness,
            paragraphs=tuple(paragraphs),
        ))

    unused = tuple(
        str(c["claim_id"]) for c in editor1_input.approved_claim_cards
        if str(c["claim_id"]) not in used_claim_ids
    )
    unresolved_gap_ids = tuple(
        str(g.get("gap_id") or g.get("gap_key") or "")
        for g in editor1_input.unresolved_research_gaps if g
    )
    return StructuredDraft(
        draft_id=resolved_draft_id,
        run_id=run_id,
        draft_version=draft_version,
        report_title=str(editor1_input.research_contract.get("report_title") or ""),
        sections=tuple(out_sections),
        unused_claim_ids=unused,
        unresolved_gap_ids=unresolved_gap_ids,
    )


# ── C.1.4 Deterministic Draft Validator ─────────────────────────────────────

def _is_gap_negative_assertion(text: str) -> bool:
    lowered = (text or "").lower()
    return any(phrase in lowered for phrase in _GAP_NEGATIVE_PHRASES)


def validate_structured_draft(
    draft: StructuredDraft,
    *,
    claim_cards: dict[str, dict[str, Any]],
    evidence_units: dict[str, dict[str, Any]],
    coverage_report: dict[str, Any],
) -> DraftValidationReport:
    """Deterministic validation of a StructuredDraft."""
    # Normalize claim assertion vocabulary (Phase A numeric/label -> C.1 enum) so
    # persisted claim cards validate consistently regardless of caller.
    claim_cards = {
        cid: normalize_claim_assertion(card) for cid, card in claim_cards.items()
    }
    issues: list[DraftValidationIssue] = []

    for section in draft.sections:
        for paragraph in section.paragraphs:
            pid = paragraph.paragraph_id
            if paragraph.paragraph_role in {"factual", "synthesis"}:
                if not paragraph.claim_ids:
                    issues.append(DraftValidationIssue(
                        f"{paragraph.paragraph_role}_paragraph_missing_claim", "error",
                        f"{paragraph.paragraph_role} paragraph has no claim_ids",
                        section.section_id, pid))
                if not paragraph.evidence_ids:
                    issues.append(DraftValidationIssue(
                        "factual_paragraph_missing_evidence", "error",
                        "factual paragraph has no evidence_ids", section.section_id, pid))

            # Paragraph claims: validate membership/approval, then check evidence
            # against the UNION of the paragraph's claims' evidence (multi-claim
            # synthesis is allowed; each claim contributes its own evidence).
            paragraph_cards: list[dict] = []
            for cid in paragraph.claim_ids:
                card = claim_cards.get(cid)
                if card is None:
                    issues.append(DraftValidationIssue(
                        "unknown_claim_id", "error",
                        f"claim {cid} does not exist", section.section_id, pid, cid))
                    continue
                if card.get("approval_status") != "approved":
                    issues.append(DraftValidationIssue(
                        "claim_not_approved", "error",
                        f"claim {cid} is {card.get('approval_status')}, not approved",
                        section.section_id, pid, cid))
                paragraph_cards.append(card)

            union_evidence = {
                eid for card in paragraph_cards for eid in (card.get("evidence_ids") or [])
            }
            for eid in paragraph.evidence_ids:
                if eid not in evidence_units:
                    issues.append(DraftValidationIssue(
                        "unknown_evidence_id", "error",
                        f"evidence {eid} does not exist", section.section_id, pid, eid))
                elif eid not in union_evidence:
                    issues.append(DraftValidationIssue(
                        "evidence_not_referenced_by_claim", "error",
                        f"evidence {eid} not referenced by any paragraph claim",
                        section.section_id, pid, eid))

            for card in paragraph_cards:
                cid = card["claim_id"]
                max_allowed = str(card.get("max_allowed_assertion_level") or "mentioned")
                if ASSERTION_RANK.get(paragraph.assertion_level, 0) > ASSERTION_RANK.get(
                    max_allowed, 0
                ):
                    issues.append(DraftValidationIssue(
                        "assertion_level_exceeded", "error",
                        f"paragraph {paragraph.assertion_level} exceeds claim max {max_allowed}",
                        section.section_id, pid, cid))

                claim_limitations = set(card.get("limitations") or [])
                if claim_limitations and not claim_limitations.issubset(
                    set(paragraph.limitations)
                ):
                    issues.append(DraftValidationIssue(
                        "limitation_not_preserved", "error",
                        f"claim {cid} limitations dropped", section.section_id, pid, cid))

            # Section readiness: blocked/unknown must not carry a strong conclusion.
            if section.readiness_at_write in {"blocked", "unknown"}:
                if paragraph.paragraph_role == "factual" or (
                    ASSERTION_RANK.get(paragraph.assertion_level, 0)
                    >= ASSERTION_RANK.get("supported", 0)
                ):
                    issues.append(DraftValidationIssue(
                        "blocked_unknown_strong_conclusion", "error",
                        f"section {section.readiness_at_write} produced a strong conclusion",
                        section.section_id, pid))

            # Gap-unapproved negative assertions are forbidden.
            if paragraph.paragraph_role == "gap_descriptive" and _is_gap_negative_assertion(
                paragraph.text
            ):
                issues.append(DraftValidationIssue(
                    "gap_unapproved_negative_assertion", "error",
                    "gap paragraph auto-asserts a negative ('not happened') conclusion",
                    section.section_id, pid))

    metrics = {
        "section_count": len(draft.sections),
        "paragraph_count": sum(len(s.paragraphs) for s in draft.sections),
        "factual_paragraph_count": sum(
            1 for s in draft.sections for p in s.paragraphs if p.paragraph_role == "factual"
        ),
        "issue_count": len(issues),
        "error_count": sum(1 for i in issues if i.severity == "error"),
    }
    return DraftValidationReport(
        draft_id=draft.draft_id,
        passed=metrics["error_count"] == 0,
        issues=tuple(issues),
        metrics=metrics,
    )


# ── convenience: full shadow pipeline over a store ──────────────────────────

def run_structured_shadow(
    *,
    store: RunEvaluationStore,
    coverage_report: dict[str, Any],
    research_gaps: Sequence[Any],
    contract: dict[str, Any] | None = None,
    run_id: str = "",
) -> dict[str, Any]:
    """Compile -> shadow draft -> validate (single call, deterministic)."""
    editor_input = compile_editor1_input(
        store=store, coverage_report=coverage_report,
        research_gaps=research_gaps, contract=contract,
    )
    draft = build_structured_shadow_draft(editor_input, run_id=run_id)
    report = validate_structured_draft(
        draft,
        claim_cards=store.claim_cards,
        evidence_units=store.evidence_units,
        coverage_report=coverage_report,
    )
    return {
        "editor1_input": editor_input_to_dict(editor_input),
        "draft": draft_to_dict(draft),
        "validation": report.to_dict(),
    }


def editor_input_to_dict(editor1_input: Editor1Input) -> dict[str, Any]:
    return {
        "approved_claim_count": len(editor1_input.approved_claim_cards),
        "approved_claim_ids": [str(c["claim_id"]) for c in editor1_input.approved_claim_cards],
        "referenced_evidence_count": len(editor1_input.referenced_evidence_units),
        "referenced_evidence_ids": [
            str(e["evidence_id"]) for e in editor1_input.referenced_evidence_units
        ],
        "section_constraints": [c.__dict__ for c in editor1_input.section_constraints],
        "unresolved_gap_count": len(editor1_input.unresolved_research_gaps),
    }


def input_fingerprint(editor1_input: Editor1Input) -> str:
    """Stable, content-derived hash of the constrained Editor1 input.

    Used for OFF/ON comparability and checkpoint idempotency.
    """
    import hashlib

    claim_ids = sorted(str(c["claim_id"]) for c in editor1_input.approved_claim_cards)
    evidence_ids = sorted(
        str(e["evidence_id"]) for e in editor1_input.referenced_evidence_units
    )
    readiness = sorted(
        f"{c.section_id}:{c.readiness}" for c in editor1_input.section_constraints
    )
    payload = "|".join([
        ",".join(claim_ids),
        ",".join(evidence_ids),
        ",".join(readiness),
        _coverage_snapshot_id(editor1_input.coverage_report),
    ])
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:16]


def draft_to_dict(draft: StructuredDraft) -> dict[str, Any]:
    return {
        "draft_id": draft.draft_id,
        "run_id": draft.run_id,
        "draft_version": draft.draft_version,
        "report_title": draft.report_title,
        "schema_version": draft.schema_version,
        "sections": [
            {
                "section_id": s.section_id,
                "title": s.title,
                "readiness_at_write": s.readiness_at_write,
                "paragraphs": [p.__dict__ for p in s.paragraphs],
            }
            for s in draft.sections
        ],
        "unused_claim_ids": list(draft.unused_claim_ids),
        "unresolved_gap_ids": list(draft.unresolved_gap_ids),
    }
