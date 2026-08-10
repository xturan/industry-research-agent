# ruff: noqa: E501
"""Threshold sweep for Source Content Clustering auto-merge.

Evaluates the auto-merge similarity threshold against HUMAN-labeled pairs, WITH
the three blocking rules applied (critical_fact_conflict / summary_or_excerpt /
document_type_incompatible). Blocking rules are precision guards that act before
the threshold, so the sweep answers: given blocking rules active, which
threshold maximizes recall while keeping precision >= 0.95 and severe false
merge = 0.

Group split: pairs are grouped by task (case / document family) and assigned
deterministically to Calibration or Validation so a pair's task never leaks
across splits.

Per-threshold metrics:
- precision = TP / (TP + FP)
- recall    = TP / (TP + FN)
- false_merge = FP
- severe_false_merge = FP where human label is high-severity (independent
  reporting / revision-or-status-update / policy-vs-interpretation)
- revision_protection = revisions correctly NOT merged / all revisions

Selection rule (Calibration): severe_false_merge == 0, precision >= 0.95,
then maximize recall.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from packages.research_harness.source_cluster import (
    _simhash,
    blocking_reasons,
    canonicalize_url,
    content_similarity_from_hashes,
)

REPO = Path(__file__).resolve().parents[1]
THRESHOLDS = [0.90, 0.88, 0.86, 0.85, 0.84, 0.82, 0.80, 0.78]
MERGE_LABELS = {"exact_duplicate", "full_reprint", "near_duplicate_rewrite"}
SEVERE_LABELS = {
    "same_event_independent_reporting",
    "revision_or_status_update",
    "related_but_independent",
}


def _load_pairs(blind_csv: Path, algorithm_csv: Path) -> list[dict]:
    """Load labeled pairs with full text + features from the audit pool."""
    csv.field_size_limit(10_000_000)
    blind = {r["pair_id"]: r for r in csv.DictReader(open(blind_csv, encoding="utf-8-sig"))}
    all_json = Path(algorithm_csv).parent / "audit_pairs_all.json"
    pool = {}
    if all_json.exists():
        pool = {p["pair_id"]: p for p in json.loads(all_json.read_text(encoding="utf-8"))}

    pairs = []
    for pid, b in blind.items():
        label = (b.get("human_label") or "").strip()
        if not label:
            continue
        # skip trivial self-pairs (same source_id + same URL)
        a_sid = (b.get("a_source_id") or "").strip()
        b_sid = (b.get("b_source_id") or "").strip()
        a_url = (b.get("a_url") or "").strip()
        b_url = (b.get("b_url") or "").strip()
        if a_sid and a_sid == b_sid and a_url and a_url == b_url:
            continue
        p = pool.get(pid, {})
        a = p.get("source_a", {})
        bb = p.get("source_b", {})
        a_text = a.get("full_text") or ""
        b_text = bb.get("full_text") or ""
        fa = _simhash(a_text) if a_text else None
        fb = _simhash(b_text) if b_text else None
        sim = content_similarity_from_hashes(fa, fb) if (fa is not None and fb is not None) else 0.0
        pairs.append({
            "pair_id": pid,
            "case": b.get("case") or p.get("case") or "",
            "a_source_id": b.get("a_source_id") or "",
            "b_source_id": b.get("b_source_id") or "",
            "a_family": b.get("a_family") or "",
            "b_family": b.get("b_family") or "",
            "a_text": a_text,
            "b_text": b_text,
            "content_similarity": sim,
            "human_label": label,
            "confidence": (b.get("human_confidence") or "").strip(),
        })
    return pairs


def _load_fixtures(path: Path) -> list[dict]:
    """Load deterministic benchmark fixtures (revision + doc-type), computing
    content_similarity from full text. These have known labels and are reported
    separately from real samples downstream."""
    if not path.exists():
        return []
    out = []
    for p in json.loads(path.read_text(encoding="utf-8")):
        a, b = p["source_a"], p["source_b"]
        fa = _simhash(a.get("full_text") or "")
        fb = _simhash(b.get("full_text") or "")
        sim = content_similarity_from_hashes(fa, fb) if (fa and fb) else 0.0
        out.append({
            "pair_id": p["pair_id"],
            "case": p.get("case", "benchmark"),
            "a_source_id": a.get("source_id", ""),
            "b_source_id": b.get("source_id", ""),
            "a_family": a.get("family", ""),
            "b_family": b.get("family", ""),
            "a_text": a.get("full_text", ""),
            "b_text": b.get("full_text", ""),
            "content_similarity": sim,
            "human_label": p.get("human_label", ""),
            "confidence": p.get("human_confidence", ""),
            "_fixture": True,
        })
    return out


def _dedup_by_url_pair(pairs: list[dict]) -> tuple[list[dict], dict]:
    """Dedup cross-checkpoint duplicate records by stable canonical URL pair.

    Same (canonical_url_a, canonical_url_b) from different checkpoints is the
    same source pair re-sampled; keep the first and count the rest. This avoids
    re-weighting a source pair in precision/recall.
    """
    seen: dict[tuple[str, str], int] = {}
    groups: dict[tuple[str, str], int] = {}
    out: list[dict] = []
    for p in pairs:
        ua = canonicalize_url(p.get("a_url") or "")
        ub = canonicalize_url(p.get("b_url") or "")
        key = tuple(sorted([ua, ub])) if (ua or ub) else (p["a_source_id"], p["b_source_id"])
        groups[key] = groups.get(key, 0) + 1
        if key in seen:
            seen[key] += 1
            continue
        seen[key] = 0
        out.append(p)
    removed = sum(seen.values())
    return out, {"removed_count": removed, "duplicate_groups": sum(1 for v in seen.values() if v > 0), "total_groups": len(groups)}


def _group_split(pairs: list[dict], *, calibration_share: float = 0.5) -> tuple[list[dict], list[dict]]:
    """Deterministic group split by task/case: a task goes entirely to one split."""
    cases = sorted({p["case"] for p in pairs})
    cal_cases = {c for i, c in enumerate(cases) if (hash((c, "cal")) % 100) < calibration_share * 100}
    cal = [p for p in pairs if p["case"] in cal_cases]
    val = [p for p in pairs if p["case"] not in cal_cases]
    return cal, val


BLOCKING_MODES = {
    "none": set(),
    "critical_fact_conflict": {"critical_fact_conflict"},
    "summary_or_excerpt": {"summary_or_excerpt"},
    "document_type_incompatible": {"document_type_incompatible"},
    "all": {"critical_fact_conflict", "summary_or_excerpt", "document_type_incompatible"},
}


def _algo_merge(p: dict, threshold: float, blocking_modes: set[str]) -> tuple[bool, list[str]]:
    reasons = blocking_reasons(
        p["a_text"], p["b_text"],
        a_family=p.get("a_family"), b_family=p.get("b_family"),
    )
    active = [r for r in reasons if r in blocking_modes]
    merge = p["content_similarity"] >= threshold and not active
    return merge, active


def _evaluate(pairs: list[dict], threshold: float, blocking_modes: set[str] | None = None) -> dict:
    blocking_modes = BLOCKING_MODES["all"] if blocking_modes is None else blocking_modes
    tp = fp = tn = fn = 0
    severe_fp: list[str] = []
    revisions = [p for p in pairs if p["human_label"] == "revision_or_status_update"]
    revision_blocked = 0
    for p in pairs:
        merge, reasons = _algo_merge(p, threshold, blocking_modes)
        human_merge = p["human_label"] in MERGE_LABELS
        if merge and human_merge:
            tp += 1
        elif merge and not human_merge:
            fp += 1
            if p["human_label"] in SEVERE_LABELS:
                severe_fp.append(p["pair_id"])
        elif not merge and human_merge:
            fn += 1
        else:
            tn += 1
        if p["human_label"] == "revision_or_status_update" and not merge:
            revision_blocked += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "threshold": threshold,
        "n": len(pairs),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "false_merge_count": fp,
        "severe_false_merge_count": len(severe_fp),
        "severe_false_merge_pairs": severe_fp,
        "revision_protection": round(revision_blocked / max(1, len(revisions)), 4),
        "revision_count": len(revisions),
        "blocking_reasons_distribution": dict(Counter(
            r for p in pairs for r in blocking_reasons(p["a_text"], p["b_text"],
                                                       a_family=p.get("a_family"), b_family=p.get("b_family"))
        )),
    }


def _pick_best(rows: list[dict]) -> dict | None:
    """Selection rule: severe_false_merge==0, precision>=0.95, then max recall."""
    eligible = [r for r in rows if r["severe_false_merge_count"] == 0 and r["precision"] >= 0.95]
    if not eligible:
        return None
    return max(eligible, key=lambda r: r["recall"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blind", required=True, help="labeled blind CSV (human labels filled)")
    ap.add_argument("--algorithm", required=True, help="algorithm CSV (same pool)")
    ap.add_argument("--output-dir", default="data/tmp/shadow_difference_report_v2")
    ap.add_argument("--thresholds", nargs="+", type=float, default=THRESHOLDS)
    ap.add_argument("--ablation", action="store_true", help="report blocking-rule ablation")
    ap.add_argument("--fixtures", default="", help="benchmark fixtures JSON (deterministic labels)")
    ap.add_argument("--dedup-url", action="store_true",
                    help="dedup cross-checkpoint duplicate records by canonical URL pair")
    args = ap.parse_args()

    pairs = _load_pairs(Path(args.blind), Path(args.algorithm))
    dedup_info = {"applied": False, "removed_count": 0, "duplicate_groups": 0, "total_groups": len(pairs)}
    if args.dedup_url:
        pairs, dedup_info = _dedup_by_url_pair(pairs)
        dedup_info["applied"] = True
    fixtures = _load_fixtures(Path(args.fixtures)) if args.fixtures else []
    print(f"[INFO] real labeled pairs={len(pairs)} (dedup removed {dedup_info['removed_count']}) "
          f"fixtures={len(fixtures)}")
    if not pairs and not fixtures:
        raise SystemExit("[ERROR] no labeled pairs found")
    cal, val = _group_split(pairs + fixtures)
    print(f"[INFO] total={len(pairs) + len(fixtures)} calibration={len(cal)} validation={len(val)}")

    cal_rows = [_evaluate(cal, t) for t in args.thresholds]
    best = _pick_best(cal_rows)
    val_rows = [_evaluate(val, best["threshold"]) if best else None for _ in [0]]

    ablation = None
    if args.ablation:
        ablation = {}
        for mode, modes in BLOCKING_MODES.items():
            rows = [_evaluate(cal, t, modes) for t in args.thresholds]
            best_mode = _pick_best(rows)
            ablation[mode] = {
                "blocking_rules": sorted(modes),
                "per_threshold": rows,
                "selected_threshold": best_mode["threshold"] if best_mode else None,
                "selected_metrics": (
                    {k: best_mode[k] for k in ("precision", "recall", "false_merge_count",
                                               "severe_false_merge_count", "revision_protection")}
                    if best_mode else None
                ),
            }

    result = {
        "label_distribution": dict(Counter(p["human_label"] for p in pairs)),
        "dedup": dedup_info,
        "split": {"calibration_pairs": len(cal), "validation_pairs": len(val),
                  "calibration_cases": sorted({p["case"] for p in cal}),
                  "validation_cases": sorted({p["case"] for p in val})},
        "thresholds": args.thresholds,
        "calibration": cal_rows,
        "selected_threshold": best["threshold"] if best else None,
        "selection_note": (
            "severe_false_merge==0 AND precision>=0.95, then max recall"
            if best else "no threshold met the selection rule"
        ),
        "validation": val_rows,
        "ablation": ablation,
    }
    out = REPO / args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "threshold_sweep.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# Threshold Sweep (auto-merge similarity)", "", f"- labeled pairs: {len(pairs)}",
             f"- calibration: {len(cal)} | validation: {len(val)}", "",
             "| threshold | precision | recall | FP | severe FP | revision protection |",
             "|---|---|---|---|---|---|"]
    for r in cal_rows:
        lines.append(f"| {r['threshold']} | {r['precision']} | {r['recall']} | {r['false_merge_count']} | "
                     f"{r['severe_false_merge_count']} | {r['revision_protection']} |")
    lines.append("")
    if best:
        lines.append(f"**selected threshold = {best['threshold']}** "
                     f"(precision {best['precision']}, recall {best['recall']}, severe FP {best['severe_false_merge_count']})")
        v = val_rows[0]
        lines.append("")
        lines.append("## Validation")
        lines.append(f"- precision={v['precision']} recall={v['recall']} "
                     f"false_merge={v['false_merge_count']} severe_fp={v['severe_false_merge_count']} "
                     f"revision_protection={v['revision_protection']}")
    else:
        lines.append("**no threshold met selection rule**")
    lines.append("")
    (out / "threshold_sweep.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[DONE] -> {out / 'threshold_sweep.json'} + .md")


if __name__ == "__main__":
    main()
