"""End-to-end checks on the generated sample trip. If these pass, the repository works."""

import datetime as dt

import pytest
from pypdf import PdfReader

from conftest import edit_trip


def _text(pdf) -> str:
    return "".join(p.extract_text() for p in PdfReader(pdf).pages)


def test_pdf_is_built(built):
    res = built["lt"]
    assert res.pdf.exists() and res.pdf.stat().st_size > 50_000
    assert 8 <= len(PdfReader(res.pdf).pages) <= 18


def test_text_is_lithuanian(built):
    text = _text(built["lt"].pdf)
    assert "Bendrieji duomenys" in text and "Aušros grandinė" in text
    assert "Techninė klasė" in text                 # the category pill and the class row
    assert "Turinys" in text and "Santrauka" not in text


def test_no_warnings(built):
    assert built["lt"].warnings == []


def test_stats_match_the_synthetic_route(built):
    an = built["lt"].analysis
    assert len(an.days) == 5
    t = an.totals
    assert 55_000 < t["distance_m"] < 65_000
    assert 3_700 < t["ascent_m"] < 4_300
    assert t["max_alt_m"] == pytest.approx(4231, abs=8)
    assert t["min_alt_m"] == pytest.approx(1300, abs=8)
    assert dt.timedelta(hours=45) < t["net_time"] < dt.timedelta(hours=55)


def test_summit_times_are_found_from_the_track(built):
    by_name = {p.name: p for p in built["lt"].analysis.peaks}
    assert all(p.time is not None for p in by_name.values())
    t = by_name["Aušros viršūnė"].time
    assert t.date() == dt.date(2025, 8, 12) and 10 <= t.hour <= 11


def test_nights_and_stops_are_detected_and_named(built, sample_dir):
    from tripreports.build import label_rests
    from tripreports.schema import load_trip

    trip, _ = load_trip(sample_dir)
    spans = built["lt"].analysis.rest_spans
    labels = label_rests(trip, spans)
    nights = [(s, lab) for s, lab in zip(spans, labels, strict=True) if (s[1] - s[0]) > dt.timedelta(hours=5)]
    assert [lab for _, lab in nights] == ["Alfos trobelė", "Beta trobelė", "Perėjos bivakas", "Gama trobelė"]
    assert "Sidabro prieglauda" in labels          # the named daytime stop


def test_diary_numbers_come_from_the_track(built):
    text = _text(built["lt"].pdf)
    assert "{distance}" not in text and "{ascent}" not in text
    assert "Dienos duomenys:" in text


def test_calibration_scales_every_day(trip_copy):
    from tripreports.build import build_report

    edit_trip(trip_copy, calibration={"distance_km": 70.0, "ascent_m": 5000})
    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    an = res.analysis
    assert an.totals["distance_m"] == pytest.approx(70_000, abs=1)
    assert an.totals["ascent_m"] == pytest.approx(5_000, abs=1)
    assert sum(d.ascent_m for d in an.days) == pytest.approx(5_000, abs=1)    # rows still add up
    assert sum(d.distance_m for d in an.days) == pytest.approx(70_000, abs=1)
    assert an.factors["ascent"] > 1


def test_acclimatisation_chart_is_optional(built, trip_copy):
    from tripreports.build import build_report

    assert not (built["lt"].build_dir / "assets" / "climb-high-sleep-low.svg").exists()
    edit_trip(trip_copy, acclimatisation_chart=True)
    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    assert (res.build_dir / "assets" / "climb-high-sleep-low.svg").exists()


def test_cover_stats_are_configurable(trip_copy):
    from tripreports.build import build_report

    edit_trip(trip_copy, cover_stats=["distance", "net_time"])
    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    first = PdfReader(res.pdf).pages[0].extract_text().upper()
    assert "ATSTUMAS" in first and "GRYNA KOPIMO TRUKMĖ" in first
    assert "\nVIRŠŪNĖS\n" not in first


def test_dark_mode_builds(trip_copy):
    from tripreports.build import build_report

    res = build_report(trip_copy, lang="lt", out=trip_copy / "dark.pdf", mode="dark")
    assert res.pdf.stat().st_size > 50_000


def test_map_tiles_use_the_cache_offline(trip_copy):
    """With a cached basemap next to the trip, `tiles` needs no network."""
    import json

    from PIL import Image

    from tripreports import plots
    from tripreports.analysis import analyse
    from tripreports.build import build_report
    from tripreports.schema import load_trip

    trip, _ = load_trip(trip_copy)
    x0, x1, y0, y1 = plots.map_view(analyse(trip, trip_copy).track).extent
    w, h = x1 - x0, y1 - y0
    extent = [x0 - 0.2 * w, x1 + 0.2 * w, y0 - 0.2 * h, y1 + 0.2 * h]
    Image.new("RGB", (800, 600), (200, 210, 200)).save(trip_copy / "basemap.jpg")
    (trip_copy / "basemap.json").write_text(json.dumps(
        {"source": "topo", "extent": extent, "attribution": "© test tiles"}), encoding="utf-8")
    edit_trip(trip_copy, map={"basemap": "tiles", "tile_source": "topo", "color_by": "none"})
    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    assert res.warnings == []
    assert (res.build_dir / "assets" / "route-map-base.jpg").exists()
    assert "© test tiles" in _text(res.pdf)


def test_clean_gpx_removes_sensor_data(tmp_path):
    from tripreports.cli import main

    src = tmp_path / "in.gpx"
    src.write_text(
        '<?xml version="1.0"?><gpx version="1.1" creator="x" xmlns="http://www.topografix.com/GPX/1/1" '
        'xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1"><trk><trkseg>'
        + "".join(
            f'<trkpt lat="46.{i:03d}" lon="8.{i:03d}"><ele>{1000 + i}</ele><time>2025-08-10T07:{i:02d}:00Z</time>'
            f"<extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>{70 + i}</gpxtpx:hr></gpxtpx:TrackPointExtension>"
            "</extensions></trkpt>" for i in range(10))
        + "</trkseg></trk></gpx>", encoding="utf-8")
    out = tmp_path / "out.gpx"
    assert main(["clean-gpx", str(src), str(out), "--every", "2"]) == 0
    text = out.read_text(encoding="utf-8")
    assert "hr" not in text and "gpxtpx" not in text
    assert text.count("<trkpt") == 6      # every 2nd point of 10, plus the last
