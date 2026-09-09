from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.agents.service import ResearchWorkflowService
from packages.core.config import get_settings
from packages.core.run_log import CompactRunLogger
from packages.db.base import Base
from packages.db.models import Document, SourceType
from packages.db.session import reset_db_session_state
from packages.ingestion.service import IngestionService

UTC = timezone(timedelta(0))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_compact_run_logger_names_file_and_compacts_payload(monkeypatch, tmp_path: Path) -> None:
    log_dir = tmp_path / "run_logs"
    monkeypatch.setenv("SYSTEM_RUN_LOG_ENABLED", "true")
    monkeypatch.setenv("SYSTEM_RUN_LOG_DIR", str(log_dir.as_posix()))
    monkeypatch.setenv("SYSTEM_RUN_LOG_MAX_VALUE_CHARS", "24")
    monkeypatch.setenv("SYSTEM_RUN_LOG_MAX_ITEMS", "3")
    get_settings.cache_clear()

    logger = CompactRunLogger(
        task_name="Research Analyze / Demo",
        run_id=42,
        started_at=datetime(2026, 4, 26, 1, 2, 3, tzinfo=UTC),
    )
    logger.start(
        input_summary={
            "query": "x" * 60,
            "password": "secret-value",
            "items": [1, 2, 3, 4],
        },
        decision_summary=["compact input", "redact sensitive fields"],
    )
    logger.finish(
        status="succeeded",
        output_summary={"token": "secret-token", "answer": "done"},
    )

    assert logger.path is not None
    assert logger.path.name == "20260426T010203Z_research-analyze-demo_run-42.jsonl"
    events = _read_jsonl(logger.path)
    assert [item["event"] for item in events] == ["start", "finish"]
    start_input = events[0]["input"]
    assert isinstance(start_input, dict)
    assert start_input["password"] == "<redacted>"
    assert "truncated chars=60" in start_input["query"]
    assert start_input["items"][-1] == {"_truncated_items": 1}
    finish_output = events[1]["output"]
    assert isinstance(finish_output, dict)
    assert finish_output["token"] == "<redacted>"


def test_research_workflow_writes_compact_run_log(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "research_with_log.db"
    raw_path = tmp_path / "raw"
    log_dir = tmp_path / "run_logs"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str(raw_path.as_posix()))
    monkeypatch.setenv("SYSTEM_RUN_LOG_ENABLED", "true")
    monkeypatch.setenv("SYSTEM_RUN_LOG_DIR", str(log_dir.as_posix()))
    monkeypatch.setenv("SYSTEM_RUN_LOG_MAX_VALUE_CHARS", "80")
    monkeypatch.setenv("SYSTEM_RUN_LOG_MAX_ITEMS", "6")
    get_settings.cache_clear()
    reset_db_session_state()

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        ingestion = IngestionService(session, max_chunk_chars=260).ingest_uploaded_file(
            file_name="seed.md",
            file_bytes=(
                b"# Battery Pricing\n\n## Signal\n"
                b"Lithium processing constraints keep contract prices elevated."
            ),
            media_type="text/markdown",
            source_type=SourceType.REPORT,
        )
        document = session.get(Document, ingestion.document_id)
        document.industry = "Energy Storage"
        session.add(document)
        session.commit()

        result = ResearchWorkflowService(session).analyze(
            ResearchAnalyzeRequest(
                query="lithium pricing power",
                top_k=4,
                industry="Energy Storage",
                mode="mock",
            )
        )

    log_files = list(log_dir.glob("*_research-analyze_run-*.jsonl"))
    assert len(log_files) == 1
    events = _read_jsonl(log_files[0])
    event_names = [item["event"] for item in events]
    assert event_names[0] == "start"
    assert event_names[-1] == "finish"
    assert "step" in event_names
    step_names = {
        item.get("meta", {}).get("step_name")
        for item in events
        if isinstance(item.get("meta"), dict)
    }
    assert {"retrieve_evidence", "thesis_builder", "synthesize_memo"} <= step_names
    assert events[-1]["run_id"] == result.run_id
    serialized = json.dumps(events, ensure_ascii=False)
    assert len(serialized) < 20000
    assert '"chars"' in serialized
    assert '"preview"' in serialized
