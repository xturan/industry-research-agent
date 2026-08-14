# ruff: noqa: E501
"""Phase A2 Shadow Source Content Clustering — audit report.

Builds the 10 labeled positive/negative source-pair scenarios, runs the
deterministic shadow clusterer, and reports:
  - duplicate precision / recall / false-merge rate
  - per-slot shadow count differences
  - cluster audit rows

This is a SHADOW audit: nothing here changes the formal source_count / claim /
gate / report behavior.
"""

from __future__ import annotations

import json
from pathlib import Path

from packages.research_harness.source_cluster import cluster_sources, slot_source_counts

BODY = "合肥低空经济产业2025年规模达500亿元，同比增长8%，预计2026年突破600亿元，政策支持持续加码。"


def _src(sid: str, *, url: str, title: str = "", full_text: str = "") -> dict:
    return {"source_id": sid, "url": url, "title": title or full_text[:20], "full_text": full_text}


def _positive_cases() -> list[tuple[str, list[dict], str]]:
    """(name, sources, expected_note) — these should merge into 1 cluster."""
    long_body = BODY * 6
    return [
        (
            "p1_same_url_diff_utm",
            [
                _src("a", url="https://hefei.gov.cn/p1?utm_source=wechat", full_text=BODY),
                _src("b", url="https://hefei.gov.cn/p1?utm_source=weibo", full_text=BODY),
            ],
            "same canonical URL + identical content",
        ),
        (
            "p2_diff_domain_same_body",
            [
                _src("a", url="https://gov.cn/p", full_text=BODY),
                _src("b", url="https://news.cn/reprint", full_text=BODY),
            ],
            "identical content, different hosts",
        ),
        (
            "p3_header_footer_template",
            [
                _src("a", url="https://a.com/p", full_text="【站点A导航】" + long_body + "【站点A版权】"),
                _src("b", url="https://b.com/p", full_text="【站点B导航】" + long_body + "【站点B备案】"),
            ],
            "site header/footer template noise only",
        ),
        (
            "p4_title_minor_change_body_high_sim",
            [
                _src("a", url="https://a.com/p1", title="合肥低空经济规模报告", full_text=BODY),
                _src("b", url="https://b.com/p2", title="合肥低空经济规模报告(修订版)", full_text=BODY[:-1] + "！"),
            ],
            "one-char body variant + near-identical title",
        ),
        (
            "p5_official_original_media_reprint",
            [
                _src("a", url="https://gov.cn/xxx", full_text=BODY),
                _src("b", url="https://media.cn/reprint", full_text=BODY),
            ],
            "official original + full media reprint",
        ),
    ]


def _negative_cases() -> list[tuple[str, list[dict], str]]:
    """(name, sources, expected_note) — these must NOT merge into one cluster."""
    summary = "合肥低空经济产业2025年规模达500亿元，同比增长8%。"
    return [
        (
            "n1_summary_report",
            [
                _src("a", url="https://gov.cn/full", full_text=BODY),
                _src("b", url="https://media.cn/summary", full_text=summary),
            ],
            "official original vs summary report (candidate only)",
        ),
        (
            "n2_independent_interview",
            [
                _src("a", url="https://a.com/i1", full_text="专家甲表示，合肥低空经济项目将于2025年投运。"),
                _src("b", url="https://b.com/i2", full_text="记者采访获悉，合肥低空经济项目预计2026年完成建设。"),
            ],
            "two independent interviews of the same event",
        ),
        (
            "n3_page_update_revision",
            [
                _src("a", url="https://gov.cn/project/1", full_text="项目处于招标阶段，计划2025年9月开工。"),
                _src("b", url="https://gov.cn/project/1", full_text="项目已正式投运，2026年1月实现首飞。"),
            ],
            "same URL, page updated (project status changed)",
        ),
        (
            "n4_policy_original_vs_interpretation",
            [
                _src("a", url="https://gov.cn/policy", full_text="为促进低空经济高质量发展，合肥市出台若干支持政策，重点支持eVTOL研发制造与场景应用。"),
                _src("b", url="https://analysis.cn/comment", full_text="分析人士认为，合肥市低空经济新政释放积极信号，将带动上游零部件与基础设施投资增长。"),
            ],
            "policy original vs editorial interpretation",
        ),
        (
            "n5_same_number_different_analysis",
            [
                _src("a", url="https://a.com/n1", full_text="A公司2024年低空经济营收2.3亿元，增长35%，业务拓展顺利。"),
                _src("b", url="https://b.com/n2", full_text="A公司2024年低空经济营收2.3亿元，增长35%，但面临成本压力与竞争加剧。"),
            ],
            "same numbers, different analysis",
        ),
    ]


def _merged(out: dict) -> bool:
    return out["shadow_distinct_content_count"] == 1


def main() -> None:
    positive = _positive_cases()
    negative = _negative_cases()

    tp = fn = tn = fp = 0
    rows: list[dict] = []
    for name, srcs, note in positive:
        out = cluster_sources(srcs)
        merged = _merged(out)
        tp += int(merged)
        fn += int(not merged)
        rows.append({
            "case": name, "kind": "positive", "expected": "merge", "note": note,
            "merged": merged, "distinct": out["shadow_distinct_content_count"],
            "clusters": out["clusters"], "candidates": out["candidates"],
        })
    for name, srcs, note in negative:
        out = cluster_sources(srcs)
        merged = _merged(out)
        tn += int(not merged)
        fp += int(merged)
        rows.append({
            "case": name, "kind": "negative", "expected": "no_merge", "note": note,
            "merged": merged, "distinct": out["shadow_distinct_content_count"],
            "clusters": out["clusters"], "candidates": out["candidates"],
        })

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    false_merge_rate = fp / (fp + tn) if (fp + tn) else 0.0

    # per-slot demo: a hypothetical project slot backed by p2's two duplicates
    cluster_output = cluster_sources(
        [s for _, srcs, _ in positive if _ in ("p1_same_url_diff_utm", "p2_diff_domain_same_body") for s in srcs]
    )
    slot_rows = slot_source_counts({"project.operation_status": ["a", "b"]}, cluster_output)

    report = {
        "clustering_version": "source_cluster_v1",
        "mode": "shadow",
        "summary": {
            "positive_cases": len(positive),
            "negative_cases": len(negative),
            "true_positive": tp,
            "false_positive": fp,
            "true_negative": tn,
            "false_negative": fn,
            "duplicate_precision": round(precision, 4),
            "duplicate_recall": round(recall, 4),
            "false_merge_rate": round(false_merge_rate, 4),
        },
        "scenarios": [
            {
                "case": r["case"], "kind": r["kind"], "expected": r["expected"],
                "note": r["note"], "merged": r["merged"],
                "distinct_content_count": r["distinct"],
                "cluster_reasons": [
                    {
                        "content_cluster_id": c["content_cluster_id"],
                        "source_ids": c["source_ids"],
                        "duplicate_confidence": c["duplicate_confidence"],
                        "duplicate_reason": c["duplicate_reason"],
                    } for c in r["clusters"]
                ],
                "candidates": [
                    {
                        "source_id": c["source_id"],
                        "representative_source_id": c["representative_source_id"],
                        "duplicate_confidence": c["duplicate_confidence"],
                    } for c in r["candidates"]
                ],
            }
            for r in rows
        ],
        "slot_counts": slot_rows,
    }

    out_dir = Path(__file__).resolve().parents[1] / "data" / "tmp" / "source_cluster_shadow_audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"\n[DONE] report -> {out_dir / 'audit.json'}")


if __name__ == "__main__":
    main()
