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
from packages.ingestion.service import IngestionService
from packages.memory.schemas import FeedbackIngestRequest, MemorySearchRequest
from packages.memory.service import MemoryService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Memory and growth-feedback demo.")
    parser.add_argument("--research-run-id", type=int, default=None)
    parser.add_argument("--content-run-id", type=int, default=None)
    parser.add_argument("--content-asset-id", type=int, default=None)
    parser.add_argument("--channel", type=str, default="xiaohongshu")
    parser.add_argument("--query", type=str, default="lithium pricing")
    parser.add_argument("--bootstrap-sample", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with SessionLocal() as session:
        research_run_id = args.research_run_id
        content_run_id = args.content_run_id
        content_asset_id = args.content_asset_id

        if args.bootstrap_sample:
            sample_path = Path("data/samples/energy_storage_note.md")
            if sample_path.exists():
                IngestionService(session).ingest_local_file(
                    sample_path, source_type=SourceType.REPORT
                )

            research = ResearchWorkflowService(session).analyze(
                ResearchAnalyzeRequest(
                    query=args.query,
                    mode=ResearchMode.MOCK,
                    top_k=6,
                )
            )
            research_run_id = research.run_id

            content_response = ContentFactoryService(session).generate(
                ContentGenerateRequest(
                    research_run_id=research_run_id,
                    content_types=[
                        ContentFormat.WECHAT_ARTICLE,
                        ContentFormat.XIAOHONGSHU_POST,
                        ContentFormat.DOUYIN_SCRIPT,
                    ],
                    mode=ContentGenerationMode.MOCK,
                )
            )
            content_run_id = content_response.generation_run_id
            content_asset_id = content_response.assets[0].asset_id

        if research_run_id is None or content_run_id is None or content_asset_id is None:
            raise ValueError(
                "Provide run/asset ids or use --bootstrap-sample for an end-to-end demo flow."
            )

        memory_service = MemoryService(session)
        research_extract = memory_service.extract_from_run(research_run_id)
        content_extract = memory_service.extract_from_run(content_run_id)
        feedback = memory_service.ingest_content_feedback(
            FeedbackIngestRequest(
                content_asset_id=content_asset_id,
                channel=args.channel,
                views=1200,
                likes=140,
                comments=23,
                shares=18,
                saves=41,
                clicks=55,
                conversions=5,
            )
        )
        search = memory_service.search(
            MemorySearchRequest(query=args.query, limit=8, recent_first=True)
        )

        print(
            json.dumps(
                {
                    "research_extract": research_extract.model_dump(mode="json"),
                    "content_extract": content_extract.model_dump(mode="json"),
                    "feedback": feedback.model_dump(mode="json"),
                    "search": search.model_dump(mode="json"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
