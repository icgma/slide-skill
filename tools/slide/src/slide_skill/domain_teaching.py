"""Teaching-domain SVG renderers for slide-skill v3.0.

Provides specialized layouts for educational content:
  - vocab-card:        Vocabulary flashcard grid (≤4 items, large type)
  - sentence-example:  Example sentences with translation
  - dialogue:          Conversation bubbles (A/B speakers)
  - grammar-point:     Rule box + example pairs
  - exercise:          Practice activities (fill-in, translate, etc.)

All renderers share the same signature and reuse chrome/decor helpers
from svg_pipeline so they blend seamlessly with existing themes.
"""

from __future__ import annotations

from .content_planner import ContentItem, SlidePlan
from .util import xml_escape


# ---------------------------------------------------------------------------
# Shared helpers (mirrored from svg_pipeline for decoupling)
# ---------------------------------------------------------------------------

def _chrome(index: int, total: int, lock: dict, w: int, h: int) -> str:
    """Left accent stripe + footer bar — same as svg_pipeline._chrome."""
    p = lock["palette"]
    font = lock["font_family"]
    return (
        f'  <g id="chrome-stripe">\n'
        f'    <rect x="0" y="0" width="6" height="{h}" fill="{p["accent"]}" />\n'
        f'  </g>\n'
        f'  <g id="chrome-footer">\n'
        f'    <rect x="0" y="{h - 32}" width="{w}" height="32" fill="{p["surface"]}" />\n'
        f'    <text x="{w - 96}" y="{h - 10}" font-family="{font}" font-size="12" '
        f'fill="{p["muted"]}" text-anchor="end">{index:02d} / {total:02d}</text>\n'
        f'  </g>'
    )


def _decor_orbs(index: int, lock: dict, w: int, h: int, intensity: float = 0.10) -> tuple[str, str]:
    """Subtle decorative orbs."""
    p = lock["palette"]
    defs = (
        f'    <radialGradient id="teach-orb-{index:02d}" cx="50%" cy="50%" r="50%">\n'
        f'      <stop offset="0%" stop-color="{p["accent"]}" stop-opacity="{intensity}"/>\n'
        f'      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0"/>\n'
        f'    </radialGradient>'
    )
    body = (
        f'  <g id="decor-{index:02d}">\n'
        f'    <circle cx="{w - 80}" cy="60" r="280" fill="url(#teach-orb-{index:02d})"/>\n'
        f'  </g>'
    )
    return defs, body


def _svg_open(w: int, h: int) -> str:
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">'


# ---------------------------------------------------------------------------
# Vocab Card Layout
# ---------------------------------------------------------------------------

def render_vocab_card(plan: SlidePlan, lock: dict, total: int) -> str:
    """Render a vocabulary card slide.

    Layout: 1-4 large vocab items in a grid.
    Each item shows:
      - Chinese characters (large, primary color)
      - Pinyin above (accent color, smaller)
      - English translation below (muted, smaller)
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h)
    title = xml_escape(plan.title)

    items = [i for i in plan.items if i.type == "vocab"]
    count = min(len(items), 4)
    if count == 0:
        # Fallback to default text layout
        return _render_text_fallback(plan, lock, total)

    # Grid layout: 1 item = centered, 2 = side by side, 3-4 = 2x2 grid
    if count <= 2:
        cols, rows = count, 1
    else:
        cols, rows = 2, 2

    card_w = (w - 160 - (cols - 1) * 32) // cols
    card_h = (h - 240 - (rows - 1) * 24) // rows
    start_x = 80
    start_y = 160

    cards_svg: list[str] = []
    for idx, item in enumerate(items[:count]):
        col = idx % cols
        row = idx // cols
        cx = start_x + col * (card_w + 32)
        cy = start_y + row * (card_h + 24)
        mid_x = cx + card_w // 2
        mid_y = cy + card_h // 2

        # Card background
        cards_svg.append(
            f'    <rect x="{cx}" y="{cy}" width="{card_w}" height="{card_h}" '
            f'rx="16" fill="{p["surface"]}"/>'
        )
        # Top accent bar
        cards_svg.append(
            f'    <rect x="{cx}" y="{cy}" width="{card_w}" height="5" '
            f'rx="3" fill="{p["accent"]}"/>'
        )

        # Pinyin (above Chinese, accent color)
        if item.tertiary:
            pinyin = xml_escape(item.tertiary)
            cards_svg.append(
                f'    <text x="{mid_x}" y="{mid_y - 50}" font-family="{font}" '
                f'font-size="22" font-style="italic" fill="{p["accent"]}" '
                f'text-anchor="middle">{pinyin}</text>'
            )

        # Chinese characters (large, centered, primary)
        chinese = xml_escape(item.primary)
        # Auto-size: shorter words get bigger font
        zh_len = len(item.primary)
        if zh_len <= 2:
            zh_font = 64
        elif zh_len <= 4:
            zh_font = 52
        else:
            zh_font = 40

        cards_svg.append(
            f'    <text x="{mid_x}" y="{mid_y + 10}" font-family="{font}" '
            f'font-size="{zh_font}" font-weight="700" fill="{p["text"]}" '
            f'text-anchor="middle">{chinese}</text>'
        )

        # English translation (below Chinese, muted)
        if item.secondary:
            eng = xml_escape(item.secondary)
            cards_svg.append(
                f'    <text x="{mid_x}" y="{mid_y + 60}" font-family="{font}" '
                f'font-size="18" fill="{p["body"]}" '
                f'text-anchor="middle">{eng}</text>'
            )

    card_content = "\n".join(cards_svg)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'  <g id="content-title-{plan.index:02d}">\n'
        f'    <text x="96" y="108" font-family="{font}" font-size="36" '
        f'font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'    <rect x="96" y="120" width="60" height="4" fill="{p["accent"]}"/>\n'
        f'  </g>\n'
        f'  <g id="content-vocab-{plan.index:02d}">\n'
        f'{card_content}\n'
        f'  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Dialogue Layout
# ---------------------------------------------------------------------------

def render_dialogue(plan: SlidePlan, lock: dict, total: int) -> str:
    """Render a dialogue/conversation slide.

    Layout: Alternating speech bubbles, left-aligned for speaker A,
    right-aligned for speaker B. Clean chat-style layout.
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h, intensity=0.06)
    title = xml_escape(plan.title)

    items = [i for i in plan.items if i.type == "dialogue"]
    bubble_parts: list[str] = []
    bubble_y = 180
    bubble_h = 70
    gap = 16
    max_bubble_w = w - 300  # Leave room for speaker label

    for item in items:
        speaker = item.meta.get("speaker", "A")
        text = xml_escape(item.primary[:80])
        annotation = xml_escape(item.secondary[:80]) if item.secondary else ""

        is_left = speaker in ("A", "甲")
        if is_left:
            bx = 120
            label_x = 80
            text_x = bx + 24
            label_anchor = "end"
        else:
            bx = w - max_bubble_w - 120
            label_x = w - 80
            text_x = bx + 24
            label_anchor = "start"

        # Speaker label circle
        circle_x = label_x if is_left else label_x
        bubble_parts.append(
            f'    <circle cx="{80 if is_left else w - 80}" cy="{bubble_y + 24}" '
            f'r="20" fill="{p["accent"]}" opacity="0.15"/>'
        )
        bubble_parts.append(
            f'    <text x="{80 if is_left else w - 80}" y="{bubble_y + 30}" '
            f'font-family="{font}" font-size="16" font-weight="700" '
            f'fill="{p["accent"]}" text-anchor="middle">{xml_escape(speaker)}</text>'
        )

        # Speech bubble
        fill = p["surface"] if is_left else p["accent"]
        text_fill = p["text"] if is_left else p["background"]
        bubble_parts.append(
            f'    <rect x="{bx}" y="{bubble_y}" width="{max_bubble_w}" '
            f'height="{bubble_h}" rx="14" fill="{fill}"/>'
        )
        bubble_parts.append(
            f'    <text x="{text_x}" y="{bubble_y + 32}" font-family="{font}" '
            f'font-size="22" fill="{text_fill}">{text}</text>'
        )

        # Annotation (translation) below the main text
        if annotation:
            bubble_parts.append(
                f'    <text x="{text_x}" y="{bubble_y + 55}" font-family="{font}" '
                f'font-size="14" font-style="italic" fill="{p["body"]}">{annotation}</text>'
            )

        bubble_y += bubble_h + gap

    bubble_content = "\n".join(bubble_parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n{orb_defs}\n  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'  <g id="content-title-{plan.index:02d}">\n'
        f'    <text x="96" y="108" font-family="{font}" font-size="36" '
        f'font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'    <rect x="96" y="120" width="60" height="4" fill="{p["accent"]}"/>\n'
        f'  </g>\n'
        f'  <g id="content-dialogue-{plan.index:02d}">\n'
        f'{bubble_content}\n'
        f'  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Sentence Example Layout
# ---------------------------------------------------------------------------

def render_sentence_example(plan: SlidePlan, lock: dict, total: int) -> str:
    """Render example sentences with translations.

    Each sentence gets a numbered card with the source text prominent
    and the translation below in muted color.
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h)
    title = xml_escape(plan.title)

    items = plan.items
    parts: list[str] = []
    y = 180
    card_h = 90
    gap = 16
    card_w = w - 180

    for idx, item in enumerate(items[:5]):
        cx = 90
        text = xml_escape(item.primary[:100])
        trans = xml_escape(item.secondary[:100]) if item.secondary else ""

        # Card background
        parts.append(
            f'    <rect x="{cx}" y="{y}" width="{card_w}" height="{card_h}" '
            f'rx="12" fill="{p["surface"]}"/>'
        )
        # Number badge
        parts.append(
            f'    <circle cx="{cx + 30}" cy="{y + card_h // 2}" r="16" '
            f'fill="{p["accent"]}" opacity="0.15"/>'
        )
        parts.append(
            f'    <text x="{cx + 30}" y="{y + card_h // 2 + 6}" font-family="{font}" '
            f'font-size="14" font-weight="700" fill="{p["accent"]}" '
            f'text-anchor="middle">{idx + 1}</text>'
        )
        # Main sentence
        parts.append(
            f'    <text x="{cx + 64}" y="{y + 36}" font-family="{font}" '
            f'font-size="24" font-weight="600" fill="{p["text"]}">{text}</text>'
        )
        # Translation
        if trans:
            parts.append(
                f'    <text x="{cx + 64}" y="{y + 64}" font-family="{font}" '
                f'font-size="16" font-style="italic" fill="{p["body"]}">{trans}</text>'
            )

        y += card_h + gap

    content = "\n".join(parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n{orb_defs}\n  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'  <g id="content-title-{plan.index:02d}">\n'
        f'    <text x="96" y="108" font-family="{font}" font-size="36" '
        f'font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'    <rect x="96" y="120" width="60" height="4" fill="{p["accent"]}"/>\n'
        f'  </g>\n'
        f'  <g id="content-examples-{plan.index:02d}">\n'
        f'{content}\n'
        f'  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Exercise Layout
# ---------------------------------------------------------------------------

def render_exercise(plan: SlidePlan, lock: dict, total: int) -> str:
    """Render a practice/exercise slide.

    Clean layout with numbered exercise items. Each item gets a
    translucent card with enough space for students to think.
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    chrome = _chrome(plan.index, total, lock, w, h)
    title = xml_escape(plan.title)

    items = plan.items
    parts: list[str] = []
    y = 200
    item_h = 70
    gap = 20

    # Section label
    parts.append(
        f'    <rect x="80" y="150" width="120" height="28" rx="14" fill="{p["accent"]}"/>'
    )
    parts.append(
        f'    <text x="140" y="170" font-family="{font}" font-size="13" '
        f'font-weight="600" fill="{p["background"]}" text-anchor="middle">PRACTICE</text>'
    )

    for idx, item in enumerate(items[:6]):
        text = xml_escape(item.primary[:120])

        # Exercise number
        parts.append(
            f'    <text x="96" y="{y + 30}" font-family="{font}" font-size="28" '
            f'font-weight="700" fill="{p["accent"]}">{idx + 1}.</text>'
        )
        # Exercise text
        parts.append(
            f'    <text x="140" y="{y + 30}" font-family="{font}" font-size="22" '
            f'fill="{p["text"]}">{text}</text>'
        )
        # Subtle separator
        if idx < len(items) - 1:
            parts.append(
                f'    <rect x="96" y="{y + item_h - 8}" width="{w - 200}" '
                f'height="1" fill="{p["muted"]}" opacity="0.3"/>'
            )

        y += item_h + gap

    content = "\n".join(parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs></defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{chrome}\n'
        f'  <g id="content-title-{plan.index:02d}">\n'
        f'    <text x="96" y="108" font-family="{font}" font-size="36" '
        f'font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'    <rect x="96" y="120" width="60" height="4" fill="{p["accent"]}"/>\n'
        f'  </g>\n'
        f'  <g id="content-exercise-{plan.index:02d}">\n'
        f'{content}\n'
        f'  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Text fallback (for plans that don't match a specialized layout)
# ---------------------------------------------------------------------------

def _render_text_fallback(plan: SlidePlan, lock: dict, total: int) -> str:
    """Simple text layout — used when a plan has no specialized items."""
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    chrome = _chrome(plan.index, total, lock, w, h)
    title = xml_escape(plan.title)

    body_parts: list[str] = []
    y = 200
    for item in plan.items[:8]:
        text = xml_escape(item.primary[:120])
        body_parts.append(
            f'    <text x="96" y="{y}" font-family="{font}" font-size="22" '
            f'fill="{p["text"]}">{text}</text>'
        )
        y += 36

    body_content = "\n".join(body_parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs></defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{chrome}\n'
        f'  <g id="content-title-{plan.index:02d}">\n'
        f'    <text x="96" y="108" font-family="{font}" font-size="36" '
        f'font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'    <rect x="96" y="120" width="60" height="4" fill="{p["accent"]}"/>\n'
        f'  </g>\n'
        f'  <g id="content-body-{plan.index:02d}">\n'
        f'{body_content}\n'
        f'  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

# Map layout names from SlidePlan to render functions
TEACHING_RENDERERS: dict[str, callable] = {
    "vocab-card": render_vocab_card,
    "dialogue": render_dialogue,
    "sentence-example": render_sentence_example,
    "exercise": render_exercise,
}


def render_teaching_slide(plan: SlidePlan, lock: dict, total: int) -> str | None:
    """Try to render a teaching-specific layout. Returns None if layout is not teaching."""
    renderer = TEACHING_RENDERERS.get(plan.layout)
    if renderer is None:
        return None
    return renderer(plan, lock, total)
