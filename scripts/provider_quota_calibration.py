"""Provider Quota Calibration — 真实 API 配额压测，把 max_concurrency 从估算变实测。

目标：对每个真实 provider（DeepSeek/AnySearch/OpenRouter），递增并发打真实调用，
记录 success / 429 / timeout / error 率与延迟，测出「触发限流的临界并发」，
反推安全并发（临界 × 0.6，留余量）。

⚠️ 消耗真实 API 额度（DeepSeek tokens / AnySearch queries / OpenRouter free quota）。
建议：-max-total 限制总调用数，-concurrency-max 限制最大并发档位。

用法：
  python scripts/provider_quota_calibration.py [--provider deepseek|anysearch|openrouter]
                                             [--concurrency-max 30] [--max-total 200]
                                             [--pause 2]

输出 data/tmp/provider_quota_calibration/<provider>.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover
    UTC = timezone.utc

OUT_DIR = _REPO / "data" / "tmp" / "provider_quota_calibration"


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_file = _REPO / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _classify(exc: Exception) -> str:
    name = type(exc).__name__
    cls = exc.__class__
    module = cls.__module__
    # 429 rate limit
    if "RateLimit" in name or "429" in str(exc):
        return "rate_limit"
    if "Timeout" in name or isinstance(exc, TimeoutError):
        return "timeout"
    if "Auth" in name or "401" in str(exc) or "403" in str(exc):
        return "auth"
    if module.startswith("packages.sources"):
        detail = getattr(exc, "detail", None) or {}
        sc = detail.get("status_code") if isinstance(detail, dict) else None
        if sc == 429:
            return "rate_limit"
        if sc == 401 or sc == 403:
            return "auth"
        if isinstance(sc, int) and sc >= 500:
            return "provider_5xx"
    return "error"


# ── DeepSeek ──────────────────────────────────────────────────────────────────

def _build_deepseek(env: dict[str, str]) -> Any:
    from packages.core.config import Settings
    from packages.providers.deepseek import DeepSeekProviderClient

    s = Settings(_env_file=None)
    s.deepseek_api_key = env.get("DEEPSEEK_API_KEY")
    return DeepSeekProviderClient(
        api_key=s.deepseek_api_key,
        base_url=s.deepseek_base_url,
        model=s.deepseek_research_model,
        timeout_seconds=30,
        max_retries=0,
        max_tokens=300,
    )


def _deepseek_call(client: Any) -> tuple[str, float]:
    t0 = time.perf_counter()
    try:
        client.generate_json(
            system_prompt="你是测试助手。只输出 JSON。",
            user_prompt='输出 {"ok": true}',
        )
        return "success", (time.perf_counter() - t0) * 1000
    except Exception as exc:  # noqa: BLE001
        return _classify(exc), (time.perf_counter() - t0) * 1000


# ── AnySearch ─────────────────────────────────────────────────────────────────

def _build_anysearch(env: dict[str, str]) -> Any:
    from packages.core.config import Settings
    from packages.sources.search_discovery import (
        AnySearchSearchAdapter,
        anysearch_settings_from_app_settings,
    )

    s = Settings(_env_file=None)
    s.anysearch_api_key = env.get("ANYSEARCH_API_KEY")
    return AnySearchSearchAdapter(settings=anysearch_settings_from_app_settings(s))


def _anysearch_call(client: Any) -> tuple[str, float]:
    from packages.sources.search_discovery import SearchDiscoveryRequest

    t0 = time.perf_counter()
    try:
        resp = client.search(
            SearchDiscoveryRequest(query="2025年低空经济政策", max_results=3)
        )
        dt = (time.perf_counter() - t0) * 1000
        if resp.status.value == "success":
            return "success", dt
        # ERROR response：从 errors 的 detail 判断
        for err in resp.errors:
            detail = getattr(err, "detail", None) or {}
            sc = detail.get("status_code") if isinstance(detail, dict) else None
            if sc == 429:
                return "rate_limit", dt
            if sc == 401 or sc == 403:
                return "auth", dt
            if isinstance(sc, int) and sc >= 500:
                return "provider_5xx", dt
        return "error", dt
    except Exception as exc:  # noqa: BLE001
        return _classify(exc), (time.perf_counter() - t0) * 1000


# ── OpenRouter ────────────────────────────────────────────────────────────────

def _build_openrouter(env: dict[str, str]) -> Any:
    from packages.core.config import Settings
    from packages.providers.openrouter import OpenRouterProviderClient

    s = Settings(_env_file=None)
    s.openrouter_api_key = env.get("OPENROUTER_API_KEY")
    return OpenRouterProviderClient(
        api_key=s.openrouter_api_key,
        base_url=s.openrouter_base_url,
        model=s.openrouter_free_model,
        timeout_seconds=30,
        max_retries=0,
        max_tokens=200,
    )


def _openrouter_call(client: Any) -> tuple[str, float]:
    t0 = time.perf_counter()
    try:
        client.generate_json(
            system_prompt="你是测试助手。只输出 JSON。",
            user_prompt='输出 {"ok": true}',
        )
        return "success", (time.perf_counter() - t0) * 1000
    except Exception as exc:  # noqa: BLE001
        return _classify(exc), (time.perf_counter() - t0) * 1000


# ── 扫描 ─────────────────────────────────────────────────────────────────────

_BUILDERS = {
    "deepseek": (_build_deepseek, _deepseek_call, "deepseek"),
    "anysearch": (_build_anysearch, _anysearch_call, "anysearch"),
    "openrouter": (_build_openrouter, _openrouter_call, "openrouter"),
}


def _run_concurrency_level(
    builder, caller, level: int, total: int, pause: float
) -> dict[str, Any]:
    """在指定并发下打 total 个真实调用，统计结果分布。"""
    client = builder()
    outcomes: dict[str, int] = {}
    latencies: list[float] = []
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=level) as pool:
        futures = [pool.submit(caller, client) for _ in range(total)]
        for f in as_completed(futures):
            try:
                outcome, latency = f.result()
            except Exception as exc:  # noqa: BLE001
                outcome, latency = _classify(exc), 0.0
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            if outcome != "success":
                errors.append(outcome)
            latencies.append(latency)

    success = outcomes.get("success", 0)
    total_count = sum(outcomes.values()) or 1
    s = sorted(latencies)
    n = len(s)
    return {
        "concurrency": level,
        "total": total_count,
        "success": success,
        "success_rate": round(success / total_count, 4),
        "rate_limit": outcomes.get("rate_limit", 0),
        "timeout": outcomes.get("timeout", 0),
        "provider_5xx": outcomes.get("provider_5xx", 0),
        "auth": outcomes.get("auth", 0),
        "error": outcomes.get("error", 0),
        "latency_p50_ms": round(s[n // 2], 1) if n else None,
        "latency_p95_ms": round(s[min(int(n * 0.95), n - 1)], 1) if n else None,
    }


def _find_safe_concurrency(levels: list[dict[str, Any]]) -> int:
    """安全并发 = 最高全成功档位 × 0.6（留余量），至少 1。"""
    last_full_success = 1
    for level in levels:
        if level["success_rate"] >= 0.98 and level["rate_limit"] == 0:
            last_full_success = level["concurrency"]
        else:
            break
    safe = max(1, int(last_full_success * 0.6))
    return safe


def main() -> int:
    parser = argparse.ArgumentParser(description="Provider quota calibration")
    parser.add_argument("--provider", choices=list(_BUILDERS.keys()), default="deepseek")
    parser.add_argument("--concurrency-max", type=int, default=30)
    parser.add_argument("--max-total", type=int, default=200)
    parser.add_argument("--pause", type=float, default=1.5)
    args = parser.parse_args()

    env = _load_env()
    builder, caller, _name = _BUILDERS[args.provider]

    # builder 需要 env（真实 key）；包闭包传入
    bound_builder = lambda: builder(env)  # noqa: E731

    levels: list[dict[str, Any]] = []
    # 并发阶梯：1, 2, 4, 6, 8, 10, 14, 18, 24, 30（对数增长）
    ladder = [1, 2, 4, 6, 8, 10, 14, 18, 24, 30]
    ladder = [c for c in ladder if c <= args.concurrency_max]
    if not ladder:
        ladder = [1, 2]

    print(f"=== {args.provider} 配额校准（消耗真实 API 额度）===")
    for level in ladder:
        # 每档并发分配部分 total，随并发递增减少每档次数（保护额度）
        per_level = min(args.max_total // len(ladder), max(10, level * 2))
        result = _run_concurrency_level(bound_builder, caller, level, per_level, args.pause)
        print(
            f"  并发={level:2d} 总={result['total']:3d} "
            f"成功={result['success']:3d} ({result['success_rate']*100:.0f}%) "
            f"429={result['rate_limit']:3d} 超时={result['timeout']:3d} "
            f"5xx={result['provider_5xx']:3d} 其他={result['error']:3d} "
            f"p50={result['latency_p50_ms']}ms p95={result['latency_p95_ms']}ms"
        )
        levels.append(result)
        # 若已严重限流（<50% 成功），提前停止，不再浪费额度
        if result["success_rate"] < 0.5:
            print(f"  → 并发 {level} 已严重降级，停止递增")
            break
        time.sleep(args.pause)

    safe = _find_safe_concurrency(levels)
    full_success_max = max(
        (
            lv["concurrency"]
            for lv in levels
            if lv["success_rate"] >= 0.98 and lv["rate_limit"] == 0
        ),
        default=1,
    )
    report = {
        "provider": args.provider,
        "calibrated_at": datetime.now(UTC).isoformat(),
        "levels": levels,
        "max_full_success_concurrency": full_success_max,
        "recommended_max_concurrency": safe,
        "current_config": _current_quota(args.provider),
        "method": "max_full_success × 0.6 (safety margin), min 1",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{args.provider}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n{args.provider} 推荐安全并发: {safe}")
    print(f"→ {OUT_DIR / (args.provider + '.json')}")
    return 0


def _current_quota(provider: str) -> int:
    from packages.capability_gateway.registry import default_registry

    mapping = {
        "deepseek": "deepseek.chat.primary",
        "anysearch": "anysearch.primary",
        "openrouter": "openrouter.free.best_effort",
    }
    inst = default_registry().get(mapping[provider])
    return inst.max_concurrency if inst else 0


if __name__ == "__main__":
    raise SystemExit(main())
