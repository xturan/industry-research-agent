"""Generate topic-adjacent boundary pairs from existing v2 raw chunks.

Pairs each training query with chunks from a SAME-LEVEL but different-topic query
-> naturally weak/medium relevance (bucket 1-3). No new search needed.

Output: data/rerank_training/v2_adjacent_train.jsonl
"""

from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
DATA_DIR = _REPO / "data" / "rerank_training"
ADJACENT_PER_QUERY = 18


def main() -> int:
    random.seed(42)
    raw = [json.loads(l) for l in open(DATA_DIR / "v2_raw_train.jsonl", encoding="utf-8") if l.strip()]
    pool_by_qid: dict[str, list[dict]] = defaultdict(list)
    level_by_qid: dict[str, str] = {}
    for r in raw:
        pool_by_qid[r["query_id"]].append(r)
        level_by_qid[r["query_id"]] = r["level"]

    qids = list(pool_by_qid.keys())
    rows: list[dict] = []
    for qid in qids:
        level = level_by_qid[qid]
        # same-level, different-topic candidates
        same_level = [q for q in qids if level_by_qid[q] == level and q != qid]
        if not same_level:
            same_level = [q for q in qids if q != qid]
        candidates = [r for q in same_level for r in pool_by_qid[q]]
        random.shuffle(candidates)
        query = pool_by_qid[qid][0]["query"]
        for r in candidates[:ADJACENT_PER_QUERY]:
            rows.append(
                {
                    "query_id": qid,
                    "level": level,
                    "query": query,
                    "chunk_id": r["chunk_id"],
                    "source_id": r["source_id"],
                    "source_family": r["source_family"],
                    "source_uri": r["source_uri"],
                    "chunk_text": r["chunk_text"],
                    "coarse_rrf_score": r.get("coarse_rrf_score"),
                    "relation": "adjacent",
                }
            )
    out = DATA_DIR / "v2_adjacent_train.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"== saved {len(rows)} adjacent pairs -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
