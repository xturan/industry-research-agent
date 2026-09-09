"""Gateway MVP Closeout Acceptance (M3)。

在 Gateway 层验证三条链真正串起来（注入 fake transport/client，不依赖真实网络）：
A. Search Gateway：normal / AnySearch→Tavily / all-error（Runtime Equivalence）
B. LLM Gateway：strict→DeepSeek only；best-effort→DeepSeek→OpenRouter；strict 失败不 fallback
C. ProviderAttempt telemetry：fallback chain 完整 trace（同 route_execution_id、不同 provider_call_id）

产出 data/tmp/gateway_mvp_acceptance/。

用法：python -m scripts.gateway_mvp_acceptance
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from packages.capability_gateway import (  # noqa: E402
    FallbackPolicy,
    InMemoryProviderAttemptRecorder,
    LLMCapabilityService,
    LLMTaskType,
    RoutingInvoker,
    build_gateway_aware_search_provider,
    build_llm_adapter_registry,
    default_registry,
)
from packages.capability_gateway.router import CapabilityRouter  # noqa: E402
from packages.core.config import Settings  # noqa: E402
from packages.sources.enums import ToolStatus  # noqa: E402
from packages.sources.search_discovery import (  # noqa: E402
    SearchDiscoveryRequest,
    SourceAnySearchError,
    SourceTavilyError,
)

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover
    UTC = timezone.utc

OUT_DIR = _REPO / "data" / "tmp" / "gateway_mvp_acceptance"


# ── fake transports / clients ────────────────────────────────────────────────

def _any_success(endpoint, payload, headers, timeout):  # noqa: ARG001
    return {"result": {"content": [{
        "type": "text", "text": "### 1. 合肥低空经济\n- **URL**: https://example.com\n正文",
    }]}}


def _any_error(endpoint, payload, headers, timeout):  # noqa: ARG001
    raise SourceAnySearchError("anysearch down", retryable=True, detail={"status_code": 500})


def _tavily_success(endpoint, payload, headers, timeout):  # noqa: ARG001
    return {"results": [{"title": "合肥低空", "url": "https://tavily.com", "content": "x"}]}


def _tavily_error(endpoint, payload, headers, timeout):  # noqa: ARG001
    raise SourceTavilyError("tavily down", retryable=True, detail={"status_code": 500})


class _FakeResp:
    def __init__(self, json_data=None, provider="fake"):
        self.json_data = json_data if json_data is not None else {}
        self.provider = provider
        self.model = "m"
        self.metadata = type("M", (), {"usage": {"input_tokens": 1, "output_tokens": 1}, "extra": {}})()


class _FakeLLMClient:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def generate_json(self, **kwargs):
        self.calls += 1
        if self.fail:
            from packages.providers.base import ProviderRetryableError
            raise ProviderRetryableError("timeout")
        return _FakeResp({"ok": True}, provider="deepseek")


def _search_settings(mode: str) -> Settings:
    return Settings(
        _env_file=None, CAPABILITY_GATEWAY_ENABLED=True,
        CAPABILITY_GATEWAY_SEARCH_MODE=mode, CAPABILITY_GATEWAY_LLM_MODE=mode,
        SEARCH_DISCOVERY_PROVIDER="anysearch", SEARCH_DISCOVERY_FALLBACK_PROVIDER="tavily",
        SEARCH_DISCOVERY_FALLBACK_ENABLED=True, SEARCH_PROVIDER_POLICY="fallback_allowed",
        TAVILY_API_KEY="test-key",
    )


def _req() -> SearchDiscoveryRequest:
    return SearchDiscoveryRequest(query="合肥低空经济 政策", max_results=5)


# ── A. Search Gateway ────────────────────────────────────────────────────────

def block_search() -> dict[str, Any]:
    settings = _search_settings("gateway")
    cases = {
        "normal": (_any_success, _tavily_success, ToolStatus.SUCCESS, ["anysearch"]),
        "primary_error_fallback": (_any_error, _tavily_success, ToolStatus.SUCCESS,
                                   ["anysearch", "tavily"]),
        "all_error": (_any_error, _tavily_error, ToolStatus.ERROR, ["anysearch", "tavily"]),
    }
    results = {}
    for name, (any_t, tav_t, expected_status, expected_calls) in cases.items():
        calls: list[str] = []

        def rec(label, _calls=calls, _any=any_t, _tav=tav_t):
            def _f(endpoint, payload, headers, timeout):  # noqa: ARG001
                _calls.append(label)
                return (_any if label == "anysearch" else _tav)(
                    endpoint, payload, headers, timeout
                )
            return _f

        gw = build_gateway_aware_search_provider(
            settings, anysearch_transport=rec("anysearch"), tavily_transport=rec("tavily"),
        )
        resp = gw.search(_req())
        results[name] = {
            "calls": list(calls),
            "expected_calls": expected_calls,
            "status": resp.status.value,
            "PASS": calls == expected_calls and resp.status == expected_status,
        }
    return {"cases": results, "PASS": all(v["PASS"] for v in results.values())}


# ── B. LLM Gateway ───────────────────────────────────────────────────────────

def block_llm() -> dict[str, Any]:
    settings = _search_settings("gateway")
    recorder = InMemoryProviderAttemptRecorder()
    ds = _FakeLLMClient()
    or_client = _FakeLLMClient()
    adapter_reg = build_llm_adapter_registry(settings, deepseek_client=ds, openrouter_client=or_client)
    invoker = RoutingInvoker(
        adapter_reg, recorder=recorder, fallback_policy=FallbackPolicy(),
    )
    svc = LLMCapabilityService(
        settings=settings, router=CapabilityRouter(default_registry()),
        invoker=invoker, adapter_registry=adapter_reg, legacy_factory=lambda: ds,
    )

    # strict → DeepSeek only
    ds.fail = False
    r = svc.generate_json(LLMTaskType.EVIDENCE_EXTRACTION, system_prompt="s", user_prompt="u")
    strict_ok = r.json_data == {"ok": True} and or_client.calls == 0

    # best-effort DeepSeek timeout → OpenRouter
    ds.calls = 0
    or_client.calls = 0
    ds.fail = True
    r = svc.generate_json(LLMTaskType.QUERY_EXPANSION, system_prompt="s", user_prompt="u")
    best_effort_ok = r.json_data == {"ok": True} and ds.calls == 1 and or_client.calls == 1

    # strict DeepSeek timeout → 不 fallback（抛错）
    ds.calls = 0
    or_client.calls = 0
    try:
        svc.generate_json(LLMTaskType.EVIDENCE_EXTRACTION, system_prompt="s", user_prompt="u")
        strict_fail_no_fallback = False
    except Exception:  # noqa: BLE001
        strict_fail_no_fallback = or_client.calls == 0

    recs = recorder.all()
    fallback_chain_ok = (
        any(rr.outcome == "failed" and rr.provider_instance_id == "deepseek.chat.primary" for rr in recs)
        and any(rr.outcome == "success" and rr.provider_instance_id == "openrouter.free.best_effort" for rr in recs)
    )
    return {
        "strict_deepseek_only": strict_ok,
        "best_effort_fallback": best_effort_ok,
        "strict_fail_no_fallback": strict_fail_no_fallback,
        "telemetry_fallback_chain": fallback_chain_ok,
        "PASS": strict_ok and best_effort_ok and strict_fail_no_fallback and fallback_chain_ok,
    }


# ── C. Telemetry fallback chain trace ────────────────────────────────────────

def block_telemetry_chain() -> dict[str, Any]:
    settings = _search_settings("gateway")
    recorder = InMemoryProviderAttemptRecorder()
    ds = _FakeLLMClient(fail=True)
    or_client = _FakeLLMClient()
    adapter_reg = build_llm_adapter_registry(settings, deepseek_client=ds, openrouter_client=or_client)
    invoker = RoutingInvoker(
        adapter_reg, recorder=recorder, fallback_policy=FallbackPolicy(),
    )
    svc = LLMCapabilityService(
        settings=settings, router=CapabilityRouter(default_registry()),
        invoker=invoker, adapter_registry=adapter_reg, legacy_factory=lambda: ds,
    )
    svc.generate_json(LLMTaskType.QUERY_EXPANSION, system_prompt="s", user_prompt="u")
    recs = recorder.all()
    c1 = next(r for r in recs if r.provider_instance_id == "deepseek.chat.primary")
    c2 = next(r for r in recs if r.provider_instance_id == "openrouter.free.best_effort")
    trace = {
        "route_execution_id": c1.route_execution_id,
        "c1": {"provider": c1.provider_instance_id, "outcome": c1.outcome,
               "failure_class": c1.failure_class, "provider_call_id": c1.provider_call_id},
        "c2": {"provider": c2.provider_instance_id, "outcome": c2.outcome,
               "provider_call_id": c2.provider_call_id},
    }
    ok = (
        c1.route_execution_id == c2.route_execution_id
        and c1.provider_call_id != c2.provider_call_id
        and c1.failure_class == "network"
    )
    return {"trace": trace, "PASS": ok}


def main() -> int:
    blocks = {
        "search_gateway": block_search(),
        "llm_gateway": block_llm(),
        "telemetry_chain": block_telemetry_chain(),
    }
    all_pass = all(b["PASS"] for b in blocks.values())
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "blocks": blocks,
        "gateway_mvp": "ACCEPTED" if all_pass else "FAIL",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "gateway_mvp_acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nGateway MVP {'ACCEPTED' if all_pass else 'FAIL'} -> {OUT_DIR}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
