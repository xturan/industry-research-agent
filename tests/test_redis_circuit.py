"""G2.4 RedisCircuitStateStore — Redis Hash 熔断状态测试。

镜像 test_capability_circuit.py 断言集：3 失败→OPEN→allow False、cooldown 后
HALF_OPEN probe、probe 成功/失败、capacity/quality 不污染、per-provider 独立、
丢失安全（flushdb 模拟重启 → CLOSED）、TTL 过期 → CLOSED。
"""

from __future__ import annotations

import fakeredis

from packages.capability_gateway import (
    CircuitBreaker,
    InMemoryCircuitStateStore,
    ProviderFailureClass,
    RedisCircuitStateStore,
)
from packages.capability_gateway.circuit import CircuitState


class _Clock:
    def __init__(self, t0):
        from datetime import UTC, datetime

        self.now = datetime(2026, 1, 1, tzinfo=UTC)

    def __call__(self):
        return self.now


def _store(client=None, *, ttl: float = 120.0):
    client = client or fakeredis.FakeRedis(decode_responses=True)
    return RedisCircuitStateStore(client, record_ttl_seconds=ttl)


def _breaker(store=None, *, threshold: int = 3, cooldown: float = 30.0):
    from datetime import UTC, datetime

    clock = _Clock(datetime(2026, 1, 1, tzinfo=UTC))
    store = store or _store()
    return CircuitBreaker(
        store, failure_threshold=threshold, cooldown_seconds=cooldown, now_provider=clock
    ), clock


def _advance(clock, seconds: float):
    from datetime import timedelta

    clock.now = clock.now + timedelta(seconds=seconds)


# ── 状态机 ──────────────────────────────────────────────────────────────────

def test_three_failures_open_then_block():
    store = _store()
    breaker, _ = _breaker(store)
    for _ in range(3):
        breaker.record_failure("p", ProviderFailureClass.NETWORK)
    assert store.get("p").state == CircuitState.OPEN
    assert breaker.allow("p") is False  # OPEN 不产生 transport


def test_cooldown_advances_to_half_open_probe():
    store = _store()
    breaker, clock = _breaker(store)
    for _ in range(3):
        breaker.record_failure("p", ProviderFailureClass.TIMEOUT)
    assert breaker.allow("p") is False
    _advance(clock, 31)  # 超过 cooldown 30s
    assert breaker.allow("p") is True  # HALF_OPEN probe
    assert store.get("p").state == CircuitState.HALF_OPEN


def test_probe_success_recovery_to_closed():
    store = _store()
    breaker, clock = _breaker(store)
    for _ in range(3):
        breaker.record_failure("p", ProviderFailureClass.NETWORK)
    _advance(clock, 31)
    breaker.allow("p")  # HALF_OPEN probe
    breaker.record_success("p")
    assert store.get("p").state == CircuitState.CLOSED
    assert breaker.allow("p") is True


def test_probe_failure_reopens():
    store = _store()
    breaker, clock = _breaker(store)
    for _ in range(3):
        breaker.record_failure("p", ProviderFailureClass.NETWORK)
    _advance(clock, 31)
    breaker.allow("p")  # probe
    breaker.record_failure("p", ProviderFailureClass.NETWORK)
    assert store.get("p").state == CircuitState.OPEN
    assert breaker.allow("p") is False


# ── 不污染 circuit ──────────────────────────────────────────────────────────

def test_capacity_exhausted_does_not_open():
    store = _store()
    breaker, _ = _breaker(store)
    for _ in range(5):
        breaker.record_failure("p", ProviderFailureClass.CAPACITY_EXHAUSTED)
    assert store.get("p").state == CircuitState.CLOSED  # capacity 不计入熔断
    assert breaker.allow("p") is True


def test_business_validation_does_not_open():
    store = _store()
    breaker, _ = _breaker(store)
    for _ in range(5):
        breaker.record_failure("p", ProviderFailureClass.OUTPUT_INVALID)
    assert store.get("p").state == CircuitState.CLOSED
    assert breaker.allow("p") is True


# ── per-provider 独立 ───────────────────────────────────────────────────────

def test_per_provider_independent():
    store = _store()
    breaker, _ = _breaker(store)
    for _ in range(3):
        breaker.record_failure("p", ProviderFailureClass.NETWORK)
    assert breaker.allow("p") is False
    assert breaker.allow("other") is True  # 独立 provider 不受影响


# ── 丢失安全（Redis 重启 / TTL 过期 → CLOSED） ──────────────────────────────

def test_flushdb_returns_closed():
    store = _store()
    breaker, clock = _breaker(store)
    for _ in range(3):
        breaker.record_failure("p", ProviderFailureClass.NETWORK)
    assert store.get("p").state == CircuitState.OPEN
    # 模拟 Redis 重启
    store._client.flushdb()
    rec = store.get("p")
    assert rec.state == CircuitState.CLOSED  # 缺失 = 安全默认
    assert breaker.allow("p") is True


def test_ttl_expiry_returns_closed():
    store = _store(ttl=0.1)
    breaker, clock = _breaker(store, cooldown=30.0)
    for _ in range(3):
        breaker.record_failure("p", ProviderFailureClass.NETWORK)
    assert store.get("p").state == CircuitState.OPEN
    import time as _t

    _t.sleep(0.15)  # 超过 record_ttl_seconds=0.1，Redis key 过期
    rec = store.get("p")
    assert rec.state == CircuitState.CLOSED  # TTL 过期 → CLOSED


# ── epoch 往返精确性（假时钟照常工作） ─────────────────────────────────────

def test_clock_independent_epoch_storage():
    """store 存 epoch ms，CircuitBreaker 的 now_provider（假时钟）照常工作。"""
    store = _store()
    breaker, clock = _breaker(store)
    for _ in range(3):
        breaker.record_failure("p", ProviderFailureClass.NETWORK)
    rec = store.get("p")
    assert rec.opened_at is not None
    assert rec.next_probe_at is not None
    # 与 InMemory store 语义一致
    inmem = CircuitBreaker(
        InMemoryCircuitStateStore(), failure_threshold=3, cooldown_seconds=30,
        now_provider=clock,
    )
    for _ in range(3):
        inmem.record_failure("p", ProviderFailureClass.NETWORK)
    rec2 = inmem._store.get("p")
    assert rec.state == rec2.state
    assert rec.consecutive_failures == rec2.consecutive_failures
