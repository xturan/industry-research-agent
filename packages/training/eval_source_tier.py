"""Evaluate Source Tiering model against holdout test set and rule baseline.

Usage:
    python -m packages.training.eval_source_tier [--model source-tier-r1]
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
TEST_FILE = DATA_DIR / "source_tier_test.jsonl"


def load_test_set() -> list[dict]:
    samples = []
    with open(TEST_FILE, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    return samples


def extract_tier_from_output(output_str: str) -> str:
    """Extract tier letter from JSON output string."""
    try:
        data = json.loads(output_str)
        return data.get("tier", "?")
    except (json.JSONDecodeError, TypeError):
        for t in "ABCD":
            if f'"{t}"' in output_str:
                return t
    return "?"


def eval_rule_baseline(samples: list[dict]) -> dict:
    """Evaluate rule-based classifier on test set."""
    import sys
    sys.path.insert(0, str(Path(__file__).parents[2]))
    from packages.agents.deep_research import _classify_source
    from urllib.parse import urlparse

    correct = 0
    predictions = []
    for s in samples:
        input_text = s["input"]
        true_tier = extract_tier_from_output(s["output"])

        lines = input_text.split("\n")
        domain = url = title = ""
        for line in lines:
            if line.startswith("域名:"):
                domain = line.split(":", 1)[1].strip()
            elif line.startswith("URL:"):
                url = line.split(":", 1)[1].strip()
            elif line.startswith("标题:"):
                title = line.split(":", 1)[1].strip()

        pred_tier, _, _ = _classify_source(domain=domain, url=url, title=title)
        predictions.append(pred_tier)
        if pred_tier == true_tier:
            correct += 1

    return {
        "accuracy": correct / len(samples) if samples else 0,
        "predictions": predictions,
        "total": len(samples),
        "correct": correct,
    }


def eval_model(samples: list[dict], model_name: str) -> dict:
    """Evaluate fine-tuned model via SourceTierModel."""
    try:
        from packages.agents.source_tier_model import SourceTierModel
    except ImportError:
        print("[ERROR] Cannot import SourceTierModel")
        return {"accuracy": 0, "predictions": [], "total": 0, "correct": 0}

    model = SourceTierModel(model_name=model_name)
    if not model.available:
        print(f"[ERROR] Model '{model_name}' not available")
        return {"accuracy": 0, "predictions": [], "total": 0, "correct": 0}

    correct = 0
    predictions = []
    latencies = []

    for i, s in enumerate(samples):
        true_tier = extract_tier_from_output(s["output"])
        input_text = s["input"]
        lines = input_text.split("\n")
        domain = url = title = ""
        for line in lines:
            if line.startswith("域名:"):
                domain = line.split(":", 1)[1].strip()
            elif line.startswith("URL:"):
                url = line.split(":", 1)[1].strip()
            elif line.startswith("标题:"):
                title = line.split(":", 1)[1].strip()

        t0 = time.time()
        prediction = model.classify(domain=domain, url=url, title=title)
        latency = time.time() - t0
        latencies.append(latency)

        pred_tier = prediction.tier
        predictions.append(pred_tier)
        if pred_tier == true_tier:
            correct += 1

        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(samples)}] acc={correct/(i+1):.2%} "
                  f"avg_latency={sum(latencies)/len(latencies):.2f}s")

    return {
        "accuracy": correct / len(samples) if samples else 0,
        "predictions": predictions,
        "total": len(samples),
        "correct": correct,
        "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
    }


def print_confusion_matrix(true_labels: list[str], pred_labels: list[str]):
    """Print a simple confusion matrix."""
    tiers = ["A", "B", "C", "D"]
    print("\n  Confusion Matrix (rows=true, cols=predicted):")
    print(f"  {'':>6}", end="")
    for t in tiers:
        print(f"{t:>6}", end="")
    print()
    for true_t in tiers:
        print(f"  {true_t:>6}", end="")
        for pred_t in tiers:
            count = sum(1 for t, p in zip(true_labels, pred_labels)
                        if t == true_t and p == pred_t)
            print(f"{count:>6}", end="")
        print()


def print_report(name: str, result: dict, samples: list[dict]):
    """Print evaluation report."""
    print(f"\n{'='*50}")
    print(f"  {name}")
    print(f"{'='*50}")
    print(f"  Accuracy: {result['accuracy']:.2%} ({result['correct']}/{result['total']})")
    if "avg_latency" in result:
        print(f"  Avg latency: {result['avg_latency']:.2f}s/sample")

    true_labels = [extract_tier_from_output(s["output"]) for s in samples]
    print_confusion_matrix(true_labels, result["predictions"])

    print("\n  Per-tier accuracy:")
    for t in "ABCD":
        indices = [i for i, s in enumerate(samples)
                   if extract_tier_from_output(s["output"]) == t]
        if indices:
            correct = sum(1 for i in indices if result["predictions"][i] == t)
            print(f"    {t}: {correct}/{len(indices)} = {correct/len(indices):.2%}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5:7b",
                        help="Ollama model name for evaluation")
    parser.add_argument("--skip-model", action="store_true",
                        help="Skip model evaluation (only run rule baseline)")
    args = parser.parse_args()

    print(f"[INFO] Loading test set from {TEST_FILE}")
    samples = load_test_set()
    print(f"[INFO] Test set: {len(samples)} samples")

    print("\n[INFO] Evaluating rule-based baseline...")
    rule_result = eval_rule_baseline(samples)
    print_report("Rule-Based Baseline", rule_result, samples)

    if not args.skip_model:
        print(f"\n[INFO] Evaluating model: {args.model}")
        model_result = eval_model(samples, args.model)
        print_report(f"Model: {args.model}", model_result, samples)

        delta = model_result["accuracy"] - rule_result["accuracy"]
        print(f"\n  Delta (model - rules): {delta:+.2%}")
        if delta > 0:
            print("  Model outperforms rules.")
        elif delta < 0:
            print("  Rules outperform model — consider more training data.")
        else:
            print("  Tied — model adds value on edge cases rules can't handle.")


if __name__ == "__main__":
    main()
