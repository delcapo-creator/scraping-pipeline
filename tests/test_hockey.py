"""Hockey teams: HTML table + pagination, tested offline."""
from pathlib import Path

from scrapekit.sites import hockey
from scrapekit.validate import HOCKEY_RULES, validate

FIX = Path(__file__).parent / "fixtures"
B = hockey.BASE
ROUTES = {
    B + "?page_num=1&per_page=100": "hockey_page1.html",
    B + "?page_num=2&per_page=100": "hockey_page2.html",
}


class Fake:
    def __init__(self):
        self.calls = []

    def get_text(self, url):
        self.calls.append(url)
        return (FIX / ROUTES[url]).read_text(encoding="utf-8")


def test_parses_table_and_follows_next():
    rows = hockey.scrape(Fake())
    assert len(rows) == 3
    assert rows[0] == {"team": "Boston Bruins", "year": 1990, "wins": 44, "losses": 24, "ot_losses": None,
                       "win_pct": 0.55, "goals_for": 299, "goals_against": 264, "goal_diff": 35}
    assert rows[2]["ot_losses"] == 16 and rows[2]["goal_diff"] == -24


def test_max_pages():
    f = Fake()
    assert len(hockey.scrape(f, max_pages=1)) == 2 and len(f.calls) == 1


def test_search_goes_into_url():
    f = Fake()
    f.get_text = lambda url: f.calls.append(url) or "<html></html>"
    hockey.scrape(f, query="boston")
    assert f.calls == [B + "?page_num=1&per_page=100&q=boston"]


def test_validation_passes():
    assert validate(hockey.scrape(Fake()), HOCKEY_RULES, ("team", "year")).ok
