#!/usr/bin/env python3
"""Build all example decks: markdown → SVG → PPTX → PDF → PNG → GIF.

Run from repo root:  python3 scripts/build_examples.py
Outputs land in:     examples/<slug>/  and  docs/examples/<slug>/
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "slide" / "src"))

from slide_skill.exporter import export_project
from slide_skill.project import init_project
from slide_skill.svg_pipeline import create_spec, finalize_svg, generate_svg
from slide_skill.templates import get_template

EXAMPLES_DIR = ROOT / "examples"
DOCS_DIR = ROOT / "docs" / "examples"
CONTENT_DIR = ROOT / "examples" / "_content"


def build_one(slug: str) -> dict:
    spec = get_template(slug)
    md_path = CONTENT_DIR / f"{slug}.md"
    if not md_path.exists():
        raise FileNotFoundError(f"Missing example content: {md_path}")

    workdir = EXAMPLES_DIR / slug
    if workdir.exists():
        shutil.rmtree(workdir)

    print(f"\n=== {slug}  ({spec.name_zh}, theme={spec.theme}) ===", flush=True)
    project = init_project(slug, "ppt169", str(EXAMPLES_DIR), overwrite=True)
    src = project / "sources" / f"{slug}.md"
    src.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")

    create_spec(project, src, title=spec.name_zh, theme_name=spec.theme)
    generate_svg(project, src, max_slides=12)
    finalize_svg(project)
    pptx = export_project(project)
    print(f"  pptx:   {pptx.relative_to(ROOT)}", flush=True)

    # PPTX → PDF via libreoffice
    pdf_dir = project / "render"
    pdf_dir.mkdir(exist_ok=True)
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf",
         "--outdir", str(pdf_dir), str(pptx)],
        check=True, capture_output=True, timeout=90,
    )
    pdf = pdf_dir / (pptx.stem + ".pdf")
    print(f"  pdf:    {pdf.relative_to(ROOT)}", flush=True)

    # PDF → PNG frames
    png_prefix = pdf_dir / "frame"
    subprocess.run(
        ["pdftoppm", "-png", "-r", "110", str(pdf), str(png_prefix)],
        check=True, timeout=60,
    )
    frames = sorted(pdf_dir.glob("frame-*.png"))
    print(f"  frames: {len(frames)}", flush=True)

    # PNG frames → GIF (1.6s per slide, infinite loop)
    gif = workdir / "preview.gif"
    subprocess.run(
        ["convert", "-delay", "160", "-loop", "0", "-resize", "1024x576",
         *[str(f) for f in frames], str(gif)],
        check=True, timeout=120,
    )
    print(f"  gif:    {gif.relative_to(ROOT)}  ({gif.stat().st_size // 1024} KB)", flush=True)

    # First-frame thumbnail (static cover for the page)
    thumb = workdir / "cover.png"
    subprocess.run(
        ["convert", str(frames[0]), "-resize", "640x360", str(thumb)],
        check=True, timeout=30,
    )

    # Mirror artefacts into docs/ so GitHub Pages can serve them
    docs_target = DOCS_DIR / slug
    docs_target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(gif, docs_target / "preview.gif")
    shutil.copy2(thumb, docs_target / "cover.png")
    shutil.copy2(pptx, docs_target / f"{slug}.pptx")

    return {
        "slug": slug, "spec": spec,
        "gif_size_kb": gif.stat().st_size // 1024,
        "frames": len(frames),
    }


SHOWCASE_SLUGS = [
    "biz-mck-strategy",
    "pitch-seed",
    "prod-keynote",
    "rep-monthly",
    "edu-stem",
    "aca-thesis",
    "mkt-campaign",
    "gov-work-report",
    "tech-conf-talk",
    "trn-onboarding",
]


def main() -> int:
    EXAMPLES_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    only = sys.argv[1:] or SHOWCASE_SLUGS
    results = []
    t0 = time.time()
    for slug in only:
        try:
            results.append(build_one(slug))
        except Exception as exc:
            print(f"  !! FAILED {slug}: {exc}", flush=True)
    print(f"\nBuilt {len(results)}/{len(only)} examples in {time.time()-t0:.1f}s")
    return 0 if len(results) == len(only) else 1


if __name__ == "__main__":
    sys.exit(main())
