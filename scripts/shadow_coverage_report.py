# ruff: noqa: E501
"""Phase B.1 — Shadow CoverageReport over recorded cases (no re-networking).

Loads the frozen 6-case checkpoint DBs, builds a graph state, and runs
build_shadow_coverage_report. Emits a dual-track shadow report showing which
slots flip raw -> duplicate_adjusted, which sections would block, which claims
are affected, and which ResearchGaps are shadow-eligible.

SHADOW ONLY: nothing here changes Editor1 routing, claim strength, backfill,
writing approvals, or the final report.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from packages.research_harness.sufficiency_gate import build_shadow_coverage_report

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ["M03", "M12", "P04", "P08", "C01", "K07"]


def _load_run(db_path: Path) -> dict:
    """Reuse the same loader as shadow_difference_report (sources full_text etc.)."""
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from shadow_difference_report import _load_run as load
    return load(db_path)


def main() -> None:
    run_dir = REPO / "data" / "tmp" / "resume_eval_A_6b"
    out_dir = REPO / "data" / "tmp" / "shadow_coverage_report_b1"
    out_dir.mkdir(parents=True, exist_ok=True)

    per_case = []
    all_flips = []
    all_eligible_gaps = []
    for qid in DEFAULT_CASES:
        db = run_dir / f"{qid}.db"
        if not db.exists():
            continue
        run = _load_run(db)
        state = {
            "plan": run.get("plan"),
            "evidence": run.get("evidence", []),
            "claims": run.get("claims", []),
            "sources": run.get("sources", []),
            "search_events": [],  # checkpoint DBs do not persist search_events
            "research_gaps": [],
        }
        report = build_shadow_coverage_report(copy.deepcopy(state))
        flips = [
            s for s in report.get("slots", [])
            if s["raw_status"] != s["duplicate_adjusted_status"]
        ]
        would_block_sections = [
            s for s in report.get("sections", [])
            if s["raw_status"] != s["duplicate_adjusted_status"]
        ]
        affected_claims = sorted({
            cid for s in flips for cid in s.get("affected_claim_ids", [])
        })
        eligible = [
            g for g in report.get("research_gaps", [])
            if g.get("shadow_reportability") == "eligible_if_enabled"
        ]
        per_case.append({
            "case": qid,
            "summary": report["summary"],
            "critical_gate": report["critical_gate"],
            "satisfied_slots": [
                s["slot_id"] for s in report.get("slots", [])
                if s["duplicate_adjusted_status"] == "satisfied"
            ],
            "insufficient_slots": [
                s["slot_id"] for s in report.get("slots", [])
                if s["duplicate_adjusted_status"] == "unsatisfied"
            ],
            "not_evaluable_slots": [
                s["slot_id"] for s in report.get("slots", [])
                if s["duplicate_adjusted_status"] == "not_evaluable"
            ],
            "flipped_slots": flips,
            "would_block_sections": would_block_sections,
            "affected_claims": affected_claims,
            "eligible_gaps": eligible,
        })
        for f in flips:
            all_flips.append({"case": qid, **f})
        for g in eligible:
            all_eligible_gaps.append({"case": qid, **g})
        sm = report["summary"]
        print(
            f"[OK] {qid}: raw[sat={sm['raw_satisfied_slot_count']} "
            f"unsat={sm['raw_insufficient_slot_count']} "
            f"ne={sm['raw_not_evaluable_slot_count']}] "
            f"dup[sat={sm['duplicate_adjusted_satisfied_slot_count']} "
            f"unsat={sm['duplicate_adjusted_insufficient_slot_count']} "
            f"ne={sm['duplicate_adjusted_not_evaluable_slot_count']}] "
            f"flips={len(flips)}"
        )

    report = {
        "report_version": "coverage_report_v1",
        "mode": "shadow",
        "shadow_only": True,
        "cases": DEFAULT_CASES,
        "per_case": per_case,
        "aggregate": {
            "flipped_slot_count": len(all_flips),
            "flipped_slots": all_flips,
            "eligible_gap_count": len(all_eligible_gaps),
            "eligible_gaps": all_eligible_gaps,
        },
        "note": "Three-state (satisfied/unsatisfied/not_evaluable). 6b checkpoints lack both structured "
                "key fields and search_events -> every slot is not_evaluable (6-7 per case), readiness=unknown. "
                "This is the honest answer per review 2026-08-04: historical data missing structured fields or "
                "search_events must be not_evaluable, never false. 0 raw->dup flips. A flip requires a slot "
                "with raw>=min and distinct<min with fields+search evaluable.",
    }
    (out_dir / "shadow_coverage_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n[DONE] -> {out_dir / 'shadow_coverage_report.json'}")


if __name__ == "__main__":
    main()
