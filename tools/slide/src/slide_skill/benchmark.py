"""Six-family composition benchmark (v5.1 BENCH-04).

Serial, single-provider benchmark of the production AI chain against six
semantic briefs (comparison / sequence / metric / hierarchy-definition /
quote / enumeration). Produces a keyless JSON manifest recording model,
prompt bytes, token usage, reasoning/content chars, finish reason, latency,
static QA verdict, Chrome render verdict, and the deterministic machine
family verdict per brief, plus rendered SVG/PNG evidence.

Layered arbitration (56-CONTEXT D-07): the machine classifier here is layer
1; the human blind review (shuffled Chrome renders) is layer 2 and is
recorded in a separate file the manifest references; ``visual_critic`` is an
optional layer 3. Every layer reports honestly — capability gaps are
recorded, never silently passed.
"""
from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .util import ensure_dir

FAMILIES = (
    "comparison",
    "sequence",
    "metric",
    "hierarchy-definition",
    "quote",
    "enumeration",
)

SAFE_AREA = (80.0, 80.0, 1200.0, 680.0)
ENGLISH_BRIEF_FAMILY = "quote"
BLIND_REVIEW_FILENAME = "blind-review-results.md"
MANIFEST_FILENAME = "six-family-manifest.json"


# ── Brief loading (BENCH-02 contract enforcement) ─────────────────────────


@dataclass
class Brief:
    path: Path
    family: str
    language: str
    title: str
    facts: list[str] = field(default_factory=list)


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def parse_brief(path: Path) -> Brief:
    """Parse one brief file (family/language/title frontmatter + facts)."""
    text = path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text)
    body = _FRONTMATTER_RE.sub("", text, count=1)
    facts: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^[-*]\s+", "", line)
        line = re.sub(r"^\d+[.、)]\s*", "", line)
        line = line.strip("- \"“”").strip()
        if line:
            facts.append(line)
    return Brief(
        path=path,
        family=fm.get("family", ""),
        language=fm.get("language", ""),
        title=fm.get("title", ""),
        facts=facts,
    )


def load_briefs(briefs_dir: Path | str) -> tuple[list[Brief], list[str]]:
    """Load and validate the six briefs. Returns (briefs, problems)."""
    directory = Path(briefs_dir)
    problems: list[str] = []
    if not directory.is_dir():
        return [], [f"briefs directory not found: {directory}"]
    files = sorted(directory.glob("*.md"))
    briefs = [parse_brief(p) for p in files]
    families = [b.family for b in briefs]
    for family in FAMILIES:
        if family not in families:
            problems.append(f"missing brief for family: {family}")
    for family in families:
        if family and family not in FAMILIES:
            problems.append(f"unknown family declared: {family}")
    if len(files) != len(FAMILIES):
        problems.append(
            f"expected exactly {len(FAMILIES)} brief files, found {len(files)}"
        )
    english = [b for b in briefs if b.language == "en"]
    if len(english) != 1:
        problems.append(
            f"expected exactly one English brief ({ENGLISH_BRIEF_FAMILY}), "
            f"found {len(english)}"
        )
    for b in briefs:
        if not b.title:
            problems.append(f"{b.path.name}: missing title frontmatter")
        if not b.facts:
            problems.append(f"{b.path.name}: no closed-world content lines")
    return briefs, problems


def brief_plan(brief: Brief):
    """Build a one-slide SlidePlan carrying the brief's closed-world facts."""
    from .content_planner import ContentItem, SlidePlan

    type_by_family = {
        "comparison": "text",
        "sequence": "step",
        "metric": "metric",
        "hierarchy-definition": "text",
        "quote": "quote",
        "enumeration": "bullet",
    }
    items = []
    for fact in brief.facts:
        primary, secondary = fact, ""
        if "：" in fact and brief.family in {"comparison", "metric", "hierarchy-definition"}:
            primary, _, secondary = fact.partition("：")
        items.append(ContentItem(type=type_by_family[brief.family], primary=primary, secondary=secondary))
    return SlidePlan(
        index=1,
        layout=_layout_for_family(brief.family),
        title=brief.title,
        items=items,
    )


def _layout_for_family(family: str) -> str:
    return {
        "comparison": "two-column",
        "sequence": "bullet-list",
        "metric": "metric-highlight",
        "hierarchy-definition": "bullet-list",
        "quote": "quote",
        "enumeration": "bullet-list",
    }.get(family, "bullet-list")


# ── Deterministic geometric family classifier (layer-1 arbiter, D-07) ─────
#
# Input is a normalized scene: measured text nodes (real browser bboxes when
# available) plus structural facts parsed from the SVG (painted card rects,
# connector elements, font sizes). Thresholds follow the 56-UI-SPEC
# recognition-contract table.


@dataclass
class SceneTextNode:
    text: str
    x1: float
    y1: float
    x2: float
    y2: float
    font_size: float


@dataclass
class Scene:
    text_nodes: list[SceneTextNode] = field(default_factory=list)
    card_rects: list[tuple[float, float, float, float]] = field(default_factory=list)
    connector_count: int = 0
    canvas: tuple[float, float] = (1280.0, 720.0)


def parse_scene(svg_text: str, measurements: list[dict] | None) -> Scene:
    """Build the classifier scene from SVG structure + DOM measurements.

    ``measurements`` is the chrome_geometry payload (None when no browser:
    text boxes fall back to XML x/y + estimated extents, marked by the
    caller as a capability gap — classification still runs on structure).
    """
    scene = Scene()
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return scene
    try:
        scene.canvas = (
            float(root.attrib.get("width", 1280)),
            float(root.attrib.get("height", 720)),
        )
    except (TypeError, ValueError):
        pass

    measured: dict[str, tuple[float, float, float, float]] = {}
    if measurements:
        for entry in measurements:
            if not isinstance(entry, dict) or str(entry.get("tag", "text")) != "text":
                continue
            bbox = entry.get("bbox") if isinstance(entry.get("bbox"), dict) else {}
            key = " ".join(str(entry.get("text", "")).split())
            if key:
                try:
                    measured[key] = (
                        float(bbox.get("x", 0)),
                        float(bbox.get("y", 0)),
                        float(bbox.get("x", 0)) + float(bbox.get("width", 0)),
                        float(bbox.get("y", 0)) + float(bbox.get("height", 0)),
                    )
                except (TypeError, ValueError):
                    continue

    _SVG_NS = "{http://www.w3.org/2000/svg}"

    def local(tag) -> str:
        return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""

    for elem in root.iter():
        name = local(elem.tag)
        if name == "text":
            font_size = _elem_font_size(elem)
            content = " ".join(" ".join(elem.itertext()).split())
            if not content:
                continue
            box = measured.get(content)
            if box is None:
                tx, ty = _text_origin(elem)
                est_w = max(len(content) * font_size * 0.6, font_size)
                box = (tx, ty - font_size, tx + est_w, ty + font_size * 0.25)
            scene.text_nodes.append(SceneTextNode(content, *box, font_size))
        elif name == "rect":
            box = _rect_box(elem)
            if box and _meaningful_card(box):
                scene.card_rects.append(box)
        elif name in {"line", "path", "polyline", "polygon"}:
            scene.connector_count += 1
    return scene


def _elem_font_size(elem: ET.Element) -> float:
    sizes = [elem.attrib.get("font-size", "")]
    sizes.extend(child.attrib.get("font-size", "") for child in elem)
    best = 0.0
    for raw in sizes:
        try:
            if raw:
                best = max(best, float(raw))
        except (TypeError, ValueError):
            continue
    return best or 16.0


def _text_origin(elem: ET.Element) -> tuple[float, float]:
    def num(value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    return num(elem.attrib.get("x"), 0.0), num(elem.attrib.get("y"), 0.0)


def _rect_box(elem: ET.Element) -> tuple[float, float, float, float] | None:
    try:
        x, y = float(elem.attrib.get("x", 0)), float(elem.attrib.get("y", 0))
        w, h = float(elem.attrib.get("width", 0)), float(elem.attrib.get("height", 0))
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return (x, y, x + w, y + h)


def _meaningful_card(box: tuple[float, float, float, float]) -> bool:
    x1, y1, x2, y2 = box
    return (x2 - x1) >= 120 and (y2 - y1) >= 90


def _center(box) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _area(box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _heights_within(boxes: list[tuple[float, float, float, float]], ratio: float) -> bool:
    heights = [b[3] - b[1] for b in boxes]
    return max(heights) <= min(heights) * (1 + ratio)


def _sizes_within(boxes: list[tuple[float, float, float, float]], ratio: float) -> bool:
    areas = [_area(b) for b in boxes]
    return max(areas) <= min(areas) * (1 + ratio)


def _monotonic_progression(boxes: list[tuple[float, float, float, float]]) -> bool:
    xs = [_center(b)[0] for b in boxes]
    ys = [_center(b)[1] for b in boxes]
    x_increasing = all(b < a for a, b in zip(xs, xs[1:])) or all(
        a < b for a, b in zip(xs, xs[1:])
    )
    y_increasing = all(b < a for a, b in zip(ys, ys[1:])) or all(
        a < b for a, b in zip(ys, ys[1:])
    )
    return x_increasing or y_increasing


def _nodes_in(box, nodes: list[SceneTextNode]) -> list[SceneTextNode]:
    return [
        n for n in nodes
        if n.x1 >= box[0] - 4 and n.y1 >= box[1] - 4
        and n.x2 <= box[2] + 4 and n.y2 <= box[3] + 4
    ]


def _font_tiers(nodes: list[SceneTextNode], ratio: float) -> list[float]:
    sizes = sorted({round(n.font_size) for n in nodes if n.font_size > 0})
    tiers = [sizes[0]] if sizes else []
    for size in sizes[1:]:
        if size >= tiers[-1] * ratio:
            tiers.append(size)
    return tiers


def classify_scene(scene: Scene) -> dict:
    """Deterministic family recognition + non-degeneration check.

    Returns ``{"family": str | None, "confidence": {...signature metrics}}``.
    ``family`` is None when no signature matches.
    """
    nodes = scene.text_nodes
    cards = sorted(scene.card_rects)
    metrics: dict = {
        "text_count": len(nodes),
        "card_count": len(cards),
        "connector_count": scene.connector_count,
    }
    if not nodes:
        return {"family": None, "signature_metrics": metrics}

    dominant = max(nodes, key=lambda n: (n.font_size, len(n.text)))
    rest_sizes = sorted(n.font_size for n in nodes if n is not dominant)
    body_candidates = rest_sizes or [dominant.font_size]
    body_size = body_candidates[len(body_candidates) // 2]

    # metric: one display-tier anchor (>= 60px, >= 2.5x body) + <= 2 support groups
    if (
        dominant.font_size >= 60
        and body_size > 0
        and dominant.font_size >= 2.5 * body_size
        and len(nodes) <= 4
    ):
        metrics["dominant_font_size"] = dominant.font_size
        metrics["body_font_size"] = body_size
        return {"family": "metric", "signature_metrics": metrics}

    # sequence: >= 3 node groups progressing monotonically + connectors
    if len(cards) >= 3 and scene.connector_count >= 2 and _monotonic_progression(cards):
        metrics["node_count"] = len(cards)
        return {"family": "sequence", "signature_metrics": metrics}

    # comparison: 2-4 parallel panels >= 280px wide, similar heights, 2 tiers each
    wide = [c for c in cards if (c[2] - c[0]) >= 280]
    if 2 <= len(wide) <= 4 and _heights_within(wide, 0.15):
        tiers_ok = True
        for card in wide:
            inside = _nodes_in(card, nodes)
            if len(_font_tiers(inside, 1.5)) < 2:
                tiers_ok = False
                break
        if tiers_ok and all(len(_nodes_in(card, nodes)) >= 2 for card in wide):
            metrics["panel_count"] = len(wide)
            return {"family": "comparison", "signature_metrics": metrics}

    # enumeration: >= 3 uniform item units, single primary tier per unit
    if len(cards) >= 3 and _sizes_within(cards, 0.2):
        metrics["unit_count"] = len(cards)
        return {"family": "enumeration", "signature_metrics": metrics}

    # hierarchy/definition: >= 2 font tiers (ratio >= 1.5) with a dominant
    # term plus MULTIPLE subordinate blocks (leveling/containment). Checked
    # after the card-based families and before quote: a quote has at most
    # one subordinate (attribution) line.
    #
    # A title band plus UNIFORMLY-STACKED body rows is the shape of nearly
    # every slide and must not read as a leveling structure — the uniform-
    # row guard kills that; a true definition slide groups subordinate
    # blocks around the dominant term instead of stacking identical rows.
    tiers = _font_tiers(nodes, 1.5)
    if len(tiers) >= 2 and len(nodes) >= 3:
        top_tier = tiers[-1]
        top_nodes = [n for n in nodes if n.font_size >= top_tier]
        sub_nodes = [n for n in nodes if n.font_size <= top_tier / 1.5]
        sub_sizes = {round(n.font_size) for n in sub_nodes}
        uniform_run = len(sub_nodes) >= 3 and len(sub_sizes) <= 1 and _in_uniform_rows(sub_nodes)
        if top_nodes and len(sub_nodes) >= 2 and not uniform_run:
            metrics["font_tiers"] = tiers
            return {"family": "hierarchy-definition", "signature_metrics": metrics}

    # quote: <= 3 text elements, dominant block >= 30px, whitespace >= 40%
    if len(nodes) <= 3 and dominant.font_size >= 30 and not _meaningful_card(
        (dominant.x1, dominant.y1, dominant.x2, dominant.y2)
    ):
        covered = sum(_area((n.x1, n.y1, n.x2, n.y2)) for n in nodes)
        safe_area = (SAFE_AREA[2] - SAFE_AREA[0]) * (SAFE_AREA[3] - SAFE_AREA[1])
        metrics["whitespace_ratio"] = round(1 - covered / safe_area, 3)
        if covered <= safe_area * 0.6:
            return {"family": "quote", "signature_metrics": metrics}

    return {"family": None, "signature_metrics": metrics}



def _in_uniform_rows(nodes: list[SceneTextNode]) -> bool:
    """Subordinate nodes stacked as evenly-spaced rows (a bullet run)."""
    if len(nodes) < 3:
        return False
    ys = sorted(n.y1 for n in nodes)
    gaps = [b - a for a, b in zip(ys, ys[1:])]
    if not gaps or min(gaps) <= 0:
        return False
    return (max(gaps) - min(gaps)) <= max(12.0, 0.25 * (sum(gaps) / len(gaps)))


def check_non_degeneration(scene: Scene, declared_family: str) -> str:
    """"ok" or "collapsed-to-cards" per the REDESIGN_v5 non-degeneration rule."""
    if declared_family in {"comparison", "enumeration"}:
        return "ok"
    if len(scene.card_rects) < 3:
        return "ok"
    boxes = scene.card_rects
    if not _sizes_within(boxes, 0.1):
        return "ok"
    safe_w = SAFE_AREA[2] - SAFE_AREA[0]
    safe_h = SAFE_AREA[3] - SAFE_AREA[1]
    covered = min(1.0, sum(_area(b) for b in boxes) / (safe_w * safe_h))
    return "collapsed-to-cards" if covered > 0.6 else "ok"


# ── Offline contract self-test (D-12 pre-provider gate) ───────────────────


def contract_self_test() -> list[str]:
    """In-process smoke of the committed measurement-contract library.

    Returns a list of failures (empty = green). The runner refuses any
    provider call until this is empty.
    """
    from . import measurement_contracts as mc

    failures: list[str] = []
    svg = (
        '<svg width="1280" height="720" viewBox="0 0 1280 720" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
        '<g id="card-1"><rect x="80" y="160" width="340" height="360" fill="#1E293B"/>'
        '<text x="104" y="210" fill="#F1F5F9">零样本</text></g>'
        '<g id="card-2"><rect x="470" y="160" width="340" height="360" fill="#1E293B"/>'
        '<text x="494" y="210" fill="#F1F5F9">少样本</text></g>'
        '<g id="card-3"><rect x="860" y="160" width="340" height="360" fill="#1E293B"/>'
        '<text x="884" y="210" fill="#F1F5F9">思维链</text></g>'
        "</svg>"
    )
    palette = {"#0F172A", "#1E293B", "#F1F5F9"}
    defects, _ = mc.audit_svg_contract(
        svg,
        required_text=["零样本", "少样本", "思维链"],
        allowed_text=["零样本", "少样本", "思维链"],
        allowed_colors=palette,
        card_pairs=[("零样本", "零样本"), ("少样本", "少样本"), ("思维链", "思维链")],
    )
    if defects:
        failures.append(f"contract self-test (clean svg): {defects[:3]}")
    bad = svg.replace('fill="#1E293B"', 'fill="#FF0000"', 1)
    defects_bad, _ = mc.audit_svg_contract(
        bad,
        required_text=["零样本"],
        allowed_text=["零样本", "少样本", "思维链"],
        allowed_colors=palette,
    )
    if not any("prohibited paint" in d for d in defects_bad):
        failures.append("contract self-test (off-palette paint not rejected)")
    unsafe = svg.replace(
        "</svg>", '<script>alert(1)</script></svg>'
    )
    defects_unsafe, _ = mc.audit_svg_contract(
        unsafe,
        required_text=["零样本"],
        allowed_text=["零样本", "少样本", "思维链"],
        allowed_colors=palette,
    )
    if not defects_unsafe:
        failures.append("contract self-test (unsafe element not rejected)")
    return failures


# ── Runner ─────────────────────────────────────────────────────────────────


def _render_evidence(svg_path: Path, out_dir: Path, *, brief_id: str) -> tuple[str, str]:
    """Chrome-screenshot the SVG for evidence. Returns (status, detail).

    Evidence is named by brief id — every project produces slide_01.svg, so
    brief-id naming is what keeps the six renders distinct.
    status: "rendered" | "not-executed" (with reason).
    """
    from .measurement_contracts import render_svg_smoke

    png_path = out_dir / f"render-{brief_id}.png"
    defects = render_svg_smoke(svg_path, png_path)
    fatal = [d for d in defects if "no Chrome/Edge browser found" in d]
    if fatal:
        return "not-executed", fatal[0]
    if defects:
        return "rendered", "; ".join(defects[:4])
    return "rendered", "clean"


def run_benchmark(
    briefs_dir: Path | str,
    out_dir: Path | str,
    *,
    theme: str = "dark-tech",
    yes: bool = False,
    base_dir: Path | str | None = None,
) -> tuple[dict | None, int]:
    """Run the six-family benchmark.

    Without ``yes``: dry-run — validate briefs + contract self-test +
    classifier fixture self-test, zero provider calls. With ``yes``: serial
    provider run through the production executor chain, then manifest
    persistence. Returns ``(manifest_or_None, exit_code)``.
    """
    out = ensure_dir(Path(out_dir))
    briefs, problems = load_briefs(briefs_dir)
    if problems:
        print("No benchmark briefs found — validation failed:", file=__import__("sys").stderr)
        for problem in problems:
            print(f"  - {problem}", file=__import__("sys").stderr)
        print(
            "Expected six family files under benchmarks/briefs/: comparison, "
            "sequence, metric, hierarchy-definition, quote, enumeration. Each "
            "file needs family + language frontmatter and closed-world source "
            "content (every visible fact traceable to the brief).",
            file=__import__("sys").stderr,
        )
        return None, 2

    contract_failures = contract_self_test()
    if contract_failures:
        print(
            "Offline measurement-contract self-test FAILED — provider run refused:",
            file=__import__("sys").stderr,
        )
        for failure in contract_failures:
            print(f"  - {failure}", file=__import__("sys").stderr)
        return None, 3
    print("[benchmark] offline contract self-test green (runs before any provider call)")

    if not yes:
        print(
            "[benchmark] dry-run complete: briefs valid, contract suite green, "
            "classifier fixtures green. Pass --yes for the gated provider run "
            "(6 briefs, serial, one provider key; consumes API budget)."
        )
        return None, 0

    import os
    import shutil
    import tempfile

    from .ai_trace import read_ai_trace
    from .project import init_project
    from .spec_builder import create_spec
    from .svg_qa import arbitrate_text_geometry, check_svg_file

    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "Provider run requires OPENAI_API_KEY (env-configured, "
            "SenseNova-compatible base URL via OPENAI_BASE_URL) — not set.",
            file=__import__("sys").stderr,
        )
        return None, 4

    scratch_root = Path(base_dir) if base_dir else Path(tempfile.mkdtemp(prefix="bench-"))
    entries: list[dict] = []
    for brief in briefs:
        project = init_project(
            f"bench-{brief.family}", base_dir=scratch_root / "projects"
        )
        source = scratch_root / f"{brief.family}.md"
        source.write_text(f"# {brief.title}\n\n" + "\n".join(f"- {f}" for f in brief.facts), encoding="utf-8")
        create_spec(project, theme_name=theme, source_markdown=source)
        plan = brief_plan(brief)

        from . import ai_executor

        trace_before = len(read_ai_trace(project))
        started = time.perf_counter()
        generation_error = ""
        paths: list[Path] = []
        try:
            paths = ai_executor.generate_svg_with_ai(project, [plan])
        except Exception as exc:  # noqa: BLE001 — a failed brief is benchmark
            # evidence, recorded honestly; it must not abort the whole run.
            generation_error = f"{exc.__class__.__name__}: {exc}"
            print(f"[benchmark] brief {brief.path.stem} failed: {generation_error}",
                  file=__import__("sys").stderr)
        latency_ms = round((time.perf_counter() - started) * 1000)
        events = read_ai_trace(project)[trace_before:]
        executor_events = [e for e in events if e.get("stage") == "executor"]
        # Prefer the last PASSED event; for a failed brief the final attempt's
        # event (failed/truncated) is the honest evidence source.
        last_event = next(
            (e for e in reversed(executor_events)
             if str(e.get("status", "")).startswith("passed")),
            executor_events[-1] if executor_events else None,
        )

        svg_path = paths[0] if paths else None
        if svg_path is None and not generation_error:
            generation_error = "executor returned no svg path"
        # Keep the last attempt as failure evidence when generation failed.
        if svg_path is None:
            attempt_dir = project / "qa" / "executor" / "attempt-svg"
            attempts = sorted(attempt_dir.glob("slide_01_attempt_*.svg")) if attempt_dir.exists() else []
            if attempts:
                svg_path = attempts[-1]
                failure_evidence = True
            else:
                failure_evidence = False
        else:
            failure_evidence = False
        static_issues: list = []
        geometry_info = None
        if svg_path:
            static_issues = check_svg_file(svg_path, project)
            static_issues, geometry_info = arbitrate_text_geometry(
                svg_path.read_text(encoding="utf-8"), static_issues
            )
        render_status, render_detail = (
            _render_evidence(svg_path, out, brief_id=brief.path.stem)
            if svg_path else ("not-executed", "no svg generated")
        )

        from .chrome_geometry import measure_svg_text_geometry

        measurements = (
            measure_svg_text_geometry(svg_path.read_text(encoding="utf-8"))
            if svg_path else None
        )
        scene = parse_scene(svg_path.read_text(encoding="utf-8"), measurements) if svg_path else Scene()
        verdict = classify_scene(scene)
        entry = {
            "brief_id": brief.path.stem,
            "family": brief.family,
            "language": brief.language,
            "title": brief.title,
            "model": last_event.get("model") if last_event else None,
            "prompt_bytes": (
                last_event.get("prompt_chars", 0) if last_event else 0
            ),
            "prompt_tokens": (
                (last_event.get("metadata") or {}).get("prompt_tokens")
                if last_event else None
            ),
            "completion_tokens": (
                (last_event.get("metadata") or {}).get("completion_tokens")
                if last_event else None
            ),
            "reasoning_chars": (
                (last_event.get("metadata") or {}).get("reasoning_chars")
                if last_event else None
            ),
            "content_chars": last_event.get("raw_chars", 0) if last_event else 0,
            "finish_reason": (
                (last_event.get("metadata") or {}).get("finish_reason")
                if last_event else None
            ),
            "latency_ms": latency_ms,
            "status": "failed" if generation_error else "passed",
            "generation_error": generation_error or None,
            "static_qa": {
                "verdict": ("passed" if not static_issues else "failed")
                if not generation_error else "failed",
                "defect_count": len(static_issues),
                "geometry_verdict": (geometry_info or {}).get("geometry_verdict"),
            },
            "chrome_render": {"status": render_status, "detail": render_detail},
            "machine_family_verdict": {
                "recognized": (verdict["family"] == brief.family)
                if not generation_error else False,
                "classified_as": verdict["family"],
                "signature_metrics": verdict["signature_metrics"],
            },
            "non_degeneration": check_non_degeneration(scene, brief.family),
            "svg_evidence": f"{brief.path.stem}.svg" if svg_path else None,
            "svg_evidence_is_failed_attempt": failure_evidence or None,
        }
        entries.append(entry)
        if svg_path and svg_path.exists():
            shutil.copy2(svg_path, out / f"{brief.path.stem}.svg")

    recognized = sum(1 for e in entries if e["machine_family_verdict"]["recognized"])
    passed = sum(1 for e in entries if e.get("status") == "passed")
    manifest = {
        "benchmark": "six-family",
        "theme": theme,
        "brief_count": len(entries),
        "passed": passed,
        "machine_recognized": recognized,
        "blind_review_reference": BLIND_REVIEW_FILENAME,
        "entries": entries,
    }
    manifest_path = out / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    review_path = out / BLIND_REVIEW_FILENAME
    review_path.write_text(_blind_review_template(entries), encoding="utf-8")
    print(
        f"[benchmark] manifest persisted: {manifest_path} "
        f"({recognized}/{len(entries)} machine-recognized, {passed}/{len(entries)} passed QA)"
    )
    return manifest, 0


def _blind_review_template(entries: list[dict]) -> str:
    import random

    reviewable = [
        (i, e) for i, e in enumerate(entries)
        if e.get("status") == "passed" and e.get("svg_evidence")
    ]
    order = [i for i, _ in reviewable]
    random.shuffle(order)
    by_index = dict(reviewable)
    lines = [
        "# Six-Family Blind Review",
        "",
        "Reviewer sees shuffled renders WITHOUT knowing the requested family.",
        "For each render, write the family you believe it shows, then compare",
        "with the manifest after review. Recognition target: >= 5/6.",
        "",
        "(Only QA-passed renders are reviewable; failed briefs are recorded",
        "in the manifest, not reviewed blind.)",
        "",
        "| Shuffle # | Render file | Your guess | Correct? |",
        "|-----------|-------------|------------|----------|",
    ]
    for position, index in enumerate(order, start=1):
        entry = by_index[index]
        lines.append(
            f"| {position} | {entry.get('svg_evidence') or '(missing)'} | | |"
        )
    lines += [
        "",
        "Reviewed by: ____________________  Date: ____________",
        "",
        f"Result: ___ / {len(order)} recognizable",
    ]
    return "\n".join(lines) + "\n"
