from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from packages.db.models import ContentAsset, ContentFeedbackEvent
from packages.memory.schemas import FeedbackIngestRequest, MemoryCandidate, MemoryKind

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc


class FeedbackError(Exception):
    """Feedback domain error."""


class ContentFeedbackRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_event(self, payload: FeedbackIngestRequest) -> ContentFeedbackEvent:
        content_asset = self.session.get(ContentAsset, payload.content_asset_id)
        if content_asset is None:
            raise FeedbackError(f"Content asset {payload.content_asset_id} not found.")

        event = ContentFeedbackEvent(
            content_asset_id=payload.content_asset_id,
            channel=payload.channel,
            views=payload.views,
            likes=payload.likes,
            comments=payload.comments,
            shares=payload.shares,
            saves=payload.saves,
            clicks=payload.clicks,
            conversions=payload.conversions,
            captured_at=payload.captured_at or datetime.now(UTC),
            metadata_json=payload.metadata_json,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def list_events_by_channel(
        self, channel: str, *, limit: int = 50
    ) -> list[ContentFeedbackEvent]:
        return self.session.scalars(
            select(ContentFeedbackEvent)
            .options(joinedload(ContentFeedbackEvent.content_asset))
            .where(ContentFeedbackEvent.channel == channel)
            .order_by(ContentFeedbackEvent.captured_at.desc(), ContentFeedbackEvent.id.desc())
            .limit(limit)
        ).all()


def build_strategy_memory_from_feedback(
    *,
    channel: str,
    events: list[ContentFeedbackEvent],
) -> MemoryCandidate | None:
    if not events:
        return None

    totals = {
        "views": 0,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "saves": 0,
        "clicks": 0,
        "conversions": 0,
    }
    format_counter: Counter[str] = Counter()
    best_event = events[0]
    best_rate = _engagement_rate(best_event)

    for event in events:
        totals["views"] += event.views
        totals["likes"] += event.likes
        totals["comments"] += event.comments
        totals["shares"] += event.shares
        totals["saves"] += event.saves
        totals["clicks"] += event.clicks
        totals["conversions"] += event.conversions

        content_format = _content_format_from_event(event)
        if content_format is not None:
            format_counter[content_format] += 1

        event_rate = _engagement_rate(event)
        if event_rate >= best_rate:
            best_rate = event_rate
            best_event = event

    event_count = len(events)
    avg_rate = sum(_engagement_rate(item) for item in events) / event_count if event_count else 0.0
    dominant_format = format_counter.most_common(1)[0][0] if format_counter else "unknown"

    content = (
        f"Channel {channel} feedback summary: events={event_count}, "
        f"avg_engagement_rate={avg_rate:.4f}, dominant_format={dominant_format}, "
        f"best_asset_id={best_event.content_asset_id}, best_engagement_rate={best_rate:.4f}."
    )

    return MemoryCandidate(
        memory_type=MemoryKind.CONTENT_STRATEGY_MEMORY,
        scope_key=f"channel:{channel}",
        content=content,
        score=max(0.0, min(avg_rate, 1.0)),
        metadata_json={
            "memory_key": f"feedback_strategy:{channel}",
            "channel": channel,
            "event_count": event_count,
            "totals": totals,
            "dominant_format": dominant_format,
            "best_asset_id": best_event.content_asset_id,
            "best_engagement_rate": round(best_rate, 4),
            "top_formats": [
                {"content_format": item[0], "count": item[1]}
                for item in format_counter.most_common(3)
            ],
            # TODO: Add trend and seasonality factors when time-windowed growth analytics are added.
        },
    )


def _content_format_from_event(event: ContentFeedbackEvent) -> str | None:
    meta = event.content_asset.meta_json if event.content_asset is not None else None
    if not isinstance(meta, dict):
        return None
    content_format = meta.get("content_format")
    if isinstance(content_format, str):
        return content_format
    return None


def _engagement_rate(event: ContentFeedbackEvent) -> float:
    interactions = (
        event.likes + event.comments + event.shares + event.saves + event.clicks + event.conversions
    )
    denominator = event.views if event.views > 0 else 1
    return interactions / denominator
