from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from backend.config import get_settings
from backend.models import Base


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Create the async database engine lazily."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create the async session factory lazily."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a database session for FastAPI dependencies."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def init_db(engine: AsyncEngine | None = None) -> None:
    """Initialize database extensions and tables.

    This is intentionally explicit instead of running during FastAPI startup so
    lightweight endpoints such as /health do not require a database connection.
    """
    active_engine = engine or get_engine()
    async with active_engine.begin() as connection:
        if active_engine.url.get_backend_name() == "postgresql":
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.create_all)
