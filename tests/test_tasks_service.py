from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.content.schemas import ContentFormat, ContentGenerateRequest
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Document, RunStep, SourceType, TaskAttempt, TaskJob
from packages.db.session import reset_db_session_state
from packages.delivery.enums import DeliveryTarget
from packages.delivery.schemas import DeliveryJobCreateRequest
from packages.delivery.service import DeliveryService
from packages.ingestion.service import IngestionService
from packages.tasks.schemas import (
    ContentGenerateTaskSubmitRequest,
    DeliveryDispatchTaskSubmitRequest,
    ResearchAnalyzeTaskSubmitRequest,
)
from packages.tasks.service import TaskService
from packages.tasks.worker import TaskWorker


def _setup_task_db(monkeypatch, tmp_path: Path) -> str:
    db_path = tmp_path / "tasks_service.db"
    raw_path = tmp_path / "raw"
    export_path = tmp_path / "exports"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str(raw_path.as_posix()))
    monkeypatch.setenv("DELIVERY_EXPORT_DIR", str(export_path.as_posix()))
    monkeypatch.setenv("TASK_RETRY_BACKOFF_SECONDS", "0")
    get_settings.cache_clear()
    reset_db_session_state()

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return db_url


def _seed_document(session: Session) -> None:
    result = IngestionService(session, max_chunk_chars=260).ingest_uploaded_file(
        file_name="tasks_seed.md",
        file_bytes=(
            b"# Storage Theme\n\n## Signal\n"
            b"Lithium refining bottlenecks keep supply tight.\n\n"
            b"## Risk\nDemand softness can lower shipment growth."
        ),
        media_type="text/markdown",
        source_type=SourceType.REPORT,
    )
    document = session.get(Document, result.document_id)
    document.industry = "Energy Storage"
    document.published_at = datetime(2026, 2, 15)
    session.add(document)
    session.commit()


def test_task_worker_end_to_end_and_idempotency(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_task_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    worker = TaskWorker(worker_id="test-worker-1", poll_interval_seconds=1)

    with Session(engine) as session:
        _seed_document(session)
        service = TaskService(session)

        research_accepted = service.enqueue_research(
            ResearchAnalyzeTaskSubmitRequest(
                idempotency_key="research:energy:1",
                request=ResearchAnalyzeRequest(
                    query="lithium pricing outlook",
                    top_k=6,
                    industry="Energy Storage",
                    mode="mock",
                ),
            )
        )
        research_dup = service.enqueue_research(
            ResearchAnalyzeTaskSubmitRequest(
                idempotency_key="research:energy:1",
                request=ResearchAnalyzeRequest(
                    query="lithium pricing outlook",
                    top_k=6,
                    industry="Energy Storage",
                    mode="mock",
                ),
            )
        )
        assert research_dup.deduplicated is True
        assert research_dup.task_id == research_accepted.task_id

    assert worker.run_once() is True

    with Session(engine) as session:
        service = TaskService(session)
        research_task = service.get_task(research_accepted.task_id)
        assert research_task is not None
        assert research_task.status.value == "succeeded"
        research_run_id = int((research_task.result_json or {}).get("run_id"))

        content_accepted = service.enqueue_content(
            ContentGenerateTaskSubmitRequest(
                idempotency_key="content:energy:1",
                request=ContentGenerateRequest(
                    research_run_id=research_run_id,
                    content_types=[
                        ContentFormat.WECHAT_ARTICLE,
                        ContentFormat.XIAOHONGSHU_POST,
                        ContentFormat.DOUYIN_SCRIPT,
                    ],
                    mode="mock",
                ),
            )
        )
        content_dup = service.enqueue_content(
            ContentGenerateTaskSubmitRequest(
                idempotency_key="content:energy:1",
                request=ContentGenerateRequest(
                    research_run_id=research_run_id,
                    content_types=[ContentFormat.WECHAT_ARTICLE],
                    mode="mock",
                ),
            )
        )
        assert content_dup.deduplicated is True
        assert content_dup.task_id == content_accepted.task_id

    assert worker.run_once() is True

    with Session(engine) as session:
        service = TaskService(session)
        content_task = service.get_task(content_accepted.task_id)
        assert content_task is not None
        assert content_task.status.value == "succeeded"
        assets = ((content_task.result_json or {}).get("assets")) or []
        assert len(assets) == 3
        asset_ids = [int(item["asset_id"]) for item in assets[:2]]
        source_research_run_id = (content_task.result_json or {}).get("source_research_run_id")

        delivery_job = DeliveryService(session).create_job(
            DeliveryJobCreateRequest(
                content_asset_ids=asset_ids,
                source_run_id=source_research_run_id,
                delivery_target=DeliveryTarget.EXPORT_BUNDLE,
                require_review=False,
                mode="mock",
            )
        )
        delivery_task = service.enqueue_delivery(
            DeliveryDispatchTaskSubmitRequest(
                idempotency_key="delivery:energy:1",
                delivery_job_id=delivery_job.delivery_job_id,
            )
        )

    assert worker.run_once() is True

    with Session(engine) as session:
        service = TaskService(session)
        delivery_task_view = service.get_task(delivery_task.task_id)
        assert delivery_task_view is not None
        assert delivery_task_view.status.value == "succeeded"
        dispatch_status = (delivery_task_view.result_json or {}).get("status")
        assert dispatch_status == "dispatched"

        task_count = session.scalar(select(func.count()).select_from(TaskJob))
        attempt_count = session.scalar(select(func.count()).select_from(TaskAttempt))
        assert task_count == 3
        assert attempt_count >= 3


def test_task_research_source_assisted(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_task_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    worker = TaskWorker(worker_id="test-worker-source-assisted", poll_interval_seconds=1)

    with Session(engine) as session:
        _seed_document(session)
        accepted = TaskService(session).enqueue_research(
            ResearchAnalyzeTaskSubmitRequest(
                idempotency_key="research:source:1",
                request=ResearchAnalyzeRequest(
                    query="Assess supply from user source",
                    mode="mock",
                    top_k=6,
                    enable_source_acquisition=True,
                    enable_pdf_processing=True,
                    max_pdf_attachments_per_source=2,
                    max_pdf_pages_per_attachment=10,
                    user_provided_sources=[
                        {
                            "title": "Inline note",
                            "inline_text": "Supply remains tight across key refiners.",
                        }
                    ],
                ),
            )
        )

    assert worker.run_once() is True

    with Session(engine) as session:
        task_view = TaskService(session).get_task(accepted.task_id)
        assert task_view is not None
        assert task_view.status.value == "succeeded"
        result_json = task_view.result_json or {}
        source_summary = result_json.get("source_acquisition") or {}
        assert source_summary.get("enabled") is True
        assert "user_input" in source_summary.get("routed_sources", [])
        pdf_summary = source_summary.get("pdf_summary") or {}
        assert pdf_summary.get("enabled") is True
        assert "attachments_discovered" in pdf_summary
        assert "attachments_processed" in pdf_summary

        run_id = int(result_json["run_id"])
        step_names = {
            row.step_name
            for row in session.scalars(select(RunStep).where(RunStep.run_id == run_id)).all()
        }
        assert {
            "source_route",
            "source_search",
            "source_fetch_detail",
            "source_extract_evidence",
            "source_build_bundle",
            "pdf_discover_attachments",
            "pdf_download",
            "pdf_extract",
            "pdf_extract_evidence",
        } <= step_names


def test_task_retry_and_dead_letter(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_task_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    worker = TaskWorker(worker_id="test-worker-2", poll_interval_seconds=1)

    with Session(engine) as session:
        _seed_document(session)
        accepted = TaskService(session).enqueue_research(
            ResearchAnalyzeTaskSubmitRequest(
                request=ResearchAnalyzeRequest(
                    query="lithium pricing outlook",
                    top_k=6,
                    industry="Energy Storage",
                    mode="mock",
                ),
                max_attempts=2,
                idempotency_key="research:retry:1",
            )
        )

    from packages.tasks import handlers as task_handlers_module

    original_execute = task_handlers_module.TaskHandlers.execute

    def _always_fail(self, *, task_type, payload_json):  # noqa: ANN001
        raise RuntimeError("simulated transient failure")

    monkeypatch.setattr(task_handlers_module.TaskHandlers, "execute", _always_fail)
    monkeypatch.setattr("packages.tasks.service.compute_retry_delay_seconds", lambda **_: 0)

    assert worker.run_once() is True
    assert worker.run_once() is True

    with Session(engine) as session:
        view = TaskService(session).get_task(accepted.task_id)
        assert view is not None
        assert view.status.value == "dead_letter"
        assert view.attempt_count == 2
        statuses = [item.status for item in view.attempts]
        assert "retry_scheduled" in statuses
        assert "failed" in statuses

    monkeypatch.setattr(task_handlers_module.TaskHandlers, "execute", original_execute)


def test_task_research_llm_deepseek_mocked(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_task_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    worker = TaskWorker(worker_id="test-worker-deepseek", poll_interval_seconds=1)

    class _FakeDeepSeekProviderClient:
        def __init__(self, **kwargs):  # noqa: ANN003
            self.default_model = kwargs.get("model", "deepseek-reasoner")

        def generate_text(self, **kwargs):  # noqa: ANN003
            raise NotImplementedError

        def generate_json(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            model: str | None = None,
            enable_thinking: bool = False,
        ):
            import json

            from packages.providers.base import JsonProviderResponse, ProviderCallMetadata

            payload = json.loads(user_prompt)
            if isinstance(payload, dict) and isinstance(payload.get("original_input"), dict):
                payload = payload["original_input"]

            if "Supervisor Agent" in system_prompt:
                data = {
                    "normalized_query": payload.get("query", ""),
                    "focus_terms": ["lithium"],
                    "planned_stages": [
                        "retrieve_evidence",
                        "thesis_builder",
                        "opponent",
                        "evidence_judge",
                        "risk_analyst",
                        "synthesize_memo",
                    ],
                    "note": None,
                }
            elif "Thesis Builder Agent" in system_prompt:
                first = payload.get("bundle", {}).get("items", [{}])[0]
                chunk_id = int(first.get("chunk_id", 1))
                doc_id = int(first.get("document_id", 1))
                data = {
                    "theses": [
                        {
                            "thesis_id": "thesis_1",
                            "title": "Supply tightness signal",
                            "stance": "constructive",
                            "summary": "Supply constraints remain visible.",
                            "confidence_score": 0.6,
                            "support_strength": 0.6,
                            "evidence_chunk_ids": [chunk_id],
                            "evidence_refs": [f"doc:{doc_id}/chunk:{chunk_id}"],
                            "rationale": "Mock deepseek output.",
                        }
                    ]
                }
            elif "Opponent Agent" in system_prompt:
                thesis = payload.get("theses", [{}])[0]
                data = {
                    "objections": [
                        {
                            "thesis_id": thesis.get("thesis_id", "thesis_1"),
                            "objection": "Demand downside remains possible.",
                            "severity": 3,
                            "evidence_chunk_ids": thesis.get("evidence_chunk_ids", [1]),
                            "evidence_refs": thesis.get("evidence_refs", ["doc:1/chunk:1"]),
                            "rationale": "Mock challenge.",
                        }
                    ]
                }
            elif "Evidence Judge Agent" in system_prompt:
                thesis = payload.get("theses", [{}])[0]
                data = {
                    "coverage": [
                        {
                            "thesis_id": thesis.get("thesis_id", "thesis_1"),
                            "support_score": 0.4,
                            "support_label": "weak",
                            "supporting_chunk_ids": thesis.get("evidence_chunk_ids", [1]),
                            "gaps": ["Need source diversity."],
                            "notes": "mock",
                        }
                    ],
                    "overall_sufficiency_score": 0.4,
                    "overall_label": "weak",
                    "global_gaps": ["Need source diversity."],
                }
            elif "Risk Analyst Agent" in system_prompt:
                thesis = payload.get("theses", [{}])[0]
                data = {
                    "risks": [
                        {
                            "thesis_id": thesis.get("thesis_id", "thesis_1"),
                            "risk_title": "Evidence concentration risk",
                            "risk_description": "Limited evidence coverage.",
                            "invalidation_condition": "Contradictory new source appears.",
                            "severity": 4,
                            "related_chunk_ids": thesis.get("evidence_chunk_ids", [1]),
                        }
                    ]
                }
            else:
                evidence_judge = payload.get("evidence_judge", {})
                data = {
                    "query": payload.get("query", ""),
                    "executive_summary": "Mock deepseek memo.",
                    "key_theses": payload.get("theses", []),
                    "counterarguments": payload.get("objections", []),
                    "evidence_gaps": evidence_judge.get("global_gaps", []),
                    "major_risks": payload.get("risks", []),
                    "confidence_assessment": "weak confidence",
                    "confidence_score": float(evidence_judge.get("overall_sufficiency_score", 0.0)),
                    "suggested_next_questions": ["Need more sources?"],
                }

            return JsonProviderResponse(
                provider="deepseek",
                model=model or self.default_model,
                content_text=json.dumps(data),
                json_data=data,
                metadata=ProviderCallMetadata(
                    provider="deepseek",
                    model=model or self.default_model,
                ),
                reasoning_content="hidden reasoning",
            )

    monkeypatch.setattr(
        "packages.agents.provider.DeepSeekProviderClient",
        _FakeDeepSeekProviderClient,
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy")
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    get_settings.cache_clear()

    with Session(engine) as session:
        _seed_document(session)
        accepted = TaskService(session).enqueue_research(
            ResearchAnalyzeTaskSubmitRequest(
                idempotency_key="research:llm:deepseek:1",
                request=ResearchAnalyzeRequest(
                    query="lithium pricing outlook",
                    top_k=6,
                    industry="Energy Storage",
                    mode="llm",
                    provider="deepseek",
                ),
            )
        )

    assert worker.run_once() is True

    with Session(engine) as session:
        task_view = TaskService(session).get_task(accepted.task_id)
        assert task_view is not None
        assert task_view.status.value == "succeeded"
        result_json = task_view.result_json or {}
        assert result_json["mode"] == "llm"
        assert result_json["provider"] == "deepseek"
