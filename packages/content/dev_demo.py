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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic content factory demo.")
    parser.add_argument("--research-run-id", type=int, default=None)
    parser.add_argument(
        "--content-types",
        nargs="+",
        default=[
            ContentFormat.WECHAT_ARTICLE.value,
            ContentFormat.XIAOHONGSHU_POST.value,
            ContentFormat.DOUYIN_SCRIPT.value,
        ],
    )
    parser.add_argument(
        "--mode",
        choices=[item.value for item in ContentGenerationMode],
        default="mock",
    )
    parser.add_argument("--style-hints", nargs="*", default=[])
    parser.add_argument("--title-preference", type=str, default=None)
    parser.add_argument(
        "--bootstrap-sample",
        action="store_true",
        help="Ingest sample and run research first when research-run-id is not provided.",
    )
    parser.add_argument("--query", type=str, default="lithium pricing power outlook")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with SessionLocal() as session:
        research_run_id = args.research_run_id
        if research_run_id is None and args.bootstrap_sample:
            sample_path = Path("data/samples/energy_storage_note.md")
            if sample_path.exists():
                IngestionService(session).ingest_local_file(
                    sample_path, source_type=SourceType.REPORT
                )
            research = ResearchWorkflowService(session).analyze(
                ResearchAnalyzeRequest(query=args.query, mode=ResearchMode.MOCK, top_k=6)
            )
            research_run_id = research.run_id

        if research_run_id is None:
            raise ValueError("Provide --research-run-id or use --bootstrap-sample.")

        request = ContentGenerateRequest(
            research_run_id=research_run_id,
            content_types=[ContentFormat(item) for item in args.content_types],
            mode=ContentGenerationMode(args.mode),
            style_hints=args.style_hints,
            title_preference=args.title_preference,
        )
        result = ContentFactoryService(session).generate(request)
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
