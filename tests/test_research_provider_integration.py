from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from apps.api.main import app
from packages.agents.provider import resolve_provider
from packages.agents.schemas import ResearchMode, ResearchProvider
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Document, SourceType
from packages.db.session import get_engine, reset_db_session_state
from packages.ingestion.service import IngestionService
from packages.providers.base import (
    JsonProviderResponse,
    ProviderCallMetadata,
    ProviderParseError,
    ProviderRetryableError,
)


def _setup_research_db(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "research_provider.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str((tmp_path / "raw").as_posix()))
    get_settings.cache_clear()
    reset_db_session_state()

    engine = get_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = IngestionService(session, max_chunk_chars=260).ingest_uploaded_file(
            file_name="llm-research.md",
            file_bytes=(
                b"# Research Note\n\n## Supply\n"
                b"Lithium refining constraints support elevated prices.\n\n"
                b"## Counterpoint\nDemand softness could pressure volumes."
            ),
            media_type="text/markdown",
            source_type=SourceType.REPORT,
        )
        document = session.get(Document, result.document_id)
        document.industry = "Energy Storage"
        document.published_at = datetime(2026, 2, 5)
        session.add(document)
        session.commit()


def _install_fake_deepseek(monkeypatch, *, fail_parse: bool = False):
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
        ) -> JsonProviderResponse:
            payload = json.loads(user_prompt)
            if isinstance(payload, dict) and isinstance(payload.get("original_input"), dict):
                payload = payload["original_input"]

            if fail_parse and "Thesis Builder Agent" in system_prompt:
                raise ProviderParseError("Provider returned invalid JSON.")

            if "Supervisor Agent" in system_prompt:
                bundle = payload.get("bundle", {})
                note = None
                if int(bundle.get("total_items", 0)) == 0:
                    note = "No evidence retrieved; keep low-confidence framing."
                data = {
                    "normalized_query": payload.get("query", ""),
                    "focus_terms": ["lithium", "pricing"],
                    "planned_stages": [
                        "retrieve_evidence",
                        "thesis_builder",
                        "opponent",
                        "evidence_judge",
                        "risk_analyst",
                        "synthesize_memo",
                    ],
                    "note": note,
                }
            elif "Thesis Builder Agent" in system_prompt:
                items = payload.get("bundle", {}).get("items", [])
                first = items[0] if items else {}
                chunk_id = int(first.get("chunk_id", 1))
                doc_id = int(first.get("document_id", 1))
                locator = first.get("citation_locator") or "chunk:0"
                data = {
                    "theses": [
                        {
                            "thesis_id": "thesis_1",
                            "title": "Supply remains tight",
                            "stance": "constructive",
                            "summary": "Refining constraints support pricing power.",
                            "confidence_score": 0.62,
                            "support_strength": 0.64,
                            "evidence_chunk_ids": [chunk_id],
                            "evidence_refs": [f"doc:{doc_id}/chunk:{chunk_id}@{locator}"],
                            "rationale": "Derived from top retrieved chunk.",
                        }
                    ]
                }
            elif "Opponent Agent" in system_prompt:
                theses = payload.get("theses", [])
                thesis = theses[0] if theses else {}
                data = {
                    "objections": [
                        {
                            "thesis_id": thesis.get("thesis_id", "thesis_1"),
                            "objection": "Demand softness could cap upside.",
                            "severity": 3,
                            "evidence_chunk_ids": thesis.get("evidence_chunk_ids", [1]),
                            "evidence_refs": thesis.get("evidence_refs", ["doc:1/chunk:1"]),
                            "rationale": "Counter-demand scenario.",
                        }
                    ]
                }
            elif "Evidence Judge Agent" in system_prompt:
                theses = payload.get("theses", [])
                if not theses:
                    data = {
                        "coverage": [],
                        "overall_sufficiency_score": 0.0,
                        "overall_label": "insufficient",
                        "global_gaps": ["No thesis-level evidence available."],
                    }
                else:
                    data = {
                        "coverage": [
                            {
                                "thesis_id": theses[0].get("thesis_id", "thesis_1"),
                                "support_score": 0.45,
                                "support_label": "weak",
                                "supporting_chunk_ids": theses[0].get("evidence_chunk_ids", [1]),
                                "gaps": ["Needs more independent sources."],
                                "notes": "single-source support",
                            }
                        ],
                        "overall_sufficiency_score": 0.45,
                        "overall_label": "weak",
                        "global_gaps": ["Needs more independent sources."],
                    }
            elif "Risk Analyst Agent" in system_prompt:
                theses = payload.get("theses", [])
                thesis = theses[0] if theses else {}
                data = {
                    "risks": [
                        {
                            "thesis_id": thesis.get("thesis_id", "thesis_1"),
                            "risk_title": "Demand downside risk",
                            "risk_description": "Demand volatility may reduce pricing support.",
                            "invalidation_condition": (
                                "Sustained demand contraction across key buyers."
                            ),
                            "severity": 4,
                            "related_chunk_ids": thesis.get("evidence_chunk_ids", [1]),
                        }
                    ]
                }
            else:
                theses = payload.get("theses", [])
                objections = payload.get("objections", [])
                risks = payload.get("risks", [])
                evidence_judge = payload.get("evidence_judge", {})
                data = {
                    "query": payload.get("query", ""),
                    "executive_summary": "Evidence points to a cautious constructive signal.",
                    "key_theses": theses,
                    "counterarguments": objections,
                    "evidence_gaps": evidence_judge.get("global_gaps", []),
                    "major_risks": risks,
                    "confidence_assessment": "weak confidence based on limited evidence",
                    "confidence_score": float(
                        evidence_judge.get("overall_sufficiency_score", 0.0)
                    ),
                    "suggested_next_questions": [
                        "Which additional primary sources can validate this?"
                    ],
                }

            return JsonProviderResponse(
                provider="deepseek",
                model=model or self.default_model,
                content_text=json.dumps(data, ensure_ascii=False),
                json_data=data,
                metadata=ProviderCallMetadata(
                    provider="deepseek",
                    model=model or self.default_model,
                    request_id="req-fake-1",
                    usage={"prompt_tokens": 10, "completion_tokens": 20},
                    finish_reason="stop",
                    response_ms=12.3,
                ),
                reasoning_content="internal reasoning trace",
            )

    monkeypatch.setattr(
        "packages.agents.provider.DeepSeekProviderClient",
        _FakeDeepSeekProviderClient,
    )


def test_resolve_provider_loads_deepseek_config(monkeypatch) -> None:
    captured = {}

    class _FakeDeepSeekProviderClient:
        def __init__(self, **kwargs):  # noqa: ANN003
            captured.update(kwargs)

        def generate_json(self, **kwargs):  # noqa: ANN003
            raise RuntimeError("not used")

        def generate_text(self, **kwargs):  # noqa: ANN003
            raise RuntimeError("not used")

    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "unit-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("DEEPSEEK_RESEARCH_MODEL", "deepseek-reasoner")
    monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", "33")
    monkeypatch.setenv("DEEPSEEK_MAX_RETRIES", "4")
    monkeypatch.setenv("DEEPSEEK_MAX_TOKENS", "888")
    monkeypatch.setenv("DEEPSEEK_MODEL_THESIS_BUILDER", "deepseek-reasoner")
    monkeypatch.setenv("DEEPSEEK_ENABLE_THINKING", "true")
    monkeypatch.setenv("DEEPSEEK_STORE_REASONING_CONTENT", "false")
    get_settings.cache_clear()

    monkeypatch.setattr(
        "packages.agents.provider.DeepSeekProviderClient",
        _FakeDeepSeekProviderClient,
    )
    resolution = resolve_provider(
        mode=ResearchMode.LLM,
        provider=ResearchProvider.DEEPSEEK,
        model=None,
        enable_thinking=None,
        debug_reasoning=False,
    )
    assert resolution.resolved_mode == ResearchMode.LLM
    assert resolution.resolved_provider == ResearchProvider.DEEPSEEK
    assert captured["api_key"] == "unit-key"
    assert captured["timeout_seconds"] == 33
    assert captured["max_retries"] == 4
    assert captured["max_tokens"] == 888
    assert resolution.resolved_step_models["thesis_builder"] == "deepseek-reasoner"
    assert resolution.resolved_step_models["supervisor_intake"] == "deepseek-reasoner"

    get_settings.cache_clear()


def test_resolve_provider_mock_mode() -> None:
    resolution = resolve_provider(mode=ResearchMode.MOCK)
    assert resolution.resolved_mode == ResearchMode.MOCK
    assert resolution.resolved_provider == ResearchProvider.MOCK


def test_research_api_llm_mode_and_reasoning_suppressed(monkeypatch, tmp_path: Path) -> None:
    _setup_research_db(monkeypatch, tmp_path)
    _install_fake_deepseek(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_STORE_REASONING_CONTENT", "false")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.post(
            "/research/analyze",
            json={
                "query": "lithium pricing power",
                "top_k": 6,
                "industry": "Energy Storage",
                "mode": "llm",
                "provider": "deepseek",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "succeeded"
        assert payload["mode"] == "llm"
        assert payload["provider"] == "deepseek"
        assert payload["theses"]
        assert (
            payload["provider_metadata"]["steps"]["thesis_builder"]["reasoning_available"]
            is True
        )
        assert (
            "reasoning_content"
            not in payload["provider_metadata"]["steps"]["thesis_builder"]
        )

        run_view = client.get(f"/research/runs/{payload['run_id']}")
        assert run_view.status_code == 200
        step_outputs = [step.get("output_json") or {} for step in run_view.json()["steps"]]
        provider_sections = [
            output.get("_provider") for output in step_outputs if "_provider" in output
        ]
        assert provider_sections
        assert all("reasoning_content" not in (item or {}) for item in provider_sections)

    get_settings.cache_clear()


def test_research_api_llm_step_model_routing(monkeypatch, tmp_path: Path) -> None:
    _setup_research_db(monkeypatch, tmp_path)
    _install_fake_deepseek(monkeypatch)
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.post(
            "/research/analyze",
            json={
                "query": "lithium pricing power",
                "top_k": 6,
                "industry": "Energy Storage",
                "mode": "llm",
                "provider": "deepseek",
                "model": "deepseek-chat",
                "step_models": {
                    "thesis_builder": "deepseek-reasoner",
                    "synthesize_memo": "deepseek-reasoner",
                },
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "succeeded"
        assert (
            payload["provider_metadata"]["steps"]["thesis_builder"]["model"]
            == "deepseek-reasoner"
        )
        assert (
            payload["provider_metadata"]["steps"]["synthesize_memo"]["model"]
            == "deepseek-reasoner"
        )
        assert (
            payload["provider_metadata"]["steps"]["supervisor_intake"]["model"]
            == "deepseek-chat"
        )

        run_view = client.get(f"/research/runs/{payload['run_id']}")
        assert run_view.status_code == 200
        run_input = run_view.json()["input_json"] or {}
        assert run_input["step_models_resolved"]["thesis_builder"] == "deepseek-reasoner"
        assert run_input["step_models_resolved"]["synthesize_memo"] == "deepseek-reasoner"

    get_settings.cache_clear()


def test_research_api_llm_mode_parse_failure_falls_back(monkeypatch, tmp_path: Path) -> None:
    _setup_research_db(monkeypatch, tmp_path)
    _install_fake_deepseek(monkeypatch, fail_parse=True)
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.post(
            "/research/analyze",
            json={
                "query": "lithium pricing power",
                "top_k": 6,
                "industry": "Energy Storage",
                "mode": "llm",
                "provider": "deepseek",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "succeeded"
        assert payload["theses"]
        thesis_step_meta = payload["provider_metadata"]["steps"]["thesis_builder"]
        assert thesis_step_meta["fallback"] == "deterministic"
        assert "ProviderParseError" in thesis_step_meta["fallback_reason"]


def test_research_api_llm_mode_supervisor_connection_fallback(
    monkeypatch, tmp_path: Path
) -> None:
    _setup_research_db(monkeypatch, tmp_path)
    _install_fake_deepseek(monkeypatch)
    get_settings.cache_clear()

    class _RetryingFakeProvider:
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
        ) -> JsonProviderResponse:
            if "Supervisor Agent" in system_prompt:
                raise ProviderRetryableError("Connection error.")
            data = {"theses": []}
            if "Evidence Judge Agent" in system_prompt:
                data = {
                    "coverage": [],
                    "overall_sufficiency_score": 0.0,
                    "overall_label": "insufficient",
                    "global_gaps": ["No thesis-level evidence available."],
                }
            elif "Risk Analyst Agent" in system_prompt:
                data = {"risks": []}
            elif "Opponent Agent" in system_prompt:
                data = {"objections": []}
            elif "Final Synthesizer Agent" in system_prompt:
                payload = json.loads(user_prompt)
                data = {
                    "query": payload.get("query", ""),
                    "executive_summary": "fallback summary",
                    "key_theses": [],
                    "counterarguments": [],
                    "evidence_gaps": ["fallback path"],
                    "major_risks": [],
                    "confidence_assessment": "insufficient",
                    "confidence_score": 0.0,
                    "suggested_next_questions": ["next"],
                }
            return JsonProviderResponse(
                provider="deepseek",
                model=model or self.default_model,
                content_text=json.dumps(data, ensure_ascii=False),
                json_data=data,
                metadata=ProviderCallMetadata(
                    provider="deepseek",
                    model=model or self.default_model,
                    request_id="req-fake-2",
                    usage={"prompt_tokens": 10, "completion_tokens": 20},
                    finish_reason="stop",
                    response_ms=12.3,
                ),
                reasoning_content=None,
            )

    monkeypatch.setattr(
        "packages.agents.provider.DeepSeekProviderClient",
        _RetryingFakeProvider,
    )

    with TestClient(app) as client:
        response = client.post(
            "/research/analyze",
            json={
                "query": "lithium pricing power",
                "top_k": 6,
                "industry": "Energy Storage",
                "mode": "llm",
                "provider": "deepseek",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "succeeded"
        supervisor_step_meta = payload["provider_metadata"]["steps"]["supervisor_intake"]
        assert supervisor_step_meta["fallback"] == "deterministic"
        assert "Connection error" in supervisor_step_meta["fallback_reason"]


def test_research_api_llm_mode_no_evidence(monkeypatch, tmp_path: Path) -> None:
    _setup_research_db(monkeypatch, tmp_path)
    _install_fake_deepseek(monkeypatch)
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.post(
            "/research/analyze",
            json={
                "query": "lithium pricing power",
                "top_k": 6,
                "industry": "Semiconductors",
                "mode": "llm",
                "provider": "deepseek",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "succeeded"
        assert payload["insufficient_evidence"] is True
        assert payload["theses"] == []


def test_research_api_rejects_invalid_step_model_key(monkeypatch, tmp_path: Path) -> None:
    _setup_research_db(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/research/analyze",
            json={
                "query": "lithium pricing power",
                "top_k": 6,
                "mode": "llm",
                "provider": "deepseek",
                "step_models": {"bad_step": "deepseek-chat"},
            },
        )
        assert response.status_code == 422
