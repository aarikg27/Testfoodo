from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..recommendations import Target, build_recommendations, make_candidate
from ..schemas import RecommendationRequest, RecommendationResponse
from .foods import effective_meal, menu_statement

router = APIRouter(tags=["recommendations"])


@router.post("/recommendations", response_model=RecommendationResponse)
async def recommend_foods(
    payload: RecommendationRequest, db: AsyncSession = Depends(get_db)
):
    meal = effective_meal(payload.menu_date, payload.meal)
    statement = menu_statement(
        menu_date=payload.menu_date,
        hall=payload.hall,
        meal=meal,
        dietary=payload.dietary_preferences,
        excluded_labels=payload.excluded_labels,
    )
    availability = (await db.scalars(statement)).unique().all()
    candidates = [
        make_candidate(
            availability_id=item.id,
            food_id=item.food.id,
            name=item.food.name,
            station=item.station.name,
            serving_size=item.food.serving_size,
            calories=item.food.calories,
            protein_g=item.food.protein_g,
            carbs_g=item.food.carbs_g,
            fat_g=item.food.fat_g,
        )
        for item in availability
    ]
    remaining = payload.remaining
    plans = build_recommendations(
        candidates,
        Target(
            calories=remaining.calories,
            protein_g=remaining.protein_g,
            carbs_g=remaining.carbs_g,
            fat_g=remaining.fat_g,
        ),
    )
    return RecommendationResponse(plans=plans, candidate_count=len(candidates))

