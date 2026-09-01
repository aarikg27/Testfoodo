from __future__ import annotations

import asyncio

from sqlalchemy import select

from .database import SessionLocal, engine
from .models import Base, DiningHall

DEFAULT_HALLS = [
    {"source_id": "16", "slug": "south-campus", "name": "South Campus Dining Hall"},
    {"source_id": "19", "slug": "yahentamitsi", "name": "Yahentamitsi Dining Hall"},
    {"source_id": "51", "slug": "251-north", "name": "251 North"},
]


async def initialize_database() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        existing = {
            row.source_id: row
            for row in (await session.scalars(select(DiningHall))).all()
        }
        for data in DEFAULT_HALLS:
            hall = existing.get(data["source_id"])
            if hall:
                hall.slug = data["slug"]
                hall.name = data["name"]
                hall.is_active = True
            else:
                session.add(DiningHall(**data))
        await session.commit()


if __name__ == "__main__":
    asyncio.run(initialize_database())

