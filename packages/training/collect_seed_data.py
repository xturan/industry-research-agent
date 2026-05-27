"""Batch runner: execute Deep Research on selected queries to accumulate
source_assessments as training seed data for the Source Tiering model.

Usage:
    python -m packages.training.collect_seed_data [--limit 20]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

SEED_DATA_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = SEED_DATA_DIR / "seed_source_assessments.jsonl"

# 20 queries selected from the 50-query stress set, covering macro/province/city/key-chain
SELECTED_QUERY_IDS = [
    "M01", "M02", "M03", "M04", "M06",
    "M08", "M09", "M10", "M11", "M12",
    "P01", "P02", "P03", "P04", "P05",
    "P08", "P10", "C01", "C07", "K07",
]


def load_queries() -> list[dict]:
    """Load selected queries from the stress eval cases file."""
    cases_file = Path("data/tmp/source_quality_stress_eval/source_quality_cases_v1.json")
    if not cases_file.exists():
        print(f"[ERROR] Cases file not found: {cases_file}")
        sys.exit(1)

    with open(cases_file, encoding="utf-8") as f:
        data = json.load(f)

    selected = []
    for case in data["cases"]:
        if case["id"] in SELECTED_QUERY_IDS:
            selected.append(case)
    return selected


def run_single_query(query: str, query_id: str) -> dict | None:
    """Run Deep Research on a single query and return the report dict."""
    try:
        from packages.agents.deep_research import DeepResearchAgent
        agent = DeepResearchAgent(max_rounds=5, max_sources_per_round=5)
        report = agent.run(query, persist=True)
        return report.model_dump(mode="json")
    except Exception as e:
        print(f"  [FAIL] {query_id}: {e}")
        return None


def extract_training_samples(report_dict: dict, query_id: str, query: str) -> list[dict]:
    """Extract source assessments as training samples from a report."""
    samples = []
    assessments = report_dict.get("source_assessments", [])
    for sa in assessments:
        samples.append({
            "query_id": query_id,
            "query": query[:200],
            "url": sa.get("url", ""),
            "title": sa.get("title", ""),
            "tier": sa.get("tier", "D"),
            "authority_score": sa.get("authority_score", 0.0),
            "proximity_score": sa.get("proximity_score", 0.0),
            "timeliness_score": sa.get("timeliness_score", 0.0),
            "verifiability_score": sa.get("verifiability_score", 0.0),
            "relevance_score": sa.get("relevance_score", 0.0),
            "overall_usable": sa.get("overall_usable", False),
            "usage_note": sa.get("usage_note", ""),
        })
    return samples


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    SEED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    queries = load_queries()[:args.limit]
    print(f"[INFO] Running Deep Research on {len(queries)} queries...")
    print(f"[INFO] Output: {OUTPUT_FILE}")

    total_samples = 0
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        for i, case in enumerate(queries, 1):
            qid = case["id"]
            query = case["query"]
            print(f"\n[{i}/{len(queries)}] {qid}: {query[:60]}...")

            t0 = time.time()
            report = run_single_query(query, qid)
            elapsed = time.time() - t0

            if report is None:
                continue

            samples = extract_training_samples(report, qid, query)
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
            total_samples += len(samples)

            n_sources = len(report.get("source_assessments", []))
            confidence = report.get("overall_confidence", "?")
            print(f"  OK: {n_sources} sources, confidence={confidence}, "
                  f"{elapsed:.1f}s, total_samples={total_samples}")

    print(f"\n[DONE] Collected {total_samples} training samples → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
