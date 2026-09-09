"""G2.4a Failure Classification + Circuit Breaker tests。

覆盖：10 类 Failure 分类、availability 才计入 circuit、OPEN 不产生 transport、
cooldown→HALF_OPEN probe、probe 成功/失败、capacity/quality 不污染 circuit、
per-provider 独立。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from packages.capability_gateway import (
    AVAILABILITY_FAILURES,
    BudgetWaitCancelled,
    CapabilityResult,
    CircuitBreaker,
    FailureClassifier,
    InMemoryCircuitStateStore,
    ProviderCapacityExhaustedError,
    ProviderFailureClass,
)


class _Clock:
    def __init__(self, t0: datetime) -> None:
        self.now = t0

    def __call__(self) -> datetime:
        return self.now


def _breaker(
    store=None, *, threshold: int = 3, cooldown: float = 30.0, clock=None
) -> tuple[CircuitBreaker, _Clock]:
    clock = clock or _Clock(datetime(2026, 1, 1, tzinfo=UTC))
    store = store or InMemoryCircuitStateStore()
    return CircuitBreaker(
        store, failure_threshold=threshold, cooldown_seconds=cooldown, now_provider=clock
    ), clock


# ── Failure classification ───────────────────────────────────────────────────

def test_classify_timeout_and_network():
    clf = FailureClassifier()
    assert clf.classify(TimeoutError("slow")) == ProviderFailureClass.TIMEOUT
    assert clf.classify(ConnectionError("reset")) == ProviderFailureClass.NETWORK


def test_classify_budget_and_cancel():
    clf = FailureClassifier()
    assert clf.classify(ProviderCapacityExhaustedError("deepseek.chat.primary")) == (
        ProviderFailureClass.CAPACITY_EXHAUSTED
    )
    assert clf.classify(BudgetWaitCancelled()) == ProviderFailureClass.CANCELLED
    assert clf.classify(asyncio.CancelledError()) == ProviderFailureClass.CANCELLED


def test_classify_http_status():
    clf = FailureClassifier()
    from packages.sources.search_discovery import SourceAnySearchError

    err429 = SourceAnySearchError("429", retryable=True, detail={"status_code": 429})
    err500 = SourceAnySearchError("500", retryable=True, detail={"status_code": 500})
    err403 = SourceAnySearchError("403", retryable=False, detail={"status_code": 403})
    assert clf.classify(err429) == ProviderFailureClass.RATE_LIMIT
    assert clf.classify(err500) == ProviderFailureClass.PROVIDER_5XX
    assert clf.classify(err403) == ProviderFailureClass.AUTH


def test_classify_capability_result():
    clf = FailureClassifier()
    assert clf.classify(CapabilityResult(provider_id="x", success=False)) == (
        ProviderFailureClass.OUTPUT_INVALID
    )
    assert clf.classify(CapabilityResult(
        provider_id="x", success=False, failure_class=ProviderFailureClass.TIMEOUT
    )) == ProviderFailureClass.TIMEOUT


def test_availability_failures_set():
    assert AVAILABILITY_FAILURES == {
        ProviderFailureClass.NETWORK,
        ProviderFailureClass.TIMEOUT,
        ProviderFailureClass.RATE_LIMIT,
        ProviderFailureClass.PROVIDER_5XX,
    }


# ── Circuit state machine ────────────────────────────────────────────────────

def test_three_failures_open_and_no_transport():
    breaker, _ = _breaker()
    for _ in range(3):
        breaker.record_failure("dp", ProviderFailureClass.TIMEOUT)
    assert breaker.allow("dp") is False  # OPEN → 不产生 transport call


def test_cooldown_opens_half_open_then_probe_success_closes():
    breaker, clock = _breaker()
    for _ in range(3):
        breaker.record_failure("dp", ProviderFailureClass.TIMEOUT)
    assert breaker.allow("dp") is False
    # cooldown 过去
    clock.now += timedelta(seconds=31)
    assert breaker.allow("dp") is True  # → HALF_OPEN probe
    breaker.record_success("dp")  # probe 成功
    assert breaker.allow("dp") is True  # CLOSED 后任意请求都放行


def test_probe_failure_reopens():
    breaker, clock = _breaker()
    for _ in range(3):
        breaker.record_failure("dp", ProviderFailureClass.TIMEOUT)
    clock.now += timedelta(seconds=31)
    assert breaker.allow("dp") is True  # HALF_OPEN
    breaker.record_failure("dp", ProviderFailureClass.NETWORK)  # probe 失败
    assert breaker.allow("dp") is False  # 回 OPEN


def test_capacity_does_not_pollute_circuit():
    breaker, _ = _breaker()
    breaker.record_failure("dp", ProviderFailureClass.CAPACITY_EXHAUSTED)
    breaker.record_failure("dp", ProviderFailureClass.OUTPUT_INVALID)
    assert breaker.allow("dp") is True  # 仍 CLOSED
    assert breaker.allow("dp") is True


def test_business_validation_not_provider_outage():
    breaker, _ = _breaker()
    breaker.record_failure("dp", ProviderFailureClass.BUSINESS_VALIDATION)
    assert breaker.allow("dp") is True


def test_per_provider_independence():
    breaker, _ = _breaker()
    for _ in range(3):
        breaker.record_failure("dp", ProviderFailureClass.TIMEOUT)
    assert breaker.allow("dp") is False  # deepseek OPEN
    assert breaker.allow("openrouter.free.best_effort") is True  # 另一个不受影响
