# ruff: noqa: E501
"""Blind-review pilot summary for the 60-pair priority audit.

Reads the human-annotated blind CSV + the algorithm CSV (linked by pair_id),
separates the 24 trivial self-pairs (same source_id + same URL) from the 36
real cross-source pairs, and reports:
- auto_merge precision / false-merge count (real pairs only)
- candidate merge-eligible ratio (threshold tuning signal)
- near_threshold composition
- revision evaluability (currently blocked by self-pair data quality)
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

MERGE_LABELS = {"exact_duplicate", "full_reprint", "near_duplicate_rewrite"}
DONT_MERGE_LABELS = {
    "summary_or_excerpt", "same_event_independent_reporting",
    "revision_or_status_update", "related_but_independent",
}


def _read(p: Path) -> list[dict]:
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blind", required=True, help="annotated blind CSV")
    ap.add_argument("--algorithm", default=str(REPO / "data/tmp/shadow_difference_report/audit_priority_review_algorithm.csv"))
    ap.add_argument("--out-dir", default=str(REPO / "data/tmp/shadow_difference_report"))
    args = ap.parse_args()

    blind = _read(Path(args.blind))
    alg = _read(Path(args.algorithm))
    alg_by_id = {r["pair_id"]: r for r in alg}

    assert {r["pair_id"] for r in blind} == set(alg_by_id), "pair_id mismatch blind/algorithm"

    self_pairs, real = [], []
    for r in blind:
        a_sid, b_sid = str(r.get("a_source_id") or "").strip(), str(r.get("b_source_id") or "").strip()
        a_url, b_url = str(r.get("a_url") or "").strip(), str(r.get("b_url") or "").strip()
        entry = {
            "pair_id": r["pair_id"],
            "a_source_id": a_sid, "b_source_id": b_sid,
            "label": (r.get("human_label") or "").strip(),
            "confidence": (r.get("human_confidence") or "").strip(),
            "notes": (r.get("review_notes") or "").strip(),
            "decision": alg_by_id[r["pair_id"]]["algorithm_decision"],
            "content_similarity": float(alg_by_id[r["pair_id"]].get("content_similarity", 0) or 0),
            "duplicate_reason": alg_by_id[r["pair_id"]].get("duplicate_reason", ""),
        }
        is_self = bool(a_sid and a_sid == b_sid and a_url and a_url == b_url)
        (self_pairs if is_self else real).append(entry)

    def _stats(rows: list[dict]) -> dict:
        n = len(rows)
        merge_n = sum(1 for e in rows if e["label"] in MERGE_LABELS)
        return {
            "n": n,
            "label_distribution": dict(Counter(e["label"] for e in rows)),
            "merge_eligible": merge_n,
            "merge_eligible_rate": round(merge_n / max(1, n), 4),
            "high_confidence": sum(1 for e in rows if e["confidence"] == "high"),
        }

    by_decision = {d: [e for e in real if e["decision"] == d] for d in ("auto_merge", "candidate", "near_threshold", "revision")}
    auto = _stats(by_decision["auto_merge"])
    auto_fp = auto["n"] - auto["merge_eligible"]
    revision_real = _stats(by_decision["revision"])

    summary = {
        "annotation_schema_version": "source_cluster_human_label_v1",
        "labeling_protocol_version": "source_cluster_review_protocol_v1",
        "input": {"blind": str(args.blind), "total_pairs": len(blind)},
        "data_quality": {
            "trivial_self_pairs": len(self_pairs),
            "trivial_self_pair_decision": dict(Counter(e["decision"] for e in self_pairs)),
            "trivial_self_pair_labels": dict(Counter(e["label"] for e in self_pairs)),
            "note": "self-pairs (same source_id+URL) are duplicate source rows; they only prove exact "
                    "duplication, NOT clustering precision; excluded from real metrics",
        },
        "real_pairs": {
            "n": len(real),
            "decision_distribution": dict(Counter(e["decision"] for e in real)),
            "auto_merge": {
                **auto,
                "precision": round(auto["merge_eligible"] / max(1, auto["n"]), 4),
                "false_merge_count": auto_fp,
            },
            "candidate": _stats(by_decision["candidate"]),
            "near_threshold": _stats(by_decision["near_threshold"]),
            "revision": {
                **revision_real,
                "evaluable": revision_real["n"] > 0,
                "note": "real cross-source revision pairs unavailable in this pool (all 24 revision "
                        "decisions were trivial self-pairs) -> revision protection rate not evaluable",
            },
        },
        "threshold_signal": {
            "candidate_merge_eligible_rate": round(
                sum(1 for e in by_decision["candidate"] if e["label"] in MERGE_LABELS) / max(1, len(by_decision["candidate"])), 4
            ),
            "note": "candidates are 100% merge-eligible -> auto_merge threshold 0.90 may be too "
                    "conservative; consider lowering toward the candidate band",
        },
    }

    out = REPO / args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "blind_review_pilot_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Blind-Review Pilot Summary (60 pairs)",
        "",
        f"- total: {len(blind)} | real cross-source: {len(real)} | trivial self-pairs: {len(self_pairs)}",
        "- labels: " + json.dumps(dict(Counter((e.get('human_label') or '').strip() for e in blind)), ensure_ascii=False),
        "",
        "## Real cross-source metrics",
        "",
        "| group | n | merge-eligible | precision / rate |",
        "|---|---|---|---|",
    ]
    for group, key in (("auto_merge", "precision"), ("candidate", "merge_eligible_rate"), ("near_threshold", "merge_eligible_rate")):
        s = summary["real_pairs"][group]
        lines.append(f"| {group} | {s['n']} | {s['merge_eligible']} | {s[key]} |")
    lines.append("")
    am_precision = summary["real_pairs"]["auto_merge"]["precision"]
    lines.append(f"**auto_merge precision = {am_precision:.3f}** (false_merge={auto_fp})")
    lines.append("")
    lines.append("## Data quality finding")
    lines.append("")
    lines.append(f"- {len(self_pairs)} trivial self-pairs (same source_id + same URL) were all algorithm "
                 "`revision` but human `exact_duplicate` -> duplicate source rows in the pool; they do NOT "
                 "test clustering precision and were excluded.")
    lines.append("- revision protection rate NOT evaluable from this pool (no real cross-source revision pairs).")
    lines.append("")
    lines.append("## Threshold signal")
    lines.append("")
    lines.append(f"- candidates {summary['threshold_signal']['candidate_merge_eligible_rate']:.0%} merge-eligible "
                 "-> auto_merge threshold 0.90 may be too conservative.")
    lines.append("")
    (out / "blind_review_pilot_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary["real_pairs"], ensure_ascii=False, indent=2))
    print(f"\n[DONE] -> {out / 'blind_review_pilot_summary.json'} + .md")


if __name__ == "__main__":
    main()
