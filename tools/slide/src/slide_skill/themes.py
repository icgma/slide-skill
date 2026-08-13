"""Design theme presets and plugin registry for slide-skill.

Themes are resolved from three sources, in priority order (lowest first;
later sources override earlier ones with the same name):

    1. Built-in themes shipped with the package (this module's BUILTIN_THEMES).
    2. Entry-point plugins registered under the `slide_skill.themes` group
       by external packages (e.g. `pip install slide-theme-foo`).
    3. User themes installed locally as TOML files under
       `~/.config/slide-skill/themes/*.toml` (or whatever
       `SLIDE_SKILL_THEMES_DIR` env var points to).

Phase 18 (v1.4): introduced. v1.4-PLUG-01..03.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

try:
    from importlib.metadata import entry_points
except ImportError:  # pragma: no cover
    from importlib_metadata import entry_points  # type: ignore[no-redef]


ENTRY_POINT_GROUP = "slide_skill.themes"

# Default monospace stack for code font role
_CODE_FONT_STACK = "'JetBrains Mono', 'Fira Code', Consolas, 'Source Code Pro', monospace"

# v4.0 extended color roles (6 base + 6 derived)
EXTENDED_COLOR_ROLES = (
    "background", "bg_secondary", "surface",
    "text", "text_secondary", "text_tertiary",
    "body", "accent", "secondary_accent", "accent_tint",
    "muted", "border",
)

# v4.0 typography size ramp (anchored on 720px canvas height)
DEFAULT_SIZE_RAMP: dict[str, int] = {
    "hero": 72, "h1": 60, "h2": 48, "h3": 36,
    "body": 24, "body_lg": 28,
    "caption": 16, "overline": 14, "footnote": 12,
}


# ---------------------------------------------------------------------------
# TypographySpec — role-based font family system
# ---------------------------------------------------------------------------

@dataclass
class TypographySpec:
    """Role-based typography specification for a slide deck.

    Each role maps to a specific font family. The size ramp provides
    canonical sizes for common text elements.
    """
    title_family: str       # Heading/title font
    body_family: str        # Body text font
    emphasis_family: str    # Bold callouts, hero numbers
    code_family: str        # Monospace for code/data
    size_ramp: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_SIZE_RAMP))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TypographySpec":
        kwargs = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        kwargs.setdefault("size_ramp", dict(DEFAULT_SIZE_RAMP))
        return cls(**kwargs)


# ---------------------------------------------------------------------------
# Palette & typography derivation helpers
# ---------------------------------------------------------------------------

def _hex_shift(hexc: str, delta: int) -> str:
    """Shift a hex color lighter (+) or darker (-) by delta per channel."""
    h_ = hexc.lstrip("#")
    r, g, b = (int(h_[i:i + 2], 16) for i in (0, 2, 4))
    r = max(0, min(255, r + delta))
    g = max(0, min(255, g + delta))
    b = max(0, min(255, b + delta))
    return f"#{r:02X}{g:02X}{b:02X}"


def _hex_with_alpha(hexc: str, alpha_hex: str = "20") -> str:
    """Append alpha channel to a 6-char hex color → 8-char RGBA hex."""
    return hexc.rstrip() + alpha_hex


def _is_light_bg(hexc: str) -> bool:
    """Return True if the hex color has a light perceived luminance."""
    h_ = hexc.lstrip("#")
    r, g, b = int(h_[0:2], 16), int(h_[2:4], 16), int(h_[4:6], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.4


def derive_extended_palette(base_palette: dict[str, str]) -> dict[str, str]:
    """Compute all 12 color roles from a base palette (6 or more roles).

    Missing roles are derived from the 6 core roles using luminance-aware
    shifts.  Existing values are preserved — this function never overwrites
    a color that is already set.

    Returns a new dict with all 12 roles populated.
    """
    p = dict(base_palette)  # shallow copy
    light = _is_light_bg(p.get("background", "#FFFFFF"))

    # bg_secondary: a subtle variant of surface
    if "bg_secondary" not in p:
        surf = p.get("surface", p.get("background", "#FFFFFF"))
        p["bg_secondary"] = _hex_shift(surf, -8 if light else 8)

    # text_secondary: defaults to body color
    if "text_secondary" not in p:
        p["text_secondary"] = p.get("body", p.get("text", "#333333"))

    # text_tertiary: defaults to muted color
    if "text_tertiary" not in p:
        p["text_tertiary"] = p.get("muted", "#999999")

    # secondary_accent: a lighter tint of accent
    if "secondary_accent" not in p:
        accent = p.get("accent", "#3B82F6")
        p["secondary_accent"] = _hex_shift(accent, 30 if light else 40)

    # accent_tint: accent at ~12% opacity (as 8-digit hex)
    if "accent_tint" not in p:
        accent = p.get("accent", "#3B82F6")
        p["accent_tint"] = _hex_with_alpha(accent, "20")

    # border: shifted from muted
    if "border" not in p:
        muted = p.get("muted", "#CCCCCC")
        p["border"] = _hex_shift(muted, 10 if light else -10)

    return p


def derive_typography(font_family: str) -> TypographySpec:
    """Build a TypographySpec from a single font_family string.

    Splits the font stack to extract the primary family for titles,
    keeps the full stack for body, and adds a monospace fallback for code.
    """
    # Extract first family name (strip quotes and whitespace)
    parts = [f.strip().strip("'\"") for f in font_family.split(",")]
    primary = parts[0] if parts else "Arial"

    return TypographySpec(
        title_family=primary,
        body_family=font_family,
        emphasis_family=primary,
        code_family=_CODE_FONT_STACK,
    )


@dataclass
class ThemeSpec:
    """A named visual theme for a slide deck."""

    name: str
    palette: dict[str, str]
    font_family: str
    design_hints: str
    layout_rhythm: list[str] = field(default_factory=lambda: ["anchor", "breathing", "dense"])
    icons: dict[str, str] = field(default_factory=dict)
    source: str = "builtin"  # "builtin" | "entry-point:<pkg>" | "user:<path>"

    # --- v4.0 computed properties ---

    @property
    def extended_palette(self) -> dict[str, str]:
        """Return palette expanded to all 12 color roles."""
        return derive_extended_palette(self.palette)

    @property
    def typography(self) -> TypographySpec:
        """Return role-based typography derived from font_family."""
        return derive_typography(self.font_family)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict, *, source: str = "builtin") -> "ThemeSpec":
        kwargs = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        kwargs.setdefault("layout_rhythm", ["anchor", "breathing", "dense"])
        kwargs.setdefault("icons", {})
        kwargs["source"] = source
        return cls(**kwargs)


BUILTIN_THEMES: dict[str, ThemeSpec] = {
    "dark-tech": ThemeSpec(
        name="dark-tech",
        palette={
            "background": "#0F172A",
            "surface": "#1E293B",
            "text": "#F1F5F9",
            "body": "#94A3B8",
            "accent": "#3B82F6",
            "muted": "#334155",
        },
        font_family="Aptos, Arial, 'Microsoft YaHei', 'PingFang SC', 'Noto Sans SC', 'Source Han Sans SC', sans-serif",
        design_hints=(
            "Dark engineering/technical deck. Deep navy-slate background (#0F172A) with bold blue accent (#3B82F6). "
            "Use linearGradient from #1E293B to #0F172A for card panel fills. "
            "White (#F1F5F9) text on dark surface. Muted body text (#94A3B8). "
            "Strong typographic hierarchy. Left accent stripe (6px wide, full height) in #3B82F6. "
            "Footer bar (32px tall at bottom) filled with #1E293B. Progress dots in accent color. "
            "Geometric chrome: thin rule lines, grid-dot texture optional."
        ),
        layout_rhythm=["anchor", "breathing", "dense"],
        icons={"stroke": "#F1F5F9", "weight": "1.5"},
    ),
    "light-corporate": ThemeSpec(
        name="light-corporate",
        palette={
            "background": "#FFFFFF",
            "surface": "#F8FAFC",
            "text": "#0F172A",
            "body": "#334155",
            "accent": "#1D4ED8",
            "muted": "#CBD5E1",
        },
        font_family="Calibri, Arial, 'Microsoft YaHei', 'PingFang SC', 'Noto Sans SC', 'Source Han Sans SC', sans-serif",
        design_hints=(
            "Clean professional/business deck. White background (#FFFFFF) with navy-blue accent (#1D4ED8). "
            "Soft card panels with fill #F8FAFC and subtle drop shadows. "
            "Dark navy text (#0F172A) on light surface. Professional structure. "
            "Top rule bar (4px) and bottom footer bar (32px) in accent color. "
            "Generous whitespace. Minimal decoration."
        ),
        layout_rhythm=["anchor", "breathing", "dense"],
        icons={"stroke": "#0F172A", "weight": "1.5"},
    ),
    "warm-editorial": ThemeSpec(
        name="warm-editorial",
        palette={
            "background": "#FDF6EE",
            "surface": "#FFFBF5",
            "text": "#1C1917",
            "body": "#57534E",
            "accent": "#EA580C",
            "muted": "#D6D3D1",
        },
        font_family="Georgia, 'Times New Roman', 'Songti SC', 'STSong', 'Source Han Serif SC', 'Noto Serif SC', serif",
        design_hints=(
            "Warm editorial/humanities deck. Cream background (#FDF6EE) with warm orange accent (#EA580C). "
            "Use serif fonts for headings and titles. Warm tones and generous whitespace. "
            "Soft horizontal rule separators in muted (#D6D3D1). "
            "Body text (#57534E) on cream surface. Feels like a high-quality publication."
        ),
        layout_rhythm=["anchor", "breathing", "breathing"],
        icons={"stroke": "#1C1917", "weight": "1.25"},
    ),
    "data-forward": ThemeSpec(
        name="data-forward",
        palette={
            "background": "#F1F5F9",
            "surface": "#FFFFFF",
            "text": "#0F172A",
            "body": "#475569",
            "accent": "#0284C7",
            "muted": "#E2E8F0",
        },
        font_family="Roboto, Arial, 'Microsoft YaHei', 'PingFang SC', 'Noto Sans SC', 'Source Han Sans SC', sans-serif",
        design_hints=(
            "Data-analytics/research deck. Light gray background (#F1F5F9) with strong sky-blue accent (#0284C7). "
            "White (#FFFFFF) card panels for data and metrics. Clean sans-serif typography. "
            "Grid layouts for multi-metric slides. Charts and numbers get center stage. "
            "Minimal decoration so data can breathe. Blue rule lines to separate sections."
        ),
        layout_rhythm=["anchor", "dense", "dense"],
        icons={"stroke": "#0F172A", "weight": "1.5"},
    ),
    "vibrant-startup": ThemeSpec(
        name="vibrant-startup",
        palette={
            "background": "#FFFFFF",
            "surface": "#FAFAFA",
            "text": "#111827",
            "body": "#6B7280",
            "accent": "#7C3AED",
            "muted": "#E5E7EB",
        },
        font_family="Inter, 'Helvetica Neue', 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', 'Source Han Sans SC', sans-serif",
        design_hints=(
            "Vibrant startup/pitch deck. White (#FFFFFF) background with vivid purple accent (#7C3AED). "
            "Bold oversized headlines. Use radialGradient for hero slide backgrounds. "
            "Modern geometric shapes as decorative elements. "
            "High visual impact and energy. Strong contrast between sections."
        ),
        layout_rhythm=["anchor", "breathing", "dense"],
        icons={"stroke": "#111827", "weight": "2"},
    ),
    "mckinsey-consulting": ThemeSpec(
        name="mckinsey-consulting",
        palette={
            "background": "#FFFFFF",
            "surface": "#ECF0F1",
            "text": "#2C3E50",
            "body": "#5D6D7E",
            "accent": "#005587",
            "muted": "#BDC3C7",
        },
        font_family="Arial, 'Helvetica Neue', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif",
        design_hints=(
            "Top-tier strategy consulting deck (McKinsey blue). White background with deep McKinsey Blue (#005587) accent. "
            "Conclusion-first layout: bold takeaway bar at top, supporting evidence below. "
            "Light gray (#ECF0F1) cards with thin borders. Title-dark-gray (#2C3E50) headings, body gray (#5D6D7E) text. "
            "Amber data highlights (#F5A623) only on key numbers. Generous whitespace, structured pyramid hierarchy. "
            "Top blue rule (3px) under title, bottom footer line in muted gray with source citation slot."
        ),
        layout_rhythm=["anchor", "dense", "dense"],
        icons={"stroke": "#005587", "weight": "1.5"},
    ),
    "anthropic-ai": ThemeSpec(
        name="anthropic-ai",
        palette={
            "background": "#FFFFFF",
            "surface": "#F8FAFC",
            "text": "#1A1A2E",
            "body": "#64748B",
            "accent": "#D97757",
            "muted": "#E2E8F0",
        },
        font_family="'Helvetica Neue', Arial, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif",
        design_hints=(
            "Anthropic-inspired AI/developer deck. Mixed mode: dark deep-space (#1A1A2E) cover and chapter dividers, "
            "light (#FFFFFF) content pages. Brand orange (#D97757) accent for emphasis and key data. "
            "Cloud-white (#F8FAFC) cards with subtle borders (#E2E8F0). "
            "Tech blue (#4A90D9) for flow-chart links, mint (#10B981) for positive signals, coral (#EF4444) for risks. "
            "Conclusion-first layout, large readable body text, monospaced code blocks where applicable."
        ),
        layout_rhythm=["anchor", "breathing", "dense"],
        icons={"stroke": "#D97757", "weight": "1.5"},
    ),
    "google-brand": ThemeSpec(
        name="google-brand",
        palette={
            "background": "#FFFFFF",
            "surface": "#F8F9FA",
            "text": "#1A237E",
            "body": "#5F6368",
            "accent": "#4285F4",
            "muted": "#E8EAED",
        },
        font_family="'Google Sans', Roboto, Arial, 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif",
        design_hints=(
            "Google-brand annual-report / tech-sharing deck. White background with the Google four-color palette: "
            "Blue (#4285F4) primary accent, plus accent rotation to Red (#EA4335) / Yellow (#FBBC04) / Green (#34A853) "
            "for category chips, multi-metric tiles, and chart series. "
            "Deep blue (#1A237E) titles, body gray (#5F6368) content, light-gray (#F8F9FA) cards. "
            "Generous whitespace, rounded card corners (12px), gradient title underline blue→deep-blue."
        ),
        layout_rhythm=["anchor", "breathing", "dense"],
        icons={"stroke": "#1A237E", "weight": "1.5"},
    ),
    "pixel-retro": ThemeSpec(
        name="pixel-retro",
        palette={
            "background": "#0D1117",
            "surface": "#161B22",
            "text": "#39FF14",
            "body": "#C9D1D9",
            "accent": "#FF2E97",
            "muted": "#30363D",
        },
        font_family="'JetBrains Mono', 'Fira Code', 'Cascadia Mono', Consolas, 'Source Code Pro', 'PingFang SC', monospace",
        design_hints=(
            "Pixel-retro / cyberpunk dev deck. Deep-space-black (#0D1117) background, starry-night card panels (#161B22). "
            "Neon palette: green (#39FF14) for primary text and success, cyber-pink (#FF2E97) for accent and warnings, "
            "electric-blue (#00D4FF) for links and info, gold (#FFD700) for highlights/timelines. "
            "Monospace fonts throughout. 8-bit pixel decoration: blocky borders, terminal-style headers (`> title`), "
            "scanline overlays optional. ASCII-art dividers welcome."
        ),
        layout_rhythm=["dense", "dense", "dense"],
        icons={"stroke": "#39FF14", "weight": "2"},
    ),
    "psychology-warm": ThemeSpec(
        name="psychology-warm",
        palette={
            "background": "#F5F0E8",
            "surface": "#FFFDF8",
            "text": "#3E3A36",
            "body": "#6B6259",
            "accent": "#A67C52",
            "muted": "#D9CFC1",
        },
        font_family="'Source Han Serif SC', 'Noto Serif SC', Georgia, 'Songti SC', 'STSong', 'Times New Roman', serif",
        design_hints=(
            "Psychology / counseling / healing deck. Warm sand background (#F5F0E8) with soft cream cards (#FFFDF8). "
            "Earthy taupe accent (#A67C52). Muted sage hint (#8FA68E) for secondary chips/tags. "
            "Serif headings for human warmth. Generous line-height, plenty of whitespace, rounded card corners. "
            "Soft, rounded geometric shapes (no sharp corners). Hand-drawn style icon strokes (rounded line-cap). "
            "Watercolor-style gradient blob in corners as decoration."
        ),
        layout_rhythm=["breathing", "breathing", "breathing"],
        icons={"stroke": "#3E3A36", "weight": "1.25"},
    ),
    "medical-clean": ThemeSpec(
        name="medical-clean",
        palette={
            "background": "#FFFFFF",
            "surface": "#F0F7F8",
            "text": "#0B3D40",
            "body": "#3E5C5F",
            "accent": "#0E9F8E",
            "muted": "#CFE3E1",
        },
        font_family="'Source Sans 3', Roboto, Arial, 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif",
        design_hints=(
            "Medical / clinical / healthcare deck. Clean white background with mint-teal accent (#0E9F8E) and "
            "pale-aqua (#F0F7F8) card panels. Deep-teal text (#0B3D40) for clinical authority. "
            "Cross/cardio/molecule iconography. Clear data tables for case studies and trial metrics. "
            "Vital-signs accent stripe (thin teal line, optional pulse waveform decoration along header). "
            "Coral red (#E24C4C) used sparingly for warnings/contraindications only."
        ),
        layout_rhythm=["anchor", "dense", "dense"],
        icons={"stroke": "#0B3D40", "weight": "1.5"},
    ),
    "gov-red": ThemeSpec(
        name="gov-red",
        palette={
            "background": "#FFFFFF",
            "surface": "#FBF3F1",
            "text": "#1A1A1A",
            "body": "#4A4A4A",
            "accent": "#B22222",
            "muted": "#E8D7D3",
        },
        font_family="'Source Han Serif SC', 'Noto Serif SC', SimSun, 'Songti SC', 'STSong', Georgia, serif",
        design_hints=(
            "Government / party / authoritative report deck. White background with deep China-red accent (#B22222) "
            "and gold trim (#C9A24A) reserved for awards/honors. Heavy serif headings (宋体/Source Han Serif). "
            "Top double-rule bar (red 6px + gold 1px) under title. Centered formal layout with symmetric composition. "
            "Soft warm cream card panels (#FBF3F1). Small decorative red ribbon accent in corner. "
            "Solemn, dignified, official tone. Avoid playful shapes."
        ),
        layout_rhythm=["anchor", "anchor", "breathing"],
        icons={"stroke": "#B22222", "weight": "1.5"},
    ),
    # ------------------------------------------------------------------
    # v3.1 themes — absorbed from `pptx` skill palettes and
    # `ui-ux-pro-max` colors.csv. Each picks ONE distinctive accent
    # so swapping it into a different topic would feel wrong (per
    # pptx skill: "if your colors would work in any deck, you weren't
    # specific enough").
    # ------------------------------------------------------------------
    "midnight-executive": ThemeSpec(
        name="midnight-executive",
        palette={
            "background": "#FFFFFF", "surface": "#F5F8FF",
            "text": "#1E2761", "body": "#3F4A7A",
            "accent": "#1E2761", "muted": "#CADCFC",
        },
        font_family="Georgia, 'Times New Roman', 'Songti SC', 'Source Han Serif SC', serif",
        design_hints=(
            "Boardroom executive deck. Deep navy (#1E2761) as both text and accent, "
            "ice-blue (#CADCFC) for soft callouts, cream (#F5F8FF) panels. "
            "Serif headlines for gravitas. Use full-bleed dark covers / closing slides."
        ),
        layout_rhythm=["anchor", "breathing", "dense"],
        icons={"stroke": "#1E2761", "weight": "1.5"},
    ),
    "forest-moss": ThemeSpec(
        name="forest-moss",
        palette={
            "background": "#F5F5F5", "surface": "#FFFFFF",
            "text": "#1F2A1F", "body": "#3D4F3D",
            "accent": "#2C5F2D", "muted": "#97BC62",
        },
        font_family="Calibri, 'Microsoft YaHei', 'PingFang SC', 'Noto Sans SC', sans-serif",
        design_hints=(
            "Sustainability / nature deck. Forest-green (#2C5F2D) accent with moss "
            "(#97BC62) supporting tone on cream. Use organic shape orbs and leaf icons."
        ),
        layout_rhythm=["anchor", "breathing", "breathing"],
        icons={"stroke": "#2C5F2D", "weight": "1.5"},
    ),
    "coral-energy": ThemeSpec(
        name="coral-energy",
        palette={
            "background": "#FFFFFF", "surface": "#FFF5F1",
            "text": "#2F3C7E", "body": "#4A5688",
            "accent": "#F96167", "muted": "#F9E795",
        },
        font_family="Poppins, Calibri, 'PingFang SC', 'Noto Sans SC', sans-serif",
        design_hints=(
            "High-energy marketing/campaign deck. Coral (#F96167) accent against navy "
            "(#2F3C7E) text, with gold (#F9E795) highlight chips. Bold geometric shapes."
        ),
        layout_rhythm=["anchor", "anchor", "dense"],
        icons={"stroke": "#2F3C7E", "weight": "2"},
    ),
    "terracotta-warm": ThemeSpec(
        name="terracotta-warm",
        palette={
            "background": "#E7E8D1", "surface": "#F4F5E2",
            "text": "#1F1F1F", "body": "#5A4A42",
            "accent": "#B85042", "muted": "#A7BEAE",
        },
        font_family="Palatino, Georgia, 'Songti SC', 'Source Han Serif SC', serif",
        design_hints=(
            "Editorial / lifestyle / cultural deck. Terracotta (#B85042) on sand "
            "(#E7E8D1) with sage (#A7BEAE) accents. Warm serif typography. "
            "Magazine-grade composition."
        ),
        layout_rhythm=["breathing", "breathing", "anchor"],
        icons={"stroke": "#B85042", "weight": "1.25"},
    ),
    "ocean-deep": ThemeSpec(
        name="ocean-deep",
        palette={
            "background": "#0A1929", "surface": "#102A43",
            "text": "#E0F2FE", "body": "#94B3CC",
            "accent": "#1C7293", "muted": "#21295C",
        },
        font_family="Roboto, Aptos, Arial, 'PingFang SC', 'Noto Sans SC', sans-serif",
        design_hints=(
            "Premium tech/product launch deck. Deep ocean navy (#0A1929) with teal "
            "(#1C7293) accents. Apple-keynote feel — large typography, dark "
            "backdrops, restrained accents, subtle gradient orbs."
        ),
        layout_rhythm=["anchor", "anchor", "breathing"],
        icons={"stroke": "#E0F2FE", "weight": "1.5"},
    ),
    "charcoal-minimal": ThemeSpec(
        name="charcoal-minimal",
        palette={
            "background": "#F2F2F2", "surface": "#FFFFFF",
            "text": "#212121", "body": "#5A5A5A",
            "accent": "#36454F", "muted": "#D4D4D4",
        },
        font_family="Helvetica, Arial, 'PingFang SC', 'Noto Sans SC', sans-serif",
        design_hints=(
            "Swiss-minimal premium deck. Charcoal (#36454F) accent on near-white "
            "(#F2F2F2). Aggressive negative space, type-driven hierarchy, NO decorative "
            "lines or shadows. Ideal for design-conscious audiences."
        ),
        layout_rhythm=["breathing", "breathing", "anchor"],
        icons={"stroke": "#212121", "weight": "1"},
    ),
    "berry-cream": ThemeSpec(
        name="berry-cream",
        palette={
            "background": "#ECE2D0", "surface": "#FFFFFF",
            "text": "#3D1A2E", "body": "#6D2E46",
            "accent": "#6D2E46", "muted": "#A26769",
        },
        font_family="Playfair Display, Georgia, 'Songti SC', 'Source Han Serif SC', serif",
        design_hints=(
            "Refined creative / portfolio / personal deck. Berry (#6D2E46) accent on "
            "cream (#ECE2D0), dusty-rose (#A26769) supporting. Display serif for "
            "emotional headlines. Plenty of whitespace."
        ),
        layout_rhythm=["breathing", "anchor", "breathing"],
        icons={"stroke": "#6D2E46", "weight": "1.25"},
    ),
    "sage-calm": ThemeSpec(
        name="sage-calm",
        palette={
            "background": "#F4F7F4", "surface": "#FFFFFF",
            "text": "#2A3D33", "body": "#50808E",
            "accent": "#69A297", "muted": "#84B59F",
        },
        font_family="Open Sans, Calibri, 'PingFang SC', 'Noto Sans SC', sans-serif",
        design_hints=(
            "Wellness / training / workshop deck. Sage (#69A297) accent with eucalyptus "
            "support, slate (#50808E) body text. Calm, low-contrast, friendly."
        ),
        layout_rhythm=["breathing", "breathing", "breathing"],
        icons={"stroke": "#2A3D33", "weight": "1.5"},
    ),
    "academic-royal": ThemeSpec(
        name="academic-royal",
        palette={
            "background": "#FFFFFF", "surface": "#F8F6FF",
            "text": "#1A1A2E", "body": "#3F3F5E",
            "accent": "#4B0082", "muted": "#D4D0E8",
        },
        font_family="Cambria, Georgia, 'Songti SC', 'Source Han Serif SC', serif",
        design_hints=(
            "Academic / thesis defense / research deck. Royal-purple (#4B0082) accent "
            "on white. Cambria serif for scholarly tone. Number-anchored layouts and "
            "rule-line dividers between sections."
        ),
        layout_rhythm=["anchor", "dense", "breathing"],
        icons={"stroke": "#4B0082", "weight": "1.5"},
    ),
    "indigo-saas": ThemeSpec(
        name="indigo-saas",
        palette={
            "background": "#F5F3FF", "surface": "#FFFFFF",
            "text": "#1E1B4B", "body": "#4A4485",
            "accent": "#6366F1", "muted": "#E0E7FF",
        },
        font_family="Poppins, Inter, Calibri, 'PingFang SC', 'Noto Sans SC', sans-serif",
        design_hints=(
            "Modern SaaS / product / pitch deck. Indigo (#6366F1) primary on lavender "
            "(#F5F3FF), emerald (#059669) optional CTA accent. Geometric Poppins "
            "headlines, clean cards with soft shadows."
        ),
        layout_rhythm=["anchor", "anchor", "dense"],
        icons={"stroke": "#1E1B4B", "weight": "1.5"},
    ),
    # ------------------------------------------------------------------
    # v5.0 Premium Frontend-Design themes — 10 distinctive high-end
    # visual styles that avoid generic "AI slop" aesthetics.
    # Each commits to a BOLD, intentional design direction per the
    # Anthropic frontend-design skill guidelines.
    # ------------------------------------------------------------------
    "academic-noir": ThemeSpec(
        name="academic-noir",
        palette={
            "background": "#FAF6F0", "surface": "#FFFFFF",
            "text": "#2D1B22", "body": "#5E4E53",
            "accent": "#A83C50", "muted": "#EAE0D5",
        },
        font_family="'Playfair Display', Georgia, 'Source Han Serif SC', 'Songti SC', SimSun, serif",
        design_hints=(
            "Premium academic editorial deck. Warm sand-paper background (#FAF6F0) with deep mulberry "
            "text (#2D1B22) and berry-terracotta accent (#A83C50). NO rounded card containers — text "
            "floats directly on the warm canvas, structured only by 0.5px hairline rules and generous "
            "whitespace. Staggered vertical offsets between columns (one shifted up 25px, next down "
            "15px) create asymmetric editorial tension. Double thin-line frame borders around slide "
            "edges. Large low-opacity CJK serif watermark characters behind content columns. "
            "Serif typography for all headings (Playfair Display / Source Han Serif SC). "
            "Fine vertical bookmark stripe (4px) on left edge in accent color."
        ),
        layout_rhythm=["breathing", "breathing", "anchor"],
        icons={"stroke": "#2D1B22", "weight": "1.25"},
    ),
    "neo-brutalist": ThemeSpec(
        name="neo-brutalist",
        palette={
            "background": "#FBFBF9", "surface": "#FFFFFF",
            "text": "#0A0A0A", "body": "#333333",
            "accent": "#1D4ED8", "muted": "#E5E5E5",
        },
        font_family="'Space Grotesk', Impact, 'Microsoft YaHei', 'Noto Sans SC', sans-serif",
        design_hints=(
            "Neo-brutalist Swiss-grid deck. Stark white (#FBFBF9) background with carbon-black "
            "(#0A0A0A) text and thick 2-3px solid black borders around ALL containers. ZERO blur, "
            "ZERO gradients, ZERO rounded corners. Drop shadows are hard offset (dx=4, dy=4) in "
            "pure black with opacity=1. Massive font-size contrast (titles 80px, body 14px) as "
            "the sole decorative element. Klein-blue (#1D4ED8) or safety-orange (#F97316) used "
            "as a single-point accent for maximum impact. Monospace code blocks welcome. "
            "Aggressive grid alignment with visible construction lines."
        ),
        layout_rhythm=["dense", "dense", "anchor"],
        icons={"stroke": "#0A0A0A", "weight": "2.5"},
    ),
    "industrial-blueprint": ThemeSpec(
        name="industrial-blueprint",
        palette={
            "background": "#0B2B5C", "surface": "#0E3470",
            "text": "#E0F2FE", "body": "#94B8D9",
            "accent": "#00E5FF", "muted": "#1A4A7A",
        },
        font_family="'Roboto Mono', 'JetBrains Mono', 'Fira Code', Consolas, 'Source Code Pro', monospace",
        design_hints=(
            "Technical blueprint / engineering drawing deck. Deep blueprint-navy (#0B2B5C) "
            "background with aurora-cyan (#00E5FF) accent lines and inspection-red (#C82A2A) "
            "for warnings. All-monospace typography. Grid-dot texture background (tiny dots at "
            "regular intervals). Content frames use L-shaped corner brackets instead of full "
            "borders. Dimension lines with arrows (|<--- 120px --->|) between elements. "
            "Cross-hair alignment markers (+) at container corners. Coordinate labels in small "
            "text. Technical drawing aesthetic — precision, cold, engineered."
        ),
        layout_rhythm=["dense", "dense", "dense"],
        icons={"stroke": "#00E5FF", "weight": "1.5"},
    ),
    "organic-clay": ThemeSpec(
        name="organic-clay",
        palette={
            "background": "#F6F4ED", "surface": "#E2DCD2",
            "text": "#343A40", "body": "#5C5248",
            "accent": "#D4A373", "muted": "#CCD5AE",
        },
        font_family="Lora, Georgia, Garamond, 'Source Han Serif SC', 'Songti SC', serif",
        design_hints=(
            "Organic clay / earthy botanics deck. Mineral chalk-white (#F6F4ED) background "
            "with warm terracotta-clay surfaces (#E2DCD2). Wild sage-green (#CCD5AE) for "
            "secondary highlights. Containers use organic smooth Bezier curves instead of "
            "hard rectangles — think soft clay blob shapes. Shadows are directionless ambient "
            "diffuse (stdDeviation=30, opacity=0.02) like sunlight on ceramic. Serif typography "
            "(Lora/Garamond) for warm human feel. Rounded line-cap icon strokes. "
            "Watercolor-style gradient blob decorations in corners at very low opacity."
        ),
        layout_rhythm=["breathing", "breathing", "breathing"],
        icons={"stroke": "#343A40", "weight": "1.25"},
    ),
    "art-deco-archive": ThemeSpec(
        name="art-deco-archive",
        palette={
            "background": "#132E27", "surface": "#1A3B32",
            "text": "#FFFFF0", "body": "#C8C8B0",
            "accent": "#D4AF37", "muted": "#2A5A4A",
        },
        font_family="Didot, Bodoni, 'Source Han Serif SC', 'Noto Serif SC', Georgia, serif",
        design_hints=(
            "Art Deco vintage archive deck. Deep midnight-emerald (#132E27) background with "
            "brushed champagne-gold (#D4AF37) decorative frames and accent lines. Ivory text "
            "(#FFFFF0) on dark surface. Symmetric golden-ratio nested line frames around content "
            "areas. Ultra-wide letter-spacing (6px+) on uppercase headings. High-contrast Didone "
            "serif titles (Didot/Bodoni). Optional Chinese vertical text layout alongside gold "
            "vertical rules. Geometric Art Deco fan/sunburst motifs as decorative corners. "
            "Lavish, classical, museum-grade archival authority."
        ),
        layout_rhythm=["anchor", "anchor", "breathing"],
        icons={"stroke": "#D4AF37", "weight": "1"},
    ),
    "japandi-zen": ThemeSpec(
        name="japandi-zen",
        palette={
            "background": "#FEFEFE", "surface": "#F8F8F6",
            "text": "#1A1A1A", "body": "#6B6B6B",
            "accent": "#8E7960", "muted": "#F3F3F3",
        },
        font_family="Satoshi, Archivo, 'Noto Sans CJK SC', 'PingFang SC', sans-serif",
        design_hints=(
            "Japandi quiet zen deck. Near-pure-white (#FEFEFE) background with dried-leaf brown "
            "(#8E7960) or soft bamboo-green (#A4B09F) as the sole accent. 90%+ of each slide is "
            "deliberate empty space. NO borders, NO containers, NO shadows. Text is positioned "
            "using absolute geometric gravity (anchored to bottom-left or right-center). A single "
            "0.25px ultra-thin gray line spans the full width as the only structural element. "
            "Typography uses extreme negative space with 130%+ letter-spacing on CJK characters. "
            "Maximum restraint. If it feels empty, it is working."
        ),
        layout_rhythm=["breathing", "breathing", "breathing"],
        icons={"stroke": "#1A1A1A", "weight": "0.75"},
    ),
    "high-fashion": ThemeSpec(
        name="high-fashion",
        palette={
            "background": "#000000", "surface": "#F8F3EC",
            "text": "#FFFFFF", "body": "#CCCCCC",
            "accent": "#FF2D2D", "muted": "#333333",
        },
        font_family="Didot, 'Bodoni MT', 'Playfair Display', Georgia, 'Source Han Serif SC', serif",
        design_hints=(
            "High-fashion luxury editorial deck (Vogue/Bazaar aesthetic). Pure black (#000000) "
            "or pure white backgrounds — never gray. High-contrast Didone serif headlines at "
            "massive sizes (80-120px) used as visual art, not just text. Body copy is ultra-thin "
            "weight sans-serif at tiny sizes (12-14px). Title text OVERLAYS content as a "
            "semi-transparent background layer. Drop-cap initials (large decorative first letter) "
            "begin each text section. NO card containers — content defined purely by typography "
            "hierarchy and alignment. Accent red (#FF2D2D) used only for single-word emphasis. "
            "Black and white photography crops welcome."
        ),
        layout_rhythm=["anchor", "breathing", "breathing"],
        icons={"stroke": "#FFFFFF", "weight": "1"},
    ),
    "retro-terminal": ThemeSpec(
        name="retro-terminal",
        palette={
            "background": "#090A09", "surface": "#162E1A",
            "text": "#00FF55", "body": "#88CC88",
            "accent": "#FF9F00", "muted": "#1A2E1A",
        },
        font_family="'JetBrains Mono', 'Courier Prime', 'Fira Code', Consolas, 'Source Code Pro', monospace",
        design_hints=(
            "Retro-futuristic tactical terminal deck. Abyss-black (#090A09) background with "
            "radar-phosphor green (#00FF55) primary text and amber (#FF9F00) accent for warnings "
            "and highlights. ALL-monospace typography throughout. Page hierarchy built using "
            "ASCII-art brackets [ SECTION-14 ] and dot-line connectors o---o instead of card "
            "borders. Concentric dashed-circle radar sweeps (stroke-dasharray) as background "
            "decoration. Scanline overlay effect optional. Terminal-style headers with > prefix. "
            "Cold War radar console / DOS CRT monitor aesthetic. Feels like mission control."
        ),
        layout_rhythm=["dense", "dense", "dense"],
        icons={"stroke": "#00FF55", "weight": "2"},
    ),
    "botanical-herbarium": ThemeSpec(
        name="botanical-herbarium",
        palette={
            "background": "#F2EAD0", "surface": "#FAF4E4",
            "text": "#3A4736", "body": "#5A6B52",
            "accent": "#7D6852", "muted": "#D4C9A8",
        },
        font_family="'Cormorant Garamond', Garamond, 'Source Han Serif SC', 'Songti SC', Georgia, serif",
        design_hints=(
            "Botanical garden / vintage herbarium deck. Antique parchment (#F2EAD0) background "
            "with pine-needle dark-green (#3A4736) text and tea-stain brown (#7D6852) accent. "
            "Misty stone-blue (#8FA2A6) for secondary highlights. Elegant italic Garamond "
            "typography evoking handwritten naturalist field notes. Containers use fine wavy "
            "serrated border lines (specimen-clip edge effect). Key numbers have a very faint, "
            "low-opacity watercolor wash ellipse behind them (soft organic blob, not a rectangle). "
            "Darwin's HMS Beagle journal aesthetic. Romantic, scientific, archival warmth."
        ),
        layout_rhythm=["breathing", "breathing", "anchor"],
        icons={"stroke": "#3A4736", "weight": "1.25"},
    ),
    "celestial-glass": ThemeSpec(
        name="celestial-glass",
        palette={
            "background": "#07070C", "surface": "#12121A",
            "text": "#F0F4FF", "body": "#A0B0D0",
            "accent": "#4FACFE", "muted": "#1A1A2E",
        },
        font_family="'Plus Jakarta Sans', 'Clash Display', Inter, 'PingFang SC', 'Noto Sans SC', sans-serif",
        design_hints=(
            "Celestial frosted-glass deck. Deep-space black (#07070C) background with large "
            "aurora gradient mesh blobs (blend of #00F2FE cyan and #4FACFE blue-violet) as "
            "deep background decoration behind a heavy Gaussian blur (stdDeviation=40). "
            "Content panels are frosted-glass: semi-transparent white fill (opacity=0.03-0.05) "
            "with ultra-thin white borders (stroke-width=0.5, stroke-opacity=0.1). Weightless, "
            "floating, zero-gravity feel. Modern geometric sans-serif typography (Plus Jakarta "
            "Sans). Fluorescent white (#F0F4FF) text. Avoid any hard edges or solid fills — "
            "everything should feel ethereal, translucent, and cosmically distant."
        ),
        layout_rhythm=["anchor", "breathing", "breathing"],
        icons={"stroke": "#F0F4FF", "weight": "1.5"},
    ),
    # ------------------------------------------------------------------
    # Phase 52 — Chinese university thesis-defense conventions
    # (cross-validated in .planning/research/v5.0-COMPETITIVE-GAP.md §2.3:
    # navy primary, white bg, YaHei-first type, dark red for key data only).
    # ------------------------------------------------------------------
    "academic-defense": ThemeSpec(
        name="academic-defense",
        palette={
            "background": "#FFFFFF",
            "surface": "#F4F6FA",
            "text": "#1B2A4A",
            "body": "#44506B",
            "accent": "#2D4A7A",
            "muted": "#C9D2E3",
        },
        font_family="'Microsoft YaHei', 'PingFang SC', 'Noto Sans SC', 'Source Han Sans SC', Arial, sans-serif",
        design_hints=(
            "Chinese academic defense deck for university thesis review (毕业答辩). "
            "White background with navy structural color (#1B2A4A) for titles and the thin top band, "
            "deep-blue accent (#2D4A7A) for cards and navigation elements. "
            "Dark red #B03A2E is reserved EXCLUSIVELY for key data emphasis (never decoration). "
            "Restrained composition: thin top navy band, bottom footer with page number \"NN / TT\", "
            "no gradient orbs, no playful decoration. Generous line spacing for projector readability. "
            "总-分-总 structure: cover → outline → body sections → conclusions → acknowledgements."
        ),
        layout_rhythm=["anchor", "breathing", "dense"],
        icons={"stroke": "#1B2A4A", "weight": "1.5"},
    ),
}


def user_themes_dir() -> Path:
    """Return the directory holding user-installed theme TOML files."""
    override = os.environ.get("SLIDE_SKILL_THEMES_DIR")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "slide-skill" / "themes"


def _load_toml_theme(path: Path) -> ThemeSpec:
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    if "theme" in data and isinstance(data["theme"], dict):
        data = data["theme"]
    if "name" not in data:
        data["name"] = path.stem
    return ThemeSpec.from_dict(data, source=f"user:{path}")


def _discover_entry_point_themes() -> Iterable[ThemeSpec]:
    """Yield ThemeSpec objects exposed via the `slide_skill.themes` entry-point group.

    Plugin authors expose either a ThemeSpec instance or a dict-like factory:

        # in their pyproject.toml:
        # [project.entry-points."slide_skill.themes"]
        # midnight = "my_theme_pkg:MIDNIGHT_THEME"
    """
    try:
        eps = entry_points(group=ENTRY_POINT_GROUP)
    except TypeError:  # pragma: no cover — older importlib_metadata
        eps = entry_points().get(ENTRY_POINT_GROUP, [])  # type: ignore[union-attr]
    for ep in eps:
        try:
            obj = ep.load()
        except Exception:  # noqa: BLE001 — plugin may be broken; skip silently
            continue
        if callable(obj):
            try:
                obj = obj()
            except Exception:  # noqa: BLE001
                continue
        if isinstance(obj, ThemeSpec):
            obj.source = f"entry-point:{ep.name}"
            yield obj
        elif isinstance(obj, dict):
            spec = ThemeSpec.from_dict(obj, source=f"entry-point:{ep.name}")
            yield spec


def _discover_user_themes() -> Iterable[ThemeSpec]:
    base = user_themes_dir()
    if not base.is_dir():
        return
    for path in sorted(base.glob("*.toml")):
        try:
            yield _load_toml_theme(path)
        except Exception:  # noqa: BLE001
            continue


def _build_registry() -> dict[str, ThemeSpec]:
    registry: dict[str, ThemeSpec] = dict(BUILTIN_THEMES)
    for spec in _discover_entry_point_themes():
        registry[spec.name] = spec
    for spec in _discover_user_themes():
        registry[spec.name] = spec
    return registry


# Backwards-compatible exposure of the all-themes mapping. We expose THEMES as
# a property-like dict that always reflects the current registry — but for
# read access existing code paths can keep using `THEMES["dark-tech"]`.
class _ThemeRegistry(dict):
    def __init__(self) -> None:
        super().__init__()
        self.refresh()

    def refresh(self) -> None:
        self.clear()
        self.update(_build_registry())


THEMES: _ThemeRegistry = _ThemeRegistry()


def get_theme(name: str) -> ThemeSpec:
    """Return a ThemeSpec by name. Falls back to 'dark-tech' if not found."""
    THEMES.refresh()
    return THEMES.get(name, THEMES["dark-tech"])


def list_themes() -> list[ThemeSpec]:
    """Return all available themes (built-in + entry-point + user-installed)."""
    THEMES.refresh()
    return list(THEMES.values())


_SAFE_THEME_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$")


def _safe_theme_dest(name: str) -> Path:
    """Resolve a user-themes destination, refusing path-traversal-y names."""
    if not isinstance(name, str) or not _SAFE_THEME_NAME.match(name):
        raise ValueError(
            f"Invalid theme name: {name!r}. Must match {_SAFE_THEME_NAME.pattern} "
            "(alphanumeric, dash, underscore; <=64 chars; no path separators)."
        )
    base = user_themes_dir().resolve()
    base.mkdir(parents=True, exist_ok=True)
    dest = (base / f"{name}.toml").resolve()
    # Containment check — protects against symlink/`..` edge cases.
    try:
        dest.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Theme path escapes user themes directory: {dest}") from exc
    return dest


def install_user_theme(toml_path: str | Path, *, overwrite: bool = False) -> Path:
    """Copy a TOML theme file into the user themes directory and return the destination."""
    src = Path(toml_path).expanduser()
    if not src.is_file():
        raise FileNotFoundError(f"Theme file not found: {src}")
    # Validate by loading — raises if malformed.
    spec = _load_toml_theme(src)
    dest = _safe_theme_dest(spec.name)
    if dest.exists() and not overwrite:
        raise FileExistsError(f"Theme already installed: {dest}. Pass overwrite=True to replace.")
    dest.write_bytes(src.read_bytes())
    THEMES.refresh()
    return dest


def remove_user_theme(name: str) -> Path:
    """Delete a user-installed theme by name. Raises if not user-installed."""
    if name in BUILTIN_THEMES:
        raise ValueError(f"Cannot remove built-in theme: {name}")
    dest = _safe_theme_dest(name)
    if not dest.is_file():
        raise FileNotFoundError(f"User theme not found: {dest}")
    dest.unlink()
    THEMES.refresh()
    return dest
