"""OpenRouter Provider — best-effort LLM fallback（免费模型兜底）。

OpenRouter 提供 OpenAI 兼容 API（base_url=https://openrouter.ai/api/v1）。
`openrouter/free` 是动态路由：自动选择当前可用的最佳免费模型（$0/token，
仅限流：~20 req/min + 50 req/day），无需固定模型名。

与 DeepSeekProviderClient 同构（复用 JsonProviderResponse / TextProviderResponse /
ProviderCallMetadata），满足 JsonProviderClient 协议，可被 capability_gateway 的
_LlmClientAdapter 桥接为 fallback adapter。

差异：
- 不做 strict_json response_format（免费模型对 json_object 支持不稳定）；
  generate_json 的 JSON 解析失败抛 ProviderParseError（同 DeepSeek）。
- 不传 enable_thinking（OpenRouter 免费模型无 reasoning_content 语义）。
- 透传 temperature/top_p/presence_penalty/frequency_penalty。
"""

from __future__ import annotations

import json
import time
from typing import Any

from packages.providers.base import (
    JsonProviderResponse,
    ProviderAuthError,
    ProviderCallMetadata,
    ProviderConfigError,
    ProviderError,
    ProviderParseError,
    ProviderRequestError,
    ProviderRetryableError,
    TextProviderResponse,
)

try:
    from openai import (
        APIConnectionError,
        APIError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        OpenAI,
        RateLimitError,
    )
except ImportError:  # pragma: no cover - optional dependency runtime guard
    class _OpenAIStubError(Exception):
        pass

    OpenAI = None
    APIConnectionError = _OpenAIStubError
    APIError = _OpenAIStubError
    APITimeoutError = _OpenAIStubError
    AuthenticationError = _OpenAIStubError
    BadRequestError = _OpenAIStubError
    RateLimitError = _OpenAIStubError


class OpenRouterProviderClient:
    provider_name = "openrouter"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout_seconds: int,
        max_retries: int,
        max_tokens: int | None = None,
        client: Any | None = None,
    ) -> None:
        if OpenAI is None:
            raise ProviderConfigError("openai package is not installed.")
        if not api_key:
            raise ProviderConfigError("OPENROUTER_API_KEY is required for openrouter provider.")
        if not base_url:
            raise ProviderConfigError("OPENROUTER_BASE_URL is required for openrouter provider.")
        if not model:
            raise ProviderConfigError("OPENROUTER_FREE_MODEL is required for openrouter provider.")

        self.default_model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(max_retries, 0)
        self.max_tokens = max_tokens if (max_tokens is not None and max_tokens > 0) else None
        self.client = client or OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        enable_thinking: bool = False,
        temperature: float | None = None,
        top_p: float | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
    ) -> JsonProviderResponse:
        chosen_model = model or self.default_model
        started = time.perf_counter()
        try:
            completion = self._chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=chosen_model,
                temperature=temperature,
                top_p=top_p,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
            )
            content_text, reasoning_content, raw_extra = self._extract_message(completion)
            json_data = self._parse_json(content_text)
            response_ms = round((time.perf_counter() - started) * 1000.0, 3)
            metadata = ProviderCallMetadata(
                provider=self.provider_name,
                model=chosen_model,
                request_id=getattr(completion, "id", None),
                usage=self._extract_usage(completion),
                finish_reason=self._extract_finish_reason(completion),
                response_ms=response_ms,
                extra=raw_extra,
            )
            return JsonProviderResponse(
                provider=self.provider_name,
                model=chosen_model,
                content_text=content_text,
                json_data=json_data,
                metadata=metadata,
                reasoning_content=reasoning_content,
            )
        except AuthenticationError as exc:
            raise ProviderAuthError(self._format_exception(exc)) from exc
        except BadRequestError as exc:
            raise ProviderRequestError(self._format_exception(exc)) from exc
        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            raise ProviderRetryableError(self._format_exception(exc)) from exc
        except ProviderError:
            raise
        except APIError as exc:
            status_code = getattr(exc, "status_code", None)
            if isinstance(status_code, int) and status_code >= 500:
                raise ProviderRetryableError(self._format_exception(exc)) from exc
            raise ProviderRequestError(self._format_exception(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(self._format_exception(exc)) from exc

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        enable_thinking: bool = False,
    ) -> TextProviderResponse:
        chosen_model = model or self.default_model
        started = time.perf_counter()
        try:
            completion = self._chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=chosen_model,
            )
            content_text, reasoning_content, raw_extra = self._extract_message(completion)
            response_ms = round((time.perf_counter() - started) * 1000.0, 3)
            metadata = ProviderCallMetadata(
                provider=self.provider_name,
                model=chosen_model,
                request_id=getattr(completion, "id", None),
                usage=self._extract_usage(completion),
                finish_reason=self._extract_finish_reason(completion),
                response_ms=response_ms,
                extra=raw_extra,
            )
            return TextProviderResponse(
                provider=self.provider_name,
                model=chosen_model,
                content_text=content_text,
                metadata=metadata,
                reasoning_content=reasoning_content,
            )
        except AuthenticationError as exc:
            raise ProviderAuthError(self._format_exception(exc)) from exc
        except BadRequestError as exc:
            raise ProviderRequestError(self._format_exception(exc)) from exc
        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            raise ProviderRetryableError(self._format_exception(exc)) from exc
        except ProviderError:
            raise
        except APIError as exc:
            status_code = getattr(exc, "status_code", None)
            if isinstance(status_code, int) and status_code >= 500:
                raise ProviderRetryableError(self._format_exception(exc)) from exc
            raise ProviderRequestError(self._format_exception(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(self._format_exception(exc)) from exc

    def _chat_completion(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float | None = None,
        top_p: float | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
    ) -> Any:
        last_error: Exception | None = None
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    # OpenRouter free 对 temperature 支持良好；默认保持确定性 0.1。
                    "temperature": temperature if temperature is not None else 0.1,
                }
                if top_p is not None:
                    kwargs["top_p"] = top_p
                if presence_penalty is not None:
                    kwargs["presence_penalty"] = presence_penalty
                if frequency_penalty is not None:
                    kwargs["frequency_penalty"] = frequency_penalty
                if self.max_tokens is not None:
                    kwargs["max_tokens"] = self.max_tokens
                # OpenRouter 官方推荐 header（路由透明度/调试）
                return self.client.chat.completions.create(
                    **kwargs,
                    extra_headers={
                        "HTTP-Referer": "https://github.com/invest-agent",
                        "X-Title": "invest-agent",
                    },
                )
            except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
                last_error = exc
                if attempt >= attempts - 1:
                    break
                time.sleep(min(0.5 * (attempt + 1), 2.0))
        if last_error is not None:
            raise ProviderRetryableError(self._format_exception(last_error)) from last_error
        raise ProviderRetryableError("OpenRouter request failed without explicit error detail.")

    def _extract_message(self, completion: Any) -> tuple[str, str | None, dict[str, Any]]:
        choices = getattr(completion, "choices", None)
        if not choices:
            raise ProviderParseError("Provider returned no choices.")
        first = choices[0]
        message = getattr(first, "message", None)
        if message is None:
            raise ProviderParseError("Provider response missing message object.")

        content = getattr(message, "content", None)
        content_text = self._normalize_content(content)
        if not content_text.strip():
            raise ProviderParseError("Provider response content is empty.")

        reasoning_content = getattr(message, "reasoning_content", None)
        raw_extra = {"reasoning_available": bool(reasoning_content)}
        return content_text, reasoning_content, raw_extra

    def _normalize_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    maybe_text = part.get("text")
                    if isinstance(maybe_text, str):
                        text_parts.append(maybe_text)
                else:
                    text_parts.append(str(part))
            return "".join(text_parts)
        if content is None:
            return ""
        return str(content)

    def _parse_json(self, content_text: str) -> dict[str, Any]:
        """解析严格 JSON。剥离 markdown 围栏（```json ... ```）与前后空白，
        应对部分免费模型把 JSON 包在代码块里的行为。"""
        text = content_text.strip()
        # 剥离 ```json / ``` 围栏
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].strip().lstrip("#").strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderParseError(f"Provider returned invalid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ProviderParseError("Provider JSON root must be an object.")
        return parsed

    def _extract_usage(self, completion: Any) -> dict[str, Any] | None:
        usage = getattr(completion, "usage", None)
        if usage is None:
            return None
        if hasattr(usage, "model_dump"):
            return usage.model_dump(mode="json")
        if isinstance(usage, dict):
            return usage
        return {"raw": str(usage)}

    def _extract_finish_reason(self, completion: Any) -> str | None:
        choices = getattr(completion, "choices", None)
        if not choices:
            return None
        return getattr(choices[0], "finish_reason", None)

    def _format_exception(self, exc: Exception) -> str:
        detail = getattr(exc, "body", None)
        if isinstance(detail, dict):
            message = detail.get("message") or detail.get("error")
            if message:
                return str(message)[:300]
        return str(exc)[:300]


__all__ = ["OpenRouterProviderClient"]
