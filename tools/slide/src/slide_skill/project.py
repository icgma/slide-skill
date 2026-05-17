"""Per-deck workspace management."""

from __future__ import annotations

import shutil
from pathlib import Path

from .formats import get_format
from .util import ensure_dir, read_json, slugify, timestamp, write_json

REQUIRED_DIRS = [
    "sources",
    "images",
    "svg_output",
    "svg_final",
    "notes",
    "exports",
    "backup",
    "qa",
]


def project_metadata_path(project_path: Path) -> Path:
    return project_path / "project.json"


def init_project(
    name: str,
    fmt: str = "ppt169",
    base_dir: Path | str = "projects",
    overwrite: bool = False,
    competition: str | None = None,
) -> Path:
    canvas = get_format(fmt)
    base = Path(base_dir)
    project_path = base / slugify(name)
    if project_path.exists() and not overwrite:
        raise FileExistsError(f"Project already exists: {project_path}")
    ensure_dir(project_path)
    for dirname in REQUIRED_DIRS:
        ensure_dir(project_path / dirname)

    metadata: dict = {
        "name": slugify(name),
        "title": name,
        "format": canvas.name,
        "canvas": {
            "width": canvas.width,
            "height": canvas.height,
            "ratio": canvas.ratio,
            "pptx_width_in": canvas.pptx_width_in,
            "pptx_height_in": canvas.pptx_height_in,
        },
        "created_at": timestamp(),
        "version": 1,
    }

    if competition:
        from .competition import get_competition
        spec = get_competition(competition)
        metadata["competition"] = {
            "id": spec.name,
            "name_zh": spec.name_zh,
            "time_limit_minutes": spec.time_limit_minutes,
            "page_range": list(spec.page_range),
        }
        outline = project_path / "sources" / "competition_outline.md"
        from .competition import competition_to_markdown
        outline.write_text(competition_to_markdown(spec), encoding="utf-8")

    write_json(project_metadata_path(project_path), metadata)
    return project_path


def load_project(project_path: Path | str) -> dict:
    path = Path(project_path)
    meta = project_metadata_path(path)
    if not meta.exists():
        raise FileNotFoundError(f"Missing project metadata: {meta}")
    data = read_json(meta)
    data["_path"] = str(path)
    return data


def import_sources(project_path: Path | str, source_paths: list[Path], move: bool = False) -> list[Path]:
    project = Path(project_path)
    dest_dir = ensure_dir(project / "sources")
    copied: list[Path] = []
    for source in source_paths:
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(source)
        dest = dest_dir / source.name
        if source.resolve() == dest.resolve():
            copied.append(dest)
            continue
        if move:
            shutil.move(str(source), str(dest))
        else:
            shutil.copy2(source, dest)
        copied.append(dest)
    return copied


def validate_project(project_path: Path | str) -> tuple[bool, list[str]]:
    project = Path(project_path)
    errors: list[str] = []
    if not project.exists():
        errors.append(f"Project directory does not exist: {project}")
        return False, errors
    if not project_metadata_path(project).exists():
        errors.append("Missing project.json")
    for dirname in REQUIRED_DIRS:
        if not (project / dirname).is_dir():
            errors.append(f"Missing directory: {dirname}")
    return not errors, errors
