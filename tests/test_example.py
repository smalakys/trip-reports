"""End-to-end checks on the synthetic example. If these pass, the repository works."""

import datetime as dt

import pytest
from pypdf import PdfReader


def test_pdf_is_built_in_both_languages(built):
    for lang, res in built.items():
        assert res.pdf.exists() and res.pdf.stat().st_size > 50_000, lang
        assert 12 <= len(PdfReader(res.pdf).pages) <= 24, lang


def test_text_is_localised(built):
    text = {lang: "".join(p.extract_text() for p in PdfReader(res.pdf).pages) for lang, res in built.items()}
    assert "Bendrieji duomenys" in text["lt"] and "Aušros viršūnė" in text["lt"]
    assert "General information" in text["en"] and "The Dawn Traverse" in text["en"]
    assert "General information" not in text["lt"]


def test_no_warnings(built):
    assert built["lt"].warnings == []


def test_stats_match_the_synthetic_route(built):
    an = built["lt"].analysis
    assert len(an.days) == 5
    t = an.totals
    assert 55_000 < t["distance_m"] < 65_000
    assert 3_700 < t["ascent_m"] < 4_300
    assert t["max_alt_m"] == pytest.approx(4231, abs=6)
    assert t["min_alt_m"] == pytest.approx(1300, abs=6)
    assert dt.timedelta(hours=45) < t["net_time"] < dt.timedelta(hours=55)


def test_summit_times_are_found_from_the_track(built):
    by_name = {p.name: p for p in built["lt"].analysis.peaks}
    assert all(p.time is not None for p in by_name.values())
    t = by_name["Aušros viršūnė"].time
    assert t.date() == dt.date(2025, 8, 12) and 10 <= t.hour <= 11


def test_nights_are_detected_as_rests(built):
    assert len(built["lt"].analysis.rest_spans) == 4
