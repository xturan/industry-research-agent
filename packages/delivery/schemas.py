from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from packages.delivery.enums import (
    DeliveryItemStatus,
    DeliveryJobStatus,
    DeliveryMode,
    DeliveryReviewStatus,
    DeliveryTarget,
)


class DeliveryJobCreateRequest(BaseModel):
    content_asset_ids: list[int] = Field(min_length=1)
    delivery_target: DeliveryTarget
    mode: DeliveryMode = DeliveryMode.MOCK
    require_review: bool = True
    source_run_id: int | None = None
    requested_by: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_asset_ids(self) -> DeliveryJobCreateRequest:
        deduped = sorted(set(self.content_asset_ids))
        if not deduped:
            raise ValueError("content_asset_ids must include at least one asset id.")
        self.content_asset_ids = deduped
        return self


class DeliveryJobCreateResponse(BaseModel):
    delivery_job_id: int
    item_count: int
    status: DeliveryJobStatus
    review_status: DeliveryReviewStatus


class DeliveryApprovalResponse(BaseModel):
    delivery_job_id: int
    status: DeliveryJobStatus
    review_status: DeliveryReviewStatus


class DispatchReceiptItem(BaseModel):
    delivery_job_item_id: int
    content_asset_id: int | None
    status: DeliveryItemStatus
    exported_path: str | None
    dispatched_ref: str | None
    metadata_json: dict[str, Any] | None


class DeliveryDispatchResponse(BaseModel):
    delivery_job_id: int
    status: DeliveryJobStatus
    review_status: DeliveryReviewStatus
    receipts: list[DispatchReceiptItem]


class DeliveryJobItemView(BaseModel):
    id: int
    content_asset_id: int | None
    status: DeliveryItemStatus
    exported_path: str | None
    dispatched_ref: str | None
    metadata_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class DeliveryJobView(BaseModel):
    id: int
    source_run_id: int | None
    status: DeliveryJobStatus
    delivery_target: DeliveryTarget
    review_status: DeliveryReviewStatus
    mode: DeliveryMode
    requested_by: str | None
    metadata_json: dict[str, Any] | None
    dispatched_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[DeliveryJobItemView]
