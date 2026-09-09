"""G2.2 ProviderAdapterRegistry — 把「Provider 元数据」与「实际 client 实现」分离。

CapabilityRegistry（G2.1）保存 Provider 描述（metadata）。
ProviderAdapterRegistry 保存 instance_id → CapabilityAdapter（实现）。

G2.2a 只建立这个 seam，不替换生产调用路径（shadow 模式不 invoke）。
第一版 Invoker 极简：按 RoutingPlan.providers 顺序尝试，非 success 视为
fallback-eligible 继续（复用现有「primary ERROR → fallback」判定，不重新发明）。

职责链：
    RoutingPlan → RoutingInvoker → ProviderAdapterRegistry.get(instance_id) → CapabilityAdapter
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC
from typing import Any, Protocol

from packages.capability_gateway.plan import RoutingPlan
from packages.capability_gateway.schemas import CapabilityType


@dataclass
class CapabilityInvocation:
    """Adapter 收到的业务调用。payload 由调用方传入（SEARCH 传检索请求、
    LLM 传 messages/prompt），Gateway 不解释 payload 内容。"""

    capability: CapabilityType
    task_type: str
    provider_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    provider_call_id: str | None = None  # 本次 Provider attempt 唯一标识（G2.3）


@dataclass
class CapabilityResult:
    provider_id: str
    success: bool
    data: Any = None
    error: str | None = None
    latency_ms: float | None = None
    # 三个身份：request_fingerprint（plan 上） / route_execution_id / provider_call_id
    route_execution_id: str | None = None  # 这一次 Capability Gateway invocation
    provider_call_id: str | None = None  # 这一次具体 Provider attempt
    failure_class: Any | None = None  # G2.4 ProviderFailureClass（失败时）
    # G2.5a 用量（LLM: tokens；Search: result_count）
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_count: int | None = None
    result_count: int | None = None


class CapabilityAdapter(Protocol):
    """统一 Provider 调用接口。SEARCH/LLM 各自的 Adapter 实现它。"""

    async def invoke(self, invocation: CapabilityInvocation) -> CapabilityResult:
        """执行一次调用并返回结构化结果。调用失败应返回 success=False，
        或抛出由调用方视为 fallback-eligible 的异常。"""
        ...


class ProviderAdapterRegistry:
    """instance_id → CapabilityAdapter 映射（与 CapabilityRegistry 的 metadata 分离）。"""

    def __init__(self) -> None:
        self._adapters: dict[str, CapabilityAdapter] = {}

    def register(self, instance_id: str, adapter: CapabilityAdapter) -> None:
        if instance_id in self._adapters:
            raise ValueError(f"duplicate adapter: {instance_id}")
        self._adapters[instance_id] = adapter

    def register_all(self, mapping: dict[str, CapabilityAdapter]) -> None:
        for instance_id, adapter in mapping.items():
            self.register(instance_id, adapter)

    def get(self, instance_id: str) -> CapabilityAdapter | None:
        return self._adapters.get(instance_id)

    def has(self, instance_id: str) -> bool:
        return instance_id in self._adapters

    def all(self) -> dict[str, CapabilityAdapter]:
        return dict(self._adapters)


class CallableAdapter:
    """把任意同步 callable 包成 async CapabilityAdapter（测试/桥接现有 client）。"""

    def __init__(
        self,
        instance_id: str,
        invoke_fn: Callable[[CapabilityInvocation], CapabilityResult],
    ) -> None:
        self.instance_id = instance_id
        self._invoke_fn = invoke_fn

    async def invoke(self, invocation: CapabilityInvocation) -> CapabilityResult:
        return await asyncio.to_thread(self._invoke_fn, invocation)


class RoutingInvoker:
    """按 RoutingPlan.providers 顺序尝试，直到 success 或耗尽。

    职责边界（G2.2b 定死；G2.3 加 Budget；G2.4 加 Circuit/Classifier/Fallback）：
    - 只执行已经形成的 RoutingPlan；**不重新评分 / 不临时发现新 Provider / 不修改
      Registry / 不做 retry/backoff / 不维护 metrics**。
    - 编排各关注点（委托，不自己懂所有规则）：
        circuit（能否调用）→ budget（能不能进去）→ adapter（调用）
        → classifier（失败分类）→ circuit feedback → fallback（是否下一个）。
    - 每个 Provider attempt 独立 `provider_call_id`；同一 fallback chain 共用
      `route_execution_id`。
    - 全败时保留最后尝试 Provider 的 data（与 Legacy 失败 Contract 一致）。

    G2.4 模式：传入 `classifier` + `fallback_policy`（可选 `circuit`）。
    未传入 fallback_policy 时保持 Legacy 行为（任意失败 → 下一个 planned provider）。
    G2.5a：传入 `recorder` 后，每个 Provider attempt 在 finally 记录
    `ProviderAttemptRecord`（append-only；telemetry fail-open，不影响业务）。
    """

    def __init__(
        self,
        adapter_registry: ProviderAdapterRegistry,
        *,
        budget: Any | None = None,
        circuit: Any | None = None,
        classifier: Any | None = None,
        fallback_policy: Any | None = None,
        recorder: Any | None = None,
    ) -> None:
        from packages.capability_gateway.circuit import FailureClassifier

        self._registry = adapter_registry
        self._budget = budget
        self._circuit = circuit
        self._classifier = classifier if classifier is not None else FailureClassifier()
        self._fallback_policy = fallback_policy
        self._recorder = recorder

    def _legacy_fallback_eligible(self, result: CapabilityResult) -> bool:
        return not result.success

    def _should_fallback(self, plan: RoutingPlan, failure_class: Any) -> bool:
        if self._fallback_policy is None:
            return True  # Legacy：任意失败 → 下一个 planned provider
        return bool(
            self._fallback_policy.should_fallback(
                routing_policy=plan.policy, failure_class=failure_class
            )
        )

    def _record_attempt(
        self,
        *,
        plan: RoutingPlan,
        route_execution_id: str,
        provider_id: str,
        provider_call_id: str,
        attempt_index: int,
        transport_invoked: bool,
        outcome: str,
        failure_class: Any,
        started: Any,
        finished: Any,
        result: CapabilityResult | None,
        run_id: str | None,
    ) -> None:
        if self._recorder is None:
            return
        try:
            from packages.capability_gateway.telemetry import ProviderAttemptRecord

            latency_ms = None
            if started is not None and finished is not None:
                latency_ms = round((finished - started).total_seconds() * 1000.0, 3)
            self._recorder.record(
                ProviderAttemptRecord(
                    provider_call_id=provider_call_id,
                    route_execution_id=route_execution_id,
                    provider_instance_id=provider_id,
                    outcome=outcome,
                    transport_invoked=transport_invoked,
                    started_at=started,
                    finished_at=finished,
                    latency_ms=latency_ms,
                    attempt_index=attempt_index,
                    fallback_used=attempt_index > 0,
                    fallback_index=attempt_index,
                    failure_class=(
                        failure_class.value if failure_class is not None else None
                    ),
                    request_fingerprint=plan.request_fingerprint,
                    run_id=run_id,
                    capability=plan.capability.value,
                    task_type=plan.task_type,
                    input_tokens=result.input_tokens if result is not None else None,
                    output_tokens=result.output_tokens if result is not None else None,
                    request_count=result.request_count if result is not None else None,
                    result_count=result.result_count if result is not None else None,
                )
            )
        except Exception:  # noqa: BLE001 - telemetry fail-open
            import logging

            logging.getLogger(__name__).warning(
                "PROVIDER_CALL_METRIC_PERSIST_FAILED provider_call_id=%s",
                provider_call_id,
                exc_info=True,
            )

    async def invoke(
        self,
        plan: RoutingPlan,
        payload: dict[str, Any],
        *,
        should_cancel: Any | None = None,
        run_id: str | None = None,
    ) -> CapabilityResult:
        import uuid
        from datetime import datetime

        from packages.capability_gateway.budget import (
            BudgetWaitCancelled,
            ProviderCapacityExhaustedError,
        )

        try:
            _UTC = datetime.UTC
        except AttributeError:  # pragma: no cover - Python < 3.11
            _UTC = UTC

        route_execution_id = uuid.uuid4().hex
        last_result: CapabilityResult | None = None
        for attempt_index, provider_id in enumerate(plan.providers):
            adapter = self._registry.get(provider_id)
            provider_call_id = uuid.uuid4().hex
            started = datetime.now(_UTC)
            transport_invoked = False
            outcome = "unknown"
            failure_class = None
            result: CapabilityResult | None = None
            permit = None
            try:
                # 1. Circuit guard：OPEN 的 Provider 不得产生 transport call
                if self._circuit is not None and not self._circuit.allow(provider_id):
                    outcome = "circuit_rejected"
                    last_result = CapabilityResult(
                        provider_id=provider_id, success=False,
                        error="provider_circuit_open",
                        route_execution_id=route_execution_id,
                        provider_call_id=provider_call_id,
                    )
                    continue

                if adapter is None:
                    outcome = "no_adapter"
                    last_result = CapabilityResult(
                        provider_id=provider_id, success=False,
                        error=f"no_adapter:{provider_id}",
                        route_execution_id=route_execution_id,
                        provider_call_id=provider_call_id,
                    )
                    continue

                # 2. Concurrency Budget（G2.3）
                if self._budget is not None:
                    try:
                        permit = await self._budget.acquire(
                            provider_instance_id=provider_id,
                            route_execution_id=route_execution_id,
                            provider_call_id=provider_call_id,
                            should_cancel=should_cancel,
                        )
                    except ProviderCapacityExhaustedError:
                        if self._fallback_policy is None:
                            raise  # Legacy：预算超时按 G2.3 传播
                        outcome = "capacity_exhausted"
                        failure_class = self._classifier.classify(
                            ProviderCapacityExhaustedError(provider_id)
                        )
                        last_result = CapabilityResult(
                            provider_id=provider_id, success=False,
                            error="provider_capacity_exhausted",
                            route_execution_id=route_execution_id,
                            provider_call_id=provider_call_id,
                            failure_class=failure_class,
                        )
                        if self._should_fallback(plan, failure_class):
                            continue
                        return last_result
                    except BudgetWaitCancelled:
                        outcome = "cancelled"
                        raise  # 取消 → 不 fallback，不 invoke

                # 3. Transport invoke（G2.2b Adapter）
                transport_invoked = True
                invocation = CapabilityInvocation(
                    capability=plan.capability,
                    task_type=plan.task_type,
                    provider_id=provider_id,
                    payload=payload,
                    provider_call_id=provider_call_id,
                )
                result = await adapter.invoke(invocation)
                result.route_execution_id = route_execution_id
                result.provider_call_id = provider_call_id

                if result.success:
                    outcome = "success"
                    if self._circuit is not None:
                        self._circuit.record_success(provider_id)
                    return result

                # 4. 失败 → 分类 + circuit 反馈
                outcome = "failed"
                failure_class = self._classifier.classify(result)
                result.failure_class = failure_class
                if self._circuit is not None:
                    self._circuit.record_failure(provider_id, failure_class)

                # 5. fallback 判断
                if self._fallback_policy is None:
                    if self._legacy_fallback_eligible(result):
                        last_result = result
                        continue
                elif self._should_fallback(plan, failure_class):
                    last_result = result
                    continue
                return result
            except asyncio.CancelledError:
                outcome = "cancelled"
                raise  # 取消 → 不 fallback
            except BudgetWaitCancelled:
                outcome = "cancelled"
                raise  # 取消 → 不 fallback（outcome 保持 cancelled）
            except Exception as exc:  # noqa: BLE001
                failure_class = self._classifier.classify(exc)
                if self._circuit is not None:
                    self._circuit.record_failure(provider_id, failure_class)
                if self._fallback_policy is not None and self._should_fallback(plan, failure_class):
                    outcome = "failed"
                    last_result = CapabilityResult(
                        provider_id=provider_id, success=False, error=str(exc),
                        route_execution_id=route_execution_id,
                        provider_call_id=provider_call_id,
                        failure_class=failure_class,
                    )
                    continue
                outcome = "failed"
                raise
            finally:
                finished = datetime.now(_UTC)
                self._record_attempt(
                    plan=plan,
                    route_execution_id=route_execution_id,
                    provider_id=provider_id,
                    provider_call_id=provider_call_id,
                    attempt_index=attempt_index,
                    transport_invoked=transport_invoked,
                    outcome=outcome,
                    failure_class=failure_class,
                    started=started,
                    finished=finished,
                    result=result,
                    run_id=run_id,
                )
                if permit is not None and self._budget is not None:
                    await self._budget.release(permit)

        if last_result is not None:
            last_result.route_execution_id = route_execution_id
            if not last_result.error:
                last_result.error = "all_providers_failed"
            return last_result
        return CapabilityResult(
            provider_id=plan.primary or "",
            success=False,
            error="all_providers_failed",
            route_execution_id=route_execution_id,
        )


# ── SEARCH 适配器（桥接现有 AnySearch/Tavily client，G2.2b 时启用） ─────────────

def build_search_adapter_registry(
    settings: Any = None,
    *,
    anysearch_transport: Any = None,
    tavily_transport: Any = None,
) -> ProviderAdapterRegistry:
    """把现有同步 Search client 桥接为 CapabilityAdapter，注册到 ProviderAdapterRegistry。

    只桥接/规范化，不复制 Provider HTTP 实现。transport 可注入（测试用 fake）。
    仅当 routing mode == gateway（G2.2b）时才会被 invoke；shadow 模式不会调用。
    """
    from packages.sources.enums import ToolStatus
    from packages.sources.search_discovery import (
        AnySearchSearchAdapter,
        SearchDiscoveryResponse,
        TavilySearchAdapter,
        anysearch_settings_from_app_settings,
        tavily_settings_from_app_settings,
    )

    app = settings  # 让调用方传 settings；None 时用默认（可能缺 key）
    anysearch = AnySearchSearchAdapter(
        settings=anysearch_settings_from_app_settings(app) if app else None,
        transport=anysearch_transport,
    )
    tavily = TavilySearchAdapter(
        settings=tavily_settings_from_app_settings(app) if app else None,
        transport=tavily_transport,
    )

    def _search_fn(client, instance_id: str):
        def _invoke(invocation: CapabilityInvocation) -> CapabilityResult:
            request = invocation.payload.get("request")
            resp: SearchDiscoveryResponse = client.search(request)
            failure_class = None
            if resp.status != ToolStatus.SUCCESS:
                # AnySearch/Tavily adapter 把 provider 错误吞成 ERROR response
                #（不是抛异常），因此这里从 response errors 还原 failure_class——
                # 否则 FailureClassifier 只能看到 success=False → OUTPUT_INVALID →
                # FallbackPolicy 不允许 fallback，search 回退失效。
                from packages.capability_gateway.circuit import (
                    ProviderFailureClass,
                    _from_status_code,
                )

                status_code = None
                retryable = None
                for err in resp.errors:
                    detail = getattr(err, "detail", None) or {}
                    if isinstance(detail, dict):
                        status_code = detail.get("status_code")
                        if status_code is not None:
                            break
                        # 网络层错误（如 SSL UNEXPECTED_EOF）detail 只有 reason，
                        # 无 status_code → 按 retryable 兜底为 NETWORK。
                        if detail.get("reason") and retryable is None:
                            retryable = bool(getattr(err, "retryable", False))
                if status_code is not None:
                    failure_class = _from_status_code(status_code)
                elif retryable:
                    # 无 status_code 但标记可重试 → 网络/上游不稳定，可 fallback
                    failure_class = ProviderFailureClass.NETWORK
            return CapabilityResult(
                provider_id=instance_id,
                success=resp.status == ToolStatus.SUCCESS,
                data=resp,
                error=(
                    "; ".join(e.message for e in resp.errors)
                    if resp.errors else None
                ),
                # G2.5a 用量：Search 记录 result_count（透传，不记录 raw content）
                result_count=len(resp.results),
                request_count=1,
                failure_class=failure_class,
            )
        return _invoke

    registry = ProviderAdapterRegistry()
    registry.register(
        "anysearch.primary",
        CallableAdapter("anysearch.primary", _search_fn(anysearch, "anysearch.primary")),
    )
    registry.register(
        "tavily.fallback",
        CallableAdapter("tavily.fallback", _search_fn(tavily, "tavily.fallback")),
    )
    return registry


# ── LLM 适配器（桥接现有 DeepSeek/OpenRouter client，G2-M1 启用） ──────────────

def _build_deepseek_client(settings: Any = None, *, max_tokens: int | None = None):
    """构造 DeepSeekProviderClient（settings 缺失 key → None）。"""
    from packages.core.config import get_settings
    from packages.providers import DeepSeekProviderClient, ProviderConfigError

    app = settings or get_settings()
    try:
        return DeepSeekProviderClient(
            api_key=app.deepseek_api_key,
            base_url=app.deepseek_base_url,
            model=app.deepseek_research_model,
            timeout_seconds=app.deepseek_timeout_seconds,
            max_retries=app.deepseek_max_retries,
            max_tokens=max_tokens or app.deepseek_max_tokens,
            store_reasoning_content=app.deepseek_store_reasoning_content,
        )
    except ProviderConfigError:
        return None


def _usage_tokens(usage: Any) -> tuple[int | None, int | None]:
    if not isinstance(usage, dict):
        return None, None
    in_tok = usage.get("input_tokens") or usage.get("prompt_tokens")
    out_tok = usage.get("output_tokens") or usage.get("completion_tokens")
    return in_tok, out_tok


class _LlmClientAdapter:
    """把同步 LLM client（DeepSeek/OpenRouter 兼容）包成 async CapabilityAdapter。

    异常原样抛出 → 由 Invoker 的 FailureClassifier 分类 + FallbackPolicy 决定
    是否尝试下一个 Provider（保持错误语义）。

    max_tokens 处理（2026-08-12 审计修复）：DeepSeek client 的 max_tokens 是
    构造时设定（providers/deepseek.py:69），generate_json 无 per-call 参数。
    client_factory 允许按 payload.max_tokens 重建 client（大 prompt 如 editor1
    喂 67 条 evidence 需要 max_tokens=4000-8000，默认 1200 会截断）。
    """

    def __init__(
        self,
        instance_id: str,
        client: Any,
        *,
        client_factory: Any | None = None,
    ) -> None:
        self._instance_id = instance_id
        self._client = client
        self._client_factory = client_factory

    async def invoke(self, invocation: CapabilityInvocation) -> CapabilityResult:
        payload = invocation.payload
        output = payload.get("output", "json")
        kwargs = {
            "system_prompt": payload.get("system_prompt", ""),
            "user_prompt": payload.get("user_prompt", ""),
            "model": payload.get("model"),
            "enable_thinking": payload.get("enable_thinking", False),
            "temperature": payload.get("temperature"),
            "top_p": payload.get("top_p"),
            "presence_penalty": payload.get("presence_penalty"),
            "frequency_penalty": payload.get("frequency_penalty"),
        }
        client = self._client
        max_tokens = payload.get("max_tokens")
        if max_tokens and self._client_factory is not None:
            client = self._client_factory(max_tokens=int(max_tokens))
        if output == "json":
            resp = client.generate_json(**kwargs)
        else:
            resp = client.generate_text(**kwargs)
        in_tok, out_tok = _usage_tokens(
            getattr(getattr(resp, "metadata", None), "usage", None)
        )
        return CapabilityResult(
            provider_id=self._instance_id,
            success=True,
            data=resp,
            input_tokens=in_tok,
            output_tokens=out_tok,
        )


class _OpenRouterUnavailableClient:
    """OpenRouter 未配置（无 key）时的占位 client：invoke 即抛 ProviderConfigError。

    被 _build_openrouter_client 选用：key 存在 → 真实 client；key 缺失 →
    占位（fallback 尝试时抛错，FailureClassifier 归类后决定是否继续 fallback）。
    """

    def generate_json(self, **kwargs):  # noqa: ARG002
        from packages.providers import ProviderConfigError

        raise ProviderConfigError("OpenRouter is not configured (no openrouter client).")

    def generate_text(self, **kwargs):  # noqa: ARG002
        return self.generate_json(**kwargs)


def _build_openrouter_client(settings: Any = None, *, max_tokens: int | None = None):
    """构造 OpenRouterProviderClient（settings 缺 key → 占位抛错 client）。"""
    from packages.core.config import get_settings
    from packages.providers import OpenRouterProviderClient, ProviderConfigError

    app = settings or get_settings()
    try:
        return OpenRouterProviderClient(
            api_key=app.openrouter_api_key,
            base_url=app.openrouter_base_url,
            model=app.openrouter_free_model,
            timeout_seconds=app.openrouter_timeout_seconds,
            max_retries=app.openrouter_max_retries,
            max_tokens=max_tokens or app.openrouter_max_tokens,
        )
    except ProviderConfigError:
        return _OpenRouterUnavailableClient()


def build_llm_adapter_registry(
    settings: Any = None,
    *,
    deepseek_client: Any = None,
    openrouter_client: Any = None,
) -> ProviderAdapterRegistry:
    """把现有同步 LLM client 桥接为 CapabilityAdapter。

    - deepseek_client 可注入（测试 fake）；默认从 settings 构造。
    - openrouter_client 可注入；默认从 settings 构造真实 client
      （key 缺失 → 占位抛错，best-effort fallback 路径真实兜底）。
    - DeepSeek adapter 绑定 client_factory：按 payload.max_tokens 重建 client
      （大 prompt 不被默认 1200 截断）。注入的 fake client 不重建（测试场景）。
    - OpenRouter adapter 同样支持按 payload.max_tokens 重建（免费模型 context 小，
      max_tokens 上限更严格）。
    """
    registry = ProviderAdapterRegistry()
    ds = deepseek_client if deepseek_client is not None else _build_deepseek_client(settings)

    def _ds_with_max_tokens(max_tokens: int):
        if deepseek_client is not None:
            return deepseek_client  # 注入的 fake：已处理 kwargs，不重建
        return _build_deepseek_client(settings, max_tokens=max_tokens)

    if ds is not None:
        registry.register(
            "deepseek.chat.primary",
            _LlmClientAdapter("deepseek.chat.primary", ds, client_factory=_ds_with_max_tokens),
        )
    or_client = (
        openrouter_client
        if openrouter_client is not None
        else _build_openrouter_client(settings)
    )

    def _or_with_max_tokens(max_tokens: int):
        if openrouter_client is not None:
            return openrouter_client  # 注入的 fake：不重建
        return _build_openrouter_client(settings, max_tokens=max_tokens)

    registry.register(
        "openrouter.free.best_effort",
        _LlmClientAdapter(
            "openrouter.free.best_effort", or_client, client_factory=_or_with_max_tokens
        ),
    )
    return registry


__all__ = [
    "CallableAdapter",
    "CapabilityAdapter",
    "CapabilityInvocation",
    "CapabilityResult",
    "ProviderAdapterRegistry",
    "RoutingInvoker",
    "build_search_adapter_registry",
    "build_llm_adapter_registry",
    "_LlmClientAdapter",
]
