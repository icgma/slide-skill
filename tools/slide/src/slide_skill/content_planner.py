"""Content planning layer — replaces naive _markdown_to_slides().

This module takes raw Markdown and domain context, and produces a structured
list of SlidePlan objects. Each SlidePlan specifies exactly what one slide
should contain, at what density, and with which layout — enabling the SVG
renderer to focus solely on visual output, not content decisions.

Phase v3.0 — the intelligence layer that was missing from v1/v2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

DomainType = Literal["teaching", "course", "competition", "general"]
DensityLevel = Literal["sparse", "normal", "dense"]


@dataclass
class ContentItem:
    """A single content item within a slide."""
    type: str  # "text", "vocab", "sentence", "bullet", "metric", "quote", "step"
    primary: str  # Main text content
    secondary: str = ""  # Subtitle, translation, description
    tertiary: str = ""  # Pinyin, annotation, etc.
    meta: dict = field(default_factory=dict)  # Extra: {"number": "98%", "bold": True}


@dataclass
class SlidePlan:
    """Complete specification for one slide."""
    index: int
    layout: str  # "cover", "vocab-card", "bullet-list", "metric-highlight", etc.
    title: str
    items: list[ContentItem] = field(default_factory=list)
    notes: str = ""  # Speaker notes
    density: DensityLevel = "normal"
    meta: dict = field(default_factory=dict)  # Layout-specific overrides

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "layout": self.layout,
            "title": self.title,
            "items": [
                {"type": i.type, "primary": i.primary,
                 "secondary": i.secondary, "tertiary": i.tertiary,
                 "meta": i.meta}
                for i in self.items
            ],
            "notes": self.notes,
            "density": self.density,
            "meta": self.meta,
        }


# ---------------------------------------------------------------------------
# Language / content config
# ---------------------------------------------------------------------------

@dataclass
class ContentConfig:
    """Configuration for content planning."""
    domain: DomainType = "general"
    max_items_per_slide: int = 6
    audience: str = "general"

    # Language settings (primarily for teaching domain)
    primary_language: str = "zh"
    auxiliary_language: str = "en"
    show_pinyin: bool = False

    # Visual density
    default_density: DensityLevel = "normal"

    # Competition constraint (if applicable)
    competition_name: str | None = None
    time_limit_minutes: int | None = None
    max_slides: int = 20


# ---------------------------------------------------------------------------
# Structural content parsers
# ---------------------------------------------------------------------------

def _parse_heading_level(line: str) -> tuple[int, str]:
    """Return (heading_level, text) for a markdown heading line."""
    stripped = line.lstrip()
    level = 0
    for ch in stripped:
        if ch == "#":
            level += 1
        else:
            break
    return level, stripped[level:].strip()


def _detect_content_type(lines: list[str]) -> str:
    """Heuristic: what kind of content block is this?"""
    if not lines:
        return "empty"

    # Count patterns
    bullet_count = sum(1 for l in lines if l.strip().startswith(("- ", "* ", "• ")))
    numbered_count = sum(1 for l in lines if re.match(r"^\d+[\.\)、]\s", l.strip()))
    metric_count = sum(
        1 for l in lines
        if re.search(r"\d+\s*[%％]|\d+\s*[万亿KMB]|\d+x\b|\d+\+\b", l)
    )
    has_arrows = any("→" in l or "->" in l for l in lines)
    has_pinyin = any(re.search(r"[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]", l) for l in lines)
    has_dialogue = any(
        re.match(r"^[AB甲乙][:：]", l.strip()) for l in lines
    )

    # Vocab pattern: "word (pinyin) — translation" or similar
    vocab_pattern = re.compile(
        r"^[-•*]?\s*[\u4e00-\u9fff]+\s*[\(（].*[\)）]\s*[—\-–]\s*\S"
    )
    vocab_count = sum(1 for l in lines if vocab_pattern.match(l.strip()))

    # Decision logic
    if vocab_count >= 2:
        return "vocabulary"
    if has_dialogue:
        return "dialogue"
    if has_pinyin and bullet_count >= 2:
        return "vocabulary"
    if has_arrows or numbered_count >= 3:
        return "process"
    if metric_count >= 2:
        return "metrics"
    if bullet_count >= 2:
        return "bullets"
    if len(lines) == 1 and len(lines[0].strip()) > 40:
        return "paragraph"

    # Check for quote
    first = lines[0].strip()
    if first.startswith("> ") or first.startswith("\u201c") or first.startswith('"'):
        return "quote"

    return "paragraph"


def _parse_vocab_item(line: str) -> ContentItem | None:
    """Try to parse a vocab line into a ContentItem.

    Supported formats:
    - 医院 (yīyuàn) — hospital
    - 医院 (yīyuàn) - hospital
    - 医院（yīyuàn）—— hospital
    - - 医院 (yīyuàn) — hospital   (with bullet prefix)
    """
    # Strip bullet prefix
    text = line.strip()
    if text.startswith(("- ", "* ", "• ")):
        text = text[2:].strip()

    # Pattern: Chinese (pinyin) — English
    m = re.match(
        r"([\u4e00-\u9fff\u3400-\u4dbf]+)\s*"  # Chinese characters
        r"[\(（](.*?)[\)）]\s*"  # Pinyin in parens
        r"[—\-–]+\s*"  # Dash separator
        r"(.+)",  # English translation
        text,
    )
    if m:
        return ContentItem(
            type="vocab",
            primary=m.group(1).strip(),
            tertiary=m.group(2).strip(),  # pinyin
            secondary=m.group(3).strip(),  # translation
        )

    # Simpler pattern: Chinese — English (no pinyin)
    m2 = re.match(
        r"([\u4e00-\u9fff\u3400-\u4dbf]+)\s*"
        r"[—\-–]+\s*"
        r"(.+)",
        text,
    )
    if m2:
        return ContentItem(
            type="vocab",
            primary=m2.group(1).strip(),
            secondary=m2.group(2).strip(),
        )

    return None


def _parse_dialogue_lines(lines: list[str]) -> list[ContentItem]:
    """Parse dialogue lines (A: ... / B: ...) into ContentItems."""
    items: list[ContentItem] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        m = re.match(r"^([AB甲乙])\s*[:：]\s*(.+)", stripped)
        if m:
            speaker = m.group(1)
            utterance = m.group(2).strip()
            items.append(ContentItem(
                type="dialogue",
                primary=utterance,
                meta={"speaker": speaker},
            ))
        else:
            # Continuation or annotation line
            if items:
                items[-1].secondary = (
                    items[-1].secondary + "\n" + stripped
                ).strip()
    return items


# ---------------------------------------------------------------------------
# Section parser
# ---------------------------------------------------------------------------

@dataclass
class _Section:
    """Intermediate parsed section before slide planning."""
    heading: str
    level: int
    body_lines: list[str]
    content_type: str = ""
    subsections: list["_Section"] = field(default_factory=list)


def _parse_sections(markdown: str) -> list[_Section]:
    """Parse markdown into a tree of sections."""
    lines = markdown.splitlines()
    sections: list[_Section] = []
    current: _Section | None = None
    body_lines: list[str] = []

    for line in lines:
        if line.strip().startswith("#"):
            # Flush current
            if current is not None:
                current.body_lines = body_lines
                current.content_type = _detect_content_type(body_lines)
                sections.append(current)
            level, text = _parse_heading_level(line)
            current = _Section(heading=text, level=level, body_lines=[])
            body_lines = []
        else:
            body_lines.append(line)

    # Flush last section
    if current is not None:
        current.body_lines = body_lines
        current.content_type = _detect_content_type(body_lines)
        sections.append(current)
    elif body_lines and any(l.strip() for l in body_lines):
        # No headings at all — treat entire content as one section
        sections.append(_Section(
            heading="Overview",
            level=1,
            body_lines=body_lines,
            content_type=_detect_content_type(body_lines),
        ))

    return sections


# ---------------------------------------------------------------------------
# Core planning logic
# ---------------------------------------------------------------------------

def _split_items_to_slides(
    items: list[ContentItem],
    title: str,
    layout: str,
    max_per_slide: int,
    start_index: int,
    density: DensityLevel,
) -> list[SlidePlan]:
    """Split a list of items across multiple slides if needed."""
    if not items:
        return [SlidePlan(
            index=start_index,
            layout=layout,
            title=title,
            density=density,
        )]

    plans: list[SlidePlan] = []
    chunks = [items[i:i + max_per_slide] for i in range(0, len(items), max_per_slide)]

    for chunk_idx, chunk in enumerate(chunks):
        suffix = f" ({chunk_idx + 1}/{len(chunks)})" if len(chunks) > 1 else ""
        plans.append(SlidePlan(
            index=start_index + chunk_idx,
            layout=layout,
            title=f"{title}{suffix}",
            items=list(chunk),
            density=density,
        ))

    return plans


def _section_to_plans(
    section: _Section,
    config: ContentConfig,
    start_index: int,
) -> list[SlidePlan]:
    """Convert one parsed section into one or more SlidePlans."""
    body_lines = [l for l in section.body_lines if l.strip()]
    ctype = section.content_type
    max_items = config.max_items_per_slide

    # -- Vocabulary --
    if ctype == "vocabulary":
        items: list[ContentItem] = []
        for line in body_lines:
            vi = _parse_vocab_item(line)
            if vi:
                # Apply pinyin config
                if not config.show_pinyin:
                    vi.tertiary = ""
                items.append(vi)
            else:
                # Non-vocab line in a vocab section — treat as annotation
                if items:
                    items[-1].meta["annotation"] = line.strip()
        vocab_max = min(max_items, 4) if config.domain == "teaching" else max_items
        return _split_items_to_slides(
            items, section.heading, "vocab-card",
            vocab_max, start_index, "sparse",
        )

    # -- Dialogue --
    if ctype == "dialogue":
        items = _parse_dialogue_lines(body_lines)
        return _split_items_to_slides(
            items, section.heading, "dialogue",
            max_items, start_index, "normal",
        )

    # -- Metrics --
    if ctype == "metrics":
        items = []
        for line in body_lines:
            text = line.strip().lstrip("-*• ").strip()
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
            text = re.sub(r"\*(.+?)\*", r"\1", text)
            # Extract number + description
            m = re.match(r"([\$¥]?[\d,.]+\s*[%％万亿秒种天年KMBx+]*)\s*(.*)", text)
            if m:
                items.append(ContentItem(
                    type="metric",
                    primary=m.group(1).strip(),
                    secondary=m.group(2).strip(),
                ))
            else:
                items.append(ContentItem(type="text", primary=text))
        return _split_items_to_slides(
            items, section.heading, "metric-highlight",
            min(max_items, 4), start_index, "normal",
        )

    # -- Process/Steps --
    if ctype == "process":
        items = []
        for line in body_lines:
            text = line.strip()
            # Strip numbered prefix
            text = re.sub(r"^\d+[\.\)、]\s*", "", text)
            text = text.lstrip("-*• ").strip()
            if text:
                items.append(ContentItem(type="step", primary=text))
        return _split_items_to_slides(
            items, section.heading, "process-flow",
            max_items, start_index, "normal",
        )

    # -- Quote --
    if ctype == "quote":
        quote_text = "\n".join(
            l.strip().lstrip("> ").strip('""\u201c\u201d') for l in body_lines
        ).strip()
        return [SlidePlan(
            index=start_index,
            layout="quote-block",
            title=section.heading,
            items=[ContentItem(type="quote", primary=quote_text)],
            density="sparse",
        )]

    # -- Bullets --
    if ctype == "bullets":
        items = []
        for line in body_lines:
            text = line.strip()
            if text.startswith(("- ", "* ", "• ")):
                text = text[2:].strip()
            if text:
                items.append(ContentItem(type="bullet", primary=text))
        return _split_items_to_slides(
            items, section.heading, "bullet-list",
            max_items, start_index, "normal",
        )

    # -- Paragraph / default --
    text = "\n".join(body_lines).strip()
    if not text:
        return [SlidePlan(
            index=start_index,
            layout="section-divider",
            title=section.heading,
            density="sparse",
        )]

    # Comparison layout: heading contains "vs" or "versus"
    if re.search(r"\bvs\.?\b|\bversus\b", section.heading, re.IGNORECASE):
        return [SlidePlan(
            index=start_index,
            layout="comparison",
            title=section.heading,
            items=[ContentItem(type="text", primary=text)],
            density="normal",
        )]

    return [SlidePlan(
        index=start_index,
        layout="default",
        title=section.heading,
        items=[ContentItem(type="text", primary=text)],
        density="normal",
    )]


def plan_slides(
    markdown: str,
    config: ContentConfig | None = None,
) -> list[SlidePlan]:
    """Plan a slide deck from markdown source and domain configuration.

    This is the main entry point replacing the old _markdown_to_slides().
    It returns a structured list of SlidePlan objects that the renderer
    can consume without making any content decisions.

    Args:
        markdown: Source content in Markdown format.
        config: Domain and density configuration. Defaults to general settings.

    Returns:
        Ordered list of SlidePlan objects, one per slide.
    """
    if config is None:
        config = ContentConfig()

    sections = _parse_sections(markdown)
    if not sections:
        return [SlidePlan(
            index=1,
            layout="cover",
            title="Untitled Presentation",
            density="sparse",
        )]

    plans: list[SlidePlan] = []
    slide_idx = 1

    for sec_idx, section in enumerate(sections):
        # First section → cover slide
        if sec_idx == 0 and len(sections) > 1:
            body_text = "\n".join(
                l.strip() for l in section.body_lines if l.strip()
            )
            plans.append(SlidePlan(
                index=slide_idx,
                layout="cover",
                title=section.heading,
                items=[ContentItem(type="text", primary=body_text)] if body_text else [],
                density="sparse",
            ))
            slide_idx += 1
            continue

        # Last section → closing slide (only if > 2 sections)
        if sec_idx == len(sections) - 1 and len(sections) > 2:
            body_text = "\n".join(
                l.strip() for l in section.body_lines if l.strip()
            )
            plans.append(SlidePlan(
                index=slide_idx,
                layout="closing",
                title=section.heading,
                items=[ContentItem(type="text", primary=body_text)] if body_text else [],
                density="sparse",
            ))
            slide_idx += 1
            continue

        # Middle sections → content-driven planning
        section_plans = _section_to_plans(section, config, slide_idx)
        for plan in section_plans:
            plan.index = slide_idx
            plans.append(plan)
            slide_idx += 1

    # Enforce max_slides
    if len(plans) > config.max_slides:
        plans = plans[:config.max_slides]
        # Ensure last slide is closing
        plans[-1].layout = "closing"

    # Anti-monotony: break runs of 3+ identical layouts
    _break_layout_monotony(plans)

    return plans


def _break_layout_monotony(plans: list[SlidePlan]) -> None:
    """In-place pass: if 3+ consecutive slides share the same content layout,
    rotate the middle one to a different layout that preserves all content."""
    chrome = {"cover", "closing", "section-divider"}
    alt_map = {
        "bullet-list": "default",
        "default": "bullet-list",
        "metric-highlight": "default",
        "vocab-card": "default",
    }
    for i in range(1, len(plans) - 1):
        if plans[i].layout in chrome:
            continue
        if plans[i - 1].layout == plans[i].layout == plans[i + 1].layout:
            alt = alt_map.get(plans[i].layout)
            if alt:
                plans[i].layout = alt


# ---------------------------------------------------------------------------
# Convenience: dump plan as markdown summary (for agent preview)
# ---------------------------------------------------------------------------

def plan_to_markdown(plans: list[SlidePlan]) -> str:
    """Render a slide plan as a human-readable markdown summary.

    Useful for agents to show the plan to the user for approval before
    generating SVGs.
    """
    lines = [
        "# Slide Plan",
        "",
        f"Total slides: **{len(plans)}**",
        "",
        "| # | Layout | Title | Items | Density |",
        "|---|--------|-------|-------|---------|",
    ]
    for p in plans:
        item_summary = f"{len(p.items)} items" if p.items else "—"
        lines.append(
            f"| {p.index} | `{p.layout}` | {p.title} | {item_summary} | {p.density} |"
        )
    lines.append("")
    return "\n".join(lines)


def plan_to_json(plans: list[SlidePlan]) -> list[dict]:
    """Serialize a slide plan to JSON-compatible list of dicts."""
    return [p.to_dict() for p in plans]
