"""Multi-language templates + font preflight.

Phase 25 (v1.4): introduced. v1.4-I18N-01..04.

Capabilities:

  * `LANGUAGE_PROFILES` — per-language metadata: script direction, default
    serif/sans-serif font candidates, line-height multiplier, character
    measurement weight (CJK/Korean/Arabic/Hebrew etc.).
  * `detect_language(text)` — quick heuristic by Unicode block frequency.
  * `font_preflight(theme, project)` — scans deck text for missing glyphs in
    the theme's declared font families; suggests fallbacks; flags RTL slides.
  * `apply_language_profile(theme, lang)` — returns a derived ThemeSpec with
    typography overrides for the target language.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Optional

from .themes import ThemeSpec


@dataclass(frozen=True)
class LanguageProfile:
    code: str
    name: str
    direction: str = "ltr"  # "ltr" | "rtl"
    serif: tuple[str, ...] = ()
    sans: tuple[str, ...] = ()
    mono: tuple[str, ...] = ()
    line_height: float = 1.4
    measure_weight: float = 1.0  # multiplier for est. character width vs Latin


LANGUAGE_PROFILES: dict[str, LanguageProfile] = {
    "en": LanguageProfile("en", "English",
                          serif=("Source Serif Pro", "Georgia"),
                          sans=("Inter", "Helvetica", "Arial"),
                          mono=("JetBrains Mono", "Menlo", "Consolas")),
    "zh": LanguageProfile("zh", "Chinese",
                          serif=("Noto Serif SC", "Source Han Serif SC", "PingFang SC"),
                          sans=("Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei"),
                          mono=("JetBrains Mono", "SF Mono"),
                          line_height=1.6, measure_weight=1.8),
    "ja": LanguageProfile("ja", "Japanese",
                          serif=("Noto Serif JP", "Source Han Serif JP", "Hiragino Mincho ProN"),
                          sans=("Noto Sans JP", "Source Han Sans JP", "Hiragino Sans"),
                          mono=("JetBrains Mono",),
                          line_height=1.65, measure_weight=1.8),
    "ko": LanguageProfile("ko", "Korean",
                          serif=("Noto Serif KR", "Source Han Serif KR"),
                          sans=("Noto Sans KR", "Source Han Sans KR", "Apple SD Gothic Neo"),
                          mono=("JetBrains Mono",),
                          line_height=1.6, measure_weight=1.6),
    "ar": LanguageProfile("ar", "Arabic", direction="rtl",
                          serif=("Noto Naskh Arabic",),
                          sans=("Noto Sans Arabic", "Tahoma"),
                          mono=("JetBrains Mono",),
                          line_height=1.7, measure_weight=1.2),
    "he": LanguageProfile("he", "Hebrew", direction="rtl",
                          serif=("Frank Ruehl CLM",),
                          sans=("Noto Sans Hebrew", "Arial Hebrew"),
                          mono=("JetBrains Mono",),
                          line_height=1.55, measure_weight=1.1),
    "es": LanguageProfile("es", "Spanish",
                          serif=("Source Serif Pro", "Georgia"),
                          sans=("Inter", "Helvetica"),
                          mono=("JetBrains Mono",)),
    "fr": LanguageProfile("fr", "French",
                          serif=("Source Serif Pro", "Georgia"),
                          sans=("Inter", "Helvetica"),
                          mono=("JetBrains Mono",)),
    "de": LanguageProfile("de", "German",
                          serif=("Source Serif Pro", "Georgia"),
                          sans=("Inter", "Helvetica"),
                          mono=("JetBrains Mono",)),
}

DEFAULT_PROFILE = LANGUAGE_PROFILES["en"]

CJK_CHAR_WIDTH = 1.0
LATIN_CHAR_WIDTH = 0.55


@dataclass
class PreflightFinding:
    severity: str  # "info" | "warn" | "error"
    code: str
    message: str
    slide: Optional[int] = None


@dataclass
class PreflightReport:
    language: str
    findings: list[PreflightFinding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)


def _block_of(ch: str) -> str:
    """Return a coarse script bucket for a single character."""
    o = ord(ch)
    if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF:
        return "han"
    if 0x3040 <= o <= 0x30FF:
        return "kana"  # Hiragana + Katakana => Japanese
    if 0xAC00 <= o <= 0xD7AF:
        return "hangul"
    if 0x0600 <= o <= 0x06FF:
        return "arabic"
    if 0x0590 <= o <= 0x05FF:
        return "hebrew"
    if 0x0041 <= o <= 0x024F:
        return "latin"
    return "other"


def detect_language(text: str) -> str:
    """Return the best-guess ISO 639-1 code for `text` using script frequency."""
    counts: dict[str, int] = {}
    for ch in text:
        if ch.isspace() or unicodedata.category(ch).startswith("P"):
            continue
        counts[_block_of(ch)] = counts.get(_block_of(ch), 0) + 1
    if not counts:
        return "en"
    # Japanese wins if any kana present; otherwise use the dominant block.
    if counts.get("kana", 0) > 0:
        return "ja"
    dominant = max(counts.items(), key=lambda kv: kv[1])[0]
    mapping = {"han": "zh", "hangul": "ko", "arabic": "ar", "hebrew": "he", "latin": "en"}
    return mapping.get(dominant, "en")


def get_language_profile(code: str) -> LanguageProfile:
    return LANGUAGE_PROFILES.get(code, DEFAULT_PROFILE)


def apply_language_profile(theme: ThemeSpec, lang: str) -> ThemeSpec:
    """Return a copy of `theme` with font_family + i18n hints swapped for `lang`.

    ThemeSpec stores typography in `font_family` (comma-separated CSS stack)
    and per-language direction/line-height live in `design_hints`. The icon
    weight/stroke maps stay untouched.
    """
    profile = get_language_profile(lang)
    new_font = ", ".join(profile.sans) if profile.sans else theme.font_family
    extra = (
        f"\n[i18n] lang={profile.code}; direction={profile.direction}; "
        f"line_height={profile.line_height}; mono={', '.join(profile.mono) or 'inherit'}"
    )
    return replace(theme, font_family=new_font, design_hints=theme.design_hints + extra)


def _theme_direction(theme: ThemeSpec) -> str:
    """Extract direction from theme.design_hints (set by apply_language_profile)."""
    hints = theme.design_hints or ""
    if "direction=rtl" in hints:
        return "rtl"
    return "ltr"


def font_preflight(
    theme: ThemeSpec,
    texts: Iterable[str],
    *,
    lang: Optional[str] = None,
) -> PreflightReport:
    """Scan deck texts for script-vs-font mismatches and RTL handling.

    No actual font-shaping happens (would require freetype/HarfBuzz). Instead
    we apply a fast heuristic: if the deck contains characters from a script
    not covered by the theme's declared font families, raise a warning.
    """
    joined = "\n".join(texts)
    detected = detect_language(joined)
    target = lang or detected
    profile = get_language_profile(target)
    report = PreflightReport(language=target)

    if lang and lang != detected:
        report.findings.append(PreflightFinding(
            "info", "lang.mismatch",
            f"Requested language is {lang!r} but content looks like {detected!r}.",
        ))

    # Script coverage check (font_family is comma-separated CSS stack).
    body_font = (theme.font_family or "").lower()
    if profile.code in {"zh", "ja", "ko"}:
        cjk_keywords = ("noto", "source han", "pingfang", "hiragino", "ya hei", "yahei", "apple sd")
        if not any(k in body_font for k in cjk_keywords):
            report.findings.append(PreflightFinding(
                "warn", "font.cjk-coverage",
                f"Theme font_family {body_font!r} likely lacks CJK glyphs; "
                f"call apply_language_profile(theme, {profile.code!r}) before export.",
            ))
    if profile.direction == "rtl":
        if _theme_direction(theme) != "rtl":
            report.findings.append(PreflightFinding(
                "warn", "rtl.direction",
                "Detected RTL script but theme direction is LTR. "
                "Apply the language profile to flip text alignment.",
            ))

    # Combining marks heuristic — flag empty content.
    if not joined.strip():
        report.findings.append(PreflightFinding(
            "info", "content.empty",
            "No text content provided to preflight.",
        ))

    return report


def font_preflight_project(
    theme: ThemeSpec, project: Path | str, *, lang: Optional[str] = None,
) -> PreflightReport:
    """Convenience: preflight by reading a project's slide source files."""
    project = Path(project)
    texts: list[str] = []
    for src_dir_name in ("sources", "slides", "source", "src", "design"):
        d = project / src_dir_name
        if d.is_dir():
            for f in sorted(d.rglob("*.md")):
                texts.append(f.read_text(encoding="utf-8", errors="ignore"))
    notes = project / "notes.md"
    if notes.is_file():
        texts.append(notes.read_text(encoding="utf-8", errors="ignore"))
    return font_preflight(theme, texts, lang=lang)
