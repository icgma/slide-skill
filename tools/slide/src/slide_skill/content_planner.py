"""Content planning layer — replaces naive _markdown_to_slides().

This module takes raw Markdown and domain context, and produces a structured
list of SlidePlan objects. Each SlidePlan specifies exactly what one slide
should contain, at what density, and with which layout — enabling the SVG
renderer to focus solely on visual output, not content decisions.

Phase v3.0 — the intelligence layer that was missing from v1/v2.
Phase v4.0 — design-aware planning: visual strategy, chart auto-selection,
             image hints, layout patterns, Eight Confirmations gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from .semantic_scenes import (
    SCENE_MARKET_OPPORTUNITY,
    SCENE_METRIC_HIGHLIGHT,
    SCENE_PROBLEM,
    SCENE_ROADMAP,
    SCENE_SOLUTION,
    SCENE_TECHNOLOGY,
)

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


RhythmLevel = Literal["anchor", "breathing", "dense", ""]


@dataclass
class SlidePlan:
    """Complete specification for one slide."""
    index: int
    layout: str  # "cover", "vocab-card", "bullet-list", "metric-highlight", etc.
    title: str
    items: list[ContentItem] = field(default_factory=list)
    notes: str = ""  # Speaker notes
    density: DensityLevel = "normal"
    rhythm: RhythmLevel = ""  # v4.0: page-level visual intensity
    meta: dict = field(default_factory=dict)  # Layout-specific overrides
    # v4.0 design-intent fields
    visual_strategy: str = ""   # e.g., "hero-stat", "image-left-text-right"
    chart_type: str = ""        # e.g., "bar_vertical", "timeline_horizontal"
    image_hint: str = ""        # e.g., "technology, abstract, blue tones"
    layout_pattern: str = ""    # e.g., "split-50-50", "cards-3-up"

    def to_dict(self) -> dict:
        d = {
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
        if self.rhythm:
            d["rhythm"] = self.rhythm
        # v4.0 design-intent fields
        if self.visual_strategy:
            d["visual_strategy"] = self.visual_strategy
        if self.chart_type:
            d["chart_type"] = self.chart_type
        if self.image_hint:
            d["image_hint"] = self.image_hint
        if self.layout_pattern:
            d["layout_pattern"] = self.layout_pattern
        return d


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

    # Markdown table: header | separator | data rows
    table_sep = re.compile(r"^\|[\s\-:]+\|[\s\-:|]*\|$")
    pipe_lines = [l for l in lines if l.strip().startswith("|") and l.strip().endswith("|")]
    has_table_sep = any(table_sep.match(l.strip()) for l in lines)
    if has_table_sep and len(pipe_lines) >= 3:
        return "table"

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


def _parse_markdown_table(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    """Parse markdown pipe table into (headers, rows).

    Returns ([], []) if input is not a valid table.
    """
    sep_pat = re.compile(r"^\|[\s\-:]+\|[\s\-:|]*\|$")
    pipe_lines = [l.strip() for l in lines if l.strip().startswith("|") and l.strip().endswith("|")]
    if not pipe_lines:
        return [], []

    def _split_row(line: str) -> list[str]:
        cells = line.strip().strip("|").split("|")
        return [c.strip() for c in cells]

    headers: list[str] = []
    rows: list[list[str]] = []
    for line in pipe_lines:
        if sep_pat.match(line):
            continue
        cells = _split_row(line)
        if not headers:
            headers = cells
        else:
            rows.append(cells)
    return headers, rows


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

    if not body_lines:
        return [SlidePlan(
            index=start_index,
            layout="section-divider",
            title=section.heading,
            density="sparse",
        )]

    body_text = "\n".join(body_lines).strip()
    heading_upper = section.heading.upper()
    body_upper = body_text.upper()
    is_premium_domain = config.domain in ("teaching", "course", "competition")

    semantic_heading_map = [
        (SCENE_PROBLEM, ["PROBLEM", "PAIN", "CHALLENGE", "问题", "痛点", "挑战"], "problem-map"),
        (SCENE_SOLUTION, ["SOLUTION", "OUR SOLUTION", "解决方案", "方案", "产品能力"], "solution-map"),
        (SCENE_TECHNOLOGY, ["TECHNOLOGY STACK", "TECH STACK", "ARCHITECTURE", "技术栈", "技术架构"], "technology-map"),
        (SCENE_ROADMAP, ["ROADMAP", "MILESTONE", "路线图", "里程碑", "规划"], "roadmap-map"),
    ]
    for scene_layout, keywords, strategy in semantic_heading_map:
        if scene_layout == SCENE_ROADMAP and config.domain in ("competition", "course", "teaching"):
            continue
        if any(k in heading_upper for k in keywords):
            if scene_layout == SCENE_ROADMAP:
                items, _ = lines_to_items("timeline", body_text, config)
            else:
                items = [
                    ContentItem(type="bullet", primary=_strip_list_prefix(line.strip()))
                    for line in body_text.splitlines()
                    if _strip_list_prefix(line.strip())
                ]
            if items:
                return [SlidePlan(
                    index=start_index,
                    layout=scene_layout,
                    title=section.heading,
                    items=items,
                    density="normal",
                    rhythm="anchor",
                    visual_strategy=strategy,
                    layout_pattern="profile-driven-scene",
                )]

    # 1. Comparison Matrix routing
    is_comparison = (
        any(k in heading_upper for k in ["VS", "VERSUS", "对比", "比较", "对照", "DIFFERENCE", "COMPARISON", "PK"])
        or (len(body_lines) >= 2 and any("VS" in line.upper() for line in body_lines))
    )
    if is_comparison and ctype != "table":
        items, meta = lines_to_items("comparison-matrix", body_text, config)
        if items:
            return [SlidePlan(
                index=start_index,
                layout="comparison-matrix",
                title=section.heading,
                items=items,
                density="normal",
                meta=meta,
            )]

    # 2. Learning Objectives routing
    is_learning_obj = (
        any(k in heading_upper for k in ["目标", "OBJECTIVE", "GOAL", "AIM", "任务"])
        and (ctype in ("bullets", "process") or len(body_lines) >= 2)
    )
    if is_learning_obj:
        items, _ = lines_to_items("learning-objectives", body_text, config)
        if items:
            return _split_items_to_slides(
                items, section.heading, "learning-objectives",
                max_items, start_index, "normal",
            )

    # 3. Team Grid routing
    is_team_grid = (
        any(k in heading_upper for k in ["团队", "师资", "成员", "TEAM", "MEMBER", "FOUNDER", "STAFF", "FACULTY", "组织"])
        and len(body_lines) >= 1
    )
    if is_team_grid:
        items, _ = lines_to_items("team-grid", body_text, config)
        if items:
            return _split_items_to_slides(
                items, section.heading, "team-grid",
                min(max_items, 4), start_index, "normal",
            )

    # 4. Timeline routing
    is_timeline = (
        any(k in heading_upper for k in ["时间线", "历程", "发展", "历史", "TIMELINE", "HISTORY", "ROADMAP", "MILESTONES", "演进", "发展规划"])
        or (ctype == "process" and is_premium_domain)
    )
    if is_timeline:
        items, _ = lines_to_items("timeline", body_text, config)
        if items:
            return _split_items_to_slides(
                items, section.heading, "timeline",
                min(max_items, 6), start_index, "normal",
            )

    # 5. Metrics routing. Keep the competition dashboard for pitch/defense
    # decks; general decks use metric-highlight so KPI slides do not inherit
    # the dense competition card system.
    metric_signal_count = len(
        re.findall(
            r"[$¥€£]?\s*\d[\d,.]*\s*[%％]|\d[\d,.]*\s*[万亿KMB]\b|\d[\d,.]*x\b|[$¥€£]\s*\d|\d+\+\b",
            body_text,
            re.IGNORECASE,
        )
    )
    is_market_opportunity = (
        any(k in heading_upper for k in ["MARKET OPPORTUNITY", "MARKET SIZE", "TAM", "市场机会", "市场规模"])
        and ctype != "table"
        and metric_signal_count >= 2
    )
    if is_market_opportunity:
        items, _ = lines_to_items(SCENE_METRIC_HIGHLIGHT, body_text, config)
        if items:
            return [SlidePlan(
                index=start_index,
                layout=SCENE_MARKET_OPPORTUNITY,
                title=section.heading,
                items=items,
                density="normal",
                rhythm="anchor",
                visual_strategy="market-map",
                layout_pattern="hero-plus-breakdown",
            )]

    is_metrics = ctype != "table" and (ctype == "metrics" or metric_signal_count >= 2)
    if is_metrics:
        metric_layout = "metrics-dashboard" if config.domain == "competition" else SCENE_METRIC_HIGHLIGHT
        items, _ = lines_to_items(metric_layout, body_text, config)
        if items:
            return _split_items_to_slides(
                items, section.heading, metric_layout,
                min(max_items, 4), start_index, "normal",
            )

    # 6. Case Study routing
    is_case_study = (
        any(k in heading_upper for k in ["案例", "CASE STUDY", "CASE", "实践", "EMPIRICAL"])
        or any(k in body_upper for k in ["SITUATION:", "FINDINGS:", "CASE:", "案例一", "案例分析"])
        or ("---" in body_text and not any(re.match(r"^\|[\s\-:|]+\|$", l.strip()) for l in body_lines))
    ) and (is_premium_domain or any(k in heading_upper for k in ["案例", "CASE STUDY", "CASE"])) and ctype != "table"
    if is_case_study:
        items, _ = lines_to_items("case-study", body_text, config)
        if items:
            return [SlidePlan(
                index=start_index,
                layout="case-study",
                title=section.heading,
                items=items,
                density="normal",
            )]

    # 7. Key Concept routing
    is_key_concept = (
        any(k in heading_upper for k in ["概念", "定义", "什么是", "CONCEPT", "DEFINITION", "WHAT IS"])
        or (len(body_lines) >= 1 and any(k in body_lines[0] for k in ["是指", "定义为", " refers to ", " is defined as "]))
        or (is_premium_domain and any(k in heading_upper for k in [
            "定位", "体系", "架构", "结构", "核心", "分类", "维度", "机制", "原理", "特征", "属性", "平台", "基地",
            "PILLARS", "ARCHITECTURE", "FRAMEWORK", "STRUCTURE", "DIMENSIONS", "CLASSIFICATION", "CATEGORY", "CORE"
        ]))
    )
    if is_key_concept:
        items, _ = lines_to_items("key-concept", body_text, config)
        if items:
            return [SlidePlan(
                index=start_index,
                layout="key-concept",
                title=section.heading,
                items=items,
                density="normal",
            )]

    # 8. Discussion routing
    is_discussion = (
        any(k in heading_upper for k in ["讨论", "思考", "思考题", "DISCUSSION", "INTERACTIVE", "QUESTION", "思考与讨论", "思考与练习"])
        or (len(body_lines) >= 1 and body_lines[0].strip().endswith(("?", "？")))
    ) and ctype not in ("dialogue", "vocabulary", "table")
    if is_discussion:
        items, _ = lines_to_items("discussion", body_text, config)
        if items:
            return [SlidePlan(
                index=start_index,
                layout="discussion",
                title=section.heading,
                items=items,
                density="normal",
            )]

    # -- Classic Vocabulary fallback --
    if ctype == "vocabulary":
        items = []
        for line in body_lines:
            vi = _parse_vocab_item(line)
            if vi:
                if not config.show_pinyin:
                    vi.tertiary = ""
                items.append(vi)
            else:
                if items:
                    items[-1].meta["annotation"] = line.strip()
        vocab_max = min(max_items, 4) if config.domain == "teaching" else max_items
        return _split_items_to_slides(
            items, section.heading, "vocab-card",
            vocab_max, start_index, "sparse",
        )

    # -- Classic Dialogue fallback --
    if ctype == "dialogue":
        items = _parse_dialogue_lines(body_lines)
        return _split_items_to_slides(
            items, section.heading, "dialogue",
            max_items, start_index, "normal",
        )

    # -- Classic Table fallback --
    if ctype == "table":
        headers, rows = _parse_markdown_table(body_lines)
        items = []
        if headers:
            items.append(ContentItem(type="table-header", primary="|".join(headers)))
        for row in rows:
            items.append(ContentItem(type="table-row", primary="|".join(row)))
        return _split_items_to_slides(
            items, section.heading, "table",
            min(max_items, 9), start_index, "normal",
        )

    # -- Classic Process fallback --
    if ctype == "process":
        items = []
        for line in body_lines:
            text = line.strip()
            text = re.sub(r"^\d+[\.\)、]\s*", "", text)
            text = re.sub(r"^\s*[-*•]\s+", "", text).strip()
            if text:
                items.append(ContentItem(type="step", primary=text))
        return _split_items_to_slides(
            items, section.heading, "process-flow",
            max_items, start_index, "normal",
        )

    # -- Classic Quote fallback --
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

    # -- Classic Bullets fallback --
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


# ---------------------------------------------------------------------------
# Layout-specific line parser (shared with svg_pipeline._build_plan_for_layout)
# ---------------------------------------------------------------------------

def _strip_list_prefix(line: str) -> str:
    line = re.sub(r"^\d+[\.\)、]\s*", "", line)
    line = re.sub(r"^\s*[-*•]\s+", "", line)
    return line.strip()


def _split_primary_secondary(line: str) -> tuple[str, str]:
    parts = re.split(r"\s*(?:—|–|(?<!-)-(?!>)|：|:)\s*", line, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return line, ""


_LAYOUT_LINE_PARSERS = {
    "vocab-card", "dialogue", "sentence-example", "exercise",
    "learning-objectives", "key-concept", "case-study", "discussion",
    "team-grid", "bullet-list", SCENE_METRIC_HIGHLIGHT, "metrics-dashboard", "timeline", "comparison-matrix",
}


def lines_to_items(
    layout: str,
    body: str,
    config: ContentConfig | None = None,
) -> tuple[list[ContentItem], dict]:
    """Parse a body of raw text lines into ContentItems for a given v3 layout.

    Returns a tuple ``(items, meta)`` where ``meta`` is a dict carrying any
    layout-level metadata (currently only comparison-matrix headers); it is
    ``{}`` for every other layout.
    """
    items, meta = _lines_to_items_impl(layout, body, config)
    for item in items:
        if item.primary:
            item.primary = re.sub(r"\*\*(.+?)\*\*", r"\1", item.primary)
            item.primary = re.sub(r"\*(.+?)\*", r"\1", item.primary)
        if item.secondary:
            item.secondary = re.sub(r"\*\*(.+?)\*\*", r"\1", item.secondary)
            item.secondary = re.sub(r"\*(.+?)\*", r"\1", item.secondary)
        if item.tertiary:
            item.tertiary = re.sub(r"\*\*(.+?)\*\*", r"\1", item.tertiary)
            item.tertiary = re.sub(r"\*(.+?)\*", r"\1", item.tertiary)
    return items, meta


def _lines_to_items_impl(
    layout: str,
    body: str,
    config: ContentConfig | None = None,
) -> tuple[list[ContentItem], dict]:
    if layout not in _LAYOUT_LINE_PARSERS:
        return [], {}

    if layout == "bullet-list":
        items = []
        for line in body.splitlines():
            line = _strip_list_prefix(line.strip())
            if line:
                primary, secondary = _split_primary_secondary(line)
                items.append(ContentItem(type="bullet", primary=primary, secondary=secondary))
        return items, {}

    # 1. vocab-card
    if layout == "vocab-card":
        items: list[ContentItem] = []
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            vi = _parse_vocab_item(line)
            if vi:
                if config is not None and not config.show_pinyin:
                    vi.tertiary = ""
                items.append(vi)
            else:
                items.append(ContentItem(type="vocab", primary=line, secondary="", tertiary=""))
        return items, {}

    # 2. dialogue
    if layout == "dialogue":
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        items = _parse_dialogue_lines(lines)
        return items, {}

    # 3. sentence-example
    if layout == "sentence-example":
        items = []
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            line = _strip_list_prefix(line)
            if not line:
                continue
            primary, secondary = _split_primary_secondary(line)
            items.append(ContentItem(type="sentence", primary=primary, secondary=secondary))
        return items, {}

    # 4. exercise
    if layout == "exercise":
        items = []
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            line = _strip_list_prefix(line)
            if line:
                items.append(ContentItem(type="text", primary=line))
        return items, {}

    # 5. learning-objectives
    if layout == "learning-objectives":
        items = []
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            line = _strip_list_prefix(line)
            if line:
                items.append(ContentItem(type="objective", primary=line))
        return items, {}

    # 6. key-concept
    if layout == "key-concept":
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        items = []
        if lines:
            first_line = _strip_list_prefix(lines[0])
            primary, secondary = _split_primary_secondary(first_line)
            items.append(ContentItem(type="concept", primary=primary, secondary=secondary))

            for line in lines[1:]:
                line = _strip_list_prefix(line)
                if line:
                    items.append(ContentItem(type="explanation", primary=line))
        else:
            items.append(ContentItem(type="concept", primary="", secondary=""))
        return items, {}

    # 7. case-study
    if layout == "case-study":
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        split_idx = -1
        for idx, line in enumerate(lines):
            if re.match(r"^-{3,}\s*$", line) or any(
                keyword in line.upper()
                for keyword in ["# ANALYSIS", "# FINDINGS", "ANALYSIS:", "FINDINGS:"]
            ):
                split_idx = idx
                break
        if split_idx != -1:
            left_lines = lines[:split_idx]
            right_lines = lines[split_idx + 1:]
        else:
            mid = len(lines) // 2
            left_lines = lines[:mid]
            right_lines = lines[mid:]

        left_items: list[ContentItem] = []
        right_items: list[ContentItem] = []

        def parse_to_items(line_list, target_list):
            for line in line_list:
                line = _strip_list_prefix(line)
                if not line or re.match(r"^-{3,}\s*$", line):
                    continue
                # Skip standalone keywords
                if line.upper() in ("CASE:", "SITUATION:", "BACKGROUND:", "ANALYSIS:", "FINDINGS:", "# CASE", "# SITUATION", "# BACKGROUND", "# ANALYSIS", "# FINDINGS"):
                    continue
                primary, secondary = _split_primary_secondary(line)
                target_list.append(ContentItem(type="case", primary=primary, secondary=secondary))

        parse_to_items(left_lines, left_items)
        parse_to_items(right_lines, right_items)
        return left_items + right_items, {}

    # 8. discussion
    if layout == "discussion":
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        items = []
        if lines:
            first_line = _strip_list_prefix(lines[0])
            items.append(ContentItem(type="discussion", primary=first_line))
            for line in lines[1:]:
                line = _strip_list_prefix(line)
                if line:
                    items.append(ContentItem(type="sub-question", primary=line))
        else:
            items.append(ContentItem(type="discussion", primary=""))
        return items, {}

    # 9. team-grid
    if layout == "team-grid":
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        items = []
        for line in lines:
            line = _strip_list_prefix(line)
            if not line:
                continue
            primary, secondary = _split_primary_secondary(line)
            items.append(ContentItem(type="member", primary=primary, secondary=secondary))
        return items, {}

    # 10. metric-highlight / metrics-dashboard
    if layout in (SCENE_METRIC_HIGHLIGHT, "metrics-dashboard"):
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        items = []
        for line in lines:
            line = _strip_list_prefix(line)
            line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            line = re.sub(r"\*(.+?)\*", r"\1", line)
            if not line:
                continue
            primary, secondary = _split_primary_secondary(line)
            if secondary:
                items.append(ContentItem(type="metric", primary=primary, secondary=secondary))
            else:
                m = re.match(r"([\$¥]?[\d,.]+\s*[%％万亿秒种天年KMBx+]*)\s*(.*)", line)
                if m:
                    items.append(ContentItem(type="metric", primary=m.group(1).strip(), secondary=m.group(2).strip()))
                else:
                    items.append(ContentItem(type="text", primary=line))
        return items, {}

    # 11. timeline
    if layout == "timeline":
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        items = []
        for line in lines:
            line = _strip_list_prefix(line)
            if not line:
                continue
            if "->" in line or "→" in line:
                subparts = re.split(r"\s*(?:->|→)\s*", line)
                for subpart in subparts:
                    subpart = _strip_list_prefix(subpart.strip())
                    if subpart:
                        items.append(ContentItem(type="milestone", primary=subpart, secondary=""))
            else:
                primary, secondary = _split_primary_secondary(line)
                items.append(ContentItem(type="milestone", primary=primary, secondary=secondary))
        return items, {}

    # 12. comparison-matrix
    if layout == "comparison-matrix":
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        split_idx = -1
        left_header = "OURS"
        right_header = "THEIRS"
        for idx, line in enumerate(lines):
            if re.match(r"^-{3,}\s*$", line):
                split_idx = idx
                break
            m = re.match(r"^#+\s*(.+?)\s+vs\.?\s+(.+)", line, re.IGNORECASE)
            if m:
                left_header = m.group(1).strip()
                right_header = m.group(2).strip()
                split_idx = idx
                break
        if split_idx != -1:
            left_lines = lines[:split_idx]
            right_lines = lines[split_idx + 1:]
        else:
            mid = len(lines) // 2
            left_lines = lines[:mid]
            right_lines = lines[mid:]

        left_items = []
        right_items = []

        def parse_comp_lines(line_list, target_list):
            for line in line_list:
                line = _strip_list_prefix(line)
                if not line or re.match(r"^-{3,}\s*$", line):
                    continue
                # Header rows of the form "X vs Y" are already consumed above
                # (the "#+ X vs Y" regex sets split_idx). Anything reaching here
                # is content — never filter on the substring "vs".
                target_list.append(ContentItem(type="comparison", primary=line))

        parse_comp_lines(left_lines, left_items)
        parse_comp_lines(right_lines, right_items)

        items = left_items + right_items
        return items, {"left_header": left_header, "right_header": right_header}

    return [], {}


def _load_confirmations(project_path):
    """Load confirmations.json if it exists and is fully confirmed."""
    from .confirmations import load_confirmations
    conf = load_confirmations(project_path)
    if conf and conf.get("all_confirmed"):
        return conf
    return None


def plan_slides(
    markdown: str,
    config: ContentConfig | None = None,
    project_path: str | None = None,
) -> list[SlidePlan]:
    """Plan a slide deck from markdown source and domain configuration.

    This is the main entry point replacing the old _markdown_to_slides().
    It returns a structured list of SlidePlan objects that the renderer
    can consume without making any content decisions.

    Args:
        markdown: Source content in Markdown format.
        config: Domain and density configuration. Defaults to general settings.
        project_path: Optional project path to load confirmations from.

    Returns:
        Ordered list of SlidePlan objects, one per slide.
    """
    if config is None:
        config = ContentConfig()

    # v4.1: consume confirmations if project_path provided
    if project_path:
        conf = _load_confirmations(project_path)
        if conf:
            values = conf.get("confirmations", {})
            audience_val = values.get("audience", {}).get("value", "")
            if audience_val:
                config = ContentConfig(
                    domain=config.domain,
                    max_items_per_slide=config.max_items_per_slide,
                    audience=audience_val,
                    primary_language=config.primary_language,
                    auxiliary_language=config.auxiliary_language,
                    show_pinyin=config.show_pinyin,
                    default_density=config.default_density,
                    competition_name=config.competition_name,
                    time_limit_minutes=config.time_limit_minutes,
                    max_slides=config.max_slides,
                )

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

    # Clean up raw markdown bold/italic tags systematically from all plan titles and item texts
    for plan in plans:
        if plan.title:
            plan.title = re.sub(r"\*\*(.+?)\*\*", r"\1", plan.title)
            plan.title = re.sub(r"\*(.+?)\*", r"\1", plan.title)
        for item in plan.items:
            if item.primary:
                item.primary = re.sub(r"\*\*(.+?)\*\*", r"\1", item.primary)
                item.primary = re.sub(r"\*(.+?)\*", r"\1", item.primary)
            if item.secondary:
                item.secondary = re.sub(r"\*\*(.+?)\*\*", r"\1", item.secondary)
                item.secondary = re.sub(r"\*(.+?)\*", r"\1", item.secondary)
            if item.tertiary:
                item.tertiary = re.sub(r"\*\*(.+?)\*\*", r"\1", item.tertiary)
                item.tertiary = re.sub(r"\*(.+?)\*", r"\1", item.tertiary)

    # Anti-monotony: break runs of 3+ identical layouts
    _break_layout_monotony(plans)

    # Drop empty section-dividers that sit between content slides.
    # A `section-divider` plan with no items is emitted whenever an H2
    # heading wraps only H3 sub-headings (e.g. "## 方案对比" followed by
    # "### 传统流程" / "### slide-skill 流程"). In short decks that yields
    # a near-empty "CHAPTER N" slide the user has to delete by hand —
    # exactly the "千篇一律且不能直接使用" complaint. Instead, fold the
    # heading into the following content slide's `meta["section"]` eyebrow
    # and drop the divider. Cover, closing and the last slide are always
    # preserved.
    plans = _merge_empty_section_dividers(plans)

    # v4.0: assign page-level rhythm
    assign_page_rhythm(plans)

    # v4.0: enrich plans with design-intent fields
    _enrich_design_intent(plans)

    return plans


def _merge_empty_section_dividers(plans: list[SlidePlan]) -> list[SlidePlan]:
    """Fold empty section-divider slides into the next content slide.

    Only dividers that have no items AND are followed by a non-chrome
    content slide are merged; the divider's title is preserved as the
    next slide's `meta["section"]` eyebrow so the user still sees the
    structural cue. Trailing dividers (no following content) are kept
    verbatim because there is nothing to fold into.
    """
    if not plans:
        return plans
    chrome_layouts = {"cover", "closing", "section-divider"}
    merged: list[SlidePlan] = []
    for i, plan in enumerate(plans):
        if (
            plan.layout == "section-divider"
            and not plan.items
            and i + 1 < len(plans)
            and plans[i + 1].layout not in chrome_layouts
        ):
            nxt = plans[i + 1]
            # Stash the divider heading as an eyebrow breadcrumb.
            meta = dict(nxt.meta) if nxt.meta else {}
            meta.setdefault("section", plan.title)
            nxt.meta = meta
            # Skip emitting the divider itself.
            continue
        merged.append(plan)
    # Re-index after the drop so renderers and page numbers stay aligned.
    for new_idx, plan in enumerate(merged, start=1):
        plan.index = new_idx
    return merged


def _break_layout_monotony(plans: list[SlidePlan]) -> None:
    """In-place pass: if 3+ consecutive slides share the same content layout,
    rotate the middle one to a different layout that preserves all content."""
    chrome = {"cover", "closing", "section-divider"}
    alt_map = {
        "bullet-list": "default",
        "default": "bullet-list",
        "metric-highlight": "default",
        "metrics-dashboard": "default",
        "vocab-card": "default",
        "learning-objectives": "default",
        "team-grid": "default",
        "timeline": "default",
        "comparison-matrix": "default",
        "key-concept": "default",
        "case-study": "default",
        "discussion": "default",
    }
    for i in range(1, len(plans) - 1):
        if plans[i].layout in chrome:
            continue
        if plans[i - 1].layout == plans[i].layout == plans[i + 1].layout:
            alt = alt_map.get(plans[i].layout)
            if alt:
                plans[i].layout = alt


def assign_page_rhythm(plans: list[SlidePlan]) -> None:
    """Assign page-level visual rhythm to each slide in-place.

    v4.0 enhanced: uses keyword analysis in addition to item-count heuristics.

    Rhythm values:
    - ``anchor``: high visual weight (hero, key takeaway, metric dashboard)
    - ``breathing``: light density, generous whitespace, visual rest
    - ``dense``: information-rich (multi-item lists, tables, detailed content)

    Heuristics:
    1. Cover/closing → anchor
    2. Section dividers → breathing
    3. v4.0 keyword-based: results/findings/conclusion/takeaway → anchor
    4. v4.0 keyword-based: overview/agenda/outline/introduction → breathing
    5. Content with ≤2 items → breathing
    6. Content with ≥6 items → dense
    7. Table/comparison layouts → dense
    8. Everything else → anchor (default)
    9. Monotony prevention: if 3+ consecutive have same rhythm, force variation.
    """
    ANCHOR_LAYOUTS = {"cover", "closing", "quote-block", "hero-cover", "split-cover"}
    BREATHING_LAYOUTS = {"section-divider"}
    DENSE_LAYOUTS = {"table", "comparison", "comparison-matrix", "team-grid",
                     "metrics-dashboard"}
    # v4.0 keyword-based rhythm hints
    _ANCHOR_KW = re.compile(
        r"(?:结[论果]|发现|要[点点]|takeaway|finding|result|conclusion|highlight|核心|关键)",
        re.IGNORECASE,
    )
    _BREATHING_KW = re.compile(
        r"(?:概[述览]|目录|大纲|议程|引言|overview|agenda|outline|introduction|背景|context)",
        re.IGNORECASE,
    )

    for plan in plans:
        if plan.layout in ANCHOR_LAYOUTS:
            plan.rhythm = "anchor"
        elif plan.layout in BREATHING_LAYOUTS:
            plan.rhythm = "breathing"
        elif plan.layout in DENSE_LAYOUTS:
            plan.rhythm = "dense"
        elif _ANCHOR_KW.search(plan.title):
            plan.rhythm = "anchor"
        elif _BREATHING_KW.search(plan.title):
            plan.rhythm = "breathing"
        elif len(plan.items) <= 2:
            plan.rhythm = "breathing"
        elif len(plan.items) >= 6:
            plan.rhythm = "dense"
        else:
            plan.rhythm = "anchor"

    # Monotony prevention: break runs of 3+ same rhythm
    _ROTATION = {"anchor": "breathing", "breathing": "dense", "dense": "anchor"}
    for i in range(1, len(plans) - 1):
        if (
            plans[i - 1].rhythm == plans[i].rhythm == plans[i + 1].rhythm
            and plans[i].layout not in ANCHOR_LAYOUTS | BREATHING_LAYOUTS
        ):
            plans[i].rhythm = _ROTATION.get(plans[i].rhythm, "anchor")


# ---------------------------------------------------------------------------
# v4.0 Design-intent enrichment
# ---------------------------------------------------------------------------

# Chart auto-selection mapping
_CHART_TYPE_MAP = {
    "metric-highlight": "kpi_cards",
    "metrics-dashboard": "kpi_cards",
    "process-flow": "timeline_horizontal",
    "timeline": "timeline_horizontal",
    "comparison": "comparison_table",
    "comparison-matrix": "comparison_table",
    "table": "data_table",
}

# Layout pattern mapping: (layout, item_count_range) → pattern
_LAYOUT_PATTERNS: list[tuple[str, tuple[int, int], str]] = [
    ("bullet-list", (1, 3), "cards-3-up"),
    ("bullet-list", (4, 5), "stacked-rows"),
    ("bullet-list", (6, 99), "compact-grid"),
    ("metric-highlight", (1, 2), "split-50-50"),
    ("metric-highlight", (3, 4), "cards-3-up"),
    ("two-column", (1, 99), "split-50-50"),
    ("comparison", (1, 99), "split-50-50"),
    ("comparison-matrix", (1, 99), "matrix-grid"),
    ("team-grid", (1, 99), "avatar-grid"),
    ("quote-block", (1, 99), "centered-hero"),
    ("cover", (0, 99), "full-bleed-hero"),
    ("closing", (0, 99), "centered-hero"),
    ("section-divider", (0, 99), "centered-hero"),
]

# Visual strategy mapping
_VISUAL_STRATEGY_MAP = {
    "cover": "hero-statement",
    "closing": "hero-statement",
    "section-divider": "section-break",
    "metric-highlight": "hero-stat",
    "metrics-dashboard": "hero-stat",
    "quote-block": "centered-quote",
    "two-column": "side-by-side",
    "comparison": "side-by-side",
    "bullet-list": "progressive-reveal",
    "process-flow": "flow-sequence",
    "timeline": "flow-sequence",
    "table": "data-dense",
    "comparison-matrix": "data-dense",
}

# Image subject keywords
_IMAGE_KEYWORDS: dict[str, str] = {
    "技术": "technology, circuits, abstract digital",
    "technology": "technology, circuits, abstract digital",
    "数据": "data visualization, charts, analytics",
    "data": "data visualization, charts, analytics",
    "教育": "education, classroom, learning",
    "education": "education, classroom, learning",
    "健康": "healthcare, medical, wellness",
    "health": "healthcare, medical, wellness",
    "金融": "finance, growth, investment",
    "finance": "finance, growth, investment",
    "环境": "nature, sustainability, green",
    "environment": "nature, sustainability, green",
    "团队": "teamwork, collaboration, people",
    "team": "teamwork, collaboration, people",
    "创新": "innovation, lightbulb, creative",
    "innovation": "innovation, lightbulb, creative",
    "市场": "market, business, strategy",
    "market": "market, business, strategy",
    "产品": "product, design, prototype",
    "product": "product, design, prototype",
    "研究": "research, laboratory, science",
    "research": "research, laboratory, science",
}


def _suggest_chart_type(plan: SlidePlan) -> str:
    """Auto-select chart type based on layout and content."""
    # Direct layout mapping
    ct = _CHART_TYPE_MAP.get(plan.layout, "")
    if ct:
        # Refine for metric-highlight based on item count
        if plan.layout in ("metric-highlight", "metrics-dashboard"):
            if len(plan.items) >= 5:
                return "bar_vertical"
        return ct

    # Check if items contain percentage data summing near 100%
    if plan.items:
        pct_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*%")
        percentages = []
        for item in plan.items:
            m = pct_pattern.search(item.primary)
            if m:
                percentages.append(float(m.group(1)))
        if len(percentages) >= 2 and 90 <= sum(percentages) <= 110:
            return "donut_chart"

    return ""


def _suggest_image(plan: SlidePlan) -> str:
    """Infer image subject hints from slide title and content keywords."""
    # Only suggest for anchor/breathing slides with ≤3 items
    if plan.rhythm == "dense" or len(plan.items) > 3:
        return ""
    # Skip chrome slides
    if plan.layout in ("cover", "closing", "section-divider"):
        return ""

    title_lower = plan.title.lower()
    for keyword, hint in _IMAGE_KEYWORDS.items():
        if keyword.lower() in title_lower:
            return hint

    # Check item content for keywords
    all_text = " ".join(i.primary for i in plan.items).lower()
    for keyword, hint in _IMAGE_KEYWORDS.items():
        if keyword.lower() in all_text:
            return hint

    return ""


def _suggest_layout_pattern(plan: SlidePlan) -> str:
    """Map layout + item count to a recommended layout pattern."""
    n = len(plan.items)
    for layout, (lo, hi), pattern in _LAYOUT_PATTERNS:
        if plan.layout == layout and lo <= n <= hi:
            return pattern
    return ""


def _suggest_visual_strategy(plan: SlidePlan) -> str:
    """Map layout to a high-level visual strategy name."""
    return _VISUAL_STRATEGY_MAP.get(plan.layout, "standard-content")


def _enrich_design_intent(plans: list[SlidePlan]) -> None:
    """Populate v4.0 design-intent fields on each plan in-place."""
    for plan in plans:
        if not plan.visual_strategy:
            plan.visual_strategy = _suggest_visual_strategy(plan)
        if not plan.chart_type:
            plan.chart_type = _suggest_chart_type(plan)
        if not plan.image_hint:
            plan.image_hint = _suggest_image(plan)
        if not plan.layout_pattern:
            plan.layout_pattern = _suggest_layout_pattern(plan)


# ---------------------------------------------------------------------------
# v4.0 Eight Confirmations design gate
# ---------------------------------------------------------------------------

def generate_design_confirmations(
    plans: list[SlidePlan],
    theme_name: str = "dark-tech",
    canvas_format: str = "16:9 (1280×720)",
) -> dict:
    """Generate the Eight Confirmations summary from a slide plan.

    This is an advisory pre-flight checklist — it does NOT block SVG
    generation, but gives the agent/user a structured summary to review.

    Returns a dict with 8 confirmation keys.
    """
    # Count rhythm distribution
    rhythm_counts: dict[str, int] = {"anchor": 0, "breathing": 0, "dense": 0}
    for p in plans:
        r = p.rhythm or "anchor"
        if r in rhythm_counts:
            rhythm_counts[r] += 1

    # Collect unique layouts
    layouts_used = sorted({p.layout for p in plans})

    # Build outline
    outline = []
    for p in plans:
        entry = f"{p.index}. [{p.layout}] {p.title}"
        if p.chart_type:
            entry += f" 📊{p.chart_type}"
        if p.image_hint:
            entry += f" 🖼️"
        outline.append(entry)

    return {
        "format": canvas_format,
        "page_count": len(plans),
        "style": theme_name,
        "color_scheme": f"Theme '{theme_name}' palette (see spec_lock.json)",
        "typography": f"Theme '{theme_name}' typography (see spec_lock.json)",
        "image_style": f"{sum(1 for p in plans if p.image_hint)}/{len(plans)} slides with image hints",
        "rhythm_pattern": (
            f"anchor={rhythm_counts['anchor']}, "
            f"breathing={rhythm_counts['breathing']}, "
            f"dense={rhythm_counts['dense']}"
        ),
        "outline": outline,
    }


def confirmations_to_markdown(confirmations: dict) -> str:
    """Render Eight Confirmations as a markdown summary block."""
    lines = [
        "## 📋 Eight Confirmations (Design Pre-flight)",
        "",
        "| # | Item | Value |",
        "|---|------|-------|",
        f"| 1 | Format | {confirmations.get('format', '—')} |",
        f"| 2 | Page Count | {confirmations.get('page_count', '—')} |",
        f"| 3 | Style | {confirmations.get('style', '—')} |",
        f"| 4 | Color Scheme | {confirmations.get('color_scheme', '—')} |",
        f"| 5 | Typography | {confirmations.get('typography', '—')} |",
        f"| 6 | Image Style | {confirmations.get('image_style', '—')} |",
        f"| 7 | Rhythm | {confirmations.get('rhythm_pattern', '—')} |",
        f"| 8 | Outline | {confirmations.get('page_count', '—')} slides |",
        "",
    ]
    outline = confirmations.get("outline", [])
    if outline:
        lines.append("### Slide Outline")
        lines.append("")
        for entry in outline:
            lines.append(f"- {entry}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience: dump plan as markdown summary (for agent preview)
# ---------------------------------------------------------------------------

def plan_to_markdown(plans: list[SlidePlan]) -> str:
    """Render a slide plan as a human-readable markdown summary.

    v4.0: includes visual strategy, chart type, and layout pattern columns.
    """
    lines = [
        "# Slide Plan",
        "",
        f"Total slides: **{len(plans)}**",
        "",
        "| # | Layout | Title | Items | Rhythm | Strategy | Chart | Pattern |",
        "|---|--------|-------|-------|--------|----------|-------|--------|",
    ]
    for p in plans:
        item_summary = f"{len(p.items)} items" if p.items else "—"
        rhythm_str = p.rhythm or "—"
        strategy = p.visual_strategy or "—"
        chart = p.chart_type or "—"
        pattern = p.layout_pattern or "—"
        lines.append(
            f"| {p.index} | `{p.layout}` | {p.title} | {item_summary} "
            f"| {rhythm_str} | {strategy} | {chart} | {pattern} |"
        )
    lines.append("")
    return "\n".join(lines)


def plan_to_json(plans: list[SlidePlan]) -> list[dict]:
    """Serialize a slide plan to JSON-compatible list of dicts.

    v4.0: includes visual_strategy, chart_type, image_hint, layout_pattern.
    """
    return [p.to_dict() for p in plans]
