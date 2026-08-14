from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.session import reset_db_session_state
from packages.themes.schemas import (
    ThemeCreateRequest,
    ThemeUpdateRequest,
)
from packages.themes.service import ThemeService, ThemeServiceError


def _setup_db(monkeypatch, tmp_path: Path) -> str:
    db_path = tmp_path / "themes.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()
    reset_db_session_state()
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return db_url


def _new_session(db_url: str) -> Session:
    return Session(create_engine(db_url))


class TestThemeSchemas:
    def test_create_request_valid(self) -> None:
        req = ThemeCreateRequest(name="新能源汽车", slug="new-energy-vehicles")
        assert req.name == "新能源汽车"
        assert req.slug == "new-energy-vehicles"
        assert req.description is None

    def test_create_request_with_description(self) -> None:
        req = ThemeCreateRequest(
            name="低空经济", slug="low-altitude-economy", description="低空经济产业链研究"
        )
        assert req.description == "低空经济产业链研究"

    def test_create_request_slug_must_match_pattern(self) -> None:
        with pytest.raises(ValueError):
            ThemeCreateRequest(name="Test", slug="INVALID SLUG")

    def test_create_request_name_required(self) -> None:
        with pytest.raises(ValueError):
            ThemeCreateRequest(name="", slug="test")  # type: ignore[arg-type]

    def test_update_request_partial(self) -> None:
        req = ThemeUpdateRequest(name="Updated Name")
        assert req.name == "Updated Name"
        assert req.description is None
        assert req.status is None

    def test_update_request_all_fields(self) -> None:
        req = ThemeUpdateRequest(name="Updated", description="New desc", status="monitoring")
        assert req.status == "monitoring"

    def test_update_request_invalid_status(self) -> None:
        with pytest.raises(ValueError):
            ThemeUpdateRequest(status="invalid")  # type: ignore[arg-type]


class TestThemeService:
    def test_create_and_list_themes(self, monkeypatch, tmp_path) -> None:
        db_url = _setup_db(monkeypatch, tmp_path)
        service = ThemeService(_new_session(db_url))
        created = service.create_theme(ThemeCreateRequest(name="人工智能", slug="ai"))
        assert created.id > 0
        assert created.name == "人工智能"
        assert created.slug == "ai"
        assert created.status == "active"
        themes = service.list_themes("all")
        assert any(t.id == created.id for t in themes)

    def test_create_duplicate_slug_fails(self, monkeypatch, tmp_path) -> None:
        db_url = _setup_db(monkeypatch, tmp_path)
        service = ThemeService(_new_session(db_url))
        service.create_theme(ThemeCreateRequest(name="AI", slug="ai-test"))
        with pytest.raises(ThemeServiceError, match="already exists"):
            service.create_theme(ThemeCreateRequest(name="AI 2", slug="ai-test"))

    def test_list_themes_filter_by_status(self, monkeypatch, tmp_path) -> None:
        db_url = _setup_db(monkeypatch, tmp_path)
        service = ThemeService(_new_session(db_url))
        service.create_theme(ThemeCreateRequest(name="Active Theme", slug="active-t"))
        created = service.create_theme(ThemeCreateRequest(name="Monitor Theme", slug="monitor-t"))
        service.update_theme(created.id, ThemeUpdateRequest(status="monitoring"))
        active = service.list_themes("active")
        monitoring = service.list_themes("monitoring")
        assert all(t.status == "active" for t in active)
        assert all(t.status == "monitoring" for t in monitoring)

    def test_get_theme_not_found(self, monkeypatch, tmp_path) -> None:
        db_url = _setup_db(monkeypatch, tmp_path)
        service = ThemeService(_new_session(db_url))
        assert service.get_theme(99999) is None

    def test_update_theme_not_found(self, monkeypatch, tmp_path) -> None:
        db_url = _setup_db(monkeypatch, tmp_path)
        service = ThemeService(_new_session(db_url))
        with pytest.raises(ThemeServiceError, match="not found"):
            service.update_theme(99999, ThemeUpdateRequest(name="Nope"))

    def test_update_theme_status_cycle(self, monkeypatch, tmp_path) -> None:
        db_url = _setup_db(monkeypatch, tmp_path)
        service = ThemeService(_new_session(db_url))
        created = service.create_theme(ThemeCreateRequest(name="Status Test", slug="status-test"))
        assert created.status == "active"
        monitoring = service.update_theme(created.id, ThemeUpdateRequest(status="monitoring"))
        assert monitoring.status == "monitoring"
        archived = service.update_theme(monitoring.id, ThemeUpdateRequest(status="archived"))
        assert archived.status == "archived"

    def test_list_all_includes_all_statuses(self, monkeypatch, tmp_path) -> None:
        db_url = _setup_db(monkeypatch, tmp_path)
        service = ThemeService(_new_session(db_url))
        service.create_theme(ThemeCreateRequest(name="T1", slug="t1"))
        service.create_theme(ThemeCreateRequest(name="T2", slug="t2"))
        themes = service.list_themes("all")
        assert len(themes) >= 2
