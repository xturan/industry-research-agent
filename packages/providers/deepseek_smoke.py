from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from packages.agents.schemas import ResearchAnalyzeRequest, ResearchMode, ResearchProvider
from packages.agents.service import ResearchWorkflowService
from packages.db.models import SourceType
from packages.db.session import SessionLocal
from packages.ingestion.service import IngestionService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual smoke test for DeepSeek-backed research analyze flow."
    )
    parser.add_argument("--query", default="lithium pricing power outlook")
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--industry", type=str, default=None)
    parser.add_argument("--enable-thinking", action="store_true")
    parser.add_argument("--debug-reasoning", action="store_true")
    parser.add_argument(
        "--ingest-sample",
        action="store_true",
        help="Ingest bundled markdown sample before running research.",
    )
    return parser.parse_args()


def main() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise SystemExit("DEEPSEEK_API_KEY is required for this smoke script.")

    args = parse_args()
    with SessionLocal() as session:
        if args.ingest_sample:
            sample_path = Path("data/samples/energy_storage_note.md")
            if sample_path.exists():
                IngestionService(session).ingest_local_file(
                    sample_path,
                    source_type=SourceType.REPORT,
                )

        request = ResearchAnalyzeRequest(
            query=args.query,
            mode=ResearchMode.LLM,
            provider=ResearchProvider.DEEPSEEK,
            top_k=args.top_k,
            industry=args.industry,
            enable_thinking=args.enable_thinking,
            debug_reasoning=args.debug_reasoning,
        )
        result = ResearchWorkflowService(session).analyze(request)
        compact = {
            "run_id": result.run_id,
            "status": result.status,
            "mode": result.mode.value,
            "provider": result.provider.value,
            "model": result.model,
            "thinking_enabled": result.thinking_enabled,
            "insufficient_evidence": result.insufficient_evidence,
            "thesis_count": len(result.theses),
            "risk_count": len(result.risks),
            "confidence_score": result.confidence_score,
            "workflow_notes": result.workflow_notes,
            "error_message": result.error_message,
            "provider_steps": (
                sorted((result.provider_metadata or {}).get("steps", {}).keys())
                if result.provider_metadata
                else []
            ),
        }
        print(json.dumps(compact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
