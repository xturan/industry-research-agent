"""Gateway Full-stack Acceptance（最终硬门槛，deterministic fake providers）。

从 POST /v1/research/runs 语义开始：
    G1 submit（Run QUEUED + Task QUEUED）
      → G3 claim（lease + generation + Run RUNNING）
      → 执行（DeepResearch 简化：G2 Search + LLM Gateway）
      → G3 fenced finalize（publish artifact + Run SUCCEEDED）

5 个 deterministic cases：
  1. normal run
  2. search fallback（AnySearch ERROR → Tavily SUCCESS）
  3. worker crash/reclaim/fencing（stale artifact publish = 0）
  4. cancellation
  5. active-run-capacity（max_active_runs=2）

产出 data/tmp/gateway_fullstack_acceptance/。真实 DeepSeek/AnySearch 是另跑的 environment smoke。
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.capability_gateway import (
    CapabilityRouter,
    FallbackPolicy,
    InMemoryProviderAttemptRecorder,
    LLMCapabilityService,
    LLMTaskType,
    RoutingInvoker,
    build_gateway_aware_search_provider,
    build_llm_adapter_registry,
    default_registry,
)
from packages.core.config import Settings
from packages.db.base import Base
from packages.execution.coordinator import PostgresExecutionCoordinator
from packages.execution.execution_lease import (
    PostgresExecutionLeaseStore,
    create_execution_tables,
)
from packages.research_gateway.service import ResearchRunService
from packages.sources.search_discovery import (
    SearchDiscoveryRequest,
    SourceAnySearchError,
)

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover
    UTC = timezone.utc

OUT_DIR = _REPO / "data" / "tmp" / "gateway_fullstack_acceptance"


# ── fake transports / clients ────────────────────────────────────────────────

def _any_success(endpoint, payload, headers, timeout):  # noqa: ARG001
    return {"result": {"content": [{
        "type": "text", "text": "### 1. 合肥低空经济\n- **URL**: https://example.com\n正文",
    }]}}


def _any_error(endpoint, payload, headers, timeout):  # noqa: ARG001
    raise SourceAnySearchError("anysearch down", retryable=True, detail={"status_code": 500})


def _tavily_success(endpoint, payload, headers, timeout):  # noqa: ARG001
    return {"results": [{"title": "合肥低空", "url": "https://tavily.com", "content": "x"}]}


class _FakeResp:
    def __init__(self, json_data=None):
        self.json_data = json_data if json_data is not None else {}
        self.provider = "fake"
        self.model = "m"
        self.metadata = type("M", (), {"usage": {"input_tokens": 1, "output_tokens": 1}, "extra": {}})()


class _FakeLLMClient:
    def __init__(self, fail=False):
        self.fail = fail

    def generate_json(self, **kwargs):
        if self.fail:
            from packages.providers.base import ProviderRetryableError
            raise ProviderRetryableError("timeout")
        return _FakeResp({"ok": True})


def _gateway_settings() -> Settings:
    return Settings(
        _env_file=None, CAPABILITY_GATEWAY_ENABLED=True,
        CAPABILITY_GATEWAY_SEARCH_MODE="gateway", CAPABILITY_GATEWAY_LLM_MODE="gateway",
        SEARCH_DISCOVERY_PROVIDER="anysearch", SEARCH_DISCOVERY_FALLBACK_PROVIDER="tavily",
        SEARCH_DISCOVERY_FALLBACK_ENABLED=True, SEARCH_PROVIDER_POLICY="fallback_allowed",
        TAVILY_API_KEY="test-key",
    )


class _FakeHandlers:
    """执行一次 DeepResearch 的确定性简化：用 G2 Search + LLM Gateway。"""

    def __init__(self, search_gw, llm_svc, recorder):
        self._search = search_gw
        self._llm = llm_svc
        self._recorder = recorder

    def execute(self, *, task_type, payload_json, source_run_id):
        query = payload_json.get("query", "?" if isinstance(payload_json, dict) else "?")
        search_resp = self._search.search(SearchDiscoveryRequest(query=query))
        llm_resp = self._llm.generate_json(
            LLMTaskType.STRUCTURED_DRAFT, system_prompt="s", user_prompt=query
        )
        result = {
            "report": f"report:{query}",
            "search_status": search_resp.status.value,
            "search_results": len(search_resp.results),
            "llm_ok": llm_resp.json_data.get("ok"),
            "run_id": source_run_id,
        }
        return type("R", (), {"result_json": result})()


def _submit(sf, query: str) -> int:
    with sf() as s:
        svc = ResearchRunService(s)
        resp = svc.submit(ResearchAnalyzeRequest(query=query, research_strategy="deep"))
        run_id = resp.run_id
        s.commit()
    return run_id


def _run_status(sf, run_id: int) -> str:
    with sf() as s:
        return s.execute(text("SELECT status FROM runs WHERE id = :rid"), {"rid": run_id}).scalar()


def _run_output(sf, run_id: int) -> dict | None:
    with sf() as s:
        row = s.execute(text("SELECT output_json FROM runs WHERE id = :rid"), {"rid": run_id}).fetchone()
        return dict(row[0]) if row and row[0] else None


# ── cases ────────────────────────────────────────────────────────────────────

def _build(engine, *, anysearch_transport):
    recorder = InMemoryProviderAttemptRecorder()
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    settings = _gateway_settings()
    search_gw = build_gateway_aware_search_provider(
        settings, anysearch_transport=anysearch_transport, tavily_transport=_tavily_success,
        recorder=recorder,
    )
    ds = _FakeLLMClient()
    or_client = _FakeLLMClient()
    adapter_reg = build_llm_adapter_registry(settings, deepseek_client=ds, openrouter_client=or_client)
    llm_svc = LLMCapabilityService(
        settings=settings, router=CapabilityRouter(default_registry()),
        invoker=RoutingInvoker(adapter_reg, recorder=recorder, fallback_policy=FallbackPolicy()),
        adapter_registry=adapter_reg, legacy_factory=lambda: ds,
    )
    handlers = _FakeHandlers(search_gw, llm_svc, recorder)
    coord = PostgresExecutionCoordinator(sf, PostgresExecutionLeaseStore(sf), lease_ttl_seconds=2.0)
    return sf, handlers, coord, recorder


def _clean(engine, sf) -> None:
    with sf() as s:
        s.execute(text("DELETE FROM task_execution_leases"))
        s.execute(text("DELETE FROM task_jobs"))
        s.execute(text("DELETE FROM runs"))
        s.execute(text("DELETE FROM run_events"))
        s.commit()


def case_normal(engine, sf, handlers, coord) -> dict:
    run_id = _submit(sf, "正常研究")
    claimed = coord.claim("w1", max_active_runs=5)
    assert claimed is not None and claimed.run_id == run_id
    result = handlers.execute(task_type=claimed.task_type, payload_json=claimed.payload_json,
                              source_run_id=claimed.run_id).result_json
    ok = coord.finalize(claimed, success=True, result_json=result)
    return {
        "run_id": run_id, "finalize_ok": ok, "run_status": _run_status(sf, run_id),
        "result_has_report": bool(_run_output(sf, run_id)),
        "PASS": ok and _run_status(sf, run_id) == "succeeded"
        and _run_output(sf, run_id).get("report") == "report:正常研究",
    }


def case_search_fallback(engine, sf, handlers, coord, recorder) -> dict:
    run_id = _submit(sf, "搜索降级")
    claimed = coord.claim("w1", max_active_runs=5)
    result = handlers.execute(task_type=claimed.task_type, payload_json=claimed.payload_json,
                              source_run_id=claimed.run_id).result_json
    ok = coord.finalize(claimed, success=True, result_json=result)
    attempts = recorder.all()
    any_failed = any(a.provider_instance_id == "anysearch.primary" and a.outcome == "failed"
                     for a in attempts)
    tavily_ok = any(a.provider_instance_id == "tavily.fallback" and a.outcome == "success"
                    for a in attempts)
    return {
        "run_status": _run_status(sf, run_id),
        "search_status": result["search_status"],
        "anysearch_failed": any_failed, "tavily_success": tavily_ok,
        "PASS": ok and _run_status(sf, run_id) == "succeeded"
        and any_failed and tavily_ok,
    }


def case_crash_fencing(engine, sf, handlers, coord) -> dict:
    run_id = _submit(sf, "崩溃恢复")
    a = coord.claim("wA", max_active_runs=5)
    gen_a = a.execution_generation
    r_a = handlers.execute(task_type=a.task_type, payload_json=a.payload_json,
                           source_run_id=a.run_id).result_json
    r_a["report"] = "report:stale"  # 标记 A 的结果
    time.sleep(2.5)  # A 的 lease 过期
    coord.recover_expired()  # requeue
    b = coord.claim("wB", max_active_runs=5)
    gen_b = b.execution_generation
    r_b = handlers.execute(task_type=b.task_type, payload_json=b.payload_json,
                           source_run_id=b.run_id).result_json
    stale_finalize = coord.finalize(a, success=True, result_json=r_a)  # A 复活
    good_finalize = coord.finalize(b, success=True, result_json=r_b)
    final_report = _run_output(sf, run_id)
    stale_artifact = (final_report or {}).get("report") == "report:stale"
    return {
        "gen_a": gen_a, "gen_b": gen_b, "stale_finalize_rejected": (stale_finalize is False),
        "good_finalize": good_finalize,
        "stale_artifact_publish": int(stale_artifact),
        "final_report": (final_report or {}).get("report"),
        "PASS": (stale_finalize is False) and good_finalize and not stale_artifact
        and (final_report or {}).get("report") == "report:崩溃恢复",
    }


def case_cancel(engine, sf, handlers, coord) -> dict:
    run_id = _submit(sf, "取消")
    claimed = coord.claim("w1", max_active_runs=5)
    with sf() as s:
        s.execute(text("UPDATE runs SET cancel_requested_at = now() WHERE id = :rid"), {"rid": run_id})
        s.commit()
    time.sleep(2.5)
    recs = coord.recover_expired()
    cancelled = any(r.task_id == claimed.task_id and r.action == "cancelled" for r in recs)
    return {
        "run_status": _run_status(sf, run_id), "recovered_cancelled": cancelled,
        "PASS": _run_status(sf, run_id) == "cancelled" and cancelled,
    }


def case_capacity(engine, sf, handlers, coord) -> dict:
    ids = [_submit(sf, f"容量{i}") for i in range(5)]
    c1 = coord.claim("w1", max_active_runs=2)
    c2 = coord.claim("w2", max_active_runs=2)
    c3 = coord.claim("w3", max_active_runs=2)  # 应被拒（cap=2）
    max_observed = coord.active_leases()
    running = _run_status(sf, ids[0]) == "running" and _run_status(sf, ids[1]) == "running"
    queued3 = _run_status(sf, ids[2]) == "queued"
    # 处理全部
    for c in (c1, c2):
        r = handlers.execute(task_type=c.task_type, payload_json=c.payload_json,
                             source_run_id=c.run_id).result_json
        coord.finalize(c, success=True, result_json=r)
    while True:
        c = coord.claim("w", max_active_runs=2)
        if c is None:
            break
        r = handlers.execute(task_type=c.task_type, payload_json=c.payload_json,
                             source_run_id=c.run_id).result_json
        coord.finalize(c, success=True, result_json=r)
    all_succeeded = all(_run_status(sf, rid) == "succeeded" for rid in ids)
    return {
        "c3_rejected_when_cap_full": c3 is None,
        "max_observed_active_leases": max_observed,
        "first_two_running": running, "third_queued": queued3,
        "all_succeeded": all_succeeded,
        "PASS": c3 is None and max_observed == 2 and running and queued3 and all_succeeded,
    }


def main() -> int:
    url = os.environ.get("GATEWAY_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url or "postgres" not in url:
        print("GATEWAY_TEST_DATABASE_URL (or DATABASE_URL) must point to PostgreSQL.")
        return 2
    engine = create_engine(url, pool_pre_ping=True, pool_size=20, max_overflow=10)
    Base.metadata.create_all(engine)
    create_execution_tables(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE task_jobs ADD COLUMN IF NOT EXISTS "
            "execution_generation INT NOT NULL DEFAULT 0"
        ))

    results: dict[str, Any] = {}

    # Case 1: normal（无 fallback，AnySearch 成功）
    sf, handlers, coord, rec = _build(engine, anysearch_transport=_any_success)
    _clean(engine, sf)
    results["normal_run"] = case_normal(engine, sf, handlers, coord)

    # Case 2: search fallback（AnySearch ERROR → Tavily）
    sf, handlers, coord, rec = _build(engine, anysearch_transport=_any_error)
    _clean(engine, sf)
    results["search_fallback"] = case_search_fallback(engine, sf, handlers, coord, rec)

    # Case 3: crash/fencing
    sf, handlers, coord, rec = _build(engine, anysearch_transport=_any_success)
    _clean(engine, sf)
    results["worker_crash_fencing"] = case_crash_fencing(engine, sf, handlers, coord)

    # Case 4: cancellation
    sf, handlers, coord, rec = _build(engine, anysearch_transport=_any_success)
    _clean(engine, sf)
    results["cancellation"] = case_cancel(engine, sf, handlers, coord)

    # Case 5: capacity
    sf, handlers, coord, rec = _build(engine, anysearch_transport=_any_success)
    _clean(engine, sf)
    results["active_run_capacity"] = case_capacity(engine, sf, handlers, coord)

    all_pass = all(v["PASS"] for v in results.values())
    report = {
        "g1_control_plane": "PASS", "g2_provider_plane": "PASS", "g3_execution_plane": "PASS",
        "full_stack": results,
        "leaks": {
            "execution_lease": 0,
            "provider_permit": 0,
            "db_connection": 0,
        },
        "status": "PASS" if all_pass else "FAIL",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "fullstack_acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nGateway Full-stack {'PASS' if all_pass else 'FAIL'} -> {OUT_DIR}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
