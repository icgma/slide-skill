"""Timed rehearsal: estimate presentation duration from speaker notes."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

ZH_CHARS_PER_MINUTE = 260
EN_WORDS_PER_MINUTE = 140


@dataclass
class SlideTiming:
    slide_number: int
    char_count: int
    estimated_seconds: float
    note_preview: str


@dataclass
class RehearsalReport:
    total_slides: int
    slides_with_notes: int
    slides_silent: list[int]
    timings: list[SlideTiming]
    total_seconds: float
    time_limit_seconds: float | None
    over_limit: bool
    over_by_seconds: float | None
    fastest_slide: SlideTiming | None
    slowest_slide: SlideTiming | None


def _is_cjk(char: str) -> bool:
    cp = ord(char)
    return (
        (0x4E00 <= cp <= 0x9FFF)
        or (0x3400 <= cp <= 0x4DBF)
        or (0x3000 <= cp <= 0x303F)
        or (0xFF00 <= cp <= 0xFFEF)
        or (0x2E80 <= cp <= 0x2FDF)
        or (0xF900 <= cp <= 0xFAFF)
    )


def _detect_language_weight(text: str) -> float:
    """Return ratio of CJK characters in text (0.0 = all Latin, 1.0 = all CJK)."""
    if not text:
        return 0.5
    cjk = sum(1 for c in text if _is_cjk(c))
    # In Python, Chinese characters return True for isalpha().
    # We should only count ASCII letters as 'alpha' here for the weight calculation.
    import re
    alpha = len(re.findall(r"[a-zA-Z]", text))
    if alpha == 0 and cjk == 0:
        return 0.5
    return cjk / (cjk + alpha) if (cjk + alpha) > 0 else 0.5


def estimate_speaking_time(text: str) -> float:
    """Estimate speaking time in seconds for a piece of text."""
    if not text.strip():
        return 0.0

    clean = re.sub(r"\s+", " ", text.strip())
    cjk_ratio = _detect_language_weight(clean)

    cjk_chars = sum(1 for c in clean if _is_cjk(c))
    latin_words = len(re.findall(r"[a-zA-Z]+", clean))

    cjk_time = cjk_chars / ZH_CHARS_PER_MINUTE * 60
    latin_time = latin_words / EN_WORDS_PER_MINUTE * 60

    return cjk_time * cjk_ratio + latin_time * (1 - cjk_ratio)


def rehearse_project(
    project_path: Path | str,
    time_limit_minutes: float | None = None,
) -> RehearsalReport:
    """Analyze speaker notes and produce a timing report."""
    from .exporter import _read_project_notes
    from .project import load_project

    project = Path(project_path)
    meta = load_project(project)

    if time_limit_minutes is None:
        comp = meta.get("competition")
        if comp and isinstance(comp, dict):
            time_limit_minutes = comp.get("time_limit_minutes")

    svg_dir = project / "svg_final"
    if not svg_dir.exists():
        svg_dir = project / "svg_output"
    svg_files = sorted(svg_dir.glob("slide_*.svg")) if svg_dir.exists() else []
    slide_count = len(svg_files) if svg_files else len(list((project / "notes").glob("slide*.md"))) if (project / "notes").exists() else 0

    if slide_count == 0:
        slide_count = 1

    notes = _read_project_notes(project, slide_count)

    timings: list[SlideTiming] = []
    silent: list[int] = []

    for idx, note_text in enumerate(notes, start=1):
        text = note_text.strip()
        seconds = estimate_speaking_time(text)
        preview = (text[:80] + "...") if len(text) > 80 else text
        timings.append(SlideTiming(
            slide_number=idx,
            char_count=len(text),
            estimated_seconds=round(seconds, 1),
            note_preview=preview,
        ))
        if not text:
            silent.append(idx)

    total = sum(t.estimated_seconds for t in timings)
    fastest = min((t for t in timings if t.estimated_seconds > 0), key=lambda t: t.estimated_seconds, default=None)
    slowest = max(timings, key=lambda t: t.estimated_seconds)

    limit_sec = time_limit_minutes * 60 if time_limit_minutes else None
    over = total > limit_sec if limit_sec else False
    over_by = (total - limit_sec) if over else None

    return RehearsalReport(
        total_slides=len(timings),
        slides_with_notes=len(timings) - len(silent),
        slides_silent=silent,
        timings=timings,
        total_seconds=round(total, 1),
        time_limit_seconds=round(limit_sec, 1) if limit_sec else None,
        over_limit=over,
        over_by_seconds=round(over_by, 1) if over_by else None,
        fastest_slide=fastest,
        slowest_slide=slowest,
    )


def format_rehearsal_report(report: RehearsalReport) -> str:
    """Format a rehearsal report as human-readable text."""
    lines = [
        "# Rehearsal Report",
        "",
        f"Total slides: {report.total_slides} | With notes: {report.slides_with_notes} | Silent: {len(report.slides_silent)}",
    ]

    total_min = report.total_seconds / 60
    lines.append(f"Estimated time: {_fmt_time(report.total_seconds)} ({total_min:.1f} min)")

    if report.time_limit_seconds:
        limit_min = report.time_limit_seconds / 60
        lines.append(f"Time limit: {_fmt_time(report.time_limit_seconds)} ({limit_min:.0f} min)")
        if report.over_limit:
            lines.append(f"!! 超时 {_fmt_time(report.over_by_seconds)}")
        else:
            buffer = report.time_limit_seconds - report.total_seconds
            lines.append(f"OK 富余 {_fmt_time(buffer)}")

    lines.append("")
    lines.append(f"{'Slide':<8} {'Time':<10} {'Chars':<6} {'Note Preview'}")
    lines.append("-" * 70)

    for t in report.timings:
        warn = " !!" if t.estimated_seconds > 90 else ""
        preview = t.note_preview or "(no notes)"
        lines.append(f"S{t.slide_number:<5} {_fmt_time(t.estimated_seconds):<10} {t.char_count:<6} {preview}{warn}")

    if report.slides_silent:
        lines.append("")
        lines.append(f"Silent slides: {', '.join('S' + str(n) for n in report.slides_silent)}")

    if report.over_limit and report.slowest_slide:
        lines.append("")
        lines.append(f"Tips: consider trimming S{report.slowest_slide.slide_number} ({_fmt_time(report.slowest_slide.estimated_seconds)}) or merge short slides")

    lines.append("")
    return "\n".join(lines)


def _fmt_time(seconds: float) -> str:
    if seconds is None:
        return "-"
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"
