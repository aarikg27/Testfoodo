from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserPublic(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    timezone: str

    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserPublic


class HallResponse(BaseModel):
    id: int
    source_id: str
    slug: str
    name: str
    item_count: int = 0


class FoodResponse(BaseModel):
    id: uuid.UUID
    availability_id: int
    source_key: str
    name: str
    serving_size: Optional[str] = None
    calories: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    saturated_fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    sugar_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    ingredients: Optional[str] = None
    source_url: str
    hall_id: int
    hall_name: str
    hall_slug: str
    station: str
    menu_date: date
    meal_period: str
    labels: List[str] = []
    dietary_labels: List[str] = []
    allergens: List[str] = []
    nutrition_updated_at: Optional[datetime] = None


class PaginatedFoods(BaseModel):
    items: List[FoodResponse]
    total: int
    limit: int
    offset: int
    menu_date: date
    last_scraped_at: Optional[datetime] = None


class GoalValues(BaseModel):
    calorie_goal: float = Field(gt=0, le=10000)
    protein_goal_g: float = Field(gt=0, le=1000)
    carbs_goal_g: float = Field(gt=0, le=1500)
    fat_goal_g: float = Field(gt=0, le=500)


class GoalResponse(GoalValues):
    goal_date: date
    source: str


class GoalUpdate(GoalValues):
    goal_date: date
    save_as_default: bool = False


class BodyProfile(BaseModel):
    age: Optional[int] = Field(default=None, ge=13, le=100)
    height_cm: Optional[float] = Field(default=None, ge=100, le=250)
    weight_kg: Optional[float] = Field(default=None, ge=30, le=350)
    gender: Optional[Literal["woman", "man", "nonbinary", "prefer_not_to_say"]] = None
    activity_level: Literal["sedentary", "light", "moderate", "very_active"] = "moderate"
    goal_type: Literal["lose", "maintain", "gain"] = "maintain"
    use_profile_targets: bool = True


class PreferenceResponse(BaseModel):
    calorie_goal: float
    protein_goal_g: float
    carbs_goal_g: float
    fat_goal_g: float
    dietary_preferences: List[str]
    excluded_labels: List[str]
    favorite_hall_id: Optional[int]
    profile: BodyProfile = Field(default_factory=BodyProfile)


class PreferenceUpdate(BaseModel):
    dietary_preferences: List[str] = []
    excluded_labels: List[str] = []
    favorite_hall_id: Optional[int] = None
    profile: BodyProfile = Field(default_factory=BodyProfile)


class FoodLogCreate(BaseModel):
    availability_id: Optional[int] = None
    servings: float = Field(default=1, gt=0, le=20)
    meal_type: str = Field(default="Snack", max_length=30)
    eaten_at: datetime
    custom_name: Optional[str] = Field(default=None, max_length=250)
    serving_size: Optional[str] = Field(default=None, max_length=100)
    calories: Optional[float] = Field(default=None, ge=0, le=10000)
    protein_g: Optional[float] = Field(default=None, ge=0, le=1000)
    carbs_g: Optional[float] = Field(default=None, ge=0, le=1500)
    fat_g: Optional[float] = Field(default=None, ge=0, le=500)

    @model_validator(mode="after")
    def require_source_or_custom(self):
        if self.availability_id is None and not self.custom_name:
            raise ValueError("Provide availability_id or custom_name")
        return self


class FoodLogUpdate(BaseModel):
    servings: Optional[float] = Field(default=None, gt=0, le=20)
    meal_type: Optional[str] = Field(default=None, max_length=30)
    eaten_at: Optional[datetime] = None


class FoodLogResponse(BaseModel):
    id: uuid.UUID
    food_id: Optional[uuid.UUID]
    availability_id: Optional[int]
    food_name: str
    serving_size: Optional[str]
    servings: float
    meal_type: str
    eaten_at: datetime
    calories_per_serving: float
    protein_per_serving_g: float
    carbs_per_serving_g: float
    fat_per_serving_g: float

    model_config = ConfigDict(from_attributes=True)


class FavoriteCreate(BaseModel):
    food_id: uuid.UUID


class FavoriteResponse(BaseModel):
    food_id: uuid.UUID
    name: str
    serving_size: Optional[str]
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    available_today: bool = False
    halls_today: List[str] = []


class SavedMealItemCreate(BaseModel):
    food_id: uuid.UUID
    servings: float = Field(gt=0, le=20)


class SavedMealCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    items: List[SavedMealItemCreate] = Field(min_length=1, max_length=30)


class SavedMealItemResponse(BaseModel):
    food_id: uuid.UUID
    name: str
    serving_size: Optional[str]
    servings: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float


class SavedMealResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    items: List[SavedMealItemResponse]


class RemainingMacros(BaseModel):
    calories: float = Field(ge=0, le=10000)
    protein_g: float = Field(ge=0, le=1000)
    carbs_g: float = Field(ge=0, le=1500)
    fat_g: float = Field(ge=0, le=500)


class RecommendationRequest(BaseModel):
    hall: Optional[str] = None
    menu_date: date
    meal: Optional[str] = None
    remaining: RemainingMacros
    excluded_labels: List[str] = []
    dietary_preferences: List[str] = []


class RecommendationItem(BaseModel):
    availability_id: int
    food_id: uuid.UUID
    name: str
    station: str
    serving_size: Optional[str]
    servings: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float


class RecommendationPlan(BaseModel):
    strategy: str
    title: str
    explanation: str
    score: float
    items: List[RecommendationItem]
    totals: RemainingMacros


class RecommendationResponse(BaseModel):
    plans: List[RecommendationPlan]
    candidate_count: int


class ScrapeStatusResponse(BaseModel):
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    menu_items_found: int = 0
    foods_refreshed: int = 0
    errors: List[str] = []


class MenuDateResponse(BaseModel):
    date: date
    meal_periods: List[str]
    item_count: int


class MenuContextResponse(BaseModel):
    today: date
    current_meal: str
    dates: List[MenuDateResponse]
    refresh_status: str
    last_refresh_at: Optional[datetime] = None

