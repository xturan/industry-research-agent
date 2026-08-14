from __future__ import annotations

import re
from time import perf_counter

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


class SecEdgarAdapter(BaseSourceAdapter):
    ADAPTER_VERSION = "v1.2"
    TICKER_PATTERN = re.compile(r"\b[A-Z]{1,5}\b")
    _ticker_map_cache: dict[str, str] | None = None

    def get_profile(self) -> SourceProfile:
        return SourceProfile(
            source_id="sec_edgar",
            display_name="SEC EDGAR",
            category=SourceCategory.REGULATORY_FILINGS,
            trust_tier=TrustTier.PRIMARY_OFFICIAL,
            enabled=True,
            description="US SEC filings source (10-K, 10-Q, 8-K) skeleton adapter.",
            access=SourceAccess(
                access_method=AccessMethod.API,
                auth_required=False,
                base_url="https://www.sec.gov",
                terms_url="https://www.sec.gov/privacy",
            ),
            capabilities=SourceCapabilities(
                supports_search=True,
                supports_document_detail=True,
                supports_evidence_extraction=True,
                supports_time_filter=True,
                supports_keyword_filter=True,
                supports_bulk=True,
            ),
            priority_hint=90,
            tags=["filings", "regulatory", "official"],
        )

    def search_documents(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        http_traces: list[HttpCallTrace] = []
        ticker = self._resolve_ticker(request)
        if not ticker:
            return self.error_response(
                request,
                code=ToolErrorCode.INVALID_REQUEST,
                message="sec_edgar requires ticker via payload.ticker or query_context.tickers.",
            )
        try:
            try:
                cik = self._lookup_cik(ticker, http_traces=http_traces)
            except TypeError:
                cik = self._lookup_cik(ticker)
            if cik is None:
                return self.error_response(
                    request,
                    code=ToolErrorCode.INVALID_REQUEST,
                    message=f"Ticker '{ticker}' not found in SEC company ticker map.",
                )
            form_type = self._resolve_form_type(request)
            limit, offset, page = self.resolve_limit_offset(
                request,
                default_limit=self._resolve_limit(request),
                max_limit=50,
            )
            fetch_limit = min(limit + offset, 200)
            try:
                filings = self._fetch_recent_filings(
                    cik,
                    form_type=form_type,
                    limit=fetch_limit,
                    http_traces=http_traces,
                )
            except TypeError:
                filings = self._fetch_recent_filings(cik, form_type=form_type, limit=fetch_limit)
            total_available = len(filings)
            selected = filings[offset : offset + limit]
            documents = [self._to_raw_document(cik, ticker, filing) for filing in selected]
            status = ToolStatus.SUCCESS if documents else ToolStatus.PARTIAL
            truncated = total_available > (offset + len(documents))
            return ToolResponse(
                status=status,
                tool_name=request.tool_name,
                source_id="sec_edgar",
                documents=documents,
                message=f"Fetched {len(documents)} SEC filing metadata record(s).",
                metadata={"ticker": ticker, "cik": cik, "form_type": form_type},
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
                        "ticker": ticker,
                        "cik": cik,
                        "form_type": form_type,
                        "offset": offset,
                        "page": page,
                        "total_available": total_available,
                    },
                ),
            )
        except SourceHttpError as exc:
            return self.error_response(
                request,
                code=ToolErrorCode.INTERNAL_ERROR,
                message=f"sec_edgar search failed: {exc}",
                retryable=exc.retryable,
                detail={"http_trace": exc.trace.to_dict()},
            )
        except Exception as exc:  # noqa: BLE001
            return self.error_response(
                request,
                code=ToolErrorCode.INTERNAL_ERROR,
                message=f"sec_edgar search failed: {exc}",
                retryable=True,
            )

    def fetch_document_detail(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        search_response = self.search_documents(
            ToolRequest(
                tool_name="search_source_documents",
                query_context=request.query_context,
                source_id="sec_edgar",
                limit=request.limit,
                page=request.page,
                offset=request.offset,
                max_evidence_per_source=request.max_evidence_per_source,
                payload=request.payload,
                evidence_mode=request.evidence_mode,
                trace_id=request.trace_id,
            )
        )
        if search_response.status == ToolStatus.ERROR:
            return ToolResponse(
                status=ToolStatus.ERROR,
                tool_name=request.tool_name,
                source_id="sec_edgar",
                errors=search_response.errors,
                message=search_response.message,
            )
        documents = search_response.documents
        if not documents:
            return ToolResponse(
                status=ToolStatus.PARTIAL,
                tool_name=request.tool_name,
                source_id="sec_edgar",
                message="No SEC documents found for detail lookup.",
                trace=self.build_trace(
                    request=request,
                    status=ToolStatus.PARTIAL,
                    duration_ms=(perf_counter() - started) * 1000.0,
                    item_count=0,
                ),
            )
        target_document = documents[0]
        if request.document_id:
            for document in documents:
                if document.document_id == request.document_id:
                    target_document = document
                    break
        normalized = NormalizedDocument(
            document_id=target_document.document_id,
            source_id="sec_edgar",
            title=target_document.title,
            language="en",
            summary=(
                f"SEC filing {target_document.document_id} for "
                f"{search_response.metadata.get('ticker', 'unknown')}."
            ),
            sections=[
                DocumentSection(
                    section_id="filing_metadata",
                    heading="Filing Metadata",
                    text=(
                        f"Form: {target_document.metadata.get('form')}\n"
                        f"Filed: {target_document.metadata.get('filing_date')}\n"
                        f"Accession: {target_document.document_id}\n"
                        f"Primary Document: {target_document.metadata.get('primary_document')}"
                    ),
                )
            ],
            metadata={
                "ticker": search_response.metadata.get("ticker"),
                "cik": search_response.metadata.get("cik"),
                **target_document.metadata,
            },
        )
        return ToolResponse(
            status=ToolStatus.SUCCESS,
            tool_name=request.tool_name,
            source_id="sec_edgar",
            documents=[target_document],
            normalized_documents=[normalized],
            message="SEC filing detail prepared.",
            trace=self.build_trace(
                request=request,
                status=ToolStatus.SUCCESS,
                duration_ms=(perf_counter() - started) * 1000.0,
                item_count=1,
            ),
        )

    def extract_evidence_items(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        detail = self.fetch_document_detail(
            ToolRequest(
                tool_name="fetch_document_detail",
                query_context=request.query_context,
                source_id="sec_edgar",
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
                source_id="sec_edgar",
                errors=detail.errors,
                message=detail.message,
            )
        if not detail.documents:
            return ToolResponse(
                status=ToolStatus.PARTIAL,
                tool_name=request.tool_name,
                source_id="sec_edgar",
                message="No SEC filing available for evidence extraction.",
            )
        document = detail.documents[0]
        form_type = str(document.metadata.get("form") or "")
        filing_date = str(document.metadata.get("filing_date") or "")
        locator = CitationLocator(
            document_id=document.document_id,
            section_id="filing_metadata",
            external_ref=document.document_id,
        )
        citation = Citation(
            citation_id=f"cit_{document.document_id}",
            source_id="sec_edgar",
            document_id=document.document_id,
            locator=locator,
            quote_text=f"{form_type} filed {filing_date}",
            source_uri=document.source_uri,
        )
        evidence = normalize_evidence_item(
            EvidenceItem(
                evidence_id=f"evi_{document.document_id}",
                source_id="sec_edgar",
                title=document.title,
                summary=f"{form_type} filing metadata for {document.document_id}.",
                support_text=(
                    detail.normalized_documents[0].sections[0].text
                    if detail.normalized_documents and detail.normalized_documents[0].sections
                    else None
                ),
                score=0.74,
                citation=citation,
                metadata=document.metadata,
            ),
            source_name=self.get_profile().display_name,
            external_id=document.document_id,
        )
        return ToolResponse(
            status=ToolStatus.SUCCESS,
            tool_name=request.tool_name,
            source_id="sec_edgar",
            documents=detail.documents,
            normalized_documents=detail.normalized_documents,
            evidence_items=[evidence],
            message="Extracted SEC filing evidence item.",
            trace=self.build_trace(
                request=request,
                status=ToolStatus.SUCCESS,
                duration_ms=(perf_counter() - started) * 1000.0,
                item_count=len(detail.documents),
                evidence_count=1,
            ),
        )

    def _resolve_ticker(self, request: ToolRequest) -> str | None:
        payload_ticker = request.payload.get("ticker")
        if isinstance(payload_ticker, str) and payload_ticker.strip():
            return payload_ticker.strip().upper()
        if request.query_context.tickers:
            first = request.query_context.tickers[0].strip().upper()
            return first or None
        query = request.query_context.query
        match = self.TICKER_PATTERN.search(query)
        if match:
            return match.group(0).upper()
        return None

    def _resolve_form_type(self, request: ToolRequest) -> str | None:
        form_type = request.payload.get("form_type")
        if isinstance(form_type, str) and form_type.strip():
            return form_type.strip().upper()
        return None

    def _resolve_limit(self, request: ToolRequest) -> int:
        limit = request.payload.get("limit")
        if isinstance(limit, int) and limit > 0:
            return min(limit, 20)
        return min(request.query_context.max_documents_per_source, 20)

    def _fetch_recent_filings(
        self,
        cik: str,
        *,
        form_type: str | None,
        limit: int,
        http_traces: list[HttpCallTrace] | None = None,
    ) -> list[dict]:
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        submissions = self._fetch_json(url, http_traces=http_traces)
        recent = submissions.get("filings", {}).get("recent", {})
        accessions = recent.get("accessionNumber", [])
        forms = recent.get("form", [])
        filed_dates = recent.get("filingDate", [])
        primary_docs = recent.get("primaryDocument", [])
        company_name = submissions.get("name")
        filings: list[dict] = []
        for idx, accession in enumerate(accessions):
            form = forms[idx] if idx < len(forms) else None
            if form_type and form != form_type:
                continue
            filed_date = filed_dates[idx] if idx < len(filed_dates) else None
            primary_document = primary_docs[idx] if idx < len(primary_docs) else None
            accession_clean = str(accession).replace("-", "")
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                f"{accession_clean}/{primary_document}"
            )
            filings.append(
                {
                    "accession_number": accession,
                    "form": form,
                    "filing_date": filed_date,
                    "primary_document": primary_document,
                    "filing_url": filing_url,
                    "company_name": company_name,
                }
            )
            if len(filings) >= limit:
                break
        return filings

    def _to_raw_document(self, cik: str, ticker: str, filing: dict) -> RawDocument:
        accession = str(filing.get("accession_number") or "unknown")
        title = (
            f"{filing.get('form') or 'FILING'} {accession} "
            f"({ticker})"
        )
        return RawDocument(
            document_id=accession,
            source_id="sec_edgar",
            title=title,
            source_uri=filing.get("filing_url"),
            publisher="SEC",
            language="en",
            snippet=f"{filing.get('company_name')} filed {filing.get('form')}",
            metadata={
                "ticker": ticker,
                "cik": cik,
                "form": filing.get("form"),
                "filing_date": filing.get("filing_date"),
                "primary_document": filing.get("primary_document"),
            },
        )

    def _ticker_map(self, *, http_traces: list[HttpCallTrace] | None = None) -> dict[str, str]:
        if self._ticker_map_cache is not None:
            return self._ticker_map_cache
        url = "https://www.sec.gov/files/company_tickers.json"
        payload = self._fetch_json(url, http_traces=http_traces)
        mapping: dict[str, str] = {}
        if isinstance(payload, dict):
            values = payload.values()
        elif isinstance(payload, list):
            values = payload
        else:
            values = []
        for item in values:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker") or "").upper()
            cik_value = item.get("cik_str")
            if ticker and cik_value is not None:
                mapping[ticker] = str(int(cik_value)).zfill(10)
        self._ticker_map_cache = mapping
        return mapping

    def _lookup_cik(
        self, ticker: str, *, http_traces: list[HttpCallTrace] | None = None
    ) -> str | None:
        return self._ticker_map(http_traces=http_traces).get(ticker.upper())

    def _fetch_json(self, url: str, *, http_traces: list[HttpCallTrace] | None = None):
        settings = get_settings()
        headers = {"User-Agent": settings.sec_user_agent}
        payload, trace = fetch_json_with_trace(
            url,
            headers=headers,
            timeout=settings.source_http_timeout_seconds,
            max_retries=settings.source_http_retry_count,
            backoff_seconds=settings.source_http_backoff_seconds,
        )
        if http_traces is not None:
            http_traces.append(trace)
        return payload
