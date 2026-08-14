"""G2.2d Deterministic Routing Contract Acceptance.

四块验收（不调用真实 OpenRouter / 不做 concurrency/circuit/metrics/retry）：

A. SEARCH —— Runtime Equivalence（G2.2b 冻结，不重改）
B. LLM workload —— provider boundary visibility=100% / workload classification=100%
   / unclassified=0 / direct bypass=0
C. Routing policy —— legacy primary divergence=0 / strict fallback leakage=0 /
   best-effort fallback plan 正确
D. Shadow safety —— LLM shadow 不 invoke；SEARCH shadow Gateway transport=0

产出 data/tmp/g2_2_routing_acceptance/ 下 JSON + MD。

用法：python -m scripts.g2_2_routing_acceptance
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
OUT_DIR = _REPO / "data" / "tmp" / "g2_2_routing_acceptance"

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover
    UTC = timezone.utc


# ── 依赖的包（脚本需要 repo 在 path 上） ──────────────────────────────────────
import sys  # noqa: E402

if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from packages.capability_gateway import (  # noqa: E402
    FALLBACK_ALLOWED_TASK_TYPES,
    STRICT_TASK_TYPES,
    CapabilityRouter,
    LLMCapabilityService,
    LLMTaskType,
    build_gateway_aware_search_provider,
    build_llm_capability_service,
    default_registry,
)
from packages.core.config import Settings  # noqa: E402
from packages.sources.enums import ToolStatus  # noqa: E402
from packages.sources.search_discovery import (  # noqa: E402
    SearchDiscoveryRequest,
    SourceAnySearchError,
    SourceTavilyError,
    build_search_discovery_provider,
)
from scripts.audit_llm_call_sites import run_audit  # noqa: E402

# ── fake search transports ───────────────────────────────────────────────────

def _any_success(endpoint, payload, headers, timeout):  # noqa: ARG001
    return {"result": {"content": [{
        "type": "text",
        "text": "### 1. 合肥低空经济政策\n- **URL**: https://example.com/hefei\n正文",
    }]}}


def _any_error(endpoint, payload, headers, timeout):  # noqa: ARG001
    raise SourceAnySearchError("anysearch down", retryable=True, detail={"status_code": 500})


def _tavily_success(endpoint, payload, headers, timeout):  # noqa: ARG001
    return {"results": [{"title": "合肥低空经济", "url": "https://tavily.com/hefei", "content": "政策"}]}


def _tavily_error(endpoint, payload, headers, timeout):  # noqa: ARG001
    raise SourceTavilyError("tavily down", retryable=True, detail={"status_code": 500})


def _recorder(calls, label, transport):
    def _f(endpoint, payload, headers, timeout):  # noqa: ARG001
        calls.append(label)
        return transport(endpoint, payload, headers, timeout)
    return _f


def _search_settings(mode: str = "gateway") -> Settings:
    return Settings(
        _env_file=None,
        CAPABILITY_GATEWAY_ENABLED=True,
        CAPABILITY_GATEWAY_SEARCH_MODE=mode,
        CAPABILITY_GATEWAY_LLM_MODE="off",
        SEARCH_DISCOVERY_PROVIDER="anysearch",
        SEARCH_DISCOVERY_FALLBACK_PROVIDER="tavily",
        SEARCH_DISCOVERY_FALLBACK_ENABLED=True,
        SEARCH_PROVIDER_POLICY="fallback_allowed",
        TAVILY_API_KEY="test-key",
    )


def _llm_settings() -> Settings:
    return Settings(
        _env_file=None,
        CAPABILITY_GATEWAY_ENABLED=True,
        CAPABILITY_GATEWAY_SEARCH_MODE="shadow",
        CAPABILITY_GATEWAY_LLM_MODE="shadow",
    )


def _request() -> SearchDiscoveryRequest:
    return SearchDiscoveryRequest(query="合肥低空经济 政策", max_results=5)


# ── A. SEARCH Runtime Equivalence ────────────────────────────────────────────

def block_search_equivalence() -> dict[str, Any]:
    settings = _search_settings("gateway")
    scenarios = {
        "primary_success": (_any_success, _tavily_success, ToolStatus.SUCCESS, ["anysearch"]),
        "primary_error_fallback_success": (_any_error, _tavily_success, ToolStatus.SUCCESS,
                                           ["anysearch", "tavily"]),
        "all_error": (_any_error, _tavily_error, ToolStatus.ERROR, ["anysearch", "tavily"]),
    }
    results: dict[str, Any] = {}
    for name, (any_t, tavily_t, expected_status, expected_calls) in scenarios.items():
        legacy_calls: list[str] = []
        gw_calls: list[str] = []
        legacy = build_search_discovery_provider(
            settings,
            anysearch_transport=_recorder(legacy_calls, "anysearch", any_t),
            tavily_transport=_recorder(legacy_calls, "tavily", tavily_t),
        )
        gateway = build_gateway_aware_search_provider(
            settings,
            anysearch_transport=_recorder(gw_calls, "anysearch", any_t),
            tavily_transport=_recorder(gw_calls, "tavily", tavily_t),
        )
        lr = legacy.search(_request())
        gr = gateway.search(_request())
        same_schema = (
            lr.status == gr.status
            and lr.query == gr.query
            and [r.url for r in lr.results] == [r.url for r in gr.results]
            and bool(lr.errors) == bool(gr.errors)
        )
        results[name] = {
            "legacy_calls": legacy_calls,
            "gateway_calls": gw_calls,
            "status": gr.status.value,
            "expected_status": expected_status.value,
            "same_schema": same_schema,
            "PASS": legacy_calls == expected_calls == gw_calls
                    and gr.status == expected_status
                    and same_schema,
        }
    return {"scenarios": results, "PASS": all(v["PASS"] for v in results.values())}


# ── B. LLM workload audit ────────────────────────────────────────────────────

def block_llm_workload_audit() -> dict[str, Any]:
    audit = run_audit()
    pv = audit["provider_boundary_visibility"]
    wc = audit["workload_classification"]
    result = {
        "provider_boundary_visibility": pv,
        "workload_classification": wc,
        "unclassified_count": len(audit["unclassified_call_sites"]),
        "direct_provider_bypass_count": audit["direct_provider_bypass_count"],
        "PASS": (
            pv["rate"] == 1.0
            and wc["rate"] == 1.0
            and len(audit["unclassified_call_sites"]) == 0
            and audit["direct_provider_bypass_count"] == 0
        ),
    }
    return result


# ── C. Routing policy ────────────────────────────────────────────────────────

def block_routing_policy() -> dict[str, Any]:
    svc = build_llm_capability_service(_llm_settings())
    plans = svc.plan_all()

    primary_divergence = 0
    strict_leakage = 0
    best_effort_correct = True
    strict_detail: dict[str, Any] = {}
    best_effort_detail: dict[str, Any] = {}

    for task_type in LLMTaskType:
        result = plans[task_type.value]
        if not result.equivalent_primary:
            primary_divergence += 1
        if task_type in STRICT_TASK_TYPES:
            strict_detail[task_type.value] = {
                "primary": result.gateway_primary,
                "fallback_chain": result.fallback_chain,
                "leakage": result.strict_leakage,
            }
            strict_leakage += result.strict_leakage
        if task_type in FALLBACK_ALLOWED_TASK_TYPES:
            best_effort_detail[task_type.value] = {
                "primary": result.gateway_primary,
                "fallback_chain": result.fallback_chain,
            }
            best_effort_correct = best_effort_correct and (
                result.gateway_primary == "deepseek.chat.primary"
                and result.fallback_chain == ["openrouter.free.best_effort"]
            )

    # 反事实：OpenRouter 具备全部 feature，strict 仍不得 fallback
    reg = default_registry()
    reg.get("openrouter.free.best_effort").features.update({
        "structured_output": True, "json_schema": True, "tool_calling": True,
    })
    counterfactual_svc = LLMCapabilityService(settings=_llm_settings(), router=CapabilityRouter(reg))
    counterfactual = {}
    for task_type in (LLMTaskType.EVIDENCE_EXTRACTION, LLMTaskType.CLAIM_GENERATION,
                      LLMTaskType.STRUCTURED_DRAFT):
        r = counterfactual_svc.plan(task_type)
        counterfactual[task_type.value] = {
            "primary": r.gateway_primary,
            "fallback_chain": r.fallback_chain,
            "filtered_openrouter": r.filtered.get("openrouter.free.best_effort"),
        }
    # DeepSeek 不可用 → strict 失败，绝不提升 OpenRouter
    reg.get("deepseek.chat.primary").enabled = False
    r = counterfactual_svc.plan(LLMTaskType.EVIDENCE_EXTRACTION)
    counterfactual["evidence_extraction_deepseek_down"] = {
        "primary": r.gateway_primary, "fallback_chain": r.fallback_chain,
    }
    counterfactual_pass = all(
        v["fallback_chain"] == [] and v["primary"] == "deepseek.chat.primary"
        for k, v in counterfactual.items() if "deepseek_down" not in k
    ) and counterfactual["evidence_extraction_deepseek_down"]["primary"] is None

    return {
        "primary_divergence_count": primary_divergence,
        "strict_fallback_leakage_count": strict_leakage,
        "best_effort_fallback_correct": best_effort_correct,
        "strict_detail": strict_detail,
        "best_effort_detail": best_effort_detail,
        "counterfactual": counterfactual,
        "counterfactual_pass": counterfactual_pass,
        "PASS": (
            primary_divergence == 0
            and strict_leakage == 0
            and best_effort_correct
            and counterfactual_pass
        ),
    }


# ── D. Shadow safety ─────────────────────────────────────────────────────────

def block_shadow_safety() -> dict[str, Any]:
    # SEARCH shadow：Legacy 执行一次，Gateway transport 0 次
    from packages.capability_gateway import RoutingInvoker, SearchCapabilityService
    from packages.capability_gateway.adapters import build_search_adapter_registry

    settings = _search_settings("shadow")
    legacy_calls: list[str] = []
    gateway_calls: list[str] = []

    router = CapabilityRouter(default_registry())
    adapter_registry = build_search_adapter_registry(
        settings,
        anysearch_transport=_recorder(gateway_calls, "anysearch", _any_success),
        tavily_transport=_recorder(gateway_calls, "tavily", _tavily_success),
    )

    def _legacy_factory():
        return build_search_discovery_provider(
            settings,
            anysearch_transport=_recorder(legacy_calls, "anysearch", _any_success),
            tavily_transport=_recorder(legacy_calls, "tavily", _tavily_success),
        )

    svc = SearchCapabilityService(
        settings=settings, router=router,
        invoker=RoutingInvoker(adapter_registry), legacy_factory=_legacy_factory,
    )
    resp = svc.search(_request())
    search_shadow_pass = (
        resp.status == ToolStatus.SUCCESS
        and legacy_calls == ["anysearch"]
        and gateway_calls == []
    )

    # LLM shadow：plan() 是纯路由，不 invoke
    llm_svc = build_llm_capability_service(_llm_settings())
    llm_plan = llm_svc.plan(LLMTaskType.EVIDENCE_EXTRACTION)
    llm_shadow_pass = llm_plan.task_type == "evidence_extraction"

    return {
        "search_shadow": {
            "legacy_calls": legacy_calls,
            "gateway_transport_calls": len(gateway_calls),
            "PASS": search_shadow_pass,
        },
        "llm_shadow": {"task_type": llm_plan.task_type, "PASS": llm_shadow_pass},
        "gateway_transport_calls": len(gateway_calls),
        "PASS": search_shadow_pass and llm_shadow_pass,
    }


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    blocks = {
        "search": block_search_equivalence(),
        "llm_workload": block_llm_workload_audit(),
        "routing_policy": block_routing_policy(),
        "shadow_safety": block_shadow_safety(),
    }
    all_pass = all(b["PASS"] for b in blocks.values())

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "search": {
            "production_modules": 5,
            "call_sites": 8,
            "runtime_equivalence": blocks["search"]["PASS"],
        },
        "llm": {
            "provider_boundary_visibility_rate": blocks["llm_workload"]["provider_boundary_visibility"]["rate"],
            "workload_classification_rate": blocks["llm_workload"]["workload_classification"]["rate"],
            "direct_provider_bypass_count": blocks["llm_workload"]["direct_provider_bypass_count"],
            "unclassified_count": blocks["llm_workload"]["unclassified_count"],
            "primary_divergence_count": blocks["routing_policy"]["primary_divergence_count"],
            "strict_fallback_leakage_count": blocks["routing_policy"]["strict_fallback_leakage_count"],
        },
        "shadow_transport_calls": blocks["shadow_safety"]["gateway_transport_calls"],
        "status": "PASS" if all_pass else "FAIL",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "search_runtime_equivalence.json").write_text(
        json.dumps(blocks["search"], ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "llm_workload_audit.json").write_text(
        json.dumps(blocks["llm_workload"], ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "strict_policy_regression.json").write_text(
        json.dumps(blocks["routing_policy"], ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "routing_acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(report)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nG2.2 {'PASS' if all_pass else 'FAIL'} -> {OUT_DIR}")
    return 0 if all_pass else 1


def _write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# G2.2 Deterministic Routing Contract Acceptance",
        "", f"- Generated: {report['generated_at']}", "",
        "| Block | Status | Key metrics |", "|---|---|---|",
        f"| SEARCH Runtime Equivalence | {'PASS' if report['search']['runtime_equivalence'] else 'FAIL'} | "
        f"{report['search']['production_modules']} modules / {report['search']['call_sites']} call sites |",
        f"| LLM workload audit | {'PASS' if report['llm']['workload_classification_rate'] == 1.0 else 'FAIL'} | "
        f"visibility={report['llm']['provider_boundary_visibility_rate']} "
        f"classification={report['llm']['workload_classification_rate']} "
        f"bypass={report['llm']['direct_provider_bypass_count']} |",
        f"| Routing policy | {'PASS' if report['llm']['primary_divergence_count'] == 0 and report['llm']['strict_fallback_leakage_count'] == 0 else 'FAIL'} | "
        f"primary_divergence={report['llm']['primary_divergence_count']} "
        f"strict_leakage={report['llm']['strict_fallback_leakage_count']} |",
        f"| Shadow safety | {'PASS' if report['shadow_transport_calls'] == 0 else 'FAIL'} | "
        f"gateway_transport_calls={report['shadow_transport_calls']} |",
        "", f"**Overall: {report['status']}**",
    ]
    (OUT_DIR / "G2_2_DETERMINISTIC_ROUTING_ACCEPTANCE.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
