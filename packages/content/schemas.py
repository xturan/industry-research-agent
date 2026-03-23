from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 fallback

    class StrEnum(str, Enum):
        pass


class ContentFormat(StrEnum):
    WECHAT_ARTICLE = "wechat_article"
    XIAOHONGSHU_POST = "xiaohongshu_post"
    DOUYIN_SCRIPT = "douyin_script"


class ContentGenerationMode(StrEnum):
    MOCK = "mock"
    LLM = "llm"


class ContentGenerateRequest(BaseModel):
    research_run_id: int | None = None
    research_memo: dict[str, Any] | None = None
    content_types: list[ContentFormat] = Field(
        default_factory=lambda: [
            ContentFormat.WECHAT_ARTICLE,
            ContentFormat.XIAOHONGSHU_POST,
            ContentFormat.DOUYIN_SCRIPT,
        ]
    )
    mode: ContentGenerationMode = ContentGenerationMode.MOCK
    style_hints: list[str] = Field(default_factory=list)
    title_preference: str | None = None

    @model_validator(mode="after")
    def validate_input_mode(self) -> ContentGenerateRequest:
        if self.research_run_id is None and self.research_memo is None:
            raise ValueError("Either research_run_id or research_memo must be provided.")
        if not self.content_types:
            raise ValueError("content_types must include at least one format.")
        return self


class GeneratedContentDraft(BaseModel):
    content_format: ContentFormat
    title: str
    body_text: str
    key_points: list[str]
    disclaimer: str
    platform_meta: dict[str, Any]


class ContentAssetSummary(BaseModel):
    asset_id: int
    content_format: ContentFormat
    content_type: str
    title: str
    status: str
    preview: str


class ContentGenerationResponse(BaseModel):
    generation_run_id: int
    source_research_run_id: int | None
    status: str
    assets: list[ContentAssetSummary]
    notes: list[str]


class ContentAssetView(BaseModel):
    id: int
    theme_id: int | None
    thesis_id: int | None
    content_type: str
    title: str
    status: str
    body_markdown: str | None
    meta_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
