from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.session import get_engine, reset_db_session_state
from packages.sources.adapters import EIAAdapter, SecEdgarAdapter, WorldBankAdapter
from packages.tasks.worker import TaskWorker


def _setup_ops_api_db(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "ops_registry_api.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str((tmp_path / "raw").as_posix()))
    monkeypatch.setenv("DELIVERY_EXPORT_DIR", str((tmp_path / "exports").as_posix()))
    monkeypatch.setenv("TASK_RETRY_BACKOFF_SECONDS", "0")
    get_settings.cache_clear()
    reset_db_session_state()
    engine = get_engine()
    Base.metadata.create_all(engine)


def test_registry_ops_and_smoke_eval_api(monkeypatch, tmp_path: Path) -> None:
    _setup_ops_api_db(monkeypatch, tmp_path)

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

    with TestClient(app) as client:
        templates = client.get("/registry/templates")
        assert templates.status_code == 200
        templates_payload = templates.json()
        assert len(templates_payload["templates"]) >= 3

        policies = client.get("/registry/policies")
        assert policies.status_code == 200
        policies_payload = policies.json()
        assert any(
            item["policy_id"] == "content_guardrail_v1"
            for item in policies_payload["policies"]
        )

        smoke = client.post(
            "/evals/run-smoke",
            json={
                "query": "lithium pricing outlook",
                "top_k": 6,
                "bootstrap_sample": True,
            },
        )
        assert smoke.status_code == 200
        smoke_payload = smoke.json()
        assert smoke_payload["eval_run_id"] > 0
        assert smoke_payload["summary"]["case_count"] > 0

        eval_run = client.get(f"/evals/runs/{smoke_payload['eval_run_id']}")
        assert eval_run.status_code == 200
        eval_payload = eval_run.json()
        assert len(eval_payload["items"]) > 0

        source_smoke = client.post("/evals/run-source-smoke", json={})
        assert source_smoke.status_code == 200
        source_smoke_payload = source_smoke.json()
        assert source_smoke_payload["eval_run_id"] > 0
        assert source_smoke_payload["scenario_count"] >= 4

        source_eval_run = client.get(
            f"/evals/source-runs/{source_smoke_payload['eval_run_id']}"
        )
        assert source_eval_run.status_code == 200
        assert source_eval_run.json()["target_type"] == "source_smoke"

        bad_task = client.post(
            "/tasks/content/generate",
            json={
                "idempotency_key": "ops-bad-task-1",
                "max_attempts": 1,
                "request": {
                    "research_run_id": 999999,
                    "content_types": ["wechat_article"],
                    "mode": "mock",
                },
            },
        )
        assert bad_task.status_code == 200
        assert (
            TaskWorker(worker_id="ops-api-test-worker", poll_interval_seconds=1).run_once()
            is True
        )

        readiness = client.get("/ops/readiness-report")
        assert readiness.status_code == 200
        readiness_payload = readiness.json()
        assert readiness_payload["status"] in {"ready", "degraded"}
        assert "database" in readiness_payload["checks"]
        assert "failure_counts" in readiness_payload

        recent_failures = client.get("/ops/failures/recent")
        assert recent_failures.status_code == 200
        failures_payload = recent_failures.json()
        assert any(item["failure_type"] == "task_job" for item in failures_payload["items"])

        sources_perf = client.get("/ops/sources/performance")
        assert sources_perf.status_code == 200
        perf_payload = sources_perf.json()
        assert "items" in perf_payload
