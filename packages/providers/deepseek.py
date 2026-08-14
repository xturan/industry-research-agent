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


class DeepSeekProviderClient:
    provider_name = "deepseek"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout_seconds: int,
        max_retries: int,
        max_tokens: int | None = None,
        store_reasoning_content: bool = False,
        client: Any | None = None,
    ) -> None:
        if OpenAI is None:
            raise ProviderConfigError("openai package is not installed.")
        if not api_key:
            raise ProviderConfigError("DEEPSEEK_API_KEY is required for deepseek provider.")
        if not base_url:
            raise ProviderConfigError("DEEPSEEK_BASE_URL is required for deepseek provider.")
        if not model:
            raise ProviderConfigError("DEEPSEEK_RESEARCH_MODEL is required for deepseek provider.")

        self.default_model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(max_retries, 0)
        self.max_tokens = max_tokens if (max_tokens is not None and max_tokens > 0) else None
        self.store_reasoning_content = store_reasoning_content
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
        gen_kwargs = {
            "temperature": temperature,
            "top_p": top_p,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
        }

        try:
            completion = self._chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=chosen_model,
                enable_thinking=enable_thinking,
                strict_json=True,
                **gen_kwargs,
            )
            content_text, reasoning_content, raw_extra = self._extract_message(completion)
            try:
                json_data = self._parse_json(content_text)
            except ProviderParseError:
                repaired_completion = self._chat_completion(
                    system_prompt=system_prompt,
                    user_prompt=(
                        f"{user_prompt}\n\n"
                        "Your previous response was invalid JSON. "
                        "Return ONLY one strict JSON object."
                    ),
                    model=chosen_model,
                    enable_thinking=enable_thinking,
                    strict_json=True,
                    **gen_kwargs,
                )
                content_text, reasoning_content, raw_extra = self._extract_message(
                    repaired_completion
                )
                json_data = self._parse_json(content_text)
                completion = repaired_completion

            response_ms = round((time.perf_counter() - started) * 1000.0, 3)
            usage = self._extract_usage(completion)
            finish_reason = self._extract_finish_reason(completion)
            metadata = ProviderCallMetadata(
                provider=self.provider_name,
                model=chosen_model,
                request_id=getattr(completion, "id", None),
                usage=usage,
                finish_reason=finish_reason,
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
                enable_thinking=enable_thinking,
                strict_json=False,
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
        enable_thinking: bool,
        strict_json: bool,
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
                    # Default remains deterministic (0.1); pass-through when set.
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
                if strict_json:
                    kwargs["response_format"] = {"type": "json_object"}
                if enable_thinking:
                    kwargs["extra_body"] = {"enable_thinking": True}
                return self.client.chat.completions.create(**kwargs)
            except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
                last_error = exc
                if attempt >= attempts - 1:
                    break
                time.sleep(min(0.5 * (attempt + 1), 2.0))
        if last_error is not None:
            raise ProviderRetryableError(self._format_exception(last_error)) from last_error
        raise ProviderRetryableError("DeepSeek request failed without explicit error detail.")

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
        if reasoning_content and self.store_reasoning_content:
            raw_extra["reasoning_content"] = reasoning_content
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
        try:
            parsed = json.loads(content_text)
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
        parts = [f"{type(exc).__name__}: {exc}"]
        current = exc.__cause__ or exc.__context__
        depth = 0
        while current is not None and depth < 2:
            parts.append(f"caused_by={type(current).__name__}: {current}")
            current = current.__cause__ or current.__context__
            depth += 1
        return " | ".join(parts)
