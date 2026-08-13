"""Interactive Eight Confirmations dialogue — captures user design intent before generation.

Provides two modes:
- ``run_interactive()`` — walks through 8 confirmation items via stdin/stdout
- ``run_auto_derive()`` — derives values from spec_lock without interaction
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from .confirmations import EIGHT_CONFIRMATION_KEYS, write_confirmations

_KEY_LABELS = {
    "format": "Canvas Format",
    "page_count": "Page Count",
    "style": "Visual Style / Theme",
    "color_scheme": "Color Scheme",
    "typography": "Typography",
    "image_style": "Image Style",
    "rhythm_pattern": "Rhythm Pattern",
    "outline": "Slide Outline",
}


def propose_values(project_path: Path) -> dict[str, str]:
    """Derive proposed values for all 8 confirmation keys from project state."""
    project = Path(project_path)
    proposals: dict[str, str] = {}

    lock = _load_spec_lock_safe(project)

    # format
    canvas = lock.get("canvas", {}) if lock else {}
    ratio = canvas.get("ratio", "16:9")
    w = canvas.get("width", 1280)
    h = canvas.get("height", 720)
    proposals["format"] = f"{ratio} ({w}x{h})" if w and h else str(ratio)

    # page_count
    source_count = _count_source_headings(project)
    if source_count > 0:
        proposals["page_count"] = str(source_count)
    elif lock and "page_count" in lock:
        proposals["page_count"] = str(lock["page_count"])
    else:
        proposals["page_count"] = "10"

    # style
    if lock and lock.get("theme"):
        proposals["style"] = str(lock["theme"])
    else:
        proposals["style"] = "general"

    # color_scheme
    palette = lock.get("palette", {}) if lock else {}
    if palette:
        accent = palette.get("accent", "")
        bg = palette.get("background", "")
        proposals["color_scheme"] = _summarize_palette(palette)
    else:
        proposals["color_scheme"] = "Default theme palette"

    # typography
    typo = lock.get("typography", {}) if lock else {}
    if typo:
        families = [typo.get(k, "") for k in ("title_family", "body_family") if typo.get(k)]
        proposals["typography"] = ", ".join(families) if families else "Theme defaults"
    else:
        font = (lock or {}).get("font_family", "System default")
        proposals["typography"] = str(font)

    # image_style
    proposals["image_style"] = "Match theme palette, moderate decoration"

    # rhythm_pattern
    rhythm = (lock or {}).get("page_rhythm", ["anchor", "breathing", "dense"])
    if isinstance(rhythm, list):
        proposals["rhythm_pattern"] = " → ".join(rhythm)
    else:
        proposals["rhythm_pattern"] = str(rhythm)

    # outline
    proposals["outline"] = ""

    return proposals


def run_interactive(
    project_path: Path,
    *,
    stdin: object = None,
    stdout: object = None,
) -> dict[str, str]:
    """Walk through 8 confirmation items interactively.

    Each item shows the proposed value and accepts:
    - Enter: accept proposed value
    - 'e': edit (enter new value)
    - 's': skip (empty string)
    """
    _in = stdin or sys.stdin
    _out = stdout or sys.stdout
    project = Path(project_path)

    proposals = propose_values(project)
    confirmed: dict[str, str] = {}

    for key in EIGHT_CONFIRMATION_KEYS:
        label = _KEY_LABELS.get(key, key)
        proposed = proposals.get(key, "")
        _out.write(f"\n## {label}\n")
        _out.write(f"Proposed: {proposed}\n")
        _out.write("[Enter] accept / [e] edit / [s] skip: ")
        _out.flush()

        raw = _in.readline()
        if raw is None:
            raw = ""
        choice = raw.strip().lower()

        if choice == "s":
            confirmed[key] = ""
        elif choice == "e":
            _out.write("New value: ")
            _out.flush()
            new_val = _in.readline()
            confirmed[key] = (new_val or "").strip()
        else:
            confirmed[key] = proposed

    write_confirmations(project, confirmed)
    return confirmed


def run_auto_derive(project_path: Path) -> dict[str, str]:
    """Auto-derive all confirmation values from spec_lock without interaction."""
    project = Path(project_path)
    proposals = propose_values(project)
    write_confirmations(project, proposals)
    return proposals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_spec_lock_safe(project: Path) -> dict | None:
    """Try loading spec_lock; return None on any failure."""
    for name in ("spec_lock.json", "spec_lock.md"):
        path = project / name
        if path.exists():
            try:
                from .spec_lock_reader import load_spec_lock
                return load_spec_lock(project)
            except Exception:
                return None
    return None


def _count_source_headings(project: Path) -> int:
    """Count markdown headings in source files to estimate page count."""
    sources_dir = project / "sources"
    if not sources_dir.is_dir():
        return 0
    count = 0
    for md_file in sources_dir.glob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
            count += sum(1 for line in text.splitlines() if line.strip().startswith("#"))
        except OSError:
            continue
    return count


def _summarize_palette(palette: dict) -> str:
    """Produce a human-readable summary of a color palette."""
    accent = palette.get("accent", "")
    bg = palette.get("background", "")
    parts = []
    if accent:
        parts.append(f"{accent} accent")
    if bg:
        parts.append(f"{bg} background")
    secondary = palette.get("secondary_accent", "")
    if secondary:
        parts.append(f"{secondary} secondary")
    return ", ".join(parts) if parts else "Theme palette"
