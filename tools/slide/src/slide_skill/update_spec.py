"""Spec propagation: incrementally update SVG files when spec_lock changes."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

UNSUPPORTED_FIELDS = {"canvas", "card_radius", "title_decoration", "page_rhythm", "svg_rules", "resources", "audience", "objective", "per_page_rationale", "format", "template", "typography"}


def update_spec(project_path: Path | str) -> dict:
    project = Path(project_path)
    svg_dir = project / "svg_output"
    if not svg_dir.exists() or not list(svg_dir.glob("*.svg")):
        return {"status": "no_svg", "files_changed": 0, "replacements": 0}
    lock_path = project / "spec_lock.json"
    if not lock_path.exists():
        return {"status": "no_spec_lock", "files_changed": 0, "replacements": 0}
    bak_dir = _backup_svg_output(project)
    current_lock = json.loads(lock_path.read_text(encoding="utf-8"))
    bak_lock = bak_dir / "spec_lock.json"
    if bak_lock.exists():
        old_lock = json.loads(bak_lock.read_text(encoding="utf-8"))
    else:
        shutil.copy2(lock_path, bak_dir / "spec_lock.json")
        return {"status": "first_run", "files_changed": 0, "replacements": 0, "backup": str(bak_dir)}
    unsupported = _check_unsupported_changes(old_lock, current_lock)
    if unsupported:
        raise ValueError(f"Cannot incrementally propagate changes to: {', '.join(unsupported)}. Re-generate SVG instead.")
    color_map = _extract_palette_diff(old_lock, current_lock)
    old_font, new_font = _extract_font_diff(old_lock, current_lock)
    total_replacements = 0
    files_changed = 0
    for svg_file in sorted(svg_dir.glob("*.svg")):
        content = svg_file.read_text(encoding="utf-8")
        original = content
        if color_map:
            content, count = _replace_colors(content, color_map)
            total_replacements += count
        if old_font and new_font and old_font != new_font:
            content, count = _replace_font(content, old_font, new_font)
            total_replacements += count
        if content != original:
            svg_file.write_text(content, encoding="utf-8")
            files_changed += 1
    from .svg_pipeline import check_project_svg
    ok, issues = check_project_svg(project)
    return {
        "status": "qa_passed" if ok else "qa_failed",
        "files_changed": files_changed,
        "replacements": total_replacements,
        "backup": str(bak_dir),
        "qa_issues": [f"{i.level}: {i.message}" for i in issues if i.level == "error"],
    }


def _backup_svg_output(project_path: Path) -> Path:
    project = Path(project_path)
    svg_dir = project / "svg_output"
    bak_dir = project / "svg_output.bak"
    if bak_dir.exists():
        shutil.rmtree(bak_dir)
    if svg_dir.exists():
        shutil.copytree(svg_dir, bak_dir)
    return bak_dir


def _extract_palette_diff(old_lock: dict, new_lock: dict) -> dict[str, str]:
    old_palette = old_lock.get("palette", {})
    new_palette = new_lock.get("palette", {})
    color_map: dict[str, str] = {}
    for key in set(old_palette) & set(new_palette):
        old_val = old_palette[key]
        new_val = new_palette[key]
        if isinstance(old_val, str) and isinstance(new_val, str) and old_val != new_val:
            if _is_hex_color(old_val) and _is_hex_color(new_val):
                color_map[old_val.lower()] = new_val
                color_map[old_val.upper()] = new_val
    return color_map


def _extract_font_diff(old_lock: dict, new_lock: dict) -> tuple[str, str]:
    old_font = old_lock.get("font_family", "")
    new_font = new_lock.get("font_family", "")
    return old_font, new_font


def _check_unsupported_changes(old_lock: dict, new_lock: dict) -> list[str]:
    changed = []
    for field in UNSUPPORTED_FIELDS:
        if old_lock.get(field) != new_lock.get(field):
            changed.append(field)
    return changed


def _replace_colors(content: str, color_map: dict[str, str]) -> tuple[str, int]:
    count = 0
    for old_color, new_color in color_map.items():
        occurrences = content.count(old_color)
        if occurrences > 0:
            content = content.replace(old_color, new_color)
            count += occurrences
    return content, count


def _replace_font(content: str, old_font: str, new_font: str) -> tuple[str, int]:
    pattern = re.compile(re.escape(old_font), re.IGNORECASE)
    count = len(pattern.findall(content))
    content = pattern.sub(new_font, content)
    return content, count


def _is_hex_color(value: str) -> bool:
    return bool(re.match(r'^#[0-9a-fA-F]{6}$', value))
