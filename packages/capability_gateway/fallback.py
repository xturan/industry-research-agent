"""G2.4b FallbackPolicy — 某类 Runtime Failure 是否允许进入下一个 Provider。

不是「容量满就换 Provider」。是否 fallback 由 workload 的 RoutingPolicy +
FailureClass 显式决定：

| Failure              | FALLBACK_ALLOWED | STRICT |
| -------------------- | ---------------: | -----: |
| NETWORK              |              ✅  |      ❌ |
| TIMEOUT              |              ✅  |      ❌ |
| RATE_LIMIT(429)      |              ✅  |      ❌ |
| PROVIDER_5XX         |              ✅  |      ❌ |
| CAPACITY_EXHAUSTED   |              ✅  |      ❌ |
| AUTH / QUOTA /       |              ❌  |      ❌ |
| OUTPUT_INVALID /     |              ❌  |      ❌ |
| BUSINESS_VALIDATION /|              ❌  |      ❌ |
| CANCELLED            |              ❌  |      ❌ |

重要边界：
- Runtime fallback 只能在 `RoutingPlan.fallback_chain` 内执行，不得临时发现新 Provider。
- STRICT workload 一律不 fallback（G2.2 contract 在 G2.4 不破坏）。
- CAPACITY_EXHAUSTED：先经过 G2.3 bounded wait，timeout 后才进入 fallback 判断。
- Cancellation 不得产生 fallback。
"""

from __future__ import annotations

from packages.capability_gateway.circuit import ProviderFailureClass
from packages.capability_gateway.schemas import RoutingPolicy

# FALLBACK_ALLOWED 第一版允许的 failure class。
_FALLBACK_ELIGIBLE = {
    ProviderFailureClass.NETWORK,
    ProviderFailureClass.TIMEOUT,
    ProviderFailureClass.RATE_LIMIT,
    ProviderFailureClass.PROVIDER_5XX,
    ProviderFailureClass.CAPACITY_EXHAUSTED,
}


class FallbackPolicy:
    """决定某类 failure 是否允许 fallback。可解释、可测试。"""

    def should_fallback(
        self,
        *,
        routing_policy: RoutingPolicy,
        failure_class: ProviderFailureClass | None,
    ) -> bool:
        if routing_policy != RoutingPolicy.FALLBACK_ALLOWED:
            return False  # STRICT 一律不 fallback
        if failure_class is None:
            return False
        return failure_class in _FALLBACK_ELIGIBLE


__all__ = ["FallbackPolicy"]
