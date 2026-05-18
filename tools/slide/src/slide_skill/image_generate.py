"""AI image generation via OpenAI-compatible API."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

from .image_search import build_image_metadata, extract_dominant_color, get_dimensions


def generate_image(prompt: str, dest_dir: Path | str, size: str = "1024x1024", backend: str | None = None) -> Path:
    effective_backend = backend or os.environ.get("IMAGE_BACKEND", "openai")
    if effective_backend == "openai":
        return _generate_openai(prompt, dest_dir, size)
    raise ValueError(f"Unsupported image generation backend: {effective_backend}")


def _generate_openai(prompt: str, dest_dir: Path | str, size: str) -> Path:
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai is required for image generation: pip install slide-skill[image]")
    api_key = os.environ.get("IMAGE_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("IMAGE_API_KEY or OPENAI_API_KEY environment variable required for image generation")
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=api_key)
    response = client.images.generate(model="dall-e-3", prompt=prompt, size=size, n=1, response_format="b64_json")
    image_data = response.data[0]
    import base64
    img_bytes = base64.b64decode(image_data.b64_json)
    h = hashlib.md5(img_bytes).hexdigest()[:8]
    filename = f"gen_{h}.png"
    path = dest / filename
    path.write_bytes(img_bytes)
    return path


def generate_and_record(prompt: str, project_path: Path | str, size: str = "1024x1024", backend: str | None = None) -> dict:
    dest = Path(project_path) / "images"
    path = generate_image(prompt, dest, size, backend)
    dims = get_dimensions(path)
    color = extract_dominant_color(path)
    meta = build_image_metadata(
        filename=path.name,
        source="generate",
        query=prompt,
        license_name="Generated (owned)",
        license_url="",
        dimensions=dims,
        dominant_color=color,
    )
    from .image_meta import add_image_metadata
    add_image_metadata(project_path, meta)
    return meta
