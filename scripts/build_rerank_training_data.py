"""Build real chunk data for reranker LoRA training + evaluation.

Splits the 50-query coverage set into train / eval / spare (stratified by level),
then for each query runs the real retrieval path:
  AnySearch(phrase) -> dedup -> coarse rank (BM25 + real bge-m3, RRF) -> chunk
and saves the top chunks as JSONL rows for DeepSeek labeling.

Output:
  data/rerank_training/raw_chunks_train.jsonl
  data/rerank_training/raw_chunks_eval.jsonl
  data/rerank_training/query_split.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
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
CHUNKS_PER_QUERY = 12
COARSE_TOP_N = 15


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


def _search_phrase(query: str) -> str:
    return str(query or "").strip()[:60]


def split_queries(
    cases: list[dict[str, Any]], train_n: int, eval_n: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Stratified split by level: train_n / eval_n / spare."""
    by_level: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_level[str(case.get("level") or "macro")].append(case)
    train, eval_, spare = [], [], []
    for level, items in by_level.items():
        per = max(1, round(len(items) * train_n / len(cases)))
        train.extend(items[:per])
        eval_.extend(items[per:per + max(1, round(len(items) * eval_n / len(cases)))])
        spare.extend(items[per + max(1, round(len(items) * eval_n / len(cases))):])
    # exact count fixups
    for bucket, n in ((train, train_n), (eval_, eval_n)):
        while len(bucket) < n and spare:
            bucket.append(spare.pop(0))
        while len(bucket) > n:
            spare.insert(0, bucket.pop())
    return train, eval_, spare


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


def collect_for_query(
    query: str, qid: str, level: str, api_key: str, max_results: int, timeout: int
) -> list[dict[str, Any]]:
    """Search + dedup + coarse rank (real bge-m3) + chunk for one query."""
    phrase = _search_phrase(query)
    started = perf_counter()
    results, _meta = anysearch_search(
        phrase, max_results=max_results, api_key=api_key, timeout_seconds=timeout
    )
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
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
    deduped = rr.dedup_sources(sources)
    coarse = rr.coarse_rank_bm25_vector_rrf(
        deduped, query, [phrase], top_n=COARSE_TOP_N
    )
    chunks = rr.chunk_documents(coarse, max_chars=700)
    rows = []
    for chunk in chunks[:CHUNKS_PER_QUERY]:
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
    print(
        f"  [{qid} {level}] '{phrase[:30]}...' -> {len(results)} results, "
        f"{len(deduped)} dedup, {len(coarse)} coarse, {len(rows)} chunks "
        f"({perf_counter() - started:.1f}s)"
    )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build reranker LoRA training/eval data")
    parser.add_argument("--train-n", type=int, default=30)
    parser.add_argument("--eval-n", type=int, default=10)
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--env-file", type=Path, default=_REPO / ".env")
    args = parser.parse_args()

    load_env_file(args.env_file)
    api_key = os.getenv("ANYSEARCH_API_KEY")
    payload = json.loads(QUERY_FILE.read_text(encoding="utf-8-sig"))
    cases = payload["cases"]
    train_q, eval_q, spare_q = split_queries(cases, args.train_n, args.eval_n)
    print(f"== split: train={len(train_q)} eval={len(eval_q)} spare={len(spare_q)}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "query_split.json").write_text(
        json.dumps(
            {
                "train": [{"id": c["id"], "level": c["level"], "query": c["query"]} for c in train_q],
                "eval": [{"id": c["id"], "level": c["level"], "query": c["query"]} for c in eval_q],
                "spare": [{"id": c["id"], "level": c["level"], "query": c["query"]} for c in spare_q],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    for bucket_name, bucket in (("train", train_q), ("eval", eval_q)):
        all_rows: list[dict[str, Any]] = []
        for case in bucket:
            try:
                all_rows.extend(
                    collect_for_query(
                        case["query"], case["id"], case["level"],
                        api_key, args.max_results, args.timeout,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - keep going on per-query failures
                print(f"  [WARN] {case['id']} failed: {type(exc).__name__}: {str(exc)[:120]}")
        out = OUT_DIR / f"raw_chunks_{bucket_name}.jsonl"
        with open(out, "w", encoding="utf-8") as f:
            for row in all_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"== saved {len(all_rows)} rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
