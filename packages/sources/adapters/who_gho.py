from __future__ import annotations

from packages.sources.adapters.base import BaseSourceAdapter
from packages.sources.enums import AccessMethod, SourceCategory, TrustTier
from packages.sources.schemas import (
    SourceAccess,
    SourceCapabilities,
    SourceProfile,
    ToolRequest,
    ToolResponse,
)


class WHOGHOAdapter(BaseSourceAdapter):
    def get_profile(self) -> SourceProfile:
        return SourceProfile(
            source_id="who_gho",
            display_name="WHO Global Health Observatory",
            category=SourceCategory.HEALTH_DATA,
            trust_tier=TrustTier.PRIMARY_OFFICIAL,
            enabled=True,
            description=(
                "Global health indicators source skeleton "
                "(mortality/disease/life expectancy)."
            ),
            access=SourceAccess(
                access_method=AccessMethod.API,
                auth_required=False,
                base_url="https://ghoapi.azureedge.net",
            ),
            capabilities=SourceCapabilities(
                supports_search=True,
                supports_document_detail=False,
                supports_evidence_extraction=True,
                supports_time_filter=True,
                supports_keyword_filter=True,
                supports_bulk=True,
            ),
            priority_hint=82,
            tags=["health", "mortality", "life_expectancy"],
        )

    def search_documents(self, request: ToolRequest) -> ToolResponse:
        return self.not_implemented(request, "search_documents")

    def fetch_document_detail(self, request: ToolRequest) -> ToolResponse:
        return self.not_implemented(request, "fetch_document_detail")

    def extract_evidence_items(self, request: ToolRequest) -> ToolResponse:
        return self.not_implemented(request, "extract_evidence_items")
