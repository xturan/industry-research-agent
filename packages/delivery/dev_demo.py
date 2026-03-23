from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.agents.schemas import ResearchAnalyzeRequest, ResearchMode
from packages.agents.service import ResearchWorkflowService
from packages.content.schemas import ContentFormat, ContentGenerateRequest, ContentGenerationMode
from packages.content.service import ContentFactoryService
from packages.db.models import SourceType
from packages.db.session import SessionLocal
from packages.delivery.enums import DeliveryMode, DeliveryTarget
from packages.delivery.schemas import DeliveryJobCreateRequest
from packages.delivery.service import DeliveryService
from packages.ingestion.service import IngestionService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delivery workflow demo.")
    parser.add_argument("--asset-ids", nargs="*", type=int, default=[])
    parser.add_argument("--source-run-id", type=int, default=None)
    parser.add_argument(
        "--delivery-target",
        choices=[item.value for item in DeliveryTarget],
        default="export_bundle",
    )
    parser.add_argument("--mode", choices=[item.value for item in DeliveryMode], default="mock")
    parser.add_argument("--require-review", action="store_true")
    parser.add_argument("--auto-approve", action="store_true")
    parser.add_argument("--auto-dispatch", action="store_true")
    parser.add_argument("--bootstrap-sample", action="store_true")
    parser.add_argument("--query", type=str, default="lithium pricing power outlook")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with SessionLocal() as session:
        asset_ids = list(args.asset_ids)
        source_run_id = args.source_run_id

        if args.bootstrap_sample and not asset_ids:
            sample_path = Path("data/samples/energy_storage_note.md")
            if sample_path.exists():
                IngestionService(session).ingest_local_file(
                    sample_path, source_type=SourceType.REPORT
                )

            research = ResearchWorkflowService(session).analyze(
                ResearchAnalyzeRequest(query=args.query, mode=ResearchMode.MOCK, top_k=6)
            )
            source_run_id = research.run_id
            content = ContentFactoryService(session).generate(
                ContentGenerateRequest(
                    research_run_id=research.run_id,
                    content_types=[
                        ContentFormat.WECHAT_ARTICLE,
                        ContentFormat.XIAOHONGSHU_POST,
                        ContentFormat.DOUYIN_SCRIPT,
                    ],
                    mode=ContentGenerationMode.MOCK,
                )
            )
            asset_ids = [item.asset_id for item in content.assets[:2]]

        if not asset_ids:
            raise ValueError("Provide --asset-ids or use --bootstrap-sample.")

        service = DeliveryService(session)
        create_response = service.create_job(
            DeliveryJobCreateRequest(
                content_asset_ids=asset_ids,
                delivery_target=DeliveryTarget(args.delivery_target),
                mode=DeliveryMode(args.mode),
                require_review=args.require_review,
                source_run_id=source_run_id,
                metadata_json={},
            )
        )

        output: dict[str, object] = {"create": create_response.model_dump(mode="json")}
        job_id = create_response.delivery_job_id

        if args.auto_approve:
            output["approve"] = service.approve_job(job_id).model_dump(mode="json")
        if args.auto_dispatch:
            output["dispatch"] = service.dispatch_job(job_id).model_dump(mode="json")
        output["job"] = service.get_job(job_id).model_dump(mode="json")

        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
