"""Alembic: async engine, metadata app.db.models'dan. URL DATABASE_URL environment'dan olinadi."""
import asyncio

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.db.models import Base

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    """Faqat bizning jadvallar: PostGIS/tiger geocoder kabi tashqi jadvallarga tegmaymiz."""
    if reflected and compare_to is None:
        return False
    return alembic_helpers.include_object(obj, name, type_, reflected, compare_to)


def _configure(connection=None, url=None):
    context.configure(
        connection=connection,
        url=url,
        target_metadata=target_metadata,
        include_object=include_object,
        process_revision_directives=alembic_helpers.writer,
        render_item=alembic_helpers.render_item,
        compare_type=True,
    )


def run_migrations_offline():
    _configure(url=get_settings().database_url)
    with context.begin_transaction():
        context.run_migrations()


def _do_run(connection):
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as conn:
        await conn.run_sync(_do_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
