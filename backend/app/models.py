from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class DiningHall(Base):
    __tablename__ = "dining_halls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    stations: Mapped[list["Station"]] = relationship(
        back_populates="hall", cascade="all, delete-orphan"
    )


class Station(Base):
    __tablename__ = "stations"
    __table_args__ = (UniqueConstraint("hall_id", "name", name="uq_station_hall_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(
        ForeignKey("dining_halls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)

    hall: Mapped[DiningHall] = relationship(back_populates="stations")
    availability: Mapped[list["MenuAvailability"]] = relationship(
        back_populates="station", cascade="all, delete-orphan"
    )


class Food(Base):
    __tablename__ = "foods"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False, index=True)
    serving_size: Mapped[Optional[str]] = mapped_column(String(100))
    calories: Mapped[Optional[float]] = mapped_column(Float)
    protein_g: Mapped[Optional[float]] = mapped_column(Float)
    carbs_g: Mapped[Optional[float]] = mapped_column(Float)
    fat_g: Mapped[Optional[float]] = mapped_column(Float)
    saturated_fat_g: Mapped[Optional[float]] = mapped_column(Float)
    fiber_g: Mapped[Optional[float]] = mapped_column(Float)
    sugar_g: Mapped[Optional[float]] = mapped_column(Float)
    sodium_mg: Mapped[Optional[float]] = mapped_column(Float)
    ingredients: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    nutrition_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    labels: Mapped[list["FoodLabel"]] = relationship(
        back_populates="food", cascade="all, delete-orphan", lazy="selectin"
    )
    availability: Mapped[list["MenuAvailability"]] = relationship(
        back_populates="food", cascade="all, delete-orphan"
    )


class FoodLabel(Base):
    __tablename__ = "food_labels"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('allergen', 'dietary', 'attribute')", name="ck_food_label_kind"
        ),
    )

    food_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("foods.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)

    food: Mapped[Food] = relationship(back_populates="labels")


class MenuAvailability(Base):
    __tablename__ = "menu_availability"
    __table_args__ = (
        UniqueConstraint(
            "food_id", "station_id", "menu_date", "meal_period", name="uq_menu_item"
        ),
        CheckConstraint(
            "meal_period IN ('Breakfast', 'Lunch', 'Dinner')",
            name="ck_menu_meal_period",
        ),
        Index("ix_menu_hall_date_meal", "menu_date", "meal_period", "station_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    food_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("foods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    menu_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    meal_period: Mapped[str] = mapped_column(String(20), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    food: Mapped[Food] = relationship(back_populates="availability", lazy="joined")
    station: Mapped[Station] = relationship(back_populates="availability", lazy="joined")


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    dates_requested: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    menu_items_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    foods_refreshed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), default="America/New_York")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    credential: Mapped["UserCredential"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    preferences: Mapped["UserPreference"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


class UserCredential(Base):
    __tablename__ = "user_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    user: Mapped[User] = relationship(back_populates="credential")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    calorie_goal: Mapped[float] = mapped_column(Float, default=2200, nullable=False)
    protein_goal_g: Mapped[float] = mapped_column(Float, default=140, nullable=False)
    carbs_goal_g: Mapped[float] = mapped_column(Float, default=250, nullable=False)
    fat_goal_g: Mapped[float] = mapped_column(Float, default=70, nullable=False)
    dietary_preferences: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    excluded_labels: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    profile_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    favorite_hall_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("dining_halls.id", ondelete="SET NULL")
    )

    user: Mapped[User] = relationship(back_populates="preferences")


class DailyGoal(Base):
    __tablename__ = "daily_goals"
    __table_args__ = (UniqueConstraint("user_id", "goal_date", name="uq_user_goal_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goal_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    calorie_goal: Mapped[float] = mapped_column(Float, nullable=False)
    protein_goal_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_goal_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_goal_g: Mapped[float] = mapped_column(Float, nullable=False)


class FoodLog(Base):
    __tablename__ = "food_logs"
    __table_args__ = (CheckConstraint("servings > 0", name="ck_food_log_servings"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    food_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("foods.id", ondelete="SET NULL"), index=True
    )
    availability_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("menu_availability.id", ondelete="SET NULL")
    )
    food_name: Mapped[str] = mapped_column(String(250), nullable=False)
    serving_size: Mapped[Optional[str]] = mapped_column(String(100))
    servings: Mapped[float] = mapped_column(Float, default=1, nullable=False)
    meal_type: Mapped[str] = mapped_column(String(30), default="Snack", nullable=False)
    eaten_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    calories_per_serving: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    protein_per_serving_g: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    carbs_per_serving_g: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    fat_per_serving_g: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class FavoriteFood(Base):
    __tablename__ = "favorite_foods"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    food_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("foods.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class SavedMeal(Base):
    __tablename__ = "saved_meals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    items: Mapped[list["SavedMealItem"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan", lazy="selectin"
    )


class SavedMealItem(Base):
    __tablename__ = "saved_meal_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    saved_meal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("saved_meals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    food_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("foods.id", ondelete="CASCADE"), nullable=False
    )
    servings: Mapped[float] = mapped_column(Float, default=1, nullable=False)

    meal: Mapped[SavedMeal] = relationship(back_populates="items")
    food: Mapped[Food] = relationship(lazy="joined")
