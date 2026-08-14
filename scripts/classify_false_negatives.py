# ruff: noqa: E501, I001
"""A2.6 — classify the 16 critical_fact_conflict false negatives.

These are exact_duplicate / full_reprint pairs wrongly BLOCKED by the current
whole-document critical_fact_conflict rule. Classification feeds the FactFrame
(entity/attribute/scope/time) design so it does not repeat the same mistake.

Error categories:
- multi_entity_document  : long doc with many entities/amounts; fact-set diff
                           belongs to DIFFERENT entities
- scope_mismatch         : 总投资 vs 一期/二期口径
- attribute_mismatch     : 总投资 vs 合同/中标/补贴金额被错误比较
- text_truncation        : page parse/truncation -> different fact set
- template_noise         : nav/related-article introduces status/years
- publication_metadata   : publication date / policy year treated as body fact
- true_revision          : actual status/amount update
- unknown
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def classify(a: str, b: str, subjects_a, subjects_b, ratio: float) -> list[str]:
    cats: list[str] = []
    if ratio < 0.6:
        cats.append("text_truncation")
    sa_set, sb_set = set(subjects_a), set(subjects_b)
    if sa_set and sb_set and len(sa_set.symmetric_difference(sb_set)) / max(1, len(sa_set | sb_set)) >= 0.4:
        cats.append("multi_entity_document")
    elif len(sa_set | sb_set) > 4 and (sa_set or sb_set):
        cats.append("multi_entity_document")
    if not cats:
        cats.append("scope_or_attribute_mismatch")
    return cats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blind", required=True)
    ap.add_argument("--algorithm", required=True)
    args = ap.parse_args()

    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from threshold_sweep import _dedup_by_url_pair, _load_pairs
    from packages.research_harness.source_cluster import blocking_reasons
    from audit_pairs_review import _conflict_detail, _subjects

    pairs, _ = _dedup_by_url_pair(_load_pairs(args.blind, args.algorithm))
    MERGE = {"exact_duplicate", "full_reprint"}
    rows = []
    for p in pairs:
        if p["human_label"] not in MERGE:
            continue
        reasons = blocking_reasons(p["a_text"], p["b_text"], a_family=p["a_family"], b_family=p["b_family"])
        if "critical_fact_conflict" not in reasons:
            continue
        a, b = p["a_text"], p["b_text"]
        cd = _conflict_detail(a, b)
        subj_a, subj_b = _subjects(a), _subjects(b)
        la, lb = len(a.replace(" ", "")), len(b.replace(" ", ""))
        ratio = round(min(la, lb) / max(1, max(la, lb)), 2)
        cats = classify(a, b, subj_a, subj_b, ratio)
        rows.append({
            "pair_id": p["pair_id"],
            "human_label": p["human_label"],
            "conflict_type": cd["conflict_type"] if cd else "?",
            "categories": cats,
            "primary_category": cats[0],
            "length_ratio": ratio,
            "families": f"{p['a_family']}/{p['b_family']}",
            "status_a": json.dumps(cd.get("a_values", []), ensure_ascii=False) if cd and cd.get("conflict_type") == "status" else "",
            "status_b": json.dumps(cd.get("b_values", []), ensure_ascii=False) if cd and cd.get("conflict_type") == "status" else "",
            "amount_a": json.dumps(cd.get("a_values", []), ensure_ascii=False) if cd and cd.get("conflict_type") == "amount" else "",
            "amount_b": json.dumps(cd.get("b_values", []), ensure_ascii=False) if cd and cd.get("conflict_type") == "amount" else "",
            "subjects_overlap": len(set(subj_a) & set(subj_b)),
        })

    summary = Counter(r["primary_category"] for r in rows)
    out = {"total": len(rows), "summary": dict(summary), "rows": rows}
    out_dir = REPO / "data" / "tmp" / "a26_error_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "false_negative_classification.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md = ["# A2.6 False-Negative Error Classification (16 pairs)", "",
          f"total: {len(rows)}", "", "| category | count |", "|---|---|"]
    for cat, n in sorted(summary.items()):
        md.append(f"| {cat} | {n} |")
    md.append("")
    md.append("| pair_id | label | conflict_type | primary_category | length_ratio | families |")
    md.append("|---|---|---|---|---|---|")
    for r in rows:
        md.append(f"| {r['pair_id']} | {r['human_label']} | {r['conflict_type']} | "
                  f"{r['primary_category']} | {r['length_ratio']} | {r['families']} |")
    (out_dir / "false_negative_classification.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"total": len(rows), "summary": dict(summary)}, ensure_ascii=False, indent=2))
    print(f"[DONE] -> {out_dir}")


if __name__ == "__main__":
    main()
