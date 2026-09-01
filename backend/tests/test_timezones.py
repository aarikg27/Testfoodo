from datetime import datetime, timedelta, timezone

from app.routers.foods import as_utc
from app.schemas import PaginatedFoods


def test_naive_database_timestamp_is_serialized_as_utc():
    timestamp = as_utc(datetime(2026, 9, 1, 2, 21))
    response = PaginatedFoods(
        items=[],
        total=0,
        limit=10,
        offset=0,
        menu_date=datetime(2026, 8, 31).date(),
        last_scraped_at=timestamp,
    )

    assert response.model_dump_json().endswith('"last_scraped_at":"2026-09-01T02:21:00Z"}')


def test_aware_database_timestamp_is_converted_to_utc():
    eastern = timezone(timedelta(hours=-4))
    timestamp = as_utc(datetime(2026, 8, 31, 22, 21, tzinfo=eastern))

    assert timestamp == datetime(2026, 9, 1, 2, 21, tzinfo=timezone.utc)
