import uuid

from app.recommendations import Candidate, Target, best_plan, build_recommendations


def candidate(name, calories, protein, carbs, fat, index):
    return Candidate(
        availability_id=index,
        food_id=uuid.uuid4(),
        name=name,
        station="Test Station",
        serving_size="4 oz",
        calories=calories,
        protein_g=protein,
        carbs_g=carbs,
        fat_g=fat,
    )


FOODS = [
    candidate("Chicken", 180, 30, 2, 6, 1),
    candidate("Rice", 190, 4, 40, 1, 2),
    candidate("Beans", 140, 9, 25, 1, 3),
    candidate("Avocado", 80, 1, 4, 7, 4),
    candidate("Salmon", 240, 26, 0, 15, 5),
]


def test_best_plan_uses_no_more_than_three_distinct_foods():
    combo, totals, score = best_plan(
        FOODS, Target(calories=650, protein_g=45, carbs_g=70, fat_g=18)
    )

    assert 1 <= len(combo) <= 3
    assert len({item.availability_id for item, _ in combo}) == len(combo)
    assert totals.calories > 0
    assert score < 1


def test_recommendations_return_explainable_strategies():
    plans = build_recommendations(
        FOODS, Target(calories=650, protein_g=45, carbs_g=70, fat_g=18)
    )

    assert 1 <= len(plans) <= 3
    assert plans[0]["strategy"] == "balanced"
    assert "protein" in plans[0]["explanation"].lower()
    assert all(1 <= len(plan["items"]) <= 3 for plan in plans)
    assert all(plan["totals"]["calories"] > 0 for plan in plans)


def test_recommendations_stop_when_daily_targets_are_met():
    plans = build_recommendations(
        FOODS, Target(calories=100, protein_g=0, carbs_g=0, fat_g=0)
    )

    assert plans == []

