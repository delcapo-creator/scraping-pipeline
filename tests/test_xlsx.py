"""Excel export: real columns, numbers stay numeric, header frozen."""
import pytest

openpyxl = pytest.importorskip("openpyxl")

from scrapekit.export import write_all  # noqa: E402


def test_xlsx(tmp_path):
    rows = [{"name": "Algeria", "capital": "Algiers", "population": 34586184, "area_km2": 2381740.0, "tags": ["a", "b"]},
            {"name": "Andorra", "capital": "Andorra la Vella", "population": 84000, "area_km2": 468.0, "tags": []}]
    (p,) = write_all(rows, tmp_path, "countries", ["xlsx"])
    ws = openpyxl.load_workbook(p).active
    assert [c.value for c in ws[1]] == ["name", "capital", "population", "area_km2", "tags"]
    assert [c.value for c in ws[2]] == ["Algeria", "Algiers", 34586184, 2381740.0, "a|b"]
    assert isinstance(ws["C2"].value, int) and ws.freeze_panes == "A2" and ws[1][0].font.bold
