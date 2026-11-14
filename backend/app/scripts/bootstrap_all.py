"""Barcha dalalar uchun iqlim tarixi, prognoz va birinchi tahlilni ishga tushiradi (worker ichida).

python -m app.scripts.bootstrap_all
"""
import asyncio

from sqlalchemy import select

from app.db.models import Field
from app.db.session import get_sessionmaker
from app.workers.tasks import bootstrap_field


async def field_ids() -> list[int]:
    async with get_sessionmaker()() as s:
        return list((await s.execute(select(Field.id).order_by(Field.id))).scalars())


if __name__ == "__main__":
    for fid in asyncio.run(field_ids()):
        print(fid, bootstrap_field(fid))
