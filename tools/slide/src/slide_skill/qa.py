"""QA checks for slide projects."""

from __future__ import annotations

import re
import json
from pathlib import Path

from .exporter import pptx_text, validate_pptx
from .project import load_project
from .svg_qa import check_project_svg
from .util import ensure_dir

PLACEHOLDER_RE = re.compile(r"\b(lorem|ipsum|placeholder|xxxx|todo|sample text)\b", re.IGNORECASE)
VISUAL_REVIEW = "VISUAL-REVIEW.md"
VISUAL_FEEDBACK = "visual-feedback.json"
FIX_VERIFY = "FIX-VERIFY.md"
_VISUAL_SEVERITY_RANK = {"ok": 0, "minor": 1, "major": 2, "critical": 3}


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
    strict_svg_quality: bool = False,
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
    ok_svg, svg_issues = check_project_svg(project, stage="final", quality=strict_svg_quality)
    svg_blocking = [
        issue for issue in svg_issues
        if issue.level == "error" or (strict_svg_quality and issue.level == "warning")
    ]
    text = pptx_text(deck)
    placeholders = PLACEHOLDER_RE.findall(text)
    visual_ok, visual_lines = _visual_evidence(project, require_visual)
    fix_ok, fix_lines = _fix_verify_evidence(project, require_fix_verify)

    ok = ok_pptx and ok_svg and not svg_blocking and not placeholders and visual_ok and fix_ok
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
        feedback_ok, feedback_lines = _visual_feedback_evidence(project)
        return feedback_ok, [f"- Passed with {len(rendered)} rendered image(s) and `{review}`."] + feedback_lines
    missing: list[str] = []
    if not rendered:
        missing.append("rendered slide images in `qa/rendered/`")
    if not review.exists():
        missing.append(f"`qa/{VISUAL_REVIEW}`")
    prefix = "- Missing required" if required else "- Not required for automated QA; missing"
    return (not required), [f"{prefix}: {', '.join(missing)}."]


def _visual_feedback_evidence(project: Path) -> tuple[bool, list[str]]:
    feedback = project / "qa" / VISUAL_FEEDBACK
    if not feedback.exists():
        return True, []
    try:
        payload = json.loads(feedback.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"- Failed: `qa/{VISUAL_FEEDBACK}` is invalid JSON ({exc.msg})."]
    severities = []
    for item in payload.get("slides", []):
        if isinstance(item, dict):
            severities.append(str(item.get("severity", "minor")).lower())
    max_severity = _max_visual_feedback_severity(severities)
    if not max_severity:
        return True, [f"- AI visual feedback found in `qa/{VISUAL_FEEDBACK}` but no slide severities were recorded."]
    line = f"- AI visual feedback max severity: {max_severity}."
    if _VISUAL_SEVERITY_RANK.get(max_severity, 1) >= _VISUAL_SEVERITY_RANK["major"]:
        return False, [f"{line} Run `slide-skill repair-feedback` or `slide-skill iterate-ai` before final QA."]
    return True, [line]


def _max_visual_feedback_severity(severities: list[str]) -> str:
    highest = ""
    highest_rank = -1
    for severity in severities:
        rank = _VISUAL_SEVERITY_RANK.get(severity, _VISUAL_SEVERITY_RANK["minor"])
        if rank > highest_rank:
            highest = severity if severity in _VISUAL_SEVERITY_RANK else "minor"
            highest_rank = rank
    return highest


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
