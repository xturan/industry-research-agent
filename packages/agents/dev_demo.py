from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.agents.schemas import ResearchAnalyzeRequest, ResearchMode, ResearchProvider
from packages.agents.service import ResearchWorkflowService
from packages.db.models import SourceType
from packages.db.session import SessionLocal
from packages.ingestion.service import IngestionService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deterministic multi-agent research workflow demo."
    )
    parser.add_argument("--query", required=True, help="Research query.")
    parser.add_argument("--mode", choices=[mode.value for mode in ResearchMode], default="mock")
    parser.add_argument(
        "--provider",
        choices=[provider.value for provider in ResearchProvider],
        default=None,
        help="Provider selection for llm mode.",
    )
    parser.add_argument("--model", default=None, help="Optional model override for llm mode.")
    parser.add_argument("--enable-thinking", action="store_true")
    parser.add_argument("--debug-reasoning", action="store_true")
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--industry", type=str, default=None)
    parser.add_argument(
        "--ingest-sample",
        action="store_true",
        help="Ingest bundled markdown sample before running research.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with SessionLocal() as session:
        if args.ingest_sample:
            sample_path = Path("data/samples/energy_storage_note.md")
            if sample_path.exists():
                IngestionService(session).ingest_local_file(
                    sample_path, source_type=SourceType.REPORT
                )

        request = ResearchAnalyzeRequest(
            query=args.query,
            mode=ResearchMode(args.mode),
            provider=ResearchProvider(args.provider) if args.provider else None,
            model=args.model,
            enable_thinking=args.enable_thinking,
            debug_reasoning=args.debug_reasoning,
            top_k=args.top_k,
            industry=args.industry,
        )
        result = ResearchWorkflowService(session).analyze(request)
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
