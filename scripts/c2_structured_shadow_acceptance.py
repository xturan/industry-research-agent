# ruff: noqa: E501
"""Phase C.2 — Structured Shadow Graph Acceptance (flag OFF vs ON).

Runs the SAME query through the provider-backed graph twice with
STRUCTURED_DRAFT_SHADOW_ENABLED off/on, using a DETERMINISTIC main-path stub
(fixed search provider + stubbed LLM) so the only intended difference is the
structured_shadow_editor1 node. The shadow node reads only the MAIN evaluation
store and writes only `structured_draft_shadow`.

Output (per case):
  data/tmp/c2_structured_shadow_acceptance/{case}/off_state.json on_state.json
  summary.json  C2_STRUCTURED_SHADOW_ACCEPTANCE.md

Run:
  python scripts/c2_structured_shadow_acceptance.py --cases case_01 case_02
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.session import reset_db_session_state
from packages.research_harness import real_nodes
from packages.research_harness.runner import ResearchGraphRunner
from packages.research_harness.schemas import GraphAnalyzeRequest

REPO = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO / "data" / "tmp" / "c2_structured_shadow_acceptance"

CASES = {
    "case_01": "2025 年合肥低空物流项目的落地进展、运营状态及官方证据",
    "case_02": "2025 年合肥低空经济相关上市公司的项目收入及订单贡献",
}

MAIN_STATE_KEYS = [
    "sources", "evidence", "claims", "documents", "approved_claims",
    "coverage_report", "quality_scores", "plan",
]
EDITOR1_INPUT_KEYS = ["query", "plan", "sources", "evidence", "claims"]


class _DeterministicSearchProvider:
    def search(self, request):
        from packages.sources.search_discovery import (
            TavilySearchResponse,
            TavilySearchResult,
            TavilyUsageMetadata,
        )

        query = str(request.query or "")
        include = " ".join(request.include_domains or [])
        results = []
        if "ggzy.gov.cn" in include or "ccgp.gov.cn" in include:
            results.append(TavilySearchResult(
                title="低空经济示范项目中标公告 2025",
                url="https://www.ggzy.gov.cn/award/2025-low-altitude-award.html",
                content="公共资源交易中心发布低空经济示范项目中标公告，合肥低空物流项目中标公示，金额1.2亿元。",
                score=0.93, published_date="2025-05-20",
                raw_content="[首页] 中标公告正文：合肥低空物流项目完成评审并发布结果，中标金额1.2亿元。",
            ))
        else:
            results.append(TavilySearchResult(
                title="低空经济政策通知 2025",
                url="https://www.gov.cn/zhengce/2025-low-altitude-policy.html",
                content="国务院有关低空经济政策通知，支持低空物流应用场景建设，合肥列入试点。",
                score=0.91, published_date="2025-01-15",
                raw_content="[首页] 政策正文：支持低空经济应用场景建设，合肥低空物流列入试点。",
            ))
        return TavilySearchResponse(
            status="success", query=query, results=results,
            usage=TavilyUsageMetadata(
                search_depth="basic", max_results=request.max_results or 5,
                estimated_credits=1, result_count=len(results),
                request_params={"query": query},
            ),
        )

    def search_task(self, task):
        return []


class _FakeLLMResult:
    def __init__(self) -> None:
        self.payload = None
        self.metadata = {
            "llm_mode": "deterministic_fallback",
            "llm_reason": "c2_structured_shadow_acceptance_stub",
        }


def _hash_value(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _extract_final_state(db_path: Path) -> dict:
    import sqlite3

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT state_json FROM research_graph_checkpoints ORDER BY id DESC"
    ).fetchall()
    con.close()
    for row in rows:
        state = json.loads(row["state_json"] or "{}")
        if isinstance(state, dict) and state.get("run_id"):
            return state
    return {}


def _run_once(*, query: str, shadow_enabled: bool, db_path: Path) -> dict:
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path.as_posix()}"
    os.environ.setdefault("TAVILY_SEARCH_DEPTH", "basic")
    os.environ.setdefault("TAVILY_TIMEOUT_SECONDS", "30")
    get_settings.cache_clear()
    reset_db_session_state()

    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(engine)

    real_nodes.set_search_provider_override(_DeterministicSearchProvider())
    real_nodes.call_tooling_json = lambda **kwargs: _FakeLLMResult()
    # Advisory backfill stays OFF; structured shadow node toggled.
    real_nodes.set_advisory_backfill_override(enabled=False, mode="shadow")
    real_nodes.set_structured_shadow_override(enabled=shadow_enabled, mode="shadow")

    with Session(engine) as session:
        runner = ResearchGraphRunner(session)
        result = runner.run(
            GraphAnalyzeRequest(
                query=query, max_rounds=1, max_loop_count=1,
                execution_mode="provider_backed",
            )
        )
    state = _extract_final_state(db_path)
    return {
        "decision": result.decision,
        "termination_reason": state.get("evaluation_termination_reason"),
        "shadow": state.get("structured_draft_shadow"),
        "state": state,
    }


def _normalize_state(state: dict) -> dict:
    normalized = dict(state)
    for key in ("drafts",):
        drafts = []
        for draft in state.get(key) or []:
            d = dict(draft)
            d.pop("draft_id", None)
            drafts.append(d)
        normalized[key] = drafts
    return normalized


def _compare(off: dict, on: dict) -> dict:
    off_state = _normalize_state(off["state"])
    on_state = _normalize_state(on["state"])

    def _snap(state, keys):
        return {k: state.get(k) for k in keys}

    main_changed = _hash_value(_snap(off_state, MAIN_STATE_KEYS)) != _hash_value(
        _snap(on_state, MAIN_STATE_KEYS)
    )
    editor1_changed = _hash_value(_snap(off_state, EDITOR1_INPUT_KEYS)) != _hash_value(
        _snap(on_state, EDITOR1_INPUT_KEYS)
    )
    rm_changed = (off_state.get("report_markdown") or "") != (
        on_state.get("report_markdown") or ""
    )
    fr_changed = off_state.get("final_report") != on_state.get("final_report")

    shadow = on.get("shadow") or {}
    return {
        "main_state_changed": main_changed,
        "formal_editor1_input_changed": editor1_changed,
        "report_markdown_changed": rm_changed,
        "final_report_changed": fr_changed,
        "shadow_draft_generated": shadow.get("status") == "completed",
        "shadow_validation_passed": bool(
            (shadow.get("validation_report") or {}).get("passed")
        ),
        "shadow_approved_claim_count": (shadow.get("editor1_input") or {}).get(
            "approved_claim_count", 0
        ),
        "off_termination_reason": off.get("termination_reason"),
        "on_termination_reason": on.get("termination_reason"),
    }


def run_case(case_id: str, query: str) -> dict:
    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{case_id}] running shadow OFF ...")
    off = _run_once(query=query, shadow_enabled=False, db_path=out_dir / "off.db")
    print(f"[{case_id}] running shadow ON ...")
    on = _run_once(query=query, shadow_enabled=True, db_path=out_dir / "on.db")

    (out_dir / "off_state.json").write_text(
        json.dumps(off["state"], ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "on_state.json").write_text(
        json.dumps(on["state"], ensure_ascii=False, indent=2), encoding="utf-8")

    comparison = _compare(off, on)
    (out_dir / "summary.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    return {"case": case_id, "comparison": comparison}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="+", default=list(CASES))
    args = ap.parse_args()

    results = []
    for case_id in args.cases:
        if case_id not in CASES:
            raise SystemExit(f"unknown case {case_id}")
        results.append(run_case(case_id, CASES[case_id]))

    (OUT_ROOT / "C2_STRUCTURED_SHADOW_ACCEPTANCE.md").write_text(
        "# Phase C.2 Structured Shadow Graph Acceptance (flag OFF vs ON)\n\n"
        + json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[DONE] -> {OUT_ROOT}")


if __name__ == "__main__":
    main()
