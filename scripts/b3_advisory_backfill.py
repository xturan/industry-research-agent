# ruff: noqa: E501
"""Phase B.3.3a — Advisory Backfill Harness (real provider).

Loads the B.2 real-run EvaluationStore for Case 1 / Case 2, derives
ResearchGaps for `unsatisfied` slots (never `not_evaluable`), and runs the
advisory backfill loop against the REAL search provider (AnySearch default,
Tavily fallback) plus a deterministic content-presence evidence builder.

Outputs (per case) under data/tmp/b3_advisory_backfill/:
  snapshot_before.json  gaps.json  actions.json  search_events.json
  snapshot_after.json   snapshot_diff.json  rounds.json  run_result.json
  final_store.json

Run:
  python scripts/b3_advisory_backfill.py --cases case_01 case_02
  python scripts/b3_advisory_backfill.py --cases case_01 --no-fetch
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.research_harness.advisory_backfill_live import (  # noqa: E501
    AnySearchBackfillExecutor,
    ContentPresenceEvidenceBuilder,
)

REPO = Path(__file__).resolve().parents[1]
B2_ROOT = REPO / "data" / "tmp" / "b2_real_run_acceptance"
OUT_ROOT = REPO / "data" / "tmp" / "b3_advisory_backfill"

CASES = {
    "case_01": "2025 年合肥低空物流项目的落地进展、运营状态及官方证据",
    "case_02": "2025 年合肥低空经济相关上市公司的项目收入及订单贡献",
}


# ── loading + outputs ───────────────────────────────────────────────────────

def _load_env_file(path: str) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in {"PYTHONIOENCODING", "PYTHONUTF8"}:
            import os

            os.environ.setdefault(key, value)


def _load_case(case_id: str) -> tuple[dict, dict]:
    store_path = B2_ROOT / case_id / "evaluation_store.json"
    report_path = B2_ROOT / case_id / "coverage_report.json"
    if not store_path.exists() or not report_path.exists():
        raise SystemExit(
            f"missing B.2 artifacts for {case_id}; run scripts/b2_real_run_acceptance.py first"
        )
    return (
        json.loads(store_path.read_text(encoding="utf-8")),
        json.loads(report_path.read_text(encoding="utf-8")),
    )


def run_case(case_id: str, *, base_query: str, allow_fetch: bool) -> dict:
    from dataclasses import asdict

    from packages.core.config import get_settings
    from packages.research_harness.advisory_backfill import run_advisory_backfill
    from packages.research_harness.eval_persistence import RunEvaluationStore
    from packages.research_harness.gap_retrieval import derive_gaps, propose_search_actions

    get_settings.cache_clear()
    store_dict, report = _load_case(case_id)
    store = RunEvaluationStore.from_dict(store_dict)
    snapshot_before = report

    gaps, egaps = derive_gaps(snapshot_before, store)
    actions = propose_search_actions(
        gaps, store, base_query=base_query, max_per_slot=2,
    )
    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "snapshot_before.json").write_text(
        json.dumps(snapshot_before, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "gaps.json").write_text(
        json.dumps(
            {"research_gaps": [asdict(g) for g in gaps],
             "evaluation_gaps": [asdict(g) for g in egaps]},
            ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "actions.json").write_text(
        json.dumps([asdict(a) for a in actions], ensure_ascii=False, indent=2),
        encoding="utf-8")

    executor = AnySearchBackfillExecutor()
    builder = ContentPresenceEvidenceBuilder(allow_fetch=allow_fetch)

    result = run_advisory_backfill(
        store=store,
        current_snapshot=snapshot_before,
        research_gaps=gaps,
        proposed_actions=actions,
        search_executor=executor,
        evidence_builder=builder,
        base_query=base_query,
        max_rounds=2,
        max_actions_per_round=3,
        max_actions_per_slot=2,
        max_total_actions=6,
    )

    # per-round search events (all rounds, append-only)
    events_by_round = {}
    for r in result.rounds:
        events_by_round[r.round_no] = [
            result.final_store.search_events[eid] for eid in r.search_event_ids
        ]
    (out_dir / "search_events.json").write_text(
        json.dumps(events_by_round, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "snapshot_after.json").write_text(
        json.dumps(result.final_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "snapshot_diff.json").write_text(
        json.dumps(
            {f"round_{r.round_no}": r.snapshot_diff for r in result.rounds},
            ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "rounds.json").write_text(
        json.dumps([r.to_dict() for r in result.rounds], ensure_ascii=False, indent=2),
        encoding="utf-8")
    (out_dir / "run_result.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "final_store.json").write_text(
        json.dumps(result.final_store.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"\n[{case_id}] stopped_reason={result.stopped_reason}")
    print(json.dumps(result.stats, ensure_ascii=False, indent=2))
    return {"case": case_id, "result": result.to_dict()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="+", default=list(CASES))
    ap.add_argument("--env-file", default=".env")
    ap.add_argument("--no-fetch", action="store_true",
                    help="skip page fetches; detect fields from search snippets only")
    args = ap.parse_args()

    _load_env_file(args.env_file)

    results = []
    for case_id in args.cases:
        if case_id not in CASES:
            raise SystemExit(f"unknown case {case_id}")
        results.append(run_case(
            case_id, base_query=CASES[case_id],
            allow_fetch=not args.no_fetch,
        ))

    summary_path = OUT_ROOT / "B3_BACKFILL_ACCEPTANCE.md"
    summary_path.write_text(
        "# B3.3a Advisory Backfill Acceptance\n\n"
        + json.dumps(
            [r["result"]["stats"] for r in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[DONE] -> {OUT_ROOT}")


if __name__ == "__main__":
    main()
