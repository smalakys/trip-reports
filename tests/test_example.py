"""End-to-end checks on the generated sample trip. If these pass, the repository works."""

import datetime as dt
import json

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
    assert "Turinys" not in text and "Santrauka" not in text   # no table of contents


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


def _gpx(day: int, hr: bool = True) -> str:
    ext = ("<extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>90</gpxtpx:hr></gpxtpx:TrackPointExtension>"
           "</extensions>") if hr else ""
    return ('<?xml version="1.0"?><gpx version="1.1" creator="x" xmlns="http://www.topografix.com/GPX/1/1" '
            'xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1"><trk><trkseg>'
            + "".join(f'<trkpt lat="46.{i:03d}" lon="8.{i:03d}"><ele>{1000 + i}</ele>'
                      f"<time>2025-08-{day:02d}T07:{i:02d}:00Z</time>{ext}</trkpt>" for i in range(5))
            + "</trkseg></trk></gpx>")


def test_merge_gpx_cleans_and_orders_daily_files(tmp_path):
    from tripreports.cli import main
    from tripreports.gpxstats import load_gpx

    for day in (12, 10, 11):      # given out of order on purpose
        (tmp_path / f"day{day}.gpx").write_text(_gpx(day), encoding="utf-8")
    out, keep = tmp_path / "merged.gpx", tmp_path / "days"
    srcs = [str(tmp_path / f"day{d}.gpx") for d in (12, 10, 11)]
    assert main(["merge-gpx", *srcs, str(out), "--keep", str(keep)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "hr" not in text and text.count("<trkpt") == 15
    assert text.index("2025-08-10") < text.index("2025-08-11") < text.index("2025-08-12")
    assert sorted(p.name for p in keep.iterdir()) == ["day10.gpx", "day11.gpx", "day12.gpx"]
    assert "hr" not in (keep / "day10.gpx").read_text(encoding="utf-8")
    assert len(load_gpx(out, "Europe/Zurich")) == 15


def test_several_track_files_get_a_map_and_profile_each(trip_copy):
    import shutil

    import gpxpy
    import gpxpy.gpx

    from tripreports.build import build_report
    from tripreports.gpxstats import load_gpx

    # split the sample track into two files at the start of its fourth day
    gpx = gpxpy.parse((trip_copy / "track.gpx").read_text(encoding="utf-8"))
    pts = [p for t in gpx.tracks for s in t.segments for p in s.points]
    track = load_gpx(trip_copy / "track.gpx", "Europe/Zurich")
    cut = next(i for i, t in enumerate(track.t) if t.date() >= dt.date(2025, 8, 13))
    for name, part in (("a.gpx", pts[:cut]), ("b.gpx", pts[cut:])):
        g = gpxpy.gpx.GPX()
        trk = gpxpy.gpx.GPXTrack()
        seg = gpxpy.gpx.GPXTrackSegment()
        seg.points = part
        trk.segments.append(seg)
        g.tracks.append(trk)
        (trip_copy / name).write_text(g.to_xml(), encoding="utf-8")
    (trip_copy / "track.gpx").unlink()
    edit_trip(trip_copy, gpx=[{"file": "a.gpx", "name": "Pirmoji dalis"}, {"file": "b.gpx", "name": "Antroji dalis"}])
    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    assert res.warnings == []
    assert len(res.analysis.groups) == 2 and len(res.analysis.days) == 5
    assert [len(g.day_start_idx) for g in res.analysis.groups] == [3, 2]
    assets = sorted(p.name for p in (res.build_dir / "assets").glob("*.svg"))
    assert "route-map-1.svg" in assets and "elevation-profile-2.svg" in assets
    text = _text(res.pdf)
    assert "Pirmoji dalis" in text and "Antroji dalis" in text
    shutil.rmtree(res.build_dir)

    # a file marked figures: false still counts in the tables, but gets no map or profile
    edit_trip(trip_copy, gpx=[{"file": "a.gpx", "name": "Pirmoji dalis", "figures": False},
                              {"file": "b.gpx", "name": "Antroji dalis"}])
    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    assert res.warnings == []
    assert len(res.analysis.days) == 5 and [len(g.day_start_idx) for g in res.analysis.groups] == [2]
    assert not (res.build_dir / "assets" / "route-map-2.svg").exists()


def test_nights_table_is_grouped_with_an_intro(trip_copy):
    import yaml

    from tripreports.build import build_report

    data = yaml.safe_load((trip_copy / "trip.yaml").read_text(encoding="utf-8"))
    nights = data["accommodation"]
    for i, night in enumerate(nights):
        night["group"] = "Pirmoji grupė" if i < 2 else "Antroji grupė"
    edit_trip(trip_copy, accommodation=nights, accommodation_intro="Stovyklų žymėjimas paaiškintas čia.")
    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    doc = json.loads((res.build_dir / "data.json").read_text(encoding="utf-8"))
    table = next(b for b in doc["blocks"] if b["type"] == "table" and b["columns"][0]["header"] == "Naktis")
    groups = [r[0]["text"] for r in table["rows"] if isinstance(r[0], dict) and r[0].get("group")]
    assert groups == ["Pirmoji grupė", "Antroji grupė"]
    assert "Stovyklų žymėjimas paaiškintas čia." in _text(res.pdf)


def test_a_base_camp_adds_the_expedition_altitude_chart(built, trip_copy):
    from tripreports.build import build_report

    assert built["lt"].analysis.expedition == []         # no base camp, no chart
    edit_trip(trip_copy, base_camp={"altitude_m": 1300, "arrival": "2025-08-10", "departure": "2025-08-14"})
    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    assert res.warnings == []
    assert len(res.analysis.expedition) == 5
    assert (res.build_dir / "assets" / "altitude-chart.svg").exists()
    text = _text(res.pdf)
    assert "virš bazinės stovyklos" in " ".join(text.split())
    doc = json.loads((res.build_dir / "data.json").read_text(encoding="utf-8"))
    kinds = [b["type"] for b in doc["blocks"]]
    daily = next(i for i, b in enumerate(doc["blocks"]) if b["type"] == "table" and b.get("total_row"))
    assert kinds[daily + 1] == "figure" and doc["blocks"][daily + 1]["image"] == "assets/altitude-chart.svg"

    # with a base camp the daily table lists every day of the stay; days without a track are greyed out
    edit_trip(trip_copy, base_camp={"altitude_m": 1300, "arrival": "2025-08-08", "departure": "2025-08-16"})
    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    doc = json.loads((res.build_dir / "data.json").read_text(encoding="utf-8"))
    table = next(b for b in doc["blocks"] if b["type"] == "table" and b.get("total_row"))
    assert [c["header"] for c in table["columns"][:2]] == ["Data", "Nakvynė"]
    greyed = [r for r in table["rows"] if isinstance(r[0], dict) and r[0].get("muted")]
    assert [r[0]["text"] for r in greyed] == ["2025-08-08", "2025-08-09", "2025-08-15", "2025-08-16"]
    assert [r[1]["text"] for r in greyed] == ["BC", "BC", "BC", ""]          # nothing after departure
    assert [r[2]["text"] for r in greyed] == ["Atvykimas į bazinę stovyklą", "Poilsio diena", "Poilsio diena",
                                              "Išvykimas iš bazinės stovyklos"]
    nights = {r[0]: r[1] for r in table["rows"] if isinstance(r[0], str)}
    assert nights["2025-08-10"] == "Alfos trobelė"                           # from the accommodation entry
    assert not any(b["type"] == "table" and b["columns"][0]["header"] == "Naktis" for b in doc["blocks"])
    assert "truko 9 dienas (2025-08-08 – 2025-08-16)" in " ".join(_text(res.pdf).split())


def test_camps_get_one_table_per_mountain(trip_copy):
    from tripreports.build import build_report

    edit_trip(trip_copy, camps=[
        {"name": "C1", "altitude_m": 3000, "lat": 46.1, "lon": 7.123456789, "group": "Pirmas kalnas",
         "note": "Ant ledyno"},
        {"name": "C2", "altitude_m": 3500, "group": "Pirmas kalnas"},
        {"name": "C1", "altitude_m": 3200, "group": "Antras kalnas", "note": "Po serakais"}])
    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    doc = json.loads((res.build_dir / "data.json").read_text(encoding="utf-8"))
    heads = [b["text"] for b in doc["blocks"] if b["type"] == "h3"
             and b["text"] not in ("Komandinė įranga", "Asmeninė įranga")]
    tables = [b for b in doc["blocks"] if b["type"] == "table" and b["columns"][0]["header"] == "Stovykla"]
    assert heads == ["Pirmas kalnas", "Antras kalnas"]          # a subsection per mountain ...
    assert [len(t["rows"]) for t in tables] == [2, 1]          # ... and no heading row in its table
    assert tables[0]["rows"][0][2] == "46.100000, 7.123457"     # dot decimals for any map, 6 places
    assert "Po serakais" in _text(res.pdf)


def test_participant_note_and_former_peak_name(trip_copy):
    import yaml

    from tripreports.build import build_report

    data = yaml.safe_load((trip_copy / "trip.yaml").read_text(encoding="utf-8"))
    data["participants"][0]["note"] = "tik Aušros viršūnė"
    data["peaks"][0]["former_name"] = "Senoji viršūnė"
    edit_trip(trip_copy, participants=data["participants"], peaks=data["peaks"])
    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    text = " ".join(_text(res.pdf).split())
    assert f"{data['participants'][0]['name']} (tik Aušros viršūnė)" in text
    assert "anksčiau – Senoji viršūnė" in text


def test_peak_grades_in_general_info_and_summit_times(trip_copy):
    import yaml

    from tripreports.build import build_report

    data = yaml.safe_load((trip_copy / "trip.yaml").read_text(encoding="utf-8"))
    for peak in data["peaks"]:
        peak.pop("grade", None)
        peak.pop("ski_grade", None)
    data["peaks"][0].update(grade="PD-", grade_system="Alpine", ski_grade="2.3 / E1", ski_grade_system="Toponeige")
    edit_trip(trip_copy, peaks=data["peaks"])
    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    text = " ".join(_text(res.pdf).split())
    assert f"{data['peaks'][0]['name']} (3 987 m) – PD-, slidėmis 2.3 / E1" in text
    assert f"{data['peaks'][1]['name']} (4 105 m) –" not in text


def test_summit_times_name_climbers_only_when_not_everyone_reached_every_summit(trip_copy):
    import yaml

    import pydantic

    from tripreports.build import build_report

    def summit_table(res):
        doc = json.loads((res.build_dir / "data.json").read_text(encoding="utf-8"))
        return next(b for b in doc["blocks"] if b["type"] == "table" and b["columns"][0]["header"] == "Viršūnė")

    data = yaml.safe_load((trip_copy / "trip.yaml").read_text(encoding="utf-8"))
    team = [p["name"] for p in data["participants"]]
    for peak in data["peaks"]:
        peak.pop("climbers", None)
    data["peaks"][1]["climbers"] = team[:1]
    edit_trip(trip_copy, peaks=data["peaks"])
    table = summit_table(build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf"))
    assert "Įkopė" in [c["header"] for c in table["columns"]]
    by_peak = {r[0]: r for r in table["rows"]}
    assert team[0] in by_peak[data["peaks"][1]["name"]]
    assert ", ".join(team) in by_peak[data["peaks"][0]["name"]]       # left out: the whole team

    data["peaks"][1]["climbers"] = team                                  # everyone everywhere: no column
    edit_trip(trip_copy, peaks=data["peaks"])
    table = summit_table(build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf"))
    assert "Įkopė" not in [c["header"] for c in table["columns"]]

    data["peaks"][1]["climbers"] = ["Niekas Nežinomas"]
    edit_trip(trip_copy, peaks=data["peaks"])
    with pytest.raises(pydantic.ValidationError):
        build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")


def test_gpx_note_under_daily_summary(trip_copy):
    from tripreports.build import build_report

    import json

    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    text = " ".join(_text(res.pdf).split())
    assert "matavimo paklaidų" in text
    doc = json.loads((res.build_dir / "data.json").read_text(encoding="utf-8"))
    daily = [b for b in doc["blocks"] if b["type"] == "table" and b.get("total_row")]
    note = " ".join(run["t"] for para in daily[0]["after"] for run in para)
    assert "matavimo paklaidų" in note     # kept on the page with the table, not a loose paragraph
    edit_trip(trip_copy, gpx_note=False)
    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    assert "matavimo paklaidų" not in " ".join(_text(res.pdf).split())


def test_climb_record_and_section_order(built):
    text = " ".join(_text(built["lt"].pdf).split())
    assert "Jonas Jonaitis – vadovas" in text
    assert "Kontaktinė informacija: jonas@example.com" in text   # the author's footnote
    assert "Alpinizmu užsiima dešimt metų" in text
    assert "Maršruto pavadinimas Aušros grandinė" in text
    assert "Šaltiniai Fictional Alpine Club" in text          # a row of the record, not a section
    body = text[text.index("Maršruto informacija"):]
    order = ["Bendrieji duomenys", "Maršruto aprašymas", "Atskirų techninių atkarpų aprašymas", "Maršruto būklė ir įranga maršrute",
             "Pasiruošimas ir logistika", "Taktika", "Įranga", "Komandinė įranga", "Asmeninė įranga",
             "Nakvynės", "Pagalba iš šalies", "Įkopimo eiga", "Meteorologinės sąlygos", "Įkopimo duomenys",
             "Viršūnių pasiekimo laikai", "Dienų santrauka", "Maršruto schema ir aukščio profilis",
             "Pastabos ir rekomendacijos", "Nuotraukos"]
    at = 0
    for heading in order:      # each heading comes after the one before it
        at = body.index(heading, at) + len(heading)


def test_trip_grade_in_general_info(trip_copy):
    from tripreports.build import build_report

    edit_trip(trip_copy, grade="AD+, III")
    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    text = " ".join(_text(res.pdf).split())
    assert "Sudėtingumas AD+, III" in text


def test_kind_note_in_general_info_only(trip_copy):
    from tripreports.build import build_report

    edit_trip(trip_copy, kind="Kalnų žygių klasė", kind_note="nekategorinis žygis slidėmis")
    res = build_report(trip_copy, lang="lt", out=trip_copy / "r.pdf")
    text = " ".join(_text(res.pdf).split())
    assert "Kalnų žygių klasė (nekategorinis žygis slidėmis)" in text
    assert text.count("nekategorinis žygis slidėmis") == 1     # not on the title page pill


def test_web_copy_is_smaller_and_keeps_the_text(built):
    import pytest
    from tripreports.compress import ghostscript

    if ghostscript() is None:
        pytest.skip("Ghostscript not installed")
    import pypdfium2 as pdfium

    res = built["lt"]
    assert res.web_pdf and res.web_pdf.name == "report-lt-web.pdf"
    assert res.web_pdf.stat().st_size < res.pdf.stat().st_size
    full, web = pdfium.PdfDocument(str(res.pdf)), pdfium.PdfDocument(str(res.web_pdf))
    assert len(web) == len(full)
    assert web[0].get_textpage().get_text_range() == full[0].get_textpage().get_text_range()
