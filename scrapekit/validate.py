"""Data-quality checks run on every dataset before it is written.

A scraper that silently returns empty strings when a site changes its HTML is
worse than one that crashes. These rules turn silent breakage into a report.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class Rule:
    field: str
    kind: str                     # "required" | "range" | "type"
    arg: object = None


@dataclass
class Report:
    rows: int = 0
    issues: list[str] = field(default_factory=list)
    duplicates: int = 0
    empty_rate: dict[str, float] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.issues and self.duplicates == 0

    def summary(self) -> str:
        lines = [f"rows: {self.rows}", f"duplicates: {self.duplicates}"]
        bad = {k: v for k, v in self.empty_rate.items() if v > 0}
        if bad:
            lines.append("empty fields: " + ", ".join(f"{k} {v:.0%}" for k, v in sorted(bad.items())))
        lines += [f"ISSUE: {i}" for i in self.issues[:20]]
        if len(self.issues) > 20:
            lines.append(f"... and {len(self.issues) - 20} more issues")
        lines.append("RESULT: " + ("PASS" if self.ok else "FAIL"))
        return "\n".join(lines)


BOOK_RULES = [
    Rule("upc", "required"), Rule("title", "required"), Rule("category", "required"),
    Rule("price_incl_tax", "range", (0.01, 10_000)), Rule("rating", "range", (1, 5)),
    Rule("in_stock", "range", (0, 100_000)), Rule("url", "required"),
]
QUOTE_RULES = [Rule("text", "required"), Rule("author", "required"), Rule("tags", "type", list)]


def validate(rows: list[dict], rules: list[Rule], key: str | tuple[str, ...],
             min_rows: int = 1) -> Report:
    rep = Report(rows=len(rows))
    if len(rows) < min_rows:
        rep.issues.append(f"expected at least {min_rows} rows, got {len(rows)}")

    for i, r in enumerate(rows):
        for rule in rules:
            v = r.get(rule.field)
            if rule.kind == "required" and (v is None or v == ""):
                rep.issues.append(f"row {i}: {rule.field} is empty")
            elif rule.kind == "range":
                lo, hi = rule.arg
                if not isinstance(v, (int, float)) or not lo <= v <= hi:
                    rep.issues.append(f"row {i}: {rule.field}={v!r} outside [{lo}, {hi}]")
            elif rule.kind == "type" and not isinstance(v, rule.arg):
                rep.issues.append(f"row {i}: {rule.field} is {type(v).__name__}, expected {rule.arg.__name__}")

    keys = (key,) if isinstance(key, str) else key
    counts = Counter(tuple(r.get(k) for k in keys) for r in rows)
    rep.duplicates = sum(c - 1 for c in counts.values() if c > 1)

    if rows:
        for f in rows[0]:
            empty = sum(1 for r in rows if r.get(f) in (None, "", []))
            rep.empty_rate[f] = empty / len(rows)
    return rep


def dedupe(rows: list[dict], key: str | tuple[str, ...]) -> list[dict]:
    keys = (key,) if isinstance(key, str) else key
    seen, out = set(), []
    for r in rows:
        k = tuple(r.get(x) for x in keys)
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out
