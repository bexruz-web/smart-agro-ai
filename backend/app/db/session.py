"""Async SQLAlchemy engine va sessiya fabrikasi."""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_engine = None
_sessionmaker = None


def get_engine(null_pool: bool = False):
    """API bitta umumiy pool ishlatadi; Celery worker'larida har bir vazifa o'z event loop'ida
    ishlagani uchun NullPool kerak (asyncpg ulanishlari loop'lar orasida bo'linmaydi)."""
    global _engine, _sessionmaker
    if _engine is None:
        kwargs = {"poolclass": NullPool} if null_pool else {"pool_size": 10, "max_overflow": 10}
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True, **kwargs)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        get_engine()
    return _sessionmaker


def reset_engine() -> None:
    """Testlar va worker'lar uchun: keyingi chaqiruvda yangi engine yaratiladi."""
    global _engine, _sessionmaker
    _engine = None
    _sessionmaker = None


async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session
