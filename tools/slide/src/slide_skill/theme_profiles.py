"""Theme-level design system profiles.

These profiles describe structural behavior, not just colors and fonts.
Renderers should ask a profile for layout/chrome/card rules instead of
branching directly on theme names.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SceneLayoutProfile:
    """Structural rules for one semantic scene."""

    variant: str
    hero_position: str
    segment_position: str
    card_shape: str
    chrome: str


@dataclass(frozen=True)
class ThemeProfile:
    """A design-system profile for one theme family."""

    name: str
    visual_language: str
    card_radius: int
    stroke_width: float
    shadow_style: str
    market: SceneLayoutProfile
    problem: SceneLayoutProfile
    solution: SceneLayoutProfile
    roadmap: SceneLayoutProfile
    technology: SceneLayoutProfile
    closing: SceneLayoutProfile


DEFAULT_PROFILE = ThemeProfile(
    name="default",
    visual_language="technical-panel",
    card_radius=24,
    stroke_width=1.5,
    shadow_style="soft",
    market=SceneLayoutProfile(
        variant="split-hero-bars",
        hero_position="left",
        segment_position="right",
        card_shape="rounded-panel",
        chrome="left-stripe",
    ),
    problem=SceneLayoutProfile(
        variant="risk-ledger",
        hero_position="left",
        segment_position="right",
        card_shape="rounded-panel",
        chrome="left-stripe",
    ),
    solution=SceneLayoutProfile(
        variant="capability-grid",
        hero_position="top",
        segment_position="below",
        card_shape="rounded-panel",
        chrome="left-stripe",
    ),
    roadmap=SceneLayoutProfile(
        variant="horizontal-rail",
        hero_position="center",
        segment_position="timeline",
        card_shape="rounded-panel",
        chrome="left-stripe",
    ),
    technology=SceneLayoutProfile(
        variant="architecture-stack",
        hero_position="left",
        segment_position="right",
        card_shape="rounded-panel",
        chrome="left-stripe",
    ),
    closing=SceneLayoutProfile(
        variant="center-card",
        hero_position="center",
        segment_position="below",
        card_shape="rounded-panel",
        chrome="orbital-frame",
    ),
)


THEME_PROFILES: dict[str, ThemeProfile] = {
    "dark-tech": DEFAULT_PROFILE,
    "warm-editorial": ThemeProfile(
        name="warm-editorial",
        visual_language="editorial-report",
        card_radius=14,
        stroke_width=1.0,
        shadow_style="paper",
        market=SceneLayoutProfile(
            variant="editorial-tam-strip",
            hero_position="top",
            segment_position="below",
            card_shape="paper-rule",
            chrome="hairline-rules",
        ),
        problem=SceneLayoutProfile(
            variant="editorial-brief",
            hero_position="top",
            segment_position="below",
            card_shape="paper-rule",
            chrome="hairline-rules",
        ),
        solution=SceneLayoutProfile(
            variant="editorial-columns",
            hero_position="left",
            segment_position="right",
            card_shape="paper-rule",
            chrome="hairline-rules",
        ),
        roadmap=SceneLayoutProfile(
            variant="dated-editorial-list",
            hero_position="left",
            segment_position="below",
            card_shape="paper-rule",
            chrome="hairline-rules",
        ),
        technology=SceneLayoutProfile(
            variant="annotated-stack",
            hero_position="top",
            segment_position="below",
            card_shape="paper-rule",
            chrome="hairline-rules",
        ),
        closing=SceneLayoutProfile(
            variant="left-editorial-card",
            hero_position="left",
            segment_position="below",
            card_shape="paper-rule",
            chrome="asymmetric-whitespace",
        ),
    ),
    "neo-brutalist": ThemeProfile(
        name="neo-brutalist",
        visual_language="brutalist-grid",
        card_radius=2,
        stroke_width=3.0,
        shadow_style="none",
        market=SceneLayoutProfile(
            variant="brutalist-block-bars",
            hero_position="left",
            segment_position="right",
            card_shape="hard-block",
            chrome="construction-lines",
        ),
        problem=SceneLayoutProfile(
            variant="brutalist-warning-grid",
            hero_position="left",
            segment_position="right",
            card_shape="hard-block",
            chrome="construction-lines",
        ),
        solution=SceneLayoutProfile(
            variant="brutalist-action-blocks",
            hero_position="top",
            segment_position="below",
            card_shape="hard-block",
            chrome="construction-lines",
        ),
        roadmap=SceneLayoutProfile(
            variant="brutalist-step-ladder",
            hero_position="left",
            segment_position="right",
            card_shape="hard-block",
            chrome="construction-lines",
        ),
        technology=SceneLayoutProfile(
            variant="brutalist-system-map",
            hero_position="left",
            segment_position="right",
            card_shape="hard-block",
            chrome="construction-lines",
        ),
        closing=SceneLayoutProfile(
            variant="wide-hard-banner",
            hero_position="center",
            segment_position="below",
            card_shape="hard-block",
            chrome="construction-lines",
        ),
    ),
    "celestial-glass": ThemeProfile(
        name="celestial-glass",
        visual_language="frosted-orbital",
        card_radius=24,
        stroke_width=1.0,
        shadow_style="glass",
        market=SceneLayoutProfile(
            variant="split-hero-bars",
            hero_position="left",
            segment_position="right",
            card_shape="glass-panel",
            chrome="orbital-glow",
        ),
        problem=SceneLayoutProfile(
            variant="glass-risk-orbits",
            hero_position="center",
            segment_position="orbit",
            card_shape="glass-panel",
            chrome="orbital-glow",
        ),
        solution=SceneLayoutProfile(
            variant="glass-capability-constellation",
            hero_position="center",
            segment_position="orbit",
            card_shape="glass-panel",
            chrome="orbital-glow",
        ),
        roadmap=SceneLayoutProfile(
            variant="orbital-timeline",
            hero_position="center",
            segment_position="timeline",
            card_shape="glass-panel",
            chrome="orbital-glow",
        ),
        technology=SceneLayoutProfile(
            variant="glass-layer-stack",
            hero_position="left",
            segment_position="right",
            card_shape="glass-panel",
            chrome="orbital-glow",
        ),
        closing=SceneLayoutProfile(
            variant="center-glass-card",
            hero_position="center",
            segment_position="below",
            card_shape="glass-panel",
            chrome="orbital-frame",
        ),
    ),
}


def get_theme_profile(lock: dict) -> ThemeProfile:
    """Resolve a structural profile from a spec lock."""

    theme = str(lock.get("theme", "")).lower()
    return THEME_PROFILES.get(theme, DEFAULT_PROFILE)
