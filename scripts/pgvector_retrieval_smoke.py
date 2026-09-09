from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.db.models import DocumentChunk
from packages.db.session import get_engine, reset_db_session_state
from packages.ingestion.service import IngestionService
from packages.rag.retrieval import ChunkRetrievalService
from packages.rag.schemas import RetrievalFilters

DEFAULT_DATABASE_URL = "postgresql+psycopg://invest:invest@localhost:5432/invest_agent"
DEFAULT_COMPOSE_FILE = Path("infra/docker-compose.yml")
DEFAULT_QUERY = "lithium refining battery supply"


def main() -> None:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    database_url = args.database_url or os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL
    compose_file = Path(args.compose_file)
    if not compose_file.is_absolute():
        compose_file = (repo_root / compose_file).resolve()

    _ensure_docker_postgres(compose_file=compose_file, service_name=args.service_name)
    _run_alembic_upgrade(repo_root=repo_root, database_url=database_url)

    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    reset_db_session_state()

    engine = get_engine(database_url)
    ingestion_result = _ingest_smoke_documents(engine)
    retrieval_response = _run_retrieval(engine, query=args.query)
    extension_installed, hnsw_indexes, vector_rows = _collect_db_diagnostics(engine)

    summary = {
        "database_url": database_url,
        "compose_file": str(compose_file),
        "service_name": args.service_name,
        "query": args.query,
        "ingestion": ingestion_result,
        "retrieval_mode": retrieval_response.retrieval_mode,
        "retrieved_count": len(retrieval_response.items),
        "top_chunk_preview": (
            retrieval_response.items[0].chunk_text[:180] if retrieval_response.items else ""
        ),
        "lane_audit": retrieval_response.audit.get("candidate_collection", []),
        "rerank_strategy": retrieval_response.audit.get("rerank_strategy"),
        "rerank_mode": retrieval_response.audit.get("rerank_mode"),
        "lane_weights": retrieval_response.audit.get("lane_weights", {}),
        "vector_extension_installed": extension_installed,
        "hnsw_indexes": hnsw_indexes,
        "vector_row_count": vector_rows,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reusable live smoke for PostgreSQL pgvector + HNSW retrieval path."
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--compose-file", default=str(DEFAULT_COMPOSE_FILE))
    parser.add_argument("--service-name", default="postgres")
    parser.add_argument("--query", default=DEFAULT_QUERY)
    return parser.parse_args()


def _ensure_docker_postgres(*, compose_file: Path, service_name: str) -> None:
    _run_command(["docker", "compose", "-f", str(compose_file), "up", "-d", service_name])
    for _ in range(30):
        result = _run_command(
            ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json", service_name],
            check=False,
        )
        stdout = result.stdout.strip()
        if not stdout:
            time.sleep(2)
            continue
        try:
            rows = [json.loads(line) for line in stdout.splitlines() if line.strip()]
        except json.JSONDecodeError:
            rows = []
        if rows and any("healthy" in str(row.get("Health", "")).lower() for row in rows):
            return
        time.sleep(2)
    raise RuntimeError(
        "Docker PostgreSQL service did not become healthy within the timeout window."
    )


def _run_alembic_upgrade(*, repo_root: Path, database_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    _run_command(
        ["python", "-m", "alembic", "-c", "packages/db/alembic.ini", "upgrade", "head"],
        cwd=repo_root,
        env=env,
    )


def _ingest_smoke_documents(engine) -> dict[str, Any]:
    with Session(engine) as session:
        _delete_existing_smoke_documents(session)
        service = IngestionService(session, max_chunk_chars=320)
        first = service.ingest_uploaded_file(
            file_name="pgvector_smoke_battery.md",
            file_bytes=(
                b"# Battery Supply Chain\n\n"
                b"## Refining\n"
                b"Lithium refining capacity remains constrained and "
                b"battery cathode projects keep expanding.\n\n"
                b"## Procurement\n"
                b"Battery manufacturers continue signing long-term supply agreements."
            ),
            media_type="text/markdown",
        )
        second = service.ingest_uploaded_file(
            file_name="pgvector_smoke_solar.md",
            file_bytes=(
                b"# Solar Buildout\n\n"
                b"## Installations\n"
                b"Utility-scale solar installations accelerate across multiple provinces.\n\n"
                b"## Costs\n"
                b"Module costs continue to decline."
            ),
            media_type="text/markdown",
        )
        return {
            "document_ids": [first.document_id, second.document_id],
            "chunk_counts": [first.chunks_count, second.chunks_count],
        }


def _delete_existing_smoke_documents(session: Session) -> None:
    session.execute(
        text(
            "DELETE FROM citations WHERE chunk_id IN ("
            "SELECT id FROM document_chunks WHERE document_id IN ("
            "SELECT id FROM documents WHERE source_uri LIKE 'upload://pgvector_smoke_%'"
            "))"
        )
    )
    session.execute(
        text(
            "DELETE FROM document_chunks WHERE document_id IN ("
            "SELECT id FROM documents WHERE source_uri LIKE 'upload://pgvector_smoke_%'"
            ")"
        )
    )
    session.execute(text("DELETE FROM documents WHERE source_uri LIKE 'upload://pgvector_smoke_%'"))
    session.commit()


def _run_retrieval(engine, *, query: str):
    with Session(engine) as session:
        return ChunkRetrievalService(session).search_chunks(query, RetrievalFilters(limit=5))


def _collect_db_diagnostics(engine) -> tuple[bool, list[str], int]:
    with engine.connect() as conn:
        extension_installed = bool(
            conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar()
        )
        indexes = conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'document_chunks' "
                "AND indexname LIKE 'ix_document_chunks_embedding_vector_hnsw%'"
            )
        ).scalars().all()
        vector_rows = int(
            conn.execute(
                select(text("count(*)")).select_from(DocumentChunk).where(
                    text("embedding_vector IS NOT NULL")
                )
            ).scalar_one()
        )
    return extension_installed, list(indexes), vector_rows


def _run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            "Command failed "
            f"({' '.join(args)}):\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


if __name__ == "__main__":
    main()
