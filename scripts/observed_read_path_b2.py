# ruff: noqa: E501
"""Phase B.2 — Observed Read Path (shadow, three-track).

Computes three parallel coverage tracks over recorded cases:
- raw                   : raw_supporting_source_count (no content dedup)
- threshold=0.90        : current auto-merge similarity (formal-read candidate)
- threshold=0.80        : PILOT_CANDIDATE threshold (0.80 is NOT the formal
                          threshold, only a candidate from the pilot sweep)

For every Slot / Section / Report, outputs readiness for all three tracks and
the transitions between them. Also aggregates blocking-rule hit counts and the
pairs/claims they affect.

HARD BOUNDARIES: this is OBSERVATION ONLY. It does not modify Editor1, Claim
cards, backfill, final report, or LangGraph routing.
"""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path

from packages.research_harness.sufficiency_gate import build_shadow_coverage_report

REPO = Path(__file__).resolve().parents[1]
PILOT_CANDIDATE = 0.80
CURRENT = 0.90


def _load_run(db_path: Path) -> dict:
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from shadow_difference_report import _load_run as load
    return load(db_path)


def _synthetic_three_track_demo() -> dict:
    """Synthetic demo to illustrate the three-track mechanism (clearly labeled).

    3 sources where 2 are near-duplicates in the [0.80, 0.90) band:
    - raw           : 3 sources -> satisfied
    - dup @ 0.90    : pair NOT merged (sim < 0.90) -> distinct 3 -> satisfied
    - dup @ 0.80    : pair merged -> distinct 2 < min_evidence 3 -> insufficient
    Demonstrates that the threshold choice flips a slot satisfied -> insufficient.
    """
    plan = {
        "normalized_query": "demo",
        "dimension_plan": [{
            "dimension_id": "dim_project", "dimension_type": "execution",
            "research_question": "项目状态", "why_it_matters": "demo",
            "coverage_required": "demo", "expected_section_heading": "项目",
            "source_priority": "B",
            "source_families": ["public_resource_transaction"],
            "caliber_terms": ["低空经济"],
        }],
        "source_obligations": [{
            "obligation_id": "obl", "source_family": "public_resource_transaction",
            "required_for": "项目", "min_required_evidence": 3,
        }],
        "query_requirements": {},
    }
    body = "合肥低空经济项目2025年开工建设，投资约10亿元，预计2026年投运，政策支持持续加码。"
    near = body + "，产业生态不断完善。"  # sim ~0.83 in [0.80, 0.90)
    state = {
        "plan": plan,
        "sources": [
            {"source_id": "a", "url": "https://x.com/a", "title": "a", "source_family": "public_resource_transaction", "full_text": body},
            {"source_id": "b", "url": "https://x.com/b", "title": "b", "source_family": "public_resource_transaction", "full_text": near},
            {"source_id": "c", "url": "https://x.com/c", "title": "c", "source_family": "public_resource_transaction", "full_text": "合肥市另一项目，规模600亿元，市场关注度高。"},
        ],
        "evidence": [
            {"evidence_id": "e1", "source_id": "a", "source_ids": ["a"], "source_family": "public_resource_transaction", "stage": "招标"},
            {"evidence_id": "e2", "source_id": "b", "source_ids": ["b"], "source_family": "public_resource_transaction", "stage": "招标"},
            {"evidence_id": "e3", "source_id": "c", "source_ids": ["c"], "source_family": "public_resource_transaction", "stage": "招标"},
        ],
        "claims": [],
        "search_events": [{"target_source_family": "public_resource_transaction", "round": 1}],
        "research_gaps": [],
    }
    r090 = build_shadow_coverage_report(copy.deepcopy(state), cluster_threshold=CURRENT)
    r080 = build_shadow_coverage_report(copy.deepcopy(state), cluster_threshold=PILOT_CANDIDATE)
    s090 = r090["slots"][0]
    s080 = r080["slots"][0]
    return {
        "label": "synthetic demo (illustrates three-track mechanism; NOT recorded data)",
        "slot_id": s090["slot_id"],
        "min_evidence": s090["min_evidence_items"],
        "raw_supporting_source_count": s090["raw_supporting_source_count"],
        "distinct_090": s090["distinct_supporting_content_count"],
        "distinct_080": s080["distinct_supporting_content_count"],
        "raw_status": s090["raw_status"],
        "dup_090_status": s090["duplicate_adjusted_status"],
        "dup_080_status": s080["duplicate_adjusted_status"],
        "transition_raw_to_080": f"{s090['raw_status']}_to_{s080['duplicate_adjusted_status']}",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="B.2 Observed Read Path (shadow, three-track)")
    ap.add_argument("--cases", nargs="+", default=["M03", "M12", "P04", "P08", "C01", "K07"])
    ap.add_argument("--run-dir", default="data/tmp/resume_eval_A_6b")
    ap.add_argument("--output-dir", default="data/tmp/observed_read_path_b2")
    args = ap.parse_args()

    out_dir = REPO / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    run_dir = REPO / args.run_dir

    per_case = []
    total_blocking = Counter()
    for qid in args.cases:
        db = run_dir / f"{qid}.db"
        if not db.exists():
            continue
        run = _load_run(db)
        state = {
            "plan": run.get("plan"),
            "evidence": run.get("evidence", []),
            "claims": run.get("claims", []),
            "sources": run.get("sources", []),
            "search_events": [],
            "research_gaps": [],
        }
        r090 = build_shadow_coverage_report(copy.deepcopy(state), cluster_threshold=CURRENT)
        r080 = build_shadow_coverage_report(copy.deepcopy(state), cluster_threshold=PILOT_CANDIDATE)

        slot_tracks = []
        slots_090 = {s["slot_id"]: s for s in r090["slots"]}
        slots_080 = {s["slot_id"]: s for s in r080["slots"]}
        for sid, s090 in slots_090.items():
            s080 = slots_080.get(sid, {})
            slot_tracks.append({
                "slot_id": sid,
                "section_id": s090.get("section_id"),
                "priority": s090.get("priority"),
                "raw_supporting_source_count": s090.get("raw_supporting_source_count"),
                "raw_status": s090.get("raw_status"),
                "dup_090_status": s090.get("duplicate_adjusted_status"),
                "dup_080_status": s080.get("duplicate_adjusted_status"),
                "dup_090_distinct": s090.get("distinct_supporting_content_count"),
                "dup_080_distinct": s080.get("distinct_supporting_content_count"),
                "transition_raw_to_090": f"{s090.get('raw_status')}_to_{s090.get('duplicate_adjusted_status')}",
                "transition_raw_to_080": f"{s090.get('raw_status')}_to_{s080.get('duplicate_adjusted_status')}",
                "affected_claim_ids": s090.get("affected_claim_ids", []),
                "blocking_reasons": s090.get("blocking_reasons", []),
            })
        for reason, n in r080.get("blocking_rule_hits", {}).items():
            total_blocking[reason] += n

        per_case.append({
            "case": qid,
            "summary_090": r090["summary"],
            "summary_080": r080["summary"],
            "blocking_rule_hits": r080.get("blocking_rule_hits", {}),
            "slot_tracks": slot_tracks,
        })
        print(f"[OK] {qid}: raw_satisfied={r090['summary']['raw_satisfied_slot_count']} "
              f"dup090={r090['summary']['duplicate_adjusted_satisfied_slot_count']} "
              f"dup080={r080['summary']['duplicate_adjusted_satisfied_slot_count']}")

    report = {
        "report_version": "coverage_report_v1",
        "mode": "shadow_observed_read_path",
        "shadow_only": True,
        "pilot_candidate_threshold": PILOT_CANDIDATE,
        "current_threshold": CURRENT,
        "note": "0.80 is a PILOT CANDIDATE threshold, NOT the formal threshold. "
                "Observed only; Editor1/Claim/backfill/final report/LangGraph routing unchanged.",
        "per_case": per_case,
        "blocking_rule_hits_total": dict(total_blocking),
        "rules_evaluated": ["critical_fact_conflict", "summary_or_excerpt", "document_type_incompatible"],
        "synthetic_demo": _synthetic_three_track_demo(),
    }
    (out_dir / "observed_read_path.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n[DONE] -> {out_dir / 'observed_read_path.json'}")


if __name__ == "__main__":
    main()
