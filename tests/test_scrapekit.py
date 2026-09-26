"""Offline tests: a fake fetcher serves saved HTML, so no network is needed."""
import json
import sqlite3
from pathlib import Path

import pytest

from scrapekit.export import write_all
from scrapekit.sites import books, quotes
from scrapekit.validate import BOOK_RULES, QUOTE_RULES, dedupe, validate

FIX = Path(__file__).parent / "fixtures"
B, Q = books.BASE, quotes.BASE

ROUTES = {
    B: "books_page1.html",
    B + "page-2.html": "books_page2.html",
    B + "a-light-in-the-attic_1000/index.html": "book_attic.html",
    B + "tipping-the-velvet_999/index.html": "book_velvet.html",
    B + "soumission_998/index.html": "book_soumission.html",
    Q: "quotes_page1.html",
    Q + "page/2/": "quotes_page2.html",
    Q + "js/": "quotes_js1.html",
    Q + "js/page/2/": "quotes_js2.html",
    Q + "api/quotes?page=1": "quotes_api1.json",
    Q + "api/quotes?page=2": "quotes_api2.json",
}


class FakeFetcher:
    def __init__(self, routes=ROUTES):
        self.routes, self.calls = routes, []

    def get_text(self, url):
        self.calls.append(url)
        if url not in self.routes:
            raise KeyError(f"no fixture for {url}")
        return (FIX / self.routes[url]).read_text(encoding="utf-8")

    def get_json(self, url):
        return json.loads(self.get_text(url))


# ------------------------------------------------------------------ books
def test_books_follows_pagination_and_parses_details():
    rows = books.scrape(FakeFetcher(), workers=2)
    assert len(rows) == 3
    attic = next(r for r in rows if r["title"] == "A Light in the Attic")
    assert attic == {
        "upc": "a897fe39b1053632", "title": "A Light in the Attic", "category": "Poetry",
        "price_incl_tax": 51.77, "price_excl_tax": 51.77, "tax": 0.0, "in_stock": 22,
        "rating": 3, "reviews": 0,
        "description": "It's hard to imagine a world without A Light in the Attic.",
        "image_url": "https://books.toscrape.com/media/cache/fe/72/a897fe39b1053632.jpg",
        "url": B + "a-light-in-the-attic_1000/index.html",
    }


def test_books_missing_description_is_empty_not_crash():
    rows = books.scrape(FakeFetcher())
    assert next(r for r in rows if r["title"] == "Soumission")["description"] == ""


def test_books_max_pages_limits_crawl():
    f = FakeFetcher()
    rows = books.scrape(f, max_pages=1)
    assert len(rows) == 2 and B + "page-2.html" not in f.calls


def test_books_failed_detail_page_is_skipped():
    routes = dict(ROUTES)
    del routes[B + "soumission_998/index.html"]
    rows = books.scrape(FakeFetcher(routes))
    assert {r["title"] for r in rows} == {"A Light in the Attic", "Tipping the Velvet"}


@pytest.mark.parametrize("txt,val", [("£51.77", 51.77), ("Â£1,234.50", 1234.5), ("12", 12.0)])
def test_money(txt, val):
    assert books._money(txt) == val


# ------------------------------------------------------------------ quotes
@pytest.mark.parametrize("mode", ["html", "js", "api"])
def test_quotes_all_modes_return_same_data(mode):
    rows = quotes.scrape(FakeFetcher(), mode=mode)
    assert [(r["author"], r["tags"]) for r in rows] == [
        ("Albert Einstein", ["change", "thinking"]),
        ("J.K. Rowling", ["abilities", "choices"]),
        ("Steve Martin", ["humor"]),
    ]
    assert rows[0]["text"] == "The world as we have created it is a process of our thinking."
    assert rows[1]["author_url"] == Q + "author/J-K-Rowling"


def test_quotes_modes_are_identical():
    runs = [quotes.scrape(FakeFetcher(), mode=m) for m in ("html", "js", "api")]
    assert runs[0] == runs[1] == runs[2]


def test_js_page_layout_change_is_loud():
    with pytest.raises(ValueError, match="not found"):
        quotes.parse_js_page("<html><script>var items = [];</script></html>", Q)


def test_unknown_mode():
    with pytest.raises(ValueError):
        quotes.scrape(FakeFetcher(), mode="nope")


# ------------------------------------------------------------------ validation + export
def test_validation_passes_on_good_data():
    rep = validate(books.scrape(FakeFetcher()), BOOK_RULES, "upc")
    assert rep.ok, rep.summary()


def test_validation_catches_breakage():
    rows = books.scrape(FakeFetcher())
    rows[0]["title"] = ""
    rows[1]["rating"] = 0
    rows.append(dict(rows[2]))
    rep = validate(rows, BOOK_RULES, "upc")
    assert not rep.ok and rep.duplicates == 1
    assert any("title is empty" in i for i in rep.issues)
    assert any("rating=0" in i for i in rep.issues)
    assert len(dedupe(rows, "upc")) == 3


def test_validation_min_rows():
    assert not validate([], QUOTE_RULES, "text").ok


def test_export_all_formats(tmp_path):
    rows = quotes.scrape(FakeFetcher(), mode="api")
    paths = write_all(rows, tmp_path, "quotes", ["csv", "json", "sqlite"])
    assert [p.suffix for p in paths] == [".csv", ".json", ".db"]
    assert json.loads(paths[1].read_text(encoding="utf-8"))[2]["author"] == "Steve Martin"
    assert "change|thinking" in paths[0].read_text(encoding="utf-8-sig")
    con = sqlite3.connect(paths[2])
    assert con.execute("select count(*) from quotes").fetchone()[0] == 3
    con.close()


# ------------------------------------------------------------------ CLI end to end
@pytest.mark.parametrize("args,name,rows", [(["books"], "books", 3), (["quotes", "--mode", "js"], "quotes_js", 3)])
def test_cli(monkeypatch, tmp_path, capsys, args, name, rows):
    from scrapekit import cli
    monkeypatch.setattr(cli, "Fetcher", lambda **kw: type("F", (FakeFetcher,), {"stats": {"requests": 0, "cache_hits": 0}})())
    assert cli.main(args + ["--out", str(tmp_path), "--strict"]) == 0
    out = capsys.readouterr().out
    assert "RESULT: PASS" in out and f"{rows} rows" in out
    assert (tmp_path / f"{name}.csv").exists() and (tmp_path / f"{name}.db").exists()
