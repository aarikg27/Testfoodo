from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable, Sequence

SERVING_OPTIONS = (0.5, 1.0, 1.5, 2.0)


@dataclass(frozen=True)
class Candidate:
    availability_id: int
    food_id: object
    name: str
    station: str
    serving_size: str | None
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float


@dataclass(frozen=True)
class Target:
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float


def _safe(value: float | None) -> float:
    return max(float(value or 0), 0.0)


def _totals(combo: Sequence[tuple[Candidate, float]]) -> Target:
    return Target(
        calories=sum(item.calories * servings for item, servings in combo),
        protein_g=sum(item.protein_g * servings for item, servings in combo),
        carbs_g=sum(item.carbs_g * servings for item, servings in combo),
        fat_g=sum(item.fat_g * servings for item, servings in combo),
    )


def _weights(target: Target, strategy: str) -> dict[str, float]:
    macro_sum = target.protein_g + target.carbs_g + target.fat_g
    if macro_sum <= 0:
        dynamic = {"protein_g": 1 / 3, "carbs_g": 1 / 3, "fat_g": 1 / 3}
    else:
        dynamic = {
            "protein_g": target.protein_g / macro_sum,
            "carbs_g": target.carbs_g / macro_sum,
            "fat_g": target.fat_g / macro_sum,
        }

    weights = {
        "calories": 0.34,
        "protein_g": 0.66 * dynamic["protein_g"],
        "carbs_g": 0.66 * dynamic["carbs_g"],
        "fat_g": 0.66 * dynamic["fat_g"],
    }
    if strategy == "high-protein":
        weights["protein_g"] *= 2.5
        weights["calories"] *= 1.15
    elif strategy == "lower-calorie":
        weights["calories"] *= 2.2
        weights["fat_g"] *= 1.25
    return weights


def _score(totals: Target, target: Target, strategy: str) -> float:
    weights = _weights(target, strategy)
    score = 0.0
    for key in ("calories", "protein_g", "carbs_g", "fat_g"):
        desired = max(getattr(target, key), 1.0)
        actual = getattr(totals, key)
        difference = actual - desired
        penalty = 1.75 if difference > 0 else 1.0
        if key == "calories" and difference > 0:
            penalty = 2.6 if strategy == "lower-calorie" else 2.1
        score += weights[key] * abs(difference) / desired * penalty

    # Prefer simpler, usable combinations when macro fit is similar.
    return score


def _single_relevance(candidate: Candidate, target: Target, strategy: str) -> float:
    return min(
        _score(
            _totals(((candidate, servings),)),
            target,
            strategy,
        )
        for servings in SERVING_OPTIONS
    )


def _preselect(
    candidates: Sequence[Candidate], target: Target, strategy: str, limit: int = 18
) -> list[Candidate]:
    ranked = sorted(candidates, key=lambda item: _single_relevance(item, target, strategy))
    selected = list(ranked[:limit])

    # Preserve complementary protein, carbohydrate, and fat sources even if their
    # single-food score is weaker than balanced entrees.
    density_rankings = [
        sorted(candidates, key=lambda item: item.protein_g / max(item.calories, 20), reverse=True),
        sorted(candidates, key=lambda item: item.carbs_g / max(item.calories, 20), reverse=True),
        sorted(candidates, key=lambda item: item.fat_g / max(item.calories, 20), reverse=True),
    ]
    seen = {item.availability_id for item in selected}
    for ranking in density_rankings:
        for item in ranking[:4]:
            if item.availability_id not in seen:
                selected.append(item)
                seen.add(item.availability_id)
    return selected[:24]


def best_plan(
    candidates: Sequence[Candidate], target: Target, strategy: str = "balanced"
) -> tuple[list[tuple[Candidate, float]], Target, float]:
    useful = [
        item
        for item in candidates
        if item.calories > 0
        and (item.protein_g > 0 or item.carbs_g > 0 or item.fat_g > 0)
    ]
    if not useful:
        return [], Target(0, 0, 0, 0), float("inf")

    pool = _preselect(useful, target, strategy)
    best_combo: list[tuple[Candidate, float]] = []
    best_totals = Target(0, 0, 0, 0)
    best_score = float("inf")

    for size in range(1, min(3, len(pool)) + 1):
        for foods in combinations(pool, size):
            serving_sets: Iterable[tuple[float, ...]]
            if size == 1:
                serving_sets = ((a,) for a in SERVING_OPTIONS)
            elif size == 2:
                serving_sets = ((a, b) for a in SERVING_OPTIONS for b in SERVING_OPTIONS)
            else:
                serving_sets = (
                    (a, b, c)
                    for a in SERVING_OPTIONS
                    for b in SERVING_OPTIONS
                    for c in SERVING_OPTIONS
                )

            for servings in serving_sets:
                combo = list(zip(foods, servings))
                totals = _totals(combo)
                score = _score(totals, target, strategy) + (size - 1) * 0.018
                if score < best_score:
                    best_combo = combo
                    best_totals = totals
                    best_score = score

    return best_combo, best_totals, best_score


def build_recommendations(
    candidates: Sequence[Candidate], target: Target
) -> list[dict]:
    if target.calories < 150 or (
        target.protein_g < 5 and target.carbs_g < 5 and target.fat_g < 3
    ):
        return []
    plans = []
    meal_target = target
    if target.calories > 900:
        meal_scale = 900 / target.calories
        meal_target = Target(
            calories=900,
            protein_g=target.protein_g * meal_scale,
            carbs_g=target.carbs_g * meal_scale,
            fat_g=target.fat_g * meal_scale,
        )
    metadata = {
        "balanced": ("Best overall fit", "Balances all of your remaining targets"),
        "high-protein": ("Protein-forward", "Prioritizes your remaining protein target"),
        "lower-calorie": ("Lighter option", "Limits calorie and fat overshoot"),
    }

    signatures = set()
    for strategy in ("balanced", "high-protein", "lower-calorie"):
        optimization_target = meal_target
        if strategy == "lower-calorie":
            optimization_target = Target(
                calories=meal_target.calories * 0.65,
                protein_g=meal_target.protein_g * 0.72,
                carbs_g=meal_target.carbs_g * 0.55,
                fat_g=meal_target.fat_g * 0.55,
            )
        combo, totals, score = best_plan(candidates, optimization_target, strategy)
        if not combo:
            continue
        signature = tuple(
            sorted((item.availability_id, servings) for item, servings in combo)
        )
        if signature in signatures:
            continue
        signatures.add(signature)
        title, explanation_start = metadata[strategy]
        if target.protein_g < 1:
            explanation = (
                f"{explanation_start}; your protein target is already met, so this "
                f"option emphasizes balance within {totals.calories:.0f} calories."
            )
        else:
            protein_coverage = min(totals.protein_g / target.protein_g * 100, 999)
            explanation = (
                f"{explanation_start}; covers {protein_coverage:.0f}% of the remaining "
                f"protein with {totals.calories:.0f} calories."
            )
        plans.append(
            {
                "strategy": strategy,
                "title": title,
                "explanation": explanation,
                "score": round(score, 4),
                "items": [
                    {
                        "availability_id": item.availability_id,
                        "food_id": item.food_id,
                        "name": item.name,
                        "station": item.station,
                        "serving_size": item.serving_size,
                        "servings": servings,
                        "calories": round(item.calories * servings, 1),
                        "protein_g": round(item.protein_g * servings, 1),
                        "carbs_g": round(item.carbs_g * servings, 1),
                        "fat_g": round(item.fat_g * servings, 1),
                    }
                    for item, servings in combo
                ],
                "totals": {
                    "calories": round(totals.calories, 1),
                    "protein_g": round(totals.protein_g, 1),
                    "carbs_g": round(totals.carbs_g, 1),
                    "fat_g": round(totals.fat_g, 1),
                },
            }
        )
    return plans


def make_candidate(
    *,
    availability_id: int,
    food_id: object,
    name: str,
    station: str,
    serving_size: str | None,
    calories: float | None,
    protein_g: float | None,
    carbs_g: float | None,
    fat_g: float | None,
) -> Candidate:
    return Candidate(
        availability_id=availability_id,
        food_id=food_id,
        name=name,
        station=station,
        serving_size=serving_size,
        calories=_safe(calories),
        protein_g=_safe(protein_g),
        carbs_g=_safe(carbs_g),
        fat_g=_safe(fat_g),
    )
