from datetime import date
from pathlib import Path

import pytest

from app.scraper import parse_label_html, parse_menu_html, source_key_from_url

FIXTURES = Path(__file__).parent / "fixtures"


def test_source_key_from_url_preserves_recipe_and_portion():
    assert (
        source_key_from_url(
            "https://nutrition.umd.edu/label.aspx?RecNumAndPort=080521%2A4"
        )
        == "080521*4"
    )


def test_parse_menu_html_extracts_station_meal_and_labels():
    html = (FIXTURES / "menu.html").read_text()
    items = parse_menu_html(
        html,
        hall_source_id="19",
        menu_date=date(2026, 8, 31),
        page_url="https://nutrition.umd.edu/?locationNum=19",
    )

    assert len(items) == 1
    item = items[0]
    assert item.source_key == "080521*4"
    assert item.name == "Peruvian Chicken"
    assert item.station == "Chef's Table"
    assert item.meal_period == "Lunch"
    assert ("halal", "dietary") in item.labels
    assert ("soy", "allergen") in item.labels


def test_parse_label_html_extracts_macros_and_allergens():
    html = (FIXTURES / "label.html").read_text()
    nutrition = parse_label_html(
        html,
        source_key="080521*4",
        source_url="https://nutrition.umd.edu/label.aspx?RecNumAndPort=080521*4",
    )

    assert nutrition.name == "Peruvian Chicken"
    assert nutrition.serving_size == "4 oz"
    assert nutrition.calories == 154
    assert nutrition.protein_g == pytest.approx(21.1)
    assert nutrition.carbs_g == pytest.approx(1.2)
    assert nutrition.fat_g == pytest.approx(6.8)
    assert nutrition.sodium_mg == pytest.approx(443.7)
    assert nutrition.ingredients == "Chicken, lime juice, olive oil"
    assert nutrition.labels == {("soy", "allergen"), ("sesame", "allergen")}

