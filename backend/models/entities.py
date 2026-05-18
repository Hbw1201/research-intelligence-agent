from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.types import EmbeddingType, json_type


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Group(TimestampMixin, Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)

    users: Mapped[list[User]] = relationship(back_populates="group")
    scores: Mapped[list[ItemScore]] = relationship(back_populates="group")
    feedback_entries: Mapped[list[Feedback]] = relationship(back_populates="group")
    digests: Mapped[list[Digest]] = relationship(back_populates="group")
    pushes: Mapped[list[Push]] = relationship(back_populates="group")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))

    group: Mapped[Group | None] = relationship(back_populates="users")
    scores: Mapped[list[ItemScore]] = relationship(back_populates="user")
    feedback_entries: Mapped[list[Feedback]] = relationship(back_populates="user")


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    url: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    items: Mapped[list[Item]] = relationship(back_populates="source")


class Item(TimestampMixin, Base):
    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("url", name="uq_items_url"),
        UniqueConstraint("content_hash", name="uq_items_content_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    authors: Mapped[list[str]] = mapped_column(json_type, default=list, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_text: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingType())

    source: Mapped[Source | None] = relationship(back_populates="items")
    scores: Mapped[list[ItemScore]] = relationship(back_populates="item")
    feedback_entries: Mapped[list[Feedback]] = relationship(back_populates="item")


class ItemScore(Base):
    __tablename__ = "item_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rank_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    item: Mapped[Item] = relationship(back_populates="scores")
    user: Mapped[User | None] = relationship(back_populates="scores")
    group: Mapped[Group | None] = relationship(back_populates="scores")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    item: Mapped[Item] = relationship(back_populates="feedback_entries")
    user: Mapped[User | None] = relationship(back_populates="feedback_entries")
    group: Mapped[Group | None] = relationship(back_populates="feedback_entries")


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    group: Mapped[Group | None] = relationship(back_populates="digests")
    pushes: Mapped[list[Push]] = relationship(back_populates="digest")


class Push(Base):
    __tablename__ = "pushes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    digest_id: Mapped[int | None] = mapped_column(ForeignKey("digests.id"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    channel: Mapped[str] = mapped_column(String(64), default="wecom", nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    digest: Mapped[Digest | None] = relationship(back_populates="pushes")
    group: Mapped[Group | None] = relationship(back_populates="pushes")
