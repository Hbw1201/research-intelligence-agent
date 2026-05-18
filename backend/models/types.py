from __future__ import annotations

from typing import Any

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - production deps include pgvector.
    Vector = None  # type: ignore[assignment]


json_type = JSON().with_variant(JSONB, "postgresql")


class EmbeddingType(TypeDecorator[list[float] | None]):
    """Use pgvector on PostgreSQL and JSON elsewhere for lightweight tests."""

    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int = 1536) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql" and Vector is not None:
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())
