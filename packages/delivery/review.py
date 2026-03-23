from __future__ import annotations

from packages.delivery.enums import DeliveryItemStatus, DeliveryJobStatus, DeliveryReviewStatus


class DeliveryStateError(Exception):
    """Raised when a delivery job state transition is invalid."""


def initial_review_state(*, require_review: bool) -> tuple[DeliveryJobStatus, DeliveryReviewStatus]:
    if require_review:
        return DeliveryJobStatus.PENDING_REVIEW, DeliveryReviewStatus.PENDING
    return DeliveryJobStatus.READY, DeliveryReviewStatus.NOT_REQUIRED


def validate_approve_transition(
    *,
    status: DeliveryJobStatus,
    review_status: DeliveryReviewStatus,
) -> None:
    if review_status != DeliveryReviewStatus.PENDING:
        raise DeliveryStateError("Delivery job is not pending review.")
    if status != DeliveryJobStatus.PENDING_REVIEW:
        raise DeliveryStateError("Delivery job is not in pending_review state.")


def validate_dispatch_transition(
    *,
    status: DeliveryJobStatus,
    review_status: DeliveryReviewStatus,
) -> None:
    if status not in {DeliveryJobStatus.READY, DeliveryJobStatus.PARTIAL_FAILED}:
        raise DeliveryStateError("Delivery job is not dispatchable in current state.")
    if review_status not in {
        DeliveryReviewStatus.NOT_REQUIRED,
        DeliveryReviewStatus.APPROVED,
    }:
        raise DeliveryStateError("Delivery job must be approved before dispatch.")


def derive_job_status_from_items(item_statuses: list[DeliveryItemStatus]) -> DeliveryJobStatus:
    if not item_statuses:
        return DeliveryJobStatus.FAILED
    succeeded = sum(1 for status in item_statuses if status == DeliveryItemStatus.DISPATCHED)
    failed = sum(1 for status in item_statuses if status == DeliveryItemStatus.FAILED)
    if succeeded == len(item_statuses):
        return DeliveryJobStatus.DISPATCHED
    if failed == len(item_statuses):
        return DeliveryJobStatus.FAILED
    return DeliveryJobStatus.PARTIAL_FAILED
