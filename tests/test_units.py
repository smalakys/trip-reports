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
    assert rich("apie 6980\u00a0m,\n  toliau") == [[{"t": "apie 6980\u00a0m, toliau", "b": False, "i": False}]]


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
    from tripreports.theme import load_theme, px_to_pt

    light, dark = load_theme(), load_theme(mode="dark")
    assert light["colors"]["series-1"] == light["colors"]["brand"] == "#fc4c02"   # alias followed
    assert light["colors"]["ink"] != dark["colors"]["ink"]
    assert light["colors"]["brand"] == dark["colors"]["brand"]
    assert px_to_pt("16px") == 12.0 and light["type"]["body"]["size"] == 12.0
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


def test_expedition_days_cover_the_base_camp_stay():
    from tripreports.analysis import expedition_days
    from tripreports.gpxstats import DayStats

    d = dt.date
    trip = Trip.model_validate({
        "title": "t", "cover": {"image": "c.jpg"}, "start_date": "2026-07-10", "end_date": "2026-07-20",
        "region": "r", "base_camp": {"altitude_m": 4350, "arrival": "2026-07-14", "departure": "2026-07-18"},
        "accommodation": [{"date": "2026-07-15", "place": "C2", "altitude_m": 5600},
                          {"date": "2026-07-16", "place": "C2", "altitude_m": 5600}],
        "days": [{"date": "2026-07-14", "title": "walk", "text": ".", "high_point_m": 5100}],
    })
    t0 = dt.datetime(2026, 7, 15, 6)
    climb = DayStats(d(2026, 7, 15), dt.timedelta(hours=7), 6000, 1300, 50, 4330, 5640, t0, t0, 5600)
    days = expedition_days(trip, [climb])
    assert [x.date.day for x in days] == [14, 15, 16, 17, 18]
    assert [x.night_m for x in days] == [4350, 5600, 5600, 4350, None]   # nothing after departure
    walk, up, rest, down, home = days
    assert (walk.low_m, walk.high_m) == (4350, 5100)                    # untracked: diary high point
    assert (up.low_m, up.high_m) == (4330, 5640)                         # tracked day: the track
    assert (rest.low_m, rest.high_m) == (5600, 5600)                     # a whole day in camp
    assert (down.low_m, down.high_m) == (4350, 5600)                     # untracked: the two nights
    assert (home.low_m, home.high_m) == (4350, 4350)
    # each day starts where the night before was and ends where the night after is
    assert [(x.open_m, x.close_m) for x in days] == [(4350, 4350), (4350, 5600), (5600, 5600),
                                                     (5600, 4350), (4350, 4350)]
    # filled up to the high camp (walk, climb, day in camp), empty on the way down and at base camp
    from tripreports.plots import day_filled
    assert [day_filled(x, 4350) for x in days] == [True, True, True, False, False]


def test_rest_days_are_known_from_the_nights():
    from tripreports.analysis import resting

    trip = Trip.model_validate({
        "title": "t", "cover": {"image": "c.jpg"}, "start_date": "2026-07-10", "end_date": "2026-07-20",
        "region": "r", "base_camp": {"altitude_m": 4350, "arrival": "2026-07-14", "departure": "2026-07-18"},
        "accommodation": [{"date": "2026-07-15", "place": "C2", "altitude_m": 5600},
                          {"date": "2026-07-16", "place": "C2", "altitude_m": 5600}],
    })
    d = dt.date
    # arrival, up to C2, a day in C2, down, departure, after: only the day in C2 is a rest day
    assert [resting(trip, d(2026, 7, n)) for n in (14, 15, 16, 17, 18, 19)] == [
        False, False, True, False, False, False]
