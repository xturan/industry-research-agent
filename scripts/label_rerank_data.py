"""Label reranker training chunks with fine-grained scores via DeepSeek.

Reads raw_chunks_{split}.jsonl, calls DeepSeek chat for a 0.00-1.00 score + short
reason, and writes:
  data/rerank_training/{split}_label.jsonl          (raw rows + score/reason)
  data/rerank_training/{split}_alpaca.jsonl          (Alpaca-format training set)

Usage:
  python scripts/label_rerank_data.py --split train --workers 8
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from packages.core.config import get_settings  # noqa: E402

DATA_DIR = _REPO / "data" / "rerank_training"

SYSTEM_PROMPT = (
    "你是一个产业研究检索精排器。你的任务是对「查询-文档」对给出相关性分数，"
    "用于训练精排模型。\n\n"
    "评分标准（0.00-1.00，两位小数）：\n"
    "- 0.00-0.20：无关或跑题，文档与查询主题没有关系\n"
    "- 0.21-0.50：弱相关，仅提及查询主题，但没有实质性信息\n"
    "- 0.51-0.80：相关且包含实质性信息（具体数据、政策条文、企业/项目名称、时间地点）\n"
    "- 0.81-1.00：核心证据，直接支撑查询所要的判断或结论\n\n"
    "要求：\n"
    "1. 文档中的具体事实/数据/政策/企业/项目应加分，泛泛而谈扣分。\n"
    "2. 分数要拉开差距，不要全部打高分。\n"
    "3. 严格按一行输出：<分数> | <理由>，理由不超过 20 字，例如：\n"
    "0.87 | 文档含浏阳花炮产值498.4亿具体数据"
)

USER_TEMPLATE = "查询：{query}\n\n文档：{chunk_text}"

_SCORE_RE = re.compile(r"^([01]\.\d{2}|0\.\d{2})\s*\|\s*(.+)$", re.S)
_FALLBACK_FLOAT_RE = re.compile(r"([01](?:\.\d{1,2})?|\.\d{1,2})")

_lock = threading.Lock()
_counts = {"ok": 0, "retry": 0, "fail": 0}


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
        reason = m.group(2).strip()
        if 0.0 <= score <= 1.0:
            return {"score": score, "reason": reason, "raw": raw}
    fm = _FALLBACK_FLOAT_RE.search(raw)
    if fm:
        score = float(fm.group(1))
        if 0.0 <= score <= 1.0:
            return {"score": score, "reason": raw[:40], "raw": raw}
    return {"score": None, "reason": raw[:40], "raw": raw}


def label_row(client: Any, model: str, row: dict[str, Any]) -> dict[str, Any]:
    result = call_deepseek(client, model, row["query"], row["chunk_text"])
    out = dict(row)
    out.update(result)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Label reranker chunks via DeepSeek")
    parser.add_argument("--split", choices=["train", "eval"], default="train")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0, help="0 = all")
    parser.add_argument("--env-file", type=Path, default=_REPO / ".env")
    args = parser.parse_args()

    _load_env(args.env_file)
    settings = get_settings()
    if not settings.deepseek_api_key:
        print("[error] DEEPSEEK_API_KEY not set", file=sys.stderr)
        return 1

    from openai import OpenAI

    client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    model = settings.deepseek_research_model

    src = DATA_DIR / f"raw_chunks_{args.split}.jsonl"
    rows = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
    if args.limit:
        rows = rows[: args.limit]
    print(f"== labeling {len(rows)} rows (split={args.split}, workers={args.workers})")

    labeled: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(label_row, client, model, r): r for r in rows}
        for fut in as_completed(futures):
            row = futures[fut]
            try:
                result = fut.result()
                labeled.append(result)
                if result.get("score") is not None:
                    _counts["ok"] += 1
                else:
                    _counts["fail"] += 1
            except Exception as exc:  # noqa: BLE001
                _counts["fail"] += 1
                result = dict(row, score=None, reason="", raw=f"ERROR: {exc}")
                labeled.append(result)
            with _lock:
                if (_counts["ok"] + _counts["fail"]) % 25 == 0:
                    print(
                        f"  progress ok={_counts['ok']} fail={_counts['fail']} "
                        f"total={_counts['ok'] + _counts['fail']}"
                    )

    # stable by chunk_id
    labeled.sort(key=lambda r: str(r.get("chunk_id") or ""))
    ok_rows = [r for r in labeled if r.get("score") is not None]
    label_path = DATA_DIR / f"{args.split}_label.jsonl"
    with open(label_path, "w", encoding="utf-8") as f:
        for r in labeled:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    if args.split == "train":
        alpaca = []
        for r in ok_rows:
            alpaca.append(
                {
                    "instruction": (
                        "你是一个产业研究检索精排器。判断下面文档对查询的相关性，"
                        "输出 0.00 到 1.00 的分数（两位小数）和一句简短理由，"
                        "格式：<分数> | <理由>。"
                    ),
                    "input": USER_TEMPLATE.format(query=r["query"], chunk_text=r["chunk_text"]),
                    "output": f"{r['score']:.2f} | {r['reason']}",
                    "query_id": r.get("query_id"),
                    "level": r.get("level"),
                    "chunk_id": r.get("chunk_id"),
                    "source_family": r.get("source_family"),
                }
            )
        alpaca_path = DATA_DIR / "train_alpaca.jsonl"
        with open(alpaca_path, "w", encoding="utf-8") as f:
            for a in alpaca:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
        print(f"== alpaca saved: {len(alpaca)} -> {alpaca_path}")

    from collections import Counter

    print(f"== done ok={_counts['ok']} fail={_counts['fail']} -> {label_path}")
    if ok_rows:
        scores = [r["score"] for r in ok_rows]
        print(f"== score dist: min={min(scores):.2f} max={max(scores):.2f} "
              f"mean={sum(scores)/len(scores):.2f}")
        buckets = Counter(round(s * 10) for s in scores)
        print("== buckets(0-1 x10):", dict(sorted(buckets.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
