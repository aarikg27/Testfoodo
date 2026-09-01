from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import sqlite

from app.routers.foods import (
    current_meal_period,
    eastern_today,
    effective_meal,
    menu_statement,
    require_current_or_future,
)


def test_past_menu_dates_are_rejected():
    with pytest.raises(HTTPException) as error:
        require_current_or_future(eastern_today() - timedelta(days=1))

    assert error.value.status_code == 422


def test_current_and_future_menu_dates_are_allowed():
    require_current_or_future(eastern_today())
    require_current_or_future(eastern_today() + timedelta(days=1))


def test_today_is_limited_to_the_current_meal_period():
    current = current_meal_period()
    other = next(meal for meal in ("Breakfast", "Lunch", "Dinner") if meal != current)

    assert effective_meal(eastern_today()) == current
    with pytest.raises(HTTPException):
        effective_meal(eastern_today(), other)


def test_station_filter_uses_an_exact_case_insensitive_match():
    statement = menu_statement(
        menu_date=eastern_today(), station="Joe's Grill"
    )
    sql = str(
        statement.compile(
            dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}
        )
    )

    assert "lower(stations.name) = 'joe''s grill'" in sql.lower()
    assert "lower(stations.name) like" not in sql.lower()
