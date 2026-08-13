"""Unified spec lock reader for slide-skill v4.0.

Reads the project's spec lock from either ``spec_lock.md`` (preferred) or
``spec_lock.json`` (fallback), normalizes the result into a dict with all
12 extended color roles and typography information.

Usage::

    from slide_skill.spec_lock_reader import load_spec_lock

    lock = load_spec_lock(project_path)
    palette = get_palette(lock)        # dict with all 12 roles
    typo    = get_typography(lock)      # TypographySpec
    rhythm  = get_rhythm(lock)          # list[str]
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .themes import (
    TypographySpec,
    derive_extended_palette,
    derive_typography,
    DEFAULT_SIZE_RAMP,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_spec_lock(project_path: Path | str) -> dict[str, Any]:
    """Load and normalize the spec lock for a project.

    Tries ``spec_lock.md`` first (Markdown format), then falls back to
    ``spec_lock.json``.  Returns a normalized dict with:
    - ``palette``: all 12 color roles (missing ones derived)
    - ``typography``: dict with title/body/emphasis/code families + size ramp
    - ``page_rhythm``: list[str]
    - all other original fields preserved

    Raises FileNotFoundError if neither file exists.
    """
    project = Path(project_path)
    md_path = project / "spec_lock.md"
    json_path = project / "spec_lock.json"

    if md_path.is_file():
        raw = _parse_spec_lock_md(md_path)
    elif json_path.is_file():
        raw = json.loads(json_path.read_text(encoding="utf-8"))
    else:
        raise FileNotFoundError(
            f"No spec_lock.md or spec_lock.json found in {project}"
        )

    return _normalize(raw)


def get_palette(lock: dict[str, Any]) -> dict[str, str]:
    """Return the extended 12-role palette from a loaded spec lock."""
    return derive_extended_palette(lock.get("palette", {}))


def get_typography(lock: dict[str, Any]) -> TypographySpec:
    """Return the TypographySpec from a loaded spec lock."""
    typo_data = lock.get("typography")
    if typo_data and isinstance(typo_data, dict):
        return TypographySpec.from_dict(typo_data)
    # Fallback: derive from font_family
    font = lock.get("font_family", "Arial, sans-serif")
    return derive_typography(font)


def get_rhythm(lock: dict[str, Any]) -> list[str]:
    """Return the default page rhythm pattern from a loaded spec lock."""
    return lock.get("page_rhythm", ["anchor", "breathing", "dense"])


# ---------------------------------------------------------------------------
# Normalization — ensure all v4.0 fields are populated
# ---------------------------------------------------------------------------

def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw spec lock dict to guarantee v4.0 fields exist."""
    lock = dict(raw)

    # Ensure extended palette
    if "palette" in lock:
        lock["palette"] = derive_extended_palette(lock["palette"])

    # Ensure typography
    if "typography" not in lock or not lock["typography"]:
        font = lock.get("font_family", "Arial, sans-serif")
        lock["typography"] = derive_typography(font).to_dict()

    # Ensure page_rhythm
    lock.setdefault("page_rhythm", ["anchor", "breathing", "dense"])

    # Ensure v4.0 structural fields
    lock.setdefault("page_layouts", {})
    lock.setdefault("page_charts", {})
    lock.setdefault("icon_inventory", [])
    lock.setdefault("forbidden_values", {"colors": [], "fonts": [], "patterns": []})

    # v4.1 design-intent fields
    lock.setdefault("design_rationale", {
        "objective": "",
        "audience": "general",
        "tone": "professional",
    })
    lock.setdefault("visual_strategy", {
        "decoration_intensity": "moderate",
        "rhythm_preference": "balanced",
    })

    return lock


# ---------------------------------------------------------------------------
# Markdown spec lock parser
# ---------------------------------------------------------------------------

def _parse_spec_lock_md(path: Path) -> dict[str, Any]:
    """Parse a spec_lock.md file into a dict compatible with the JSON format.

    This is a best-effort parser that extracts structured data from the
    Markdown tables and list items.  It does NOT need to round-trip
    perfectly — it's a convenience loader for the AI-readable format.
    """
    text = path.read_text(encoding="utf-8")
    lock: dict[str, Any] = {}

    # Title
    m = re.search(r"^# Spec Lock:\s*(.+)", text, re.MULTILINE)
    if m:
        lock["title"] = m.group(1).strip()

    # Canvas section
    canvas: dict[str, Any] = {}
    for m in re.finditer(
        r"- Format:\s*(.+)|"
        r"- Size:\s*(\d+)\s*[×x]\s*(\d+)|"
        r"- Theme:\s*`?([^`\n]+)`?|"
        r"- Language:\s*`?([^`\n]+)`?",
        text,
    ):
        if m.group(1):
            lock["format"] = m.group(1).strip()
            canvas["ratio"] = m.group(1).strip()
        elif m.group(2) and m.group(3):
            canvas["width"] = int(m.group(2))
            canvas["height"] = int(m.group(3))
        elif m.group(4):
            lock["theme"] = m.group(4).strip()
        elif m.group(5):
            lock["lang"] = m.group(5).strip()
    if canvas:
        lock["canvas"] = canvas

    # Palette table
    palette: dict[str, str] = {}
    palette_table = re.findall(
        r"^\|\s*(\w+)\s*\|\s*`([^`]+)`\s*\|",
        text,
        re.MULTILINE,
    )
    for role, hex_val in palette_table:
        if role.lower() not in ("role",):  # skip header
            palette[role] = hex_val
    if palette:
        lock["palette"] = palette

    # Typography
    typo: dict[str, Any] = {}
    for field_name in ("title_family", "body_family", "emphasis_family", "code_family"):
        label = field_name.replace("_", " ").title()
        m = re.search(rf"\*\*{label}:\*\*\s*`([^`]+)`", text)
        if m:
            typo[field_name] = m.group(1)

    # Size ramp table
    size_ramp: dict[str, int] = {}
    ramp_rows = re.findall(
        r"^\|\s*(\w+)\s*\|\s*(\d+)px\s*\|",
        text,
        re.MULTILINE,
    )
    for elem, size in ramp_rows:
        if elem.lower() not in ("element",):
            size_ramp[elem] = int(size)
    if size_ramp:
        typo["size_ramp"] = size_ramp
    if typo:
        lock["typography"] = typo

    # Page rhythm
    m = re.search(r"Default pattern:\s*`([^`]+)`", text)
    if m:
        parts = [p.strip() for p in m.group(1).split("→")]
        if parts:
            lock["page_rhythm"] = parts

    # Font family fallback
    m = re.search(r"- Font family:\s*`([^`]+)`", text)
    if m:
        lock.setdefault("font_family", m.group(1))

    return lock
