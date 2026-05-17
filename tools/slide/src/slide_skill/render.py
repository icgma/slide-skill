"""PPTX rendering helpers for visual QA."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .util import ensure_dir


def render_environment() -> dict:
    soffice = _find_soffice()
    pdftoppm = shutil.which("pdftoppm")
    issues: list[str] = []
    if not soffice:
        issues.append("LibreOffice soffice was not found on PATH or common Windows install paths.")
    if not pdftoppm:
        issues.append("Poppler pdftoppm was not found on PATH.")
    return {
        "ok": not issues,
        "soffice": soffice,
        "pdftoppm": pdftoppm,
        "issues": issues,
    }


def render_environment_report() -> str:
    env = render_environment()
    lines = [
        "# Render Environment",
        "",
        f"status: {'ready' if env['ok'] else 'missing-dependencies'}",
        "",
        f"- soffice: {env['soffice'] or 'not found'}",
        f"- pdftoppm: {env['pdftoppm'] or 'not found'}",
    ]
    if env["issues"]:
        lines.append("")
        lines.append("## Issues")
        lines.extend(f"- {issue}" for issue in env["issues"])
    return "\n".join(lines) + "\n"


# Subprocess timeouts (seconds). Keep generous to allow large decks while
# still preventing indefinite hangs from a wedged LibreOffice / pdftoppm.
SOFFICE_TIMEOUT_SECONDS = 180
PDFTOPPM_TIMEOUT_SECONDS = 120


def _run_with_timeout(cmd: list[str], *, timeout: int, label: str) -> None:
    """subprocess.run wrapper that converts hangs into a typed RuntimeError."""
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"{label} timed out after {timeout}s; the input may be malformed."
        ) from exc


def _convert_pptx_to_pdf(soffice: str, pptx: Path, out_dir: Path) -> Path:
    _run_with_timeout(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(pptx)],
        timeout=SOFFICE_TIMEOUT_SECONDS,
        label="LibreOffice PDF conversion",
    )
    pdf = out_dir / (pptx.stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError(f"LibreOffice did not create expected PDF: {pdf}")
    return pdf


def _render_to_images(
    pptx_path: Path | str,
    output_dir: Path | str,
    *,
    fmt: str,           # "jpeg" or "png"
    dpi: int,
    prefix_name: str,   # output file prefix passed to pdftoppm
) -> Path:
    """Shared PPTX→PDF→images pipeline. Returns the out_dir for the caller to glob."""
    pptx = Path(pptx_path)
    out_dir = ensure_dir(Path(output_dir))
    env = render_environment()
    if not env["ok"]:
        raise RuntimeError("Render dependencies are not ready. Run `slide-skill render-doctor` for details.")
    pdf = _convert_pptx_to_pdf(env["soffice"], pptx, out_dir)
    _run_with_timeout(
        [env["pdftoppm"], f"-{fmt}", "-r", str(dpi), str(pdf), str(out_dir / prefix_name)],
        timeout=PDFTOPPM_TIMEOUT_SECONDS,
        label="pdftoppm image extraction",
    )
    return out_dir


def render_pptx(pptx_path: Path | str, output_dir: Path | str, dpi: int = 150) -> list[Path]:
    out_dir = _render_to_images(pptx_path, output_dir, fmt="jpeg", dpi=dpi, prefix_name="slide")
    return sorted(out_dir.glob("slide-*.jpg"))


def snapshot_pptx(pptx_path: Path | str, output_dir: Path | str, dpi: int = 150) -> list[Path]:
    """Render PPTX to per-slide PNGs with deterministic naming (slide-01.png, etc.)."""
    import re

    out_dir = _render_to_images(pptx_path, output_dir, fmt="png", dpi=dpi, prefix_name="snapshot")
    # Rename pdftoppm output (snapshot-1.png → slide-01.png)
    result: list[Path] = []
    for raw in sorted(out_dir.glob("snapshot-*.png")):
        match = re.search(r"snapshot-(\d+)\.png$", raw.name)
        if match:
            num = int(match.group(1))
            new_path = out_dir / f"slide-{num:02d}.png"
            raw.rename(new_path)
            result.append(new_path)

    return sorted(result)


def _find_soffice() -> str | None:
    found = shutil.which("soffice")
    if found:
        return found
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None
