from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from packages.db.models import DeliveryJob, DeliveryJobItem
from packages.delivery.enums import DeliveryTarget
from packages.delivery.exporters import ExportBundleResult, ExportedItemArtifact


@dataclass(slots=True)
class DispatchReceipt:
    dispatched_ref: str
    metadata_json: dict[str, object]


class DeliveryConnector(Protocol):
    def dispatch(
        self,
        *,
        job: DeliveryJob,
        item: DeliveryJobItem,
        artifact: ExportedItemArtifact | None,
        export_result: ExportBundleResult,
    ) -> DispatchReceipt:
        """Dispatch a single delivery job item and return an auditable receipt."""


class ExportBundleConnector:
    def dispatch(
        self,
        *,
        job: DeliveryJob,
        item: DeliveryJobItem,
        artifact: ExportedItemArtifact | None,
        export_result: ExportBundleResult,
    ) -> DispatchReceipt:
        return DispatchReceipt(
            dispatched_ref=f"file://{export_result.manifest_path}",
            metadata_json={"connector": "export_bundle", "delivery_job_item_id": item.id},
        )


class ManualReviewConnector:
    def dispatch(
        self,
        *,
        job: DeliveryJob,
        item: DeliveryJobItem,
        artifact: ExportedItemArtifact | None,
        export_result: ExportBundleResult,
    ) -> DispatchReceipt:
        return DispatchReceipt(
            dispatched_ref=f"manual-review://job/{job.id}/item/{item.id}",
            metadata_json={"connector": "manual_review", "note": "Manual handoff required."},
        )


class MockSocialConnector:
    def dispatch(
        self,
        *,
        job: DeliveryJob,
        item: DeliveryJobItem,
        artifact: ExportedItemArtifact | None,
        export_result: ExportBundleResult,
    ) -> DispatchReceipt:
        return DispatchReceipt(
            dispatched_ref=f"mock-social://job/{job.id}/item/{item.id}",
            metadata_json={
                "connector": "mock_social_connector",
                "target": job.delivery_target.value,
                "artifact_path": artifact.markdown_path if artifact else None,
            },
        )


class WebhookConnector:
    def dispatch(
        self,
        *,
        job: DeliveryJob,
        item: DeliveryJobItem,
        artifact: ExportedItemArtifact | None,
        export_result: ExportBundleResult,
    ) -> DispatchReceipt:
        metadata_json = job.metadata_json if isinstance(job.metadata_json, dict) else {}
        webhook_url = metadata_json.get("webhook_url")
        if not isinstance(webhook_url, str) or not webhook_url:
            raise ValueError("webhook_url is required for webhook delivery target.")
        return DispatchReceipt(
            dispatched_ref=f"mock-webhook://{webhook_url}",
            metadata_json={
                "connector": "webhook",
                "webhook_url": webhook_url,
                "simulated": True,
                "delivery_job_item_id": item.id,
            },
        )


def build_connector(delivery_target: DeliveryTarget) -> DeliveryConnector:
    if delivery_target == DeliveryTarget.EXPORT_BUNDLE:
        return ExportBundleConnector()
    if delivery_target == DeliveryTarget.MANUAL_REVIEW:
        return ManualReviewConnector()
    if delivery_target == DeliveryTarget.WEBHOOK:
        return WebhookConnector()
    return MockSocialConnector()
