from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.sources.enums import ChinaLocatorType

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc  # noqa: UP017


class ChinaCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, max_length=80)
    source_name: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=500)
    url: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    locator_type: ChinaLocatorType = ChinaLocatorType.URL
    locator_value: str | None = None
    attachment_ref: str | None = None
    external_id: str | None = None
    quote_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_locator(self) -> ChinaCitation:
        if not self.locator_value:
            self.locator_value = self.external_id or self.attachment_ref or self.url or "unknown"
        return self


def normalize_china_citation(
    *,
    source_id: str,
    source_name: str,
    title: str,
    url: str | None,
    published_at: datetime | None = None,
    retrieved_at: datetime | None = None,
    locator_type: ChinaLocatorType = ChinaLocatorType.URL,
    locator_value: str | None = None,
    attachment_ref: str | None = None,
    external_id: str | None = None,
    quote_text: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ChinaCitation:
    citation = ChinaCitation(
        source_id=source_id,
        source_name=source_name,
        title=title,
        url=url,
        published_at=published_at,
        retrieved_at=retrieved_at or datetime.now(UTC),
        locator_type=locator_type,
        locator_value=locator_value,
        attachment_ref=attachment_ref,
        external_id=external_id,
        quote_text=quote_text,
        metadata=metadata or {},
    )
    citation.metadata = {
        **citation.metadata,
        "citation_normalized": True,
        "source_id": citation.source_id,
        "source_name": citation.source_name,
        "locator_type": citation.locator_type.value,
        "locator_value": citation.locator_value,
        "attachment_ref": citation.attachment_ref,
        "external_id": citation.external_id,
    }
    return citation

