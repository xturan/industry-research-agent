from __future__ import annotations

import argparse

from packages.db.models import SourceType
from packages.db.session import SessionLocal
from packages.ingestion.service import IngestionService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local ingestion demo pipeline.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=str, help="Path to local file (.txt/.md/.html).")
    group.add_argument("--url", type=str, help="URL to ingest.")
    parser.add_argument(
        "--source-type",
        type=str,
        default=SourceType.OTHER.value,
        choices=[item.value for item in SourceType],
        help="Document source type enum value.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_type = SourceType(args.source_type)
    with SessionLocal() as session:
        service = IngestionService(session)
        if args.file:
            result = service.ingest_local_file(args.file, source_type=source_type)
        else:
            result = service.ingest_url(args.url, source_type=source_type)
        print(
            "Ingestion finished:",
            f"document_id={result.document_id}",
            f"run_id={result.run_id}",
            f"chunks={result.chunks_count}",
            f"citations={result.citations_count}",
            f"status={result.status}",
        )


if __name__ == "__main__":
    main()
