"""Snapshot comparison engine for cross-render visual QA."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class SlideDiff:
    slide_name: str
    score: float  # 0-100
    verdict: str  # PASS or FAIL


@dataclass
class DeckDiff:
    slides: list[SlideDiff]
    overall_score: float
    verdict: str
    threshold: float


def compare_snapshots(
    reference_dir: Path | str,
    actual_dir: Path | str,
    threshold: float = 95.0,
    pixel_tolerance: int = 10,
) -> DeckDiff:
    """Compare two sets of per-slide PNGs and produce similarity scores.

    Args:
        reference_dir: Directory with reference PNGs (slide-01.png, etc.)
        actual_dir: Directory with actual PNGs to compare
        threshold: Minimum similarity score (0-100) for PASS
        pixel_tolerance: Max per-channel difference (0-255) to count as matching

    Returns:
        DeckDiff with per-slide scores and overall verdict.
    """
    import numpy as np
    from PIL import Image

    ref_dir = Path(reference_dir)
    act_dir = Path(actual_dir)

    ref_files = sorted(ref_dir.glob("slide-*.png"))
    act_files = sorted(act_dir.glob("slide-*.png"))

    if not ref_files:
        return DeckDiff(slides=[], overall_score=0.0, verdict="FAIL", threshold=threshold)

    slides: list[SlideDiff] = []
    ref_names = {f.name for f in ref_files}
    act_map = {f.name: f for f in act_files}

    for ref_file in ref_files:
        act_file = act_map.get(ref_file.name)
        if not act_file or not act_file.exists():
            slides.append(SlideDiff(slide_name=ref_file.name, score=0.0, verdict="FAIL"))
            continue

        ref_img = Image.open(ref_file).convert("RGB")
        act_img = Image.open(act_file).convert("RGB")

        if ref_img.size != act_img.size:
            act_img = act_img.resize(ref_img.size, Image.LANCZOS)

        ref_arr = np.array(ref_img, dtype=np.int16)
        act_arr = np.array(act_img, dtype=np.int16)

        diff = np.abs(ref_arr - act_arr)
        matching = np.all(diff <= pixel_tolerance, axis=2)
        score = float(np.mean(matching)) * 100.0

        slides.append(SlideDiff(
            slide_name=ref_file.name,
            score=round(score, 2),
            verdict="PASS" if score >= threshold else "FAIL",
        ))

    # Add missing slides from actual that aren't in reference
    for act_file in act_files:
        if act_file.name not in ref_names:
            slides.append(SlideDiff(slide_name=act_file.name, score=0.0, verdict="FAIL"))

    overall = sum(s.score for s in slides) / len(slides) if slides else 0.0
    verdict = "PASS" if overall >= threshold and all(s.verdict == "PASS" for s in slides) else "FAIL"

    return DeckDiff(
        slides=slides,
        overall_score=round(overall, 2),
        verdict=verdict,
        threshold=threshold,
    )


def write_snapshot_report(deck_diff: DeckDiff, output_path: Path | str) -> Path:
    """Write a markdown QA report from a DeckDiff."""
    out = Path(output_path)
    lines = [
        "# Snapshot QA Report",
        "",
        f"status: {deck_diff.verdict.lower()}",
        f"threshold: {deck_diff.threshold}%",
        f"overall_score: {deck_diff.overall_score}%",
        "",
        "## Per-Slide Scores",
        "",
        "| Slide | Score | Verdict |",
        "|-------|-------|---------|",
    ]
    for s in deck_diff.slides:
        lines.append(f"| {s.slide_name} | {s.score:.2f}% | {s.verdict} |")
    lines.append("")
    lines.append(f"**Overall:** {deck_diff.overall_score:.2f}% — {deck_diff.verdict}")
    lines.append("")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
