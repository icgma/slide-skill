"""AI image generation via OpenAI-compatible API.

v4.0 additions:
- palette/rendering style parameters for spec-lock-aware generation
- image manifest integration in spec_lock
- prompt enhancement with palette colors and rendering prefixes
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .image_search import build_image_metadata, extract_dominant_color, get_dimensions

# Path to bundled reference materials
_REFERENCES_DIR = Path(__file__).parent / "references"
_PALETTES_DIR = _REFERENCES_DIR / "image-palettes"
_RENDERINGS_DIR = _REFERENCES_DIR / "image-renderings"


def list_palettes() -> list[str]:
    """List available image palette names."""
    if not _PALETTES_DIR.is_dir():
        return []
    return sorted(p.stem for p in _PALETTES_DIR.glob("*.md"))


def list_rendering_styles() -> list[str]:
    """List available rendering style names."""
    if not _RENDERINGS_DIR.is_dir():
        return []
    return sorted(p.stem for p in _RENDERINGS_DIR.glob("*.md"))


def get_palette_info(name: str) -> dict | None:
    """Read a palette guide and return structured info."""
    path = _PALETTES_DIR / f"{name}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    # Parse simple structure
    info = {"name": name, "raw": text}
    for line in text.splitlines():
        if line.startswith("**Mood:**"):
            info["mood"] = line.split("**Mood:**")[1].strip()
        elif line.startswith("> "):
            info["prompt_hint"] = line.lstrip("> ").strip()
    return info


def get_rendering_info(name: str) -> dict | None:
    """Read a rendering style guide and return structured info."""
    path = _RENDERINGS_DIR / f"{name}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    info = {"name": name, "raw": text}
    for line in text.splitlines():
        if line.startswith("**Description:**"):
            info["description"] = line.split("**Description:**")[1].strip()
    # Extract prompt prefix from code block
    in_code = False
    for line in text.splitlines():
        if line.strip() == "```" and not in_code:
            in_code = True
            continue
        elif line.strip() == "```" and in_code:
            break
        elif in_code:
            info["prompt_prefix"] = line.strip()
    return info


def enhance_prompt(
    base_prompt: str,
    palette: str | None = None,
    rendering: str | None = None,
    spec_lock: dict | None = None,
) -> str:
    """Enhance a generation prompt with palette colors and rendering style.

    Priority:
    1. If spec_lock is provided, extract colors from palette section
    2. If palette name is given, load palette prompt hint
    3. If rendering name is given, prepend rendering prompt prefix
    """
    parts = []

    # Rendering prefix
    if rendering:
        rinfo = get_rendering_info(rendering)
        if rinfo and "prompt_prefix" in rinfo:
            parts.append(rinfo["prompt_prefix"])

    # Base prompt
    parts.append(base_prompt)

    # Color context
    if spec_lock and "palette" in spec_lock:
        pal = spec_lock["palette"]
        colors = [pal.get("background", ""), pal.get("accent", ""), pal.get("surface", "")]
        color_str = ", ".join(c for c in colors if c)
        if color_str:
            parts.append(f"Color palette: {color_str}.")
    elif palette:
        pinfo = get_palette_info(palette)
        if pinfo and "prompt_hint" in pinfo:
            parts.append(pinfo["prompt_hint"])

    # Safety suffix
    parts.append("No text, no watermarks, no borders.")

    return " ".join(parts)


def generate_image(
    prompt: str,
    dest_dir: Path | str,
    size: str = "1024x1024",
    backend: str | None = None,
    palette: str | None = None,
    rendering: str | None = None,
    spec_lock: dict | None = None,
) -> Path:
    """Generate an image with optional palette/rendering style enhancement.

    Args:
        prompt: Base image description
        dest_dir: Directory to save the image
        size: Image size (e.g., "1024x1024")
        backend: Generation backend ("openai" or env-configured)
        palette: Palette name from image-palettes/ (e.g., "tech-midnight")
        rendering: Rendering style name (e.g., "flat", "glassmorphism")
        spec_lock: Spec lock dict to extract palette colors from
    """
    enhanced = enhance_prompt(prompt, palette=palette, rendering=rendering, spec_lock=spec_lock)
    effective_backend = backend or os.environ.get("IMAGE_BACKEND", "openai")
    if effective_backend == "openai":
        return _generate_openai(enhanced, dest_dir, size)
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


def generate_and_record(
    prompt: str,
    project_path: Path | str,
    size: str = "1024x1024",
    backend: str | None = None,
    palette: str | None = None,
    rendering: str | None = None,
    crop_policy: str = "cover",
    placement_pattern: str = "center-hero",
) -> dict:
    """Generate image, record metadata, and return enriched manifest entry.

    v4.0: Returns manifest-compatible dict with crop_policy and placement_pattern.
    """
    # Load spec_lock if available
    spec_lock = None
    lock_path = Path(project_path) / "spec_lock.json"
    if lock_path.exists():
        spec_lock = json.loads(lock_path.read_text(encoding="utf-8"))

    dest = Path(project_path) / "images"
    path = generate_image(prompt, dest, size, backend, palette=palette, rendering=rendering, spec_lock=spec_lock)
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
    # v4.0: enriched manifest fields
    meta["palette"] = palette or "auto"
    meta["rendering_style"] = rendering or "auto"
    meta["crop_policy"] = crop_policy
    meta["placement_pattern"] = placement_pattern

    from .image_meta import add_image_metadata
    add_image_metadata(project_path, meta)
    return meta


def build_image_manifest(project_path: Path | str) -> list[dict]:
    """Read all image metadata and return as manifest for spec_lock integration."""
    meta_path = Path(project_path) / "images_meta.json"
    if not meta_path.exists():
        return []
    return json.loads(meta_path.read_text(encoding="utf-8"))
