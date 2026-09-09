from __future__ import annotations

from pathlib import Path

from packages.db.models import SourceType
from packages.ingestion.schemas import RawSourceData
from packages.sources.adapters import (
    EIAAdapter,
    SecEdgarAdapter,
    UserInputAdapter,
    WorldBankAdapter,
)
from packages.sources.adapters.http_utils import HttpCallTrace, SourceHttpError
from packages.sources.enums import ToolStatus
from packages.sources.registry import SourceRegistry
from packages.sources.router import SourceRouter
from packages.sources.schemas import QueryContext, ToolRequest, UserProvidedSource
from packages.sources.service import SourceIntelligenceService
from packages.sources.tools import build_source_tool_registry


def test_user_input_adapter_end_to_end(monkeypatch, tmp_path: Path) -> None:
    file_path = tmp_path / "note.md"
    file_path.write_text("# Local Note\n\nDemand trend remains mixed.", encoding="utf-8")

    def _fake_fetch_url(url: str, **kwargs):  # noqa: ANN003
        return RawSourceData(
            source_uri=url,
            source_name="url_note.md",
            source_type=SourceType.ARTICLE,
            content_bytes=b"# URL Note\n\nSupply remains tight.",
            media_type="text/markdown",
            file_extension=".md",
        )

    monkeypatch.setattr("packages.sources.adapters.user_input.fetch_url", _fake_fetch_url)

    adapter = UserInputAdapter()
    context = QueryContext(
        query="user source test",
        user_provided_sources=[
            UserProvidedSource(title="Inline", inline_text="Inline note for testing."),
            UserProvidedSource(source_uri="https://example.com/report"),
            UserProvidedSource(file_ref=str(file_path)),
        ],
    )
    search = adapter.search_documents(
        ToolRequest(tool_name="search_source_documents", query_context=context)
    )
    assert search.status == ToolStatus.SUCCESS
    assert len(search.documents) == 3
    assert len(search.normalized_documents) == 3

    extract = adapter.extract_evidence_items(
        ToolRequest(tool_name="extract_evidence_items", query_context=context)
    )
    assert extract.status == ToolStatus.SUCCESS
    assert len(extract.evidence_items) >= 1


def test_world_bank_adapter_minimal_flow(monkeypatch) -> None:
    adapter = WorldBankAdapter()

    def _fake_fetch_json(url: str):  # noqa: ANN001
        if "/v2/indicator/" in url and "/country/" not in url:
            return [{}, [{"id": "NY.GDP.MKTP.CD", "name": "GDP (current US$)"}]]
        if "/v2/country/" in url:
            return [{}, [{"date": "2024", "value": 100.0}, {"date": "2023", "value": 95.0}]]
        raise AssertionError(url)

    monkeypatch.setattr(adapter, "_fetch_json", _fake_fetch_json)
    request = ToolRequest(
        tool_name="search_source_documents",
        query_context=QueryContext(query="gdp trend", countries=["USA"]),
    )
    search = adapter.search_documents(request)
    assert search.status == ToolStatus.SUCCESS
    assert search.documents

    detail = adapter.fetch_document_detail(
        ToolRequest(tool_name="fetch_document_detail", query_context=request.query_context)
    )
    assert detail.status == ToolStatus.SUCCESS
    assert detail.normalized_documents

    extract = adapter.extract_evidence_items(
        ToolRequest(tool_name="extract_evidence_items", query_context=request.query_context)
    )
    assert extract.status == ToolStatus.SUCCESS
    assert extract.evidence_items


def test_eia_adapter_minimal_flow(monkeypatch) -> None:
    adapter = EIAAdapter()

    def _fake_fetch_json(url: str):  # noqa: ANN001
        return {
            "series": [
                {
                    "series_id": "PET.WCESTUS1.W",
                    "name": "Crude Oil Stocks",
                    "data": [["2024-01-05", 450.2], ["2023-12-29", 447.0]],
                }
            ]
        }

    monkeypatch.setattr(adapter, "_fetch_json", _fake_fetch_json)
    request = ToolRequest(
        tool_name="search_source_documents",
        query_context=QueryContext(query="oil inventory"),
        payload={"api_key": "demo", "series_id": "PET.WCESTUS1.W"},
    )
    search = adapter.search_documents(request)
    assert search.status == ToolStatus.SUCCESS
    assert search.documents

    detail = adapter.fetch_document_detail(
        ToolRequest(
            tool_name="fetch_document_detail",
            query_context=request.query_context,
            payload=request.payload,
        )
    )
    assert detail.status == ToolStatus.SUCCESS
    assert detail.normalized_documents

    extract = adapter.extract_evidence_items(
        ToolRequest(
            tool_name="extract_evidence_items",
            query_context=request.query_context,
            payload=request.payload,
        )
    )
    assert extract.status == ToolStatus.SUCCESS
    assert extract.evidence_items


def test_sec_edgar_adapter_minimal_flow(monkeypatch) -> None:
    adapter = SecEdgarAdapter()
    monkeypatch.setattr(adapter, "_lookup_cik", lambda ticker: "0000320193")
    monkeypatch.setattr(
        adapter,
        "_fetch_recent_filings",
        lambda cik, form_type, limit: [  # noqa: ARG005
            {
                "accession_number": "0000320193-24-000001",
                "form": "10-K",
                "filing_date": "2024-11-01",
                "primary_document": "a10k.htm",
                "filing_url": (
                    "https://www.sec.gov/Archives/edgar/data/320193/"
                    "000032019324000001/a10k.htm"
                ),
                "company_name": "APPLE INC",
            }
        ],
    )

    context = QueryContext(query="10-k filing analysis", tickers=["AAPL"])
    search = adapter.search_documents(
        ToolRequest(tool_name="search_source_documents", query_context=context)
    )
    assert search.status == ToolStatus.SUCCESS
    assert search.documents

    detail = adapter.fetch_document_detail(
        ToolRequest(
            tool_name="fetch_document_detail",
            query_context=context,
            document_id=search.documents[0].document_id,
        )
    )
    assert detail.status == ToolStatus.SUCCESS
    assert detail.normalized_documents

    extract = adapter.extract_evidence_items(
        ToolRequest(
            tool_name="extract_evidence_items",
            query_context=context,
            document_id=search.documents[0].document_id,
        )
    )
    assert extract.status == ToolStatus.SUCCESS
    assert extract.evidence_items


def test_build_evidence_bundle_from_mixed_sources(monkeypatch) -> None:
    user_adapter = UserInputAdapter()
    world_bank = WorldBankAdapter()

    def _fake_wb_fetch_json(url: str):  # noqa: ANN001
        if "/v2/indicator/" in url and "/country/" not in url:
            return [{}, [{"id": "NY.GDP.MKTP.CD", "name": "GDP (current US$)"}]]
        return [{}, [{"date": "2024", "value": 100.0}, {"date": "2023", "value": 95.0}]]

    monkeypatch.setattr(world_bank, "_fetch_json", _fake_wb_fetch_json)

    registry = SourceRegistry()
    registry.register(user_adapter)
    registry.register(world_bank)
    tools = build_source_tool_registry(source_registry=registry, source_router=SourceRouter())

    context = QueryContext(
        query="gdp with internal memo",
        user_provided_sources=[
            UserProvidedSource(inline_text="Internal memo supports macro view.")
        ],
    )
    response = tools.dispatch(ToolRequest(tool_name="build_evidence_bundle", query_context=context))
    assert response.bundle is not None
    assert response.bundle.items
    assert response.bundle.source_summary


def test_source_service_router_registry_integration() -> None:
    service = SourceIntelligenceService()
    macro = service.route_sources(QueryContext(query="gdp cpi trend"))
    energy = service.route_sources(QueryContext(query="oil inventory outlook"))
    filings = service.route_sources(QueryContext(query="10-k filing review"))
    with_user = service.route_sources(
        QueryContext(
            query="custom note",
            user_provided_sources=[UserProvidedSource(inline_text="x")],
        )
    )
    assert any(item.source_id == "world_bank" for item in macro)
    assert any(item.source_id == "eia" for item in energy)
    assert any(item.source_id == "sec_edgar" for item in filings)
    assert any(item.source_id == "user_input" for item in with_user)


def test_empty_no_result_case_is_graceful(monkeypatch) -> None:
    adapter = WorldBankAdapter()
    monkeypatch.setattr(adapter, "_fetch_json", lambda url: [{}, []])  # noqa: ARG005
    response = adapter.fetch_document_detail(
        ToolRequest(tool_name="fetch_document_detail", query_context=QueryContext(query="gdp"))
    )
    assert response.status in {ToolStatus.PARTIAL, ToolStatus.ERROR}


def test_world_bank_source_http_error_detail_is_serializable(monkeypatch) -> None:
    adapter = WorldBankAdapter()

    def _raise_source_http_error(*args, **kwargs):  # noqa: ANN002,ANN003
        raise SourceHttpError(
            "upstream timeout",
            retryable=True,
            trace=HttpCallTrace(
                url="https://api.worldbank.org/v2/indicator/NY.GDP.MKTP.CD?format=json",
                status_code=504,
                attempts=2,
                retry_count=1,
                retryable_failures=1,
                non_retryable_failures=0,
                latency_ms=321.5,
                error="TimeoutError: request timed out",
            ),
        )

    monkeypatch.setattr(adapter, "_fetch_indicator_meta", _raise_source_http_error)
    response = adapter.search_documents(
        ToolRequest(tool_name="search_source_documents", query_context=QueryContext(query="gdp"))
    )
    assert response.status == ToolStatus.ERROR
    assert response.errors
    detail = response.errors[0].detail
    assert isinstance(detail, dict)
    assert isinstance(detail.get("http_trace"), dict)
    assert detail["http_trace"]["status_code"] == 504
