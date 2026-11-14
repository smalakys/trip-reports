"""Locale-aware formatting: numbers, dates, durations, plurals and UI strings."""

from __future__ import annotations

import datetime as dt
import tomllib

from .theme import ASSETS

NBSP = " "
NNBSP = " "
EN_DASH = "–"


class Locale:
    def __init__(self, code: str):
        path = ASSETS / "locales" / f"{code}.toml"
        if not path.exists():
            raise ValueError(f"unsupported language {code!r}; add assets/locales/{code}.toml")
        self.data = tomllib.loads(path.read_text(encoding="utf-8"))
        self.code = code

    # ---- strings -------------------------------------------------------------------------
    def ui(self, key: str) -> str:
        return self.data["ui"][key]

    def fig(self, key: str) -> str:
        return self.data["figure"][key]

    # ---- numbers -------------------------------------------------------------------------
    def num(self, x: float, decimals: int = 0) -> str:
        s = f"{abs(x):,.{decimals}f}"
        s = s.replace(",", "\0").replace(".", self.data["decimal"]).replace("\0", self.data["thousands"])
        return "\u2212" + s if x < 0 and round(abs(x), decimals) != 0 else s

    def metres(self, x: float) -> str:
        return f"{self.num(round(x))}{NBSP}{self.ui('meters')}"

    def km(self, metres: float, decimals: int = 1) -> str:
        return f"{self.num(metres / 1000, decimals)}{NBSP}{self.ui('kilometers')}"

    # ---- dates ---------------------------------------------------------------------------
    def month(self, d: dt.date) -> str:
        return self.data["months_genitive"][d.month - 1]

    def date(self, d: dt.date) -> str:
        if self.code == "lt":
            return f"{d.year}{NBSP}m. {self.month(d)} {d.day}{NBSP}d."
        return f"{d.day} {self.month(d)} {d.year}"

    def short_date(self, d: dt.date) -> str:
        if self.code == "lt":
            return f"{self.month(d).capitalize()} {d.day}{NBSP}d."
        return f"{d.day} {self.month(d)}"

    def date_range(self, a: dt.date, b: dt.date) -> str:
        if a == b:
            return self.date(a)
        if self.code == "lt":
            if (a.year, a.month) == (b.year, b.month):
                return f"{a.year}{NBSP}m. {self.month(a)} {a.day}{EN_DASH}{b.day}{NBSP}d."
            if a.year == b.year:
                return (f"{a.year}{NBSP}m. {self.month(a)} {a.day}{NBSP}d. {EN_DASH} "
                        f"{self.month(b)} {b.day}{NBSP}d.")
            return f"{self.date(a)} {EN_DASH} {self.date(b)}"
        if (a.year, a.month) == (b.year, b.month):
            return f"{a.day}{EN_DASH}{b.day} {self.month(a)} {a.year}"
        if a.year == b.year:
            return f"{a.day} {self.month(a)} {EN_DASH} {b.day} {self.month(b)} {b.year}"
        return f"{self.date(a)} {EN_DASH} {self.date(b)}"

    def clock(self, t: dt.datetime) -> str:
        return t.strftime("%H:%M")

    def duration(self, td: dt.timedelta) -> str:
        minutes = round(td.total_seconds() / 60)
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    def hours(self, td: dt.timedelta) -> str:
        return f"{round(td.total_seconds() / 3600)}{NBSP}{self.ui('hours_short')}"

    # ---- plurals -------------------------------------------------------------------------
    def days(self, n: int) -> str:
        f = self.data["figure"]
        if self.code == "lt":
            if n % 10 == 1 and n % 100 != 11:
                return f["days_one"].format(n=n)
            if n % 10 != 0 and not 11 <= n % 100 <= 19:
                return f["days_many"].format(n=n)
            return f["days_many_gen"].format(n=n)
        return (f["days_one"] if n == 1 else f["days_many"]).format(n=n)
