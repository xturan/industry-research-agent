"""Evaluate the trained reranker LoRA vs DeepSeek labels vs V1 baseline.

Reads data/rerank_training/eval_label.jsonl (DeepSeek ground-truth scores for the
held-out 10 queries' chunks), then calls the rerank vLLM service with the base
model (no LoRA) and the LoRA model, both using the SAME instruction prompt, and
reports Spearman / MAE / binary accuracy against the DeepSeek labels.

Usage:
  python scripts/eval_rerank_lora.py [--lora-model rerank-lora]
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from packages.rag.rerankers import (  # noqa: E402
    _RERANKER_INSTRUCTION,
    _RERANK_INPUT_TEMPLATE,
    _RERANK_BUCKET_RE,
    _BUCKET_TO_SCORE,
)

EVAL_FILE = _REPO / "data" / "rerank_training" / "eval_label.jsonl"
BASE_MODEL = "Qwen2.5-3B-Instruct-AWQ"

_lock = threading.Lock()


def _load_rows() -> list[dict[str, Any]]:
    return [json.loads(l) for l in open(EVAL_FILE, encoding="utf-8") if l.strip()]


def call_scorer(
    endpoint: str, model: str, query: str, chunk_text: str, timeout: float = 60.0
) -> float:
    import requests

    content = f"{_RERANKER_INSTRUCTION}\n\n{_RERANK_INPUT_TEMPLATE.format(query=query, text=chunk_text)}"
    resp = requests.post(
        endpoint,
        json={
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 64,
            "temperature": 0.0,
        },
        timeout=timeout,
    )
    data = resp.json()
    raw = str(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
    match = _RERANK_BUCKET_RE.search(raw)
    if match:
        return _BUCKET_TO_SCORE[int(match.group(1))]
    return 0.5


def _score_rows(endpoint: str, model: str, rows: list[dict[str, Any]], workers: int) -> list[float]:
    scores: list[float] = [0.5] * len(rows)

    def work(i: int) -> tuple[int, float]:
        r = rows[i]
        return i, call_scorer(endpoint, model, r["query"], r["chunk_text"])

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, i) for i in range(len(rows))]
        done = 0
        for fut in as_completed(futures):
            i, s = fut.result()
            scores[i] = s
            done += 1
            with _lock:
                if done % 25 == 0:
                    print(f"  [{model}] {done}/{len(rows)}")
    return scores


def _spearman(a: list[float], b: list[float]) -> float:
    n = len(a)
    ra = {v: i for i, v in enumerate(sorted(a))}
    rb = {v: i for i, v in enumerate(sorted(b))}
    # average ranks for ties
    def ranks(x: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: x[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and x[order[j + 1]] == x[order[i]]:
                j += 1
            avg = (i + j) / 2.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((x - mb) ** 2 for x in rb) ** 0.5
    return num / (da * db) if da and db else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lora-model", default="rerank-lora")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--endpoint", default="http://localhost:8000/v1/chat/completions")
    args = parser.parse_args()

    rows = _load_rows()
    print(f"== eval rows: {len(rows)}")

    labels = [float(r["score"]) for r in rows]
    print(f"== scoring baseline ({BASE_MODEL}) ...")
    base_scores = _score_rows(args.endpoint, BASE_MODEL, rows, args.workers)
    print(f"== scoring lora ({args.lora_model}) ...")
    lora_scores = _score_rows(args.endpoint, args.lora_model, rows, args.workers)

    metrics: dict[str, Any] = {
        "n": len(rows),
        "baseline": {
            "model": BASE_MODEL,
            "spearman_vs_label": round(_spearman(base_scores, labels), 4),
            "mae_vs_label": round(sum(abs(a - b) for a, b in zip(base_scores, labels)) / len(labels), 4),
            "binary_acc": round(
                sum((a >= 0.5) == (b >= 0.5) for a, b in zip(base_scores, labels)) / len(labels), 4
            ),
            "mean_score": round(sum(base_scores) / len(base_scores), 3),
        },
        "lora": {
            "model": args.lora_model,
            "spearman_vs_label": round(_spearman(lora_scores, labels), 4),
            "mae_vs_label": round(sum(abs(a - b) for a, b in zip(lora_scores, labels)) / len(labels), 4),
            "binary_acc": round(
                sum((a >= 0.5) == (b >= 0.5) for a, b in zip(lora_scores, labels)) / len(labels), 4
            ),
            "mean_score": round(sum(lora_scores) / len(lora_scores), 3),
        },
        "label_mean": round(sum(labels) / len(labels), 3),
    }
    report = {
        "metrics": metrics,
        "samples": [
            {
                "query_id": r.get("query_id"), "chunk_id": r.get("chunk_id"),
                "label": labels[i], "baseline": round(base_scores[i], 3),
                "lora": round(lora_scores[i], 3),
            }
            for i, r in enumerate(rows)
        ],
    }
    out = _REPO / "data" / "rerank_training" / "eval_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n== METRICS ==")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"== saved -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
