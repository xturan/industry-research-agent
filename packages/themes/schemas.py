from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ThemeCreateRequest(BaseModel):
    """Request to create a new research/investment theme."""

    name: str = Field(min_length=1, max_length=255, description="Theme display name")
    slug: str = Field(
        min_length=1,
        max_length=255,
        pattern=r"^[a-z0-9\-]+$",
        description="URL-safe unique identifier (lowercase, digits, hyphens)",
    )
    description: str | None = Field(
        default=None, max_length=2000, description="Optional theme description"
    )


class ThemeUpdateRequest(BaseModel):
    """Request to update an existing theme. All fields optional."""

    name: str | None = Field(
        default=None, min_length=1, max_length=255, description="Updated theme name"
    )
    description: str | None = Field(
        default=None, max_length=2000, description="Updated description"
    )
    status: Literal["active", "monitoring", "archived"] | None = Field(
        default=None, description="Updated status"
    )


class ThemeResponse(BaseModel):
    """Theme data returned by the API."""

    id: int
    name: str
    slug: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


ThemeStatusFilter = Literal["active", "monitoring", "archived", "all"]
