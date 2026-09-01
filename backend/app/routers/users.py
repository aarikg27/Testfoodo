from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from ..auth import get_current_user
from ..database import get_db
from ..models import (
    DailyGoal,
    DiningHall,
    FavoriteFood,
    Food,
    FoodLog,
    MenuAvailability,
    SavedMeal,
    SavedMealItem,
    Station,
    User,
    UserPreference,
)
from ..schemas import (
    BodyProfile,
    FavoriteCreate,
    FavoriteResponse,
    FoodLogCreate,
    FoodLogResponse,
    FoodLogUpdate,
    GoalResponse,
    GoalUpdate,
    PreferenceResponse,
    PreferenceUpdate,
    SavedMealCreate,
    SavedMealItemResponse,
    SavedMealResponse,
)

router = APIRouter(prefix="/users/me", tags=["user data"])
EASTERN = ZoneInfo("America/New_York")
ALLOWED_DIETARY = {"vegan", "vegetarian", "halal"}
ALLOWED_EXCLUSIONS = {
    "alcohol",
    "coconut",
    "dairy",
    "eggs",
    "fish",
    "gluten",
    "nuts",
    "pea_protein",
    "pork",
    "sesame",
    "shellfish",
    "soy",
}


def date_bounds(start: date, end: date | None = None) -> tuple[datetime, datetime]:
    end = end or start
    lower = datetime.combine(start, time.min, tzinfo=EASTERN).astimezone(timezone.utc)
    upper = datetime.combine(end, time.max, tzinfo=EASTERN).astimezone(timezone.utc)
    return lower, upper


async def get_preferences(db: AsyncSession, user_id: uuid.UUID) -> UserPreference:
    preferences = await db.get(UserPreference, user_id)
    if preferences is None:
        preferences = UserPreference(user_id=user_id)
        db.add(preferences)
        await db.flush()
    return preferences


def preferences_response(preferences: UserPreference) -> PreferenceResponse:
    return PreferenceResponse(
        calorie_goal=preferences.calorie_goal,
        protein_goal_g=preferences.protein_goal_g,
        carbs_goal_g=preferences.carbs_goal_g,
        fat_goal_g=preferences.fat_goal_g,
        dietary_preferences=preferences.dietary_preferences or [],
        excluded_labels=preferences.excluded_labels or [],
        favorite_hall_id=preferences.favorite_hall_id,
        profile=BodyProfile(**(preferences.profile_data or {})),
    )


@router.get("/goals", response_model=GoalResponse)
async def get_goals(
    goal_date: date = Query(alias="date"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    override = await db.scalar(
        select(DailyGoal).where(
            DailyGoal.user_id == user.id, DailyGoal.goal_date == goal_date
        )
    )
    if override:
        return GoalResponse(
            goal_date=goal_date,
            source="daily_override",
            calorie_goal=override.calorie_goal,
            protein_goal_g=override.protein_goal_g,
            carbs_goal_g=override.carbs_goal_g,
            fat_goal_g=override.fat_goal_g,
        )
    preferences = await get_preferences(db, user.id)
    return GoalResponse(
        goal_date=goal_date,
        source="default",
        calorie_goal=preferences.calorie_goal,
        protein_goal_g=preferences.protein_goal_g,
        carbs_goal_g=preferences.carbs_goal_g,
        fat_goal_g=preferences.fat_goal_g,
    )


@router.put("/goals", response_model=GoalResponse)
async def update_goals(
    payload: GoalUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    override = await db.scalar(
        select(DailyGoal).where(
            DailyGoal.user_id == user.id, DailyGoal.goal_date == payload.goal_date
        )
    )
    values = payload.model_dump(exclude={"goal_date", "save_as_default"})
    if override:
        for key, value in values.items():
            setattr(override, key, value)
    else:
        override = DailyGoal(user_id=user.id, goal_date=payload.goal_date, **values)
        db.add(override)

    if payload.save_as_default:
        preferences = await get_preferences(db, user.id)
        for key, value in values.items():
            setattr(preferences, key, value)
    await db.commit()
    return GoalResponse(
        goal_date=payload.goal_date,
        source="daily_override",
        **values,
    )


@router.get("/preferences", response_model=PreferenceResponse)
async def read_preferences(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return preferences_response(await get_preferences(db, user.id))


@router.put("/preferences", response_model=PreferenceResponse)
async def update_preferences(
    payload: PreferenceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dietary = sorted({item.lower() for item in payload.dietary_preferences})
    excluded = sorted({item.lower() for item in payload.excluded_labels})
    if not set(dietary).issubset(ALLOWED_DIETARY):
        raise HTTPException(status_code=422, detail="Unknown dietary preference")
    if not set(excluded).issubset(ALLOWED_EXCLUSIONS):
        raise HTTPException(status_code=422, detail="Unknown exclusion label")
    if payload.favorite_hall_id is not None and not await db.get(
        DiningHall, payload.favorite_hall_id
    ):
        raise HTTPException(status_code=422, detail="Unknown dining hall")

    preferences = await get_preferences(db, user.id)
    preferences.dietary_preferences = dietary
    preferences.excluded_labels = excluded
    preferences.favorite_hall_id = payload.favorite_hall_id
    preferences.profile_data = payload.profile.model_dump()
    await db.commit()
    return preferences_response(preferences)


@router.get("/logs", response_model=list[FoodLogResponse])
async def list_logs(
    date_from: date,
    date_to: date | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lower, upper = date_bounds(date_from, date_to)
    return (
        await db.scalars(
            select(FoodLog)
            .where(
                FoodLog.user_id == user.id,
                FoodLog.eaten_at >= lower,
                FoodLog.eaten_at <= upper,
            )
            .order_by(FoodLog.eaten_at.desc())
        )
    ).all()


@router.post("/logs", response_model=FoodLogResponse, status_code=status.HTTP_201_CREATED)
async def create_log(
    payload: FoodLogCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.availability_id is not None:
        availability = await db.scalar(
            select(MenuAvailability)
            .where(MenuAvailability.id == payload.availability_id)
            .options(joinedload(MenuAvailability.food))
        )
        if not availability:
            raise HTTPException(status_code=404, detail="Menu item is no longer available")
        food = availability.food
        log = FoodLog(
            user_id=user.id,
            food_id=food.id,
            availability_id=availability.id,
            food_name=food.name,
            serving_size=food.serving_size,
            servings=payload.servings,
            meal_type=payload.meal_type,
            eaten_at=payload.eaten_at,
            calories_per_serving=food.calories or 0,
            protein_per_serving_g=food.protein_g or 0,
            carbs_per_serving_g=food.carbs_g or 0,
            fat_per_serving_g=food.fat_g or 0,
        )
    else:
        log = FoodLog(
            user_id=user.id,
            food_name=payload.custom_name or "Custom food",
            serving_size=payload.serving_size,
            servings=payload.servings,
            meal_type=payload.meal_type,
            eaten_at=payload.eaten_at,
            calories_per_serving=payload.calories or 0,
            protein_per_serving_g=payload.protein_g or 0,
            carbs_per_serving_g=payload.carbs_g or 0,
            fat_per_serving_g=payload.fat_g or 0,
        )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


@router.patch("/logs/{log_id}", response_model=FoodLogResponse)
async def update_log(
    log_id: uuid.UUID,
    payload: FoodLogUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    log = await db.scalar(
        select(FoodLog).where(FoodLog.id == log_id, FoodLog.user_id == user.id)
    )
    if not log:
        raise HTTPException(status_code=404, detail="Food log not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(log, key, value)
    await db.commit()
    await db.refresh(log)
    return log


@router.delete("/logs/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_log(
    log_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        delete(FoodLog).where(FoodLog.id == log_id, FoodLog.user_id == user.id)
    )
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Food log not found")
    await db.commit()


@router.get("/favorites", response_model=list[FavoriteResponse])
async def list_favorites(
    menu_date: date = Query(alias="date"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    foods = (
        await db.scalars(
            select(Food)
            .join(FavoriteFood, FavoriteFood.food_id == Food.id)
            .where(FavoriteFood.user_id == user.id)
            .order_by(Food.name)
        )
    ).all()
    availability_rows = (
        await db.execute(
            select(MenuAvailability.food_id, DiningHall.name)
            .join(Station, Station.id == MenuAvailability.station_id)
            .join(DiningHall, DiningHall.id == Station.hall_id)
            .where(
                MenuAvailability.menu_date == menu_date,
                MenuAvailability.food_id.in_([food.id for food in foods] or [uuid.uuid4()]),
            )
        )
    ).all()
    halls_by_food: dict[uuid.UUID, set[str]] = {}
    for food_id, hall_name in availability_rows:
        halls_by_food.setdefault(food_id, set()).add(hall_name)

    return [
        FavoriteResponse(
            food_id=food.id,
            name=food.name,
            serving_size=food.serving_size,
            calories=food.calories or 0,
            protein_g=food.protein_g or 0,
            carbs_g=food.carbs_g or 0,
            fat_g=food.fat_g or 0,
            available_today=bool(halls_by_food.get(food.id)),
            halls_today=sorted(halls_by_food.get(food.id, set())),
        )
        for food in foods
    ]


@router.post("/favorites", status_code=status.HTTP_201_CREATED)
async def add_favorite(
    payload: FavoriteCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await db.get(Food, payload.food_id):
        raise HTTPException(status_code=404, detail="Food not found")
    existing = await db.get(FavoriteFood, (user.id, payload.food_id))
    if not existing:
        db.add(FavoriteFood(user_id=user.id, food_id=payload.food_id))
        await db.commit()
    return {"food_id": payload.food_id}


@router.delete("/favorites/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    food_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(FavoriteFood).where(
            FavoriteFood.user_id == user.id, FavoriteFood.food_id == food_id
        )
    )
    await db.commit()


def saved_meal_response(meal: SavedMeal) -> SavedMealResponse:
    return SavedMealResponse(
        id=meal.id,
        name=meal.name,
        created_at=meal.created_at,
        items=[
            SavedMealItemResponse(
                food_id=item.food_id,
                name=item.food.name,
                serving_size=item.food.serving_size,
                servings=item.servings,
                calories=(item.food.calories or 0) * item.servings,
                protein_g=(item.food.protein_g or 0) * item.servings,
                carbs_g=(item.food.carbs_g or 0) * item.servings,
                fat_g=(item.food.fat_g or 0) * item.servings,
            )
            for item in meal.items
        ],
    )


@router.get("/saved-meals", response_model=list[SavedMealResponse])
async def list_saved_meals(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    meals = (
        await db.scalars(
            select(SavedMeal)
            .where(SavedMeal.user_id == user.id)
            .options(selectinload(SavedMeal.items).joinedload(SavedMealItem.food))
            .order_by(SavedMeal.created_at.desc())
        )
    ).unique().all()
    return [saved_meal_response(meal) for meal in meals]


@router.post(
    "/saved-meals", response_model=SavedMealResponse, status_code=status.HTTP_201_CREATED
)
async def create_saved_meal(
    payload: SavedMealCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    food_ids = {item.food_id for item in payload.items}
    known_ids = set(
        (await db.scalars(select(Food.id).where(Food.id.in_(food_ids)))).all()
    )
    if known_ids != food_ids:
        raise HTTPException(status_code=422, detail="One or more foods no longer exist")
    meal = SavedMeal(user_id=user.id, name=payload.name.strip())
    meal.items = [
        SavedMealItem(food_id=item.food_id, servings=item.servings)
        for item in payload.items
    ]
    db.add(meal)
    await db.commit()
    meal = await db.scalar(
        select(SavedMeal)
        .where(SavedMeal.id == meal.id)
        .options(selectinload(SavedMeal.items).joinedload(SavedMealItem.food))
    )
    return saved_meal_response(meal)


@router.delete("/saved-meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_meal(
    meal_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        delete(SavedMeal).where(SavedMeal.id == meal_id, SavedMeal.user_id == user.id)
    )
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Saved meal not found")
    await db.commit()

