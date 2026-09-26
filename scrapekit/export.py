"""Write datasets to CSV, JSON and SQLite."""
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path


def _flat(v):
    return "|".join(map(str, v)) if isinstance(v, list) else v


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig: opens cleanly in Excel
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows({k: _flat(v) for k, v in r.items()} for r in rows)


def write_json(rows: list[dict], path: Path) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def write_sqlite(rows: list[dict], path: Path, table: str) -> None:
    if not rows:
        return
    cols = list(rows[0])
    con = sqlite3.connect(path)
    try:
        con.execute(f'DROP TABLE IF EXISTS "{table}"')
        con.execute(f'CREATE TABLE "{table}" ({", ".join(f"{c!r}" for c in cols)})')
        con.executemany(f'INSERT INTO "{table}" VALUES ({", ".join("?" * len(cols))})',
                        [[_flat(r.get(c)) for c in cols] for r in rows])
        con.commit()
    finally:
        con.close()


def write_all(rows: list[dict], out_dir: Path, name: str, formats: list[str]) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for fmt in formats:
        p = out_dir / f"{name}.{ 'db' if fmt == 'sqlite' else fmt }"
        {"csv": lambda: write_csv(rows, p), "json": lambda: write_json(rows, p),
         "sqlite": lambda: write_sqlite(rows, p, name)}[fmt]()
        written.append(p)
    return written
