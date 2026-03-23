from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from packages.db.models import ContentAsset, DeliveryJob, DeliveryJobItem
from packages.delivery.enums import (
    DeliveryItemStatus,
    DeliveryJobStatus,
    DeliveryMode,
    DeliveryReviewStatus,
    DeliveryTarget,
)
from packages.delivery.schemas import DeliveryJobItemView, DeliveryJobView


class DeliveryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def load_assets(self, content_asset_ids: list[int]) -> list[ContentAsset]:
        return self.session.scalars(
            select(ContentAsset)
            .where(ContentAsset.id.in_(content_asset_ids))
            .order_by(ContentAsset.id.asc())
        ).all()

    def create_job(
        self,
        *,
        source_run_id: int | None,
        status: DeliveryJobStatus,
        delivery_target: DeliveryTarget,
        review_status: DeliveryReviewStatus,
        mode: DeliveryMode,
        requested_by: str | None,
        metadata_json: dict[str, object] | None,
        content_assets: list[ContentAsset],
    ) -> DeliveryJob:
        job = DeliveryJob(
            source_run_id=source_run_id,
            status=status,
            delivery_target=delivery_target,
            review_status=review_status,
            mode=mode,
            requested_by=requested_by,
            metadata_json=metadata_json,
        )
        self.session.add(job)
        self.session.flush()

        for asset in content_assets:
            item = DeliveryJobItem(
                delivery_job_id=job.id,
                content_asset_id=asset.id,
                status=DeliveryItemStatus.PENDING,
            )
            self.session.add(item)

        self.session.commit()
        self.session.refresh(job)
        return self.get_job(job.id)

    def get_job(self, job_id: int) -> DeliveryJob | None:
        return self.session.scalar(
            select(DeliveryJob)
            .options(
                selectinload(DeliveryJob.items).selectinload(DeliveryJobItem.content_asset),
            )
            .where(DeliveryJob.id == job_id)
        )

    def list_by_asset(self, asset_id: int) -> list[DeliveryJob]:
        return self.session.scalars(
            select(DeliveryJob)
            .join(DeliveryJobItem, DeliveryJobItem.delivery_job_id == DeliveryJob.id)
            .where(DeliveryJobItem.content_asset_id == asset_id)
            .order_by(DeliveryJob.id.desc())
        ).all()

    def list_by_source_run(self, source_run_id: int) -> list[DeliveryJob]:
        return self.session.scalars(
            select(DeliveryJob)
            .where(DeliveryJob.source_run_id == source_run_id)
            .order_by(DeliveryJob.id.desc())
        ).all()


def item_to_view(item: DeliveryJobItem) -> DeliveryJobItemView:
    return DeliveryJobItemView(
        id=item.id,
        content_asset_id=item.content_asset_id,
        status=item.status,
        exported_path=item.exported_path,
        dispatched_ref=item.dispatched_ref,
        metadata_json=item.metadata_json,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def job_to_view(job: DeliveryJob) -> DeliveryJobView:
    return DeliveryJobView(
        id=job.id,
        source_run_id=job.source_run_id,
        status=job.status,
        delivery_target=job.delivery_target,
        review_status=job.review_status,
        mode=job.mode,
        requested_by=job.requested_by,
        metadata_json=job.metadata_json,
        dispatched_at=job.dispatched_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
        items=[item_to_view(item) for item in sorted(job.items, key=lambda row: row.id)],
    )
