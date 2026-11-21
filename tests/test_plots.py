"""Label placement on the elevation profile."""

from tripreports.plots import _flag_layout


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
