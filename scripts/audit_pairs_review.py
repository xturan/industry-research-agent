# ruff: noqa: E501
"""Generate the A2.5 manual-review audit list (md + csv).

Collects recorded checkpoint DBs across several historical run dirs (no
re-networking), runs the deterministic shadow clusterer, and emits every
decision-relevant source pair:

- auto_merge      : members of the same multi-member cluster (vs representative)
- candidate       : medium-similarity candidate (not merged)
- revision        : same canonical URL with different content
- near_threshold  : content_similarity in [0.72, 0.92) that was NOT merged /
                    candidate / revision (likely related-but-independent)

Each pair is enriched with: titles/URLs/families/publish dates, algorithm
decision, total similarity + sub-scores, duplicate_reason, critical-fact
conflict detail, body openings, A/B-unique paragraphs, and number/date/status/
subject differences.

Human labels (fixed vocabulary): exact_duplicate / full_reprint /
near_duplicate_rewrite / summary_or_excerpt / same_event_independent_reporting /
revision_or_status_update / related_but_independent / uncertain.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from pathlib import Path

from packages.research_harness.source_cluster import (
    _critical_fact_conflict,
    _extract_money,
    _extract_status_words,
    _extract_years,
    _simhash,
    canonicalize_url,
    cluster_sources,
    content_fingerprint,
    content_similarity_from_hashes,
    date_overlap,
    number_overlap,
    title_similarity,
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s or ""))


def _longest_common_substring(a: str, b: str, max_len: int = 220) -> str:
    """Longest common contiguous substring of two normalized contents."""
    from difflib import SequenceMatcher
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return ""
    match = SequenceMatcher(None, na, nb, autojunk=False).find_longest_match(
        0, len(na), 0, len(nb)
    )
    return na[match.a:match.a + match.size][:max_len]


def _money_strings(text: str) -> list[str]:
    out = []
    for value, unit in _extract_money(text):
        rendered = f"{value:g}{unit}" if float(value).is_integer() else f"{value}{unit}"
        out.append(rendered)
    return out


def _conflict_detail(a: str, b: str) -> dict | None:
    """Like _critical_fact_conflict but returns the SPECIFIC trigger values."""
    status_a, status_b = _extract_status_words(a), _extract_status_words(b)
    if status_a and status_b and status_a != status_b:
        return {
            "conflict_type": "status",
            "a_values": sorted(status_a), "b_values": sorted(status_b),
            "matched_values": sorted(status_a & status_b),
            "unmatched_values": sorted(status_a ^ status_b),
        }
    money_a, money_b = _money_strings(a), _money_strings(b)
    set_a, set_b = set(money_a), set(money_b)
    if money_a and money_b:
        # per-unit near-match check (reuse money signature semantics)
        from packages.research_harness.source_cluster import _money_conflict
        if _money_conflict(a, b):
            return {
                "conflict_type": "amount",
                "a_values": money_a, "b_values": money_b,
                "matched_values": sorted(set_a & set_b),
                "unmatched_values": sorted(set_a ^ set_b),
            }
    years_a, years_b = _extract_years(a), _extract_years(b)
    if (years_a or years_b) and years_a != years_b and (status_a or status_b):
        return {
            "conflict_type": "year",
            "a_values": sorted(years_a), "b_values": sorted(years_b),
            "matched_values": sorted(years_a & years_b),
            "unmatched_values": sorted(years_a ^ years_b),
        }
    return None

REPO = Path(__file__).resolve().parents[1]
HUMAN_LABELS = [
    "exact_duplicate", "full_reprint", "near_duplicate_rewrite",
    "summary_or_excerpt", "same_event_independent_reporting",
    "revision_or_status_update", "related_but_independent", "uncertain",
]
NEAR_THRESHOLD_LO = 0.72
NEAR_THRESHOLD_HI = 0.92
SUBJECT_RE = re.compile(r"[\u4e00-\u9fa5A-Za-z0-9]{2,24}(?:公司|集团|股份|局|厅|委|政府|县政府|区政府|市政府|研究院|大学|银行|证券|航空|科技|股份有限)")


def _load_sources(db_path: Path) -> list[dict]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    sources = []
    seen: set[str] = set()
    for r in cur.execute("SELECT * FROM research_graph_sources").fetchall():
        payload = json.loads(r["payload_json"] or "{}")
        sid = str(r["source_id"])
        # Dedup duplicate source rows (same source_id can appear once per search
        # phrase; these are the SAME source and must not create self-pairs).
        if sid in seen:
            continue
        seen.add(sid)
        sources.append({
            "source_id": sid,
            "url": r["url"] or "",
            "title": r["title"] or "",
            "source_family": r["source_family"] or "",
            "source_tier": r["source_tier"] or "",
            "published_date": r["published_date"] or None,
            "full_text": payload.get("full_text") or payload.get("raw_text") or "",
        })
    con.close()
    return sources


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", str(text or "")) if p.strip()]


def _unique_paragraphs(a: str, b: str) -> tuple[list[str], list[str]]:
    pa = {_norm(p) for p in _paragraphs(a)}
    pb = {_norm(p) for p in _paragraphs(b)}
    a_only = [p for p in _paragraphs(a) if _norm(p) not in pb]
    b_only = [p for p in _paragraphs(b) if _norm(p) not in pa]
    return a_only[:3], b_only[:3]


def _subjects(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0) for m in SUBJECT_RE.finditer(str(text or ""))))


def _opening(text: str, n: int = 120) -> str:
    return " ".join(str(text or "").split())[:n]


def _extract_pairs(sources: list[dict], case: str = "") -> list[dict]:
    """Generate all decision-relevant pairs for one case."""
    cluster_output = cluster_sources(sources)
    by_id = {s["source_id"]: s for s in sources}
    simhash_cache = {s["source_id"]: _simhash(s["full_text"]) for s in sources if s["full_text"]}
    decision_by_pair: dict[tuple[str, str], str] = {}

    pairs: list[dict] = []

    # auto_merge: within multi-member clusters
    for c in cluster_output["clusters"]:
        if len(c["source_ids"]) <= 1:
            continue
        rep = c["cluster_representative_source_id"]
        for sid in c["source_ids"]:
            if sid == rep:
                continue
            key = tuple(sorted([rep, sid]))
            decision_by_pair[key] = "auto_merge"
            pairs.append((rep, sid, "auto_merge", c.get("duplicate_reason", [])))

    # candidate: source vs representative
    for cand in cluster_output["candidates"]:
        key = tuple(sorted([cand["source_id"], cand["representative_source_id"]]))
        decision_by_pair[key] = "candidate"
        pairs.append((cand["source_id"], cand["representative_source_id"], "candidate", cand.get("duplicate_reason", [])))

    # revision: same canonical URL AND DIFFERENT content (status/amount/year update).
    # Same URL with identical content is an exact duplicate, not a revision.
    by_url: dict[str, list[dict]] = {}
    for s in sources:
        cu = canonicalize_url(s.get("url") or "")
        if cu:
            by_url.setdefault(cu, []).append(s)
    for members in by_url.values():
        if len(members) <= 1:
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                key = tuple(sorted([members[i]["source_id"], members[j]["source_id"]]))
                if key in decision_by_pair:
                    continue
                a_fp = content_fingerprint(members[i].get("full_text") or "")
                b_fp = content_fingerprint(members[j].get("full_text") or "")
                if a_fp and b_fp and a_fp != b_fp:
                    decision_by_pair[key] = "revision"
                    pairs.append(
                        (members[i]["source_id"], members[j]["source_id"],
                         "revision", ["same_url_different_content"])
                    )

    # near_threshold: sim in [0.72, 0.92), not already decided
    ids = [s["source_id"] for s in sources if s["full_text"]]
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            key = tuple(sorted([ids[i], ids[j]]))
            if key in decision_by_pair:
                continue
            fa = simhash_cache.get(ids[i])
            fb = simhash_cache.get(ids[j])
            if fa is None or fb is None:
                continue
            cs = content_similarity_from_hashes(fa, fb)
            if NEAR_THRESHOLD_LO <= cs < NEAR_THRESHOLD_HI:
                decision_by_pair[key] = "near_threshold"
                pairs.append((ids[i], ids[j], "near_threshold", ["below_auto_merge_threshold"]))

    # hard_negative: low-similarity related pairs (summary/same-event/policy-vs-
    # interpretation) sharing numbers/entities/dates but NOT near-duplicates.
    # Capped per case so the pool stays labelable.
    hard_candidates = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            key = tuple(sorted([ids[i], ids[j]]))
            if key in decision_by_pair:
                continue
            fa = simhash_cache.get(ids[i])
            fb = simhash_cache.get(ids[j])
            if fa is None or fb is None:
                continue
            sim = content_similarity_from_hashes(fa, fb)
            if not (0.40 <= sim < NEAR_THRESHOLD_LO):
                continue
            a_text = by_id[ids[i]]["full_text"]
            b_text = by_id[ids[j]]["full_text"]
            no = number_overlap(a_text, b_text)
            subj_a, subj_b = _subjects(a_text), _subjects(b_text)
            entity_overlap = len(set(subj_a) & set(subj_b)) > 0
            if no >= 0.3 or entity_overlap:
                hard_candidates.append((sim, ids[i], ids[j]))
    hard_candidates.sort(reverse=True)
    for _, a_id, b_id in hard_candidates[:8]:  # cap hard negatives per case
        key = tuple(sorted([a_id, b_id]))
        decision_by_pair[key] = "hard_negative"
        pairs.append((a_id, b_id, "hard_negative", ["related_low_similarity"]))

    # enrich
    enriched = []
    for a_id, b_id, decision, reasons in pairs:
        a, b = by_id[a_id], by_id[b_id]
        fa, fb = simhash_cache.get(a_id), simhash_cache.get(b_id)
        cs = content_similarity_from_hashes(fa, fb) if (fa is not None and fb is not None) else 0.0
        a_text, b_text = a["full_text"], b["full_text"]
        conflict = bool(_critical_fact_conflict(a_text, b_text)) if a_text and b_text else False
        a_only, b_only = _unique_paragraphs(a_text, b_text)
        numbers_a = [m.group(0) for m in re.finditer(r"\d+(?:\.\d+)?(?:亿|万|%|％|万元|亿元)?", _norm(a_text))]
        numbers_b = [m.group(0) for m in re.finditer(r"\d+(?:\.\d+)?(?:亿|万|%|％|万元|亿元)?", _norm(b_text))]
        set_a, set_b = set(numbers_a), set(numbers_b)
        status_a, status_b = sorted(_extract_status_words(a_text)), sorted(_extract_status_words(b_text))
        money_a, money_b = _extract_money(a_text), _extract_money(b_text)
        years_a, years_b = sorted(_extract_years(a_text)), sorted(_extract_years(b_text))
        subj_a, subj_b = _subjects(a_text), _subjects(b_text)

        enriched.append({
            "pair_id": f"{case}__{a_id}__{b_id}",
            "case": case,
            "decision": decision,
            "human_label": "",
            "human_confidence": "",
            "review_notes": "",
            "longest_common_substring": "",
            "conflict_detail": _conflict_detail(a_text, b_text) if conflict else None,
            "source_a": {
                "source_id": a_id, "title": a["title"], "url": a["url"],
                "family": a["source_family"], "tier": a["source_tier"],
                "published_date": a["published_date"], "opening": _opening(a_text),
                "full_text": a_text,
            },
            "source_b": {
                "source_id": b_id, "title": b["title"], "url": b["url"],
                "family": b["source_family"], "tier": b["source_tier"],
                "published_date": b["published_date"], "opening": _opening(b_text),
                "full_text": b_text,
            },
            "algorithm": {
                "decision": decision,
                "content_similarity": round(cs, 3),
                "title_similarity": round(title_similarity(a["title"], b["title"]), 3),
                "number_overlap": round(number_overlap(a_text, b_text), 3),
                "date_overlap": round(date_overlap(a_text, b_text), 3),
                "duplicate_reason": reasons,
                "critical_fact_conflict": conflict,
            },
            "differences": {
                "numbers_a_only": sorted(set_a - set_b)[:8],
                "numbers_b_only": sorted(set_b - set_a)[:8],
                "money": {"a": money_a, "b": money_b},
                "years": {"a": years_a, "b": years_b},
                "status_words": {"a": status_a, "b": status_b},
                "subjects": {"a": subj_a, "b": subj_b},
            },
            "paragraphs": {
                "a_only": a_only, "b_only": b_only,
            },
        })
    return enriched


def _base_id(stem: str) -> str:
    """'P04_final_v2'/'P04_v2' -> 'P04'; 'case1' -> 'case1'."""
    s = re.sub(r"_final(?:_v\d+)?$", "", stem)
    s = re.sub(r"_v\d+$", "", s)
    return s


def _collect_cases(root: Path) -> dict[str, dict]:
    """Scan all historical checkpoint DBs under root.

    Dedup by base query id, keeping the run with the MOST sources (most
    complete) so repeated reruns (P04_final_v2, etc.) do not inflate pairs.
    """
    cases: dict[str, dict] = {}
    for db in sorted(root.rglob("*.db")):
        try:
            sources = _load_sources(db)
        except Exception:
            continue
        if len(sources) < 3:
            continue
        base = _base_id(db.stem)
        current = cases.get(base)
        if current is None or len(sources) > len(current["sources"]):
            cases[base] = {"db": db, "sources": sources}
    return cases


def _write_review(pairs: list[dict], out_dir: Path) -> None:
    lines = [
        "# A2.5 Source-Clustering Manual Audit List",
        "",
        f"- generated: 2026-08-04 | total pairs: {len(pairs)}",
        "- human labels (fixed vocabulary): " + ", ".join(HUMAN_LABELS),
        "- decisions: auto_merge / candidate / revision / near_threshold",
        "",
        "## Stratified count",
        "",
        "| decision | count |",
        "|---|---|",
    ]
    from collections import Counter
    counter = Counter(p["decision"] for p in pairs)
    for decision, count in sorted(counter.items()):
        lines.append(f"| {decision} | {count} |")
    lines.append("")

    for p in pairs:
        lines.append("---")
        lines.append("")
        lines.append(f"## {p['pair_id']}  `{p['decision']}`")
        lines.append(f"- **人工标签**: `{p['human_label'] or '_未标_'}`")
        lines.append("")
        lines.append(f"### A: `{p['source_a']['source_id']}`  {p['source_a']['title']}")
        lines.append(f"- URL: {p['source_a']['url']} | family: {p['source_a']['family']} | tier: {p['source_a']['tier']} | published: {p['source_a']['published_date']}")
        lines.append(f"- 正文开头: {p['source_a']['opening']}")
        lines.append("")
        lines.append(f"### B: `{p['source_b']['source_id']}`  {p['source_b']['title']}")
        lines.append(f"- URL: {p['source_b']['url']} | family: {p['source_b']['family']} | tier: {p['source_b']['tier']} | published: {p['source_b']['published_date']}")
        lines.append(f"- 正文开头: {p['source_b']['opening']}")
        lines.append("")
        alg = p["algorithm"]
        lines.append(f"### algorithm: decision=`{alg['decision']}` conflict=`{alg['critical_fact_conflict']}`")
        lines.append(f"- content_similarity={alg['content_similarity']} title_similarity={alg['title_similarity']} "
                     f"number_overlap={alg['number_overlap']} date_overlap={alg['date_overlap']}")
        lines.append(f"- duplicate_reason: {alg['duplicate_reason']}")
        lines.append("")
        diff = p["differences"]
        lines.append("### 差异")
        lines.append(f"- 数字 A-only: {diff['numbers_a_only']}")
        lines.append(f"- 数字 B-only: {diff['numbers_b_only']}")
        lines.append(f"- 金额: A={diff['money']['a']} B={diff['money']['b']}")
        lines.append(f"- 年份: A={diff['years']['a']} B={diff['years']['b']}")
        lines.append(f"- 状态词: A={diff['status_words']['a']} B={diff['status_words']['b']}")
        lines.append(f"- 主体: A={diff['subjects']['a']} B={diff['subjects']['b']}")
        lines.append("")
        lines.append("### 独有段落")
        lines.append(f"- A-only: {p['paragraphs']['a_only']}")
        lines.append(f"- B-only: {p['paragraphs']['b_only']}")
        lines.append("")

    (out_dir / "audit_pairs_review.md").write_text("\n".join(lines), encoding="utf-8")

    with (out_dir / "audit_pairs_review.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "pair_id", "decision", "human_label", "a_source_id", "a_title", "a_url", "a_family", "a_published",
            "b_source_id", "b_title", "b_url", "b_family", "b_published",
            "content_similarity", "title_similarity", "number_overlap", "date_overlap",
            "duplicate_reason", "critical_fact_conflict",
            "numbers_a_only", "numbers_b_only", "money_a", "money_b", "years_a", "years_b",
            "status_a", "status_b", "subjects_a", "subjects_b", "a_only_paras", "b_only_paras",
        ])
        for p in pairs:
            writer.writerow([
                p["pair_id"], p["decision"], p["human_label"],
                p["source_a"]["source_id"], p["source_a"]["title"], p["source_a"]["url"],
                p["source_a"]["family"], p["source_a"]["published_date"],
                p["source_b"]["source_id"], p["source_b"]["title"], p["source_b"]["url"],
                p["source_b"]["family"], p["source_b"]["published_date"],
                p["algorithm"]["content_similarity"], p["algorithm"]["title_similarity"],
                p["algorithm"]["number_overlap"], p["algorithm"]["date_overlap"],
                "|".join(p["algorithm"]["duplicate_reason"]), p["algorithm"]["critical_fact_conflict"],
                "|".join(p["differences"]["numbers_a_only"]), "|".join(p["differences"]["numbers_b_only"]),
                json.dumps(p["differences"]["money"], ensure_ascii=False), json.dumps(p["differences"]["money"]["b"], ensure_ascii=False),
                "|".join(p["differences"]["years"]["a"]), "|".join(p["differences"]["years"]["b"]),
                "|".join(p["differences"]["status_words"]["a"]), "|".join(p["differences"]["status_words"]["b"]),
                "|".join(p["differences"]["subjects"]["a"]), "|".join(p["differences"]["subjects"]["b"]),
                json.dumps(p["paragraphs"]["a_only"], ensure_ascii=False), json.dumps(p["paragraphs"]["b_only"], ensure_ascii=False),
            ])


def _algorithm_suggestion(p: dict) -> dict:
    """Algorithmic suggestion WITHOUT forcing a human verdict.

    Candidates/near-threshold default to manual_review/uncertain (do not force
    independent-reporting); auto_merge/revision get cautious suggestions gated
    by confidence. Used only in the algorithm CSV, never the blind CSV.
    """
    decision = p["decision"]
    sim = p["algorithm"]["content_similarity"]
    conflict = p["algorithm"]["critical_fact_conflict"]
    reason = "|".join(p["algorithm"]["duplicate_reason"])
    if decision == "auto_merge" and not conflict and sim >= 0.9:
        return {
            "algorithm_suggested_label": "full_reprint",
            "algorithm_suggestion_confidence": round(sim, 3),
            "algorithm_suggestion_reason": f"auto_merge high body sim {sim}, no conflict ({reason})",
        }
    if decision == "revision":
        return {
            "algorithm_suggested_label": "revision_or_status_update",
            "algorithm_suggestion_confidence": 0.8,
            "algorithm_suggestion_reason": "same canonical URL with different content",
        }
    # candidate / near_threshold / conflict-broken merges -> manual review
    return {
        "algorithm_suggested_label": "uncertain",
        "algorithm_suggestion_confidence": round(min(0.5, sim), 3),
        "algorithm_suggestion_reason": f"manual_review ({decision}, sim {sim})",
    }


def _select_priority(pairs: list[dict], *, random_seed: int = 20260804) -> dict:
    """Stratified first-round review selection (~60 pairs).

    - all auto_merge (3)
    - all revision (24)
    - top 15 candidates by content_similarity (descending)
    - 10 pairs closest to candidate_threshold 0.78, not already selected
      (near-threshold: just above/below)
    - 8 random candidates, fixed seed (not already selected)
    """
    import random
    rng = random.Random(random_seed)

    by_decision = {d: [] for d in ("auto_merge", "candidate", "revision", "near_threshold", "hard_negative")}
    for p in pairs:
        by_decision.setdefault(p["decision"], []).append(p)

    auto_merge = list(by_decision.get("auto_merge", []))
    revision = list(by_decision.get("revision", []))
    candidates = list(by_decision.get("candidate", []))
    near_threshold = list(by_decision.get("near_threshold", []))

    selected: list[dict] = []
    selected_ids: set[str] = set()

    def _add(p: dict) -> None:
        if p["pair_id"] not in selected_ids:
            selected.append(p)
            selected_ids.add(p["pair_id"])

    # 1) all auto_merge
    for p in auto_merge:
        _add(p)
    # 2) all revision
    for p in revision:
        _add(p)
    # 3) top-15 candidates by content_similarity
    top_candidates = sorted(candidates, key=lambda p: -p["algorithm"]["content_similarity"])[:15]
    for p in top_candidates:
        _add(p)
    # 4) 10 closest to 0.78, split 5 just-above (lowest candidates) + 5 just-below
    #    (highest near_threshold), not already selected
    rest_candidates = sorted(
        [p for p in candidates if p["pair_id"] not in selected_ids],
        key=lambda p: p["algorithm"]["content_similarity"],
    )
    rest_near = sorted(
        [p for p in near_threshold if p["pair_id"] not in selected_ids],
        key=lambda p: -p["algorithm"]["content_similarity"],
    )
    for p in rest_candidates[:5]:
        _add(p)
    for p in rest_near[:5]:
        _add(p)
    # 5) 8 random candidates, fixed seed
    pool = [p for p in candidates if p["pair_id"] not in selected_ids]
    rng.shuffle(pool)
    for p in pool[:8]:
        _add(p)

    return {
        "selected": selected,
        "counts": {
            "auto_merge_all": len(auto_merge),
            "revision_all": len(revision),
            "top_candidate": len(top_candidates),
            "near_threshold": 10,
            "random_candidate": 8,
        },
    }


def _write_priority_review(selected: list[dict], counts: dict, out_dir: Path, *, random_seed: int) -> None:
    lines = [
        "# A2.5 高风险首轮审查包 (Priority Review)",
        "",
        f"- total selected: {len(selected)} | pool: 218 | random_seed: {random_seed}",
        "- selection: " + ", ".join(f"{k}={v}" for k, v in counts.items()),
        "- human labels: exact_duplicate / full_reprint / near_duplicate_rewrite / summary_or_excerpt / "
        "same_event_independent_reporting / revision_or_status_update / related_but_independent / uncertain",
        "",
    ]
    from collections import Counter
    counter = Counter(p["decision"] for p in selected)
    lines.append("## Selected by decision")
    lines.append("")
    for decision, count in sorted(counter.items()):
        lines.append(f"- {decision}: {count}")
    lines.append("")

    for idx, p in enumerate(selected, 1):
        lines.append("---")
        lines.append("")
        lines.append(f"## Pair {idx} · `{p['pair_id']}` · Decision=`{p['decision']}` · case={p.get('case')}")
        alg = p["algorithm"]
        lines.append(f"- **算法**: content_sim={alg['content_similarity']} title_sim={alg['title_similarity']} "
                     f"number_overlap={alg['number_overlap']} date_overlap={alg['date_overlap']} "
                     f"conflict={alg['critical_fact_conflict']} reason={alg['duplicate_reason']}")
        cd = p.get("conflict_detail")
        if cd:
            lines.append(f"- **冲突详情**: type={cd['conflict_type']} a={cd['a_values']} b={cd['b_values']} "
                         f"matched={cd['matched_values']} unmatched={cd['unmatched_values']}")
        lines.append("")
        lines.append(f"### A: `{p['source_a']['source_id']}`  {p['source_a']['title']}")
        lines.append(f"- URL: {p['source_a']['url']} | family={p['source_a']['family']} | tier={p['source_a']['tier']} | published={p['source_a']['published_date']}")
        lines.append(f"- 正文开头: {p['source_a']['opening']}")
        lines.append("")
        lines.append(f"### B: `{p['source_b']['source_id']}`  {p['source_b']['title']}")
        lines.append(f"- URL: {p['source_b']['url']} | family={p['source_b']['family']} | tier={p['source_b']['tier']} | published={p['source_b']['published_date']}")
        lines.append(f"- 正文开头: {p['source_b']['opening']}")
        lines.append("")
        lines.append("### 共同内容")
        lcs = p.get("longest_common_substring", "")
        lines.append(f"- 最长共同连续片段: {lcs[:180] + ('…' if len(lcs) > 180 else '')}")
        lines.append("")
        lines.append("### 差异内容")
        diff = p["differences"]
        lines.append(f"- 数字 A-only: {diff['numbers_a_only']}")
        lines.append(f"- 数字 B-only: {diff['numbers_b_only']}")
        lines.append(f"- 金额: A={diff['money']['a']} B={diff['money']['b']}")
        lines.append(f"- 年份: A={diff['years']['a']} B={diff['years']['b']}")
        lines.append(f"- 状态词: A={diff['status_words']['a']} B={diff['status_words']['b']}")
        lines.append(f"- 主体: A={diff['subjects']['a']} B={diff['subjects']['b']}")
        lines.append(f"- A-only 段落: {p['paragraphs']['a_only']}")
        lines.append(f"- B-only 段落: {p['paragraphs']['b_only']}")
        lines.append("")
        lines.append("### 人工标签")
        lines.append(f"- human_label: {p['human_label'] or '_待标_'}")
        lines.append(f"- human_confidence: {p['human_confidence'] or ''}")
        lines.append(f"- review_notes: {p['review_notes'] or ''}")
        lines.append("")

    (out_dir / "audit_priority_review.md").write_text("\n".join(lines), encoding="utf-8")

    with (out_dir / "audit_priority_review.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "pair_id", "case", "decision", "human_label", "human_confidence", "review_notes",
            "a_source_id", "a_title", "a_url", "a_family", "a_tier", "a_published",
            "b_source_id", "b_title", "b_url", "b_family", "b_tier", "b_published",
            "content_similarity", "title_similarity", "number_overlap", "date_overlap",
            "duplicate_reason", "critical_fact_conflict", "conflict_type",
            "longest_common_substring", "numbers_a_only", "numbers_b_only",
            "money_a", "money_b", "years_a", "years_b", "status_a", "status_b",
            "subjects_a", "subjects_b", "a_only_paras", "b_only_paras",
        ])
        for p in selected:
            cd = p.get("conflict_detail") or {}
            writer.writerow([
                p["pair_id"], p.get("case"), p["decision"], p["human_label"], p["human_confidence"], p["review_notes"],
                p["source_a"]["source_id"], p["source_a"]["title"], p["source_a"]["url"],
                p["source_a"]["family"], p["source_a"]["tier"], p["source_a"]["published_date"],
                p["source_b"]["source_id"], p["source_b"]["title"], p["source_b"]["url"],
                p["source_b"]["family"], p["source_b"]["tier"], p["source_b"]["published_date"],
                p["algorithm"]["content_similarity"], p["algorithm"]["title_similarity"],
                p["algorithm"]["number_overlap"], p["algorithm"]["date_overlap"],
                "|".join(p["algorithm"]["duplicate_reason"]), p["algorithm"]["critical_fact_conflict"], cd.get("conflict_type", ""),
                p.get("longest_common_substring", ""),
                "|".join(p["differences"]["numbers_a_only"]), "|".join(p["differences"]["numbers_b_only"]),
                json.dumps(p["differences"]["money"]["a"], ensure_ascii=False), json.dumps(p["differences"]["money"]["b"], ensure_ascii=False),
                "|".join(p["differences"]["years"]["a"]), "|".join(p["differences"]["years"]["b"]),
                "|".join(p["differences"]["status_words"]["a"]), "|".join(p["differences"]["status_words"]["b"]),
                "|".join(p["differences"]["subjects"]["a"]), "|".join(p["differences"]["subjects"]["b"]),
                json.dumps(p["paragraphs"]["a_only"], ensure_ascii=False), json.dumps(p["paragraphs"]["b_only"], ensure_ascii=False),
            ])


def _write_blind_and_algorithm_csv(selected: list[dict], out_dir: Path, *, prefix: str = "audit_priority_review") -> None:
    """Blind CSV (no algorithm) + algorithm CSV (by pair_id), for unbiased review."""
    # Blind CSV: pair content/metadata/common/unique/fact diffs, human fields blank.
    blind_path = out_dir / f"{prefix}_blind.csv"
    alg_path = out_dir / f"{prefix}_algorithm.csv"
    blind_header = [
        "pair_id", "case", "a_source_id", "a_title", "a_url", "a_family", "a_tier", "a_published", "a_opening",
        "b_source_id", "b_title", "b_url", "b_family", "b_tier", "b_published", "b_opening",
        "longest_common_substring", "numbers_a_only", "numbers_b_only",
        "money_a", "money_b", "years_a", "years_b", "status_a", "status_b", "subjects_a", "subjects_b",
        "a_only_paras", "b_only_paras", "human_label", "human_confidence", "review_notes",
    ]
    with blind_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(blind_header)
        for p in selected:
            d = p["differences"]
            writer.writerow([
                p["pair_id"], p.get("case"),
                p["source_a"]["source_id"], p["source_a"]["title"], p["source_a"]["url"],
                p["source_a"]["family"], p["source_a"]["tier"], p["source_a"]["published_date"], p["source_a"]["opening"],
                p["source_b"]["source_id"], p["source_b"]["title"], p["source_b"]["url"],
                p["source_b"]["family"], p["source_b"]["tier"], p["source_b"]["published_date"], p["source_b"]["opening"],
                p.get("longest_common_substring", ""),
                "|".join(d["numbers_a_only"]), "|".join(d["numbers_b_only"]),
                json.dumps(d["money"]["a"], ensure_ascii=False), json.dumps(d["money"]["b"], ensure_ascii=False),
                "|".join(d["years"]["a"]), "|".join(d["years"]["b"]),
                "|".join(d["status_words"]["a"]), "|".join(d["status_words"]["b"]),
                "|".join(d["subjects"]["a"]), "|".join(d["subjects"]["b"]),
                json.dumps(p["paragraphs"]["a_only"], ensure_ascii=False),
                json.dumps(p["paragraphs"]["b_only"], ensure_ascii=False),
                "", "", "",
            ])

    # Algorithm CSV: linked by pair_id, no content.
    alg_header = [
        "pair_id", "algorithm_decision", "algorithm_suggested_label",
        "algorithm_suggestion_confidence", "algorithm_suggestion_reason",
        "content_similarity", "title_similarity", "number_overlap", "date_overlap",
        "duplicate_reason", "critical_fact_conflict", "conflict_type",
    ]
    with alg_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(alg_header)
        for p in selected:
            alg = p["algorithm"]
            sugg = _algorithm_suggestion(p)
            cd = p.get("conflict_detail") or {}
            writer.writerow([
                p["pair_id"], p["decision"], sugg["algorithm_suggested_label"],
                sugg["algorithm_suggestion_confidence"], sugg["algorithm_suggestion_reason"],
                alg["content_similarity"], alg["title_similarity"], alg["number_overlap"], alg["date_overlap"],
                "|".join(alg["duplicate_reason"]), alg["critical_fact_conflict"], cd.get("conflict_type", ""),
            ])


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate A2.5 manual audit list (md + csv)")
    ap.add_argument("--run-dir", default="data/tmp")
    ap.add_argument("--output-dir", default="data/tmp/shadow_difference_report")
    ap.add_argument("--random-seed", type=int, default=20260804)
    args = ap.parse_args()

    cases = _collect_cases(REPO / args.run_dir)
    print(f"[INFO] collected {len(cases)} cases: {sorted(cases.keys())}")

    all_pairs: list[dict] = []
    for qid, case in sorted(cases.items()):
        pairs = _extract_pairs(case["sources"], case=qid)
        all_pairs.extend(pairs)
        print(f"[OK] {qid}: {len(pairs)} pairs")

    from collections import Counter
    counter = Counter(p["decision"] for p in all_pairs)
    print(f"[DONE] total pairs={len(all_pairs)} | {dict(counter)}")

    out_dir = REPO / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    # Full pool (keep, do not overwrite semantics): write all pairs
    _write_review(all_pairs, out_dir)
    (out_dir / "audit_pairs_all.json").write_text(
        json.dumps(all_pairs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Clean Pool v2: full-pool blind + algorithm CSVs for labeling
    _write_blind_and_algorithm_csv(all_pairs, out_dir, prefix="clean_pool_v2")

    # Priority first-round review package
    selection = _select_priority(all_pairs, random_seed=args.random_seed)
    selected = selection["selected"]
    # Longest-common-substring is expensive: compute only for the selected ~60
    for p in selected:
        if not p.get("longest_common_substring"):
            p["longest_common_substring"] = _longest_common_substring(
                p["source_a"].get("full_text", ""), p["source_b"].get("full_text", "")
            )
    _write_priority_review(selected, selection["counts"], out_dir, random_seed=args.random_seed)
    _write_blind_and_algorithm_csv(selected, out_dir)
    manifest = {
        "clustering_version": "source_cluster_v1",
        "auto_merge_threshold": 0.90,
        "candidate_threshold": 0.78,
        "source_pair_pool_size": len(all_pairs),
        "selected_pair_count": len(selected),
        "selection": selection["counts"],
        "random_seed": args.random_seed,
    }
    (out_dir / "audit_priority_review_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[DONE] audit_pairs_review.* + audit_priority_review.* -> {out_dir}")


if __name__ == "__main__":
    main()
