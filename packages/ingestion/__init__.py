"""Ingestion pipeline for raw sources -> documents/chunks/citations with run tracing."""

from packages.ingestion.service import IngestionResult, IngestionService

__all__ = ["IngestionResult", "IngestionService"]
