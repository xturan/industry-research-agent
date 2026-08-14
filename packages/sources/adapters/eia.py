from __future__ import annotations

from time import perf_counter
from urllib.parse import quote

from packages.core.config import get_settings
from packages.sources.adapters.base import BaseSourceAdapter
from packages.sources.adapters.http_utils import (
    HttpCallTrace,
    SourceHttpError,
    fetch_json_with_trace,
)
from packages.sources.citation import normalize_evidence_item
from packages.sources.enums import (
    AccessMethod,
    SourceCategory,
    ToolErrorCode,
    ToolStatus,
    TrustTier,
)
from packages.sources.schemas import (
    Citation,
    CitationLocator,
    DocumentSection,
    EvidenceItem,
    NormalizedDocument,
    RawDocument,
    SourceAccess,
    SourceCapabilities,
    SourceProfile,
    ToolRequest,
    ToolResponse,
)


class EIAAdapter(BaseSourceAdapter):
    ADAPTER_VERSION = "v1.2"

    SERIES_HINTS = {
        "oil": "PET.WCESTUS1.W",
        "inventory": "PET.WCESTUS1.W",
        "gas": "NG.RNGWHHD.D",
        "electricity": "ELEC.GEN.ALL-US-99.M",
        "power": "ELEC.GEN.ALL-US-99.M",
    }

    def get_profile(self) -> SourceProfile:
        return SourceProfile(
            source_id="eia",
            display_name="US Energy Information Administration",
            category=SourceCategory.ENERGY_DATA,
            trust_tier=TrustTier.PRIMARY_OFFICIAL,
            enabled=True,
            description="Energy fundamentals source skeleton (oil/gas/electricity/inventory).",
            access=SourceAccess(
                access_method=AccessMethod.API,
                auth_required=True,
                auth_type="api_key",
                base_url="https://api.eia.gov",
            ),
            capabilities=SourceCapabilities(
                supports_search=True,
                supports_document_detail=False,
                supports_evidence_extraction=True,
                supports_time_filter=True,
                supports_keyword_filter=True,
                supports_bulk=True,
            ),
            priority_hint=88,
            tags=["energy", "oil", "gas", "electricity"],
        )

    def search_documents(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        series_id = self._resolve_series_id(request)
        if not series_id:
            return self.error_response(
                request,
                code=ToolErrorCode.INVALID_REQUEST,
                message=(
                    "eia requires series_id in payload or an energy keyword "
                    "(oil/gas/electricity/inventory) in query."
                ),
            )
        limit, offset, page = self.resolve_limit_offset(
            request,
            default_limit=request.query_context.max_documents_per_source,
            max_limit=100,
        )
        # EIA series search currently resolves to one canonical series document.
        document = RawDocument(
            document_id=f"eia:{series_id}",
            source_id="eia",
            title=f"EIA Series {series_id}",
            source_uri=f"https://api.eia.gov/series/?series_id={quote(series_id)}",
            publisher="U.S. EIA",
            language="en",
            snippet="EIA series reference resolved from query.",
            metadata={
                "series_id": series_id,
                "offset": offset,
                "limit": limit,
                "page": page,
            },
        )
        return ToolResponse(
            status=ToolStatus.SUCCESS if offset == 0 else ToolStatus.PARTIAL,
            tool_name=request.tool_name,
            source_id="eia",
            documents=[document] if offset == 0 else [],
            message="Resolved EIA series reference.",
            trace=self.build_trace(
                request=request,
                status=ToolStatus.SUCCESS if offset == 0 else ToolStatus.PARTIAL,
                duration_ms=(perf_counter() - started) * 1000.0,
                page_count=1,
                item_count=1 if offset == 0 else 0,
                truncated=offset > 0,
                warnings=(
                    ["EIA search supports one canonical series document."]
                    if offset > 0
                    else []
                ),
            ),
        )

    def fetch_document_detail(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        http_traces: list[HttpCallTrace] = []
        series_id = self._resolve_series_id(request)
        if not series_id:
            return self.error_response(
                request,
                code=ToolErrorCode.INVALID_REQUEST,
                message="eia fetch_document_detail requires series_id.",
            )
        api_key = self._resolve_api_key(request)
        if not api_key:
            return self.error_response(
                request,
                code=ToolErrorCode.INVALID_REQUEST,
                message="eia requires api_key via payload.api_key or EIA_API_KEY env.",
            )
        try:
            limit, offset, page = self.resolve_limit_offset(
                request,
                default_limit=request.query_context.max_documents_per_source,
                max_limit=500,
            )
            url = (
                "https://api.eia.gov/series/"
                f"?api_key={quote(api_key)}&series_id={quote(series_id)}"
            )
            try:
                data = self._fetch_json(url, http_traces=http_traces)
            except TypeError:
                data = self._fetch_json(url)
            series_list = data.get("series", []) if isinstance(data, dict) else []
            if not series_list:
                return ToolResponse(
                    status=ToolStatus.PARTIAL,
                    tool_name=request.tool_name,
                    source_id="eia",
                    message="No series data returned from EIA.",
                    trace=self.build_trace(
                        request=request,
                        status=ToolStatus.PARTIAL,
                        duration_ms=(perf_counter() - started) * 1000.0,
                        http_calls=len(http_traces),
                        retry_count=sum(trace.retry_count for trace in http_traces),
                        item_count=0,
                    ),
                )
            series = series_list[0]
            observations = series.get("data", [])
            lines = []
            normalized_points = []
            total_available = len(observations)
            selected = observations[offset : offset + limit]
            for point in selected:
                if not isinstance(point, list) or len(point) < 2:
                    continue
                period, value = point[0], point[1]
                lines.append(f"{period}: {value}")
                normalized_points.append({"period": period, "value": value})
            normalized = NormalizedDocument(
                document_id=f"eia:{series_id}",
                source_id="eia",
                title=series.get("name") or f"EIA Series {series_id}",
                language="en",
                summary=f"EIA series {series_id} observations.",
                sections=[
                    DocumentSection(
                        section_id="series_observations",
                        heading="Observations",
                        text="\n".join(lines) if lines else "No observations",
                        metadata={
                            "series_id": series_id,
                            "offset": offset,
                            "limit": limit,
                            "page": page,
                        },
                    )
                ],
                metadata={
                    "series_id": series_id,
                    "observations": normalized_points,
                    "api_url": url,
                    "total_observations": total_available,
                    "offset": offset,
                    "limit": limit,
                    "page": page,
                },
            )
            return ToolResponse(
                status=ToolStatus.SUCCESS,
                tool_name=request.tool_name,
                source_id="eia",
                normalized_documents=[normalized],
                message="Fetched EIA series detail.",
                trace=self.build_trace(
                    request=request,
                    status=ToolStatus.SUCCESS,
                    duration_ms=(perf_counter() - started) * 1000.0,
                    http_calls=len(http_traces),
                    retry_count=sum(trace.retry_count for trace in http_traces),
                    page_count=max(((total_available - 1) // max(limit, 1)) + 1, 1)
                    if total_available
                    else 0,
                    item_count=len(normalized_points),
                    truncated=total_available > (offset + len(normalized_points)),
                    metadata={"series_id": series_id},
                ),
            )
        except SourceHttpError as exc:
            return self.error_response(
                request,
                code=ToolErrorCode.INTERNAL_ERROR,
                message=f"eia fetch_document_detail failed: {exc}",
                retryable=exc.retryable,
                detail={"http_trace": exc.trace.to_dict()},
            )
        except Exception as exc:  # noqa: BLE001
            return self.error_response(
                request,
                code=ToolErrorCode.INTERNAL_ERROR,
                message=f"eia fetch_document_detail failed: {exc}",
                retryable=True,
            )

    def extract_evidence_items(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        detail = self.fetch_document_detail(
            ToolRequest(
                tool_name="fetch_document_detail",
                query_context=request.query_context,
                source_id="eia",
                document_id=request.document_id,
                limit=request.limit,
                page=request.page,
                offset=request.offset,
                max_evidence_per_source=request.max_evidence_per_source,
                payload=request.payload,
                evidence_mode=request.evidence_mode,
                trace_id=request.trace_id,
            )
        )
        if detail.status == ToolStatus.ERROR:
            return ToolResponse(
                status=ToolStatus.ERROR,
                tool_name=request.tool_name,
                source_id="eia",
                errors=detail.errors,
                message=detail.message,
            )
        if not detail.normalized_documents:
            return ToolResponse(
                status=ToolStatus.PARTIAL,
                tool_name=request.tool_name,
                source_id="eia",
                message="No EIA normalized documents to extract evidence from.",
            )
        normalized = detail.normalized_documents[0]
        observations = normalized.metadata.get("observations", [])
        if not isinstance(observations, list) or not observations:
            return ToolResponse(
                status=ToolStatus.PARTIAL,
                tool_name=request.tool_name,
                source_id="eia",
                message="No EIA observations available for evidence extraction.",
            )
        evidence_limit = self.resolve_evidence_limit(
            request,
            default_limit=request.query_context.max_evidence_per_source,
            max_limit=500,
        )
        series_id = normalized.metadata.get("series_id", "unknown")
        evidence_items: list[EvidenceItem] = []
        for idx, latest in enumerate(observations[:evidence_limit]):
            locator = CitationLocator(
                document_id=normalized.document_id,
                section_id="series_observations",
                chunk_index=idx,
                external_ref=f"eia:{series_id}:{latest.get('period')}",
            )
            citation = Citation(
                citation_id=f"cit_{normalized.document_id}_{idx}",
                source_id="eia",
                document_id=normalized.document_id,
                locator=locator,
                quote_text=f"{latest.get('period')}: {latest.get('value')}",
                source_uri=normalized.metadata.get("api_url"),
            )
            evidence_items.append(
                normalize_evidence_item(
                    EvidenceItem(
                        evidence_id=f"evi_{normalized.document_id}_{idx}",
                        source_id="eia",
                        title=normalized.title,
                        summary=(
                            "EIA observation: "
                            f"{latest.get('period')}={latest.get('value')}"
                        ),
                        support_text=(
                            normalized.sections[0].text[:400]
                            if normalized.sections
                            else None
                        ),
                        score=0.76,
                        citation=citation,
                        metadata={
                            "series_id": series_id,
                            "observation_count": len(observations),
                        },
                    ),
                    source_name=self.get_profile().display_name,
                    external_id=f"{series_id}:{latest.get('period')}",
                )
            )
        truncated = len(observations) > len(evidence_items)
        return ToolResponse(
            status=ToolStatus.SUCCESS,
            tool_name=request.tool_name,
            source_id="eia",
            normalized_documents=detail.normalized_documents,
            evidence_items=evidence_items,
            message="Extracted EIA evidence item.",
            trace=self.build_trace(
                request=request,
                status=ToolStatus.SUCCESS,
                duration_ms=(perf_counter() - started) * 1000.0,
                item_count=len(detail.normalized_documents),
                evidence_count=len(evidence_items),
                truncated=truncated,
                metadata={
                    "series_id": series_id,
                    "evidence_limit": evidence_limit,
                    "total_observations": len(observations),
                },
            ),
        )

    def _resolve_series_id(self, request: ToolRequest) -> str | None:
        payload_series = request.payload.get("series_id")
        if isinstance(payload_series, str) and payload_series.strip():
            return payload_series.strip()
        query = request.query_context.query.lower()
        for keyword, series_id in self.SERIES_HINTS.items():
            if keyword in query:
                return series_id
        return None

    def _resolve_api_key(self, request: ToolRequest) -> str | None:
        payload_key = request.payload.get("api_key")
        if isinstance(payload_key, str) and payload_key.strip():
            return payload_key.strip()
        settings = get_settings()
        env_key = getattr(settings, "eia_api_key", None)
        if isinstance(env_key, str) and env_key.strip():
            return env_key.strip()
        return None

    def _fetch_json(self, url: str, *, http_traces: list[HttpCallTrace] | None = None):
        settings = get_settings()
        payload, trace = fetch_json_with_trace(
            url,
            timeout=settings.source_http_timeout_seconds,
            max_retries=settings.source_http_retry_count,
            backoff_seconds=settings.source_http_backoff_seconds,
        )
        if http_traces is not None:
            http_traces.append(trace)
        return payload
