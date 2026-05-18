"""First-class PDF export — `slide pdf` subcommand backends.

Phase 23 (v1.4): introduced. v1.4-PDF-01..03.

Two backends:

  * `soffice` — delegates to the existing render.py LibreOffice path
    (shells out to `soffice --headless --convert-to pdf`). Default; produces
    pixel-perfect parity with PPTX rendering.

  * `cairo`   — serialises the project's finalized SVG pages directly to a
    multi-page PDF via `cairosvg`. No LibreOffice needed; faster; preserves
    SVG fidelity. Falls back with a clear error if cairosvg is missing.

Quality knob (`quality`): "draft" | "standard" | "print" tunes output DPI for
any embedded raster bitmaps (cairo backend only; soffice ignores it).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, Literal, Optional

from .render import (
    _convert_pptx_to_pdf,
    _run_with_timeout,
    SOFFICE_TIMEOUT_SECONDS,
    render_environment,
)  # noqa: F401

QUALITY_DPI = {"draft": 96, "standard": 150, "print": 300}

Backend = Literal["soffice", "cairo"]


def _list_finalized_svgs(project: Path) -> list[Path]:
    """Return finalized SVG pages, in slide order.

    The slide-skill project contract puts finalized pages in
    `<project>/svg_final/` (see svg_pipeline.finalize_svg).
    """
    final = project / "svg_final"
    if not final.is_dir():
        raise FileNotFoundError(
            f"No finalized SVG pages found at {final}. Run `slide-skill finalize-svg` first."
        )
    pages = sorted(final.glob("*.svg"))
    if not pages:
        raise FileNotFoundError(f"No *.svg files in {final}")
    return pages


def export_pdf_cairo(
    project: Path | str,
    output: Path | str,
    *,
    quality: str = "standard",
) -> Path:
    """Concatenate finalized SVGs into a multi-page PDF using cairosvg."""
    try:
        import cairosvg  # type: ignore[import-not-found]
        from pypdf import PdfMerger, PdfReader  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "cairo backend requires `cairosvg` and `pypdf`. "
            "Install with `pip install cairosvg pypdf`."
        ) from exc

    project = Path(project)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    dpi = QUALITY_DPI.get(quality, 150)
    svg_paths = _list_finalized_svgs(project)

    merger = PdfMerger()
    page_pdfs: list[bytes] = []
    for svg in svg_paths:
        pdf_bytes = cairosvg.svg2pdf(url=str(svg), dpi=dpi)
        page_pdfs.append(pdf_bytes)

    import io
    for buf in page_pdfs:
        merger.append(PdfReader(io.BytesIO(buf)))
    with output.open("wb") as fh:
        merger.write(fh)
    merger.close()
    return output


def export_pdf_soffice(
    pptx_path: Path | str,
    output: Path | str,
) -> Path:
    """Convert a PPTX to PDF via LibreOffice headless."""
    pptx_path = Path(pptx_path)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    env = render_environment()
    if not env.get("ok"):
        raise RuntimeError(
            "LibreOffice not available. Run `slide-skill render-doctor` for details, "
            "or use `--backend cairo` if cairosvg is installed."
        )
    pdf = _convert_pptx_to_pdf(env["soffice"], pptx_path, output.parent)
    if pdf != output:
        pdf.replace(output)
    return output


def export_pdf(
    project_or_pptx: Path | str,
    output: Path | str,
    *,
    backend: Backend = "soffice",
    quality: str = "standard",
) -> Path:
    """Top-level dispatcher."""
    p = Path(project_or_pptx)
    if backend == "cairo":
        if p.is_file() and p.suffix.lower() == ".pptx":
            raise ValueError("cairo backend expects a project directory, not a .pptx file")
        return export_pdf_cairo(p, output, quality=quality)
    elif backend == "soffice":
        if p.is_dir():
            # Caller passed a project; export PPTX from it first.
            from .exporter import export_project
            pptx = export_project(p)
            return export_pdf_soffice(pptx, output)
        return export_pdf_soffice(p, output)
    else:  # pragma: no cover
        raise ValueError(f"Unknown backend: {backend!r}")
