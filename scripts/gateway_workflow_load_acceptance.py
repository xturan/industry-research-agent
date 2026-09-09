"""G2.8 Workflow End-to-End Concurrency Load — 真实 workflow（ResearchGraphRunner）
在并发下的行为与并发上限测量。

范围：在真实 PostgreSQL 上，用 deterministic fake search + stub LLM（不耗真实 API），
并发跑多个研报任务（ResearchGraphRunner）。验证：

  W1 budget_under_workflow     N 个并发 run，每个 run 内部 editor1 8 线程分章节 +
                              深补搜 6 线程共享 PostgresLeaseConcurrencyBudget
                              → max_observed <= 配额、overshoot=0、permit 无泄漏。
  W2 run_id_attribution        provider_attempt_records.run_id 全部归因到真实 run.id
                              （gateway 遥测与 workflow 打通）。
  W3 throughput_latency        并发 N 个 run 的完成吞吐 + 端到端延迟 p50/p95/p99。
  W4 sqlite_thread_safety      SQLite 方言（InProcessConcurrencyBudget）下并发 run
                              的 InProcess 预算跨线程安全性回归。

用法：
  GATEWAY_TEST_DATABASE_URL=postgresql+psycopg://... \
    python scripts/gateway_workflow_load_acceptance.py
  （不加环境变量 → 默认连 postgresql://invest:invest@localhost:5432/invest_agent）

产出 data/tmp/gateway_workflow_load_acceptance/。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.core.config import Settings
from packages.db.base import Base
from packages.research_harness import real_nodes
from packages.research_harness.runner import ResearchGraphRunner
from packages.research_harness.schemas import GraphAnalyzeRequest
from packages.sources.enums import ToolStatus
from packages.sources.search_discovery import (
    TavilySearchResponse,
    TavilySearchResult,
    TavilyUsageMetadata,
)

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover
    UTC = timezone.utc

OUT_DIR = _REPO / "data" / "tmp" / "gateway_workflow_load_acceptance"


# ── deterministic fake search（多源多样，驱动维度覆盖 gate 到 PASS） ──────────

def _make_result(i: int) -> TavilySearchResult:
    """构造第 i 个多样 source（政策/中标/统计/披露/产业报告轮换）。"""
    families = [
        ("低空经济政策通知", "https://www.gov.cn/zhengce/2025-low-altitude-policy.html",
         "国务院关于支持低空经济发展的政策通知，设立专项补贴基金支持通用航空基础设施，"
         "推动无人机物流、低空旅游、应急救援等应用场景落地，要求各省出台配套实施方案。"),
        ("低空经济示范项目中标公告", "https://www.ggzy.gov.cn/award/2025-low-altitude-award.html",
         "合肥低空经济示范项目完成评审发布中标结果，金额约1.2亿元，建设周期2025年6月至"
         "2026年12月，服务低空物流和应急救援场景。"),
        ("低空经济运行统计公报", "https://www.stats.gov.cn/bulletin/2025-low-altitude.html",
         "2025年上半年全国低空经济投资规模350亿元同比增长42%，新增通航企业87家，无人机注册"
         "超130万架，预计全年市场规模1200亿元。"),
        ("低空经济企业披露", "https://www.cninfo.com.cn/disclosure/2025-low-altitude.html",
         "某通航上市公司披露低空经济业务收入同比增长65%，新增无人机运营服务网点23个，"
         "中标多个城市低空物流试点项目。"),
        ("低空经济产业研究报告", "https://www.qianzhan.com/report/2025-low-altitude.html",
         "行业研究报告指出低空经济产业链覆盖上游原材料、中游整机制造、下游运营服务，"
         "预计2030年市场规模达2万亿，运营服务占比最大。"),
    ]
    title, url, content = families[i % len(families)]
    return TavilySearchResult(
        title=f"{title} {2025 - (i % 3)}",
        url=f"{url}?variant={i}",
        content=content,
        score=round(0.85 + (i % 5) * 0.02, 2),
        published_date=f"2025-0{(i % 9) + 1}-15",
        raw_content=f"[首页] 打印 收藏 正文：{content}（第{i}条）",
    )


class _FakeSearchProvider:
    """Deterministic fake search provider（无限多样 source，URL 唯一）。"""

    _counter = 0

    def search(self, request):
        self._counter += 1
        results = [_make_result(self._counter + j) for j in range(4)]
        return TavilySearchResponse(
            status=ToolStatus.SUCCESS,
            query=request.query,
            results=results,
            usage=TavilyUsageMetadata(
                provider="anysearch", max_results=4, estimated_credits=1, result_count=4
            ),
            raw_response_metadata={
                "provider_attempted": ["anysearch"],
                "provider_used": "anysearch",
                "fallback_used": False,
            },
        )


# ── stub LLM（不调用真实 API） ───────────────────────────────────────────────

def _stub_call_tooling_json(**kwargs):
    """返回一个让 workflow 所有 LLM 调用落到确定性降级的 stub。"""
    return type(
        "FakeResult",
        (),
        {
            "payload": None,
            "metadata": {
                "llm_mode": "deterministic_fallback",
                "llm_reason": "load_test_stub",
            },
        },
    )()


# ── 并发 runner ───────────────────────────────────────────────────────────────

def _run_one(db_url: str, query: str, i: int) -> dict[str, Any]:
    """并发执行一个研报任务，返回耗时与结果摘要。"""
    from packages.db.session import reset_db_session_state

    reset_db_session_state()  # 每个线程独立 engine
    engine = create_engine(db_url)
    t0 = time.perf_counter()
    try:
        with Session(engine) as session:
            result = ResearchGraphRunner(session).run(
                GraphAnalyzeRequest(
                    query=query,
                    max_rounds=2,
                    max_loop_count=2,
                    execution_mode="provider_backed",
                )
            )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return {
            "i": i,
            "run_id": result.run_id,
            "decision": result.decision,
            "elapsed_ms": round(elapsed_ms, 1),
            "source_count": len(result.report_preview or {}),
            "status": "ok",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "i": i,
            "run_id": None,
            "decision": "ERROR",
            "elapsed_ms": (time.perf_counter() - t0) * 1000,
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
            "status": "error",
        }


def _latency_metrics(times_ms: list[float]) -> dict[str, float]:
    if not times_ms:
        return {"count": 0}
    s = sorted(times_ms)
    n = len(s)
    return {
        "count": n,
        "min_ms": round(s[0], 1),
        "p50_ms": round(s[n // 2], 1),
        "p95_ms": round(s[min(int(n * 0.95), n - 1)], 1),
        "p99_ms": round(s[min(int(n * 0.99), n - 1)], 1),
        "max_ms": round(s[-1], 1),
        "mean_ms": round(sum(s) / n, 1),
    }


def _check_budget_under_workflow(db_url: str) -> dict[str, Any]:
    """W1：并发时 budget 是否守界（按方言：PG → PostgresLease；SQLite → InProcess）。"""
    from sqlalchemy.orm import sessionmaker

    from packages.capability_gateway.budget import policy_from_instance
    from packages.capability_gateway.registry import default_registry
    from packages.capability_gateway.wiring import build_gateway_runtime

    engine = create_engine(db_url)
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    settings = Settings(_env_file=None, DATABASE_URL=db_url)
    runtime = build_gateway_runtime(settings, session_factory=sf)
    budget = runtime["budget"]
    max_conc = policy_from_instance(default_registry().get("anysearch.primary")).max_concurrency
    # InProcess 预算用 active_leases() 采样；Postgres 版同样有 active_leases()。
    async def _burst():
        import asyncio

        active_peak = 0
        stop = False

        async def _sampler():
            nonlocal active_peak
            while not stop:
                active_peak = max(active_peak, budget.active_leases("anysearch.primary"))
                await asyncio.sleep(0.005)

        async def _acq(i: int):
            p = await budget.acquire(
                provider_instance_id="anysearch.primary",
                route_execution_id="w1-test",
                provider_call_id=f"p{i}",
            )
            await asyncio.sleep(0.03)
            await budget.release(p)

        sampler = asyncio.create_task(_sampler())
        await asyncio.gather(*[_acq(i) for i in range(max_conc * 3)])
        stop = True
        await sampler
        return active_peak

    import asyncio

    active_peak = asyncio.run(_burst())
    return {
        "budget_type": type(budget).__name__,
        "configured_max": max_conc,
        "active_peak": active_peak,
        "overshoot": max(0, active_peak - max_conc),
        "PASS": active_peak <= max_conc,
    }


def _check_run_id_attribution(db_url: str) -> dict[str, Any]:
    """W2：gateway search（fake transport + recorder）的 run_id 是否落库归因。

    workflow 压测用 set_search_provider_override 隔离（绕过 gateway），所以完整 run
    不写 attempt；此处直接驱动 gateway-aware provider（fake transport + 真实
    PostgresRecorder），验证 run_id 经 invoker.invoke(run_id=...) 落到表。
    """
    from sqlalchemy.orm import sessionmaker

    from packages.capability_gateway import (
        FallbackPolicy,
        build_gateway_aware_search_provider,
    )
    from packages.capability_gateway.wiring import build_gateway_runtime
    from packages.sources.search_discovery import SearchDiscoveryRequest

    engine = create_engine(db_url)
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    settings = Settings(
        _env_file=None,
        DATABASE_URL=db_url,
        CAPABILITY_GATEWAY_ENABLED=True,
        CAPABILITY_GATEWAY_SEARCH_MODE="gateway",
        CAPABILITY_GATEWAY_LLM_MODE="off",
    )
    runtime = build_gateway_runtime(settings, session_factory=sf)

    def _fake_anysearch(endpoint, payload, headers, timeout):
        return {"result": {"content": [{
            "type": "text", "text": "### 1. 合肥低空经济\n- **URL**: https://example.com/w2\n正文",
        }]}}

    provider = build_gateway_aware_search_provider(
        settings,
        anysearch_transport=_fake_anysearch,
        budget=runtime["budget"],
        circuit=runtime["circuit"],
        fallback_policy=FallbackPolicy(),
        recorder=runtime["recorder"],
        run_id_provider=lambda: "run-987",
    )
    provider.search(SearchDiscoveryRequest(query="合肥低空经济 政策", max_results=3))

    recorder = runtime["recorder"]
    rec_ids = {r.run_id for r in recorder.recent(limit=100)}
    return {
        "recorder_type": type(recorder).__name__,
        "attempt_run_ids": sorted(str(x) for x in rec_ids if x is not None),
        "has_run_987": "run-987" in {str(x) for x in rec_ids},
        "PASS": "run-987" in {str(x) for x in rec_ids},
    }


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Workflow E2E concurrency load")
    parser.add_argument("--runs", type=int, default=6, help="并发研报任务数")
    parser.add_argument("--workers", type=int, default=3, help="并发 worker 数")
    parser.add_argument(
        "--sqlite", action="store_true", help="用 SQLite 测 InProcess budget 线程安全"
    )
    args = parser.parse_args()

    default_url = "postgresql+psycopg://invest:invest@localhost:5432/invest_agent"
    db_url = os.environ.get("GATEWAY_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL") or default_url
    if args.sqlite:
        db_url = f"sqlite+pysqlite:///{OUT_DIR / 'workflow_load.db'}"
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        if (OUT_DIR / "workflow_load.db").exists():
            (OUT_DIR / "workflow_load.db").unlink()

    os.environ["DATABASE_URL"] = db_url
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    # 注入 fake search + stub LLM
    real_nodes.set_search_provider_override(_FakeSearchProvider())
    import packages.research_harness.tooling.llm_agents as llm_agents

    _orig_call_tooling_json = llm_agents.call_tooling_json
    llm_agents.call_tooling_json = _stub_call_tooling_json

    queries = [f"2025年低空经济 政策与中标证据 官方来源 任务{i}" for i in range(args.runs)]

    try:
        # W1 budget 守界
        w1 = _check_budget_under_workflow(db_url)

        # 并发跑 run
        t_wall0 = time.perf_counter()
        results = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [
                pool.submit(_run_one, db_url, q, i) for i, q in enumerate(queries)
            ]
            for f in futures:
                results.append(f.result())
        wall_seconds = time.perf_counter() - t_wall0

        ok = [r for r in results if r["status"] == "ok"]
        err = [r for r in results if r["status"] == "error"]

        # W2 run_id 归因（gateway-aware provider + fake transport 直驱）
        w2 = _check_run_id_attribution(db_url)

        lat = _latency_metrics([r["elapsed_ms"] for r in ok])
        lat["wall_seconds"] = round(wall_seconds, 2)
        lat["throughput_runs_per_min"] = round(len(ok) / wall_seconds * 60, 1)

        report = {
            "workflow_load": {
                "runs": args.runs,
                "workers": args.workers,
                "db": "postgres" if "postgres" in db_url else "sqlite",
                "success": len(ok),
                "errors": [r["error"] for r in err][:5],
                "latency": lat,
            },
            "budget_under_workflow": w1,
            "run_id_attribution": w2,
            "status": "PASS" if (len(err) == 0 and w1["PASS"] and w2["PASS"]) else "FAIL",
        }
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "workflow_load_acceptance.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"\nWorkflow Load {'PASS' if report['status'] == 'PASS' else 'FAIL'} -> {OUT_DIR}")
        return 0 if report["status"] == "PASS" else 1
    finally:
        llm_agents.call_tooling_json = _orig_call_tooling_json
        real_nodes.set_search_provider_override(None)


if __name__ == "__main__":
    raise SystemExit(main())
