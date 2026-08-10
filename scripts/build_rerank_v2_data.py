"""Build EXPANDED reranker training data: 40 queries + hard negatives + boundary.

Natural chunks (40 train queries x ~30) + cross-topic hard negatives (unrelated
query chunks) -> ~2500-3000 raw rows for DeepSeek bucketed labeling.

Output:
  data/rerank_training/v2_raw_train.jsonl        (natural, query_i <-> own chunk)
  data/rerank_training/v2_crossneg_train.jsonl   (hard negatives, query_i <-> unrelated chunk)
  data/rerank_training/query_split_v2.json       (train 40 / eval 10)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import random
from collections import defaultdict
from pathlib import Path
from time import perf_counter
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from packages.research_harness import retrieval_rank as rr  # noqa: E402
from scripts.compare_search_providers import anysearch_search  # noqa: E402

QUERY_FILE = _REPO / "data" / "evals" / "report_coverage_50_queries_v1.json"
OUT_DIR = _REPO / "data" / "rerank_training"
EVAL_QUERY_IDS = {
    "M08", "M09", "P09", "P10", "P11", "C09", "C10", "C11", "K08", "K09",
}
NATURAL_CHUNKS_PER_QUERY = 30
COARSE_TOP_N = 32
CROSS_NEG_PER_QUERY = 20
ADJACENT_PER_QUERY = 15


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and value:
            os.environ.setdefault(name, value)


def _search_phrases(query: str) -> list[str]:
    q = str(query or "").strip()
    return [q[:60], q[:35], q[:25]]


def _family(url: str, title: str) -> str:
    host = (url.split("/")[2].lower() if "://" in url else "").removeprefix("www.")
    text = f"{title} {url}".lower()
    if host.endswith("gov.cn") or host.endswith("ndrc.gov.cn"):
        if any(t in text for t in ("统计", "tjj", "公报")):
            return "official_statistics"
        if any(t in text for t in ("采购", "招标", "ggzy", "ccgp")):
            return "tender_procurement"
        return "policy_document"
    if any(host.endswith(s) for s in ("cninfo.com.cn", "sse.com.cn", "szse.cn", "bse.cn")):
        return "company_disclosure"
    if any(t in text for t in ("采购", "招标", "ggzy", "ccgp")):
        return "tender_procurement"
    if any(t in text for t in ("日报", "新闻", "news")):
        return "local_official"
    return "industry_research"


def collect_query_chunks(
    query: str, qid: str, level: str, api_key: str, max_results: int, timeout: int
) -> list[dict[str, Any]]:
    """Search multiple phrases -> dedup -> coarse rank -> chunks (keeping lower ranks)."""
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for phrase in _search_phrases(query):
        try:
            results, _meta = anysearch_search(
                phrase, max_results=max_results, api_key=api_key, timeout_seconds=timeout
            )
        except Exception as exc:  # noqa: BLE001
            print(f"    [WARN] {qid} phrase '{phrase[:20]}' failed: {str(exc)[:80]}")
            continue
        for result in results:
            if not result.url or result.url in seen:
                continue
            seen.add(result.url)
            sources.append(
                {
                    "source_id": f"{qid}_src_{len(sources)}",
                    "url": result.url,
                    "title": result.title,
                    "source_family": _family(result.url, result.title),
                    "snippet": result.snippet,
                    "raw_text": result.content or result.snippet,
                    "full_text": result.content or result.snippet,
                }
            )
    if not sources:
        return []
    deduped = rr.dedup_sources(sources)
    coarse = rr.coarse_rank_bm25_vector_rrf(
        deduped, query, _search_phrases(query)[:2], top_n=COARSE_TOP_N
    )
    chunks = rr.chunk_documents(coarse, max_chars=700)
    rows = []
    for chunk in chunks[:NATURAL_CHUNKS_PER_QUERY]:
        rows.append(
            {
                "query_id": qid,
                "level": level,
                "query": query,
                "chunk_id": chunk.get("chunk_id"),
                "source_id": chunk.get("source_id"),
                "source_family": chunk.get("source_family"),
                "source_uri": chunk.get("source_uri"),
                "chunk_text": chunk.get("chunk_text"),
                "coarse_rrf_score": chunk.get("rerank_score"),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build expanded v2 reranker data")
    parser.add_argument("--max-results", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--cross-neg", type=int, default=CROSS_NEG_PER_QUERY)
    parser.add_argument("--adjacent", type=int, default=ADJACENT_PER_QUERY)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--env-file", type=Path, default=_REPO / ".env")
    args = parser.parse_args()
    random.seed(args.seed)

    load_env_file(args.env_file)
    api_key = os.getenv("ANYSEARCH_API_KEY")
    payload = json.loads(QUERY_FILE.read_text(encoding="utf-8-sig"))
    cases = payload["cases"]
    train_cases = [c for c in cases if c["id"] not in EVAL_QUERY_IDS]
    eval_cases = [c for c in cases if c["id"] in EVAL_QUERY_IDS]
    print(f"== train queries: {len(train_cases)} (eval held out: {len(eval_cases)})")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Natural chunks per training query.
    natural_rows: list[dict[str, Any]] = []
    for case in train_cases:
        started = perf_counter()
        rows = collect_query_chunks(
            case["query"], case["id"], case["level"], api_key, args.max_results, args.timeout
        )
        natural_rows.extend(rows)
        print(
            f"  [{case['id']} {case['level']}] {len(rows)} chunks "
            f"({perf_counter() - started:.1f}s)"
        )

    # 2) Cross-topic hard negatives: query_i <-> chunks of unrelated queries.
    by_id = {r["query_id"]: r for r in natural_rows}
    pool_by_qid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in natural_rows:
        pool_by_qid[r["query_id"]].append(r)

    qids = [c["id"] for c in train_cases]
    cross_rows: list[dict[str, Any]] = []
    adjacent_rows: list[dict[str, Any]] = []
    for i, qid in enumerate(qids):
        query_row = by_id[qid]
        # unrelated queries: far apart in the ordered list (rotating offsets).
        unrelated = [qids[(i + k) % len(qids)] for k in (3, 7, 11, 13, 17)]
        unrelated = [q for q in unrelated if q != qid]
        neg_pool = [r for q in unrelated for r in pool_by_qid[q]]
        random.shuffle(neg_pool)
        for r in neg_pool[: args.cross_neg]:
            cross_rows.append(
                {
                    "query_id": qid,
                    "level": query_row["level"],
                    "query": query_row["query"],
                    "chunk_id": r["chunk_id"],
                    "source_id": r["source_id"],
                    "source_family": r["source_family"],
                    "source_uri": r["source_uri"],
                    "chunk_text": r["chunk_text"],
                    "coarse_rrf_score": r.get("coarse_rrf_score"),
                    "relation": "cross_topic",
                }
            )
        # topic-adjacent boundary: chunks from the SAME query but lower coarse ranks
        # (coarse_rrf_score lower = weaker evidence) — these are the boundary set.
        own_pool = sorted(
            pool_by_qid[qid], key=lambda r: -(r.get("coarse_rrf_score") or 0.0)
        )
        boundary = [r for r in own_pool if (r.get("coarse_rrf_score") or 1.0) < 0.03]
        random.shuffle(boundary)
        for r in boundary[: args.adjacent]:
            adjacent_rows.append(
                {
                    "query_id": qid,
                    "level": query_row["level"],
                    "query": query_row["query"],
                    "chunk_id": r["chunk_id"],
                    "source_id": r["source_id"],
                    "source_family": r["source_family"],
                    "source_uri": r["source_uri"],
                    "chunk_text": r["chunk_text"],
                    "coarse_rrf_score": r.get("coarse_rrf_score"),
                    "relation": "boundary",
                }
            )

    def save(name: str, rows: list[dict[str, Any]]) -> None:
        path = OUT_DIR / name
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"== saved {len(rows)} -> {path}")

    save("v2_raw_train.jsonl", natural_rows)
    save("v2_crossneg_train.jsonl", cross_rows)
    save("v2_boundary_train.jsonl", adjacent_rows)

    (OUT_DIR / "query_split_v2.json").write_text(
        json.dumps(
            {
                "train": [c["id"] for c in train_cases],
                "eval": [c["id"] for c in eval_cases],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    total = len(natural_rows) + len(cross_rows) + len(adjacent_rows)
    print(f"== TOTAL raw rows: {total} (natural={len(natural_rows)}, "
          f"cross={len(cross_rows)}, boundary={len(adjacent_rows)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
