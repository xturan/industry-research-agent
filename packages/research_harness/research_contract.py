"""Research Contract Compiler (research-contract-refactor Phase A).

Deterministically derives a ResearchContract v1 from the existing semantic plan
(dimension_plan + evidence_requirement_spec) WITHOUT changing the Planner.

The contract is the single source of truth that downstream stages consume:

- claim_slots -> retrieval planner (Phase D) builds search tasks per slot
- claim_slots -> Sufficiency Gate (Phase B) checks critical/required coverage
- slot_id -> ClaimCard (this phase) links claims to slots
- writing_policy -> Editor1/claim_strength_guard constraint levels

This module is pure derivation with no I/O and no LLM: the same plan dict
always produces the same contract, so it is safe to compile on demand from any
node (build_evidence / build_claims / gate) at zero runtime risk.

Priority semantics (review 2026-08-03):

- Slot importance is a property of the RESEARCH QUESTION, not of the evidence
  channel. source_family only describes where evidence is gathered from.
- Therefore `critical` is NEVER derived from source_family. A slot is critical
  ONLY when the plan explicitly marks it via `plan["critical_slots"]` (a list of
  slot_id strings, or {"section_id","source_family"} pairs), or when a task
  template / user requirement declares it.
- The per-dimension primary family maps to `required` by default; context
  families map to `optional`; everything else is `required`.
"""

from __future__ import annotations

from typing import Any

from packages.research_harness import research_taxonomy
from packages.research_harness.plan_semantic import (
    _DEFAULT_MIN_EVIDENCE,
    build_evidence_requirement_spec,
)
from packages.sources.local_source_patterns import canonical_source_family

CONTRACT_VERSION = "research_contract_v1"

# The dimension/family taxonomy lives in research_taxonomy (single source of
# truth). These mirrors keep read sites stable.
# Per dimension_type: the PRIMARY evidence channel for that section. Primary
# family slots default to `required` (NOT critical). Used only for slot_id
# stability and for the "primary_source_required" hint, never for priority.
_DIMENSION_PRIMARY_FAMILY: dict[str, str] = dict(research_taxonomy.DIMENSION_PRIMARY_FAMILY)

# family -> slot purpose suffix. Keeps slot_id human-readable and stable when
# the dimension_plan ordering changes.
_FAMILY_SLOT_PURPOSE: dict[str, str] = dict(research_taxonomy.SOURCE_FAMILY_PURPOSE)

# Supporting-context families never qualify as required, no matter the section.
_CONTEXT_FAMILIES: frozenset[str] = frozenset(research_taxonomy.CONTEXT_FAMILIES)

_CRITICAL = "critical"
_REQUIRED = "required"
_OPTIONAL = "optional"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def _obligation_min_by_family(plan: dict[str, Any]) -> dict[str, int]:
    """Strongest obligation min_evidence per canonical source_family."""
    out: dict[str, int] = {}
    for obl in plan.get("source_obligations") or []:
        if not isinstance(obl, dict):
            continue
        family = canonical_source_family(obl.get("source_family"))
        try:
            mn = int(obl.get("min_required_evidence") or 1)
        except (TypeError, ValueError):
            mn = 1
        out[family] = max(out.get(family, 0), mn)
    return out


def _resolve_field_requirements(
    plan: dict[str, Any],
    dim: dict[str, Any],
    key_fields: list[str],
) -> tuple[dict[str, Any], str]:
    """Resolve per-slot field_requirements (review 2026-08-03).

    Returns (field_requirements, field_validation_mode):
    - Explicit config (plan["field_requirements"][dim_id], plan["field_requirements"]["default"],
      or dim["field_requirements"]) -> "strict" with mandatory_fields + any_of_fields +
      minimum_optional_fields.
    - No config -> legacy fallback: any_of_fields = key_fields, minimum_optional_fields = 1,
      mode "legacy_any_key_field" (at least one key field present).
    """
    dim_id = str(dim.get("dimension_id") or "").strip()
    explicit: Any = None
    plan_fr = plan.get("field_requirements")
    if isinstance(plan_fr, dict):
        explicit = plan_fr.get(dim_id) or plan_fr.get("default")
    if not isinstance(explicit, dict):
        explicit = dim.get("field_requirements")
    if isinstance(explicit, dict) and (
        explicit.get("mandatory_fields") or explicit.get("any_of_fields")
    ):
        mandatory = [str(f) for f in explicit.get("mandatory_fields", []) if str(f).strip()]
        any_of = [str(f) for f in explicit.get("any_of_fields", []) if str(f).strip()]
        try:
            min_opt = int(explicit.get("minimum_optional_fields", 0))
        except (TypeError, ValueError):
            min_opt = 0
        return {
            "mandatory_fields": mandatory,
            "any_of_fields": any_of or list(key_fields),
            "minimum_optional_fields": max(0, min_opt),
        }, "strict"
    return {
        "mandatory_fields": [],
        "any_of_fields": list(key_fields),
        "minimum_optional_fields": 1,
    }, "legacy_any_key_field"


def _build_section(
    *,
    plan: dict[str, Any],
    dim: dict[str, Any],
    spec_entry: dict[str, Any] | None,
    obl_min_by_family: dict[str, int],
    explicit_critical_slot_ids: set[str],
) -> dict[str, Any] | None:
    dim_id = str(dim.get("dimension_id") or "").strip()
    dtype = research_taxonomy.canonicalize_dimension_type(
        str(dim.get("dimension_type") or "").strip()
    )
    if not dim_id or not dtype:
        return None
    title = str(dim.get("expected_section_heading") or dtype or "其他").strip()
    families = _dedupe(
        canonical_source_family(f) for f in (dim.get("source_families") or [])
    )
    primary = _DIMENSION_PRIMARY_FAMILY.get(dtype)
    dim_meta = research_taxonomy.DIMENSIONS.get(dtype, {})
    key_fields = list(
        (spec_entry or {}).get("key_fields")
        or dim_meta.get("key_fields")
        or []
    )
    research_question = str(dim.get("research_question") or "")
    coverage_required = str(dim.get("coverage_required") or "")
    field_requirements, field_validation_mode = _resolve_field_requirements(
        plan, dim, key_fields
    )

    slots: list[dict[str, Any]] = []
    for family in families:
        purpose = _FAMILY_SLOT_PURPOSE.get(family, "evidence")
        slot_id = f"{dim_id}.{family}.{purpose}"
        # Priority is NEVER derived from source_family. A slot is critical only
        # when the plan explicitly declares it (review 2026-08-03).
        if slot_id in explicit_critical_slot_ids:
            required = _CRITICAL
        elif family in _CONTEXT_FAMILIES:
            required = _OPTIONAL
        else:
            required = _REQUIRED
        slots.append(
            {
                "slot_id": slot_id,
                "section_id": dim_id,
                "source_family": family,
                "slot_purpose": purpose,
                "required": required,
                "primary_source_required": family == primary,
                "min_evidence": obl_min_by_family.get(
                    family, _DEFAULT_MIN_EVIDENCE
                ),
                "key_fields": key_fields,
                "field_requirements": dict(field_requirements),
                "field_validation_mode": field_validation_mode,
                "research_question": research_question,
                "coverage_required": coverage_required,
            }
        )

    return {
        "section_id": dim_id,
        "title": title,
        "dimension_type": dtype,
        "research_question": research_question,
        "coverage_required": coverage_required,
        "source_priority": str(dim.get("source_priority") or "mixed").strip(),
        "claim_slots": slots,
        "evidence_requirements": {
            "required_source_families": families,
            "min_evidence": (spec_entry or {}).get(
                "min_evidence", _DEFAULT_MIN_EVIDENCE
            ),
            "key_fields": key_fields,
        },
    }


def _explicit_critical_slot_ids(plan: dict[str, Any]) -> set[str]:
    """Normalize plan['critical_slots'] into a set of slot_id strings.

    Accepts a list of:
    - slot_id strings (e.g. "dim_policy.official_policy.policy_basis"), or
    - {"section_id": ..., "source_family": ...} dicts.
    Invalid entries are skipped (additive, never raises).
    """
    raw = plan.get("critical_slots")
    if not isinstance(raw, list):
        return set()
    out: set[str] = set()
    for entry in raw:
        if isinstance(entry, str):
            out.add(entry)
        elif isinstance(entry, dict) and entry.get("section_id") and entry.get("source_family"):
            section_id = str(entry["section_id"]).strip()
            family = canonical_source_family(entry.get("source_family"))
            purpose = _FAMILY_SLOT_PURPOSE.get(family, "evidence")
            out.add(f"{section_id}.{family}.{purpose}")
    return out


def compile_research_contract(plan: dict[str, Any]) -> dict[str, Any]:
    """Compile a ResearchContract v1 dict from a semantic plan dict.

    Pure and deterministic: the same plan always yields the same contract.
    Empty/invalid plan yields an empty contract (never raises).
    """
    if not isinstance(plan, dict):
        return _empty_contract()

    spec = build_evidence_requirement_spec(plan)
    spec_by_dim_id = {s["dimension_id"]: s for s in spec}
    obl_min_by_family = _obligation_min_by_family(plan)
    explicit_critical_slot_ids = _explicit_critical_slot_ids(plan)

    sections: list[dict[str, Any]] = []
    for dim in plan.get("dimension_plan") or []:
        if not isinstance(dim, dict):
            continue
        section = _build_section(
            plan=plan,
            dim=dim,
            spec_entry=spec_by_dim_id.get(str(dim.get("dimension_id") or "").strip()),
            obl_min_by_family=obl_min_by_family,
            explicit_critical_slot_ids=explicit_critical_slot_ids,
        )
        if section is not None:
            sections.append(section)

    all_slots = [s for sec in sections for s in sec.get("claim_slots", [])]
    critical = sum(1 for s in all_slots if s.get("required") == _CRITICAL)
    required = sum(1 for s in all_slots if s.get("required") == _REQUIRED)
    optional = sum(1 for s in all_slots if s.get("required") == _OPTIONAL)

    contract_warnings: list[dict[str, Any]] = []
    if sections and critical == 0:
        # Review 2026-08-03: critical is only ever explicit. A contract with NO
        # critical slot is a Blueprint-quality warning (Planner convergence must
        # fix it) — we do NOT re-derive critical implicitly.
        contract_warnings.append(
            {
                "code": "NO_CRITICAL_SLOT_DECLARED",
                "message": (
                    "当前研究契约未声明 critical slot，"
                    "Sufficiency Gate 将无法执行 critical 硬门禁"
                ),
                "severity": "warning",
            }
        )

    return {
        "contract_version": CONTRACT_VERSION,
        "normalized_query": str(plan.get("normalized_query") or ""),
        "sections": sections,
        "contract_warnings": contract_warnings,
        "writing_policy": {
            "default_max_assertion_level": 3,
            # Critical slot missing -> report must degrade to evidence_gap_only,
            # never compensated by optional/required weighting.
            "critical_slot_missing_mode": "evidence_gap_only",
            # Global editorial rules apply to EVERY claim/paragraph (not stored
            # per-claim, to avoid prompt duplication). Review 2026-08-03.
            "global_editorial_rules": {
                "new_numeric_fact_requires_evidence": True,
                "new_entity_requires_claim_binding": True,
            },
        },
        "meta": {
            "compiler": CONTRACT_VERSION,
            "source_spec_entries": len(spec),
            "section_count": len(sections),
            "slot_count": len(all_slots),
            "critical_slot_count": critical,
            "required_slot_count": required,
            "optional_slot_count": optional,
        },
    }


def _empty_contract() -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "normalized_query": "",
        "sections": [],
        "contract_warnings": [],
        "writing_policy": {
            "default_max_assertion_level": 3,
            "critical_slot_missing_mode": "evidence_gap_only",
            "global_editorial_rules": {
                "new_numeric_fact_requires_evidence": True,
                "new_entity_requires_claim_binding": True,
            },
        },
        "meta": {
            "compiler": CONTRACT_VERSION,
            "source_spec_entries": 0,
            "section_count": 0,
            "slot_count": 0,
            "critical_slot_count": 0,
            "required_slot_count": 0,
            "optional_slot_count": 0,
        },
    }
