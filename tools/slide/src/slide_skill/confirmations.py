"""Design gate confirmations for the SVG pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .project import load_project

DEFAULT_CONFIRMATION_ITEMS = [
    "title",
    "audience",
    "key_points",
    "layout_strategy",
    "color_scheme",
    "page_count",
    "special_requirements",
    "confirmation",
]

# v4.0 Eight Confirmations — design pre-flight checklist.
# Used by generate_design_confirmations() in content_planner.py.
EIGHT_CONFIRMATION_KEYS = [
    "format",           # canvas format (16:9, etc.)
    "page_count",       # planned number of slides
    "style",            # theme/style name
    "color_scheme",     # palette summary
    "typography",       # font families
    "image_style",      # palette + rendering approach
    "rhythm_pattern",   # distribution of anchor/breathing/dense
    "outline",          # slide titles and layouts
]

COMPETITION_EXTRA_ITEMS = {
    "internet-plus": ["time_limit", "evaluation_criteria"],
    "challenge-cup": ["time_limit", "evaluation_criteria"],
    "math-modeling": ["time_limit", "evaluation_criteria"],
    "innovation-training": ["time_limit", "evaluation_criteria"],
    "thesis-defense": ["time_limit", "evaluation_criteria"],
    "course-presentation": ["time_limit", "evaluation_criteria"],
}


def get_confirmation_items(project_path: Path | str) -> list[str]:
    project = Path(project_path)
    items = list(DEFAULT_CONFIRMATION_ITEMS)
    try:
        meta = load_project(project)
        comp = meta.get("competition", {}).get("type", "")
        if comp in COMPETITION_EXTRA_ITEMS:
            for item in COMPETITION_EXTRA_ITEMS[comp]:
                if item not in items:
                    items.append(item)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return items


def check_confirmations(project_path: Path | str) -> tuple[bool, list[str]]:
    project = Path(project_path)
    conf_path = project / "confirmations.json"
    if not conf_path.exists():
        return False, get_confirmation_items(project_path)
    try:
        data = json.loads(conf_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False, get_confirmation_items(project_path)
    required = get_confirmation_items(project_path)
    missing = []
    for item in required:
        entry = data.get("confirmations", {}).get(item)
        if not entry or not entry.get("value"):
            missing.append(item)
    if not data.get("all_confirmed", False) and "confirmation" not in missing:
        missing.append("confirmation")
    return len(missing) == 0, missing


def write_confirmations(project_path: Path | str, values: dict) -> Path:
    project = Path(project_path)
    conf_path = project / "confirmations.json"
    now = datetime.now(timezone.utc).isoformat()
    existing: dict = {}
    if conf_path.exists():
        try:
            existing = json.loads(conf_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
    confirmations = existing.get("confirmations", {})
    for key, val in values.items():
        confirmations[key] = {"value": val, "confirmed_at": now}
    all_confirmed = False
    required = get_confirmation_items(project_path)
    if all(confirmations.get(r, {}).get("value") for r in required):
        if confirmations.get("confirmation", {}).get("value"):
            all_confirmed = True
    data = {
        "project": existing.get("project", project.name),
        "confirmations": confirmations,
        "all_confirmed": all_confirmed,
        "created_at": existing.get("created_at", now),
        "updated_at": now,
    }
    conf_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return conf_path


def load_confirmations(project_path: Path | str) -> dict | None:
    project = Path(project_path)
    conf_path = project / "confirmations.json"
    if not conf_path.exists():
        return None
    try:
        return json.loads(conf_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
