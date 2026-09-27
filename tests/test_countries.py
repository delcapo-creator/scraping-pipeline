"""Countries: one page, card layout. Written by Saad as his first site module."""
from pathlib import Path

from scrapekit.sites import countries
from scrapekit.validate import COUNTRY_RULES, validate

HTML = (Path(__file__).parent / "fixtures" / "countries.html").read_text(encoding="utf-8")


def test_parses_cards_ignoring_flag_icon_and_labels():
    rows = countries.parse_page(HTML)
    assert rows == [
        {"name": "Andorra", "capital": "Andorra la Vella", "population": 84000, "area_km2": 468.0},
        {"name": "Algeria", "capital": "Algiers", "population": 34586184, "area_km2": 2381740.0},
    ]


def test_scrape_uses_one_request():
    calls = []
    rows = countries.scrape(type("F", (), {"get_text": lambda self, u: calls.append(u) or HTML})())
    assert len(rows) == 2 and calls == [countries.BASE]


def test_validation_passes():
    assert validate(countries.parse_page(HTML), COUNTRY_RULES, "name").ok
