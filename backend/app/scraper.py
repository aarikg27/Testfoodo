from __future__ import annotations

import argparse
import asyncio
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import APIRequestContext, async_playwright
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from .config import get_settings
from .database import SessionLocal
from .db_init import DEFAULT_HALLS, initialize_database
from .models import (
    DiningHall,
    Food,
    FoodLabel,
    MenuAvailability,
    ScrapeRun,
    Station,
    utcnow,
)

BASE_URL = "https://nutrition.umd.edu/"
LABEL_KINDS = {
    "vegan": "dietary",
    "vegetarian": "dietary",
    "halal": "dietary",
    "locally_grown": "dietary",
    "alcohol": "attribute",
    "pork": "attribute",
    "coconut": "allergen",
    "dairy": "allergen",
    "eggs": "allergen",
    "fish": "allergen",
    "gluten": "allergen",
    "nuts": "allergen",
    "pea_protein": "allergen",
    "sesame": "allergen",
    "shellfish": "allergen",
    "soy": "allergen",
}
LABEL_ALIASES = {
    "egg": "eggs",
    "eggs": "eggs",
    "soybeans": "soy",
    "soybean": "soy",
    "halalfriendly": "halal",
    "halal friendly": "halal",
    "locally grown": "locally_grown",
    "pea protein": "pea_protein",
    "pea_protein": "pea_protein",
    "tree nuts": "nuts",
    "nut": "nuts",
}


@dataclass(frozen=True)
class MenuOccurrence:
    source_key: str
    name: str
    hall_source_id: str
    station: str
    menu_date: date
    meal_period: str
    source_url: str
    labels: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass
class ParsedNutrition:
    source_key: str
    name: str
    serving_size: str | None
    calories: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    saturated_fat_g: float | None
    fiber_g: float | None
    sugar_g: float | None
    sodium_mg: float | None
    ingredients: str | None
    source_url: str
    labels: set[tuple[str, str]] = field(default_factory=set)


def normalize_label(raw: str) -> tuple[str, str] | None:
    value = re.sub(r"\s+", " ", raw.strip().lower())
    value = re.sub(r"^contains\s+", "", value)
    value = LABEL_ALIASES.get(value, value.replace(" ", "_"))
    kind = LABEL_KINDS.get(value)
    return (value, kind) if kind else None


def source_key_from_url(url: str) -> str | None:
    values = parse_qs(urlparse(url).query).get("RecNumAndPort")
    return values[0] if values else None


def parse_menu_html(
    html: str, hall_source_id: str, menu_date: date, page_url: str
) -> list[MenuOccurrence]:
    soup = BeautifulSoup(html, "html.parser")
    meal_by_pane: dict[str, str] = {}
    for tab in soup.select('[role="tab"][aria-controls]'):
        meal = tab.get_text(" ", strip=True).title()
        if meal in {"Breakfast", "Lunch", "Dinner"}:
            meal_by_pane[tab.get("aria-controls", "")] = meal
    meal_by_pane.update({"pane-1": "Breakfast", "pane-2": "Lunch", "pane-3": "Dinner"})

    occurrences: list[MenuOccurrence] = []
    for pane in soup.select('[role="tabpanel"]'):
        meal = meal_by_pane.get(pane.get("id", ""))
        if not meal:
            continue
        for card in pane.select(".card"):
            heading = card.select_one("h3.card-title")
            station = heading.get_text(" ", strip=True) if heading else "Other"
            for row in card.select(".menu-item-row"):
                anchor = row.select_one("a.menu-item-name[href]")
                if not anchor:
                    continue
                source_url = urljoin(page_url, anchor.get("href", ""))
                source_key = source_key_from_url(source_url)
                if not source_key:
                    continue
                labels = []
                for image in row.select("img[alt]"):
                    label = normalize_label(image.get("alt", ""))
                    if label:
                        labels.append(label)
                occurrences.append(
                    MenuOccurrence(
                        source_key=source_key,
                        name=anchor.get_text(" ", strip=True),
                        hall_source_id=hall_source_id,
                        station=station,
                        menu_date=menu_date,
                        meal_period=meal,
                        source_url=source_url,
                        labels=tuple(sorted(set(labels))),
                    )
                )
    return occurrences


def _amount(text: str, label: str, unit: str = "g") -> float | None:
    match = re.search(
        rf"{label}\s*([0-9]+(?:\.[0-9]+)?)\s*{unit}", text, re.IGNORECASE
    )
    return float(match.group(1)) if match else None


def parse_label_html(html: str, source_key: str, source_url: str) -> ParsedNutrition:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h1")
    facts = soup.select_one("table.facts_table")
    if not heading or not facts:
        raise ValueError(f"Nutrition label structure missing for {source_key}")

    facts_text = facts.get_text(" ", strip=True).replace("\xa0", " ")
    serving_nodes = facts.select(".nutfactsservsize")
    serving_size = (
        serving_nodes[-1].get_text(" ", strip=True) if len(serving_nodes) > 1 else None
    )
    calories = None
    paragraphs = [p.get_text(" ", strip=True) for p in facts.select("td[rowspan] p")]
    for index, value in enumerate(paragraphs):
        if "calories per serving" in value.lower() and index + 1 < len(paragraphs):
            match = re.search(r"[0-9]+(?:\.[0-9]+)?", paragraphs[index + 1])
            calories = float(match.group(0)) if match else None
            break
    if calories is None:
        calories = _amount(facts_text, "Calories", "(?:kcal)?")

    ingredients_node = soup.select_one(".labelingredientsvalue")
    allergens_node = soup.select_one(".labelallergensvalue")
    labels: set[tuple[str, str]] = set()
    if allergens_node:
        for raw in re.split(r"[,;/]", allergens_node.get_text(" ", strip=True)):
            label = normalize_label(raw)
            if label:
                labels.add(label)

    return ParsedNutrition(
        source_key=source_key,
        name=heading.get_text(" ", strip=True),
        serving_size=serving_size,
        calories=calories,
        protein_g=_amount(facts_text, r"Protein"),
        carbs_g=_amount(facts_text, r"Total\s+Carbohydrate\.?"),
        fat_g=_amount(facts_text, r"Total\s+Fat"),
        saturated_fat_g=_amount(facts_text, r"Saturated\s+Fat"),
        fiber_g=_amount(facts_text, r"Dietary\s+Fiber"),
        sugar_g=_amount(facts_text, r"Total\s+Sugars"),
        sodium_mg=_amount(facts_text, r"Sodium", "mg"),
        ingredients=(
            ingredients_node.get_text(" ", strip=True) if ingredients_node else None
        ),
        source_url=source_url,
        labels=labels,
    )


async def fetch_text(
    request: APIRequestContext, url: str, *, attempts: int = 3
) -> str:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = await request.get(url, timeout=30_000, fail_on_status_code=False)
            if response.ok:
                return await response.text()
            last_error = RuntimeError(f"HTTP {response.status} for {url}")
        except Exception as exc:  # Playwright provides several transport exceptions.
            last_error = exc
        if attempt + 1 < attempts:
            await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError(str(last_error) if last_error else f"Unable to fetch {url}")


def _format_umd_date(value: date) -> str:
    return f"{value.month}/{value.day}/{value.year}"


def _is_stale(updated_at: datetime | None, refresh_days: int) -> bool:
    if updated_at is None:
        return True
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return updated_at < datetime.now(timezone.utc) - timedelta(days=refresh_days)


async def scrape(
    dates: Iterable[date],
    *,
    hall_source_ids: Iterable[str] | None = None,
    refresh_days: int = 30,
    force_nutrition_refresh: bool = False,
) -> ScrapeRun:
    settings = get_settings()
    target_dates = sorted(set(dates))
    target_halls = set(hall_source_ids or [hall["source_id"] for hall in DEFAULT_HALLS])
    await initialize_database()

    async with SessionLocal() as db:
        run = ScrapeRun(dates_requested=[value.isoformat() for value in target_dates])
        db.add(run)
        await db.commit()
        run_id = run.id

    errors: list[str] = []
    occurrences: list[MenuOccurrence] = []
    nutrition_by_key: dict[str, ParsedNutrition] = {}
    successful_scopes: set[tuple[str, date]] = set()

    try:
        async with async_playwright() as playwright:
            request = await playwright.request.new_context(
                user_agent=settings.scraper_user_agent,
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            for menu_date in target_dates:
                for hall_source_id in sorted(target_halls):
                    query = urlencode(
                        {
                            "locationNum": hall_source_id,
                            "dtdate": _format_umd_date(menu_date),
                        }
                    )
                    page_url = f"{BASE_URL}?{query}"
                    try:
                        html = await fetch_text(request, page_url)
                        parsed = parse_menu_html(
                            html, hall_source_id, menu_date, page_url
                        )
                        if not parsed:
                            errors.append(f"No items found for hall {hall_source_id} on {menu_date}")
                        else:
                            successful_scopes.add((hall_source_id, menu_date))
                        occurrences.extend(parsed)
                    except Exception as exc:
                        errors.append(f"Menu {hall_source_id} {menu_date}: {exc}")

            if not occurrences:
                raise RuntimeError("No menu items were found for any requested hall or date")

            async with SessionLocal() as db:
                existing_foods = {
                    food.source_key: food
                    for food in (
                        await db.scalars(select(Food).options(selectinload(Food.labels)))
                    ).all()
                }

            first_occurrence: dict[str, MenuOccurrence] = {}
            for item in occurrences:
                first_occurrence.setdefault(item.source_key, item)
            refresh_keys = [
                key
                for key, item in first_occurrence.items()
                if force_nutrition_refresh
                or key not in existing_foods
                or _is_stale(existing_foods[key].nutrition_updated_at, refresh_days)
            ]

            semaphore = asyncio.Semaphore(max(1, settings.scraper_concurrency))

            async def fetch_nutrition(key: str) -> None:
                item = first_occurrence[key]
                async with semaphore:
                    try:
                        html = await fetch_text(request, item.source_url)
                        nutrition_by_key[key] = parse_label_html(
                            html, key, item.source_url
                        )
                    except Exception as exc:
                        errors.append(f"Nutrition {key}: {exc}")

            await asyncio.gather(*(fetch_nutrition(key) for key in refresh_keys))
            await request.dispose()

        async with SessionLocal() as db:
            halls = {
                hall.source_id: hall
                for hall in (
                    await db.scalars(
                        select(DiningHall).where(DiningHall.source_id.in_(target_halls))
                    )
                ).all()
            }
            foods = {
                food.source_key: food
                for food in (
                    await db.scalars(select(Food).options(selectinload(Food.labels)))
                ).all()
            }
            labels_by_key: dict[str, set[tuple[str, str]]] = {
                key: {(label.name, label.kind) for label in food.labels}
                for key, food in foods.items()
            }
            for item in occurrences:
                labels_by_key.setdefault(item.source_key, set()).update(item.labels)
                food = foods.get(item.source_key)
                if food is None:
                    food = Food(
                        source_key=item.source_key,
                        name=item.name,
                        source_url=item.source_url,
                    )
                    db.add(food)
                    foods[item.source_key] = food
                else:
                    food.name = item.name
                    food.source_url = item.source_url

            now = utcnow()
            for key, nutrition in nutrition_by_key.items():
                food = foods[key]
                for field_name in (
                    "name",
                    "serving_size",
                    "calories",
                    "protein_g",
                    "carbs_g",
                    "fat_g",
                    "saturated_fat_g",
                    "fiber_g",
                    "sugar_g",
                    "sodium_mg",
                    "ingredients",
                    "source_url",
                ):
                    setattr(food, field_name, getattr(nutrition, field_name))
                food.nutrition_updated_at = now
                labels_by_key.setdefault(key, set()).update(nutrition.labels)

            await db.flush()
            scoped_foods = {
                key: food for key, food in foods.items() if key in first_occurrence
            }
            if scoped_foods:
                await db.execute(
                    delete(FoodLabel).where(
                        FoodLabel.food_id.in_([food.id for food in scoped_foods.values()])
                    )
                )
                db.add_all(
                    [
                        FoodLabel(food_id=food.id, name=name, kind=kind)
                        for key, food in scoped_foods.items()
                        for name, kind in sorted(labels_by_key.get(key, set()))
                    ]
                )

            stations = {
                (station.hall_id, station.name): station
                for station in (await db.scalars(select(Station))).all()
            }
            for item in occurrences:
                hall = halls.get(item.hall_source_id)
                if hall is None:
                    errors.append(f"Unknown hall source ID {item.hall_source_id}")
                    continue
                key = (hall.id, item.station)
                if key not in stations:
                    station = Station(hall_id=hall.id, name=item.station)
                    db.add(station)
                    stations[key] = station
            await db.flush()

            for hall_source_id, successful_date in successful_scopes:
                hall = halls.get(hall_source_id)
                if hall is None:
                    continue
                scoped_station_ids = [
                    station.id
                    for (hall_id, _), station in stations.items()
                    if hall_id == hall.id
                ]
                if scoped_station_ids:
                    await db.execute(
                        delete(MenuAvailability).where(
                            MenuAvailability.menu_date == successful_date,
                            MenuAvailability.station_id.in_(scoped_station_ids),
                        )
                    )

            seen_availability = set()
            for item in occurrences:
                hall = halls.get(item.hall_source_id)
                if hall is None:
                    continue
                station = stations[(hall.id, item.station)]
                food = foods[item.source_key]
                unique_key = (food.id, station.id, item.menu_date, item.meal_period)
                if unique_key in seen_availability:
                    continue
                seen_availability.add(unique_key)
                db.add(
                    MenuAvailability(
                        food_id=food.id,
                        station_id=station.id,
                        menu_date=item.menu_date,
                        meal_period=item.meal_period,
                        source_url=item.source_url,
                        scraped_at=now,
                    )
                )

            run = await db.get(ScrapeRun, run_id)
            run.completed_at = utcnow()
            run.status = "completed_with_warnings" if errors else "completed"
            run.menu_items_found = len(seen_availability)
            run.foods_refreshed = len(nutrition_by_key)
            run.errors = errors[:200]
            await db.commit()
            await db.refresh(run)
            return run
    except Exception as exc:
        errors.append(str(exc))
        async with SessionLocal() as db:
            run = await db.get(ScrapeRun, run_id)
            run.completed_at = utcnow()
            run.status = "failed"
            run.menu_items_found = len(occurrences)
            run.foods_refreshed = len(nutrition_by_key)
            run.errors = errors[:200]
            await db.commit()
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape UMD dining menus into Neon")
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=date.today(),
        help="First menu date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument("--days", type=int, default=7, help="Number of days to scrape")
    parser.add_argument(
        "--hall",
        action="append",
        choices=[hall["source_id"] for hall in DEFAULT_HALLS],
        help="UMD hall source ID; repeat to include multiple halls",
    )
    parser.add_argument("--refresh-days", type=int, default=30)
    parser.add_argument("--force-nutrition-refresh", action="store_true")
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()
    if args.days < 1 or args.days > 14:
        raise SystemExit("--days must be between 1 and 14")
    target_dates = [args.date + timedelta(days=index) for index in range(args.days)]
    run = await scrape(
        target_dates,
        hall_source_ids=args.hall,
        refresh_days=args.refresh_days,
        force_nutrition_refresh=args.force_nutrition_refresh,
    )
    print(
        f"Scrape {run.status}: {run.menu_items_found} availability rows, "
        f"{run.foods_refreshed} nutrition labels refreshed, {len(run.errors)} warnings"
    )


if __name__ == "__main__":
    asyncio.run(async_main())
