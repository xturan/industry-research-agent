"""Tests for the LLM reranker inference protocol (rerankers.py).

Covers the handoff v6 protocol: exact training prompt template, token-logprobs
expected_score parsing, text-regex fallback, and model-unavailable degradation.
"""

from __future__ import annotations

import pytest

from packages.rag import rerankers


class _FakeResp:
    def __init__(self, data, status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data


def _logprobs_response(bucket: str = "4") -> dict:
    """OpenAI chat-completions response shape with top_logprobs on the digits."""
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": bucket},
                "logprobs": {
                    "content": [
                        {
                            "token": bucket,
                            "logprob": -0.1,
                            "top_logprobs": [
                                {"token": "4", "logprob": -0.1},
                                {"token": "3", "logprob": -0.5},
                                {"token": "2", "logprob": -2.0},
                                {"token": "1", "logprob": -3.0},
                                {"token": "0", "logprob": -4.0},
                            ],
                        }
                    ]
                },
            }
        ]
    }


def test_parse_rerank_response_uses_logprobs_expected_score():
    resp = _FakeResp(_logprobs_response(bucket="4"))
    bucket, expected = rerankers._parse_rerank_response(resp)
    assert bucket == 4
    assert expected == pytest.approx(3.3586, abs=0.01)


def test_parse_rerank_response_falls_back_to_text_regex():
    resp = _FakeResp({
        "choices": [{"message": {"role": "assistant", "content": "3"}, "logprobs": None}]
    })
    bucket, expected = rerankers._parse_rerank_response(resp)
    assert bucket == 3
    assert expected == 3.0


def test_parse_rerank_response_no_choices_returns_none():
    assert rerankers._parse_rerank_response(_FakeResp({"choices": []})) == (None, 0.0)
    assert rerankers._parse_rerank_response(_FakeResp({})) == (None, 0.0)


def test_rerank_with_llm_happy_path_sends_v6_prompt(monkeypatch):
    captured: dict = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResp(_logprobs_response(bucket="4"))

    monkeypatch.setattr("requests.post", fake_post)
    chunks = [{"chunk_id": "a_chunk_0", "chunk_text": "2023年浏阳烟花产值突破500亿元。"}]
    out = rerankers.rerank_with_llm(
        "湖南浏阳烟花产业发展", chunks, model_endpoint="http://m/v1", model_name="rerank-lora"
    )
    assert out[0]["chunk_id"] == "a_chunk_0"
    assert out[0]["rerank_bucket"] == 4
    assert out[0]["rerank_score"] == pytest.approx(0.8397, abs=0.01)

    payload = captured["json"]
    assert payload["model"] == "rerank-lora"
    assert payload["max_tokens"] == 1
    assert payload["logprobs"] is True
    content = payload["messages"][0]["content"]
    assert content.startswith("### Instruction:")
    assert "### Response:\n" in content
    assert "湖南浏阳烟花产业发展" in content
    assert "2023年浏阳烟花产值突破500亿元。" in content


def test_rerank_with_llm_model_down_returns_neutral(monkeypatch):
    def boom(url, json=None, timeout=None):
        raise ConnectionError("vllm down")

    monkeypatch.setattr("requests.post", boom)
    chunks = [{"chunk_id": "a_chunk_0", "chunk_text": "正文"}]
    out = rerankers.rerank_with_llm("q", chunks, model_endpoint="http://m/v1", model_name="m")
    assert out[0]["rerank_score"] == 0.5
    assert out[0]["rerank_bucket"] is None


def test_rerank_with_llm_retries_without_logprobs_on_400(monkeypatch):
    calls: list[dict] = []

    def fake_post(url, json=None, timeout=None):
        calls.append(json)
        if json.get("logprobs"):
            # Server rejects the logprobs params.
            return _FakeResp({"error": {"message": "logprobs not supported"}}, status_code=400)
        return _FakeResp({
            "choices": [{"message": {"role": "assistant", "content": "2"}, "logprobs": None}]
        })

    monkeypatch.setattr("requests.post", fake_post)
    chunks = [{"chunk_id": "a_chunk_0", "chunk_text": "正文"}]
    out = rerankers.rerank_with_llm("q", chunks, model_endpoint="http://m/v1", model_name="m")
    assert len(calls) == 2
    assert "logprobs" not in calls[1]
    assert out[0]["rerank_bucket"] == 2
    assert out[0]["rerank_score"] == pytest.approx(0.5)


def test_rerank_with_llm_empty_chunk_scores_zero():
    chunks = [{"chunk_id": "empty", "chunk_text": "   "}]
    out = rerankers.rerank_with_llm(
        "q", chunks, model_endpoint="http://m/v1", model_name="m"
    )
    assert out[0]["rerank_score"] == 0.0
    assert out[0]["rerank_bucket"] is None
