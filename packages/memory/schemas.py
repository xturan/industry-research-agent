from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from packages.db.models.enums import MemoryType as DbMemoryType

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 fallback

    class StrEnum(str, Enum):
        pass


class MemoryKind(StrEnum):
    THEME_MEMORY = "theme_memory"
    CONTENT_STRATEGY_MEMORY = "content_strategy_memory"
    ACCOUNT_PREFERENCE_MEMORY = "account_preference_memory"
    RUN_MEMORY = "run_memory"


_MEMORY_KIND_TO_DB: dict[MemoryKind, DbMemoryType] = {
    MemoryKind.THEME_MEMORY: DbMemoryType.THEME,
    MemoryKind.CONTENT_STRATEGY_MEMORY: DbMemoryType.CONTENT_STRATEGY,
    MemoryKind.ACCOUNT_PREFERENCE_MEMORY: DbMemoryType.USER_PREFERENCE,
    MemoryKind.RUN_MEMORY: DbMemoryType.RUN_TRACE,
}
_DB_TO_MEMORY_KIND: dict[DbMemoryType, MemoryKind] = {
    value: key for key, value in _MEMORY_KIND_TO_DB.items()
}


def to_db_memory_type(memory_kind: MemoryKind) -> DbMemoryType:
    return _MEMORY_KIND_TO_DB[memory_kind]


def to_memory_kind(memory_type: DbMemoryType) -> MemoryKind:
    return _DB_TO_MEMORY_KIND[memory_type]


class MemoryCandidate(BaseModel):
    memory_type: MemoryKind
    scope_key: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class MemoryRecordView(BaseModel):
    id: int
    memory_type: MemoryKind
    scope_key: str
    content: str
    score: float | None
    metadata_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime | None


class MemorySearchRequest(BaseModel):
    query: str | None = None
    memory_types: list[MemoryKind] = Field(default_factory=list)
    scope_key: str | None = None
    limit: int = Field(default=10, ge=1, le=100)
    min_score: float | None = Field(default=None, ge=0.0, le=1.0)
    recent_first: bool = False


class MemorySearchResponse(BaseModel):
    total: int
    items: list[MemoryRecordView]


class MemoryExtractRunResponse(BaseModel):
    source_run_id: int
    memory_refresh_run_id: int
    created_or_updated: int
    memory_ids: list[int]
    memory_types: list[MemoryKind]
    status: str


class ScopeMemoriesResponse(BaseModel):
    scope_key: str
    items: list[MemoryRecordView]


class FeedbackIngestRequest(BaseModel):
    content_asset_id: int
    channel: str = Field(min_length=1, max_length=64)
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    saves: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    conversions: int = Field(default=0, ge=0)
    captured_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None


class FeedbackIngestResponse(BaseModel):
    event_id: int
    content_asset_id: int
    channel: str
    captured_at: datetime
    memory_refresh_run_id: int
    strategy_memory_ids: list[int]
    status: str


class AccountPreferenceUpsertRequest(BaseModel):
    scope_key: str = Field(default="account:default", min_length=1, max_length=255)
    content: str = Field(min_length=1)
    score: float | None = Field(default=0.6, ge=0.0, le=1.0)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AccountPreferenceUpsertResponse(BaseModel):
    memory_id: int
