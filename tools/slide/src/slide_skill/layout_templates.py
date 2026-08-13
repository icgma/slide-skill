"""Layout template registry — the design system for slide-skill v4.0.

Each LayoutTemplate defines:
  - A fixed visual structure (card positions, chrome, decorations)
  - Content slots with constraints (min/max items, text length)
  - Density range it supports (sparse / normal / dense)
  - Visual communication goal it serves (impact / information / narrative / comparison / engagement)

The AI selects templates based on content analysis; the renderer generates SVG.
This decouples design decisions (AI) from rendering fidelity (tool).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .content_planner import ContentItem, SlidePlan

Density = Literal["sparse", "normal", "dense"]
CommGoal = Literal["impact", "information", "narrative", "comparison", "engagement", "transition"]
SlideRole = Literal["opening", "transition", "content", "closing"]


# ---------------------------------------------------------------------------
# Slot definition — what the AI must fill
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SlotSpec:
    """Specification for a content slot in a layout template."""
    name: str              # e.g. "hero_title", "cards", "metric_values"
    type: str              # "title", "subtitle", "cards", "bullets", "metrics",
                           # "steps", "columns", "quote", "body_text"
    min_items: int = 0     # Minimum content items to fill this slot
    max_items: int = 12    # Maximum content items
    max_chars_per_item: int = 80  # Character limit per item (for font sizing)
    max_chars_per_item_secondary: int = 0  # Character limit for secondary text
    required: bool = True  # Whether this slot must be filled


# ---------------------------------------------------------------------------
# Layout template definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LayoutTemplate:
    """A named layout template with visual structure and content slots."""
    name: str                         # e.g. "hero-cover", "bold-statement"
    role: SlideRole                   # opening / transition / content / closing
    densities: tuple[Density, ...]    # Which densities this template supports
    goals: tuple[CommGoal, ...]       # Visual communication goals
    slots: tuple[SlotSpec, ...]       # Content slots the AI fills
    description: str                  # One-line description for AI selection
    ideal_items: int = 0              # Sweet spot for number of items
    visual_weight: str = "balanced"   # "light" / "balanced" / "heavy" — how much visual decoration


# ---------------------------------------------------------------------------
# Template Catalog — all available layouts
# ---------------------------------------------------------------------------

TEMPLATE_CATALOG: dict[str, LayoutTemplate] = {}

def _reg(t: LayoutTemplate) -> LayoutTemplate:
    TEMPLATE_CATALOG[t.name] = t
    return t


# === OPENING ===

_reg(LayoutTemplate(
    name="hero-cover",
    role="opening",
    densities=("sparse",),
    goals=("impact",),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=30),
        SlotSpec("subtitle", "subtitle", min_items=0, max_items=1, max_chars_per_item=60),
    ),
    description="Full-bleed hero with oversized title, ambient gradient orbs, geometric decor. Maximum visual impact for opening slide.",
    ideal_items=1,
    visual_weight="heavy",
))

_reg(LayoutTemplate(
    name="split-cover",
    role="opening",
    densities=("sparse",),
    goals=("impact",),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=25),
        SlotSpec("subtitle", "subtitle", min_items=0, max_items=1, max_chars_per_item=50),
        SlotSpec("accent_items", "cards", min_items=0, max_items=3, max_chars_per_item=20),
    ),
    description="Left title + right decorative cards/graphics. Good when you have 1-3 key points to preview.",
    ideal_items=3,
    visual_weight="heavy",
))


# === TRANSITION / SECTION DIVIDERS ===

_reg(LayoutTemplate(
    name="section-divider",
    role="transition",
    densities=("sparse",),
    goals=("transition",),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=30),
        SlotSpec("subtitle", "subtitle", min_items=0, max_items=1, max_chars_per_item=50),
    ),
    description="Centered glassmorphic card with concentric orbital rings. Bold section title with optional subtitle.",
    ideal_items=1,
    visual_weight="balanced",
))


# === CLOSING ===

_reg(LayoutTemplate(
    name="closing",
    role="closing",
    densities=("sparse",),
    goals=("impact",),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=25),
        SlotSpec("body_text", "body_text", min_items=0, max_items=1, max_chars_per_item=60),
    ),
    description="Thank-you / closing slide with centered title and contact info.",
    ideal_items=1,
    visual_weight="light",
))


# === CONTENT — SPARSE (1-3 items, large visual impact) ===

_reg(LayoutTemplate(
    name="bold-statement",
    role="content",
    densities=("sparse",),
    goals=("impact",),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=25),
        SlotSpec("hero_text", "body_text", min_items=1, max_items=1, max_chars_per_item=80),
        SlotSpec("caption", "subtitle", min_items=0, max_items=1, max_chars_per_item=40),
    ),
    description="One bold statement dominates the slide. Minimal decoration, maximum whitespace. For key takeaways and powerful quotes.",
    ideal_items=1,
    visual_weight="light",
))

_reg(LayoutTemplate(
    name="hero-metric",
    role="content",
    densities=("sparse",),
    goals=("impact",),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=25),
        SlotSpec("metric_value", "body_text", min_items=1, max_items=1, max_chars_per_item=10),
        SlotSpec("metric_label", "subtitle", min_items=1, max_items=1, max_chars_per_item=40),
    ),
    description="One giant number + label centered on slide. For headline stats (98% pass rate, #1 ranking). Maximum data impact.",
    ideal_items=1,
    visual_weight="balanced",
))

_reg(LayoutTemplate(
    name="key-concept",
    role="content",
    densities=("sparse",),
    goals=("information",),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=25),
        SlotSpec("concept_term", "body_text", min_items=1, max_items=1, max_chars_per_item=12),
        SlotSpec("explanations", "bullets", min_items=1, max_items=4, max_chars_per_item=60),
        SlotSpec("example", "subtitle", min_items=0, max_items=1, max_chars_per_item=80),
    ),
    description="Left panel with bold concept term + right panel with explanations. Asymmetric split. For defining key concepts.",
    ideal_items=3,
    visual_weight="balanced",
))


# === CONTENT — NORMAL (3-6 items, balanced) ===

_reg(LayoutTemplate(
    name="card-row",
    role="content",
    densities=("normal",),
    goals=("information",),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=25),
        SlotSpec("cards", "cards", min_items=2, max_items=4, max_chars_per_item=30),
    ),
    description="2-4 cards in a horizontal row. Each card has title + subtitle. For features, highlights, overview.",
    ideal_items=3,
    visual_weight="balanced",
))

_reg(LayoutTemplate(
    name="numbered-list",
    role="content",
    densities=("normal", "dense"),
    goals=("information",),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=25),
        SlotSpec("items", "bullets", min_items=2, max_items=7, max_chars_per_item=80),
    ),
    description="Title + numbered list items in frosted glass cards with dual-ring badges. For structured content, steps, objectives.",
    ideal_items=5,
    visual_weight="balanced",
))

_reg(LayoutTemplate(
    name="metrics-dashboard",
    role="content",
    densities=("normal",),
    goals=("impact", "information"),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=25),
        SlotSpec("metrics", "metrics", min_items=2, max_items=4, max_chars_per_item=15, max_chars_per_item_secondary=40),
    ),
    description="2-4 metric cards with big numbers + descriptive labels. For data showcases, KPIs, rankings.",
    ideal_items=4,
    visual_weight="balanced",
))

_reg(LayoutTemplate(
    name="two-column",
    role="content",
    densities=("normal",),
    goals=("comparison", "information"),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=25),
        SlotSpec("left_header", "subtitle", min_items=0, max_items=1, max_chars_per_item=15),
        SlotSpec("left_items", "bullets", min_items=1, max_items=5, max_chars_per_item=50),
        SlotSpec("right_header", "subtitle", min_items=0, max_items=1, max_chars_per_item=15),
        SlotSpec("right_items", "bullets", min_items=1, max_items=5, max_chars_per_item=50),
    ),
    description="Two-column comparison with headers, checkmarks/crosses. For before/after, pros/cons, us vs them.",
    ideal_items=4,
    visual_weight="balanced",
))

_reg(LayoutTemplate(
    name="left-stack",
    role="content",
    densities=("normal",),
    goals=("information",),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=25),
        SlotSpec("items", "cards", min_items=2, max_items=5, max_chars_per_item=60),
    ),
    description="Title on left (vertical) + stacked cards on right. Good for explaining components or layers.",
    ideal_items=4,
    visual_weight="balanced",
))

_reg(LayoutTemplate(
    name="quote-block",
    role="content",
    densities=("sparse",),
    goals=("impact",),
    slots=(
        SlotSpec("title", "title", min_items=0, max_items=1, max_chars_per_item=20),
        SlotSpec("quote", "quote", min_items=1, max_items=1, max_chars_per_item=120),
        SlotSpec("attribution", "subtitle", min_items=0, max_items=1, max_chars_per_item=30),
    ),
    description="Large decorative quote marks + centered quote text. For impactful quotes, testimonials, key statements.",
    ideal_items=1,
    visual_weight="light",
))


# === CONTENT — NARRATIVE / FLOW ===

_reg(LayoutTemplate(
    name="timeline",
    role="content",
    densities=("normal",),
    goals=("narrative",),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=25),
        SlotSpec("milestones", "cards", min_items=3, max_items=6, max_chars_per_item=20),
    ),
    description="Horizontal timeline with milestone dots and alternating cards above/below. For history, roadmap, process.",
    ideal_items=5,
    visual_weight="balanced",
))

_reg(LayoutTemplate(
    name="process-flow",
    role="content",
    densities=("normal",),
    goals=("narrative",),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=25),
        SlotSpec("steps", "steps", min_items=2, max_items=6, max_chars_per_item=40),
    ),
    description="Horizontal step cards connected by arrows. For workflows, procedures, how-it-works.",
    ideal_items=4,
    visual_weight="balanced",
))


# === CONTENT — ENGAGEMENT ===

_reg(LayoutTemplate(
    name="discussion",
    role="content",
    densities=("sparse",),
    goals=("engagement",),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=25),
        SlotSpec("question", "body_text", min_items=1, max_items=1, max_chars_per_item=80),
        SlotSpec("sub_questions", "bullets", min_items=0, max_items=3, max_chars_per_item=60),
    ),
    description="Large question mark icon + discussion prompt centered. Sub-questions below. For interactive moments.",
    ideal_items=2,
    visual_weight="balanced",
))


# === CONTENT — SPECIALIZED ===

_reg(LayoutTemplate(
    name="team-grid",
    role="content",
    densities=("normal",),
    goals=("information",),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=25),
        SlotSpec("members", "cards", min_items=2, max_items=4, max_chars_per_item=20),
    ),
    description="Avatar circles + name + role in card grid. For team showcase, faculty, speakers.",
    ideal_items=4,
    visual_weight="balanced",
))

_reg(LayoutTemplate(
    name="image-showcase",
    role="content",
    densities=("sparse",),
    goals=("impact",),
    slots=(
        SlotSpec("title", "title", min_items=1, max_items=1, max_chars_per_item=25),
        SlotSpec("image_url", "body_text", min_items=1, max_items=1, max_chars_per_item=200),
        SlotSpec("caption", "subtitle", min_items=0, max_items=1, max_chars_per_item=60),
    ),
    description="Large image with overlay title. For hero images, photo showcases, visual stories.",
    ideal_items=1,
    visual_weight="light",
))


# ---------------------------------------------------------------------------
# Template selection helpers
# ---------------------------------------------------------------------------

def select_templates_for_content(
    item_count: int,
    density: Density,
    goal: CommGoal | None = None,
    role: SlideRole = "content",
) -> list[LayoutTemplate]:
    """Return templates that fit the given constraints, ranked by suitability.

    The AI calls this to see which layouts work for a given slide's content,
    then picks the best one for the visual story it wants to tell.
    """
    candidates: list[tuple[float, LayoutTemplate]] = []

    for t in TEMPLATE_CATALOG.values():
        if t.role != role:
            continue
        if density not in t.densities:
            continue
        if goal and goal not in t.goals:
            continue

        # Score: how well does this template's item range match?
        # Find the most permissive slot
        max_slot_items = max((s.max_items for s in t.slots), default=0)
        min_slot_items = min((s.min_items for s in t.slots if s.required), default=0)

        if item_count < min_slot_items or item_count > max_slot_items:
            continue

        # Prefer templates whose ideal_items is closest to actual count
        if t.ideal_items > 0:
            distance = abs(t.ideal_items - item_count)
            score = 1.0 / (1.0 + distance)
        else:
            score = 0.5

        candidates.append((score, t))

    candidates.sort(key=lambda x: -x[0])
    return [t for _, t in candidates]


def get_template(name: str) -> LayoutTemplate | None:
    """Look up a template by name."""
    return TEMPLATE_CATALOG.get(name)


def list_templates(role: SlideRole | None = None) -> list[LayoutTemplate]:
    """List all templates, optionally filtered by role."""
    templates = list(TEMPLATE_CATALOG.values())
    if role:
        templates = [t for t in templates if t.role == role]
    return templates


def templates_to_markdown() -> str:
    """Render the full template catalog as markdown for AI reference."""
    lines = [
        "# Layout Template Catalog",
        "",
        "Each template defines a visual structure with content slots.",
        "Select templates based on content density and communication goal.",
        "",
    ]

    roles = ["opening", "transition", "content", "closing"]
    role_labels = {
        "opening": "Opening Slides",
        "transition": "Section Dividers",
        "content": "Content Slides",
        "closing": "Closing Slides",
    }

    for role in roles:
        templates = [t for t in TEMPLATE_CATALOG.values() if t.role == role]
        if not templates:
            continue

        lines.append(f"## {role_labels[role]}")
        lines.append("")

        for t in templates:
            densities = " / ".join(t.densities)
            goals = " / ".join(t.goals)
            lines.append(f"### `{t.name}`")
            lines.append(f"- **Densities**: {densities}")
            lines.append(f"- **Goals**: {goals}")
            lines.append(f"- **Ideal items**: {t.ideal_items}")
            lines.append(f"- **Visual weight**: {t.visual_weight}")
            lines.append(f"- **Description**: {t.description}")
            lines.append("")
            lines.append("**Slots:**")
            lines.append("")
            lines.append("| Slot | Type | Items | Max Chars | Required |")
            lines.append("|------|------|-------|-----------|----------|")
            for s in t.slots:
                items_range = f"{s.min_items}-{s.max_items}"
                chars = str(s.max_chars_per_item)
                if hasattr(s, 'max_chars_per_item_secondary') and s.max_chars_per_item_secondary:
                    chars += f" / {s.max_chars_per_item_secondary}"
                req = "yes" if s.required else "no"
                lines.append(f"| {s.name} | {s.type} | {items_range} | {chars} | {req} |")
            lines.append("")

    return "\n".join(lines)
