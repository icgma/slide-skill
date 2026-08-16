from __future__ import annotations
import json
from pathlib import Path
import re
from .project import load_project
from .svg_qa import SUPPORTED_DRAWABLE_TAGS, BANNED_TAGS, BANNED_ATTRS
from .layout_router import _select_layout


# ---------------------------------------------------------------------------
# Color role usage descriptions for spec_lock.md
# ---------------------------------------------------------------------------

_PALETTE_USAGE: dict[str, str] = {
    "background": "Slide background fill",
    "bg_secondary": "Alternate background, card hover state",
    "surface": "Card panels, footer bar",
    "text": "Headings, primary text",
    "text_secondary": "Body copy, captions",
    "text_tertiary": "Muted labels, footnotes",
    "body": "Body copy (alias of text_secondary)",
    "accent": "Accent stripe, bullets, links, CTA",
    "secondary_accent": "Supporting accent, chart series 2",
    "accent_tint": "Accent at ~12% opacity for backgrounds",
    "muted": "Alternating rows, rule lines",
    "border": "Card borders, dividers",
}


def create_spec(
    project_path: Path | str,
    source_markdown: Path | str | None = None,
    title: str | None = None,
    theme_name: str = "dark-tech",
) -> tuple[Path, Path]:
    """Create design_spec.md, spec_lock.json, spec_lock.md, and design_guide.md."""
    from .themes import get_theme
    from .design_guide import build_design_guide

    project = Path(project_path)
    meta = load_project(project)
    source_text = Path(source_markdown).read_text(encoding="utf-8") if source_markdown else ""
    inferred_title = title or _first_heading(source_text) or meta.get("title", meta["name"])
    theme = get_theme(theme_name)
    p = theme.palette

    spec = (
        f"# Design Specification: {inferred_title}\n\n"
        f"## Canvas\n\n"
        f"- Format: {meta['format']}\n"
        f"- Size: {meta['canvas']['width']} x {meta['canvas']['height']} px\n"
        f"- Ratio: {meta['canvas']['ratio']}\n\n"
        f"## Theme\n\n"
        f"- Name: {theme.name}\n"
        f"- Direction: {theme.design_hints}\n\n"
        f"## Visual Direction\n\n"
        f"- Background: {p['background']}\n"
        f"- Surface: {p['surface']}\n"
        f"- Accent: {p['accent']}\n"
        f"- Typography: {theme.font_family}\n\n"
        f"## Content Plan\n\n"
        f"Use source headings as slide boundaries. Each SVG page must follow the\n"
        f"spec lock and design guide. Read design_guide.md before writing SVG files.\n"
    )
    spec_path = project / "design_spec.md"
    spec_path.write_text(spec, encoding="utf-8")

    from .i18n import detect_language
    detected_lang = detect_language(source_text) if source_text else "en"

    # v4.0: extended palette (12 roles) and typography
    ext_palette = theme.extended_palette
    typo = theme.typography

    spec_lock = {
        "title": inferred_title,
        "theme": theme_name,
        "lang": detected_lang,
        "format": meta["format"],
        "canvas": meta["canvas"],
        "palette": ext_palette,
        "font_family": theme.font_family,
        "typography": typo.to_dict(),
        "page_rhythm": theme.layout_rhythm,
        "page_layouts": {},
        "page_charts": {},
        "icon_inventory": [],
        "forbidden_values": {
            "colors": [],
            "fonts": [],
            "patterns": [],
        },
        "design_hints": theme.design_hints,
        "svg_rules": {
            "semantic_groups_required": True,
            "supported_drawable_tags": sorted(SUPPORTED_DRAWABLE_TAGS),
            "banned_tags": sorted(BANNED_TAGS),
            "banned_attrs": sorted(BANNED_ATTRS),
            "note": (
                "v2.0: gradients, opacity, filters, transform, paths fully allowed. "
                "Only script/foreignObject/animation tags and on* event handlers are banned."
            ),
        },
    }
    lock_path = project / "spec_lock.json"
    lock_path.write_text(json.dumps(spec_lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # v4.0: generate human-readable spec_lock.md
    md_path = project / "spec_lock.md"
    md_path.write_text(
        _render_spec_lock_md(spec_lock, theme),
        encoding="utf-8",
    )

    # Write design guide for the AI Executor role
    build_design_guide(project, theme_name, source_text)

    return spec_path, lock_path

def generate_guide(
    project_path: Path | str,
    source_markdown: Path | str,
    theme_name: str = "dark-tech",
    max_slides: int = 12,
) -> Path:
    """Generate svg_generation_prompt.md — the AI agent's per-slide authoring guide.

    Does NOT generate SVGs itself. Creates a Markdown prompt telling the
    Executor role what to write for each slide: content, layout, coordinates.

    Returns the path to the generated prompt file.
    """
    from .themes import get_theme
    from .design_guide import build_design_guide

    project = Path(project_path)
    meta = load_project(project)
    source_text = Path(source_markdown).read_text(encoding="utf-8")
    slides = _markdown_to_slides(source_text)[:max_slides]
    spec_lock = _load_or_create_lock(project, source_markdown, theme_name)
    theme = get_theme(spec_lock.get("theme", theme_name))
    p = theme.palette
    font = theme.font_family
    w = int(meta["canvas"]["width"])
    h = int(meta["canvas"]["height"])

    # Ensure design_guide.md exists
    build_design_guide(project, spec_lock.get("theme", theme_name), source_text)

    lines = [
        "# SVG Generation Prompt",
        "",
        f"Project: `{meta['name']}`  |  Theme: `{theme.name}`  |  Slides: {len(slides)}",
        "",
        "## Instructions",
        "",
        "1. Read `design_guide.md` in this project directory BEFORE writing any SVG.",
        "2. Write each slide as a separate `.svg` file in `svg_output/`.",
        f"3. Canvas: **{w} x {h} px**. Always set width, height, viewBox on root `<svg>`.",
        "4. Chrome (accent stripe / footer bar) is an OPTIONAL deck-level motif: "
        "choose it once per deck for visual consistency, or omit it entirely — "
        "it is never required on every slide. Compose each slide from its content.",
        "5. Every top-level `<g>` MUST have an `id` attribute.",
        "6. Choose the appropriate layout template from design_guide.md for each slide.",
        "7. Use ONLY palette colours from the spec lock below.",
        "8. Gradients, opacity, filters are allowed — use them for visual richness.",
        "",
        "## Palette Reference",
        "",
        "| Role | Hex |",
        "|------|-----|",
        f"| background | `{p['background']}` |",
        f"| surface | `{p['surface']}` |",
        f"| text | `{p['text']}` |",
        f"| body | `{p['body']}` |",
        f"| accent | `{p['accent']}` |",
        f"| muted | `{p['muted']}` |",
        "",
        f"Font: `{font}`",
        "",
        "---",
        "",
        "## Slide Plan",
        "",
        f"Total slides: **{len(slides)}**",
        "",
    ]

    for i, (heading, body) in enumerate(slides, start=1):
        layout = _select_layout(heading, body, i, len(slides))
        lines.append(f"### Slide {i:02d} of {len(slides):02d} — Layout: {layout}")
        lines.append(f"**File:** `svg_output/slide_{i:02d}.svg`")
        lines.append("")
        lines.append(f"**Title:** {heading}")
        if body.strip():
            lines.append("**Body content:**")
            lines.append("```")
            lines.append(body.strip())
            lines.append("```")
        else:
            lines.append("*(No body text — use section-divider layout)*")
        lines.append("")

    prompt_path = project / "svg_generation_prompt.md"
    prompt_path.write_text("\n".join(lines), encoding="utf-8")
    return prompt_path

def _load_or_create_lock(
    project: Path,
    source_markdown: Path | str,
    theme_name: str = "dark-tech",
) -> dict:
    lock = project / "spec_lock.json"
    if not lock.exists():
        create_spec(project, source_markdown, theme_name=theme_name)
    return json.loads(lock.read_text(encoding="utf-8"))

def _first_heading(markdown: str) -> str | None:
    for line in markdown.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return None

def _markdown_to_slides(markdown: str) -> list[tuple[str, str]]:
    slides: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_body: list[str] = []
    for line in markdown.splitlines():
        # h1 (# ) is document title — use as cover, skip as slide split
        # h2 (## ) is slide boundary — creates a new slide
        # h3+ (### ) is sub-heading — treat as body content, don't split
        if line.startswith("## ") and not line.startswith("### "):
            if current_title:
                slides.append((current_title, current_body))
            current_title = line.lstrip("#").strip()
            current_body = []
        elif line.startswith("# ") and current_title is None:
            # First h1 becomes the cover slide title
            current_title = line.lstrip("#").strip()
            current_body = []
        else:
            current_body.append(line.strip())
    if current_title:
        slides.append((current_title, current_body))
    if not slides and markdown.strip():
        slides.append(("Overview", markdown.strip().splitlines()))
    return [(title, "\n".join(body)) for title, body in slides]


def _render_spec_lock_md(lock: dict, theme) -> str:
    """Render spec_lock.md — a human-readable, AI-friendly Markdown spec lock.

    This format is designed to be re-read by the AI Executor at the start
    of each page generation for drift prevention.
    """
    lines = [
        f"# Spec Lock: {lock['title']}",
        "",
        "> **Re-read this file before writing EVERY slide SVG.**",
        "> All colors, fonts, and layout decisions must conform to this spec.",
        "",
        "---",
        "",
        "## Canvas",
        "",
        f"- Format: {lock['format']}",
        f"- Size: {lock['canvas']['width']} × {lock['canvas']['height']} px",
        f"- Theme: `{lock['theme']}`",
        f"- Language: `{lock.get('lang', 'en')}`",
        "",
        "---",
        "",
        "## Palette",
        "",
        "| Role | Hex | Usage |",
        "|------|-----|-------|",
    ]

    palette = lock.get("palette", {})
    # Ordered output: base roles first, then derived
    role_order = [
        "background", "bg_secondary", "surface",
        "text", "text_secondary", "text_tertiary", "body",
        "accent", "secondary_accent", "accent_tint",
        "muted", "border",
    ]
    for role in role_order:
        if role in palette:
            usage = _PALETTE_USAGE.get(role, "")
            lines.append(f"| {role} | `{palette[role]}` | {usage} |")
    # Any extra roles not in the standard list
    for role, val in palette.items():
        if role not in role_order:
            lines.append(f"| {role} | `{val}` | (custom) |")

    lines.extend([
        "",
        "**Use ONLY these colors.** Never introduce colors not listed above.",
        "",
        "---",
        "",
        "## Typography",
        "",
    ])

    typo = lock.get("typography", {})
    if typo:
        lines.extend([
            f"- **Title family:** `{typo.get('title_family', '')}`",
            f"- **Body family:** `{typo.get('body_family', '')}`",
            f"- **Emphasis family:** `{typo.get('emphasis_family', '')}`",
            f"- **Code family:** `{typo.get('code_family', '')}`",
            "",
            "### Size Ramp",
            "",
            "| Element | Size |",
            "|---------|------|",
        ])
        for elem, size in typo.get("size_ramp", {}).items():
            lines.append(f"| {elem} | {size}px |")
    else:
        lines.append(f"- Font family: `{lock.get('font_family', '')}`")

    lines.extend([
        "",
        "---",
        "",
        "## Page Rhythm",
        "",
        f"Default pattern: `{' → '.join(lock.get('page_rhythm', ['anchor', 'breathing', 'dense']))}`",
        "",
        "- **anchor** — High visual weight. Hero elements, key takeaways, metric dashboards.",
        "- **breathing** — Light density. Generous whitespace, minimal content, visual rest.",
        "- **dense** — Information-rich. Multi-item lists, tables, detailed content.",
        "",
        "---",
        "",
        "## Design Direction",
        "",
        lock.get("design_hints", ""),
        "",
    ])

    # Forbidden values
    forbidden = lock.get("forbidden_values", {})
    if any(forbidden.get(k) for k in ("colors", "fonts", "patterns")):
        lines.extend([
            "---",
            "",
            "## Forbidden Values",
            "",
        ])
        for k in ("colors", "fonts", "patterns"):
            vals = forbidden.get(k, [])
            if vals:
                lines.append(f"- **{k.title()}:** {', '.join(f'`{v}`' for v in vals)}")
        lines.append("")

    return "\n".join(lines) + "\n"
