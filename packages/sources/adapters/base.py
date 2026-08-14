from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from packages.sources.enums import ToolErrorCode, ToolStatus
from packages.sources.schemas import SourceProfile, ToolError, ToolRequest, ToolResponse, ToolTrace


class BaseSourceAdapter(ABC):
    ADAPTER_VERSION = "v1.1"

    @abstractmethod
    def get_profile(self) -> SourceProfile:
        """Return adapter profile metadata."""

    @abstractmethod
    def search_documents(self, request: ToolRequest) -> ToolResponse:
        """Search documents under the source."""

    @abstractmethod
    def fetch_document_detail(self, request: ToolRequest) -> ToolResponse:
        """Fetch one document detail."""

    @abstractmethod
    def extract_evidence_items(self, request: ToolRequest) -> ToolResponse:
        """Extract evidence items from source or document."""

    def not_implemented(self, request: ToolRequest, operation: str) -> ToolResponse:
        profile = self.get_profile()
        return ToolResponse(
            status=ToolStatus.NOT_IMPLEMENTED,
            tool_name=request.tool_name,
            source_id=profile.source_id,
            message=f"{profile.source_id}.{operation} is not implemented yet.",
            errors=[
                ToolError(
                    code=ToolErrorCode.NOT_IMPLEMENTED,
                    message=f"{profile.source_id}.{operation} is not implemented.",
                    retryable=False,
                )
            ],
            trace=self.build_trace(
                request=request,
                status=ToolStatus.NOT_IMPLEMENTED,
                warnings=[f"{profile.source_id}.{operation} is not implemented."],
            ),
        )

    def error_response(
        self,
        request: ToolRequest,
        *,
        code: ToolErrorCode,
        message: str,
        retryable: bool = False,
        detail: dict[str, Any] | None = None,
    ) -> ToolResponse:
        profile = self.get_profile()
        return ToolResponse(
            status=ToolStatus.ERROR,
            tool_name=request.tool_name,
            source_id=profile.source_id,
            message=message,
            errors=[
                ToolError(
                    code=code,
                    message=message,
                    retryable=retryable,
                    detail=detail or {},
                )
            ],
            trace=self.build_trace(
                request=request,
                status=ToolStatus.ERROR,
                retry_count=1 if retryable else 0,
                warnings=[message],
                metadata={"error_detail": detail or {}},
            ),
        )

    def build_trace(
        self,
        *,
        request: ToolRequest,
        status: ToolStatus,
        duration_ms: float | None = None,
        http_calls: int = 0,
        page_count: int = 1,
        item_count: int = 0,
        evidence_count: int = 0,
        retry_count: int = 0,
        truncated: bool = False,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolTrace:
        profile = self.get_profile()
        request_params = {
            "limit": request.limit,
            "page": request.page,
            "offset": request.offset,
            "max_evidence_per_source": request.max_evidence_per_source,
            **request.payload,
        }
        return ToolTrace(
            tool_name=request.tool_name,
            source_id=profile.source_id,
            status=status,
            duration_ms=duration_ms,
            request_params=request_params,
            http_calls=max(http_calls, 0),
            page_count=max(page_count, 0),
            item_count=max(item_count, 0),
            evidence_count=max(evidence_count, 0),
            retry_count=max(retry_count, 0),
            adapter_version=self.ADAPTER_VERSION,
            truncated=truncated,
            warnings=warnings or [],
            notes=[],
            metadata=metadata or {},
        )

    def resolve_limit_offset(
        self,
        request: ToolRequest,
        *,
        default_limit: int,
        max_limit: int = 200,
    ) -> tuple[int, int, int]:
        raw_limit = request.limit if request.limit is not None else request.payload.get("limit")
        if isinstance(raw_limit, int) and raw_limit > 0:
            limit = min(raw_limit, max_limit)
        else:
            limit = min(default_limit, max_limit)

        raw_page = request.page if request.page is not None else request.payload.get("page")
        raw_offset = (
            request.offset
            if request.offset is not None
            else request.payload.get("offset")
        )
        page = raw_page if isinstance(raw_page, int) and raw_page > 0 else 1
        if isinstance(raw_offset, int) and raw_offset >= 0:
            offset = raw_offset
            page = int((offset / max(limit, 1)) + 1)
        else:
            offset = (page - 1) * limit
        return limit, offset, page

    def resolve_evidence_limit(
        self,
        request: ToolRequest,
        *,
        default_limit: int,
        max_limit: int = 200,
    ) -> int:
        raw_limit = (
            request.max_evidence_per_source
            if request.max_evidence_per_source is not None
            else request.payload.get("max_evidence_per_source")
        )
        if isinstance(raw_limit, int) and raw_limit > 0:
            return min(raw_limit, max_limit)
        return min(default_limit, max_limit)

    def now(self) -> datetime:
        return datetime.now()
