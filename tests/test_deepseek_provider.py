from __future__ import annotations

from types import SimpleNamespace

import pytest

from packages.providers.base import ProviderParseError
from packages.providers.deepseek import DeepSeekProviderClient


def _make_completion(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="resp-1",
        usage={"prompt_tokens": 10, "completion_tokens": 20},
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=content, reasoning_content=None),
            )
        ],
    )


def test_deepseek_generate_json_repairs_once(monkeypatch) -> None:
    responses = [_make_completion("not-json"), _make_completion('{"ok": true, "value": 1}')]

    class _FakeChatCompletions:
        def create(self, **kwargs):  # noqa: ANN003
            return responses.pop(0)

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeChatCompletions()))
    monkeypatch.setattr("packages.providers.deepseek.OpenAI", object)

    provider = DeepSeekProviderClient(
        api_key="x",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-reasoner",
        timeout_seconds=30,
        max_retries=0,
        client=fake_client,
    )
    response = provider.generate_json(
        system_prompt="Return JSON",
        user_prompt="input",
        enable_thinking=False,
    )
    assert response.json_data == {"ok": True, "value": 1}


def test_deepseek_generate_json_raises_after_failed_repair(monkeypatch) -> None:
    responses = [_make_completion("not-json"), _make_completion("still-not-json")]

    class _FakeChatCompletions:
        def create(self, **kwargs):  # noqa: ANN003
            return responses.pop(0)

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeChatCompletions()))
    monkeypatch.setattr("packages.providers.deepseek.OpenAI", object)

    provider = DeepSeekProviderClient(
        api_key="x",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-reasoner",
        timeout_seconds=30,
        max_retries=0,
        client=fake_client,
    )

    with pytest.raises(ProviderParseError):
        provider.generate_json(
            system_prompt="Return JSON",
            user_prompt="input",
            enable_thinking=False,
        )
