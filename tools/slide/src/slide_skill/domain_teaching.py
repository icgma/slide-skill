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
from .svg_shared import (
    adaptive_title_font,
    card_style_params,
    chrome_body,
    chrome_defs,
    decor_orbs,
    design_tokens,
    hex_shift,
    is_light,
    shadow_filter_def,
    svg_open,
    title_block,
    title_underline,
)
from .util import xml_escape


# ---------------------------------------------------------------------------
# Local aliases — single source of truth is svg_shared
# ---------------------------------------------------------------------------

_tokens = design_tokens
_hex_shift = hex_shift
_shadow_filter_def = shadow_filter_def
_svg_open = svg_open
_title_underline = title_underline
_title_block = title_block
_decor_orbs = decor_orbs


def _chrome(index: int, total: int, lock: dict, w: int, h: int) -> str:
    """Wrapper combining svg_shared chrome_defs + chrome_body."""
    defs = chrome_defs(index, lock, w, h)
    body = chrome_body(index, total, lock, w, h)
    return f'  <defs>\n{defs}\n  </defs>\n{body}'


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
    t = _tokens(w, h)
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

    m = t["margin"]["content"]
    card_w = (w - m * 2 - (cols - 1) * 32) // cols
    card_h = (h - m * 2 - 80 - (rows - 1) * 24) // rows
    start_x = m
    start_y = m + 80

    defs_parts: list[str] = [
        _shadow_filter_def(plan.index),
        orb_defs
    ]
    cards_svg: list[str] = []

    for idx, item in enumerate(items[:count]):
        col = idx % cols
        row = idx // cols
        cx = start_x + col * (card_w + 32)
        cy = start_y + row * (card_h + 24)
        mid_x = cx + card_w // 2
        mid_y = cy + card_h // 2

        ca = _hex_shift(p["accent"], idx * 15 - 30)
        cs = card_style_params(lock, idx)
        grad_id = f"vocab-card-grad-{plan.index:02d}-{idx}"
        clip_id = f"vocab-card-clip-{plan.index:02d}-{idx}"

        defs_parts.append(
            f'    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{cs["fill_opacity_start"]}"/>\n'
            f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -10)}" stop-opacity="{cs["fill_opacity_end"]}"/>\n'
            f'    </linearGradient>'
        )
        defs_parts.append(
            f'    <clipPath id="{clip_id}">\n'
            f'      <rect x="{cx}" y="{cy}" width="{card_w}" height="{card_h}" rx="16" />\n'
            f'    </clipPath>'
        )

        cards_svg.append(
            f'    <g clip-path="url(#{clip_id})">\n'
            f'      <rect x="{cx}" y="{cy}" width="{card_w}" height="{card_h}" fill="url(#{grad_id})"/>\n'
            f'      <rect x="{cx}" y="{cy}" width="{card_w}" height="5" fill="{ca}" opacity="0.85"/>\n'
            f'    </g>'
        )

        cards_svg.append(
            f'    <rect x="{cx}" y="{cy}" width="{card_w}" height="{card_h}" rx="16" fill="none" '
            f'stroke="{ca}" stroke-opacity="{cs["stroke_opacity"]}" stroke-width="{cs["stroke_width"]}" '
            f'filter="url(#card-shadow-{plan.index:02d})"/>'
        )

        if cs["inner_border"]:
            cards_svg.append(
                f'    <rect x="{cx + 6}" y="{cy + 6}" width="{card_w - 12}" height="{card_h - 12}" rx="12" fill="none" '
                f'stroke="{ca}" stroke-opacity="{cs["inner_stroke_opacity"]}" stroke-width="{cs["inner_stroke_width"]}"/>'
            )

        # Pinyin (above Chinese, shifted accent color)
        if item.tertiary:
            pinyin = xml_escape(item.tertiary)
            cards_svg.append(
                f'    <text x="{mid_x}" y="{mid_y - 36}" font-family="{font}" '
                f'font-size="20" font-weight="600" fill="{ca}" '
                f'text-anchor="middle">{pinyin}</text>'
            )

        # Chinese characters (large, centered, primary)
        chinese = xml_escape(item.primary)
        zh_len = len(item.primary)
        if zh_len <= 2:
            zh_font = 64
        elif zh_len <= 4:
            zh_font = 48
        else:
            zh_font = 40

        cards_svg.append(
            f'    <text x="{mid_x}" y="{mid_y + 12}" font-family="{font}" '
            f'font-size="{zh_font}" font-weight="700" fill="{p["text"]}" '
            f'text-anchor="middle">{chinese}</text>'
        )

        # English translation (below Chinese, muted)
        if item.secondary:
            from .svg_pipeline import _wrap_to_tspans
            eng_font = 20
            eng_w = card_w - 32
            tspans, line_count = _wrap_to_tspans(item.secondary, mid_x, eng_font, eng_w, line_height=1.2)
            ey = mid_y + 42 - ((line_count - 1) * 15 // 2)
            cards_svg.append(
                f'    <text x="{mid_x}" y="{ey}" font-family="{font}" '
                f'font-size="{eng_font}" fill="{p["body"]}" '
                f'text-anchor="middle">{tspans}</text>'
            )

    card_content = "\n".join(cards_svg)
    defs_content = "\n".join(defs_parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n'
        f'{defs_content}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, plan.title, lock, w, h)}\n'
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
    t = _tokens(w, h)
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h, intensity=0.12)
    title = xml_escape(plan.title)

    items = [i for i in plan.items if i.type == "dialogue"]
    bubble_parts: list[str] = []
    
    max_bubble_w = w - 320  # Leave room for speaker label

    accent_lighter = _hex_shift(p["accent"], 40)
    defs_parts: list[str] = [
        _shadow_filter_def(plan.index),
        orb_defs
    ]

    from .svg_pipeline import _wrap_to_tspans
    
    dialogue_data = []
    total_bubble_h = 0
    count = min(len(items), 4)
    if count == 0:
        return _render_text_fallback(plan, lock, total)
        
    for idx, item in enumerate(items[:count]):
        speaker = item.meta.get("speaker", "A")
        is_left = speaker in ("A", "甲", "1") or idx % 2 == 0
        
        if is_left:
            bx = 130
            text_x = bx + 24
        else:
            bx = w - max_bubble_w - 130
            text_x = bx + 24
            
        text_w = max_bubble_w - 48
        p_tspans, p_lines = _wrap_to_tspans(item.primary, text_x, 18, text_w, line_height=1.3)
        p_h = p_lines * 23
        
        s_tspans, s_lines = "", 0
        s_h = 0
        if item.secondary:
            s_tspans, s_lines = _wrap_to_tspans(item.secondary, text_x, 13, text_w, line_height=1.3)
            s_h = s_lines * 16
            
        text_h = p_h + (s_h + 8 if item.secondary else 0)
        curr_bubble_h = max(72, text_h + 28)
        
        total_bubble_h += curr_bubble_h
        dialogue_data.append({
            "item": item,
            "speaker": speaker,
            "is_left": is_left,
            "bx": bx,
            "text_x": text_x,
            "p_tspans": p_tspans,
            "s_tspans": s_tspans,
            "text_h": text_h,
            "p_h": p_h,
            "bubble_h": curr_bubble_h
        })
        
    # Calculate gaps and starting y
    content_h = h - 220
    gap = min(16, max(10, (content_h - total_bubble_h) // max(count - 1, 1))) if count > 1 else 16
    bubble_y = 150 + max(0, (content_h - (total_bubble_h + gap * (count - 1))) // 2)

    for idx, data in enumerate(dialogue_data):
        bx = data["bx"]
        text_x = data["text_x"]
        bubble_h = data["bubble_h"]
        speaker = data["speaker"]
        is_left = data["is_left"]
        p_tspans = data["p_tspans"]
        s_tspans = data["s_tspans"]
        text_h = data["text_h"]
        p_h = data["p_h"]
        
        if is_left:
            label_x = 80
        else:
            label_x = w - 80
            
        ca = p["accent"] if is_left else accent_lighter
        cs = card_style_params(lock, idx)
        grad_id = f"dialogue-bubble-grad-{plan.index:02d}-{idx}"
        clip_id = f"dialogue-bubble-clip-{plan.index:02d}-{idx}"

        defs_parts.append(
            f'    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{cs["fill_opacity_start"]}"/>\n'
            f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -10)}" stop-opacity="{cs["fill_opacity_end"]}"/>\n'
            f'    </linearGradient>'
        )
        defs_parts.append(
            f'    <clipPath id="{clip_id}">\n'
            f'      <rect x="{bx}" y="{bubble_y}" width="{max_bubble_w}" height="{bubble_h}" rx="14" />\n'
            f'    </clipPath>'
        )
        
        # Speaker label circle with concentric glowing rings
        label_cy = bubble_y + bubble_h // 2
        bubble_parts.append(
            f'    <circle cx="{label_x}" cy="{label_cy}" r="26" '
            f'fill="{ca}" fill-opacity="0.04" stroke="{ca}" stroke-opacity="0.1" stroke-width="1"/>'
        )
        bubble_parts.append(
            f'    <circle cx="{label_x}" cy="{label_cy}" r="21" '
            f'fill="{ca}" fill-opacity="0.08" stroke="{ca}" stroke-opacity="0.2" stroke-dasharray="3 2" stroke-width="1"/>'
        )
        bubble_parts.append(
            f'    <circle cx="{label_x}" cy="{label_cy}" r="17" '
            f'fill="{ca}" fill-opacity="0.15" stroke="{ca}" stroke-opacity="0.3"/>'
        )
        bubble_parts.append(
            f'    <text x="{label_x}" y="{label_cy + 6}" font-family="{font}" font-size="20" font-weight="700" '
            f'fill="{ca}" text-anchor="middle">{xml_escape(speaker)}</text>'
        )
        
        # Speech bubble body with clip path
        bubble_parts.append(
            f'    <g clip-path="url(#{clip_id})">\n'
            f'      <rect x="{bx}" y="{bubble_y}" width="{max_bubble_w}" height="{bubble_h}" fill="url(#{grad_id})"/>\n'
            f'      <!-- Left/Right accent stripe -->\n'
            f'      <rect x="{bx if is_left else bx + max_bubble_w - 4}" y="{bubble_y}" width="4" height="{bubble_h}" fill="{ca}" opacity="0.85"/>\n'
            f'    </g>'
        )
        
        # Outer bubble frame
        bubble_parts.append(
            f'    <rect x="{bx}" y="{bubble_y}" width="{max_bubble_w}" height="{bubble_h}" rx="14" fill="none" '
            f'stroke="{ca}" stroke-opacity="{cs["stroke_opacity"]}" stroke-width="{cs["stroke_width"]}" '
            f'filter="url(#card-shadow-{plan.index:02d})"/>'
        )

        if cs["inner_border"]:
            bubble_parts.append(
                f'    <rect x="{bx + 5}" y="{bubble_y + 5}" width="{max_bubble_w - 10}" height="{bubble_h - 10}" rx="10" fill="none" '
                f'stroke="{ca}" stroke-opacity="{cs["inner_stroke_opacity"]}" stroke-width="{cs["inner_stroke_width"]}"/>'
            )
        
        # Text Y position logic: vertically centered
        text_padding = (bubble_h - text_h) // 2
        py = bubble_y + text_padding + 16 # shift down by font size baseline
        
        bubble_parts.append(
            f'    <text x="{text_x}" y="{py}" font-family="{font}" '
            f'font-size="22" font-weight="600" fill="{p["text"]}">{p_tspans}</text>'
        )

        if s_tspans:
            sy = py + p_h + 8 - 3
            bubble_parts.append(
                f'    <text x="{text_x}" y="{sy}" font-family="{font}" '
                f'font-size="17" font-style="italic" fill="{p["body"]}" opacity="0.9">{s_tspans}</text>'
            )
            
        bubble_y += bubble_h + gap

    bubble_content = "\n".join(bubble_parts)
    defs_content = "\n".join(defs_parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n'
        f'{defs_content}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, plan.title, lock, w, h)}\n'
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
    t = _tokens(w, h)
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h)
    title = xml_escape(plan.title)

    items = plan.items
    parts: list[str] = []
    
    card_w = w - 180
    text_w = card_w - 96
    
    defs_parts: list[str] = [
        _shadow_filter_def(plan.index),
        orb_defs
    ]

    from .svg_pipeline import _wrap_to_tspans
    
    sentence_data = []
    total_card_h = 0
    count = min(len(items), 5)
    if count == 0:
        return _render_text_fallback(plan, lock, total)
        
    for idx, item in enumerate(items[:count]):
        cx = 90
        text_x = cx + 72
        
        p_tspans, p_lines = _wrap_to_tspans(item.primary, text_x, 22, text_w, line_height=1.3)
        p_h = p_lines * 28
        
        s_tspans, s_lines = "", 0
        s_h = 0
        if item.secondary:
            s_tspans, s_lines = _wrap_to_tspans(item.secondary, text_x, 15, text_w, line_height=1.3)
            s_h = s_lines * 19
            
        text_h = p_h + (s_h + 8 if item.secondary else 0)
        curr_card_h = max(80, text_h + 28)
        
        total_card_h += curr_card_h
        sentence_data.append({
            "item": item,
            "cx": cx,
            "text_x": text_x,
            "p_tspans": p_tspans,
            "s_tspans": s_tspans,
            "text_h": text_h,
            "p_h": p_h,
            "card_h": curr_card_h
        })
        
    # Calculate starting y and gaps
    content_h = h - 220
    gap = min(16, max(10, (content_h - total_card_h) // max(count - 1, 1))) if count > 1 else 16
    y = 150 + max(0, (content_h - (total_card_h + gap * (count - 1))) // 2)

    for idx, data in enumerate(sentence_data):
        cx = data["cx"]
        text_x = data["text_x"]
        card_h = data["card_h"]
        p_tspans = data["p_tspans"]
        s_tspans = data["s_tspans"]
        text_h = data["text_h"]
        p_h = data["p_h"]
        
        ca = _hex_shift(p["accent"], idx * 15 - 30)
        cs = card_style_params(lock, idx)
        grad_id = f"sent-card-grad-{plan.index:02d}-{idx}"
        clip_id = f"sent-card-clip-{plan.index:02d}-{idx}"

        defs_parts.append(
            f'    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{cs["fill_opacity_start"]}"/>\n'
            f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -10)}" stop-opacity="{cs["fill_opacity_end"]}"/>\n'
            f'    </linearGradient>'
        )
        defs_parts.append(
            f'    <clipPath id="{clip_id}">\n'
            f'      <rect x="{cx}" y="{y}" width="{card_w}" height="{card_h}" rx="14" />\n'
            f'    </clipPath>'
        )

        parts.append(
            f'    <g clip-path="url(#{clip_id})">\n'
            f'      <rect x="{cx}" y="{y}" width="{card_w}" height="{card_h}" fill="url(#{grad_id})"/>\n'
            f'      <rect x="{cx}" y="{y}" width="5" height="{card_h}" fill="{ca}" opacity="0.85"/>\n'
            f'    </g>'
        )

        parts.append(
            f'    <rect x="{cx}" y="{y}" width="{card_w}" height="{card_h}" rx="14" fill="none" '
            f'stroke="{ca}" stroke-opacity="{cs["stroke_opacity"]}" stroke-width="{cs["stroke_width"]}" '
            f'filter="url(#card-shadow-{plan.index:02d})"/>'
        )

        if cs["inner_border"]:
            parts.append(
                f'    <rect x="{cx + 5}" y="{y + 5}" width="{card_w - 10}" height="{card_h - 10}" rx="10" fill="none" '
                f'stroke="{ca}" stroke-opacity="{cs["inner_stroke_opacity"]}" stroke-width="{cs["inner_stroke_width"]}"/>'
            )
        
        # Number badge (Concentric rings)
        badge_cx = cx + 36
        badge_cy = y + card_h // 2
        parts.append(
            f'    <circle cx="{badge_cx}" cy="{badge_cy}" r="20" '
            f'fill="{ca}" fill-opacity="0.05" stroke="{ca}" stroke-opacity="0.1" stroke-width="1"/>'
        )
        parts.append(
            f'    <circle cx="{badge_cx}" cy="{badge_cy}" r="15" '
            f'fill="{ca}" fill-opacity="0.12" stroke="{ca}" stroke-opacity="0.25" stroke-width="1"/>'
        )
        parts.append(
            f'    <text x="{badge_cx}" y="{badge_cy + 5}" font-family="{font}" '
            f'font-size="16" font-weight="700" fill="{ca}" '
            f'text-anchor="middle">{idx + 1}</text>'
        )
        
        # Text Y positioning: centered
        text_padding = (card_h - text_h) // 2
        py = y + text_padding + 20
        
        # Main sentence
        parts.append(
            f'    <text x="{text_x}" y="{py}" font-family="{font}" '
            f'font-size="26" font-weight="600" fill="{p["text"]}">{p_tspans}</text>'
        )
        # Translation
        if s_tspans:
            sy = py + p_h + 8 - 4
            parts.append(
                f'    <text x="{text_x}" y="{sy}" font-family="{font}" '
                f'font-size="19" font-style="italic" fill="{p["body"]}" opacity="0.9">{s_tspans}</text>'
            )
            
        y += card_h + gap

    content = "\n".join(parts)
    defs_content = "\n".join(defs_parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n'
        f'{defs_content}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, plan.title, lock, w, h)}\n'
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

    Clean layout with numbered exercise items inside frosted glass cards.
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h, intensity=0.08)
    title = xml_escape(plan.title)

    items = plan.items
    parts: list[str] = []
    
    # Top Section label (PRACTICE badge)
    parts.append(
        f'    <rect x="90" y="145" width="100" height="24" rx="12" fill="{p["accent"]}" fill-opacity="0.12" stroke="{p["accent"]}" stroke-opacity="0.25" stroke-width="1"/>'
    )
    parts.append(
        f'    <text x="140" y="161" font-family="{font}" font-size="15" '
        f'font-weight="700" fill="{p["accent"]}" text-anchor="middle" letter-spacing="1">PRACTICE</text>'
    )

    card_w = w - 180
    text_w = card_w - 88
    
    defs_parts: list[str] = [
        _shadow_filter_def(plan.index),
        orb_defs
    ]

    from .svg_pipeline import _wrap_to_tspans
    
    exercise_data = []
    total_card_h = 0
    count = min(len(items), 6)
    if count == 0:
        return _render_text_fallback(plan, lock, total)
        
    for idx, item in enumerate(items[:count]):
        cx = 90
        text_x = cx + 64
        
        tspans, lines = _wrap_to_tspans(item.primary, text_x, 18, text_w, line_height=1.3)
        text_h = lines * 23
        curr_card_h = max(56, text_h + 20)
        
        total_card_h += curr_card_h
        exercise_data.append({
            "item": item,
            "cx": cx,
            "text_x": text_x,
            "tspans": tspans,
            "text_h": text_h,
            "card_h": curr_card_h
        })
        
    # Calculate starting y and gaps
    content_h = h - 240
    gap = min(12, max(8, (content_h - total_card_h) // max(count - 1, 1))) if count > 1 else 12
    y = 185 + max(0, (content_h - (total_card_h + gap * (count - 1))) // 2)

    for idx, data in enumerate(exercise_data):
        cx = data["cx"]
        text_x = data["text_x"]
        card_h = data["card_h"]
        tspans = data["tspans"]
        text_h = data["text_h"]
        
        ca = _hex_shift(p["accent"], idx * 10 - 25)
        cs = card_style_params(lock, idx)
        grad_id = f"exercise-card-grad-{plan.index:02d}-{idx}"
        clip_id = f"exercise-card-clip-{plan.index:02d}-{idx}"

        defs_parts.append(
            f'    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{cs["fill_opacity_start"]}"/>\n'
            f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -8)}" stop-opacity="{cs["fill_opacity_end"]}"/>\n'
            f'    </linearGradient>'
        )
        defs_parts.append(
            f'    <clipPath id="{clip_id}">\n'
            f'      <rect x="{cx}" y="{y}" width="{card_w}" height="{card_h}" rx="10" />\n'
            f'    </clipPath>'
        )

        parts.append(
            f'    <g clip-path="url(#{clip_id})">\n'
            f'      <rect x="{cx}" y="{y}" width="{card_w}" height="{card_h}" fill="url(#{grad_id})"/>\n'
            f'      <rect x="{cx}" y="{y}" width="4" height="{card_h}" fill="{ca}" opacity="0.85"/>\n'
            f'    </g>'
        )

        parts.append(
            f'    <rect x="{cx}" y="{y}" width="{card_w}" height="{card_h}" rx="10" fill="none" '
            f'stroke="{ca}" stroke-opacity="{cs["stroke_opacity"]}" stroke-width="{cs["stroke_width"]}" '
            f'filter="url(#card-shadow-{plan.index:02d})"/>'
        )

        if cs["inner_border"]:
            parts.append(
                f'    <rect x="{cx + 5}" y="{y + 5}" width="{card_w - 10}" height="{card_h - 10}" rx="8" fill="none" '
                f'stroke="{ca}" stroke-opacity="{cs["inner_stroke_opacity"]}" stroke-width="{cs["inner_stroke_width"]}"/>'
            )
        
        text_padding = (card_h - text_h) // 2
        py = y + text_padding + 15
        
        # Exercise number
        parts.append(
            f'    <text x="{cx + 24}" y="{py}" font-family="{font}" font-size="24" '
            f'font-weight="700" fill="{ca}">{idx + 1}.</text> '
        )
        # Exercise text
        parts.append(
            f'    <text x="{cx + 64}" y="{py - 1}" font-family="{font}" font-size="22" '
            f'font-weight="500" fill="{p["text"]}">{tspans}</text>'
        )
        
        y += card_h + gap

    content = "\n".join(parts)
    defs_content = "\n".join(defs_parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n'
        f'{defs_content}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, plan.title, lock, w, h)}\n'
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
    t = _tokens(w, h)
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h, intensity=0.08)
    title = xml_escape(plan.title)

    card_x = 90
    card_y = 160
    card_w = w - 180
    card_h = h - 230

    ca = p["accent"]
    cs = card_style_params(lock, 0)
    grad_id = f"fallback-card-grad-{plan.index:02d}"
    clip_id = f"fallback-card-clip-{plan.index:02d}"

    defs_parts: list[str] = [
        orb_defs,
        f'    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{cs["fill_opacity_start"]}"/>\n'
        f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -10)}" stop-opacity="{cs["fill_opacity_end"]}"/>\n'
        f'    </linearGradient>',
        f'    <clipPath id="{clip_id}">\n'
        f'      <rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="16" />\n'
        f'    </clipPath>'
    ]

    body_parts: list[str] = []
    body_parts.append(
        f'    <g clip-path="url(#{clip_id})">\n'
        f'      <rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" fill="url(#{grad_id})"/>\n'
        f'      <rect x="{card_x}" y="{card_y}" width="4" height="{card_h}" fill="{ca}" opacity="0.85"/>\n'
        f'    </g>'
    )
    body_parts.append(
        f'    <rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="16" fill="none" '
        f'stroke="{ca}" stroke-opacity="{cs["stroke_opacity"]}" stroke-width="{cs["stroke_width"]}"/>'
    )
    if cs["inner_border"]:
        body_parts.append(
            f'    <rect x="{card_x + 6}" y="{card_y + 6}" width="{card_w - 12}" height="{card_h - 12}" rx="12" fill="none" '
            f'stroke="{ca}" stroke-opacity="{cs["inner_stroke_opacity"]}" stroke-width="{cs["inner_stroke_width"]}"/>'
        )

    from .svg_pipeline import _wrap_to_tspans
    
    y = card_y + 36
    max_y = card_y + card_h - 24
    
    for item in plan.items:
        if y >= max_y:
            break
        text_w = card_w - 72
        text_x = card_x + 36
        tspans, lines = _wrap_to_tspans(item.primary, text_x, 20, text_w, line_height=1.3)
        item_h = lines * 26
        
        if y + item_h > max_y:
            break
            
        body_parts.append(
            f'    <text x="{text_x}" y="{y}" font-family="{font}" font-size="20" '
            f'fill="{p["text"]}">{tspans}</text>'
        )
        y += item_h + 12

    body_content = "\n".join(body_parts)
    defs_content = "\n".join(defs_parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n'
        f'{defs_content}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, plan.title, lock, w, h)}\n'
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
