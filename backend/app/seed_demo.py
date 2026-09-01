from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy import delete, select

from .database import SessionLocal
from .db_init import initialize_database
from .models import DiningHall, Food, FoodLabel, MenuAvailability, Station, utcnow

DEMO_FOODS = [
    ("demo-chicken", "Peruvian Chicken", "4 oz", 154, 21.1, 1.2, 6.8, ["halal"]),
    ("demo-sesame", "Sauteed Sesame Chicken", "4 oz", 150, 26.3, 0, 4.2, ["sesame"]),
    ("demo-rice", "Brown Rice", "4 oz", 146, 3.2, 30.5, 1.2, ["vegan", "vegetarian"]),
    ("demo-broccoli", "Steamed Broccoli", "4 oz", 38, 2.6, 7.2, 0.4, ["vegan", "vegetarian"]),
    ("demo-beans", "Black Beans", "4 oz", 132, 8.9, 23.7, 0.5, ["vegan", "vegetarian"]),
    ("demo-salmon", "Herb Roasted Salmon", "4 oz", 232, 25.4, 2.0, 13.1, ["fish"]),
    ("demo-tofu", "Garlic Chive Spiced Tofu", "4 oz", 128, 12.2, 5.4, 7.1, ["vegan", "vegetarian", "soy", "gluten", "sesame"]),
    ("demo-potatoes", "Roasted Red Potatoes", "4 oz", 168, 3.4, 31.2, 3.8, ["vegan", "vegetarian"]),
    ("demo-yogurt", "Greek Yogurt", "6 oz", 120, 17.0, 7.0, 2.5, ["vegetarian", "dairy"]),
    ("demo-eggs", "Scrambled Eggs", "4 oz", 196, 13.7, 2.1, 14.7, ["vegetarian", "eggs"]),
    ("demo-pasta", "Penne Marinara", "6 oz", 284, 9.1, 51.0, 5.2, ["vegan", "vegetarian", "gluten"]),
    ("demo-avocado", "Avocado Sliced", "1 oz", 49, 0.6, 2.6, 4.5, ["vegan", "vegetarian"]),
]


async def seed_demo() -> None:
    await initialize_database()
    today = date.today()
    async with SessionLocal() as db:
        halls = {hall.source_id: hall for hall in (await db.scalars(select(DiningHall))).all()}
        station_specs = [
            ("19", "Chef's Table"),
            ("19", "Roma"),
            ("51", "Purple Zone"),
            ("16", "Chef's Table"),
        ]
        stations = {}
        for source_id, name in station_specs:
            hall = halls[source_id]
            station = await db.scalar(
                select(Station).where(Station.hall_id == hall.id, Station.name == name)
            )
            if station is None:
                station = Station(hall_id=hall.id, name=name)
                db.add(station)
                await db.flush()
            stations[(source_id, name)] = station

        foods = {}
        dietary = {"vegan", "vegetarian", "halal"}
        for key, name, serving, calories, protein, carbs, fat, labels in DEMO_FOODS:
            food = await db.scalar(select(Food).where(Food.source_key == key))
            if food is None:
                food = Food(source_key=key, name=name, source_url="https://nutrition.umd.edu/")
                db.add(food)
            food.name = name
            food.serving_size = serving
            food.calories = calories
            food.protein_g = protein
            food.carbs_g = carbs
            food.fat_g = fat
            food.nutrition_updated_at = utcnow()
            food.labels = [
                FoodLabel(
                    name=label,
                    kind=(
                        "dietary"
                        if label in dietary
                        else "attribute"
                        if label == "pork"
                        else "allergen"
                    ),
                )
                for label in labels
            ]
            foods[key] = food
        await db.flush()

        station_ids = [station.id for station in stations.values()]
        await db.execute(
            delete(MenuAvailability).where(
                MenuAvailability.menu_date == today,
                MenuAvailability.station_id.in_(station_ids),
                MenuAvailability.food_id.in_([food.id for food in foods.values()]),
            )
        )
        station_cycle = list(stations.values())
        for index, food in enumerate(foods.values()):
            for meal in ("Lunch", "Dinner"):
                station = station_cycle[index % len(station_cycle)]
                db.add(
                    MenuAvailability(
                        food_id=food.id,
                        station_id=station.id,
                        menu_date=today,
                        meal_period=meal,
                        source_url=food.source_url,
                    )
                )
        await db.commit()
    print(f"Seeded {len(DEMO_FOODS)} demo foods for {today}")


if __name__ == "__main__":
    asyncio.run(seed_demo())

