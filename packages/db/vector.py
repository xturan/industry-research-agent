from __future__ import annotations

from typing import Any

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - exercised implicitly in non-pgvector envs
    Vector = None


class VectorType(TypeDecorator[list[float] | None]):
    """Use native pgvector on PostgreSQL and a portable fallback elsewhere."""

    cache_ok = True
    impl = JSON

    def __init__(self, dimensions: int):
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == "postgresql" and Vector is not None:
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: list[float] | None, dialect) -> Any:  # type: ignore[override]
        if value is None:
            return None
        if dialect.name == "postgresql" and Vector is not None:
            return [float(item) for item in value]
        return [float(item) for item in value]

    def process_result_value(self, value: Any, dialect) -> list[float] | None:  # type: ignore[override]
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return [float(item) for item in value]
        return value


def vector_column(dimensions: int) -> VectorType:
    return VectorType(dimensions=dimensions)
