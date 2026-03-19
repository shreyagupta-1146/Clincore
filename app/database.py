"""
app/database.py
───────────────
Async SQLAlchemy setup.

- `engine`         — async engine connected to PostgreSQL
- `AsyncSession`   — session factory for dependency injection
- `Base`           — declarative base that all models inherit from
- `get_db()`       — FastAPI dependency that yields a DB session per request
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from app.config import settings


# ── Engine ────────────────────────────────────────────────────────────────────
# pool_pre_ping=True: tests connections before using them (handles dropped connections)
# pool_size=10: number of persistent connections
# max_overflow=20: extra connections allowed when pool is full
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,       # SQL logging in development
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# ── Session Factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,    # objects remain accessible after commit
)


# ── Declarative Base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── FastAPI Dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncSession:
    """
    Yields a database session for each request.
    Automatically closes on request completion (or error).

    Usage in routes:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Startup: Create all tables ────────────────────────────────────────────────
async def create_tables():
    """Called on app startup to create all tables that don't exist yet."""
    async with engine.begin() as conn:
        # Set the encryption key for this session (used by pgcrypto functions)
        await conn.execute(
            text(f"SET app.encryption_key = '{settings.DB_ENCRYPTION_KEY}'")
        )
        from app.models import user, folder, chat, message, share, audit  # noqa
        await conn.run_sync(Base.metadata.create_all)
