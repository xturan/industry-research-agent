from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.db.models import Theme, ThemeStatus
from packages.themes.schemas import (
    ThemeCreateRequest,
    ThemeResponse,
    ThemeStatusFilter,
    ThemeUpdateRequest,
)

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc  # noqa: UP017


class ThemeServiceError(Exception):
    """Domain-level theme operation error."""


class ThemeService:
    """CRUD service for research/investment themes."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_theme(self, request: ThemeCreateRequest) -> ThemeResponse:
        existing = self.session.execute(
            select(Theme).where(Theme.slug == request.slug.strip().lower())
        ).scalar_one_or_none()
        if existing is not None:
            raise ThemeServiceError(f"Theme with slug '{request.slug}' already exists.")

        theme = Theme(
            name=request.name.strip(),
            slug=request.slug.strip().lower(),
            description=request.description.strip() if request.description else None,
            status=ThemeStatus.ACTIVE,
        )
        self.session.add(theme)
        self.session.commit()
        self.session.refresh(theme)
        return self._to_response(theme)

    def list_themes(self, status_filter: ThemeStatusFilter = "all") -> list[ThemeResponse]:
        stmt = select(Theme).order_by(Theme.name)
        if status_filter != "all":
            try:
                theme_status = ThemeStatus(status_filter)
            except ValueError as exc:
                raise ThemeServiceError(f"Invalid status filter: '{status_filter}'") from exc
            stmt = stmt.where(Theme.status == theme_status)
        rows = self.session.execute(stmt).scalars().all()
        return [self._to_response(row) for row in rows]

    def get_theme(self, theme_id: int) -> ThemeResponse | None:
        theme = self.session.get(Theme, theme_id)
        if theme is None:
            return None
        return self._to_response(theme)

    def update_theme(self, theme_id: int, request: ThemeUpdateRequest) -> ThemeResponse:
        theme = self.session.get(Theme, theme_id)
        if theme is None:
            raise ThemeServiceError(f"Theme {theme_id} not found.")

        if request.name is not None:
            theme.name = request.name.strip()
        if request.description is not None:
            theme.description = request.description.strip() if request.description else None
        if request.status is not None:
            try:
                theme.status = ThemeStatus(request.status)
            except ValueError as exc:
                raise ThemeServiceError(f"Invalid status: '{request.status}'") from exc

        self.session.add(theme)
        self.session.commit()
        self.session.refresh(theme)
        return self._to_response(theme)

    @staticmethod
    def _to_response(theme: Theme) -> ThemeResponse:
        return ThemeResponse(
            id=theme.id,
            name=theme.name,
            slug=theme.slug,
            description=theme.description,
            status=theme.status.value,
            created_at=theme.created_at,
            updated_at=theme.updated_at,
        )
