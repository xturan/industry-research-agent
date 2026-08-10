"""Label v2 reranker data with DeepSeek -> 5-bucket classification -> rebalance.

Reads v2_raw_train / v2_crossneg_train / v2_boundary_train, DeepSeek-scores each
(continuous 0.00-1.00), converts to bucket 0-4, then resamples to target class
proportions. Writes the balanced Alpaca training set.

Target proportions: bucket0 15% / 1 20% / 2 20% / 3 20% / 4 25%.

Output:
  data/rerank_training/v2_label_all.jsonl
  data/rerank_training/v2_alpaca_balanced.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from packages.core.config import get_settings  # noqa: E402

DATA_DIR = _REPO / "data" / "rerank_training"

SYSTEM_PROMPT = (
    "你是一个产业研究检索精排器。你的任务是对「查询-文档」对给出相关性分数。\n\n"
    "评分标准（0.00-1.00，两位小数）：\n"
    "- 0.00-0.19：无关或跑题\n"
    "- 0.20-0.39：弱相关，仅提及主题但无实质信息\n"
    "- 0.40-0.59：一般相关，有些内容但不够具体\n"
    "- 0.60-0.79：相关且有实质性信息（具体数据/政策/企业/项目）\n"
    "- 0.80-1.00：核心证据，直接支撑查询判断\n\n"
    "要求：分数要拉开差距；具体事实/数据/政策/企业加分，泛泛而谈扣分。"
    "严格按一行输出：<分数> | <理由（≤20字）>"
)

USER_TEMPLATE = "查询：{query}\n\n文档：{chunk_text}"
_SCORE_RE = re.compile(r"^([01]\.\d{2})\s*\|\s*(.+)$", re.S)
_FALLBACK_RE = re.compile(r"([01](?:\.\d{1,2})?|\.\d{1,2})")

TARGET_PROPS = {0: 0.15, 1: 0.20, 2: 0.20, 3: 0.20, 4: 0.25}


def score_to_bucket(score: float) -> int:
    if score < 0.20:
        return 0
    if score < 0.40:
        return 1
    if score < 0.60:
        return 2
    if score < 0.80:
        return 3
    return 4


def _load_env(path: Path) -> None:
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


def call_deepseek(client: Any, model: str, query: str, chunk_text: str) -> dict[str, Any]:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(
                query=query, chunk_text=str(chunk_text or "")[:700]
            )},
        ],
        temperature=0.2,
        max_tokens=64,
    )
    raw = str(resp.choices[0].message.content or "").strip()
    m = _SCORE_RE.search(raw)
    if m:
        score = float(m.group(1))
        if 0.0 <= score <= 1.0:
            return {"score": score, "reason": m.group(2).strip(), "raw": raw}
    fm = _FALLBACK_RE.search(raw)
    if fm:
        score = float(fm.group(1))
        if 0.0 <= score <= 1.0:
            return {"score": score, "reason": raw[:40], "raw": raw}
    return {"score": None, "reason": raw[:40], "raw": raw}


def label_row(client: Any, model: str, row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out.update(call_deepseek(client, model, row["query"], row["chunk_text"]))
    return out


def rebalance(rows: list[dict[str, Any]], target: dict[int, float], seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    by_bucket: dict[int, list[dict[str, Any]]] = {b: [] for b in target}
    for r in rows:
        if r.get("score") is not None:
            by_bucket[score_to_bucket(r["score"])].append(r)
    total = len(rows)
    picked: list[dict[str, Any]] = []
    for b, prop in target.items():
        want = int(total * prop)
        pool = by_bucket[b]
        if len(pool) >= want:
            picked.extend(rng.sample(pool, want))
        else:
            # undersupplied: use all + oversample to reach want.
            picked.extend(pool)
            if pool:
                picked.extend(rng.choices(pool, k=want - len(pool)))
    return picked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--env-file", type=Path, default=_REPO / ".env")
    args = parser.parse_args()
    random.seed(args.seed)

    _load_env(args.env_file)
    settings = get_settings()
    if not settings.deepseek_api_key:
        print("[error] DEEPSEEK_API_KEY not set", file=sys.stderr)
        return 1
    from openai import OpenAI

    client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    model = settings.deepseek_research_model

    rows: list[dict[str, Any]] = []
    for fname in ("v2_raw_train.jsonl", "v2_crossneg_train.jsonl", "v2_adjacent_train.jsonl"):
        p = DATA_DIR / fname
        if p.exists():
            rows.extend(json.loads(l) for l in open(p, encoding="utf-8") if l.strip())
            print(f"== loaded {fname}: {sum(1 for _ in open(p, encoding='utf-8'))} rows")
    if args.limit:
        rows = rows[: args.limit]
    print(f"== labeling {len(rows)} v2 rows (workers={args.workers})")

    labeled: list[dict[str, Any]] = []
    done = 0
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(label_row, client, model, r) for r in rows]
        for fut in as_completed(futures):
            try:
                labeled.append(fut.result())
            except Exception as exc:  # noqa: BLE001
                labeled.append(dict(rows[futures.index(fut)], score=None, reason="", raw=str(exc)))
            done += 1
            with lock:
                if done % 100 == 0:
                    print(f"  progress {done}/{len(rows)}")

    labeled.sort(key=lambda r: str(r.get("chunk_id") or "") + str(r.get("query_id")))
    all_path = DATA_DIR / "v2_label_all.jsonl"
    with open(all_path, "w", encoding="utf-8") as f:
        for r in labeled:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"== saved labels -> {all_path}")

    ok = [r for r in labeled if r.get("score") is not None]
    print(f"== ok={len(ok)} / {len(labeled)}")
    dist = Counter(score_to_bucket(r["score"]) for r in ok)
    print("== raw bucket dist:", dict(sorted(dist.items())))

    balanced = rebalance(ok, TARGET_PROPS, args.seed)
    bal_dist = Counter(score_to_bucket(r["score"]) for r in balanced)
    print("== balanced bucket dist:", dict(sorted(bal_dist.items())), f"(n={len(balanced)})")

    alpaca = []
    for r in balanced:
        bucket = score_to_bucket(r["score"])
        alpaca.append(
            {
                "instruction": (
                    "你是一个产业研究检索精排器。判断下面文档对查询的相关性，"
                    "输出 0-4 五档分数：0=无关，1=弱相关，2=一般相关，"
                    "3=相关且有实质信息，4=核心证据。只输出一个数字。"
                ),
                "input": USER_TEMPLATE.format(query=r["query"], chunk_text=r["chunk_text"]),
                "output": str(bucket),
                "query_id": r.get("query_id"),
                "level": r.get("level"),
                "chunk_id": r.get("chunk_id"),
                "source_family": r.get("source_family"),
                "score": r.get("score"),
                "relation": r.get("relation"),
            }
        )
    out_path = DATA_DIR / "v2_alpaca_balanced.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for a in alpaca:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    print(f"== saved balanced Alpaca -> {out_path} ({len(alpaca)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
