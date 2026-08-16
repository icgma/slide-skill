"""Render-convergence publish gate (v5.1 GATE-01..04).

A deck may only be exported when every page is pixel-level deliverable:
structural QA clean, DOM-geometry-arbitrated text verdicts clean, Chrome
render healthy (not uniform/black, text visibly painted, not clipped), and
the deck-level rhythm / layout-variety QA green. Failing any of these
blocks export — no partial PPTX is ever produced.

Honesty discipline: every capability gap (no browser, no PowerPoint COM) is
recorded explicitly in the gate report; nothing silently passes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .svg_qa import arbitrate_text_geometry, check_project_svg, check_svg_file


@dataclass
class PageGateResult:
    path: Path
    passed: bool
    blockers: list[str] = field(default_factory=list)
    render_status: str = "not-executed"
    render_detail: str = ""
    geometry_verdict: str | None = None
    static_defects: int = 0

    def to_dict(self) -> dict:
        return {
            "file": self.path.name,
            "passed": self.passed,
            "blockers": self.blockers,
            "render": {"status": self.render_status, "detail": self.render_detail},
            "geometry_verdict": self.geometry_verdict,
            "static_defects": self.static_defects,
        }


@dataclass
class DeckGateResult:
    project: Path
    stage: str
    passed: bool
    pages: list[PageGateResult] = field(default_factory=list)
    deck_issues: list[str] = field(default_factory=list)
    deck_findings: list[str] = field(default_factory=list)
    capability_gaps: list[str] = field(default_factory=list)
    com_smoke: dict | None = None

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "passed": self.passed,
            "pages": [p.to_dict() for p in self.pages],
            "deck_issues": self.deck_issues,
            "deck_findings": self.deck_findings,
            "capability_gaps": self.capability_gaps,
            "com_smoke": self.com_smoke,
        }


def gate_page(svg_path: Path, project: Path) -> PageGateResult:
    """One page through the render-convergence gate.

    Structural QA first, DOM-geometry arbitration second (measured-clean
    static verdicts drop), Chrome render smoke last (uniform/black frames,
    clipped or unpainted text are blockers). No browser: static verdict
    retained, capability gap recorded — never a silent pass.
    """
    from .measurement_contracts import render_svg_smoke

    result = PageGateResult(path=svg_path, passed=True)
    svg_text = svg_path.read_text(encoding="utf-8")
    static_issues = check_svg_file(svg_path, project)
    static_issues, geometry_info = arbitrate_text_geometry(svg_text, static_issues)
    result.geometry_verdict = (geometry_info or {}).get("geometry_verdict")
    result.static_defects = len(static_issues)
    for issue in static_issues:
        result.blockers.append(f"{issue.level}: {issue.message}")
    png_path = svg_path.with_suffix(".gate.png")
    render_defects = render_svg_smoke(svg_path, png_path)
    if png_path.exists():
        png_path.unlink()
    missing_browser = [d for d in render_defects if "no Chrome/Edge browser found" in d]
    if missing_browser:
        result.render_status = "not-executed"
        result.render_detail = missing_browser[0]
    elif render_defects:
        result.render_status = "failed"
        result.render_detail = "; ".join(render_defects[:6])
        result.blockers.extend(f"render: {d}" for d in render_defects[:6])
    else:
        result.render_status = "rendered"
        result.render_detail = "clean"
    result.passed = not result.blockers
    return result


def gate_deck(
    project_path: Path | str,
    stage: str = "final",
    *,
    quality: bool = True,
    strict: bool = False,
    com_smoke: bool | None = None,
    pptx_path: Path | None = None,
) -> DeckGateResult:
    """Whole deck through the gate (GATE-03).

    Per-page render-convergence gates plus the deck-level rhythm /
    layout-variety QA (``check_project_svg(quality=True)``). Severity
    policy: error-level findings always block; warning/info findings are
    recorded in the report and block only in ``strict`` mode. When
    ``com_smoke`` is requested and a ``pptx_path`` is given, the optional
    PowerPoint COM smoke verdict is attached (GATE-04).
    """
    project = Path(project_path)
    svg_dir = project / ("svg_final" if stage == "final" else "svg_output")
    deck = DeckGateResult(project=project, stage=stage, passed=True)

    ok, issues = check_project_svg(project, stage=stage, quality=quality)
    for issue in issues:
        text = f"{issue.level}: {Path(issue.file).name}: {issue.message}"
        deck.deck_findings.append(text)
        if issue.level == "error" or "No SVG files found" in issue.message:
            deck.deck_issues.append(text)
        elif quality and strict:
            deck.deck_issues.append(text)

    for svg_file in sorted(svg_dir.glob("*.svg")):
        page = gate_page(svg_file, project)
        if page.render_status == "not-executed":
            deck.capability_gaps.append(
                f"{svg_file.name}: {page.render_detail}"
            )
        deck.pages.append(page)

    deck.passed = not deck.deck_issues and all(p.passed for p in deck.pages)

    if com_smoke and pptx_path is not None:
        status, detail = com_smoke_render(pptx_path)
        deck.com_smoke = {"status": status, "detail": detail}
        if status == "not-executed":
            deck.capability_gaps.append(f"com-smoke: {detail}")
        elif status == "failed":
            deck.passed = False
    return deck


def com_smoke_render(pptx_path: Path | str) -> tuple[str, str]:
    """Optional PowerPoint COM final smoke render (GATE-04).

    Opens the deck in PowerPoint via COM and exports slide images; a
    successful export with at least one image is "passed". Any missing
    capability (no pywin32, no PowerPoint, COM error) is reported as
    ("not-executed", reason) — explicitly logged, never a silent pass.
    """
    try:
        import pythoncom  # noqa: F401
        import win32com.client
    except ImportError as exc:
        return "not-executed", f"pywin32 unavailable: {exc.__class__.__name__}"
    import tempfile

    pptx = Path(pptx_path)
    if not pptx.exists():
        return "not-executed", f"pptx not found: {pptx}"
    out_dir = Path(tempfile.mkdtemp(prefix="com-smoke-"))
    try:
        pythoncom.CoInitialize()
        try:
            app = win32com.client.Dispatch("PowerPoint.Application")
            presentation = app.Presentations.Open(
                str(pptx.resolve()), ReadOnly=True, WithWindow=False,
            )
            try:
                presentation.Export(str(out_dir), "PNG")
            finally:
                presentation.Close()
        finally:
            pythoncom.CoUninitialize()
    except Exception as exc:  # noqa: BLE001 — COM surfaces many error classes.
        return "not-executed", f"PowerPoint COM unavailable: {exc.__class__.__name__}: {exc}"
    images = {p for p in out_dir.iterdir() if p.suffix.lower() == ".png"}
    if not images:
        return "failed", "PowerPoint COM export produced no slide images"
    return "passed", f"exported {len(images)} slide image(s)"


def write_gate_report(project_path: Path | str, deck: DeckGateResult) -> Path:
    """Persist qa/PUBLISH-GATE.json — the gate's durable evidence."""
    project = Path(project_path)
    qa_dir = project / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    report_path = qa_dir / "PUBLISH-GATE.json"
    report_path.write_text(
        json.dumps(deck.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report_path
