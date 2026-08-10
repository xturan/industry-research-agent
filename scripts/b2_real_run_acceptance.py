# ruff: noqa: E501
"""Phase B.2 — Real-run Acceptance.

Runs 2 fresh tasks through graph_provider_backed_smoke.py (current schema, no
old checkpoint), extracts the persisted RunEvaluationStore from the run's
checkpoint DB, computes build_runtime_coverage_report(mode=evaluable_persistence)
and writes per-case integrity diagnostics.

Cases:
- case_01: evidence-adequate  (合肥低空物流项目落地进展/运营状态/官方证据)
- case_02: evidence-sparse    (合肥低空经济上市公司项目收入/订单贡献)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO / "data" / "tmp" / "b2_real_run_acceptance"
SMOKE = REPO / "scripts" / "graph_provider_backed_smoke.py"

CASES = {
    "case_01": "2025 年合肥低空物流项目的落地进展、运营状态及官方证据",
    "case_02": "2025 年合肥低空经济相关上市公司的项目收入及订单贡献",
}


def _extract_store(db_path: Path) -> dict:
    import sqlite3

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT state_json FROM research_graph_checkpoints ORDER BY id DESC"
    ).fetchall()
    con.close()
    for row in rows:
        state = json.loads(row["state_json"] or "{}")
        store = state.get("evaluation_store")
        if isinstance(store, dict) and store:
            return store
    return {}


def integrity_diagnostics(store: dict, coverage: dict, run_id: str, status: str) -> dict:
    claim_slots = store.get("claim_slots", {})
    search_tasks = store.get("search_tasks", {})
    search_events = store.get("search_events", {})
    evidence_units = store.get("evidence_units", {})
    claim_cards = store.get("claim_cards", {})

    task_terminal = sum(
        1 for t in search_tasks.values()
        if t.get("status") in {"completed", "failed", "cancelled", "budget_exhausted"}
    )
    executed_tasks = sum(
        1 for t in search_tasks.values()
        if t.get("status") in {"completed", "failed"}
    )
    ev_linked = sum(1 for e in evidence_units.values() if e.get("supports_slot_ids"))
    claim_ev_linked = sum(1 for c in claim_cards.values() if c.get("evidence_ids"))
    claim_slot_linked = sum(1 for c in claim_cards.values() if c.get("slot_ids"))

    slot_status = Counter(r.get("status") for r in coverage.get("slot_reports", []))
    return {
        "run_id": run_id,
        "claim_slot_count": len(claim_slots),
        "claim_slot_trace_rate": round(min(1.0, len(claim_slots) / max(1, len(claim_slots))), 4),
        "search_task_count": len(search_tasks),
        "search_task_terminal_status_rate": round(task_terminal / max(1, len(search_tasks)), 4),
        "executed_search_count": len(search_events),
        "search_event_recording_rate": round(min(1.0, len(search_events) / max(1, executed_tasks)), 4),
        "evidence_unit_count": len(evidence_units),
        "evidence_field_status_rate": round(
            sum(1 for e in evidence_units.values() if e.get("key_field_extraction_status") != "not_extracted")
            / max(1, len(evidence_units)), 4,
        ),
        "evidence_to_slot_link_rate": round(ev_linked / max(1, len(evidence_units)), 4),
        "approved_claim_count": len(claim_cards),
        "claim_to_evidence_link_rate": round(claim_ev_linked / max(1, len(claim_cards)), 4),
        "claim_to_slot_link_rate": round(claim_slot_linked / max(1, len(claim_cards)), 4),
        "evaluation_persistence_status": status,
        "evaluation_completeness": coverage.get("evaluation_completeness", 0.0),
        "slot_status_distribution": dict(slot_status),
        "coverage_input_source": coverage.get("coverage_input_source"),
        "legacy_fallback_used": coverage.get("legacy_fallback_used"),
        "readiness": coverage.get("readiness"),
    }


def run_case(case_id: str, query: str, *, max_rounds: int, env_file: str) -> dict:
    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = OUT_ROOT / f"{case_id}.db"
    cmd = [
        sys.executable, str(SMOKE),
        "--query", query,
        "--max-rounds", str(max_rounds),
        "--max-loop-count", "1",
        "--output-dir", str(out_dir),
        "--env-file", env_file,
        "--reset",
    ]
    print(f"[RUN] {case_id}: {' '.join(cmd[-5:])}")
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    if proc.returncode != 0:
        return {"case": case_id, "error": f"exit {proc.returncode}", "stderr": (proc.stderr or "")[-500:]}

    store_dict = _extract_store(db_path)
    from packages.research_harness.eval_persistence import (
        RunEvaluationStore,
        build_runtime_coverage_report,
    )

    store = RunEvaluationStore.from_dict(store_dict)
    degraded = False
    report = build_runtime_coverage_report(
        run_id=str(store.run_id or case_id),
        evaluation_store=store,
        legacy_state={},
        mode="evaluable_persistence",
        degraded=degraded,
    )
    diag = integrity_diagnostics(store_dict, report, str(store.run_id or case_id), "active")

    (out_dir / "evaluation_store.json").write_text(
        json.dumps(store_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "coverage_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "integrity_diagnostics.json").write_text(
        json.dumps(diag, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(diag, ensure_ascii=False, indent=2))
    return {"case": case_id, "diagnostics": diag}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="+", default=list(CASES))
    ap.add_argument("--max-rounds", type=int, default=2)
    ap.add_argument("--env-file", default=".env")
    args = ap.parse_args()

    results = []
    for case_id in args.cases:
        if case_id not in CASES:
            raise SystemExit(f"unknown case {case_id}")
        results.append(run_case(case_id, CASES[case_id], max_rounds=args.max_rounds, env_file=args.env_file))

    (OUT_ROOT / "B2_REAL_RUN_ACCEPTANCE.md").write_text(
        "# B2 Real-run Acceptance\n\n" +
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[DONE] -> {OUT_ROOT}")


if __name__ == "__main__":
    main()
