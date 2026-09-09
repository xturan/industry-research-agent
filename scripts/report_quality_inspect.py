"""Report quality inspection harness — Phase 1 baseline tool.

Reads graph-v1 smoke artifacts (response.json + summary.json) and emits
product-quality metrics. Classifies output as:
  - workflow_pass_product_pass: workflow succeeded AND product quality meets thresholds
  - workflow_pass_product_fail: workflow succeeded BUT product quality is insufficient
  - workflow_fail: workflow did not succeed

Usage:
    python scripts/report_quality_inspect.py \
        --response data/tmp/final_fix_smoke/case1/response.json \
        --summary data/tmp/final_fix_smoke/case1/summary.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field

# ── Thresholds (from PRD) ──

REQUIRED_SECTIONS = {
    "executive_summary": ["执行摘要", "executive summary", "Executive Summary"],
    "method_scope": ["方法与口径", "方法", "口径", "Method", "Scope"],
    "policy_basis": ["政策", "Policy"],
    "disclosure": ["披露", "Disclosure"],
    "uncertainty_risk": ["不确定性", "风险", "Uncertainty", "Risk"],
    "conclusion_next": ["结论", "建议", "后续", "Conclusion", "Next"],
}

MIN_BUSINESS_BODY_CHARS = 1500
MIN_BUSINESS_BODY_RATIO = 0.35
MAX_OBLIGATION_GAPS = 0
MAX_SOURCE_FAMILY_MISMATCH = 0
MAX_P0_ISSUES = 0
MAX_LIMITATIONS_TRUNCATED = 3
MAX_OVER_BUDGET_PACKS = 5

AUDIT_APPENDIX_MARKERS = [
    "Audit Appendix", "审计附录", "## Audit",
    "Claim Verifications", "key_claims", "Evidence And Limitations",
]


@dataclass(slots=True)
class InspectResult:
    file_paths: dict[str, str] = field(default_factory=dict)
    workflow: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, float | int | str] = field(default_factory=dict)
    checks: list[dict[str, str | bool]] = field(default_factory=list)
    overall: str = "unknown"


def _recover_draft_markdown(node_steps: list) -> str:
    """Recover the latest report draft when the run halts before finalize.

    On HUMAN_REVIEW / REVIEW_RISK the flow stops at human_review and never
    populates report_preview.report_markdown, yet a full editor1 LLM draft
    exists in the node outputs. Walk the latest report-bearing nodes
    (human_review first, then editor1_draft) and return the longest
    report_markdown found so the inspector evaluates the real draft instead of
    an empty string.
    """
    def _deepest_markdown(obj: object) -> str:
        best = ""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "report_markdown" and isinstance(value, str) and len(value) > len(best):
                    best = value
                nested = _deepest_markdown(value)
                if len(nested) > len(best):
                    best = nested
        elif isinstance(obj, list):
            for value in obj:
                nested = _deepest_markdown(value)
                if len(nested) > len(best):
                    best = nested
        return best

    for target in ("human_review", "editor1_draft"):
        for step in reversed(node_steps):
            if isinstance(step, dict) and step.get("node_name") == target:
                md = _deepest_markdown(step.get("output_summary") or {})
                if md:
                    return md
    return ""


def inspect(response_path: str, summary_path: str) -> InspectResult:
    response = _load_json(response_path)
    summary = _load_json(summary_path)

    result = InspectResult(
        file_paths={"response": str(response_path), "summary": str(summary_path)},
    )

    # ── Workflow status ──
    result.workflow["status"] = str(response.get("status", "unknown"))
    result.workflow["decision"] = str(response.get("decision", "unknown"))

    rp = response.get("report_preview") or {}
    rm = str(rp.get("report_markdown", ""))
    node_steps = response.get("node_steps") or []
    node_summaries = _index_node_summaries(node_steps)
    tcr = rp.get("tool_composed_report") or {}

    # Fallback: when the run halts before finalize (HUMAN_REVIEW / REVIEW_RISK),
    # report_preview.report_markdown is empty but a full editor1 LLM draft exists
    # in the node outputs. Recover it so quality reflects the real draft.
    report_from_draft = False
    if not rm.strip():
        recovered = _recover_draft_markdown(node_steps)
        if recovered.strip():
            rm = recovered
            report_from_draft = True
    result.workflow["report_source"] = "draft_fallback" if report_from_draft else "report_preview"

    # ── Metrics ──
    result.metrics["report_markdown_chars"] = len(rm)

    # Claim / evidence / source counts: read the real graph-v1 fields.
    # Extraction order (truth-first):
    #   1. report_preview top-level integer counters (canonical)
    #   2. tool_composed_report claim_briefs list length + evidence_count
    #   3. node_steps output_summary counters (collect_sources / build_evidence / build_claims)
    result.metrics["claim_count"] = _extract_count(
        rp.get("claim_count"),
        len(tcr.get("claim_briefs") or []) if isinstance(tcr.get("claim_briefs"), list) else None,
        _node_count(node_summaries, "build_claims", "claim_count"),
    )
    result.metrics["evidence_count"] = _extract_count(
        rp.get("evidence_count"),
        tcr.get("evidence_count") if isinstance(tcr.get("evidence_count"), int) else None,
        _node_count(node_summaries, "build_evidence", "evidence_count"),
    )
    result.metrics["source_count"] = _extract_count(
        rp.get("source_count"),
        _node_count(node_summaries, "collect_sources", "source_count"),
        _node_count(node_summaries, "score_sources", "source_count"),
    )
    result.metrics["gate_obligation_gap_count"] = summary.get("gate_obligation_gap_count", 0)
    result.metrics["gate_local_precision"] = summary.get("gate_local_precision", 0)
    result.metrics["over_budget_context_packs"] = len(
        summary.get("over_budget_context_packs", [])
    )

    # Audit appendix detection
    audit_idx = len(rm)
    for marker in AUDIT_APPENDIX_MARKERS:
        idx = rm.find(marker)
        if idx >= 0 and idx < audit_idx:
            audit_idx = idx
    business_body = rm[:audit_idx] if audit_idx < len(rm) else rm
    result.metrics["business_body_chars"] = len(business_body.strip())
    result.metrics["audit_appendix_start_index"] = audit_idx if audit_idx < len(rm) else -1
    result.metrics["business_body_ratio"] = round(
        len(business_body.strip()) / max(len(rm), 1), 3
    )

    # ── Checks ──
    checks: list[dict[str, str | bool]] = []

    # 1. Business body length
    body_ok = len(business_body.strip()) >= MIN_BUSINESS_BODY_CHARS
    checks.append({
        "check": "business_body_length",
        "value": str(len(business_body.strip())),
        "threshold": f">={MIN_BUSINESS_BODY_CHARS}",
        "passed": body_ok,
    })

    # 2. Business body ratio
    ratio_ok = result.metrics["business_body_ratio"] >= MIN_BUSINESS_BODY_RATIO
    checks.append({
        "check": "business_body_ratio",
        "value": str(result.metrics["business_body_ratio"]),
        "threshold": f">={MIN_BUSINESS_BODY_RATIO}",
        "passed": ratio_ok,
    })

    # 3. Required section coverage
    sections_found, sections_missing = _check_sections(rm)
    result.metrics["sections_found"] = sections_found
    result.metrics["sections_missing"] = ",".join(sections_missing) if sections_missing else ""
    checks.append({
        "check": "required_sections",
        "value": f"found={len(sections_found)} missing={len(sections_missing)}",
        "threshold": f"missing<={2}",
        "passed": len(sections_missing) <= 2,
        "detail": f"missing: {', '.join(sections_missing)}" if sections_missing else "",
    })

    # 4. Obligation gap
    gaps = summary.get("gate_obligation_gap_count", 0)
    gaps_ok = gaps <= MAX_OBLIGATION_GAPS
    checks.append({
        "check": "obligation_gaps",
        "value": str(gaps),
        "threshold": f"<={MAX_OBLIGATION_GAPS}",
        "passed": gaps_ok,
    })

    # 5. Obligation detail
    obligation_coverage = list(summary.get("required_obligation_coverage", []))
    uncovered = [o for o in obligation_coverage if isinstance(o, dict) and not o.get("covered")]
    result.metrics["obligations_uncovered"] = ",".join(
        str(o.get("obligation_id", "?")) for o in uncovered
    )
    result.metrics["obligations_covered_count"] = sum(
        1 for o in obligation_coverage if isinstance(o, dict) and o.get("covered")
    )
    result.metrics["obligations_total_count"] = len(obligation_coverage)
    checks.append({
        "check": "obligation_coverage_detail",
        "value": (
            f"{result.metrics['obligations_covered_count']}"
            f"/{result.metrics['obligations_total_count']}"
        ),
        "threshold": "all covered",
        "passed": len(uncovered) == 0,
        "detail": f"uncovered: {result.metrics['obligations_uncovered']}" if uncovered else "",
    })

    # 6. Source-family mismatch detection
    mismatch_count = _count_source_family_mismatches(rp)
    result.metrics["source_family_mismatch_count"] = mismatch_count
    checks.append({
        "check": "source_family_mismatch",
        "value": str(mismatch_count),
        "threshold": f"<={MAX_SOURCE_FAMILY_MISMATCH}",
        "passed": mismatch_count <= MAX_SOURCE_FAMILY_MISMATCH,
    })

    # 7. P0 review issues
    p0_count = _count_p0_review_issues(rp, rm)
    result.metrics["p0_review_issue_count"] = p0_count
    checks.append({
        "check": "p0_issues",
        "value": str(p0_count),
        "threshold": f"<={MAX_P0_ISSUES}",
        "passed": p0_count <= MAX_P0_ISSUES,
    })

    # 8. Limitations truncation
    truncated = _count_truncated_limitations(rp, rm)
    result.metrics["limitations_truncated"] = truncated
    checks.append({
        "check": "limitations_truncated",
        "value": str(truncated),
        "threshold": f"<={MAX_LIMITATIONS_TRUNCATED}",
        "passed": truncated <= MAX_LIMITATIONS_TRUNCATED,
    })

    # 9. Over-budget context packs (ADVISORY, non-blocking)
    # token_estimate counts each source's full clean_text/raw_text + all
    # source_chunks — content that is NOT injected into the LLM prompt (nodes
    # send a curated digest). A deep report legitimately processes many sources,
    # so this is an operational/cost signal, not a report-quality defect. It is
    # reported but does not gate product_pass.
    over_budget = result.metrics["over_budget_context_packs"]
    checks.append({
        "check": "over_budget_packs",
        "value": str(over_budget),
        "threshold": f"<={MAX_OVER_BUDGET_PACKS}",
        "passed": over_budget <= MAX_OVER_BUDGET_PACKS,
        "advisory": True,
    })

    result.checks = checks

    # ── Overall classification ──
    # Only blocking (non-advisory) checks gate product_pass. Advisory checks are
    # operational/cost signals surfaced for visibility, not quality defects.
    workflow_ok = result.workflow["status"] == "succeeded"
    blocking_checks = [c for c in checks if not c.get("advisory")]
    product_ok = all(c["passed"] for c in blocking_checks)

    if not workflow_ok:
        result.overall = "workflow_fail"
    elif product_ok:
        result.overall = "workflow_pass_product_pass"
    else:
        result.overall = "workflow_pass_product_fail"

    return result


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _extract_count(*candidates) -> int:
    """Return the first non-negative int candidate, else 0.

    Used to read claim/evidence/source counts across the canonical
    report_preview counters, tool_composed_report, and node-step fallbacks.
    """
    for cand in candidates:
        if isinstance(cand, bool):
            continue
        if isinstance(cand, int) and cand >= 0:
            return cand
    return 0


def _index_node_summaries(node_steps: list) -> dict[str, dict]:
    """Map node_name -> output_summary for node-step fallback extraction."""
    indexed: dict[str, dict] = {}
    for step in node_steps:
        if not isinstance(step, dict):
            continue
        name = step.get("node_name") or step.get("node")
        if not name:
            continue
        summary = step.get("output_summary")
        if isinstance(summary, dict):
            indexed.setdefault(str(name), summary)
    return indexed


def _node_count(node_summaries: dict, node_name: str, field: str) -> int | None:
    """Read an integer counter from a node's output_summary, or None."""
    summary = node_summaries.get(node_name) or {}
    value = summary.get(field)
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _check_sections(markdown: str) -> tuple[list[str], list[str]]:
    found: list[str] = []
    missing: list[str] = []
    md_lower = markdown.lower()
    for section_key, patterns in REQUIRED_SECTIONS.items():
        if any(p.lower() in md_lower for p in patterns):
            found.append(section_key)
        else:
            missing.append(section_key)
    return found, missing


def _count_source_family_mismatches(report_preview: dict) -> int:
    """Count claims where required_source_family differs from the evidence's source family."""
    count = 0
    # Claim briefs live under tool_composed_report in graph-v1 responses, not at
    # the report_preview top level. Fall back to sections paragraphs for safety.
    tcr = report_preview.get("tool_composed_report") or {}
    claim_briefs = list(tcr.get("claim_briefs") or [])
    if not claim_briefs:
        claim_briefs = list(report_preview.get("claim_briefs") or [])
    if not claim_briefs:
        sections = list(report_preview.get("sections", []))
        for sec in sections:
            if isinstance(sec, dict):
                claim_briefs.extend(list(sec.get("paragraphs", [])))
    for cb in claim_briefs:
        if not isinstance(cb, dict):
            continue
        required = str(cb.get("required_source_family", ""))
        # Check if the claim's evidence comes from a different family
        # (simplified: check claim family vs required_source_family alignment)
        claim_family = str(cb.get("claim_family", ""))
        if required == "official_policy" and claim_family in ("company_disclosure", "disclosure"):
            count += 1
        if required == "company_disclosure" and claim_family in ("policy_basis",):
            count += 1
    return count


def _count_p0_review_issues(report_preview: dict, markdown: str) -> int:
    """Count P0-level review issues: section_role mismatch, obligation blocker."""
    count = 0
    # Count section_role_mismatch from review issues in markdown
    role_mismatches = len(re.findall(
        r"section.?role.*mismatch|does not match.*claim family",
        markdown, re.IGNORECASE,
    ))
    count += role_mismatches
    # Count source diversity issues
    diversity = len(re.findall(
        r"fewer than two distinct sources|low.?source.?diversity",
        markdown, re.IGNORECASE,
    ))
    count += diversity
    return count


def _count_truncated_limitations(report_preview: dict, markdown: str) -> int:
    """Count truncated limitation strings in the markdown."""
    truncated = len(re.findall(r"…\(截断\)|…\(truncated\)", markdown))
    # Also detect very short limitation sentences (less than 15 chars ending abruptly)
    short_lims = len(re.findall(
        r"limitations?:.*?[\"'][^\"']{1,15}[\"']",
        markdown, re.IGNORECASE,
    ))
    return truncated + short_lims


def print_report(result: InspectResult) -> None:
    """Print a human-readable inspection report."""
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 60)
    print("Report Quality Inspection")
    print("=" * 60)
    print(f"Response:    {result.file_paths['response']}")
    print(f"Summary:     {result.file_paths['summary']}")
    print()
    wf = result.workflow
    print(f"Workflow:    status={wf['status']}  decision={wf['decision']}")
    print(f"Overall:     {result.overall}")
    print()
    print("── Metrics ──")
    for k, v in result.metrics.items():
        print(f"  {k}: {v}")
    print()
    print("── Checks ──")
    for c in result.checks:
        icon = "✅" if c["passed"] else "❌"
        detail = f"  ({c.get('detail', '')})" if c.get("detail") else ""
        print(f"  {icon} {c['check']}: {c['value']} (threshold: {c['threshold']}){detail}")
    print()
    passed = sum(1 for c in result.checks if c["passed"])
    total = len(result.checks)
    print(f"Checks passed: {passed}/{total}")
    print(f"Classification: {result.overall}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report quality inspection harness"
    )
    parser.add_argument(
        "--response", required=True,
        help="Path to response.json from a graph-v1 smoke run",
    )
    parser.add_argument(
        "--summary", required=True,
        help="Path to summary.json from a graph-v1 smoke run",
    )
    args = parser.parse_args()

    result = inspect(
        response_path=args.response,
        summary_path=args.summary,
    )
    print_report(result)

    # Exit code: 0 if workflow_pass_product_pass, 1 otherwise
    if result.overall == "workflow_pass_product_pass":
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    main()
