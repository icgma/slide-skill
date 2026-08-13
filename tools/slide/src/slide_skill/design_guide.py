"""Per-deck design guide generator for slide-skill v4.0.

The design guide is a Markdown document placed in the project directory.
It gives the AI agent (Executor role) exact visual specifications for
writing SVG slide pages: palette, typography, layout templates, chrome
coordinates, and SVG authoring rules.

v4.0 additions:
- Expanded palette (12 colour roles) and typography (4 font families)
- Page rhythm section
- References to external executor documents
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .themes import get_theme, ThemeSpec
from .util import ensure_dir

# Path to the bundled reference documents
_REFERENCES_DIR = Path(__file__).parent / "references"


def build_design_guide(
    project_path: Path | str,
    theme_name: str = "dark-tech",
    source_text: str = "",
) -> Path:
    """Write design_guide.md into the project directory.

    Also copies executor reference documents into the project's
    ``references/`` subdirectory.  Returns the path to the written guide.
    """
    project = Path(project_path)
    ensure_dir(project)
    theme = get_theme(theme_name)
    content = _render_guide(theme)
    guide_path = project / "design_guide.md"
    guide_path.write_text(content, encoding="utf-8")

    # v4.0: copy executor reference documents
    copy_references(project)

    return guide_path


def copy_references(project_path: Path | str) -> Path:
    """Copy bundled executor reference documents into a project.

    Creates ``{project}/references/`` and copies all ``.md`` files from
    the package's ``references/`` directory, including subdirectories
    (image-palettes, image-renderings).

    Also copies template SVGs from ``templates/`` into the project.

    Returns the references dir.
    """
    project = Path(project_path)
    dest = project / "references"
    ensure_dir(dest)

    if _REFERENCES_DIR.is_dir():
        # Copy top-level .md files
        for src_file in sorted(_REFERENCES_DIR.glob("*.md")):
            dst_file = dest / src_file.name
            shutil.copy2(src_file, dst_file)
        # Copy subdirectories (image-palettes, image-renderings)
        for subdir in sorted(_REFERENCES_DIR.iterdir()):
            if subdir.is_dir():
                dest_sub = dest / subdir.name
                ensure_dir(dest_sub)
                for src_file in sorted(subdir.glob("*.md")):
                    shutil.copy2(src_file, dest_sub / src_file.name)

    # Copy templates
    templates_src = Path(__file__).parent / "templates"
    if templates_src.is_dir():
        templates_dest = project / "templates"
        ensure_dir(templates_dest)
        for src_file in templates_src.rglob("*"):
            if src_file.is_file():
                rel = src_file.relative_to(templates_src)
                dst = templates_dest / rel
                ensure_dir(dst.parent)
                shutil.copy2(src_file, dst)

    return dest


def _render_guide(theme: ThemeSpec) -> str:
    p = theme.extended_palette  # v4.0: 12 color roles
    typo = theme.typography     # v4.0: role-based families
    font = theme.font_family
    bg = p["background"]
    bg2 = p["bg_secondary"]
    surf = p["surface"]
    text_c = p["text"]
    text2 = p["text_secondary"]
    text3 = p["text_tertiary"]
    body_c = p["body"]
    accent = p["accent"]
    accent2 = p["secondary_accent"]
    accent_t = p["accent_tint"]
    muted = p["muted"]
    border = p["border"]

    lines = [
        f"# Design Guide — Theme: {theme.name}",
        "",
        "> **READ THIS ENTIRE GUIDE before writing any SVG file.**",
        "> Every SVG page must conform strictly to these specifications.",
        "",
        "---",
        "",
        "## 1. Design Direction",
        "",
        theme.design_hints,
        "",
        "---",
        "",
        "## 2. Colour Palette (12 roles)",
        "",
        "| Role             | Hex           | Usage                                |",
        "|------------------|---------------|--------------------------------------|",
        f"| background       | `{bg}`   | Slide background fill                |",
        f"| bg_secondary     | `{bg2}`  | Alternate background, hover state    |",
        f"| surface          | `{surf}` | Card panels, footer bar              |",
        f"| text             | `{text_c}` | Headings, primary text             |",
        f"| text_secondary   | `{text2}` | Body copy, captions                |",
        f"| text_tertiary    | `{text3}` | Muted labels, footnotes            |",
        f"| body             | `{body_c}` | Body copy (alias of text_secondary)|",
        f"| accent           | `{accent}` | Accent stripe, bullets, links, CTA |",
        f"| secondary_accent | `{accent2}` | Supporting accent, chart series 2  |",
        f"| accent_tint      | `{accent_t}` | Accent at ~12% opacity for fills |",
        f"| muted            | `{muted}` | Alternating rows, rule lines       |",
        f"| border           | `{border}` | Card borders, dividers             |",
        "",
        "Always use these exact hex codes. Never introduce colours not in this table.",
        "",
        "---",
        "",
        "## 3. Typography",
        "",
        f"**Title family:** `{typo.title_family}`",
        f"**Body family:** `{typo.body_family}`",
        f"**Emphasis family:** `{typo.emphasis_family}`",
        f"**Code family:** `{typo.code_family}`",
        "",
        "### Size Ramp",
        "",
        "| Element         | font-size | font-weight | fill           | family    |",
        "|-----------------|-----------|-------------|----------------|-----------|",
        f"| Hero title      | {typo.size_ramp.get('hero', 72)}px   | 700         | `{text_c}`    | title     |",
        f"| Section heading | {typo.size_ramp.get('h1', 60)}px   | 700         | `{text_c}`    | title     |",
        f"| Subheading      | {typo.size_ramp.get('h2', 48)}px   | 600         | `{text_c}`    | title     |",
        f"| Body large      | {typo.size_ramp.get('body_lg', 28)}px   | 400         | `{body_c}`    | body      |",
        f"| Body text       | {typo.size_ramp.get('body', 24)}px   | 400         | `{body_c}`    | body      |",
        f"| Metric value    | {typo.size_ramp.get('hero', 72)}px   | 700         | `{accent}`    | emphasis  |",
        f"| Caption         | {typo.size_ramp.get('caption', 16)}px   | 400         | `{text2}`    | body      |",
        f"| Overline        | {typo.size_ramp.get('overline', 14)}px   | 600         | `{accent}`    | body      |",
        f"| Footer text     | {typo.size_ramp.get('footnote', 12)}px   | 400         | `{muted}`     | body      |",
        f"| Code / data     | {typo.size_ramp.get('body', 24)}px   | 400         | `{text_c}`    | code      |",
        "",
        "**Title font-size rules:**",
        "- 1–15 chars → 56–64px",
        "- 16–25 chars → 44–48px",
        "- 26+ chars → 36–40px (or split across two `<text>` elements)",
        "",
        "---",
        "",
        "## 3.5. Page Rhythm",
        "",
        "Each slide has a **rhythm** assignment that controls visual density:",
        "",
        "| Rhythm    | Visual Strategy                                   |",
        "|-----------|---------------------------------------------------|",
        "| anchor    | High visual weight. Hero elements, big numbers.   |",
        "| breathing | Light density. Generous whitespace, visual rest.   |",
        "| dense     | Information-rich. Multi-item lists, tables.        |",
        "",
        "**Rules:**",
        "- Never have 3+ consecutive slides with the same rhythm.",
        "- Cover and closing slides are always `anchor`.",
        "- Section dividers are always `breathing`.",
        "- Data-heavy slides (6+ items) should be `dense`.",
        "",
        "---",
        "",
        "## 4. Canvas & Chrome (required on EVERY slide)",
        "",
        "Canvas: **1280 × 720 px**, always `width=\"1280\" height=\"720\" viewBox=\"0 0 1280 720\"`.",
        "",
        "### Left accent stripe (required)",
        "```xml",
        '<g id="chrome-stripe">',
        f'  <rect x="0" y="0" width="6" height="720" fill="{accent}" />',
        "</g>",
        "```",
        "",
        "### Footer bar (required)",
        "```xml",
        '<g id="chrome-footer">',
        f'  <rect x="0" y="688" width="1280" height="32" fill="{surf}" />',
        f'  <text x="1184" y="708" font-family="{font}" font-size="12"',
        f'        fill="{muted}" text-anchor="end">NN / TT</text>',
        "</g>",
        "```",
        "NN = zero-padded current slide number. TT = total slide count.",
        "",
        "Content safe area: **x 80–1200 px**, **y 80–680 px**.",
        "",
        "---",
        "",
        "## 5. SVG Group Structure",
        "",
        "Every slide must have semantic top-level `<g id=\"...\">` groups. Minimum:",
        "```xml",
        '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">',
        "  <defs><!-- gradients/filters here --></defs>",
        '  <g id="background"><!-- full-bleed background rect --></g>',
        '  <g id="chrome-stripe"><!-- left accent stripe --></g>',
        '  <g id="content-title-NN"><!-- title text --></g>',
        '  <g id="content-body-NN"><!-- body content --></g>',
        '  <g id="chrome-footer"><!-- footer bar + page number --></g>',
        "</svg>",
        "```",
        "Omit `content-body-NN` for section-divider layout.",
        "Add `content-left-NN`, `content-right-NN` for two-column.",
        "Add `content-metric-NN` for metric highlight.",
        "Add `section-band-NN` for dividers.",
        "",
        "---",
        "",
        "## 6. Layout Templates",
        "",
        "| Template          | When to use                              |",
        "|-------------------|------------------------------------------|",
        "| cover             | First slide; deck title                  |",
        "| section-divider   | Section heading with no body text        |",
        "| bullet-list       | 3–7 bullet points                        |",
        "| two-column        | Side-by-side comparison                  |",
        "| metric-highlight  | 2–4 large numbers or percentages         |",
        "| quote             | A single strong quote                    |",
        "| closing           | Final thank-you slide                    |",
        "",
        "---",
        "",
        "## 7. Layout Examples",
        "",
        "### cover",
        "```xml",
        '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">',
        "  <defs>",
        '    <linearGradient id="bg-grad" x1="0%" y1="0%" x2="100%" y2="100%">',
        f'      <stop offset="0%" stop-color="{bg}" />',
        f'      <stop offset="100%" stop-color="{surf}" stop-opacity="0.4" />',
        "    </linearGradient>",
        "  </defs>",
        f'  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="url(#bg-grad)" /></g>',
        f'  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{accent}" /></g>',
        '  <g id="content-title-01">',
        f'    <text x="640" y="310" font-family="{font}" font-size="60" font-weight="700"',
        f'          fill="{text_c}" text-anchor="middle">DECK TITLE</text>',
        f'    <rect x="540" y="326" width="200" height="4" fill="{accent}" />',
        f'    <text x="640" y="380" font-family="{font}" font-size="26" fill="{body_c}"',
        '          text-anchor="middle">Subtitle or author line</text>',
        "  </g>",
        '  <g id="chrome-footer">',
        f'    <rect x="0" y="688" width="1280" height="32" fill="{surf}" />',
        "  </g>",
        "</svg>",
        "```",
        "",
        "### section-divider",
        "```xml",
        '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">',
        "  <defs>",
        '    <linearGradient id="band-grad" x1="0%" y1="0%" x2="100%" y2="0%">',
        f'      <stop offset="0%" stop-color="{accent}" />',
        f'      <stop offset="100%" stop-color="{accent}" stop-opacity="0.7" />',
        "    </linearGradient>",
        "  </defs>",
        f'  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="{bg}" /></g>',
        f'  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{accent}" /></g>',
        '  <g id="section-band-NN"><rect x="0" y="290" width="1280" height="140" fill="url(#band-grad)" /></g>',
        '  <g id="content-title-NN">',
        f'    <text x="640" y="376" font-family="{font}" font-size="52" font-weight="700"',
        f'          fill="{text_c}" text-anchor="middle">SECTION HEADING</text>',
        "  </g>",
        '  <g id="chrome-footer">',
        f'    <rect x="0" y="688" width="1280" height="32" fill="{surf}" />',
        f'    <text x="1184" y="708" font-family="{font}" font-size="12" fill="{muted}" text-anchor="end">NN / TT</text>',
        "  </g>",
        "</svg>",
        "```",
        "",
        "### bullet-list",
        "```xml",
        '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">',
        f'  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="{bg}" /></g>',
        f'  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{accent}" /></g>',
        '  <g id="content-title-NN">',
        f'    <text x="96" y="100" font-family="{font}" font-size="44" font-weight="700" fill="{text_c}">SLIDE TITLE</text>',
        f'    <rect x="96" y="112" width="80" height="4" fill="{accent}" />',
        "  </g>",
        '  <g id="content-body-NN">',
        "    <!-- Each bullet: row height 64px. First row y=148, next y=212, 276, ... -->",
        f'    <rect x="80" y="148" width="1120" height="56" rx="8" fill="{surf}" />',
        f'    <text x="120" y="183" font-family="{font}" font-size="22" fill="{accent}">&#x2022;</text>',
        f'    <text x="148" y="183" font-family="{font}" font-size="22" fill="{body_c}">First bullet point</text>',
        f'    <rect x="80" y="212" width="1120" height="56" rx="8" fill="{muted}" />',
        f'    <text x="120" y="247" font-family="{font}" font-size="22" fill="{accent}">&#x2022;</text>',
        f'    <text x="148" y="247" font-family="{font}" font-size="22" fill="{body_c}">Second bullet point</text>',
        "  </g>",
        '  <g id="chrome-footer">',
        f'    <rect x="0" y="688" width="1280" height="32" fill="{surf}" />',
        f'    <text x="1184" y="708" font-family="{font}" font-size="12" fill="{muted}" text-anchor="end">NN / TT</text>',
        "  </g>",
        "</svg>",
        "```",
        "",
        "### two-column",
        "```xml",
        '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">',
        f'  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="{bg}" /></g>',
        f'  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{accent}" /></g>',
        '  <g id="content-title-NN">',
        f'    <text x="96" y="80" font-family="{font}" font-size="38" font-weight="700" fill="{text_c}">SLIDE TITLE</text>',
        f'    <rect x="96" y="92" width="60" height="3" fill="{accent}" />',
        "  </g>",
        '  <g id="content-left-NN">',
        f'    <rect x="80" y="112" width="555" height="554" rx="12" fill="{surf}" />',
        f'    <text x="120" y="164" font-family="{font}" font-size="24" font-weight="700" fill="{text_c}">Left Heading</text>',
        f'    <text x="120" y="200" font-family="{font}" font-size="18" fill="{body_c}">Left body content.</text>',
        "  </g>",
        '  <g id="content-right-NN">',
        f'    <rect x="648" y="112" width="555" height="554" rx="12" fill="{surf}" />',
        f'    <text x="688" y="164" font-family="{font}" font-size="24" font-weight="700" fill="{text_c}">Right Heading</text>',
        f'    <text x="688" y="200" font-family="{font}" font-size="18" fill="{body_c}">Right body content.</text>',
        "  </g>",
        '  <g id="chrome-footer">',
        f'    <rect x="0" y="688" width="1280" height="32" fill="{surf}" />',
        f'    <text x="1184" y="708" font-family="{font}" font-size="12" fill="{muted}" text-anchor="end">NN / TT</text>',
        "  </g>",
        "</svg>",
        "```",
        "",
        "### metric-highlight",
        "```xml",
        '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">',
        f'  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="{bg}" /></g>',
        f'  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{accent}" /></g>',
        '  <g id="content-title-NN">',
        f'    <text x="96" y="100" font-family="{font}" font-size="44" font-weight="700" fill="{text_c}">SLIDE TITLE</text>',
        f'    <rect x="96" y="112" width="80" height="4" fill="{accent}" />',
        "  </g>",
        '  <g id="content-metric-NN">',
        "    <!-- 3 equal cards, each ~356px wide, 24px gap -->",
        f'    <rect x="80" y="148" width="356" height="480" rx="16" fill="{surf}" />',
        f'    <text x="258" y="380" font-family="{font}" font-size="72" font-weight="700"',
        f'          fill="{accent}" text-anchor="middle">85%</text>',
        f'    <text x="258" y="430" font-family="{font}" font-size="18" fill="{body_c}" text-anchor="middle">Metric label</text>',
        "  </g>",
        '  <g id="chrome-footer">',
        f'    <rect x="0" y="688" width="1280" height="32" fill="{surf}" />',
        f'    <text x="1184" y="708" font-family="{font}" font-size="12" fill="{muted}" text-anchor="end">NN / TT</text>',
        "  </g>",
        "</svg>",
        "```",
        "",
        "### quote",
        "```xml",
        '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">',
        f'  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="{bg}" /></g>',
        f'  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{accent}" /></g>',
        '  <g id="content-quote-NN">',
        f'    <text x="200" y="280" font-family="{font}" font-size="160" font-weight="700"',
        f'          fill="{accent}" fill-opacity="0.2">"</text>',
        f'    <text x="200" y="370" font-family="{font}" font-size="36" font-style="italic" fill="{text_c}">Quote text here.</text>',
        f'    <text x="200" y="480" font-family="{font}" font-size="20" fill="{body_c}">— Attribution</text>',
        "  </g>",
        '  <g id="chrome-footer">',
        f'    <rect x="0" y="688" width="1280" height="32" fill="{surf}" />',
        "  </g>",
        "</svg>",
        "```",
        "",
        "### closing",
        "```xml",
        '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">',
        "  <defs>",
        '    <radialGradient id="close-grad" cx="50%" cy="50%" r="70%">',
        f'      <stop offset="0%" stop-color="{surf}" />',
        f'      <stop offset="100%" stop-color="{bg}" />',
        "    </radialGradient>",
        "  </defs>",
        '  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="url(#close-grad)" /></g>',
        f'  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{accent}" /></g>',
        '  <g id="content-title-NN">',
        f'    <text x="640" y="310" font-family="{font}" font-size="72" font-weight="700"',
        f'          fill="{text_c}" text-anchor="middle">Thank You</text>',
        f'    <rect x="490" y="328" width="300" height="4" fill="{accent}" />',
        f'    <text x="640" y="390" font-family="{font}" font-size="22" fill="{body_c}"',
        '          text-anchor="middle">contact info / next steps</text>',
        "  </g>",
        '  <g id="chrome-footer">',
        f'    <rect x="0" y="688" width="1280" height="32" fill="{surf}" />',
        "  </g>",
        "</svg>",
        "```",
        "",
        "---",
        "",
        "## 8. Gradients & Filters",
        "",
        "- Always place `linearGradient`, `radialGradient`, `filter` inside `<defs>` at the top of the SVG.",
        "- Reference with `fill=\"url(#id)\"` — only local IDs (`#id`) are allowed.",
        "- Gradient IDs must be unique per file.",
        "- `fill-opacity` and `stop-opacity` are allowed and encouraged.",
        "- `<filter>` with `feGaussianBlur` is allowed for subtle shadows; keep `stdDeviation` ≤ 8.",
        "",
        "---",
        "",
        "## 9. SVG Authoring Rules",
        "",
        "**ALLOWED tags:**",
        "rect circle ellipse line text tspan image path polygon polyline",
        "g defs linearGradient radialGradient stop filter feGaussianBlur feOffset",
        "feFlood feComposite feMerge feMergeNode clipPath pattern use title desc",
        "",
        "**BANNED (hard error — never use):**",
        "script foreignObject iframe animate animateTransform set animateMotion",
        "",
        "**BANNED attributes (hard error):**",
        "onclick onload onmouseover onmouseout onmousedown onmouseup onfocus onblur (any on* handler)",
        "",
        "**Fully permitted (previously restricted):**",
        "opacity fill-opacity stroke-opacity transform class style",
        "",
        "---",
        "",
        "## 10. Pre-save Checklist",
        "",
        '- [ ] `width="1280" height="720" viewBox="0 0 1280 720"` on root `<svg>`',
        "- [ ] `<defs>` block at top if gradients/filters used",
        '- [ ] Left accent stripe `<rect x="0" y="0" width="6" height="720">` present',
        '- [ ] Footer bar `<rect x="0" y="688" width="1280" height="32">` present',
        '- [ ] All top-level `<g>` elements have `id` attribute',
        "- [ ] All text within safe area (x 80–1200, y 80–680)",
        "- [ ] No banned tags or on* event-handler attributes",
        "- [ ] Only local `url(#id)` references in fill/stroke",
        "- [ ] Palette colours match Section 2 exactly",
        "- [ ] Font families match Section 3 typography roles",
        "- [ ] Page rhythm visually matches assignment (anchor/breathing/dense)",
        "",
        "---",
        "",
        "## 11. Executor Reference Documents",
        "",
        "For detailed guidance beyond this design guide, read these reference files",
        "in the `references/` directory:",
        "",
        "| Document | Purpose | When to Read |",
        "|----------|---------|-------------|",
        "| `executor-base.md` | Spec lock protocol, generation rhythm, card patterns, text handling | Before starting ANY page |",
        "| `executor-general.md` | Creative/versatile style guidelines, image integration, composition | For business/marketing decks |",
        "| `executor-academic.md` | Formal/scholarly style, table design, citation formatting | For academic/research decks |",
        "| `shared-standards.md` | SVG tag rules, PPTX compatibility, font safety, gradient limits | When unsure about a tag/attribute |",
        "| `image-layout-patterns.md` | 72+ image-layout composition patterns | When placing images on slides |",
        "| `image-layout-spec.md` | Pixel-precise coordinates for each layout pattern | When calculating image positions |",
        "| `image-base.md` | AI image generation best practices, prompt templates | When generating images |",
        "",
        "**Template Libraries** (in `templates/` directory):",
        "",
        "| Library | Contents | When to Use |",
        "|---------|----------|-------------|",
        "| `templates/charts/` | 17 chart/visualization SVG templates | When creating data slides |",
        "| `templates/layouts/general/` | 8 general-purpose layout templates | For business/marketing decks |",
        "| `templates/layouts/academic/` | 8 formal/scholarly layout templates | For academic/research decks |",
        "| `templates/layouts/creative/` | 8 bold/editorial layout templates | For creative/portfolio decks |",
        "",
        "> **Start with `executor-base.md`** — it contains the essential workflow.",
        "> Then read the style-specific guide that matches your deck's audience.",
        "> Consult `shared-standards.md` for any technical SVG questions.",
        "> Use `image-layout-patterns.md` and `image-base.md` for image-rich slides.",
    ]

    return "\n".join(lines) + "\n"
