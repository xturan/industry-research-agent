#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build a 3/4 boundary calibration set for the rerank LoRA.

The first LoRA run improved ranking quality, but the eval confusion matrix
showed a conservative bias: many gold 4 samples were predicted as 3. This
script constructs a follow-up SFT dataset from the original training data only,
with intentional row duplication around the 3/4 decision boundary.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Construct rerank 3/4 calibration data")
    p.add_argument("--input", default="data/v2_alpaca_balanced.jsonl")
    p.add_argument("--output", default="data/v3_boundary34_calibration.jsonl")
    p.add_argument("--report", default="data/v3_boundary34_calibration_report.md")
    p.add_argument("--seed", type=int, default=20260808)
    p.add_argument("--repeat-4", type=int, default=2)
    p.add_argument("--repeat-3", type=int, default=1)
    p.add_argument("--near-2-limit", type=int, default=220)
    p.add_argument("--low-anchor-per-label", type=int, default=96)
    return p.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, 1):
            line = raw.strip()
            if not line:
                continue
            item = json.loads(line)
            item["_source_line"] = line_no
            rows.append(item)
    return rows


def dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            clean = {k: v for k, v in row.items() if not k.startswith("_")}
            f.write(json.dumps(clean, ensure_ascii=False) + "\n")


def bucket(row: dict[str, Any]) -> str:
    return str(row.get("output", "")).strip()


def score(row: dict[str, Any]) -> float:
    try:
        return float(row.get("score", 0.0))
    except (TypeError, ValueError):
        return 0.0


def choose_balanced(
    rows: list[dict[str, Any]],
    limit: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Sample rows with a light source-family balance."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("source_family", "unknown"))].append(row)
    for items in grouped.values():
        rng.shuffle(items)

    selected: list[dict[str, Any]] = []
    keys = sorted(grouped, key=lambda k: len(grouped[k]), reverse=True)
    cursor = 0
    while len(selected) < limit and any(grouped.values()):
        key = keys[cursor % len(keys)]
        if grouped[key]:
            selected.append(grouped[key].pop())
        cursor += 1
    return selected


def clone(row: dict[str, Any], role: str, repeat_index: int) -> dict[str, Any]:
    out = dict(row)
    source_line = out.pop("_source_line", None)
    source_row_id = (
        f"v2_line_{source_line}"
        if source_line is not None
        else str(out.get("chunk_id", "unknown"))
    )
    out["calibration_stage"] = "boundary34_v1"
    out["calibration_role"] = role
    out["calibration_repeat_index"] = repeat_index
    out["source_dataset"] = "v2_alpaca_balanced"
    out["source_row_id"] = source_row_id
    return out


def construct(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    rng = random.Random(args.seed)
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_label[bucket(row)].append(row)
    for items in by_label.values():
        rng.shuffle(items)

    output_rows: list[dict[str, Any]] = []

    # Positive pressure: repeat all class-4 samples, because the trained model
    # under-called core evidence as class 3.
    for repeat_index in range(args.repeat_4):
        for row in by_label["4"]:
            output_rows.append(clone(row, "core_evidence_positive_repeat", repeat_index))

    # Boundary contrast: keep every class-3 sample once, so the model still sees
    # "substantive but not core" evidence next to class 4.
    for repeat_index in range(args.repeat_3):
        for row in by_label["3"]:
            output_rows.append(clone(row, "substantive_boundary_negative", repeat_index))

    # High class-2 rows are the closest lower anchor. Prefer score=0.55/0.45
    # because they prevent the calibration pass from turning all useful text
    # into 3/4.
    near_2 = sorted(by_label["2"], key=score, reverse=True)
    near_2 = choose_balanced(near_2, min(args.near_2_limit, len(near_2)), rng)
    for row in near_2:
        output_rows.append(clone(row, "near_miss_anchor_2", 0))

    # Sparse low anchors preserve rejection ability without dominating the pass.
    for label in ("0", "1"):
        anchors = choose_balanced(
            by_label[label],
            min(args.low_anchor_per_label, len(by_label[label])),
            rng,
        )
        for row in anchors:
            output_rows.append(clone(row, f"low_anchor_{label}", 0))

    rng.shuffle(output_rows)
    return output_rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_output = Counter(bucket(r) for r in rows)
    by_role = Counter(str(r.get("calibration_role", "original")) for r in rows)
    by_family = defaultdict(Counter)
    by_score = defaultdict(Counter)
    for row in rows:
        label = bucket(row)
        by_family[label][str(row.get("source_family", "unknown"))] += 1
        by_score[label][str(row.get("score", ""))] += 1
    return {
        "total": len(rows),
        "by_output": dict(sorted(by_output.items())),
        "by_role": dict(by_role.most_common()),
        "by_family": {
            label: dict(counter.most_common())
            for label, counter in sorted(by_family.items())
        },
        "by_score": {
            label: dict(counter.most_common())
            for label, counter in sorted(by_score.items())
        },
    }


def write_report(
    path: Path,
    input_path: Path,
    output_path: Path,
    original_summary: dict[str, Any],
    calibration_summary: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    lines = [
        "# Rerank 3/4 Boundary Calibration Dataset",
        "",
        "## Purpose",
        "",
        "The previous LoRA improved ranking metrics, but eval showed many gold class-4 chunks were predicted as class 3. "
        "This dataset is a second-stage calibration set built only from the original training file, with no eval leakage.",
        "",
        "## Construction Policy",
        "",
        f"- Source file: `{input_path}`",
        f"- Output file: `{output_path}`",
        f"- Seed: `{args.seed}`",
        f"- Class 4 repeats: `{args.repeat_4}`",
        f"- Class 3 repeats: `{args.repeat_3}`",
        f"- Near class-2 anchors: `{args.near_2_limit}`",
        f"- Low anchors per label 0/1: `{args.low_anchor_per_label}`",
        "",
        "Class 4 is intentionally upweighted to improve core-evidence recall. "
        "Class 3 is kept as the main contrast set. High class-2 samples and sparse 0/1 anchors are retained to reduce score drift.",
        "",
        "## Original Distribution",
        "",
        "```json",
        json.dumps(original_summary, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Calibration Distribution",
        "",
        "```json",
        json.dumps(calibration_summary, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Recommended Follow-up Training",
        "",
        "Use this as a short second-stage SFT pass from the existing LoRA output. Suggested starting point:",
        "",
        "```bash",
        "torchrun --standalone --nproc_per_node=2 train_rerank_lora_cloud.py \\",
        "  --base-model Qwen/Qwen2.5-3B-Instruct \\",
        "  --data-file data/v3_boundary34_calibration.jsonl \\",
        "  --output-dir output/rerank_3b_lora_v4_boundary34 \\",
        "  --epochs 1 \\",
        "  --batch 2 \\",
        "  --grad-accum 4 \\",
        "  --max-length 1536 \\",
        "  --lr 8e-5 \\",
        "  --max-lora-rank 16 \\",
        "  --save-steps 120 \\",
        "  --completion-only \\",
        "  --resume-from output/rerank_3b_lora_v3_ddp_2x4090_len1536/checkpoint-668",
        "```",
        "",
        "If that checkpoint has been cleaned up, add adapter-loading support to the trainer before doing calibration; "
        "training this boundary set from the base model alone is not the intended use.",
        "",
        "Evaluate against `data_eval/eval_label.jsonl` exactly as before, and watch class-4 recall plus nDCG@5. "
        "If class-4 recall rises but precision drops sharply, lower `--repeat-4` or shorten the pass.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    report_path = Path(args.report)

    rows = load_jsonl(input_path)
    calibration_rows = construct(rows, args)
    dump_jsonl(output_path, calibration_rows)

    original_summary = summarize(rows)
    calibration_summary = summarize(calibration_rows)
    write_report(
        report_path,
        input_path,
        output_path,
        original_summary,
        calibration_summary,
        args,
    )
    print(json.dumps({
        "input": str(input_path),
        "output": str(output_path),
        "report": str(report_path),
        "original": original_summary,
        "calibration": calibration_summary,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
