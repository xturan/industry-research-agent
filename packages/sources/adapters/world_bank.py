from __future__ import annotations

from datetime import datetime
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
from packages.sources.enums import AccessMethod, SourceCategory, ToolStatus, TrustTier
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
    ToolErrorCode,
    ToolRequest,
    ToolResponse,
)


class WorldBankAdapter(BaseSourceAdapter):
    ADAPTER_VERSION = "v1.2"

    INDICATOR_MAP = {
        "gdp": "NY.GDP.MKTP.CD",
        "cpi": "FP.CPI.TOTL.ZG",
        "inflation": "FP.CPI.TOTL.ZG",
        "population": "SP.POP.TOTL",
    }

    def get_profile(self) -> SourceProfile:
        return SourceProfile(
            source_id="world_bank",
            display_name="World Bank Data",
            category=SourceCategory.MACRO_DATA,
            trust_tier=TrustTier.PRIMARY_OFFICIAL,
            enabled=True,
            description="Global macro indicators source skeleton (GDP/CPI/population).",
            access=SourceAccess(
                access_method=AccessMethod.API,
                auth_required=False,
                base_url="https://api.worldbank.org",
            ),
            capabilities=SourceCapabilities(
                supports_search=True,
                supports_document_detail=False,
                supports_evidence_extraction=True,
                supports_time_filter=True,
                supports_keyword_filter=True,
                supports_bulk=True,
            ),
            priority_hint=85,
            tags=["macro", "gdp", "population"],
        )

    def search_documents(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        http_traces: list[HttpCallTrace] = []
        try:
            indicator_code = self._resolve_indicator_code(request)
            if indicator_code is None:
                return self.error_response(
                    request,
                    code=ToolErrorCode.INVALID_REQUEST,
                    message=(
                        "world_bank requires indicator_code in payload or "
                        "query keywords (gdp/cpi/population)."
                    ),
                )
            countries = self._resolve_country_codes(request)
            limit, offset, page = self.resolve_limit_offset(
                request,
                default_limit=request.query_context.max_documents_per_source,
                max_limit=100,
            )
            indicator_meta = self._fetch_indicator_meta(indicator_code, http_traces=http_traces)
            total_available = len(countries)
            selected_countries = countries[offset : offset + limit]
            documents = [
                RawDocument(
                    document_id=f"wb:{country}:{indicator_code}",
                    source_id="world_bank",
                    title=f"{indicator_meta.get('name', indicator_code)} [{country}]",
                    source_uri=(
                        "https://api.worldbank.org/v2/country/"
                        f"{country}/indicator/{quote(indicator_code)}?format=json"
                    ),
                    publisher="World Bank",
                    language="en",
                    snippet=indicator_meta.get("sourceNote"),
                    metadata={
                        "country_code": country,
                        "indicator_code": indicator_code,
                        "indicator_name": indicator_meta.get("name"),
                    },
                )
                for country in selected_countries
            ]
            truncated = total_available > (offset + len(documents))
            status = ToolStatus.SUCCESS if documents else ToolStatus.PARTIAL
            return ToolResponse(
                status=status,
                tool_name=request.tool_name,
                source_id="world_bank",
                documents=documents,
                message=f"Prepared {len(documents)} world_bank indicator document reference(s).",
                trace=self.build_trace(
                    request=request,
                    status=status,
                    duration_ms=(perf_counter() - started) * 1000.0,
                    http_calls=len(http_traces),
                    retry_count=sum(trace.retry_count for trace in http_traces),
                    page_count=max(((total_available - 1) // max(limit, 1)) + 1, 1)
                    if total_available
                    else 0,
                    item_count=len(documents),
                    truncated=truncated,
                    metadata={
                        "total_available": total_available,
                        "indicator_code": indicator_code,
                        "countries": selected_countries,
                        "page": page,
                        "offset": offset,
                    },
                ),
            )
        except SourceHttpError as exc:
            return self.error_response(
                request,
                code=ToolErrorCode.INTERNAL_ERROR,
                message=f"world_bank search failed: {exc}",
                retryable=exc.retryable,
                detail={"http_trace": exc.trace.to_dict()},
            )
        except Exception as exc:  # noqa: BLE001
            return self.error_response(
                request,
                code=ToolErrorCode.INTERNAL_ERROR,
                message=f"world_bank search failed: {exc}",
                retryable=True,
            )

    def fetch_document_detail(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        http_traces: list[HttpCallTrace] = []
        try:
            indicator_code = self._resolve_indicator_code(request)
            if indicator_code is None:
                return self.error_response(
                    request,
                    code=ToolErrorCode.INVALID_REQUEST,
                    message="world_bank fetch_document_detail requires indicator_code.",
                )
            country_code = self._resolve_country_codes(request)[0]
            start_year, end_year = self._resolve_year_range(request)
            limit, offset, page = self.resolve_limit_offset(
                request,
                default_limit=request.query_context.max_documents_per_source,
                max_limit=500,
            )
            series = self._fetch_series(
                country_code,
                indicator_code,
                start_year,
                end_year,
                http_traces=http_traces,
            )
            observations = self._extract_observations(series)
            total_available = len(observations)
            observations = observations[offset : offset + limit]
            if not observations:
                return ToolResponse(
                    status=ToolStatus.PARTIAL,
                    tool_name=request.tool_name,
                    source_id="world_bank",
                    message="No non-null observations returned by world_bank.",
                    trace=self.build_trace(
                        request=request,
                        status=ToolStatus.PARTIAL,
                        duration_ms=(perf_counter() - started) * 1000.0,
                        http_calls=len(http_traces),
                        retry_count=sum(trace.retry_count for trace in http_traces),
                        page_count=max(((total_available - 1) // max(limit, 1)) + 1, 1)
                        if total_available
                        else 0,
                        item_count=0,
                        truncated=total_available > 0,
                        warnings=["No observations after applying offset/limit."],
                    ),
                )
            title = f"{indicator_code} [{country_code}]"
            lines = [f"{item['date']}: {item['value']}" for item in observations]
            normalized_document = NormalizedDocument(
                document_id=f"wb:{country_code}:{indicator_code}",
                source_id="world_bank",
                title=title,
                language="en",
                summary=f"World Bank series {indicator_code} for {country_code}.",
                sections=[
                    DocumentSection(
                        section_id="series_observations",
                        heading="Observations",
                        text="\n".join(lines),
                        metadata={
                            "country_code": country_code,
                            "indicator_code": indicator_code,
                            "start_year": start_year,
                            "end_year": end_year,
                            "offset": offset,
                            "limit": limit,
                            "page": page,
                        },
                    )
                ],
                metadata={
                    "series": observations,
                    "country_code": country_code,
                    "indicator_code": indicator_code,
                    "total_observations": total_available,
                    "offset": offset,
                    "limit": limit,
                    "page": page,
                },
            )
            return ToolResponse(
                status=ToolStatus.SUCCESS,
                tool_name=request.tool_name,
                source_id="world_bank",
                normalized_documents=[normalized_document],
                message="Fetched world_bank series detail.",
                trace=self.build_trace(
                    request=request,
                    status=ToolStatus.SUCCESS,
                    duration_ms=(perf_counter() - started) * 1000.0,
                    http_calls=len(http_traces),
                    retry_count=sum(trace.retry_count for trace in http_traces),
                    page_count=max(((total_available - 1) // max(limit, 1)) + 1, 1),
                    item_count=len(observations),
                    truncated=total_available > (offset + len(observations)),
                    metadata={
                        "total_available": total_available,
                        "country_code": country_code,
                        "indicator_code": indicator_code,
                    },
                ),
            )
        except SourceHttpError as exc:
            return self.error_response(
                request,
                code=ToolErrorCode.INTERNAL_ERROR,
                message=f"world_bank fetch_document_detail failed: {exc}",
                retryable=exc.retryable,
                detail={"http_trace": exc.trace.to_dict()},
            )
        except Exception as exc:  # noqa: BLE001
            return self.error_response(
                request,
                code=ToolErrorCode.INTERNAL_ERROR,
                message=f"world_bank fetch_document_detail failed: {exc}",
                retryable=True,
            )

    def extract_evidence_items(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        detail = self.fetch_document_detail(
            ToolRequest(
                tool_name="fetch_document_detail",
                query_context=request.query_context,
                source_id="world_bank",
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
                source_id="world_bank",
                errors=detail.errors,
                message=detail.message,
            )
        if not detail.normalized_documents:
            return ToolResponse(
                status=ToolStatus.PARTIAL,
                tool_name=request.tool_name,
                source_id="world_bank",
                message="No world_bank normalized documents to extract evidence from.",
            )

        normalized = detail.normalized_documents[0]
        series = normalized.metadata.get("series", [])
        if not isinstance(series, list) or not series:
            return ToolResponse(
                status=ToolStatus.PARTIAL,
                tool_name=request.tool_name,
                source_id="world_bank",
                message="world_bank normalized series is empty.",
            )
        latest = series[0]
        indicator_code = normalized.metadata.get("indicator_code", "unknown")
        country_code = normalized.metadata.get("country_code", "WLD")
        evidence_limit = self.resolve_evidence_limit(
            request,
            default_limit=request.query_context.max_evidence_per_source,
            max_limit=500,
        )
        evidence_items: list[EvidenceItem] = []
        for idx, row in enumerate(series[:evidence_limit]):
            locator = CitationLocator(
                document_id=normalized.document_id,
                section_id="series_observations",
                chunk_index=idx,
                external_ref=f"wb:{country_code}:{indicator_code}:{row.get('date')}",
            )
            citation = Citation(
                citation_id=f"cit_{normalized.document_id}_{idx}",
                source_id="world_bank",
                document_id=normalized.document_id,
                locator=locator,
                quote_text=f"{row.get('date')}: {row.get('value')}",
                source_uri=(
                    "https://api.worldbank.org/v2/country/"
                    f"{country_code}/indicator/{quote(str(indicator_code))}?format=json"
                ),
            )
            evidence_items.append(
                normalize_evidence_item(
                    EvidenceItem(
                        evidence_id=f"evi_{normalized.document_id}_{idx}",
                        source_id="world_bank",
                        title=normalized.title,
                        summary=(
                            "World Bank observation: "
                            f"{row.get('date')}={row.get('value')}"
                        ),
                        support_text=(
                            normalized.sections[0].text[:400]
                            if normalized.sections
                            else None
                        ),
                        score=0.78,
                        citation=citation,
                        metadata={
                            "country_code": country_code,
                            "indicator_code": indicator_code,
                            "observation_count": len(series),
                        },
                    ),
                    source_name=self.get_profile().display_name,
                    external_id=f"{country_code}:{indicator_code}:{row.get('date')}",
                )
            )
        truncated = len(series) > len(evidence_items)
        return ToolResponse(
            status=ToolStatus.SUCCESS,
            tool_name=request.tool_name,
            source_id="world_bank",
            normalized_documents=detail.normalized_documents,
            evidence_items=evidence_items,
            message="Extracted world_bank evidence item.",
            trace=self.build_trace(
                request=request,
                status=ToolStatus.SUCCESS,
                duration_ms=(perf_counter() - started) * 1000.0,
                item_count=len(detail.normalized_documents),
                evidence_count=len(evidence_items),
                truncated=truncated,
                metadata={
                    "total_series_points": len(series),
                    "evidence_limit": evidence_limit,
                    "latest": latest,
                },
            ),
        )

    def _resolve_indicator_code(self, request: ToolRequest) -> str | None:
        payload_indicator = request.payload.get("indicator_code")
        if isinstance(payload_indicator, str) and payload_indicator.strip():
            return payload_indicator.strip()
        query = request.query_context.query.lower()
        for keyword, indicator_code in self.INDICATOR_MAP.items():
            if keyword in query:
                return indicator_code
        return None

    def _resolve_country_codes(self, request: ToolRequest) -> list[str]:
        payload_codes = request.payload.get("country_codes")
        if isinstance(payload_codes, list):
            normalized = [str(code).upper() for code in payload_codes if str(code).strip()]
            if normalized:
                return normalized
        if request.query_context.countries:
            return [country.upper() for country in request.query_context.countries]
        return ["WLD"]

    def _resolve_year_range(self, request: ToolRequest) -> tuple[int, int]:
        date_range = request.payload.get("date_range")
        if isinstance(date_range, dict):
            try:
                start = int(date_range.get("start_year"))
                end = int(date_range.get("end_year"))
                if start <= end:
                    return start, end
            except (TypeError, ValueError):
                pass
        if request.query_context.time_range and request.query_context.time_range.start_at:
            start_year = request.query_context.time_range.start_at.year
            end_year = (
                request.query_context.time_range.end_at.year
                if request.query_context.time_range.end_at
                else datetime.now().year
            )
            if start_year <= end_year:
                return start_year, end_year
        current_year = datetime.now().year
        return current_year - 5, current_year

    def _fetch_indicator_meta(
        self, indicator_code: str, *, http_traces: list[HttpCallTrace] | None = None
    ) -> dict:
        url = f"https://api.worldbank.org/v2/indicator/{quote(indicator_code)}?format=json"
        try:
            data = self._fetch_json(url, http_traces=http_traces)
        except TypeError:
            data = self._fetch_json(url)
        if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list) and data[1]:
            first = data[1][0]
            if isinstance(first, dict):
                return first
        return {"id": indicator_code, "name": indicator_code}

    def _fetch_series(
        self,
        country_code: str,
        indicator_code: str,
        start_year: int,
        end_year: int,
        *,
        http_traces: list[HttpCallTrace] | None = None,
    ):
        url = (
            "https://api.worldbank.org/v2/country/"
            f"{country_code}/indicator/{quote(indicator_code)}"
            f"?format=json&per_page=200&date={start_year}:{end_year}"
        )
        try:
            data = self._fetch_json(url, http_traces=http_traces)
        except TypeError:
            data = self._fetch_json(url)
        if isinstance(data, list) and len(data) >= 2:
            return data[1]
        return []

    def _extract_observations(self, rows) -> list[dict]:  # noqa: ANN001
        observations: list[dict] = []
        if not isinstance(rows, list):
            return observations
        for row in rows:
            if not isinstance(row, dict):
                continue
            value = row.get("value")
            date = row.get("date")
            if value is None or date is None:
                continue
            observations.append({"date": str(date), "value": value})
        observations.sort(key=lambda item: item["date"], reverse=True)
        return observations

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
