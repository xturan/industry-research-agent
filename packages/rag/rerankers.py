from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalRerankSpec:
    rerank_mode: str
    strategy_name: str
    notes: tuple[str, ...]
    multi_lane_bonus_step: float = 0.0
    multi_lane_bonus_cap: float = 0.0

    def bonus_for_lane_count(self, lane_count: int) -> float:
        if self.multi_lane_bonus_step <= 0.0 or lane_count <= 1:
            return 0.0
        return min(self.multi_lane_bonus_step * float(lane_count - 1), self.multi_lane_bonus_cap)


_RERANK_SPECS: dict[str, RetrievalRerankSpec] = {
    "deterministic_v2": RetrievalRerankSpec(
        rerank_mode="deterministic_v2",
        strategy_name="deterministic_chunk_rerank_v2",
        notes=("Applied deterministic chunk rerank with metadata-aware bonuses.",),
    ),
    "lane_balance_v1": RetrievalRerankSpec(
        rerank_mode="lane_balance_v1",
        strategy_name="lane_balance_rerank_v1",
        notes=(
            "Applied lane-balance rerank to reward chunks supported by multiple retrieval lanes.",
        ),
        multi_lane_bonus_step=0.03,
        multi_lane_bonus_cap=0.09,
    ),
}


def resolve_rerank_spec(rerank_mode: str | None) -> RetrievalRerankSpec:
    normalized = str(rerank_mode or "deterministic_v2").strip() or "deterministic_v2"
    return _RERANK_SPECS.get(normalized, _RERANK_SPECS["deterministic_v2"])


# ── Phase A2: Local LLM reranker (LLM-as-reranker via chat completions) ──
# NOTE: this is an LLM reranker, NOT a true cross-encoder (e.g. bge-reranker).
# It asks a chat-completions LLM to score document-query relevance 0..1.
# Recommended LoRA adapter (handoff v6): Qwen2.5-3B-Instruct base +
# data/rerank_cloud_train/output/rerank_3b_lora_v6_opd_clean/checkpoint-120.
# Deploy via: python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-3B-Instruct
#   --enable-lora --max-lora-rank 16 --lora-modules rerank-lora=<checkpoint-120 path> --port 8000
# Fallback: deterministic lane-balance reranking when model unavailable.

import math as _math
import re as _re
from typing import Any as _Any

# Prompt/format shared with the reranker LoRA training data
# (data/rerank_cloud_train/RERANK_TRAINING_HANDOFF.md). The prompt template MUST
# match the v6 clean-OPD training format exactly (### Instruction / Input /
# Response), otherwise the LoRA's learned distribution is not exercised.
_RERANKER_INSTRUCTION = (
    "你是一个产业研究检索精排器。判断下面文档对查询的相关性，"
    "输出 0-4 五档分数：0=无关，1=弱相关，2=一般相关，"
    "3=相关且有实质信息，4=核心证据。只输出一个数字。"
)
_RERANK_PROMPT_TEMPLATE = (
    "### Instruction:\n"
    + _RERANKER_INSTRUCTION
    + "\n\n"
    + "### Input:\n"
    + "查询：{query}\n\n"
    + "文档：{text}\n\n"
    + "### Response:\n"
)
_RERANK_DIGITS = ("0", "1", "2", "3", "4")
_RERANK_BUCKET_RE = _re.compile(r"\b([0-4])\b")


def _parse_rerank_response(resp: _Any) -> tuple[int | None, float]:
    """Extract (bucket, expected_score) from an OpenAI chat-completions response.

    Preferred path (handoff v6): token logprobs over the 0-4 digit vocabulary;
    expected_score = sum(prob[i] * i for i in 0..4). Falls back to regex over the
    generated text. Returns (None, 0.0) when no usable 0-4 signal exists.
    """
    try:
        data = resp.json()
    except Exception:
        return None, 0.0
    choices = data.get("choices") or []
    if not choices:
        return None, 0.0
    choice = choices[0]
    probs: dict[str, float] = {}
    content_lp = (choice.get("logprobs") or {}).get("content") or []
    for token_entry in content_lp:
        for top in (token_entry or {}).get("top_logprobs") or []:
            token = str(top.get("token") or "").strip()
            logprob = top.get("logprob")
            if token in _RERANK_DIGITS and logprob is not None:
                try:
                    probs[token] = max(probs.get(token, 0.0), _math.exp(float(logprob)))
                except (OverflowError, ValueError):
                    continue
    if probs:
        total = sum(probs.values())
        if total > 0.0:
            norm = {k: v / total for k, v in probs.items()}
            bucket = max(norm, key=norm.get)
            expected = sum(int(k) * p for k, p in norm.items())
            return int(bucket), expected
    # Fallback: parse the generated text for a 0-4 digit.
    raw = str(choice.get("message", {}).get("content") or "").strip()
    match = _RERANK_BUCKET_RE.search(raw)
    if match:
        b = int(match.group(1))
        return b, float(b)
    return None, 0.0


def rerank_with_llm(
    query: str,
    chunks: list[dict[str, _Any]],
    *,
    model_endpoint: str | None = None,
    model_name: str | None = None,
    top_k: int = 8,
    timeout: float = 30.0,
) -> list[dict[str, _Any]]:
    """Call the local LLM reranker (vLLM chat-completions) to score chunks.

    Endpoint/model resolve from settings (RERANK_ENDPOINT / RERANK_MODEL) when not
    passed. Uses the trained 0-4 bucketed reranker protocol (handoff v6): request
    token logprobs, compute expected_score = sum(prob[i] * i), and map to a 0..1
    relevance score (expected_score / 4). Returns a list of
    {"chunk_id", "rerank_score", "rerank_bucket"} sorted desc by rerank_score.
    Falls back to uniform neutral scores (0.5) if the model is unavailable.
    """
    import requests as _requests

    if model_endpoint is None or model_name is None:
        from packages.core.config import get_settings

        _settings = get_settings()
        model_endpoint = model_endpoint or _settings.rerank_endpoint
        model_name = model_name or _settings.rerank_model

    scores: list[dict[str, _Any]] = []
    for chunk in chunks[: max(top_k * 3, 15)]:
        text = str(chunk.get("chunk_text") or chunk.get("text") or "")[:4000]
        chunk_id = str(chunk.get("chunk_id") or chunk.get("id") or "")
        if not text.strip():
            scores.append({"chunk_id": chunk_id, "rerank_score": 0.0, "rerank_bucket": None})
            continue
        bucket: int | None = None
        score = 0.5
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": _RERANK_PROMPT_TEMPLATE.format(query=query, text=text),
                }
            ],
            "max_tokens": 1,
            "temperature": 0.0,
            "logprobs": True,
            "top_logprobs": 8,
        }
        try:
            resp = _requests.post(model_endpoint, json=payload, timeout=timeout)
            bucket, expected = _parse_rerank_response(resp)
            if bucket is None and resp.status_code >= 400:
                # Some OpenAI-compatible servers reject logprobs/top_logprobs.
                payload.pop("logprobs", None)
                payload.pop("top_logprobs", None)
                resp = _requests.post(model_endpoint, json=payload, timeout=timeout)
                bucket, expected = _parse_rerank_response(resp)
            if bucket is not None:
                score = min(1.0, max(0.0, expected / 4.0))
        except Exception:
            score = 0.5  # fallback: neutral score
        scores.append({
            "chunk_id": chunk_id,
            "rerank_score": round(score, 4),
            "rerank_bucket": bucket,
        })

    scores.sort(key=lambda x: -x["rerank_score"])
    return scores[:top_k]


# Backward-compatible alias (legacy name "cross_encoder" is inaccurate — this is
# an LLM reranker, not a cross-encoder).
def reranker_health_check(
    *,
    model_endpoint: str | None = None,
    timeout: float = 1.5,
) -> bool:
    """快速检测 LLM reranker 是否可达（vLLM 健康检查）。

    2026-08-11：parse_sources 卡死的根因是 vLLM 不可达时逐 chunk 30s 超时。
    在 rerank 前做一次快速健康检查（短超时探测），不可达立即回退 deterministic。
    """
    import requests as _requests

    if model_endpoint is None:
        from packages.core.config import get_settings

        _settings = get_settings()
        model_endpoint = model_endpoint or _settings.rerank_endpoint
    if not model_endpoint:
        return False
    base = str(model_endpoint)
    # /v1/chat/completions -> /v1/models 探测；非标准路径直接 HEAD 原地址。
    models_url = base
    if "/chat/completions" in base:
        models_url = base.split("/chat/completions")[0] + "/models"
    try:
        resp = _requests.get(models_url, timeout=timeout)
        return resp.status_code < 500
    except Exception:
        return False


rerank_with_cross_encoder = rerank_with_llm
