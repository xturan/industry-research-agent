from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.db.models import SourceType
from packages.db.session import SessionLocal
from packages.ingestion.service import IngestionService
from packages.rag.bundle import EvidenceBundleBuilder
from packages.rag.retrieval import ChunkRetrievalService
from packages.rag.schemas import RetrievalFilters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG v1 retrieval demo")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--mode", choices=["chunks", "bundle"], default="chunks")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--industry", type=str, default=None)
    parser.add_argument(
        "--ingest-sample",
        action="store_true",
        help="Ingest bundled sample markdown before retrieval.",
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

        filters = RetrievalFilters(limit=args.limit, industry=args.industry)
        retrieval = ChunkRetrievalService(session).search_chunks(args.query, filters)
        if args.mode == "chunks":
            payload = retrieval.to_dict()
        else:
            payload = (
                EvidenceBundleBuilder().build_bundle(retrieval, group_by_document=True).to_dict()
            )

        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
