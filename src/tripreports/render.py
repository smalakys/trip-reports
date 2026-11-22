"""ReportLab renderer: turns the document model (document.py) into the PDF.

Layout follows a classic technical-report grid: a flat title page, 24-26 pt chapter titles,
justified 9 pt text, bold run-in labels, tables with a hairline under the header and a
heavier rule at the bottom, figures with a finding as title, a small source line and a caption.
Colours come from the resolved theme (design tokens), so light and dark builds differ only in
token values. All sizes are in points.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from reportlab.graphics import renderPDF
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents
from svglib.svglib import svg2rlg

from .theme import FONTS_DIR

BODY = "Barlow"
SEMI = "Barlow-SemiBold"
LIGHT = "Barlow-Light"
DISPLAY = "BarlowCondensed-Bold"
NUM = "BarlowSemiCondensed-SemiBold"

_FONT_FILES = {
    "Barlow": "Barlow-Regular.ttf", "Barlow-Italic": "Barlow-Italic.ttf",
    "Barlow-Medium": "Barlow-Medium.ttf", "Barlow-SemiBold": "Barlow-SemiBold.ttf",
    "Barlow-Bold": "Barlow-Bold.ttf", "Barlow-BoldItalic": "Barlow-BoldItalic.ttf",
    "Barlow-Light": "Barlow-Light.ttf", "BarlowCondensed-Bold": "BarlowCondensed-Bold.ttf",
    "BarlowSemiCondensed-Medium": "BarlowSemiCondensed-Medium.ttf",
    "BarlowSemiCondensed-SemiBold": "BarlowSemiCondensed-SemiBold.ttf",
}


def register_fonts() -> None:
    for name, file in _FONT_FILES.items():
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(FONTS_DIR / file)))
    pdfmetrics.registerFontFamily("Barlow", normal="Barlow", bold="Barlow-SemiBold",
                                  italic="Barlow-Italic", boldItalic="Barlow-BoldItalic")


# --------------------------------------------------------------------------------------------
# Styles
# --------------------------------------------------------------------------------------------

@dataclass
class Palette:
    ink: Color
    muted: Color
    line: Color
    rule: Color          # table and divider rules
    accent: Color        # accent-text: small orange text
    brand: Color
    ski: Color           # series-2 (glacier blue): ski mountaineering grade badges
    action: Color
    on_action: Color
    page: Color
    inverse: Color
    on_inverse: Color
    chart_grid: Color
    surface_200: Color
    flags: tuple[Color, Color, Color]


def palette(theme: dict) -> Palette:
    c = theme["colors"]
    h = lambda n: HexColor(c[n][:7])  # noqa: E731 (strip any alpha)
    return Palette(
        ink=h("ink"), muted=h("ink-muted"), line=h("line"), rule=h("ink"), accent=h("accent-text"),
        brand=h("brand"), ski=h("series-2"), action=h("action"), on_action=h("on-action"), page=h("surface-000"),
        inverse=h("surface-inverse"), on_inverse=h("ink-inverse"), chart_grid=h("chart-grid"),
        surface_200=h("surface-200"),
        flags=(h("flag-yellow"), h("flag-green"), h("flag-red")),
    )


def make_styles(pal: Palette, lang: str, justify: bool) -> dict[str, ParagraphStyle]:
    hyph = {"lt": "lt", "en": "en_GB"}.get(lang)
    base = dict(fontName=BODY, textColor=pal.ink, hyphenationLang=hyph, allowWidows=0, allowOrphans=0,
                splitLongWords=1)
    body = ParagraphStyle("body", fontSize=10, leading=13.6, alignment=TA_JUSTIFY if justify else TA_LEFT,
                          spaceAfter=8, **base)
    s = {"body": body}
    s["h1"] = ParagraphStyle("h1", parent=body, fontName=BODY, fontSize=28, leading=32, alignment=TA_LEFT,
                             spaceAfter=14, keepWithNext=1, hyphenationLang=None)
    s["h2"] = ParagraphStyle("h2", parent=body, fontName=SEMI, fontSize=16, leading=20, alignment=TA_LEFT,
                             spaceBefore=16, spaceAfter=6, keepWithNext=1, hyphenationLang=None)
    s["h3"] = ParagraphStyle("h3", parent=body, fontName=SEMI, fontSize=12, leading=15, alignment=TA_LEFT,
                             spaceBefore=10, spaceAfter=2, keepWithNext=1, hyphenationLang=None)
    s["bullet"] = ParagraphStyle("bullet", parent=body, leftIndent=12, spaceAfter=2.5, alignment=TA_LEFT)
    s["cell"] = ParagraphStyle("cell", parent=body, fontSize=9.5, leading=11.6, alignment=TA_LEFT,
                               spaceAfter=0, hyphenationLang=None)
    s["cell_r"] = ParagraphStyle("cell_r", parent=s["cell"], alignment=TA_RIGHT)
    s["cell_h"] = ParagraphStyle("cell_h", parent=s["cell"], fontName=SEMI)
    s["cell_hr"] = ParagraphStyle("cell_hr", parent=s["cell_h"], alignment=TA_RIGHT)
    s["cell_k"] = ParagraphStyle("cell_k", parent=s["cell"], fontName=SEMI, textColor=pal.accent)
    s["cell_b"] = ParagraphStyle("cell_b", parent=s["cell"], fontName=SEMI)
    s["cell_br"] = ParagraphStyle("cell_br", parent=s["cell_b"], alignment=TA_RIGHT)
    s["cell_m"] = ParagraphStyle("cell_m", parent=s["cell"], textColor=pal.muted)        # greyed-out row
    s["cell_mk"] = ParagraphStyle("cell_mk", parent=s["cell_m"], fontName=SEMI)
    s["caption"] = ParagraphStyle("caption", parent=body, fontSize=9.5, leading=12, alignment=TA_LEFT,
                                  textColor=pal.muted, spaceBefore=2, spaceAfter=0, hyphenationLang=None)
    s["fig_title"] = ParagraphStyle("fig_title", parent=body, fontName=SEMI, fontSize=14, leading=17,
                                    alignment=TA_LEFT, spaceAfter=1, keepWithNext=1, hyphenationLang=None)
    s["fig_sub"] = ParagraphStyle("fig_sub", parent=body, fontSize=10.5, leading=13, alignment=TA_LEFT,
                                  textColor=pal.muted, spaceAfter=5, keepWithNext=1, hyphenationLang=None)
    s["source"] = ParagraphStyle("source", parent=body, fontName="Barlow-Italic", fontSize=7, leading=9,
                                 alignment=TA_LEFT, textColor=pal.muted, spaceBefore=2, spaceAfter=2,
                                 hyphenationLang=None)
    s["toc1"] = ParagraphStyle("toc1", parent=body, fontName=SEMI, fontSize=11, leading=13.5, alignment=TA_LEFT,
                               spaceBefore=9, spaceAfter=0, hyphenationLang=None)
    s["toc2"] = ParagraphStyle("toc2", parent=body, fontSize=10, leading=12.5, alignment=TA_LEFT,
                               leftIndent=14, spaceBefore=3, spaceAfter=0, hyphenationLang=None)
    return s


# --------------------------------------------------------------------------------------------
# Flowables
# --------------------------------------------------------------------------------------------

class Heading(Paragraph):
    """A heading that registers itself in the contents and the PDF outline.

    """

    def __init__(self, text, style, level, key, toc_text, prefix: str = ""):
        super().__init__(text, style)
        self.toc_level, self.toc_key, self.toc_text = level, key, toc_text
        self.toc_prefix = prefix

    def draw(self):
        super().draw()


class BulletItem(Paragraph):
    """A list item with a small square bullet centred on the first line's x-height."""

    def __init__(self, text, style, color: Color, size: float = 2.8):
        super().__init__(text, style)
        self.bullet_color, self.bullet_size = color, size

    def draw(self):
        super().draw()
        st = self.style
        baseline = self.height - pdfmetrics.getAscent(st.fontName, st.fontSize)
        mid = baseline + st.fontSize * 0.27          # vertical middle of lowercase letters
        c = self.canv
        c.setFillColor(self.bullet_color)
        c.rect(1.5, mid - self.bullet_size / 2, self.bullet_size, self.bullet_size, stroke=0, fill=1)


class GradeBadge(Flowable):
    """A route's grade as a pill: grading system in small caps, then the grade as written."""

    def __init__(self, grade: str, system: str, key: bool, pal: Palette, on_dark: bool = False, ski: bool = False):
        super().__init__()
        self.grade, self.system, self.key, self.pal, self.on_dark = grade, system.upper(), key, pal, on_dark
        self.ski = ski
        self.h = 14.0
        self.sys_w = pdfmetrics.stringWidth(self.system, SEMI, 5.5) if system else 0
        self.grade_w = pdfmetrics.stringWidth(grade, NUM, 8)
        self.w = 11 + self.sys_w + (3 if system else 0) + self.grade_w

    def wrap(self, aw, ah):
        return self.w, self.h

    def draw(self):
        c, p = self.canv, self.pal
        if self.ski:
            fill, stroke, fg, sysc = p.ski, p.ski, p.on_action, p.on_action
        elif self.key:
            fill, stroke, fg, sysc = p.action, p.action, p.on_action, p.on_action
        else:
            fill = None if self.on_dark else p.page
            stroke = p.on_inverse if self.on_dark else p.muted
            fg = p.on_inverse if self.on_dark else p.ink
            sysc = fg
        c.setLineWidth(0.6)
        c.setStrokeColor(stroke)
        if fill is not None:
            c.setFillColor(fill)
        c.roundRect(0, 0, self.w, self.h, self.h / 2, stroke=1, fill=1 if fill is not None else 0)
        x = 5.5
        if self.system:
            c.setFillColor(sysc)
            c.setFont(SEMI, 5.5)
            c.drawString(x, self.h / 2 - 1.9, self.system)
            x += self.sys_w + 3
        c.setFillColor(fg)
        c.setFont(NUM, 8)
        c.drawString(x, self.h / 2 - 2.8, self.grade)


class Vector(Flowable):
    """An SVG figure drawn as vector graphics at a given width."""

    def __init__(self, svg_path: Path, width: float, under: Path | None = None):
        super().__init__()
        self.under = under
        d = svg2rlg(str(svg_path))
        s = width / d.width
        d.scale(s, s)
        d.width, d.height = d.width * s, d.height * s
        self.drawing, self.width, self.height = d, d.width, d.height

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        if self.under is not None:
            self.canv.drawImage(str(self.under), 0, 0, self.width, self.height)
        renderPDF.draw(self.drawing, self.canv, 0, 0)


# --------------------------------------------------------------------------------------------
# Content helpers
# --------------------------------------------------------------------------------------------

def markup(text: str) -> str:
    return escape(text).replace("\n", "<br/>")


def runs_markup(paras: list[list[dict]]) -> list[str]:
    out = []
    for para in paras:
        parts = []
        for r in para:
            t = escape(r["t"])
            if r["b"]:
                t = f"<b>{t}</b>"
            if r["i"]:
                t = f"<i>{t}</i>"
            parts.append(t)
        out.append("".join(parts))
    return out


def crop_to_fill(src: Path, dst: Path, w: float, h: float) -> Path:
    """Centre-crop a JPEG to the aspect ratio w:h."""
    with PILImage.open(src) as im:
        iw, ih = im.size
        target = w / h
        if iw / ih > target:
            nw = round(ih * target)
            box = ((iw - nw) // 2, 0, (iw - nw) // 2 + nw, ih)
        else:
            nh = round(iw / target)
            box = (0, (ih - nh) // 2, iw, (ih - nh) // 2 + nh)
        im.crop(box).save(dst, "JPEG", quality=88, optimize=True)
    return dst


# --------------------------------------------------------------------------------------------
# Document
# --------------------------------------------------------------------------------------------

class Report(BaseDocTemplate):
    def __init__(self, path: str, doc: dict, build_dir: Path):
        self.d = doc
        self.theme = doc["theme"]
        self.pal = palette(self.theme)
        self.build_dir = build_dir
        pg = self.theme["page"]
        self.W, self.H = pg["width_mm"] * mm, pg["height_mm"] * mm
        self.ml, self.mr = pg["margin_left_mm"] * mm, pg["margin_right_mm"] * mm
        self.mt, self.mb = pg["margin_top_mm"] * mm, pg["margin_bottom_mm"] * mm
        self.tw = self.W - self.ml - self.mr
        super().__init__(path, pagesize=(self.W, self.H), leftMargin=self.ml, rightMargin=self.mr,
                         topMargin=self.mt, bottomMargin=self.mb, title=doc["meta"]["title"],
                         author=doc["meta"]["author"], subject=doc["cover"]["kind"], invariant=1,
                         creator="tripreports")
        body_frame = Frame(self.ml, self.mb, self.tw, self.H - self.mt - self.mb, id="body",
                           leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        cover_frame = Frame(0, 0, 1, 1, id="cover")
        self.addPageTemplates([
            PageTemplate("cover", frames=[cover_frame], onPage=self._cover_page, autoNextPageTemplate="body"),
            PageTemplate("body", frames=[body_frame], onPage=self._body_page),
        ])
        self.styles = make_styles(self.pal, doc["lang"], bool(self.theme["text"]["justify"]))
        self._n = 0

    # ---- page furniture --------------------------------------------------------------------
    def _background(self, c) -> None:
        c.setFillColor(self.pal.page)
        c.rect(0, 0, self.W, self.H, stroke=0, fill=1)

    def _body_page(self, c, doc) -> None:
        c.saveState()
        self._background(c)
        c.setFillColor(self.pal.muted)
        c.setFont(BODY, 6)
        c.drawString(self.ml, self.H - 43, f"{self.d['cover']['association']} · {self.d['cover']['kind']}")
        c.setFillColor(self.pal.muted)
        title = self.d["meta"]["title"]
        num = str(doc.page)
        c.drawRightString(self.W - self.mr, 29, num)
        c.drawRightString(self.W - self.mr - pdfmetrics.stringWidth(num, BODY, 6) - 10, 29, title)
        c.restoreState()

    def _cover_page(self, c, doc) -> None:
        cv, p = self.d["cover"], self.pal
        c.saveState()
        c.setFillColor(p.inverse)
        c.rect(0, 0, self.W, self.H, stroke=0, fill=1)
        photo_h = self.H * 0.46
        crop = crop_to_fill(self.build_dir / cv["image"], self.build_dir / "assets" / "cover-crop.jpg",
                            self.W, photo_h)
        c.drawImage(str(crop), 0, self.H - photo_h, self.W, photo_h)
        x, top = self.ml, self.H - photo_h

        # association band: a small caps line under the photo
        y = top - 38
        c.setFillColor(p.on_inverse)
        c.setFont(SEMI, 6)
        c.drawString(x, y + 1.5, f"{cv['association']} · {cv['kind']}".upper())

        # Title (bold) and subtitle (light) fill the space between the band and the numbers;
        # their type steps down until they fit.
        stats_y = 150
        gap = 18   # space between the title and the subtitle: more than the title's own line gap
        avail = (y - 20) - (stats_y + 46) - (46 if cv["badges"] else 0) - gap
        title = sub = None
        for t_size, s_size in ((46, 24), (40, 21), (34, 18), (30, 16), (26, 14)):
            title = Paragraph(markup(cv["title"]), ParagraphStyle(
                "ct", fontName=DISPLAY, fontSize=t_size, leading=t_size * 1.02, textColor=p.on_inverse))
            # break the subtitle only at its dashes, never inside a name such as "Mont Blanc"
            sub_text = " – ".join(part.replace(" ", "\u00a0") for part in cv["subtitle"].split(" – "))
            sub = Paragraph(markup(sub_text), ParagraphStyle(
                "cs", fontName=LIGHT, fontSize=s_size, leading=s_size * 1.2, textColor=p.on_inverse)
            ) if cv["subtitle"] else None
            th = title.wrap(self.tw, 400)[1]
            sh = sub.wrap(self.tw, 400)[1] if sub else 0
            if th + sh <= avail:
                break
        y -= 30
        title.drawOn(c, x, y - th)
        y -= th
        if sub:
            sub.drawOn(c, x, y - gap - sh)
            y -= gap + sh
        # grades
        if cv["badges"]:
            y -= 14
            bx = x
            for b in cv["badges"]:
                gb = GradeBadge(b["grade"], b["system"], b["key"], p, on_dark=True)
                gb.drawOn(c, bx, y - 14)
                bx += gb.w + 6
        # headline numbers
        self._cover_stats(c, x, stats_y, cv["stats"])
        # meta rows (label bold, value regular), as on the classic title page
        c.setFillColor(p.on_inverse)
        my = 94
        for row in cv["meta"]:
            c.setFont(SEMI, 8.5)
            c.drawString(x, my, row["k"])
            c.setFont(BODY, 8.5)
            c.drawString(x + 120, my, row["v"])
            my -= 14
        # wordmark: the tricolour (a 3:5 flag, as tall as the capitals) and the association's name
        # in the display face
        flag_h = pdfmetrics.getFont(DISPLAY).face.capHeight / 1000 * 19
        flag_w = flag_h * 5 / 3
        for i, col in enumerate(p.flags):
            c.setFillColor(col)
            c.rect(x, 36 + flag_h - (i + 1) * flag_h / 3, flag_w, flag_h / 3, stroke=0, fill=1)
        c.setFillColor(p.on_inverse)
        c.setFont(DISPLAY, 19)
        c.drawString(x + flag_w + 10, 36, cv["association"])
        c.restoreState()

    def _cover_stats(self, c, x: float, y: float, stats: list[dict]) -> None:
        p = self.pal
        col_w = self.tw / len(stats)
        for i, s in enumerate(stats):
            cx = x + i * col_w
            if i:
                c.setStrokeColor(p.on_inverse)
                c.setStrokeAlpha(0.3)
                c.setLineWidth(0.5)
                c.line(cx - 8, y - 8, cx - 8, y + 30)
                c.setStrokeAlpha(1)
            c.setFillColor(p.on_inverse)
            c.setFillAlpha(0.72)
            c.setFont(SEMI, 6)
            c.drawString(cx, y + 24, s["label"].upper())
            c.setFillAlpha(1)
            c.setFillColor(p.brand if s["accent"] else p.on_inverse)
            c.setFont(NUM, 22)
            c.drawString(cx, y, s["value"])
            if s["unit"]:
                vw = pdfmetrics.stringWidth(s["value"], NUM, 22)
                c.setFont(BODY, 11)
                c.setFillAlpha(0.72)
                c.setFillColor(p.on_inverse)
                c.drawString(cx + vw + 2, y, s["unit"])
                c.setFillAlpha(1)

    # ---- contents and outline --------------------------------------------------------------
    def afterFlowable(self, flowable) -> None:
        # headings kept together with a table sit inside a KeepTogether: register those too
        for inner in getattr(flowable, "_content", []):
            if isinstance(inner, Heading):
                self._register(inner)
        if isinstance(flowable, Heading):
            self._register(flowable)

    def _register(self, flowable: Heading) -> None:
        if True:
            key = flowable.toc_key
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.toc_text, key, level=flowable.toc_level, closed=False)
            if (flowable.toc_level == 0 or (flowable.toc_level == 1 and not flowable.toc_prefix)) \
                    and flowable.toc_text != self._toc_title:
                self.notify("TOCEntry", (flowable.toc_level, flowable.toc_text, self.page, key))

    # ---- story -----------------------------------------------------------------------------
    def heading(self, text: str, level: int, prefix: str = "", skip_toc: bool = False) -> list:
        self._n += 1
        key = f"h{self._n}"
        style = self.styles[("h1", "h2", "h3")[level]]
        label = escape(text)
        if prefix:
            hexcol = "#" + self.pal.accent.hexval()[2:]
            label = f'<font color="{hexcol}" name="{BODY}">{escape(prefix)}</font>&nbsp;&nbsp;{label}'
        return [Heading(label, style, level, key, (f"{prefix}  {text}" if prefix else text), prefix=prefix)]

    def build_story(self) -> list:
        S = self.styles
        story: list = [NextPageTemplate("body"), PageBreak()]
        self._toc_title = ""
        first = True
        for b in self.d["blocks"]:
            t = b["type"]
            if t == "h1":
                if b["newpage"] and not first:
                    story.append(PageBreak())
                elif not first:
                    story += [CondPageBreak(160), Spacer(1, 26)]
                story += self.heading(b["text"], 0)
                first = False
            elif t == "h3":
                story += self.heading(b["text"], 2)
            elif t == "h2":
                story += self.heading(b["text"], 1, b["prefix"])
            elif t == "paras":
                story += [Paragraph(m, S["body"]) for m in runs_markup(b["paras"])]
            elif t == "labeled":
                for item in b["items"]:
                    label = item["label"]
                    sep = "" if label.endswith((".", ":")) else "."
                    ms = runs_markup(item["paras"])
                    story.append(Paragraph(f"<b>{escape(label + sep)}</b> {ms[0]}", S["body"]))
                    story += [Paragraph(m, S["body"]) for m in ms[1:]]
            elif t == "bullets":
                if b.get("plain"):
                    story += [Paragraph(markup(i), S["body"]) for i in b["items"]]
                else:
                    story += [BulletItem(markup(i), S["bullet"], self.pal.muted) for i in b["items"]]
                    story.append(Spacer(1, 4))
            elif t == "table":
                tbl = self.table(b)
                lead = []          # every heading right above the table (a section and its subsection)
                while story and isinstance(story[-1], Heading):
                    lead.insert(0, story.pop())
                if len(b["rows"]) <= 14:    # short tables never split across pages, nor from their heading
                    story.append(KeepTogether([*lead, Spacer(1, 4), tbl]))
                else:   # a long one starts under its heading and runs on; the heading needs room for a few rows
                    for h in lead:
                        h.keepWithNext = 0
                    story += [CondPageBreak(150), *lead, Spacer(1, 4)] if lead else []
                    story.append(tbl)
                story.append(Spacer(1, 12))
            elif t == "figure":
                story.append(self.figure(b))
            elif t == "figure_group":     # a heading and its map and profile, kept on one page
                if b["newpage"]:
                    story.append(PageBreak())
                head = [*self.heading(b["title"], 1), Spacer(1, 4)] if b["title"] else []
                # flat list: a KeepTogether inside another always reports itself too tall to fit
                story.append(KeepTogether([*head, *[x for f in b["figures"] for x in self.figure_parts(f)]]))
            elif t == "contents":
                if not first:   # right after the title page it already starts a fresh page
                    story.append(PageBreak())
                self._toc_title = b["title"]
                story += self.heading(b["title"], 0)
                first = False
                toc = TableOfContents(dotsMinLevel=-1, rightColumnWidth=24)
                toc.tableStyle = TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0)])
                toc.levelStyles = [S["toc1"], S["toc2"]]
                story.append(toc)
            elif t == "photo_pages":
                story += self.photo_pages(b)
        return story

    # ---- tables ----------------------------------------------------------------------------
    def table(self, b: dict) -> Table:
        S, p = self.styles, self.pal
        cols = b["columns"]
        has_header = any(c["header"] for c in cols)
        data, styles = [], []
        if has_header:
            data.append([Paragraph(markup(c["header"]), S["cell_hr" if c["align"] == "right" else "cell_h"])
                         for c in cols])
        ncols = len(cols)
        r0 = len(data)
        for ri, row in enumerate(b["rows"]):
            r = r0 + ri
            out, ci = [], 0
            for cell in row:
                is_dict = isinstance(cell, dict)
                span = cell.get("span", 1) if is_dict else 1
                right = cols[ci]["align"] == "right"
                if is_dict and cell.get("group"):
                    inner = [Paragraph(f"<b>{markup(cell['text'])}</b>", S["cell"])]
                    cells = [inner[0]]
                    badges = [GradeBadge(bd["grade"], bd["system"], True, p, ski=bd.get("ski", False))
                              for bd in cell.get("badges", [])]
                    cells += badges
                    if cell["note"]:
                        cells.append(Paragraph(markup(cell["note"]), S["caption"]))
                    fs = S["cell"].fontSize
                    widths = [pdfmetrics.stringWidth(cell["text"], SEMI, fs) + 12]
                    widths += [gb.w + 8 for gb in badges]
                    if cell["note"]:
                        widths.append(pdfmetrics.stringWidth(cell["note"], BODY, S["caption"].fontSize) + 14)
                    t = Table([cells], colWidths=widths, hAlign="LEFT")
                    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                                           ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
                    out.append(t)
                    styles += [("SPAN", (ci, r), (ci + span - 1, r)), ("TOPPADDING", (0, r), (-1, r), 10)]
                elif is_dict and cell.get("heading"):    # a route's own row inside a table of its sections
                    out.append(Paragraph(markup(cell["text"]), S["cell_b"]))
                    styles.append(("TOPPADDING", (0, r), (-1, r), 10))
                elif is_dict and cell.get("badges"):
                    gbs = [GradeBadge(bd["grade"], bd["system"], bd["key"], p, ski=bd.get("ski", False))
                           for bd in cell["badges"]]
                    if len(gbs) == 1:
                        out.append(gbs[0])
                    else:
                        bt = Table([gbs], colWidths=[gb.w + 4 for gb in gbs], hAlign="LEFT")
                        bt.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                                                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                                ("TOPPADDING", (0, 0), (-1, -1), 0),
                                                ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
                        out.append(bt)
                elif is_dict and cell.get("badge"):
                    bd = cell["badge"]
                    out.append(GradeBadge(bd["grade"], bd["system"], bd["key"], p, ski=bd.get("ski", False)))
                else:
                    txt = cell["text"] if is_dict else cell
                    bold = is_dict and cell.get("bold")
                    key = b.get("key_first") and ci == 0
                    sty = ("cell_k" if key else ("cell_br" if right else "cell_b")) if (key or bold) else (
                        "cell_r" if right else "cell")
                    if is_dict and cell.get("muted"):
                        sty = "cell_mk" if key else "cell_m"
                    out.append(Paragraph(markup(txt), S[sty]))
                    if span > 1:
                        styles.append(("SPAN", (ci, r), (ci + span - 1, r)))
                out += [""] * (span - 1)
                ci += span
            data.append(out + [""] * (ncols - len(out)))
            if b.get("total_row") and ri == len(b["rows"]) - 1:
                styles.append(("LINEABOVE", (0, r), (-1, r), 0.25, p.rule))
        total_w = sum(c["width"] for c in cols)
        widths = [self.tw * c["width"] / total_w for c in cols]
        ts = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6),
              ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 4.2),
              ("BOTTOMPADDING", (0, 0), (-1, -1), 4.8)]
        if has_header:
            ts += [("LINEBELOW", (0, 0), (-1, 0), 0.25, p.rule), ("VALIGN", (0, 0), (-1, 0), "BOTTOM")]
        else:
            ts.append(("LINEABOVE", (0, 0), (-1, 0), 0.25, p.rule))
        ts.append(("LINEBELOW", (0, -1), (-1, -1), 0.5, p.rule))
        tbl = Table(data, colWidths=widths, repeatRows=1 if has_header else 0, hAlign="LEFT")
        tbl.setStyle(TableStyle(ts + styles))
        return tbl

    # ---- figures and photos ----------------------------------------------------------------
    def figure(self, b: dict) -> KeepTogether:
        return KeepTogether(self.figure_parts(b))

    def figure_parts(self, b: dict) -> list:
        S = self.styles
        parts = [Paragraph(markup(b["headline"]), S["fig_title"]), Paragraph(markup(b["subtitle"]), S["fig_sub"]),
                 Vector(self.build_dir / b["image"], self.tw,
                        under=self.build_dir / b["under"] if b.get("under") else None)]
        if b["source"]:
            parts.append(Paragraph(markup(b["source"]), S["source"]))
        if b["caption"]:
            parts.append(Paragraph(markup(b["caption"]), S["caption"]))
        parts.append(Spacer(1, 14))
        return parts

    def photo_pages(self, b: dict) -> list:
        out: list = []
        for pi, pg in enumerate(b["pages"]):
            if pi:
                out.append(PageBreak())
            for it in pg:
                src = self.build_dir / it["image"]
                w = it["w_mm"] * mm
                if it["h_mm"]:
                    h = it["h_mm"] * mm
                    src = crop_to_fill(src, src.with_name(src.stem + "-crop.jpg"), w, h)
                else:
                    with PILImage.open(src) as im:
                        h = w * im.size[1] / im.size[0]
                img = Image(str(src), width=w, height=h, hAlign="CENTER")
                out.append(KeepTogether([img, Paragraph(markup(it["caption"]), self.styles["caption"]),
                                         Spacer(1, 16)]))
        return out


def render_pdf(doc: dict, out_pdf: Path, build_dir: Path) -> None:
    from reportlab import rl_config

    rl_config.invariant = 1
    register_fonts()
    report = Report(str(out_pdf), doc, build_dir)
    report.multiBuild(report.build_story())
