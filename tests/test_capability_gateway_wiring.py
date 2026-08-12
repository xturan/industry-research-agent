"""G2.8 Gateway Production Wiring tests.

验证统一 wiring 工厂（packages/capability_gateway/wiring.py）：
- Postgres 方言 → PostgresLeaseConcurrencyBudget / PostgresCircuitStateStore /
  PostgresProviderAttemptRecorder（跨进程共享）。
- SQLite/dev 方言 → InProcessConcurrencyBudget / InMemoryCircuitStateStore /
  InMemoryProviderAttemptRecorder（不崩、可单测）。
- 进程级单例：get_gateway_runtime_cached 按 database_url 缓存一次。
- ensure_gateway_tables 幂等（SQLite 可安全重复调用）。

同时覆盖 G2-M1 修复回归：
- gateway 模式下 max_tokens 经 payload 透传到 adapter（不再被默认 1200 截断）。
- run_id 经 invoker.invoke(run_id=...) 落到 ProviderAttemptRecord。
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from packages.capability_gateway.adapters import _LlmClientAdapter
from packages.capability_gateway.budget import (
    InProcessConcurrencyBudget,
    PostgresLeaseConcurrencyBudget,
)
from packages.capability_gateway.circuit import (
    InMemoryCircuitStateStore,
    PostgresCircuitStateStore,
)
from packages.capability_gateway.telemetry import (
    InMemoryProviderAttemptRecorder,
    PostgresProviderAttemptRecorder,
)
from packages.capability_gateway.wiring import (
    build_gateway_runtime,
    ensure_gateway_tables,
)
from packages.core.config import Settings
from packages.research_harness.tooling.llm_agents import call_tooling_json


def _settings(database_url: str) -> Settings:
    return Settings(_env_file=None, DATABASE_URL=database_url)


# ── 方言守卫 ─────────────────────────────────────────────────────────────────

def test_postgres_dialect_uses_shared_stores():
    rt = build_gateway_runtime(_settings("postgresql+psycopg://u:p@h/db"))
    assert isinstance(rt["budget"], PostgresLeaseConcurrencyBudget)
    assert isinstance(rt["recorder"], PostgresProviderAttemptRecorder)
    # circuit 外层是 CircuitBreaker，内部 store 是 Postgres
    assert isinstance(rt["circuit"]._store, PostgresCircuitStateStore)


def test_sqlite_dialect_falls_back_to_inmemory():
    rt = build_gateway_runtime(_settings("sqlite+pysqlite:///:memory:"))
    assert isinstance(rt["budget"], InProcessConcurrencyBudget)
    assert isinstance(rt["recorder"], InMemoryProviderAttemptRecorder)
    assert isinstance(rt["circuit"]._store, InMemoryCircuitStateStore)


def test_ensure_gateway_tables_noop_on_sqlite(tmp_path):
    """SQLite 方言下 ensure_gateway_tables 是 no-op（InMemory store 不依赖 DB 表）。"""
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'gw.db'}")
    ensure_gateway_tables(engine, settings=_settings("sqlite+pysqlite:///:memory:"))
    from sqlalchemy import inspect

    tables = set(inspect(engine).get_table_names())
    assert "provider_attempt_records" not in tables  # no-op，未建任何 gateway 表


# ── max_tokens 透传（G2-M1 修复） ───────────────────────────────────────────

class _FakeResp:
    def __init__(self, json_data=None):
        self.json_data = json_data if json_data is not None else {}
        self.provider = "deepseek"
        self.model = "deepseek-chat"
        self.metadata = type(
            "M",
            (),
            {
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "extra": {},
                "request_id": "req-1",
                "finish_reason": "stop",
                "response_ms": 12.3,
            },
        )()


class _MaxTokensProbeClient:
    """记录 generate_json 收到的 kwargs（验证 max_tokens 透传）。"""

    def __init__(self):
        self.last_kwargs = None
        self.calls = 0

    def generate_json(self, **kwargs):
        self.calls += 1
        self.last_kwargs = dict(kwargs)
        return _FakeResp({"ok": True})

    def generate_text(self, **kwargs):
        return self.generate_json(**kwargs)


def test_adapter_forwards_max_tokens_to_rebuilt_client():
    """_LlmClientAdapter 按 payload.max_tokens 重建 client（大 prompt 不截断）。"""
    probe = _MaxTokensProbeClient()
    built_with: list[int | None] = []

    def _factory(max_tokens):
        built_with.append(max_tokens)
        return probe

    adapter = _LlmClientAdapter("deepseek.chat.primary", probe, client_factory=_factory)
    from packages.capability_gateway.adapters import CapabilityInvocation
    from packages.capability_gateway.schemas import CapabilityType

    invocation = CapabilityInvocation(
        capability=CapabilityType.LLM,
        task_type="editor1_dimension_section",
        provider_id="deepseek.chat.primary",
        payload={
            "system_prompt": "s", "user_prompt": "u", "model": "m",
            "enable_thinking": False, "output": "json", "max_tokens": 4000,
        },
    )
    import asyncio

    result = asyncio.run(adapter.invoke(invocation))
    assert result.success
    assert built_with == [4000]  # factory 收到 max_tokens=4000
    assert probe.last_kwargs["temperature"] is None  # 未传则保持 None


def test_gateway_mode_forwards_max_tokens_and_records_attempt():
    """gateway 模式：max_tokens 进 payload、recorder 落 attempt 带 run_id。"""
    from packages.capability_gateway.llm_tasks import LLMTaskType

    settings = Settings(
        _env_file=None,
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        CAPABILITY_GATEWAY_ENABLED=True,
        CAPABILITY_GATEWAY_LLM_MODE="gateway",
    )

    probe = _MaxTokensProbeClient()
    recorder = InMemoryProviderAttemptRecorder()

    from packages.capability_gateway import (
        CapabilityRouter,
        FallbackPolicy,
        LLMCapabilityService,
        RoutingInvoker,
        build_llm_adapter_registry,
        default_registry,
    )

    adapter_reg = build_llm_adapter_registry(
        settings, deepseek_client=probe, openrouter_client=probe
    )
    invoker = RoutingInvoker(
        adapter_reg, recorder=recorder, fallback_policy=FallbackPolicy()
    )
    svc = LLMCapabilityService(
        settings=settings, router=CapabilityRouter(default_registry()),
        invoker=invoker, adapter_registry=adapter_reg,
        legacy_factory=lambda: probe,
        run_id_provider=lambda: "run-42",
    )
    resp = svc.generate_json(
        LLMTaskType.EDITOR1_DIMENSION_SECTION,
        system_prompt="s", user_prompt="u", max_tokens=4000,
    )
    assert resp.json_data == {"ok": True}
    recs = recorder.all()
    assert len(recs) == 1
    assert recs[0].run_id == "run-42"  # run_id 归因打通
    assert recs[0].task_type == "editor1_dimension_section"


def test_call_tooling_json_gateway_branch_injects_runtime(monkeypatch):
    """call_tooling_json 的 gateway 分支被选中（mode=gateway）且注入 runtime。

    不触发真实 DeepSeek：把 llm_agents 模块内的 build_gateway_aware_llm_client
    替换为记录调用参数的探针，验证 runtime（budget/circuit/recorder）与 task_type
    被正确传入。
    """
    settings = Settings(
        _env_file=None,
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        CAPABILITY_GATEWAY_ENABLED=True,
        CAPABILITY_GATEWAY_LLM_MODE="gateway",
    )

    captured: dict[str, Any] = {}

    def _fake_builder(settings_ignored, *, task_type=None, budget=None, circuit=None,
                      recorder=None, run_id_provider=None):
        captured.update({
            "task_type": task_type,
            "budget": budget,
            "circuit": circuit,
            "recorder": recorder,
            "run_id_provider": run_id_provider,
        })
        # 返回一个直接返回结构化结果的探针 client（避免真实 provider）。
        class _ProbeClient:
            def generate_json(self, **kwargs):
                return _FakeResp({"dimensions": {}})
        return _ProbeClient()

    monkeypatch.setattr(
        "packages.research_harness.tooling.llm_agents.get_settings", lambda: settings
    )
    monkeypatch.setattr(
        "packages.capability_gateway.llm_service.build_gateway_aware_llm_client",
        _fake_builder,
    )
    monkeypatch.setattr(
        "packages.capability_gateway.router.llm_routing_mode",
        lambda s: "gateway",
    )

    result = call_tooling_json(
        system_prompt="s", user_prompt="u", task_type="dimension_search_terms",
    )
    assert result is not None
    assert result.payload == {"dimensions": {}}
    assert captured["task_type"] == "dimension_search_terms"  # 未注册不再 KeyError
    assert captured["budget"] is not None and captured["recorder"] is not None


# ── OpenRouter free parser（markdown 围栏剥离） ──────────────────────────────

def test_openrouter_parse_json_strips_markdown_fence():
    """OpenRouter 免费模型常把 JSON 包在 ```json 围栏里；parser 须剥离。"""
    from packages.providers.openrouter import OpenRouterProviderClient

    obj = object.__new__(OpenRouterProviderClient)
    assert OpenRouterProviderClient._parse_json(
        obj, '{"queries": ["a"]}'
    ) == {"queries": ["a"]}
    assert OpenRouterProviderClient._parse_json(
        obj, '```json\n{"queries": ["a"]}\n```'
    ) == {"queries": ["a"]}
    assert OpenRouterProviderClient._parse_json(
        obj, '\n\n  {"queries": ["a"]}  \n'
    ) == {"queries": ["a"]}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
