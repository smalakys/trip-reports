"""Label placement and the day axis of the elevation profile."""

import datetime as dt

from tripreports.plots import _day_axis, _flag_layout, _strip_rows


def _boxes(labels, slots):
    return [((xc - w - 3, xc + 3) if side == "right" else (xc - 3, xc + w + 3), xc, row)
            for (xc, w), (row, side) in zip(labels, slots, strict=True)]


def test_leaders_never_cross_labels_when_a_clean_layout_exists():
    # three close summits: greedy placement put the middle label where the last leader crossed it
    labels = [(100.0, 180.0), (300.0, 200.0), (380.0, 150.0)]
    boxes = _boxes(labels, _flag_layout(labels, left_limit=0.0))
    for (x0, x1), _, row in boxes:
        for _, oxc, orow in boxes:
            if orow > row:
                assert not x0 <= oxc <= x1, "a higher label's leader runs through a lower label"
    rows = [row for *_, row in boxes]
    for i, ((a0, a1), _, ra) in enumerate(boxes):
        for (b0, b1), _, rb in boxes[i + 1:]:
            assert ra != rb or a1 < b0 or b1 < a0, "labels in one row overlap"
    assert max(rows) <= 1


def test_day_axis_labels_rest_days_and_marks_midnights():
    # track from the 3rd 07:42 to the 6th 16:26 with nothing recorded on the 4th (a rest day)
    labelled, midnights = _day_axis(dt.datetime(2026, 8, 3, 7, 42), dt.datetime(2026, 8, 6, 16, 26))
    assert [d.day for d, _ in labelled] == [3, 4, 5, 6]
    assert dict(labelled)[dt.date(2026, 8, 4)] == dt.datetime(2026, 8, 4, 12, 0)
    assert midnights == [dt.datetime(2026, 8, d) for d in (4, 5, 6)]
    # a sliver of a day at the end is not labelled, but its midnight is still drawn
    labelled, midnights = _day_axis(dt.datetime(2026, 8, 3, 8), dt.datetime(2026, 8, 4, 1))
    assert [d.day for d, _ in labelled] == [3] and midnights == [dt.datetime(2026, 8, 4)]


def test_rest_labels_that_would_overlap_go_to_another_row():
    # three labels on top of each other take three rows; one far away goes back to the first
    assert _strip_rows([(100, 160), (150, 210), (155, 215), (400, 450)]) == [0, 1, 2, 0]
    assert _strip_rows([(100, 160), (170, 230)]) == [0, 0]
