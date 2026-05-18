from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import Base, Digest, Feedback, Group, Item, ItemScore, Push, Source, User


def make_item(url: str = "https://example.org/item/1", content_hash: str = "hash-1") -> Item:
    return Item(
        title="Example paper",
        abstract="A short abstract.",
        url=url,
        source_name="arxiv",
        source_type="paper",
        item_type="paper",
        authors=["Ada Lovelace"],
        published_at=datetime(2026, 5, 18, tzinfo=timezone.utc),
        raw_text="Example paper\nA short abstract.",
        content_hash=content_hash,
    )


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as active_session:
        yield active_session


def test_model_imports() -> None:
    assert User.__tablename__ == "users"
    assert Group.__tablename__ == "groups"
    assert Source.__tablename__ == "sources"
    assert Item.__tablename__ == "items"
    assert ItemScore.__tablename__ == "item_scores"
    assert Feedback.__tablename__ == "feedback"
    assert Digest.__tablename__ == "digests"
    assert Push.__tablename__ == "pushes"


def test_item_creation(session: Session) -> None:
    item = make_item()
    session.add(item)
    session.commit()

    assert item.id is not None
    assert item.title == "Example paper"
    assert item.authors == ["Ada Lovelace"]
    assert item.created_at is not None
    assert item.updated_at is not None


def test_duplicate_item_url_constraint(session: Session) -> None:
    session.add(make_item(url="https://example.org/duplicate", content_hash="hash-1"))
    session.commit()

    session.add(make_item(url="https://example.org/duplicate", content_hash="hash-2"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_duplicate_item_content_hash_constraint(session: Session) -> None:
    session.add(make_item(url="https://example.org/item/1", content_hash="same-hash"))
    session.commit()

    session.add(make_item(url="https://example.org/item/2", content_hash="same-hash"))
    with pytest.raises(IntegrityError):
        session.commit()
