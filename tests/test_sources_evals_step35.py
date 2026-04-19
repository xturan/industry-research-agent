from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Run
from packages.db.models.enums import RunStatus, RunType
from packages.db.session import reset_db_session_state
from packages.evals.graders import grade_source_acquisition_result
from packages.evals.schemas import SourceSmokeEvalRequest
from packages.evals.service import EvalService
from packages.sources.citation import normalize_evidence_item
from packages.sources.performance import SourcePerformanceService
from packages.sources.router import SourceRouter
from packages.sources.schemas import (
    Citation,
    CitationLocator,
    EvidenceItem,
    QueryContext,
    RoutingRecommendation,
    SourcePerformanceItem,
    ToolResponse,
    ToolStatus,
    ToolTrace,
)


def _setup_step35_db(monkeypatch, tmp_path: Path) -> str:
    db_path = tmp_path / "source_step35.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str((tmp_path / "raw").as_posix()))
    monkeypatch.setenv("DELIVERY_EXPORT_DIR", str((tmp_path / "exports").as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return db_url


def test_query_type_classification() -> None:
    router = SourceRouter()
    macro_type, _ = router.classify_query_type(QueryContext(query="gdp cpi trend"))
    energy_type, _ = router.classify_query_type(QueryContext(query="oil inventory shift"))
    filing_type, _ = router.classify_query_type(
        QueryContext(query="10-k filing review", tickers=["AAPL"])
    )
    health_type, _ = router.classify_query_type(QueryContext(query="mortality risk outlook"))
    general_type, _ = router.classify_query_type(QueryContext(query="supply chain memo"))

    assert macro_type.value == "macro"
    assert energy_type.value == "energy"
    assert filing_type.value == "filing"
    assert health_type.value == "health"
    assert general_type.value == "general"


def test_router_explanation_fields_present() -> None:
    router = SourceRouter()
    recs = router.route(QueryContext(query="oil inventory and electricity outlook"))
    assert recs
    top = recs[0]
    assert top.final_score > 0
    assert "rule_match_score" in top.score_breakdown
    assert "failure_penalty" in top.score_breakdown
    assert top.selected_via in {"routing_logic", "user_provided_sources"}
    assert top.query_type is not None


def test_router_penalizes_historically_weak_source() -> None:
    router = SourceRouter()
    context = QueryContext(query="macro and energy outlook with gdp and oil signals")
    performance = {
        "world_bank": SourcePerformanceItem(
            source_id="world_bank",
            attempt_count=10,
            success_count=9,
            partial_count=1,
            failure_count=0,
            no_result_count=1,
            avg_latency_ms=320.0,
            avg_evidence_density=0.9,
            avg_citation_completeness=0.8,
        ),
        "eia": SourcePerformanceItem(
            source_id="eia",
            attempt_count=10,
            success_count=1,
            partial_count=0,
            failure_count=9,
            no_result_count=8,
            avg_latency_ms=1200.0,
            avg_evidence_density=0.1,
            avg_citation_completeness=0.2,
        ),
    }
    recs = router.route(context, performance_by_source=performance)
    ids = [item.source_id for item in recs]
    assert "world_bank" in ids and "eia" in ids
    wb = next(item for item in recs if item.source_id == "world_bank")
    eia = next(item for item in recs if item.source_id == "eia")
    assert wb.final_score > eia.final_score
    assert eia.score_breakdown["failure_penalty"] < 0
    assert eia.score_breakdown["no_result_penalty"] < 0


def test_router_no_result_penalty_case() -> None:
    router = SourceRouter()
    context = QueryContext(query="gdp trend")
    base = router.route(context)
    with_penalty = router.route(
        context,
        performance_by_source={
            "world_bank": SourcePerformanceItem(
                source_id="world_bank",
                attempt_count=10,
                success_count=2,
                partial_count=2,
                failure_count=6,
                no_result_count=10,
                avg_latency_ms=200.0,
                avg_evidence_density=0.0,
                avg_citation_completeness=0.1,
            )
        },
    )
    base_wb = next(item for item in base if item.source_id == "world_bank")
    penalty_wb = next(item for item in with_penalty if item.source_id == "world_bank")
    assert penalty_wb.final_score < base_wb.final_score


def test_source_performance_summary_aggregation(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_step35_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        session.add_all(
            [
                Run(
                    run_type=RunType.RESEARCH,
                    status=RunStatus.SUCCEEDED,
                    input_json={"query": "q1"},
                    output_json={
                        "source_acquisition": {
                            "enabled": True,
                            "routed_sources": ["world_bank"],
                            "source_quality_summary": {
                                "citation_completeness_score": 0.8,
                            },
                            "source_traces": [
                                {
                                    "tool_name": "extract_evidence_items",
                                    "source_id": "world_bank",
                                    "status": "success",
                                    "duration_ms": 120.0,
                                    "item_count": 2,
                                    "evidence_count": 2,
                                    "retry_count": 0,
                                    "warnings": [],
                                }
                            ],
                        }
                    },
                ),
                Run(
                    run_type=RunType.RESEARCH,
                    status=RunStatus.SUCCEEDED,
                    input_json={"query": "q2"},
                    output_json={
                        "source_acquisition": {
                            "enabled": True,
                            "routed_sources": ["world_bank"],
                            "source_quality_summary": {
                                "citation_completeness_score": 0.4,
                            },
                            "source_traces": [
                                {
                                    "tool_name": "extract_evidence_items",
                                    "source_id": "world_bank",
                                    "status": "error",
                                    "duration_ms": 250.0,
                                    "item_count": 1,
                                    "evidence_count": 0,
                                    "retry_count": 1,
                                    "warnings": ["timeout"],
                                }
                            ],
                        }
                    },
                ),
            ]
        )
        session.commit()

        summary = SourcePerformanceService(session).summarize(lookback_days=365)
        assert summary.items
        wb = next(item for item in summary.items if item.source_id == "world_bank")
        assert wb.attempt_count == 2
        assert wb.success_count == 1
        assert wb.failure_count == 1
        assert wb.no_result_count == 1
        assert wb.avg_latency_ms > 0
        assert wb.avg_citation_completeness > 0


def test_source_eval_scoring() -> None:
    query_context = QueryContext(query="gdp trend", countries=["USA"])
    evidence = normalize_evidence_item(
        EvidenceItem(
            evidence_id="evi_1",
            source_id="world_bank",
            title="GDP sample",
            summary="GDP observation",
            support_text="2024: 100",
            score=0.8,
            citation=Citation(
                citation_id="cit_1",
                source_id="world_bank",
                document_id="wb:USA:NY.GDP.MKTP.CD",
                locator=CitationLocator(
                    document_id="wb:USA:NY.GDP.MKTP.CD",
                    section_id="series_observations",
                ),
                quote_text="2024: 100",
                source_uri="https://api.worldbank.org/",
            ),
        ),
        source_name="World Bank Data",
        external_id="USA:NY.GDP.MKTP.CD:2024",
    )
    response = ToolResponse(
        status=ToolStatus.SUCCESS,
        tool_name="build_evidence_bundle",
        route_recommendations=[
            RoutingRecommendation(
                source_id="world_bank",
                reason="macro match",
                priority=95,
            )
        ],
        evidence_items=[evidence],
        traces=[
            ToolTrace(
                tool_name="extract_evidence_items",
                source_id="world_bank",
                status=ToolStatus.SUCCESS,
                duration_ms=80.0,
                http_calls=1,
                page_count=1,
                item_count=1,
                evidence_count=1,
                retry_count=0,
                adapter_version="v1.2",
            )
        ],
    )
    cases, metrics = grade_source_acquisition_result(
        scenario_name="macro_world_bank",
        query_context=query_context,
        response=response,
    )
    assert cases
    assert "world_bank" in metrics
    assert metrics["world_bank"]["overall_score"] > 0
    assert any(item.case_name.endswith(":query_fit") and item.passed for item in cases)


def test_source_smoke_eval_flow(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_step35_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    from packages.sources.adapters import EIAAdapter, SecEdgarAdapter, WorldBankAdapter

    def _wb_fetch_json(self, url: str, **kwargs):  # noqa: ANN001,ARG002
        if "/v2/indicator/" in url and "/country/" not in url:
            return [{}, [{"id": "NY.GDP.MKTP.CD", "name": "GDP"}]]
        return [{}, [{"date": "2024", "value": 100.0}, {"date": "2023", "value": 95.0}]]

    def _eia_fetch_json(self, url: str, **kwargs):  # noqa: ANN001,ARG002
        return {
            "series": [
                {
                    "series_id": "PET.WCESTUS1.W",
                    "name": "Crude Oil Stocks",
                    "data": [["2024-01-05", 450.2], ["2023-12-29", 447.0]],
                }
            ]
        }

    def _sec_lookup_cik(self, ticker: str, **kwargs):  # noqa: ANN001,ARG002
        return "0000320193"

    def _sec_fetch_recent(
        self, cik: str, *, form_type: str | None, limit: int, **kwargs
    ):  # noqa: ANN001,ARG002
        return [
            {
                "accession_number": "0000320193-24-000001",
                "form": form_type or "10-K",
                "filing_date": "2024-11-01",
                "primary_document": "a10k.htm",
                "filing_url": (
                    "https://www.sec.gov/Archives/edgar/data/320193/"
                    "000032019324000001/a10k.htm"
                ),
                "company_name": "APPLE INC",
            }
        ][:limit]

    monkeypatch.setattr(WorldBankAdapter, "_fetch_json", _wb_fetch_json)
    monkeypatch.setattr(EIAAdapter, "_fetch_json", _eia_fetch_json)
    monkeypatch.setattr(SecEdgarAdapter, "_lookup_cik", _sec_lookup_cik)
    monkeypatch.setattr(SecEdgarAdapter, "_fetch_recent_filings", _sec_fetch_recent)

    with Session(engine) as session:
        response = EvalService(session).run_source_smoke(SourceSmokeEvalRequest())
        assert response.eval_run_id > 0
        assert response.scenario_count >= 4
        view = EvalService(session).get_eval_run(response.eval_run_id)
        assert view is not None
        assert view.target_type == "source_smoke"
        assert len(view.items) > 0
