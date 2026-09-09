"""G2.2c LLMCapabilityService — LLM 路由 Shadow（本轮 shadow only）。

与 Search 相同的 off / shadow / gateway 契约，但本轮只启用 shadow：
- Legacy DeepSeek 正式执行（现有调用链不动）；
- Gateway 仅生成 RoutingPlan + Shadow 诊断；
- **禁止 Gateway transport 调用**（OpenRouter Free 只是 routing candidate）。

`plan(task_type)` 是纯路由计算（不 invoke），因此可安全用于 shadow 对比。
正式 invoke（gateway mode）留给 G2.2d/G2.3。

Shadow 记录：
    task_type / legacy_provider / gateway_primary / fallback_chain /
    filtered reasons / request_fingerprint / equivalent_primary
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.capability_gateway.adapters import (
    RoutingInvoker,
    build_llm_adapter_registry,
)
from packages.capability_gateway.llm_tasks import (
    get_llm_profile,
    legacy_primary_instance,
    legacy_provider_for_task,
    llm_capability_request,
)
from packages.capability_gateway.registry import CapabilityRegistry, default_registry
from packages.capability_gateway.router import CapabilityRouter, llm_routing_mode
from packages.capability_gateway.schemas import CapabilityRequest


@dataclass
class LLMShadowResult:
    """一次 LLM task 的 shadow 路由诊断（不 invoke，纯计算）。"""

    task_type: str
    policy: str
    legacy_provider: str
    legacy_primary_instance: str
    gateway_primary: str | None
    fallback_chain: list[str] = field(default_factory=list)
    filtered: dict[str, str] = field(default_factory=dict)
    request_fingerprint: str | None = None
    equivalent_primary: bool = False
    route_reason: list[str] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)

    @property
    def strict_leakage(self) -> int:
        """strict task 中 best-effort fallback 的泄漏数（期望 0）。"""
        return len(self.fallback_chain)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "policy": self.policy,
            "legacy_provider": self.legacy_provider,
            "legacy_primary_instance": self.legacy_primary_instance,
            "gateway_primary": self.gateway_primary,
            "fallback_chain": list(self.fallback_chain),
            "filtered": dict(self.filtered),
            "request_fingerprint": self.request_fingerprint,
            "equivalent_primary": self.equivalent_primary,
            "route_reason": list(self.route_reason),
            "providers": list(self.providers),
        }


class LLMCapabilityService:
    """统一 LLM 入口（off / shadow / gateway），与 Search 对称。

    - off     → Legacy DeepSeek（行为不变）
    - shadow  → Legacy DeepSeek 执行 + Gateway route-only 诊断
    - gateway → Gateway route + budget/circuit/fallback/telemetry 执行

    `plan(task_type)` 纯路由计算（shadow 用）；`generate_json/generate_text`
    是正式执行 facade（sync，内部 asyncio.run 与 Search 一致）。
    """

    def __init__(
        self,
        *,
        settings: Any,
        router: CapabilityRouter,
        invoker: Any | None = None,
        adapter_registry: Any | None = None,
        legacy_factory: Any | None = None,
        run_id_provider: Any | None = None,
    ) -> None:
        self._settings = settings
        self._router = router
        self._invoker = invoker
        self._adapter_registry = adapter_registry
        self._legacy_factory = legacy_factory
        self._legacy_client = None
        # G2.5a：run_id 来源（callable 返回 str|None）。从 real_nodes._trace_ctx
        # 解析；测试可注入固定值或 None。
        self._run_id_provider = run_id_provider

    def mode(self) -> str:
        return llm_routing_mode(self._settings)

    def _run_id(self) -> str | None:
        if self._run_id_provider is not None:
            try:
                return self._run_id_provider()
            except Exception:  # noqa: BLE001 - telemetry 辅助，fail-open
                return None
        return None

    def _legacy(self):
        if self._legacy_client is None:
            self._legacy_client = (
                self._legacy_factory() if self._legacy_factory is not None else None
            )
        return self._legacy_client

    def plan(self, task_type: Any) -> LLMShadowResult:
        """对给定 task_type 计算 RoutingPlan + shadow 诊断（纯路由，无 transport）。

        primary equivalence = gateway primary == legacy semantic provider
        （不再假设所有 workload 都是 DeepSeek；source_tier → ollama）。
        """
        get_llm_profile(task_type)  # 提前暴露分类缺口
        request: CapabilityRequest = llm_capability_request(task_type)
        plan = self._router.route(request)
        expected = legacy_primary_instance(request.task_type)
        return LLMShadowResult(
            task_type=request.task_type,
            policy=plan.policy.value,
            legacy_provider=legacy_provider_for_task(request.task_type),
            legacy_primary_instance=expected,
            gateway_primary=plan.primary,
            fallback_chain=list(plan.fallback_chain),
            filtered=dict(plan.filtered),
            request_fingerprint=plan.request_fingerprint,
            equivalent_primary=plan.primary == expected,
            route_reason=list(plan.route_reason),
            providers=plan.providers,
        )

    def plan_all(self) -> dict[str, LLMShadowResult]:
        """对所有已分类 task_type 批量计算 shadow plan（inventory 便捷入口）。"""
        from packages.capability_gateway.llm_tasks import LLM_TASK_PROFILES

        return {
            profile.task_type.value: self.plan(profile.task_type)
            for profile in LLM_TASK_PROFILES.values()
        }

    # ── G2-M1：正式执行 facade（off / shadow / gateway） ─────────────────────

    def generate_json(
        self,
        task_type: Any,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        enable_thinking: bool = False,
        **kwargs: Any,
    ) -> Any:
        return self._generate(
            task_type, output="json", system_prompt=system_prompt,
            user_prompt=user_prompt, model=model, enable_thinking=enable_thinking,
            **kwargs,
        )

    def generate_text(
        self,
        task_type: Any,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        enable_thinking: bool = False,
        **kwargs: Any,
    ) -> Any:
        return self._generate(
            task_type, output="text", system_prompt=system_prompt,
            user_prompt=user_prompt, model=model, enable_thinking=enable_thinking,
            **kwargs,
        )

    def _generate(
        self, task_type: Any, *, output: str, system_prompt: str, user_prompt: str,
        model: str | None, enable_thinking: bool, **kwargs: Any,
    ) -> Any:
        mode = self.mode()
        if mode == "gateway":
            return self._gateway_generate(
                task_type, output, system_prompt, user_prompt, model, enable_thinking,
                **kwargs,
            )
        response = self._legacy_call(
            output, system_prompt, user_prompt, model, enable_thinking, **kwargs
        )
        if mode == "shadow":
            self._attach_shadow(response, task_type)
        return response

    def _legacy_call(
        self, output: str, system_prompt: str, user_prompt: str,
        model: str | None, enable_thinking: bool, **kwargs: Any,
    ) -> Any:
        client = self._legacy()
        if client is None:
            from packages.providers import ProviderConfigError

            raise ProviderConfigError("LLM provider is not configured.")
        if output == "json":
            return client.generate_json(
                system_prompt=system_prompt, user_prompt=user_prompt,
                model=model, enable_thinking=enable_thinking, **kwargs,
            )
        return client.generate_text(
            system_prompt=system_prompt, user_prompt=user_prompt,
            model=model, enable_thinking=enable_thinking,
        )

    def _gateway_generate(
        self, task_type: Any, output: str, system_prompt: str, user_prompt: str,
        model: str | None, enable_thinking: bool, **kwargs: Any,
    ) -> Any:
        import asyncio

        if self._invoker is None:
            raise RuntimeError("LLM gateway mode requires an invoker.")
        request = llm_capability_request(task_type)
        plan = self._router.route(request)
        payload = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "model": model,
            "enable_thinking": enable_thinking,
            "output": output,
            # G2-M1 修复：透传 max_tokens/temperature 等，供 adapter 按需处理。
            "max_tokens": kwargs.get("max_tokens"),
            "temperature": kwargs.get("temperature"),
            "top_p": kwargs.get("top_p"),
            "presence_penalty": kwargs.get("presence_penalty"),
            "frequency_penalty": kwargs.get("frequency_penalty"),
        }
        result = asyncio.run(
            self._invoker.invoke(plan, payload, run_id=self._run_id())
        )
        if result.success and result.data is not None:
            return result.data
        from packages.providers import ProviderError

        raise ProviderError(result.error or "LLM gateway call failed.")

    def _attach_shadow(self, response: Any, task_type: Any) -> Any:
        """shadow：Legacy 执行 + 挂 Gateway route-only 诊断（不改响应语义）。"""
        try:
            plan = self._router.route(llm_capability_request(task_type))
            diagnostic = {
                "mode": "shadow",
                "request_fingerprint": plan.request_fingerprint,
                "planned_primary": plan.primary,
                "planned_fallback_chain": list(plan.fallback_chain),
            }
            metadata = getattr(response, "metadata", None)
            extra = getattr(metadata, "extra", None)
            if isinstance(extra, dict):
                extra["capability_routing"] = diagnostic
        except Exception:  # noqa: BLE001 - shadow 诊断不干扰主路径
            pass
        return response


def build_llm_capability_service(
    settings: Any = None,
    *,
    budget: Any | None = None,
    circuit: Any | None = None,
    recorder: Any | None = None,
    run_id_provider: Any | None = None,
) -> LLMCapabilityService:
    """构建 LLM 服务（plan + 执行 facade）。settings=None → get_settings()。

    默认不注入 budget/circuit/recorder（off/shadow 不受影响）；gateway 模式若要
    完整保护，由调用方注入（G2.8 wiring）。
    """
    from packages.capability_gateway.fallback import FallbackPolicy
    from packages.core.config import get_settings

    app = settings or get_settings()
    registry: CapabilityRegistry = default_registry()
    router = CapabilityRouter(registry)
    adapter_registry = build_llm_adapter_registry(app)
    invoker = RoutingInvoker(
        adapter_registry, budget=budget, circuit=circuit, recorder=recorder,
        fallback_policy=FallbackPolicy(),
    )

    def _legacy_factory():
        from packages.capability_gateway.adapters import _build_deepseek_client

        return _build_deepseek_client(app)

    return LLMCapabilityService(
        settings=app, router=router, invoker=invoker,
        adapter_registry=adapter_registry, legacy_factory=_legacy_factory,
        run_id_provider=run_id_provider,
    )


def build_gateway_aware_llm_client(
    settings: Any = None,
    *,
    task_type: Any = None,
    budget: Any | None = None,
    circuit: Any | None = None,
    recorder: Any | None = None,
    run_id_provider: Any | None = None,
) -> Any:
    """返回一个带 generate_json/generate_text 的 client 形状对象（绑定 task_type）。

    off/shadow → Legacy DeepSeek；gateway → Gateway 执行。作为 `call_tooling_json`
    等生产 call site 的 drop-in client。

    budget/circuit/recorder/run_id_provider 透传到 RoutingInvoker（G2.3/G2.4/G2.5），
    由 G2.8 wiring 注入。
    """
    svc = build_llm_capability_service(
        settings,
        budget=budget,
        circuit=circuit,
        recorder=recorder,
        run_id_provider=run_id_provider,
    )

    class _GatewayAwareClient:
        def generate_json(self, **kwargs: Any) -> Any:
            return svc.generate_json(task_type, **kwargs)

        def generate_text(self, **kwargs: Any) -> Any:
            return svc.generate_text(task_type, **kwargs)

    return _GatewayAwareClient()


__all__ = [
    "LLMCapabilityService",
    "LLMShadowResult",
    "build_llm_capability_service",
    "build_gateway_aware_llm_client",
]
