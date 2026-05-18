"""Image metadata management for project workspaces."""

from __future__ import annotations

import json
from pathlib import Path


def load_metadata(project_path: Path | str) -> dict:
    project = Path(project_path)
    meta_path = project / "images" / "metadata.json"
    if not meta_path.exists():
        return {"images": []}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"images": []}
    if "images" not in data:
        data["images"] = []
    return data


def save_metadata(project_path: Path | str, metadata: dict) -> Path:
    project = Path(project_path)
    meta_path = project / "images" / "metadata.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta_path


def add_image_metadata(project_path: Path | str, entry: dict) -> Path:
    metadata = load_metadata(project_path)
    existing = [img["filename"] for img in metadata["images"] if "filename" in img]
    if entry.get("filename") not in existing:
        metadata["images"].append(entry)
    return save_metadata(project_path, metadata)


def list_images(project_path: Path | str) -> list[dict]:
    return load_metadata(project_path).get("images", [])


def get_image_paths(project_path: Path | str) -> list[str]:
    metadata = load_metadata(project_path)
    project = Path(project_path)
    paths: list[str] = []
    for img in metadata.get("images", []):
        fname = img.get("filename", "")
        if fname and (project / "images" / fname).exists():
            paths.append(fname)
    return paths
