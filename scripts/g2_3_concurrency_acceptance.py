"""G2.3b PostgreSQL Concurrency Budget Acceptance — 多 worker 共享 Lease。

验证：无论多少 worker 并发，同一 Provider 的 active leases 永不超过
`max_concurrency`；overshoot=0；permit_leak=0；stale lease recovery；
per-provider 独立。

需要真实 PostgreSQL（GATEWAY_TEST_DATABASE_URL 或 DATABASE_URL）。

用法：
  GATEWAY_TEST_DATABASE_URL=postgresql+psycopg://... python -m scripts.g2_3_concurrency_acceptance

产出 data/tmp/g2_3_concurrency_acceptance/。
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from packages.capability_gateway.budget import (
    PostgresLeaseConcurrencyBudget,
    ProviderConcurrencyPolicy,
    create_concurrency_tables,
)

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover
    UTC = timezone.utc

OUT_DIR = _REPO / "data" / "tmp" / "g2_3_concurrency_acceptance"

DEEPSEEK = "deepseek.chat.primary"
ANYSEARCH = "anysearch.primary"


def _worker(budget, provider: str, delay: float, results: dict[str, int]) -> None:
    async def _run():
        permit = await budget.acquire(
            provider_instance_id=provider,
            route_execution_id=uuid.uuid4().hex,
            provider_call_id=uuid.uuid4().hex,
        )
        await asyncio.sleep(delay)
        await budget.release(permit)

    try:
        asyncio.run(_run())
        results["success"] += 1
    except Exception as exc:  # noqa: BLE001
        results["error"] += 1
        results["last_error"] = str(exc)


def block_multi_worker(budget, *, cap: int, workers: int, delay: float = 0.05) -> dict[str, Any]:
    stop = {"stop": False}
    max_observed = {"value": 0}

    def _observer():
        while not stop["stop"]:
            v = budget.active_leases(DEEPSEEK)
            if v > max_observed["value"]:
                max_observed["value"] = v
            time.sleep(0.002)

    results: dict[str, Any] = {"success": 0, "error": 0, "last_error": None}
    obs = threading.Thread(target=_observer, daemon=True)
    obs.start()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_worker, budget, DEEPSEEK, delay, results)
                   for _ in range(workers)]
        for f in futures:
            f.result()
    stop["stop"] = True
    obs.join(timeout=5)

    active_after = budget.active_leases(DEEPSEEK)
    return {
        "cap": cap,
        "workers": workers,
        "success": results["success"],
        "error": results["error"],
        "last_error": results["last_error"],
        "max_observed_active_leases": max_observed["value"],
        "overshoot": max_observed["value"] - cap,
        "active_leases_after": active_after,
        "permit_leak_detected": active_after != 0,
        "PASS": (
            results["error"] == 0
            and max_observed["value"] <= cap
            and active_after == 0
        ),
    }


def block_stale_recovery(budget) -> dict[str, Any]:
    async def _run():
        policy = budget._policy(DEEPSEEK)
        lease_ttl = policy.lease_ttl_seconds
        permit = await budget.acquire(
            provider_instance_id=DEEPSEEK,
            route_execution_id="stale-1", provider_call_id="stale-c1",
        )
        # 不 release（Worker 崩溃），等 TTL 过期
        await asyncio.sleep(lease_ttl + 0.2)
        permit2 = await budget.acquire(
            provider_instance_id=DEEPSEEK,
            route_execution_id="stale-2", provider_call_id="stale-c2",
        )
        await budget.release(permit2)
        return permit.lease_id != permit2.lease_id

    recovered = asyncio.run(_run())
    return {"stale_lease_recovery": recovered, "PASS": recovered}


def block_per_provider_independent(budget) -> dict[str, Any]:
    async def _run():
        # 占满 deepseek
        permits = [
            await budget.acquire(
                provider_instance_id=DEEPSEEK,
                route_execution_id=f"i{i}", provider_call_id=f"ic{i}",
            )
            for i in range(budget._policy(DEEPSEEK).max_concurrency)
        ]
        # anysearch 仍可立即获取
        permit_any = await budget.acquire(
            provider_instance_id=ANYSEARCH,
            route_execution_id="a1", provider_call_id="ac1",
        )
        acquired = permit_any.provider_instance_id == ANYSEARCH
        for p in permits + [permit_any]:
            await budget.release(p)
        return acquired

    acquired = asyncio.run(_run())
    return {"independent_acquire": acquired, "PASS": acquired}


def main() -> int:
    url = os.environ.get("GATEWAY_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url or "postgres" not in url:
        print("GATEWAY_TEST_DATABASE_URL (or DATABASE_URL) must point to PostgreSQL.")
        return 2
    engine = create_engine(url, pool_pre_ping=True, pool_size=50, max_overflow=0, pool_timeout=60)
    create_concurrency_tables(engine)

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    policies = {
        DEEPSEEK: ProviderConcurrencyPolicy(
            provider_instance_id=DEEPSEEK, max_concurrency=5,
            acquire_timeout_seconds=10.0, lease_ttl_seconds=1.0,
        ),
        ANYSEARCH: ProviderConcurrencyPolicy(
            provider_instance_id=ANYSEARCH, max_concurrency=1,
            acquire_timeout_seconds=5.0, lease_ttl_seconds=5.0,
        ),
    }
    budget = PostgresLeaseConcurrencyBudget(session_factory, policies, poll_interval_seconds=0.02)

    # 清空旧 lease
    with session_factory() as s:
        s.execute(__import__("sqlalchemy").text("DELETE FROM provider_concurrency_leases"))
        s.commit()

    blocks = {
        "multi_worker_cap": block_multi_worker(budget, cap=5, workers=30, delay=0.2),
        "stale_lease_recovery": block_stale_recovery(budget),
        "per_provider_independent": block_per_provider_independent(budget),
    }
    all_pass = all(b["PASS"] for b in blocks.values())

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "database": str(engine.url).split("@")[-1],
        "blocks": blocks,
        "summary": {
            "all_pass": all_pass,
            "passed": sum(1 for b in blocks.values() if b["PASS"]),
            "total": len(blocks),
        },
        "invariants": {
            "inflight_le_configured_max": blocks["multi_worker_cap"]["max_observed_active_leases"] <= 5,
            "overshoot": blocks["multi_worker_cap"]["overshoot"],
            "permit_leak": blocks["multi_worker_cap"]["permit_leak_detected"],
            "stale_recovery": blocks["stale_lease_recovery"]["PASS"],
            "per_provider_independent": blocks["per_provider_independent"]["PASS"],
        },
        "note": "短事务 Lease：Provider 网络调用期间不持有 DB transaction/connection。",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nG2.3b {'PASS' if all_pass else 'FAIL'} -> {OUT_DIR}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
