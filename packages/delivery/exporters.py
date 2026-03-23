from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.db.models import DeliveryJob, DeliveryJobItem


@dataclass(slots=True)
class ExportedItemArtifact:
    delivery_job_item_id: int
    content_asset_id: int | None
    markdown_path: str | None
    text_path: str | None
    metadata_path: str | None


@dataclass(slots=True)
class ExportBundleResult:
    job_dir: str
    manifest_path: str
    artifacts: list[ExportedItemArtifact]


class LocalExportBundleWriter:
    def __init__(self, export_root: str) -> None:
        self.export_root = Path(export_root)

    def export_job(self, job: DeliveryJob) -> ExportBundleResult:
        job_dir = self.export_root / f"delivery_job_{job.id}"
        job_dir.mkdir(parents=True, exist_ok=True)

        artifacts: list[ExportedItemArtifact] = []
        manifest_items: list[dict[str, Any]] = []

        for item in sorted(job.items, key=lambda row: row.id):
            artifact = self._export_item(job_dir=job_dir, item=item)
            artifacts.append(artifact)
            manifest_items.append(
                {
                    "delivery_job_item_id": item.id,
                    "content_asset_id": item.content_asset_id,
                    "markdown_path": artifact.markdown_path,
                    "text_path": artifact.text_path,
                    "metadata_path": artifact.metadata_path,
                }
            )

        manifest_path = job_dir / "manifest.json"
        manifest_payload = {
            "delivery_job_id": job.id,
            "delivery_target": job.delivery_target.value,
            "mode": job.mode.value,
            "review_status": job.review_status.value,
            "status": job.status.value,
            "source_run_id": job.source_run_id,
            "items": manifest_items,
        }
        manifest_path.write_text(
            json.dumps(manifest_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return ExportBundleResult(
            job_dir=str(job_dir.as_posix()),
            manifest_path=str(manifest_path.as_posix()),
            artifacts=artifacts,
        )

    def _export_item(self, *, job_dir: Path, item: DeliveryJobItem) -> ExportedItemArtifact:
        asset = item.content_asset
        if asset is None:
            return ExportedItemArtifact(
                delivery_job_item_id=item.id,
                content_asset_id=item.content_asset_id,
                markdown_path=None,
                text_path=None,
                metadata_path=None,
            )

        stem = f"asset_{asset.id}_item_{item.id}"
        markdown_path = job_dir / f"{stem}.md"
        text_path = job_dir / f"{stem}.txt"
        metadata_path = job_dir / f"{stem}.json"

        body = asset.body_markdown or ""
        markdown_path.write_text(body, encoding="utf-8")
        text_path.write_text(body, encoding="utf-8")

        meta_json = asset.meta_json if isinstance(asset.meta_json, dict) else {}
        metadata_payload = {
            "delivery_job_item_id": item.id,
            "content_asset_id": asset.id,
            "title": asset.title,
            "content_type": asset.content_type.value,
            "source_research_run_id": meta_json.get("source_research_run_id"),
            "generation_run_id": meta_json.get("generation_run_id"),
            "content_format": meta_json.get("content_format"),
            "disclaimers": meta_json.get("disclaimers", []),
            "delivery_target": item.delivery_job.delivery_target.value,
        }
        metadata_path.write_text(
            json.dumps(metadata_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return ExportedItemArtifact(
            delivery_job_item_id=item.id,
            content_asset_id=asset.id,
            markdown_path=str(markdown_path.as_posix()),
            text_path=str(text_path.as_posix()),
            metadata_path=str(metadata_path.as_posix()),
        )
