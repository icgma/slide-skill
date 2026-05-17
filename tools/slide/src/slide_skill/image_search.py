"""Image search and download with Creative Commons license filtering."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

PERMISSIVE_LICENSES = {
    "CC0", "cc0", "publicdomain", "pdm",
    "CC BY 4.0", "CC BY 3.0", "CC BY 2.5", "CC BY 2.0", "CC BY 1.0",
    "cc-by", "ccby", " attribution",
    "CC BY-SA 4.0", "CC BY-SA 3.0", "CC BY-SA 2.5", "CC BY-SA 2.0",
    "cc-by-sa", "ccbysa",
}

NC_ND_PATTERNS = re.compile(r"nc|nd|noderivatives|noncommercial", re.IGNORECASE)


def search_images(query: str, limit: int = 5, allow_nc: bool = False) -> list[dict]:
    try:
        import requests
    except ImportError:
        raise ImportError("requests is required for image search: pip install slide-skill[intake]")
    results: list[dict] = []
    url = f"https://api.creativecommons.org/image/search?q={quote_plus(query)}&page_size={limit * 2}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError, ValueError):
        return []
    for item in data.get("results", []):
        license_name = item.get("license", "") or ""
        license_url = item.get("license_url", "") or item.get("license_landing_url", "") or ""
        if not allow_nc and _is_restricted_license(license_name, license_url):
            continue
        image_url = item.get("url", "") or item.get("image", "")
        thumbnail = item.get("thumbnail", "") or image_url
        if not image_url:
            continue
        results.append({
            "url": image_url,
            "thumbnail": thumbnail,
            "title": item.get("title", ""),
            "license": _normalize_license(license_name),
            "license_url": license_url,
            "source": item.get("source", ""),
            "creator": item.get("creator", ""),
        })
        if len(results) >= limit:
            break
    return results


def download_image(url: str, dest_dir: Path | str, filename: str | None = None, query: str = "") -> Path:
    try:
        import requests
    except ImportError:
        raise ImportError("requests is required for image download: pip install slide-skill[intake]")
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    if not filename:
        ext = _ext_from_url(url) or ".jpg"
        h = hashlib.md5(url.encode()).hexdigest()[:8]
        filename = f"img_{h}{ext}"
    path = dest / filename
    resp = requests.get(url, timeout=30, stream=True)
    resp.raise_for_status()
    with open(path, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)
    return path


def extract_dominant_color(image_path: Path | str) -> str:
    try:
        from PIL import Image
    except ImportError:
        return "#000000"
    try:
        img = Image.open(image_path).convert("RGB").resize((1, 1))
        r, g, b = img.getpixel((0, 0))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return "#000000"


def get_dimensions(image_path: Path | str) -> dict[str, int] | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        img = Image.open(image_path)
        return {"width": img.width, "height": img.height}
    except Exception:
        return None


def build_image_metadata(filename: str, source: str, query: str, license_name: str, license_url: str = "", dimensions: dict | None = None, dominant_color: str = "#000000") -> dict:
    return {
        "filename": filename,
        "source": source,
        "query": query,
        "license": license_name,
        "license_url": license_url,
        "dimensions": dimensions or {},
        "dominant_color": dominant_color,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _is_restricted_license(license_name: str, license_url: str) -> bool:
    combined = f"{license_name} {license_url}"
    return bool(NC_ND_PATTERNS.search(combined))


def _normalize_license(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return "Unknown"
    lower = raw.lower().replace(" ", "-")
    if lower in ("cc0", "cc0-1.0", "publicdomain", "pdm"):
        return "CC0"
    if "by-sa" in lower:
        return "CC BY-SA"
    if "by-nc-nd" in lower:
        return "CC BY-NC-ND"
    if "by-nc-sa" in lower:
        return "CC BY-NC-SA"
    if "by-nc" in lower:
        return "CC BY-NC"
    if "by-nd" in lower:
        return "CC BY-ND"
    if "by" in lower:
        return "CC BY"
    return raw


def _ext_from_url(url: str) -> str:
    for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"):
        if url.lower().rstrip("/").endswith(ext):
            return ext
    return ""
