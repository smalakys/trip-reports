import datetime as dt

import numpy as np
import pytest

from tripreports.document import rich
from tripreports.gpxstats import gain_loss
from tripreports.i18n import NBSP, Locale
from tripreports.schema import Trip, json_schema, resolve


def test_rich_text():
    assert rich("a **b** *c*\n\nsecond") == [
        [{"t": "a ", "b": False, "i": False}, {"t": "b", "b": True, "i": False},
         {"t": " ", "b": False, "i": False}, {"t": "c", "b": False, "i": True}],
        [{"t": "second", "b": False, "i": False}],
    ]


def test_gain_loss_ignores_noise():
    rng = np.random.default_rng(0)
    flat = 3000 + rng.normal(0, 0.8, 500)
    up, down = gain_loss(flat)
    assert up < 25 and down < 25   # raw noise barely registers; ~1000 m of it would without the threshold
    ramp = np.linspace(1000, 2000, 400) + rng.normal(0, 0.8, 400)
    up, down = gain_loss(ramp)
    assert up == pytest.approx(1000, abs=15) and down < 15


def test_number_and_date_formats():
    lt, en = Locale("lt"), Locale("en")
    assert lt.num(4248) == f"4{NBSP}248" and lt.num(60.1, 1) == "60,1"
    assert en.num(4248) == "4,248" and en.num(60.1, 1) == "60.1"
    assert lt.gain(1555) == f"+1{NBSP}555{NBSP}m" and en.gain(-823) == f"\u2212823{NBSP}m"
    a, b = dt.date(2025, 8, 10), dt.date(2025, 8, 14)
    assert lt.date_range(a, b) == en.date_range(a, b) == "2025-08-10 – 2025-08-14"   # ISO, every language
    assert en.duration(dt.timedelta(hours=7, minutes=5)) == "7:05"                     # h:mm
    assert [lt.days(n) for n in (1, 5, 11, 21)] == [f"{n}".join(["", s]) for n, s in
        ((1, " dieną"), (5, " dienas"), (11, " dienų"), (21, " dieną"))]


def test_tokens_resolve_for_both_modes():
    from tripreports.theme import load_theme, px_to_pt, typst_font

    light, dark = load_theme(), load_theme(mode="dark")
    assert light["colors"]["series-1"] == light["colors"]["brand"] == "#fc4c02"   # alias followed
    assert light["colors"]["ink"] != dark["colors"]["ink"]
    assert light["colors"]["brand"] == dark["colors"]["brand"]
    assert px_to_pt("16px") == 12.0 and light["type"]["body"]["size"] == 12.0
    assert typst_font("Barlow Semi Condensed") == ("Barlow", 87.5)
    assert typst_font("Barlow Condensed") == ("Barlow", 75.0)
    with pytest.raises(ValueError):
        load_theme(mode="sepia")


def test_localised_text_fallbacks():
    assert resolve({"lt": "a", "en": "b"}, "en") == "b"
    assert resolve({"lt": "a"}, "en", ["lt"]) == "a"
    assert resolve("plain", "en") == "plain" and resolve(None, "en") == ""


def test_trip_requires_both_lat_and_lon():
    base = dict(title="t", cover={"image": "c.jpg"}, start_date="2025-01-01", end_date="2025-01-02",
                region="r", participants=[{"name": "n"}])
    Trip.model_validate({**base, "peaks": [{"name": "p", "elevation_m": 4000, "lat": 1, "lon": 2}]})
    with pytest.raises(ValueError):
        Trip.model_validate({**base, "peaks": [{"name": "p", "elevation_m": 4000, "lat": 1}]})


def test_committed_schema_is_current():
    import json
    from pathlib import Path

    committed = json.loads((Path(__file__).parents[1] / "schema" / "trip.schema.json").read_text())
    assert committed == json_schema(), "run `make schema`"
