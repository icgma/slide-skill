"""QA checks for slide projects."""

from __future__ import annotations

import re
from pathlib import Path

from .exporter import pptx_text, validate_pptx
from .project import load_project
from .svg_pipeline import check_project_svg
from .util import ensure_dir

PLACEHOLDER_RE = re.compile(r"\b(lorem|ipsum|placeholder|xxxx|todo|sample text)\b", re.IGNORECASE)
VISUAL_REVIEW = "VISUAL-REVIEW.md"
FIX_VERIFY = "FIX-VERIFY.md"


def run_snapshot_qa(
    pptx_path: Path | str,
    reference_dir: Path | str,
    project_path: Path | str,
    threshold: float = 95.0,
    dpi: int = 150,
) -> tuple[bool, Path]:
    """Run snapshot rendering and pixel-diff comparison against reference.

    Returns (passed, report_path).
    """
    from .render import snapshot_pptx
    from .snapshot_diff import compare_snapshots, write_snapshot_report

    project = Path(project_path)
    qa_dir = ensure_dir(project / "qa")
    actual_dir = ensure_dir(qa_dir / "snapshots")

    snapshot_pptx(pptx_path, actual_dir, dpi=dpi)
    deck_diff = compare_snapshots(reference_dir, actual_dir, threshold=threshold)
    report = write_snapshot_report(deck_diff, qa_dir / "SNAPSHOT-QA.md")
    return deck_diff.verdict == "PASS", report


def run_qa(
    project_path: Path | str,
    pptx_path: Path | str | None = None,
    require_visual: bool = False,
    require_fix_verify: bool = False,
) -> tuple[bool, Path]:
    project = Path(project_path)
    load_project(project)
    if pptx_path is None:
        exports = sorted((project / "exports").glob("*.pptx"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not exports:
            raise FileNotFoundError("No exported PPTX found. Run export first.")
        deck = exports[0]
    else:
        deck = Path(pptx_path)

    ok_pptx, pptx_errors = validate_pptx(deck)
    ok_svg, svg_issues = check_project_svg(project, stage="final")
    text = pptx_text(deck)
    placeholders = PLACEHOLDER_RE.findall(text)
    visual_ok, visual_lines = _visual_evidence(project, require_visual)
    fix_ok, fix_lines = _fix_verify_evidence(project, require_fix_verify)

    ok = ok_pptx and ok_svg and not placeholders and visual_ok and fix_ok
    complete_evidence = _has_visual_evidence(project) and _has_fix_verify(project)
    status = "passed" if ok and complete_evidence else "automated-passed" if ok else "failed"
    report = ensure_dir(project / "qa") / "QA.md"
    lines = [
        "# Slide Skill QA",
        "",
        f"status: {status}",
        f"deck: {deck}",
        "",
        "## PPTX Package",
    ]
    lines.extend(["- Passed"] if ok_pptx else [f"- {err}" for err in pptx_errors])
    lines.append("")
    lines.append("## SVG Gate")
    if svg_issues:
        lines.extend(f"- **{issue.level}** `{issue.file}`: {issue.message}" for issue in svg_issues)
    else:
        lines.append("- Passed")
    lines.append("")
    lines.append("## Placeholder Scan")
    if placeholders:
        lines.append(f"- Found placeholders: {', '.join(sorted(set(placeholders)))}")
    else:
        lines.append("- No placeholder patterns found")
    lines.append("")
    lines.append("## Visual QA")
    lines.extend(visual_lines)
    lines.append("")
    lines.append("## Fix And Verify")
    lines.extend(fix_lines)
    lines.append("")
    lines.append("## Extracted Text")
    lines.append("```text")
    lines.append(text.strip())
    lines.append("```")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ok, report


def _visual_evidence(project: Path, required: bool) -> tuple[bool, list[str]]:
    rendered = _rendered_images(project)
    review = project / "qa" / VISUAL_REVIEW
    if rendered and review.exists():
        return True, [f"- Passed with {len(rendered)} rendered image(s) and `{review}`."]
    missing: list[str] = []
    if not rendered:
        missing.append("rendered slide images in `qa/rendered/`")
    if not review.exists():
        missing.append(f"`qa/{VISUAL_REVIEW}`")
    prefix = "- Missing required" if required else "- Not required for automated QA; missing"
    return (not required), [f"{prefix}: {', '.join(missing)}."]


def _fix_verify_evidence(project: Path, required: bool) -> tuple[bool, list[str]]:
    evidence = project / "qa" / FIX_VERIFY
    if evidence.exists():
        return True, [f"- Passed with `{evidence}`."]
    prefix = "- Missing required" if required else "- Not required for automated QA; missing"
    return (not required), [f"{prefix}: `qa/{FIX_VERIFY}`."]


def _has_visual_evidence(project: Path) -> bool:
    return bool(_rendered_images(project)) and (project / "qa" / VISUAL_REVIEW).exists()


def _has_fix_verify(project: Path) -> bool:
    return (project / "qa" / FIX_VERIFY).exists()


def _rendered_images(project: Path) -> list[Path]:
    rendered = project / "qa" / "rendered"
    if not rendered.exists():
        return []
    return sorted(
        path
        for path in rendered.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
