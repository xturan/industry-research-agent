from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class RetrievalQuery:
    text: str
    top_k: int = 5
    filters: dict[str, str] | None = None


@dataclass(slots=True)
class EvidenceBundle:
    bundle_id: str
    snippets: list[str]
    metadata: dict[str, str]


class Retriever(Protocol):
    async def retrieve(self, query: RetrievalQuery) -> list[EvidenceBundle]:
        """Return evidence bundles with metadata for auditability."""


# TODO: Add embedding retrieval backend and hybrid weighted fusion.
# TODO: Add advanced reranker (cross-encoder or feature-based model) behind a clean interface.
