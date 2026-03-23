from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from packages.core.config import get_settings

EXPECTED_TABLES = {
    "documents",
    "document_chunks",
    "citations",
    "themes",
    "companies",
    "events",
    "theses",
    "thesis_evidence_links",
    "thesis_risks",
    "content_assets",
    "runs",
    "run_steps",
    "memory_records",
    "content_feedback_events",
    "delivery_jobs",
    "delivery_job_items",
    "task_jobs",
    "task_attempts",
    "eval_runs",
    "eval_run_items",
}


def test_alembic_upgrade_head_creates_expected_tables(tmp_path, monkeypatch) -> None:
    db_path = Path(tmp_path) / "migration_sanity.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"

    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()

    cfg = Config("packages/db/alembic.ini")
    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())

    assert EXPECTED_TABLES.issubset(actual_tables)

    get_settings.cache_clear()
