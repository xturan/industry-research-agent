from __future__ import annotations

from datetime import datetime

from packages.rag.schemas import EvidenceBundle, RetrievalResponse, build_bundle_id


class EvidenceBundleBuilder:
    """Builds auditable, grouped evidence bundles from retrieval output."""

    def build_bundle(
        self,
        response: RetrievalResponse,
        *,
        group_by_document: bool = True,
        max_items: int | None = None,
    ) -> EvidenceBundle:
        if max_items is None:
            selected_items = response.items
        else:
            selected_items = response.items[: max(max_items, 1)]

        grouped_documents: list[dict[str, object]] = []
        if group_by_document:
            grouping: dict[int, dict[str, object]] = {}
            for item in selected_items:
                if item.document_id not in grouping:
                    grouping[item.document_id] = {
                        "document_id": item.document_id,
                        "document_title": item.document_title,
                        "source_uri": item.source_uri,
                        "publisher": item.publisher,
                        "source_type": item.source_type,
                        "document_status": item.document_status,
                        "item_count": 0,
                        "chunk_ids": [],
                    }
                payload = grouping[item.document_id]
                payload["item_count"] = int(payload["item_count"]) + 1
                payload["chunk_ids"] = [*payload["chunk_ids"], item.chunk_id]  # type: ignore[list-item]
            grouped_documents = list(grouping.values())

        return EvidenceBundle(
            bundle_id=build_bundle_id(response.query, selected_items),
            query=response.query,
            retrieval_mode=response.retrieval_mode,
            filters=response.filters,
            total_candidates=response.total_candidates,
            items=selected_items,
            grouped_documents=grouped_documents,
            generated_at=datetime.now().isoformat(),
        )
