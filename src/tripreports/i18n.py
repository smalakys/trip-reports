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

    def gain(self, x: float) -> str:
        """Elevation gain/loss with an explicit sign: +1 555 m, −823 m."""
        sign = "+" if x > 0 else ""
        return f"{sign}{self.metres(x)}"

    def km(self, metres: float, decimals: int = 1) -> str:
        return f"{self.num(metres / 1000, decimals)}{NBSP}{self.ui('kilometers')}"

    # ---- dates ---------------------------------------------------------------------------
    # Dates are ISO (2025-08-10) in every language; times are 24 h; durations are h:mm.
    def date(self, d: dt.date) -> str:
        return d.isoformat()

    def short_date(self, d: dt.date) -> str:
        return d.isoformat()

    def date_range(self, a: dt.date, b: dt.date) -> str:
        return self.date(a) if a == b else f"{a.isoformat()} {EN_DASH} {b.isoformat()}"

    def clock(self, t: dt.datetime) -> str:
        return t.strftime("%H:%M")

    def duration(self, td: dt.timedelta) -> str:
        minutes = round(td.total_seconds() / 60)
        return f"{minutes // 60}:{minutes % 60:02d}"

    def hours(self, td: dt.timedelta) -> str:
        return f"{round(td.total_seconds() / 3600)}{NBSP}{self.ui('hours_short')}"

    # ---- plurals -------------------------------------------------------------------------
    def plural(self, n: int, word: str) -> str:
        """``n`` with the right form of ``word`` (figure keys ``<word>_one``, ``_many``, ``_many_gen``)."""
        f = self.data["figure"]
        if self.code == "lt":
            if n % 10 == 1 and n % 100 != 11:
                return f[f"{word}_one"].format(n=n)
            if n % 10 != 0 and not 11 <= n % 100 <= 19:
                return f[f"{word}_many"].format(n=n)
            return f[f"{word}_many_gen"].format(n=n)
        return (f[f"{word}_one"] if n == 1 else f[f"{word}_many"]).format(n=n)

    def days(self, n: int) -> str:
        return self.plural(n, "days")
