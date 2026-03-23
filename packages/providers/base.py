from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class ProviderError(Exception):
    """Base class for provider-layer errors."""


class ProviderConfigError(ProviderError):
    """Missing or invalid provider configuration."""


class ProviderAuthError(ProviderError):
    """Authentication/authorization failure."""


class ProviderRetryableError(ProviderError):
    """Transient provider failure that can be retried."""


class ProviderRequestError(ProviderError):
    """Non-retryable request/validation error."""


class ProviderParseError(ProviderError):
    """Provider returned output that failed strict parsing."""


@dataclass(slots=True)
class ProviderCallMetadata:
    provider: str
    model: str
    request_id: str | None = None
    usage: dict[str, Any] | None = None
    finish_reason: str | None = None
    response_ms: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class JsonProviderResponse:
    provider: str
    model: str
    content_text: str
    json_data: dict[str, Any]
    metadata: ProviderCallMetadata
    reasoning_content: str | None = None


@dataclass(slots=True)
class TextProviderResponse:
    provider: str
    model: str
    content_text: str
    metadata: ProviderCallMetadata
    reasoning_content: str | None = None


class JsonProviderClient(Protocol):
    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        enable_thinking: bool = False,
    ) -> JsonProviderResponse:
        """Generate strict JSON output for agent boundary consumption."""

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        enable_thinking: bool = False,
    ) -> TextProviderResponse:
        """Generate plain text output for non-JSON use cases."""
