# ruff: noqa: E501
"""Clean Pool v2 — stratified sampling + revision benchmark fixtures.

Samples ~180-220 pairs from the 733-pair v2 pool for human labeling:
- all auto_merge (3) + all near_threshold (33)
- candidate (~78) stratified by similarity tertile (high/medium/low)
- hard_negative (~78) stratified, plus guaranteed policy-vs-interpretation and
  announcement-vs-analysis subsets

Also emits a REVISION BENCHMARK of 20 deterministic fixtures (same URL, content
status/amount/year update), labeled revision_or_status_update. Real samples and
deterministic fixtures are reported SEPARATELY in downstream evaluation.

Group split (Calibration/Validation) is applied by task/case downstream.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = 20260804
REVISION_FIXTURES = 20


def _load_pool(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sim(p: dict) -> float:
    return float(p.get("algorithm", {}).get("content_similarity", 0) or 0)


def _stratified(rows: list[dict], n: int, key: str, rng: random.Random) -> list[dict]:
    if not rows:
        return []
    rows = sorted(rows, key=_sim)
    bands = []
    lo = min(_sim(p) for p in rows)
    hi = max(_sim(p) for p in rows)
    for i in range(3):
        b_lo = lo + (hi - lo) * i / 3
        b_hi = lo + (hi - lo) * (i + 1) / 3
        bands.append([p for p in rows if b_lo <= _sim(p) <= b_hi])
    out = []
    per_band = max(1, n // 3)
    for band in bands:
        rng.shuffle(band)
        out.extend(band[:per_band])
    if len(out) < n:
        rng.shuffle(rows)
        out.extend(rows[: n - len(out)])
    return out


def _filter_family(rows: list[dict], fam_a: str, fam_b: str) -> list[dict]:
    def _has(p, fam):
        return p["source_a"]["family"] == fam or p["source_b"]["family"] == fam
    return [p for p in rows if _has(p, fam_a) and _has(p, fam_b)]


def _dedup(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for p in rows:
        if p["pair_id"] not in seen:
            seen.add(p["pair_id"])
            out.append(p)
    return out


def _doc_type_fixtures() -> list[dict]:
    """Deterministic doc-type hard-negative fixtures (policy-vs-interpretation,
    announcement-vs-analysis, same-event independent, summary/excerpt). These
    cover the hard-negative types the historical pool lacks."""
    fixtures = []
    policy_original = "为促进低空经济高质量发展，合肥市出台若干支持政策，重点支持eVTOL研发制造与场景应用，并设立专项基金。"
    policy_interpret = "分析人士认为，合肥市低空经济新政释放积极信号，将带动上游零部件与基础设施投资增长，但短期落地效果仍待观察。"
    announcement = "某某航空公告：公司低空经济相关业务2024年营收2.3亿元，同比增长35%。"
    media_analysis = "分析认为，某某航空低空经济业务增长亮眼，但面临适航认证与成本压力，后续盈利仍存不确定性。"
    ev_a = "专家甲表示，合肥低空经济项目将于2025年投运，产业前景广阔。"
    ev_b = "记者采访获悉，合肥低空经济项目预计2026年完成建设并投入运营。"
    summary = "合肥低空经济项目2025年开工，投资约10亿元。"
    full = "合肥低空经济项目2025年开工，投资约10亿元，预计2026年投运，政策支持持续加码，产业生态不断完善。"

    def _src(sid, url, title, family, text):
        return {"source_id": sid, "url": url, "title": title, "family": family,
                "tier": "B", "published_date": None, "full_text": text}

    specs = [
        ("dt_policy_interpret_1", _src("pa", "https://gov.cn/p1", "政策原文", "official_policy", policy_original),
         _src("pb", "https://analysis.cn/c1", "政策解读", "industry_research", policy_interpret),
         "related_but_independent", "policy original vs interpretation"),
        ("dt_policy_interpret_2", _src("pc", "https://gov.cn/p2", "政策原文", "official_policy", policy_original),
         _src("pd", "https://media.cn/c2", "媒体解读", "commercial_media", policy_interpret),
         "related_but_independent", "policy original vs media commentary"),
        ("dt_announce_analysis_1", _src("qa", "https://cninfo.cn/a1", "公司公告", "company_disclosure", announcement),
         _src("qb", "https://media.cn/a2", "媒体分析", "commercial_media", media_analysis),
         "related_but_independent", "announcement vs media analysis"),
        ("dt_announce_analysis_2", _src("qc", "https://cninfo.cn/a3", "公司公告", "company_disclosure", announcement),
         _src("qd", "https://research.cn/a4", "券商点评", "industry_research", media_analysis),
         "same_event_independent_reporting", "announcement vs research note"),
        ("dt_same_event_1", _src("ra", "https://media.cn/e1", "采访甲", "official_news", ev_a),
         _src("rb", "https://other.cn/e2", "采访乙", "commercial_media", ev_b),
         "same_event_independent_reporting", "same event, independent interviews"),
        ("dt_summary_1", _src("sa", "https://gov.cn/s1", "完整报道", "official_news", full),
         _src("sb", "https://media.cn/s2", "摘要", "commercial_media", summary),
         "summary_or_excerpt", "full report vs short excerpt"),
    ]
    for pid, a, b, label, note in specs:
        fixtures.append({
            "pair_id": pid, "case": "benchmark_doc_type",
            "source_a": a, "source_b": b,
            "human_label": label, "human_confidence": "high", "review_notes": note,
            "decision": "doc_type_fixture", "content_similarity": 0.0,
        })
    return fixtures


def _revision_fixtures(n: int) -> list[dict]:
    """Deterministic revision benchmark: same URL, content updated."""
    base_url = "https://gov.cn/project/1"
    fixtures = []
    scenarios = [
        ("拟建", "正式投运", "拟建阶段", "已正式投运"),
        ("开工", "投运", "2025年开工", "2026年投运"),
        ("试运行", "正式运营", "处于试运行", "正式运营"),
        ("签约", "开工", "已签约", "已开工"),
        ("在建", "完工验收", "在建", "完工验收"),
        ("10亿元", "12亿元", "投资约10亿元", "投资约12亿元"),
        ("2025年", "2026年", "计划2025年投运", "计划2026年投运"),
        ("招标", "中标", "进入招标阶段", "已公示中标结果"),
        ("正常运营", "停运", "正常运营中", "已停运整改"),
        ("立项", "终止", "项目已立项", "项目已终止"),
    ]
    for i in range(n):
        a_state, b_state, a_phrase, b_phrase = scenarios[i % len(scenarios)]
        base = "合肥低空经济产业园一期工程"
        a_text = f"{base}{a_phrase}，总投资10亿元，位于高新区。"
        b_text = f"{base}{b_phrase}，总投资10亿元，位于高新区。"
        # make b actually differ in the key fact
        b_text = b_text.replace(a_phrase, b_phrase)
        fixtures.append({
            "pair_id": f"rev_fixture_{i:02d}",
            "case": "revision_benchmark",
            "source_a": {
                "source_id": f"rv_a_{i}", "url": base_url, "title": f"revision A {i}",
                "family": "public_resource_transaction", "tier": "B",
                "published_date": None, "full_text": a_text,
            },
            "source_b": {
                "source_id": f"rv_b_{i}", "url": base_url, "title": f"revision B {i}",
                "family": "public_resource_transaction", "tier": "B",
                "published_date": None, "full_text": b_text,
            },
            "human_label": "revision_or_status_update",
            "human_confidence": "high",
            "review_notes": f"fixture: {a_state} -> {b_state}",
            "decision": "revision_benchmark_fixture",
            "content_similarity": 0.0,  # computed at eval time
        })
    return fixtures


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="data/tmp/shadow_difference_report_v2/audit_pairs_all.json")
    ap.add_argument("--out-dir", default="data/tmp/shadow_difference_report_v2")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    pool = _load_pool(REPO / args.pool)
    rng = random.Random(args.seed)

    auto = [p for p in pool if p["decision"] == "auto_merge"]
    near = [p for p in pool if p["decision"] == "near_threshold"]
    cand = [p for p in pool if p["decision"] == "candidate"]
    hn = [p for p in pool if p["decision"] == "hard_negative"]

    # policy-vs-interpretation + announcement-vs-analysis guaranteed in hard negatives
    policy_interpret = _filter_family(hn, "official_policy", "industry_research") + \
                       _filter_family(hn, "official_policy", "commercial_media")
    announcement_analysis = _filter_family(hn, "company_disclosure", "commercial_media") + \
                            _filter_family(hn, "company_disclosure", "industry_research")
    hn_rest = [p for p in hn if p not in policy_interpret and p not in announcement_analysis]

    sampled_cand = _stratified(cand, 78, "content_similarity", rng)
    sampled_hn_rest = _stratified(hn_rest, 80, "content_similarity", rng)
    sampled_hn_policy = policy_interpret[:12] if policy_interpret else []
    sampled_hn_ann = announcement_analysis[:6] if announcement_analysis else []
    sampled_hn = _dedup(sampled_hn_rest + sampled_hn_policy + sampled_hn_ann)

    selected_ids = list(dict.fromkeys(
        [p["pair_id"] for p in auto] + [p["pair_id"] for p in near] +
        [p["pair_id"] for p in sampled_cand] + [p["pair_id"] for p in sampled_hn]
    ))
    selected = selected_ids
    selected_pairs = [p for p in pool if p["pair_id"] in selected]
    # ensure no duplicate pair_ids
    assert len({p["pair_id"] for p in selected_pairs}) == len(selected_pairs)

    out_dir = REPO / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # blind CSV (no algorithm) for labeling
    with (out_dir / "clean_pool_v2_sample_blind.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["pair_id", "case", "a_source_id", "a_title", "a_url", "a_family", "a_tier",
                         "a_published", "a_opening", "b_source_id", "b_title", "b_url", "b_family",
                         "b_tier", "b_published", "b_opening", "longest_common_substring",
                         "numbers_a_only", "numbers_b_only", "money_a", "money_b", "years_a", "years_b",
                         "status_a", "status_b", "subjects_a", "subjects_b", "a_only_paras", "b_only_paras",
                         "human_label", "human_confidence", "review_notes"])
        for p in selected_pairs:
            d = p["differences"]
            writer.writerow([p["pair_id"], p["case"],
                             p["source_a"]["source_id"], p["source_a"]["title"], p["source_a"]["url"],
                             p["source_a"]["family"], p["source_a"]["tier"], p["source_a"]["published_date"],
                             p["source_a"]["opening"],
                             p["source_b"]["source_id"], p["source_b"]["title"], p["source_b"]["url"],
                             p["source_b"]["family"], p["source_b"]["tier"], p["source_b"]["published_date"],
                             p["source_b"]["opening"], p.get("longest_common_substring", ""),
                             "|".join(d["numbers_a_only"]), "|".join(d["numbers_b_only"]),
                             json.dumps(d["money"]["a"], ensure_ascii=False), json.dumps(d["money"]["b"], ensure_ascii=False),
                             "|".join(d["years"]["a"]), "|".join(d["years"]["b"]),
                             "|".join(d["status_words"]["a"]), "|".join(d["status_words"]["b"]),
                             "|".join(d["subjects"]["a"]), "|".join(d["subjects"]["b"]),
                             json.dumps(p["paragraphs"]["a_only"], ensure_ascii=False),
                             json.dumps(p["paragraphs"]["b_only"], ensure_ascii=False),
                             "", "", ""])

    # algorithm CSV (linked by pair_id)
    with (out_dir / "clean_pool_v2_sample_algorithm.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["pair_id", "algorithm_decision", "content_similarity", "title_similarity",
                         "number_overlap", "date_overlap", "duplicate_reason", "critical_fact_conflict",
                         "conflict_type", "blocking_reasons"])
        for p in selected_pairs:
            alg = p["algorithm"]
            cd = p.get("conflict_detail") or {}
            writer.writerow([p["pair_id"], p["decision"], alg["content_similarity"], alg["title_similarity"],
                             alg["number_overlap"], alg["date_overlap"], "|".join(alg["duplicate_reason"]),
                             alg["critical_fact_conflict"], cd.get("conflict_type", ""), ""])

    # revision benchmark + doc-type hard-negative fixtures (deterministic, labeled)
    fixtures = _revision_fixtures(REVISION_FIXTURES) + _doc_type_fixtures()
    (out_dir / "clean_pool_v2_benchmark_fixtures.json").write_text(
        json.dumps(fixtures, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manifest = {
        "sampling_method": "stratified",
        "random_seed": args.seed,
        "pool_size": len(pool),
        "selected_count": len(selected_pairs),
        "selection": {
            "auto_merge_all": len(auto),
            "near_threshold_all": len(near),
            "candidate_stratified": len(sampled_cand),
            "hard_negative_total": len(sampled_hn),
            "hard_negative_policy_vs_interpretation": len(sampled_hn_policy),
            "hard_negative_announcement_vs_analysis": len(sampled_hn_ann),
        },
        "revision_benchmark_fixtures": REVISION_FIXTURES,
        "doc_type_fixtures": len(fixtures) - REVISION_FIXTURES,
        "note": "revision + doc-type benchmarks are deterministic fixtures (no real revisions / policy-vs-"
                "interpretation in historical pool); report real-sample metrics and fixture metrics separately",
    }
    (out_dir / "clean_pool_v2_sample_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"[DONE] sample -> {out_dir / 'clean_pool_v2_sample_blind.csv'} (+ algorithm CSV + revision fixtures)")


if __name__ == "__main__":
    main()
