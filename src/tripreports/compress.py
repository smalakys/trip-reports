"""A smaller copy of a finished PDF for email and the web, made with Ghostscript.

The report is built once at full quality; this only downsamples the photographs and map to ``ppi``
(200 is indistinguishable on screen and in a normal print) and recompresses them. Text, vector
figures, bookmarks and links are kept.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

WEB_SUFFIX = "-web"


def web_path(pdf: str | Path) -> Path:
    """``report-lt.pdf`` -> ``report-lt-web.pdf``."""
    p = Path(pdf)
    return p.with_name(p.stem + WEB_SUFFIX + p.suffix)


def ghostscript() -> str | None:
    return shutil.which("gs")


def compress_pdf(src: str | Path, dst: str | Path | None = None, ppi: int = 200,
                 quality: float = 0.4) -> Path:
    """Write a smaller copy of ``src`` to ``dst`` (default: ``web_path(src)``) and return its path.

    ``quality`` is Ghostscript's JPEG QFactor: lower is better (0.4 is about JPEG quality 80).
    Raises RuntimeError when Ghostscript is not installed or fails.
    """
    gs = ghostscript()
    if gs is None:
        raise RuntimeError("Ghostscript (gs) is not installed; install it, e.g. `brew install ghostscript`")
    src = Path(src)
    dst = Path(dst) if dst else web_path(src)
    tmp = dst.with_name(dst.name + ".tmp")
    setup = (f"<< /ColorACSImageDict << /QFactor {quality} /Blend 1 /HSamples [1 1 1 1] "
             "/VSamples [1 1 1 1] >> >> setdistillerparams")
    cmd = [gs, "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.6",
           "-dDetectDuplicateImages=true", "-dDownsampleColorImages=true", "-dDownsampleGrayImages=true",
           "-dColorImageDownsampleType=/Bicubic", f"-dColorImageResolution={ppi}",
           f"-dGrayImageResolution={ppi}", "-dColorImageDownsampleThreshold=1.0",
           "-dAutoFilterColorImages=false", "-dColorImageFilter=/DCTEncode", "-dPassThroughJPEGImages=false",
           f"-sOutputFile={tmp}", "-c", setup, "-f", str(src)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Ghostscript failed: {res.stderr.strip() or res.stdout.strip()}")
    tmp.replace(dst)
    return dst
