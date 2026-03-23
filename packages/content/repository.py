from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.content.schemas import ContentAssetView, ContentFormat, GeneratedContentDraft
from packages.db.models import ContentAsset, ContentStatus, ContentType


class ContentAssetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_asset(
        self,
        *,
        draft: GeneratedContentDraft,
        mapped_content_type: ContentType,
        theme_id: int | None,
        source_research_run_id: int | None,
        generation_run_id: int,
        generation_mode: str,
        policy_report: dict[str, Any] | None = None,
    ) -> ContentAsset:
        meta_json = {
            "content_format": draft.content_format.value,
            "source_research_run_id": source_research_run_id,
            "generation_run_id": generation_run_id,
            "generation_mode": generation_mode,
            "key_points": draft.key_points,
            "disclaimers": [draft.disclaimer],
            "platform_meta": draft.platform_meta,
            "thesis_id_note": (
                "TODO: map generated assets to persisted theses when thesis persistence is added."
            ),
            "policy_report": policy_report,
        }
        row = ContentAsset(
            theme_id=theme_id,
            thesis_id=None,
            content_type=mapped_content_type,
            title=draft.title[:255],
            status=ContentStatus.DRAFT,
            body_markdown=draft.body_text,
            meta_json=meta_json,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def get_asset(self, asset_id: int) -> ContentAsset | None:
        return self.session.get(ContentAsset, asset_id)

    def list_by_research_run_id(self, research_run_id: int) -> list[ContentAsset]:
        assets = self.session.scalars(
            select(ContentAsset).order_by(ContentAsset.id.asc())
        ).all()
        filtered: list[ContentAsset] = []
        for asset in assets:
            meta = asset.meta_json or {}
            if not isinstance(meta, dict):
                continue
            if meta.get("source_research_run_id") == research_run_id:
                filtered.append(asset)
        return filtered


def map_format_to_content_type(content_format: ContentFormat) -> ContentType:
    if content_format == ContentFormat.WECHAT_ARTICLE:
        return ContentType.ARTICLE
    if content_format == ContentFormat.XIAOHONGSHU_POST:
        return ContentType.THREAD
    return ContentType.VIDEO_SCRIPT


def asset_to_view(asset: ContentAsset) -> ContentAssetView:
    return ContentAssetView(
        id=asset.id,
        theme_id=asset.theme_id,
        thesis_id=asset.thesis_id,
        content_type=asset.content_type.value,
        title=asset.title,
        status=asset.status.value,
        body_markdown=asset.body_markdown,
        meta_json=asset.meta_json,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )
