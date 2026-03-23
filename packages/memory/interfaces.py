from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from packages.memory.schemas import MemoryKind


@dataclass(slots=True)
class MemoryHint:
    memory_type: MemoryKind
    scope_key: str
    content: str
    score: float | None


class MemoryStoreAdapter(Protocol):
    def upsert_hint(self, hint: MemoryHint) -> int:
        """Persist and return memory id."""

    def search_hints(self, query: str, *, limit: int = 10) -> list[MemoryHint]:
        """Search hints for downstream planning/generation."""


# TODO: Add Redis-backed short-term memory adapter for worker pipelines.
# TODO: Add MCP-compatible memory provider adapter for external memory servers.
