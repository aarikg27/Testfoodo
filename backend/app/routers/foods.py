from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from ..database import get_db
from ..models import (
    DiningHall,
    Food,
    FoodLabel,
    MenuAvailability,
    ScrapeRun,
    Station,
)
from ..schemas import (
    FoodResponse,
    HallResponse,
    PaginatedFoods,
    ScrapeStatusResponse,
)

router = APIRouter(tags=["menu"])
EASTERN = ZoneInfo("America/New_York")


def eastern_today() -> date:
    return datetime.now(EASTERN).date()


def _label_groups(food: Food) -> tuple[list[str], list[str], list[str]]:
    labels = sorted({label.name for label in food.labels})
    dietary = sorted({label.name for label in food.labels if label.kind == "dietary"})
    allergens = sorted(
        {
            label.name
            for label in food.labels
            if label.kind in {"allergen", "attribute"}
        }
    )
    return labels, dietary, allergens


def availability_to_response(item: MenuAvailability) -> FoodResponse:
    food = item.food
    labels, dietary, allergens = _label_groups(food)
    return FoodResponse(
        id=food.id,
        availability_id=item.id,
        source_key=food.source_key,
        name=food.name,
        serving_size=food.serving_size,
        calories=float(food.calories or 0),
        protein_g=float(food.protein_g or 0),
        carbs_g=float(food.carbs_g or 0),
        fat_g=float(food.fat_g or 0),
        saturated_fat_g=food.saturated_fat_g,
        fiber_g=food.fiber_g,
        sugar_g=food.sugar_g,
        sodium_mg=food.sodium_mg,
        ingredients=food.ingredients,
        source_url=food.source_url,
        hall_id=item.station.hall.id,
        hall_name=item.station.hall.name,
        hall_slug=item.station.hall.slug,
        station=item.station.name,
        menu_date=item.menu_date,
        meal_period=item.meal_period,
        labels=labels,
        dietary_labels=dietary,
        allergens=allergens,
        nutrition_updated_at=food.nutrition_updated_at,
    )


def menu_statement(
    *,
    menu_date: date,
    hall: str | None = None,
    meal: str | None = None,
    station: str | None = None,
    search: str | None = None,
    dietary: Iterable[str] = (),
    excluded_labels: Iterable[str] = (),
):
    statement = (
        select(MenuAvailability)
        .join(MenuAvailability.food)
        .join(MenuAvailability.station)
        .join(Station.hall)
        .where(MenuAvailability.menu_date == menu_date)
        .options(
            joinedload(MenuAvailability.station).joinedload(Station.hall),
            joinedload(MenuAvailability.food).selectinload(Food.labels),
        )
    )
    if hall:
        hall_value = hall.strip().lower()
        statement = statement.where(
            or_(
                func.lower(DiningHall.slug) == hall_value,
                func.lower(DiningHall.name) == hall_value,
                DiningHall.source_id == hall,
                func.lower(DiningHall.name).like(f"%{hall_value}%"),
            )
        )
    if meal:
        statement = statement.where(func.lower(MenuAvailability.meal_period) == meal.lower())
    if station:
        statement = statement.where(func.lower(Station.name).like(f"%{station.lower()}%"))
    if search:
        statement = statement.where(func.lower(Food.name).like(f"%{search.lower()}%"))
    for label in {item.strip().lower() for item in dietary if item.strip()}:
        statement = statement.where(
            exists(
                select(FoodLabel.food_id).where(
                    FoodLabel.food_id == Food.id,
                    FoodLabel.name == label,
                    FoodLabel.kind == "dietary",
                )
            )
        )
    excluded = {item.strip().lower() for item in excluded_labels if item.strip()}
    if excluded:
        statement = statement.where(
            not_(
                exists(
                    select(FoodLabel.food_id).where(
                        FoodLabel.food_id == Food.id,
                        FoodLabel.name.in_(excluded),
                    )
                )
            )
        )
    return statement.order_by(Station.name, Food.name)


@router.get("/halls", response_model=list[HallResponse])
async def list_halls(
    menu_date: date = Query(default_factory=eastern_today, alias="date"),
    db: AsyncSession = Depends(get_db),
):
    count_subquery = (
        select(Station.hall_id, func.count(MenuAvailability.id).label("item_count"))
        .join(MenuAvailability, MenuAvailability.station_id == Station.id)
        .where(MenuAvailability.menu_date == menu_date)
        .group_by(Station.hall_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(DiningHall, func.coalesce(count_subquery.c.item_count, 0))
            .outerjoin(count_subquery, count_subquery.c.hall_id == DiningHall.id)
            .where(DiningHall.is_active.is_(True))
            .order_by(DiningHall.id)
        )
    ).all()
    return [
        HallResponse(
            id=hall.id,
            source_id=hall.source_id,
            slug=hall.slug,
            name=hall.name,
            item_count=count,
        )
        for hall, count in rows
    ]


@router.get("/foods", response_model=PaginatedFoods)
async def list_foods(
    hall: str | None = None,
    menu_date: date = Query(default_factory=eastern_today, alias="date"),
    meal: str | None = None,
    station: str | None = None,
    search: str | None = None,
    dietary: list[str] = Query(default=[]),
    exclude: list[str] = Query(default=[]),
    limit: int = Query(default=300, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    statement = menu_statement(
        menu_date=menu_date,
        hall=hall,
        meal=meal,
        station=station,
        search=search,
        dietary=dietary,
        excluded_labels=exclude,
    )
    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    total = int((await db.scalar(count_statement)) or 0)
    items = (await db.scalars(statement.offset(offset).limit(limit))).unique().all()

    day_start = datetime.combine(menu_date, time.min, tzinfo=EASTERN).astimezone(timezone.utc)
    day_end = datetime.combine(menu_date, time.max, tzinfo=EASTERN).astimezone(timezone.utc)
    last_scraped = await db.scalar(
        select(func.max(MenuAvailability.scraped_at)).where(
            MenuAvailability.menu_date == menu_date,
            MenuAvailability.scraped_at >= day_start,
            MenuAvailability.scraped_at <= day_end,
        )
    )
    if last_scraped is None:
        last_scraped = await db.scalar(
            select(func.max(MenuAvailability.scraped_at)).where(
                MenuAvailability.menu_date == menu_date
            )
        )

    return PaginatedFoods(
        items=[availability_to_response(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
        menu_date=menu_date,
        last_scraped_at=last_scraped,
    )


@router.get("/foods/{food_id}", response_model=FoodResponse)
async def get_food(
    food_id: uuid.UUID,
    menu_date: date = Query(default_factory=eastern_today, alias="date"),
    db: AsyncSession = Depends(get_db),
):
    statement = menu_statement(menu_date=menu_date).where(
        Food.id == food_id
    )
    item = await db.scalar(statement.limit(1))
    if not item:
        raise HTTPException(status_code=404, detail="Food is not available on this date")
    return availability_to_response(item)


@router.get("/scrape-status", response_model=ScrapeStatusResponse)
async def scrape_status(db: AsyncSession = Depends(get_db)):
    run = await db.scalar(select(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(1))
    if not run:
        return ScrapeStatusResponse(status="never_run")
    return ScrapeStatusResponse(
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        menu_items_found=run.menu_items_found,
        foods_refreshed=run.foods_refreshed,
        errors=run.errors,
    )
