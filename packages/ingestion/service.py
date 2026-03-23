from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.db.models import (
    Citation,
    Document,
    DocumentChunk,
    DocumentStatus,
    Run,
    RunStatus,
    RunStep,
    RunType,
    SourceType,
    StepStatus,
)
from packages.ingestion.chunker import chunk_parsed_content
from packages.ingestion.citations import build_citations_for_chunks
from packages.ingestion.fetchers import fetch_local_file, fetch_url
from packages.ingestion.parser import parse_source
from packages.ingestion.schemas import RawSourceData
from packages.ingestion.storage import LocalRawStorage

T = TypeVar("T")


class IngestionError(Exception):
    """Domain-level ingestion error."""


@dataclass(slots=True)
class IngestionResult:
    document_id: int
    run_id: int
    chunks_count: int
    citations_count: int
    status: str


class IngestionService:
    """Deterministic ingestion pipeline with full run-step traceability."""

    def __init__(
        self,
        session: Session,
        *,
        storage: LocalRawStorage | None = None,
        max_chunk_chars: int | None = None,
    ) -> None:
        self.session = session
        settings = get_settings()
        self.storage = storage or LocalRawStorage(settings.raw_storage_dir)
        self.max_chunk_chars = max_chunk_chars or settings.ingestion_max_chunk_chars

    def ingest_local_file(
        self,
        file_path: str | Path,
        *,
        source_type: SourceType = SourceType.OTHER,
    ) -> IngestionResult:
        raw_source = fetch_local_file(file_path, source_type=source_type)
        return self._ingest(
            raw_source,
            run_input={"mode": "file", "file_path": str(Path(file_path).resolve().as_posix())},
        )

    def ingest_uploaded_file(
        self,
        *,
        file_name: str,
        file_bytes: bytes,
        media_type: str | None = None,
        source_type: SourceType = SourceType.OTHER,
    ) -> IngestionResult:
        extension = Path(file_name).suffix.lower() or ".txt"
        raw_source = RawSourceData(
            source_uri=f"upload://{file_name}",
            source_name=file_name,
            source_type=source_type,
            content_bytes=file_bytes,
            media_type=media_type,
            file_extension=extension,
        )
        return self._ingest(raw_source, run_input={"mode": "upload", "file_name": file_name})

    def ingest_url(
        self,
        url: str,
        *,
        source_type: SourceType = SourceType.ARTICLE,
    ) -> IngestionResult:
        raw_source = self._run_fetch_url(url, source_type)
        return self._ingest(raw_source, run_input={"mode": "url", "url": url})

    def _run_fetch_url(self, url: str, source_type: SourceType) -> RawSourceData:
        settings = get_settings()
        try:
            return fetch_url(
                url,
                source_type=source_type,
                timeout_seconds=settings.ingestion_request_timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover - exercised in service tests through ingest_url
            raise IngestionError(f"URL fetch failed: {exc}") from exc

    def _create_run(self, run_input: dict[str, Any]) -> Run:
        run = Run(
            run_type=RunType.RESEARCH,
            status=RunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            input_json={"pipeline": "ingestion", **run_input},
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def _run_step(
        self,
        *,
        run: Run,
        name: str,
        input_json: dict[str, Any] | None,
        fn: Callable[[], T],
        output_serializer: Callable[[T], dict[str, Any]] | None = None,
    ) -> T:
        step = RunStep(
            run_id=run.id,
            step_name=name,
            agent_name="ingestion-service",
            status=StepStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            input_json=input_json,
        )
        self.session.add(step)
        self.session.commit()
        self.session.refresh(step)

        try:
            result = fn()
        except Exception as exc:
            step.status = StepStatus.FAILED
            step.error_message = str(exc)
            step.finished_at = datetime.now(timezone.utc)
            self.session.add(step)
            self.session.commit()
            raise

        step.status = StepStatus.SUCCEEDED
        step.finished_at = datetime.now(timezone.utc)
        step.output_json = output_serializer(result) if output_serializer else None
        self.session.add(step)
        self.session.commit()
        return result

    def _ingest(self, raw_source: RawSourceData, *, run_input: dict[str, Any]) -> IngestionResult:
        run = self._create_run(run_input=run_input)
        document: Document | None = None
        chunks_count = 0
        citations_count = 0

        try:
            self._run_step(
                run=run,
                name="fetch",
                input_json={"source_uri": raw_source.source_uri},
                fn=lambda: raw_source,
                output_serializer=lambda result: {
                    "source_name": result.source_name,
                    "byte_size": len(result.content_bytes),
                    "media_type": result.media_type,
                },
            )

            stored_raw = self._run_step(
                run=run,
                name="store",
                input_json={"base_dir": str(self.storage.base_dir)},
                fn=lambda: self.storage.persist(raw_source),
                output_serializer=lambda result: {
                    "raw_storage_path": result.storage_path,
                    "content_hash": result.content_hash,
                    "byte_size": result.byte_size,
                },
            )

            def init_document() -> Document:
                existing = self.session.scalar(
                    select(Document).where(Document.content_hash == stored_raw.content_hash)
                )
                if existing is not None:
                    existing.raw_storage_path = stored_raw.storage_path
                    existing.source_uri = raw_source.source_uri
                    self.session.add(existing)
                    self.session.commit()
                    self.session.refresh(existing)
                    return existing

                document_name = Path(raw_source.source_name).stem[:200] or "untitled-source"
                created = Document(
                    title=document_name,
                    source_type=raw_source.source_type,
                    source_uri=raw_source.source_uri,
                    summary=None,
                    raw_storage_path=stored_raw.storage_path,
                    content_hash=stored_raw.content_hash,
                    status=DocumentStatus.NEW,
                )
                self.session.add(created)
                self.session.commit()
                self.session.refresh(created)
                return created

            document = self._run_step(
                run=run,
                name="persist_document",
                input_json={"content_hash": stored_raw.content_hash},
                fn=init_document,
                output_serializer=lambda result: {
                    "document_id": result.id,
                    "status": result.status.value,
                },
            )

            parsed = self._run_step(
                run=run,
                name="parse",
                input_json={
                    "source_uri": raw_source.source_uri,
                    "file_extension": raw_source.file_extension,
                },
                fn=lambda: parse_source(raw_source),
                output_serializer=lambda result: {
                    "title": result.title,
                    "section_count": len(result.sections),
                    "char_count": len(result.text),
                    "parser": result.metadata.get("parser"),
                },
            )

            document.title = parsed.title
            document.publisher = parsed.publisher
            document.published_at = parsed.published_at
            document.language = parsed.language
            document.summary = parsed.text[:500]
            document.status = DocumentStatus.PARSED
            self.session.add(document)
            self.session.commit()

            chunk_drafts = self._run_step(
                run=run,
                name="chunk",
                input_json={"max_chunk_chars": self.max_chunk_chars},
                fn=lambda: chunk_parsed_content(parsed, max_chars=self.max_chunk_chars),
                output_serializer=lambda result: {"chunks_count": len(result)},
            )
            citation_drafts = build_citations_for_chunks(chunk_drafts)

            def persist_chunks_and_citations() -> tuple[int, int]:
                existing_chunks = self.session.scalars(
                    select(DocumentChunk).where(DocumentChunk.document_id == document.id)
                ).all()
                for chunk in existing_chunks:
                    self.session.delete(chunk)
                self.session.flush()

                chunk_rows: list[DocumentChunk] = []
                for chunk in chunk_drafts:
                    row = DocumentChunk(
                        document_id=document.id,
                        chunk_index=chunk.chunk_index,
                        section_name=chunk.section_name,
                        text=chunk.text,
                        metadata_json=chunk.metadata_json,
                        token_count=chunk.token_count,
                    )
                    self.session.add(row)
                    chunk_rows.append(row)
                self.session.flush()

                for idx, chunk_row in enumerate(chunk_rows):
                    citation = citation_drafts[idx]
                    self.session.add(
                        Citation(
                            document_id=document.id,
                            chunk_id=chunk_row.id,
                            locator=citation.locator,
                            quote_text=citation.quote_text,
                        )
                    )

                document.status = DocumentStatus.INDEXED
                self.session.add(document)
                self.session.commit()
                return len(chunk_rows), len(citation_drafts)

            chunks_count, citations_count = self._run_step(
                run=run,
                name="persist_chunks",
                input_json={"document_id": document.id},
                fn=persist_chunks_and_citations,
                output_serializer=lambda result: {
                    "chunks_count": result[0],
                    "citations_count": result[1],
                },
            )

            run.status = RunStatus.SUCCEEDED
            run.finished_at = datetime.now(timezone.utc)
            run.output_json = {
                "document_id": document.id,
                "chunks_count": chunks_count,
                "citations_count": citations_count,
            }
            self.session.add(run)
            self.session.commit()
            self.session.refresh(run)

            return IngestionResult(
                document_id=document.id,
                run_id=run.id,
                chunks_count=chunks_count,
                citations_count=citations_count,
                status=document.status.value,
            )

        except Exception as exc:
            if document is not None:
                document.status = DocumentStatus.FAILED
                self.session.add(document)
            run.status = RunStatus.FAILED
            run.finished_at = datetime.now(timezone.utc)
            run.output_json = {"error": str(exc)}
            self.session.add(run)
            self.session.commit()
            raise IngestionError(str(exc)) from exc
