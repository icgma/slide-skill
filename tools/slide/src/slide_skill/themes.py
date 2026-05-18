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
