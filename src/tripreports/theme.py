"""Theme loading: design tokens (assets/design/tokens.json) + page settings, light or dark.

Token values are resolved for one mode (aliases like ``"{brand}"`` followed) and lengths are
converted from CSS px to typographic points (1 px = 0.75 pt), so the PDF renderer and the
matplotlib figures read the same numbers.
"""

from __future__ import annotations

import json
import re
import tomllib
from importlib import resources
from pathlib import Path

ASSETS = Path(str(resources.files("tripreports") / "assets"))
FONTS_DIR = ASSETS / "fonts"
TOKENS_PATH = ASSETS / "design" / "tokens.json"

PT_PER_PX = 0.75


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def px_to_pt(value: str | int | float) -> float:
    """'16px' -> 12.0; bare numbers are taken as px."""
    m = re.fullmatch(r"\s*(-?[\d.]+)\s*(px)?\s*", str(value))
    if not m:
        raise ValueError(f"unsupported length {value!r}")
    return float(m.group(1)) * PT_PER_PX


def _resolve_colors(color: dict, mode: str) -> dict[str, str]:
    raw: dict[str, str] = {}
    themes = [t["id"] for t in color["themes"]]
    if mode not in themes:
        raise ValueError(f"unknown mode {mode!r}; the tokens define {themes}")
    for tok in color["tokens"]:
        v = tok["value"]
        raw[tok["name"]] = v if isinstance(v, str) else v.get(mode, v[themes[0]])

    def resolve(name: str, seen: tuple[str, ...] = ()) -> str:
        v = raw[name]
        m = re.fullmatch(r"\{(.+)\}", v)
        if not m:
            return v
        if m.group(1) in seen or m.group(1) not in raw:
            raise ValueError(f"bad colour alias {v!r} in token {name!r}")
        return resolve(m.group(1), (*seen, name))

    return {name: resolve(name) for name in raw}


def _first_family(css: str) -> str:
    return css.split(",")[0].strip().strip('"')


def load_theme(path: str | Path | None = None, mode: str | None = None) -> dict:
    """Return the resolved theme as a plain dict (JSON-serialisable)."""
    settings = tomllib.loads((ASSETS / "theme" / "default.toml").read_text(encoding="utf-8"))
    if path is not None:
        settings = _merge(settings, tomllib.loads(Path(path).read_text(encoding="utf-8")))
    tokens = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    mode = mode or settings["mode"]

    colors = _resolve_colors(tokens["color"], mode)
    colors.update(settings.get("colors", {}))
    fonts = {k: _first_family(v) for k, v in tokens["type"]["families"].items()}

    styles: dict[str, dict] = {}
    for group in tokens["type"]["groups"]:
        for s in group["styles"]:
            lead = px_to_pt(s["lineHeight"])
            styles[s["name"]] = {
                "family": fonts[group["family"]],
                "size": px_to_pt(s["fontSize"]),
                "leading": lead,
                "weight": int(s["fontWeight"]),
                "tracking": px_to_pt(s.get("letterSpacing", "0px")),
            }
    return {
        "mode": mode,
        "colors": colors,
        "fonts": fonts,
        "type": styles,
        "space": {t["name"]: px_to_pt(t["value"]) for t in tokens["spacing"]["tokens"]},
        "radius": {t["name"]: px_to_pt(t["value"]) for t in tokens["radius"]["tokens"]},
        "page": settings["page"],
        "text": settings["text"],
        "images": settings["images"],
        "plots": settings["plots"],
    }


def text_width_mm(theme: dict) -> float:
    page = theme["page"]
    return page["width_mm"] - page["margin_left_mm"] - page["margin_right_mm"]
