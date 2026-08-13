"""SVG Quality Assurance — structural integrity AND design quality.

Phase 44 (v4.0): Extends the original structural checks with five
design-quality checkers that assess visual consistency against the
project's spec lock.

Issue levels:
- ``error``   — must fix; blocks export
- ``warning`` — should fix; may cause issues
- ``info``    — consider; quality improvement
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .text_wrap import _estimate_text_bounds, _char_width
from .util import ensure_dir

SUPPORTED_DRAWABLE_TAGS = {
    "rect", "circle", "ellipse", "line", "text", "tspan", "image",
    "path", "polygon", "polyline", "g",
    "defs", "linearGradient", "radialGradient", "stop",
    "filter", "feGaussianBlur", "feDropShadow", "feOffset", "feFlood", "feComposite",
    "feMerge", "feMergeNode", "clipPath", "mask", "pattern", "use",
    "title", "desc",
}

# Only ban security-dangerous and animation tags
BANNED_TAGS = {
    "script", "foreignObject", "iframe",
    "animate", "animateTransform", "set", "animateMotion",
}

# Only ban DOM event-handler attributes
BANNED_ATTRS = {
    "onclick", "onload", "onmouseover", "onmouseout",
    "onmousedown", "onmouseup", "onfocus", "onblur",
    "onchange", "onerror", "onsubmit",
}

# ── PPT-safe fonts (from shared-standards.md §6.5) ──────────────────
PPT_SAFE_FONTS = {
    # Western
    "aptos", "arial", "calibri", "cambria", "consolas",
    "courier new", "georgia", "segoe ui", "tahoma",
    "times new roman", "trebuchet ms", "verdana",
    "helvetica", "helvetica neue", "roboto", "inter",
    "open sans", "poppins", "palatino", "playfair display",
    # CJK
    "microsoft yahei", "simsun", "simhei", "kaiti", "fangsong",
    "noto sans sc", "noto sans tc", "noto sans jp", "noto sans kr",
    "source han sans sc", "noto serif sc", "source han serif sc",
    "pingfang sc", "songti sc", "stsong", "stkaiti",
    # Monospace
    "jetbrains mono", "fira code", "cascadia mono",
    "source code pro",
    # Generic families (always safe)
    "sans-serif", "serif", "monospace", "cursive",
}


@dataclass
class SvgIssue:
    level: str   # "error", "warning", "info"
    file: str
    message: str


# =====================================================================
# Public API
# =====================================================================

def check_project_svg(
    project_path: Path | str,
    stage: str = "output",
    *,
    quality: bool = False,
) -> tuple[bool, list[SvgIssue]]:
    """Run structural checks on all SVGs; optionally run design-quality checks.

    Args:
        project_path: Path to the slide-skill project directory.
        stage: ``"output"`` or ``"final"`` — which SVG subdirectory.
        quality: If True, also run spec-drift, font-safety, rhythm,
                 layout-variety, and image-integration checks.

    Returns:
        (passed, issues) where *passed* is True when zero errors exist.
    """
    project = Path(project_path)
    svg_dir = project / ("svg_final" if stage == "final" else "svg_output")
    issues: list[SvgIssue] = []

    svg_files = sorted(svg_dir.glob("*.svg"))
    if not svg_files:
        issues.append(SvgIssue("error", str(svg_dir), "No SVG files found"))
        return False, issues

    # Load spec lock once if quality mode is enabled
    spec_lock: dict[str, Any] | None = None
    if quality:
        try:
            from .spec_lock_reader import load_spec_lock
            spec_lock = load_spec_lock(project)
        except (FileNotFoundError, Exception):
            spec_lock = None

    # Per-file structural checks
    parsed_roots: list[tuple[Path, ET.Element]] = []
    for svg_file in svg_files:
        file_issues = check_svg_file(svg_file, project)
        issues.extend(file_issues)
        # Parse for design-quality checks
        if quality:
            try:
                root = ET.fromstring(svg_file.read_text(encoding="utf-8"))
                parsed_roots.append((svg_file, root))
            except ET.ParseError:
                pass

    # Design-quality checks (project-wide)
    if quality and parsed_roots:
        if spec_lock:
            issues.extend(_check_spec_drift(parsed_roots, spec_lock))
            issues.extend(_check_spec_polish(parsed_roots, spec_lock))
            issues.extend(_check_text_contrast(parsed_roots, spec_lock))
        issues.extend(_check_font_safety(parsed_roots))
        issues.extend(_check_rhythm_monotony(parsed_roots))
        issues.extend(_check_layout_variety(parsed_roots))
        issues.extend(_check_image_usage(parsed_roots))

    return not any(issue.level == "error" for issue in issues), issues


def canvas_overflow_margins(canvas_w: int, canvas_h: int) -> tuple[int, int]:
    """Tolerance (x, y) in px before an overflow verdict is reported.

    Shared threshold: the static estimate below and the browser-measured
    arbitration in ai_executor (QA-02) must agree on what counts as
    "beyond the canvas", so the browser can overrule the estimate without
    moving the goalposts.
    """
    return max(8, round(canvas_w * 0.02)), max(8, round(canvas_h * 0.02))


def text_boxes_overlap(
    ax1: float, ay1: float, ax2: float, ay2: float,
    bx1: float, by1: float, bx2: float, by2: float,
) -> bool:
    """Material text-box collision per the static QA thresholds.

    True only when the boxes intersect, are not near-identical duplicates
    (< 5px on every edge), and the vertical intersection covers at least
    30% of the shorter box. Shared by the static overlap loop below and the
    browser-measured re-verdict in ai_executor (QA-02).
    """
    if not (ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1):
        return False
    if abs(ax1 - bx1) < 5 and abs(ay1 - by1) < 5 and abs(ax2 - bx2) < 5 and abs(ay2 - by2) < 5:
        return False
    overlap_h = min(ay2, by2) - max(ay1, by1)
    min_h = min(ay2 - ay1, by2 - by1)
    return overlap_h >= min_h * 0.3


def check_svg_file(svg_file: Path, project_path: Path) -> list[SvgIssue]:
    """Structural QA for a single SVG file (unchanged from pre-v4.0)."""
    issues: list[SvgIssue] = []
    try:
        root = ET.fromstring(svg_file.read_text(encoding="utf-8"))
    except ET.ParseError as exc:
        return [SvgIssue("error", str(svg_file), f"Invalid XML: {exc}")]

    if not root.tag.endswith("svg"):
        issues.append(SvgIssue("error", str(svg_file), "Root element is not <svg>"))

    width = root.attrib.get("width")
    height = root.attrib.get("height")
    viewbox = root.attrib.get("viewBox")
    if not (width and height and viewbox):
        issues.append(SvgIssue("error", str(svg_file), "SVG must declare width, height, and viewBox"))
    elif viewbox.strip() != f"0 0 {width} {height}":
        issues.append(SvgIssue("error", str(svg_file), "viewBox must match width and height"))

    for elem in root.iter():
        tag = _local_name(elem.tag)

        # Banned tags — hard error
        if tag in BANNED_TAGS or tag.startswith("animate"):
            issues.append(SvgIssue("error", str(svg_file), f"Banned SVG tag: <{tag}>"))

        # Path must have non-empty d
        if tag == "path" and not elem.attrib.get("d", "").strip():
            issues.append(SvgIssue("error", str(svg_file), "SVG <path> requires a non-empty d attribute"))

        # Polygon/polyline must have points
        if tag in {"polygon", "polyline"} and not elem.attrib.get("points", "").strip():
            issues.append(SvgIssue("error", str(svg_file), f"SVG <{tag}> requires a non-empty points attribute"))

        # Only ban event-handler attributes
        for attr in elem.attrib:
            if attr in BANNED_ATTRS or attr.startswith("on"):
                issues.append(SvgIssue("error", str(svg_file), f"Banned event-handler attribute: {attr}"))

        # Warn (not error) for external href in <use>
        if tag == "use":
            href = elem.attrib.get("href", "") or elem.attrib.get(
                "{http://www.w3.org/1999/xlink}href", ""
            )
            if href and not href.startswith("#"):
                issues.append(
                    SvgIssue("warning", str(svg_file), f"External href in <use>: {href} (prefer local #id)")
                )

    # Require at least one semantic top-level content group
    content_groups = [
        child for child in list(root)
        if _local_name(child.tag) == "g" and not _is_chrome_group(child.attrib.get("id", ""))
    ]
    if not content_groups:
        issues.append(SvgIssue("error", str(svg_file), "No semantic top-level content groups found"))

    for group in content_groups:
        if not group.attrib.get("id"):
            issues.append(SvgIssue("error", str(svg_file), "Top-level content group missing id attribute"))

    # ── Ghost element detection (QA-04) ─────────────────────────────
    # Invisible markup pads structure without pixels and makes QA lie
    # about what the audience actually sees — hard error, not warning.
    issues.extend(_check_ghost_elements(root, svg_file))

    # ── Text overflow detection ──────────────────────────────────────
    canvas_w = int(width) if width and width.isdigit() else 0
    canvas_h = int(height) if height and height.isdigit() else 0
    if canvas_w and canvas_h:
        for elem, offset_x, offset_y in _iter_with_translate(root):
            tag = _local_name(elem.tag)
            if tag != "text":
                continue
            try:
                tx = int(float(elem.attrib.get("x", "0")) + offset_x)
                ty = int(float(elem.attrib.get("y", "0")) + offset_y)
            except (ValueError, TypeError):
                continue
            fs_str = elem.attrib.get("font-size", "")
            try:
                fs = int(float(fs_str)) if fs_str else 20
            except (ValueError, TypeError):
                fs = 20
            try:
                line_height = float(elem.attrib.get("data-line-height", "1.45"))
            except (ValueError, TypeError):
                line_height = 1.45
            texts = []
            if elem.text and elem.text.strip():
                texts.append(elem.text.strip())
            for child in elem:
                if _local_name(child.tag) == "tspan" and child.text:
                    texts.append(child.text.strip())
            full_text = " ".join(texts)
            if not full_text:
                continue
            fit_box = _parse_fit_box(elem.attrib.get("data-fit-box", ""))
            text_anchor = elem.attrib.get("text-anchor", "")
            has_tspan = any(_local_name(child.tag) == "tspan" for child in elem)
            if fit_box:
                box_x, box_y, box_w, box_h = fit_box
                est_x = box_x
                max_width = box_w
            elif not has_tspan:
                max_width = None
                est_x = _estimate_anchor_x(full_text, fs, tx, text_anchor)
            elif text_anchor == "middle":
                max_width = max(1, min(tx * 2, (canvas_w - tx) * 2) - 20)
                est_x = tx - max_width // 2
            else:
                max_width = canvas_w - tx - 20
                est_x = tx

            _, y_top, x_right, y_bottom = _estimate_text_bounds(
                full_text, fs, est_x, ty, max_width=max_width, line_height=line_height,
            )
            # Text bounds are an approximation (character-width model), so a
            # few pixels of estimated overshoot are within noise. Use a small
            # proportional tolerance to avoid failing a whole deck on a 1-2px
            # estimated overflow that is visually imperceptible.
            x_margin, y_margin = canvas_overflow_margins(canvas_w, canvas_h)
            if x_right > canvas_w + x_margin:
                issues.append(SvgIssue(
                    "error", str(svg_file),
                    f"Text may overflow right edge: x_right≈{x_right}px > canvas {canvas_w}px "
                    f"(text: \"{full_text[:40]}...\")"
                ))
            if y_bottom > canvas_h + y_margin:
                issues.append(SvgIssue(
                    "error", str(svg_file),
                    f"Text may overflow bottom edge: y_bottom≈{y_bottom}px > canvas {canvas_h}px "
                    f"(text: \"{full_text[:40]}...\")"
                ))
            if fit_box:
                box_x, box_y, box_w, box_h = fit_box
                box_margin = 2
                if x_right > box_x + box_w + box_margin:
                    issues.append(SvgIssue(
                        "error", str(svg_file),
                        f"Text may overflow fit box right edge: x_right≈{x_right}px > box {box_x + box_w}px "
                        f"(text: \"{full_text[:40]}...\")"
                    ))
                if y_top < box_y - box_margin:
                    issues.append(SvgIssue(
                        "error", str(svg_file),
                        f"Text may overflow fit box top edge: y_top≈{y_top}px < box {box_y}px "
                        f"(text: \"{full_text[:40]}...\")"
                    ))
                if y_bottom > box_y + box_h + box_margin:
                    issues.append(SvgIssue(
                        "error", str(svg_file),
                        f"Text may overflow fit box bottom edge: y_bottom≈{y_bottom}px > box {box_y + box_h}px "
                        f"(text: \"{full_text[:40]}...\")"
                    ))

    # ── Text overlap detection ──────────────────────────────────────
    # Each text row — including every wrapping <tspan> with its own
    # x/dy — gets its own bbox. Two historical false-positive classes
    # are handled here:
    #   * Wrapped CJK (fixed earlier): concatenating all tspans into one
    #     string measured the joined width, pushing the box into the
    #     neighbouring card even though the wrapped lines fit. Rows are
    #     measured separately instead.
    #   * Horizontal rich-text flow (REDESIGN_v5 F.3): <tspan dx="…">
    #     segments inside one <text> are one flowing line. They used to
    #     collapse onto the parent x, stacking phantom boxes on top of
    #     each other — a healthy timeline slide got 11 fake overlap
    #     reports. A per-<text> horizontal cursor now models the flow
    #     (explicit x resets it, dx advances it, each measured segment
    #     advances it by its estimated width), and boxes of the SAME
    #     <text> element are never overlap-compared with each other.
    if canvas_w and canvas_h:
        text_boxes: list[tuple[int, str, int, int, int, int]] = []  # (elem_key, text, x1, y1, x2, y2)
        for elem, offset_x, offset_y in _iter_with_translate(root):
            tag = _local_name(elem.tag)
            if tag != "text":
                continue
            try:
                tx = int(float(elem.attrib.get("x", "0")) + offset_x)
                ty = int(float(elem.attrib.get("y", "0")) + offset_y)
            except (ValueError, TypeError):
                continue
            fs_str = elem.attrib.get("font-size", "")
            try:
                fs = int(float(fs_str)) if fs_str else 20
            except (ValueError, TypeError):
                fs = 20
            parent_id = ""
            p = elem
            while p is not None:
                pid = p.attrib.get("id", "")
                if pid:
                    parent_id = pid
                    break
                p = _get_parent(root, p)
            if _is_chrome_group(parent_id):
                continue
            text_anchor = elem.attrib.get("text-anchor", "")
            ascent = int(fs * 0.75)

            # Build the list of measured segments with a per-<text>
            # horizontal cursor (SVG chunk semantics):
            # - explicit tspan x  -> reset the cursor to x (+ group offset)
            # - dx                -> advance the cursor; the segment
            #                        CONTINUES the current row (horizontal
            #                        rich-text flow, e.g. label+value+unit)
            # - dy                -> move the baseline down (vertical stack);
            #                        the first wrap tspan carries dy="0"
            # - none of the above -> continue the row at the cursor
            # After measuring, the cursor advances past the segment so
            # consecutive dx segments flow like really rendered text.
            segments: list[tuple[str, float, float, int]] = []  # (seg, start_x, est_w, row_y)
            tspan_children = [
                c for c in elem
                if _local_name(c.tag) == "tspan"
            ]
            if tspan_children:
                cursor_x = float(tx)
                cur_y = ty
                for c in tspan_children:
                    x_attr = c.attrib.get("x")
                    if x_attr is not None:
                        try:
                            cursor_x = float(x_attr) + offset_x
                        except (ValueError, TypeError):
                            cursor_x = float(tx)
                    dx_attr = c.attrib.get("dx")
                    if dx_attr is not None:
                        try:
                            cursor_x += float(dx_attr)
                        except (ValueError, TypeError):
                            pass
                    try:
                        dy = float(c.attrib.get("dy", "0"))
                    except (ValueError, TypeError):
                        dy = 0
                    cur_y += int(dy)
                    seg = (c.text or "").strip()
                    if not seg:
                        # Cursor already consumed x/dx/dy for empty spans.
                        continue
                    est_w = sum(_char_width(ch, fs) for ch in seg)
                    segments.append((seg, cursor_x, est_w, cur_y))
                    cursor_x += est_w
            elif elem.text and elem.text.strip():
                seg = elem.text.strip()
                segments.append(
                    (seg, float(tx), sum(_char_width(ch, fs) for ch in seg), ty)
                )

            # Group segments into rows (same baseline y). One box per row:
            # the x-range spans from the first segment to the end of the
            # last dx-shifted segment, so canvas/collision geometry stays
            # accurate for horizontal flows.
            rows: dict[int, list[tuple[str, float, float]]] = {}
            for seg, sx, sw, sy in segments:
                rows.setdefault(sy, []).append((seg, sx, sw))

            elem_key = id(elem)
            for row_y, row_segs in rows.items():
                row_x1 = min(sx for _, sx, _ in row_segs)
                row_x2 = max(sx + sw for _, sx, sw in row_segs)
                row_w = row_x2 - row_x1
                row_text = " ".join(seg for seg, _, _ in row_segs)
                if text_anchor == "middle":
                    x1 = int(row_x1 - row_w // 2)
                elif text_anchor == "end":
                    x1 = int(row_x1 - row_w)
                else:
                    x1 = int(row_x1)
                x2 = x1 + int(row_w)
                y1 = row_y - ascent
                y2 = row_y + int(fs * 0.25)
                text_boxes.append((elem_key, row_text, x1, y1, x2, y2))

        for i in range(len(text_boxes)):
            for j in range(i + 1, len(text_boxes)):
                key_a, txt_a, ax1, ay1, ax2, ay2 = text_boxes[i]
                key_b, txt_b, bx1, by1, bx2, by2 = text_boxes[j]
                if key_a == key_b:
                    # Rows/segments of the same <text> element model one
                    # flowing block — never report them as mutual overlaps.
                    continue
                if not text_boxes_overlap(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
                    continue
                issues.append(SvgIssue(
                    "warning", str(svg_file),
                    f"Text overlap: \"{txt_a[:25]}\" ({ay1}-{ay2}y) "
                    f"overlaps \"{txt_b[:25]}\" ({by1}-{by2}y)"
                ))

    return issues


# =====================================================================
# Ghost element detection (QA-04)
# =====================================================================

# Containers whose children are definitions/geometry, not painted pixels.
# Invisibility inside them is legitimate (gradient stops, clip shapes...).
_NON_RENDER_CONTEXTS = {
    "defs", "lineargradient", "radialgradient", "pattern",
    "clippath", "mask", "filter", "symbol", "title", "desc",
}

_GHOST_DRAWABLE_TAGS = {"rect", "circle", "ellipse", "path", "polygon"}

_QA_ALLOW_ATTR = "data-qa-allow"


def _check_ghost_elements(root: ET.Element, svg_file: Path) -> list[SvgIssue]:
    """Error on invisible ghost markup outside non-render contexts.

    Two error classes:
      (a) ``<text>``/``<tspan>`` whose effective content is empty or
          whitespace-only;
      (b) drawable shapes (rect/circle/ellipse/path/polygon) whose
          effective opacity makes them invisible: element ``opacity``
          (inherited multiplicatively) x ``fill-opacity``, plus
          ``fill="none"`` with no visible stroke.

    ``data-qa-allow="invisible"`` on the element or an ancestor opts a
    subtree out for intentional cases, so future themes are not boxed in.
    """
    ghost_issues: list[SvgIssue] = []
    _walk_ghost_elements(root, svg_file, ghost_issues, allowed=False, opacity=1.0)
    return ghost_issues


def _walk_ghost_elements(
    elem: ET.Element,
    svg_file: Path,
    out: list[SvgIssue],
    *,
    allowed: bool,
    opacity: float,
) -> None:
    tag = _local_name(elem.tag)
    if tag.lower() in _NON_RENDER_CONTEXTS:
        return
    allowed = allowed or elem.attrib.get(_QA_ALLOW_ATTR, "") == "invisible"
    eff_opacity = opacity * _float_or(elem.attrib.get("opacity"), 1.0)

    if tag == "text":
        if allowed:
            return
        content = "".join(elem.itertext()).strip()
        if not content:
            out.append(SvgIssue(
                "error", str(svg_file),
                f"Ghost element: empty <text> at ({elem.attrib.get('x', '?')},"
                f"{elem.attrib.get('y', '?')}) renders nothing — remove it "
                f"or mark it {_QA_ALLOW_ATTR}=\"invisible\""
            ))
            return
        # Non-empty text may still carry empty <tspan> ghosts.
        for sub in elem.iter():
            if sub is elem or _local_name(sub.tag) != "tspan":
                continue
            if sub.attrib.get(_QA_ALLOW_ATTR, "") == "invisible":
                continue
            if not "".join(sub.itertext()).strip():
                out.append(SvgIssue(
                    "error", str(svg_file),
                    f"Ghost element: empty <tspan> inside <text> "
                    f"\"{content[:30]}\" renders nothing — remove it or mark "
                    f"it {_QA_ALLOW_ATTR}=\"invisible\""
                ))
        return

    if not allowed and tag in _GHOST_DRAWABLE_TAGS:
        reason = _invisible_drawable_reason(elem, eff_opacity)
        if reason:
            pos_x = elem.attrib.get("x") or elem.attrib.get("cx") or "?"
            pos_y = elem.attrib.get("y") or elem.attrib.get("cy") or "?"
            out.append(SvgIssue(
                "error", str(svg_file),
                f"Ghost element: <{tag}> at ({pos_x},{pos_y}) {reason} — "
                f"remove it or mark it {_QA_ALLOW_ATTR}=\"invisible\""
            ))

    for child in list(elem):
        _walk_ghost_elements(child, svg_file, out, allowed=allowed, opacity=eff_opacity)


def _invisible_drawable_reason(elem: ET.Element, eff_opacity: float) -> str | None:
    """Return why a drawable is effectively invisible, or None if visible."""
    if eff_opacity <= 0:
        return "is fully transparent (effective opacity 0)"

    stroke = elem.attrib.get("stroke", "").strip()
    stroke_opacity = _float_or(elem.attrib.get("stroke-opacity"), 1.0)
    has_stroke = bool(stroke) and stroke.lower() != "none" and stroke_opacity > 0

    fill = elem.attrib.get("fill", "").strip()
    fill_opacity = _float_or(elem.attrib.get("fill-opacity"), 1.0)
    fill_alpha = _hex_alpha(fill)
    fill_invisible = (
        fill.lower() == "none"
        or fill_opacity <= 0
        or (fill_alpha is not None and fill_alpha <= 0)
    )
    if fill_invisible and not has_stroke:
        if fill.lower() == "none":
            return 'has fill="none" and no stroke'
        return "has a fully transparent fill and no stroke"
    return None


def _float_or(value: object, default: float) -> float:
    if value is None:
        return default
    try:
        return float(str(value))
    except (ValueError, TypeError):
        return default


def _iter_with_translate(root: ET.Element):
    """Yield elements with inherited simple translate(x,y) offsets."""
    yield from _iter_with_translate_inner(root, 0.0, 0.0)


def _iter_with_translate_inner(elem: ET.Element, offset_x: float, offset_y: float):
    tx, ty = _parse_translate(elem.attrib.get("transform", ""))
    current_x = offset_x + tx
    current_y = offset_y + ty
    yield elem, current_x, current_y
    for child in list(elem):
        yield from _iter_with_translate_inner(child, current_x, current_y)


def _parse_translate(transform: str) -> tuple[float, float]:
    match = re.search(
        r"translate\(\s*(-?\d+(?:\.\d+)?)(?:[\s,]+(-?\d+(?:\.\d+)?))?",
        str(transform or ""),
        flags=re.IGNORECASE,
    )
    if not match:
        return 0.0, 0.0
    return float(match.group(1)), float(match.group(2) or 0)


def _estimate_anchor_x(text: str, font_size: int, x: int, text_anchor: str) -> int:
    """Convert an SVG text anchor point to an estimated left edge."""
    if text_anchor not in {"middle", "end"}:
        return x
    left, _, right, _ = _estimate_text_bounds(text, font_size, 0, 0, max_width=None)
    width = right - left
    if text_anchor == "middle":
        return int(x - width / 2)
    return x - width


# =====================================================================
# Report writer
# =====================================================================

def write_svg_report(
    project_path: Path | str,
    stage: str = "output",
    *,
    quality: bool = False,
) -> Path:
    """Write SVG QA report grouped by severity level."""
    project = Path(project_path)
    ok, issues = check_project_svg(project, stage=stage, quality=quality)
    report = project / "qa" / "SVG-QA.md"
    ensure_dir(report.parent)

    errors = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warning"]
    infos = [i for i in issues if i.level == "info"]

    passed = ok and not (quality and warnings)
    lines = [
        "# SVG QA Report",
        "",
        f"**Status:** {'✅ passed' if passed else '❌ failed'}",
        f"**Mode:** {'structural + design quality' if quality else 'structural only'}",
        "",
        f"| Level | Count |",
        f"|-------|-------|",
        f"| Errors | {len(errors)} |",
        f"| Warnings | {len(warnings)} |",
        f"| Info | {len(infos)} |",
        "",
    ]

    if errors:
        lines.append("## ❌ Errors (must fix)")
        lines.append("")
        for issue in errors:
            lines.append(f"- `{issue.file}`: {issue.message}")
        lines.append("")

    if warnings:
        lines.append("## ⚠️ Warnings (should fix)")
        lines.append("")
        for issue in warnings:
            lines.append(f"- `{issue.file}`: {issue.message}")
        lines.append("")

    if infos:
        lines.append("## ℹ️ Info (consider)")
        lines.append("")
        for issue in infos:
            lines.append(f"- `{issue.file}`: {issue.message}")
        lines.append("")

    if not issues:
        lines.append("No issues found. ✨")
        lines.append("")

    report.write_text("\n".join(lines), encoding="utf-8")
    return report


# =====================================================================
# Design-quality checkers (Phase 44)
# =====================================================================

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?$")


def _extract_hex_colors(root: ET.Element) -> set[str]:
    """Extract all literal hex colors from fill/stroke/stop-color attributes."""
    colors: set[str] = set()
    for elem in root.iter():
        for attr in ("fill", "stroke", "stop-color", "flood-color"):
            val = elem.attrib.get(attr, "")
            if val and _HEX_COLOR_RE.match(val):
                # Normalize to uppercase 6-char
                colors.add(val[:7].upper())
    return colors


def _extract_font_families(root: ET.Element) -> set[str]:
    """Extract all font-family values from <text> elements."""
    families: set[str] = set()
    for elem in root.iter():
        tag = _local_name(elem.tag)
        if tag in ("text", "tspan"):
            ff = elem.attrib.get("font-family", "")
            if ff:
                families.add(ff.strip())
    return families


def _parse_font_stack(font_family: str) -> list[str]:
    """Parse a CSS font-family string into individual font names."""
    return [f.strip().strip("'\"").lower() for f in font_family.split(",") if f.strip()]


def _check_spec_drift(
    parsed_roots: list[tuple[Path, ET.Element]],
    spec_lock: dict[str, Any],
) -> list[SvgIssue]:
    """Flag colors and fonts not in the spec lock palette/typography."""
    issues: list[SvgIssue] = []
    palette = spec_lock.get("palette", {})
    palette_colors = _allowed_palette_colors(palette)
    # Also accept "none" and common structural colors (black, white)
    palette_colors |= {"#FFFFFF", "#000000"}

    # Typography families from spec lock
    typo = spec_lock.get("typography", {})
    spec_fonts: set[str] = set()
    for key in ("title_family", "body_family", "emphasis_family", "code_family"):
        ff = typo.get(key, "")
        if ff:
            for name in _parse_font_stack(ff):
                spec_fonts.add(name)
    # Also accept generic families
    spec_fonts |= {"sans-serif", "serif", "monospace", "cursive", "fantasy"}

    for svg_file, root in parsed_roots:
        fname = svg_file.name
        # Color drift
        used_colors = _extract_hex_colors(root)
        for color in sorted(used_colors):
            if color not in palette_colors:
                issues.append(SvgIssue(
                    "warning", fname,
                    f"Color {color} not in spec lock palette"
                ))
        # Font drift
        used_fonts = _extract_font_families(root)
        for ff in sorted(used_fonts):
            parsed = _parse_font_stack(ff)
            if not parsed:
                continue
            primary = parsed[0]
            if primary not in spec_fonts and primary not in PPT_SAFE_FONTS:
                issues.append(SvgIssue(
                    "warning", fname,
                    f"Font '{primary}' not in spec lock typography"
                ))

    return issues


def _allowed_palette_colors(palette: dict[str, Any]) -> set[str]:
    """Return locked palette colors plus the renderer's bounded derived tints.

    The SVG renderer intentionally creates a small set of accent/surface
    variants for depth and rhythm. Treat those as in-spec while still flagging
    arbitrary colors that are unrelated to the locked theme.
    """
    base_colors = {
        v.upper()[:7]
        for v in palette.values()
        if isinstance(v, str) and _HEX_COLOR_RE.match(v)
    }
    virtual_bases = set(base_colors)
    for color in base_colors:
        # Intent-aware rendering may first nudge the palette by slide rhythm
        # and then derive local card accents from that nudged color.
        virtual_bases.add(_shift_hex(color, 10))
        virtual_bases.add(_shift_hex(color, -8))
    allowed = set(virtual_bases)
    allowed |= {"#FFFFFF", "#000000"}
    for color in virtual_bases:
        for delta in range(-60, 61):
            allowed.add(_shift_hex(color, delta))
    return allowed


def _shift_hex(hexc: str, delta: int) -> str:
    h_ = hexc.lstrip("#")
    try:
        r, g, b = (int(h_[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return hexc.upper()[:7]
    r = max(0, min(255, r + delta))
    g = max(0, min(255, g + delta))
    b = max(0, min(255, b + delta))
    return f"#{r:02X}{g:02X}{b:02X}"


def _check_spec_polish(
    parsed_roots: list[tuple[Path, ET.Element]],
    spec_lock: dict[str, Any],
) -> list[SvgIssue]:
    """Flag common spec-lock polish misses that visual critics repeatedly catch."""
    issues: list[SvgIssue] = []
    hints = str(spec_lock.get("design_hints") or "").lower()
    palette = spec_lock.get("palette", {}) if isinstance(spec_lock.get("palette"), dict) else {}
    wants_card_gradient = "lineargradient" in hints and any(term in hints for term in ("card", "panel", "surface"))
    wants_progress_dots = "progress dots" in hints
    surface = _normalize_hex(palette.get("surface"))
    accent = _normalize_hex(palette.get("accent"))
    text_secondary = _normalize_hex(palette.get("text_secondary") or palette.get("body"))

    for svg_file, root in parsed_roots:
        fname = svg_file.name
        if wants_card_gradient and _has_flat_content_surface(root, surface):
            issues.append(SvgIssue(
                "warning",
                fname,
                "Spec polish: content card/panel uses a flat fill even though the spec asks for a linearGradient surface",
            ))
        footer_issue = _footer_contrast_issue(root, text_secondary, fallback_background=surface)
        if footer_issue:
            issues.append(SvgIssue("warning", fname, footer_issue))
        progress_issue = _footer_progress_dots_issue(root, accent) if wants_progress_dots else ""
        if progress_issue:
            issues.append(SvgIssue(
                "warning",
                fname,
                progress_issue,
            ))
    return issues


# ── Text contrast (Change 3a) ────────────────────────────────────────
# WCAG-style thresholds: body text (< 24px) needs ≥ 4.5:1 against its
# background; large/title text (≥ 24px) needs ≥ 3.0:1. The footer page-number
# case is already handled by _footer_contrast_issue, so this checker skips
# any text inside the chrome-footer group to avoid duplicate reports.
_TEXT_CONTRAST_BODY_MIN = 4.5
_TEXT_CONTRAST_LARGE_MIN = 3.0
_LARGE_TEXT_FONT_SIZE = 24  # px; matches WCAG "large text" breakpoint (18pt ≈ 24px)
_DECORATIVE_FONT_SIZE = 10  # skip tiny decorative glyphs below this size


def _resolve_text_fill(elem: ET.Element, root: ET.Element) -> str | None:
    """Resolve the effective fill color of a <text> element, walking ancestors."""
    node: ET.Element | None = elem
    while node is not None:
        fill = _normalize_hex(node.attrib.get("fill"))
        if fill:
            return fill
        node = _get_parent(root, node)
    return None


def _resolve_raw_text_fill(elem: ET.Element, root: ET.Element) -> str | None:
    """Like :func:`_resolve_text_fill` but returns the raw fill string,
    preserving any 8-digit ``#RRGGBBAA`` alpha channel.

    Used only by the contrast check, which needs the alpha to detect
    translucent body text (e.g. an ``accent_tint`` misused as a text fill).
    Callers that only want the 6-digit color continue to use
    :func:`_resolve_text_fill`.
    """
    node: ET.Element | None = elem
    while node is not None:
        fill = str(node.attrib.get("fill") or "").strip()
        if fill and _HEX_COLOR_RE.match(fill):
            return fill
        node = _get_parent(root, node)
    return None


def _resolve_text_background(elem: ET.Element, root: ET.Element, fallback: str | None) -> str | None:
    """Resolve the background color behind a <text> element.

    Strategy: climb ancestors and return the first solid <rect> fill found
    on an enclosing <g>. A <rect> is a candidate background only when it is
    opaque (no fill-opacity < 1 and not url()/none). If none is found, fall
    back to the canvas/palette background.
    """
    point = _text_anchor_point(elem)
    branch: ET.Element = elem
    node: ET.Element | None = _get_parent(root, elem)
    while node is not None:
        children = list(node)
        try:
            branch_index = children.index(branch)
            candidates = children[:branch_index]
        except ValueError:
            candidates = children
        for child in reversed(candidates):
            shape_fill = _containing_shape_fill(child, point)
            if shape_fill:
                # Translucent fills (e.g. an accent_tint circle written as
                # 8-digit hex) read as their composited color over the canvas,
                # not their raw paint. Composite before returning so contrast
                # is judged against what the viewer sees.
                return _effective_background(shape_fill, fallback) or shape_fill
            if _local_name(child.tag) != "rect":
                continue
            # A background rect is typically a direct child of the enclosing group.
            fill = child.attrib.get("fill", "")
            if not fill or fill.lower() in ("none", "transparent") or fill.lower().startswith("url("):
                continue
            if not _is_opaque_rect(child):
                continue
            # An accent_tint rect is written as 8-digit hex (alpha baked in),
            # which _is_opaque_rect cannot see (it only checks the
            # fill-opacity/opacity attributes). Resolve to the effective opaque
            # color over the canvas fallback so contrast is accurate.
            effective = _effective_background(fill, fallback)
            if effective:
                return effective
        branch = node
        node = _get_parent(root, node)
    return fallback


def _text_anchor_point(elem: ET.Element) -> tuple[float, float] | None:
    try:
        return (
            float(elem.attrib.get("x", "0")),
            float(elem.attrib.get("y", "0")),
        )
    except (ValueError, TypeError):
        return None


def _containing_shape_fill(elem: ET.Element, point: tuple[float, float] | None) -> str | None:
    if point is None or not _is_opaque_rect(elem):
        return None
    tag = _local_name(elem.tag)
    fill = elem.attrib.get("fill", "")
    if not fill or fill.lower() in ("none", "transparent") or fill.lower().startswith("url("):
        return None
    normalized = _normalize_hex(fill)
    if not normalized:
        return None
    px, py = point
    if tag == "circle":
        cx = _numeric_svg_attr(elem.attrib.get("cx"))
        cy = _numeric_svg_attr(elem.attrib.get("cy"))
        r = _numeric_svg_attr(elem.attrib.get("r"))
        if cx is None or cy is None or r is None:
            return None
        return normalized if (px - cx) ** 2 + (py - cy) ** 2 <= r ** 2 else None
    if tag == "ellipse":
        cx = _numeric_svg_attr(elem.attrib.get("cx"))
        cy = _numeric_svg_attr(elem.attrib.get("cy"))
        rx = _numeric_svg_attr(elem.attrib.get("rx"))
        ry = _numeric_svg_attr(elem.attrib.get("ry"))
        if cx is None or cy is None or rx in (None, 0) or ry in (None, 0):
            return None
        return normalized if ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 <= 1 else None
    return None


def _is_opaque_rect(elem: ET.Element) -> bool:
    for attr in ("fill-opacity", "opacity"):
        raw = elem.attrib.get(attr)
        if raw is None:
            continue
        try:
            if float(raw) < 1.0:
                return False
        except (ValueError, TypeError):
            continue
    return True


def _is_in_footer_group(elem: ET.Element, root: ET.Element) -> bool:
    """True when the text element lives inside a chrome-footer group."""
    node: ET.Element | None = _get_parent(root, elem)
    while node is not None:
        gid = node.attrib.get("id", "")
        if gid == "chrome-footer" or "footer" in gid.lower():
            return True
        node = _get_parent(root, node)
    return False


def _check_text_contrast(
    parsed_roots: list[tuple[Path, ET.Element]],
    spec_lock: dict[str, Any],
) -> list[SvgIssue]:
    """Flag low-contrast text against its resolved background.

    Catches the AI-path equivalent of the contrast bug fixed for the
    deterministic renderer in 43f9bca: body text in ``muted`` on a dark
    surface, titles in low-luminance accent tints, etc. Reports one issue per
    offending (fill, background) pair per file to avoid flooding the report.
    """
    palette = spec_lock.get("palette", {}) if isinstance(spec_lock.get("palette"), dict) else {}
    canvas_bg = _normalize_hex(palette.get("background"))
    surface = _normalize_hex(palette.get("surface"))
    issues: list[SvgIssue] = []

    for svg_file, root in parsed_roots:
        fname = svg_file.name
        seen_pairs: set[tuple[str, str]] = set()
        for elem in root.iter():
            if _local_name(elem.tag) != "text":
                continue
            # Skip empty text or whitespace-only.
            if not "".join(elem.itertext()).strip():
                continue
            if _is_in_footer_group(elem, root):
                continue
            fill = _resolve_text_fill(elem, root)
            if not fill:
                continue
            fs_str = elem.attrib.get("font-size", "")
            try:
                fs = int(float(fs_str)) if fs_str else 20
            except (ValueError, TypeError):
                fs = 20
            if fs < _DECORATIVE_FONT_SIZE:
                continue
            background = _resolve_text_background(elem, root, canvas_bg) or surface
            if not background:
                continue
            # Translucent text (e.g. an accent_tint used as a body fill via
            # 8-digit hex) is nearly invisible even when its raw RGB would
            # pass contrast. Composite the effective fill onto the background
            # before measuring, so tinted body text is caught rather than
            # silently approved. _resolve_text_fill already stripped alpha,
            # so re-read the owning fill's alpha from the raw attribute chain.
            raw_fill = _resolve_raw_text_fill(elem, root) or fill
            effective_fill = _composite_over_opaque(raw_fill, background) or fill
            pair = (effective_fill, background)
            if pair in seen_pairs:
                continue
            ratio = _contrast_ratio(effective_fill, background)
            threshold = _TEXT_CONTRAST_LARGE_MIN if fs >= _LARGE_TEXT_FONT_SIZE else _TEXT_CONTRAST_BODY_MIN
            if ratio < threshold:
                kind = "large/title" if fs >= _LARGE_TEXT_FONT_SIZE else "body"
                seen_pairs.add(pair)
                note = ""
                if effective_fill != fill:
                    note = f" (translucent {fill} reads as {effective_fill})"
                issues.append(SvgIssue(
                    "warning",
                    fname,
                    f"Low text contrast: {kind} text {effective_fill}{note} on {background} "
                    f"is {ratio:.2f}:1 (need ≥{threshold:.1f}); use a higher-contrast palette role"
                ))
    return issues


def _has_flat_content_surface(root: ET.Element, surface: str | None) -> bool:
    for elem in root.iter():
        if _local_name(elem.tag) != "rect":
            continue
        fill = elem.attrib.get("fill", "")
        if not fill or fill.lower().startswith("url("):
            continue
        if surface and _normalize_hex(fill) != surface:
            continue
        parent_id = _ancestor_id_hint(root, elem)
        if "content" in parent_id or "card" in parent_id or "panel" in parent_id:
            return True
    return False


def _footer_contrast_issue(root: ET.Element, preferred: str | None, *, fallback_background: str | None = None) -> str:
    footer = _find_group_by_id(root, "chrome-footer")
    if footer is None:
        return ""
    footer_bg = _footer_background_fill(footer) or fallback_background
    for elem in footer.iter():
        if _local_name(elem.tag) != "text":
            continue
        text = "".join(elem.itertext()).strip()
        if not re.search(r"\d{2}\s*/\s*\d{2}", text):
            continue
        fill = _normalize_hex(elem.attrib.get("fill"))
        if fill and preferred and fill == preferred:
            continue
        if fill and footer_bg and _contrast_ratio(fill, footer_bg) < 3.0:
            suffix = f"; use {preferred}" if preferred else ""
            return f"Spec polish: footer page number uses low-contrast color {fill}{suffix}"
    return ""


def _footer_progress_dots_issue(root: ET.Element, accent: str | None) -> str:
    footer = _find_group_by_id(root, "chrome-footer")
    if footer is None:
        return ""
    dot_xs: list[float] = []
    for elem in footer.iter():
        if _local_name(elem.tag) not in {"circle", "ellipse"}:
            continue
        cy = _numeric_svg_attr(elem.attrib.get("cy"))
        if cy is not None and not 688 <= cy <= 720:
            continue
        fill = _normalize_hex(elem.attrib.get("fill"))
        stroke = _normalize_hex(elem.attrib.get("stroke"))
        if accent and fill != accent and stroke != accent:
            continue
        cx = _numeric_svg_attr(elem.attrib.get("cx"))
        if cx is not None:
            dot_xs.append(cx)
    if not dot_xs:
        return "Spec polish: footer is missing accent-colored progress dots requested by the spec lock"
    if min(dot_xs) >= 1120:
        return "Spec polish: footer progress dots are too close to the right-aligned page number; place them near the left edge of the footer"
    return ""


def _footer_background_fill(footer: ET.Element) -> str | None:
    for elem in footer.iter():
        if _local_name(elem.tag) == "rect":
            fill = _normalize_hex(elem.attrib.get("fill"))
            if fill:
                return fill
    return None


def _numeric_svg_attr(value: object) -> float | None:
    match = re.match(r"\s*(-?\d+(?:\.\d+)?)", str(value or ""))
    if not match:
        return None
    return float(match.group(1))


def _check_font_safety(
    parsed_roots: list[tuple[Path, ET.Element]],
) -> list[SvgIssue]:
    """Flag fonts that may not render in PowerPoint."""
    issues: list[SvgIssue] = []
    for svg_file, root in parsed_roots:
        fname = svg_file.name
        used_fonts = _extract_font_families(root)
        for ff in sorted(used_fonts):
            parsed = _parse_font_stack(ff)
            if not parsed:
                continue
            primary = parsed[0]
            has_safe_fallback = any(f in PPT_SAFE_FONTS for f in parsed[1:])
            if primary not in PPT_SAFE_FONTS and not has_safe_fallback:
                issues.append(SvgIssue(
                    "warning", fname,
                    f"Font '{primary}' may not render in PowerPoint — no safe fallback in stack"
                ))
    return issues


def _count_visual_elements(root: ET.Element) -> int:
    """Count drawable visual elements (excluding defs and chrome)."""
    count = 0
    drawable = {"rect", "circle", "ellipse", "line", "text", "path",
                "polygon", "polyline", "image"}
    for elem in root.iter():
        tag = _local_name(elem.tag)
        if tag in drawable:
            count += 1
    return count


def _check_rhythm_monotony(
    parsed_roots: list[tuple[Path, ET.Element]],
) -> list[SvgIssue]:
    """Warn if all slides have similar visual density."""
    if len(parsed_roots) < 3:
        return []

    counts = [_count_visual_elements(root) for _, root in parsed_roots]
    avg = sum(counts) / len(counts) if counts else 0
    if avg == 0:
        return []

    # Check if all counts are within ±15% of average
    all_similar = all(abs(c - avg) / avg <= 0.15 for c in counts)
    if all_similar:
        return [SvgIssue(
            "warning", "project",
            f"All {len(counts)} pages have similar visual density "
            f"(avg {avg:.0f} elements, ±15%) — vary rhythm with at least one "
            f"anchor page (heavy) and one breathing page (sparse)"
        )]
    return []


def _extract_layout_signature(root: ET.Element) -> str:
    """Extract a layout signature from top-level group IDs."""
    ids = []
    for child in list(root):
        tag = _local_name(child.tag)
        if tag == "g":
            gid = child.attrib.get("id", "")
            if gid:
                # Normalize: strip page numbers to get structure
                normalized = re.sub(r"-\d+$", "", gid)
                ids.append(normalized)
    return "|".join(sorted(ids))


def _check_layout_variety(
    parsed_roots: list[tuple[Path, ET.Element]],
) -> list[SvgIssue]:
    """Warn if 3+ consecutive slides share identical layout structure."""
    if len(parsed_roots) < 3:
        return []

    issues: list[SvgIssue] = []
    signatures = [(f.name, _extract_layout_signature(root)) for f, root in parsed_roots]

    run_start = 0
    for i in range(1, len(signatures)):
        if signatures[i][1] != signatures[run_start][1]:
            if i - run_start >= 3:
                first = signatures[run_start][0]
                last = signatures[i - 1][0]
                issues.append(SvgIssue(
                    "warning", "project",
                    f"Pages {first}–{last} ({i - run_start} slides) have identical "
                    f"layout structure — break the repetition with a different focal "
                    f"placement, container shape, or alignment"
                ))
            run_start = i

    # Check final run
    if len(signatures) - run_start >= 3:
        first = signatures[run_start][0]
        last = signatures[-1][0]
        issues.append(SvgIssue(
            "warning", "project",
            f"Pages {first}–{last} ({len(signatures) - run_start} slides) have identical "
            f"layout structure — break the repetition with a different focal "
            f"placement, container shape, or alignment"
        ))

    return issues


def _check_image_usage(
    parsed_roots: list[tuple[Path, ET.Element]],
) -> list[SvgIssue]:
    """Info if many content slides lack imagery."""
    chrome_patterns = {"cover", "closing", "section-divider", "section-band"}

    content_count = 0
    no_image_count = 0

    for svg_file, root in parsed_roots:
        # Determine if this is a content slide (not cover/closing/divider)
        top_ids = {
            child.attrib.get("id", "")
            for child in list(root)
            if _local_name(child.tag) == "g"
        }
        # Skip chrome-only slides
        is_chrome = any(
            any(cp in gid for cp in chrome_patterns)
            for gid in top_ids
            if gid and not gid.startswith("chrome-")
        )
        has_content_group = any(
            gid.startswith("content-") for gid in top_ids
        )
        if not has_content_group:
            continue
        if is_chrome and not any(gid.startswith("content-body") for gid in top_ids):
            continue

        content_count += 1

        # Check for <image> elements
        has_image = any(
            _local_name(elem.tag) == "image" for elem in root.iter()
        )
        if not has_image:
            no_image_count += 1

    if content_count >= 4 and no_image_count / content_count > 0.5:
        return [SvgIssue(
            "info", "project",
            f"{no_image_count} of {content_count} content pages have no imagery "
            f"— consider adding visuals"
        )]
    return []


# =====================================================================
# Helpers
# =====================================================================

def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _get_parent(root: ET.Element, child: ET.Element) -> ET.Element | None:
    for parent in root.iter():
        if child in list(parent):
            return parent
    return None


def _normalize_hex(value: object) -> str | None:
    text = str(value or "").strip()
    if not _HEX_COLOR_RE.match(text):
        return None
    return text[:7].upper()


def _hex_alpha(value: object) -> float | None:
    """Return the alpha channel of an 8-digit ``#RRGGBBAA`` hex as 0..1.

    Returns ``None`` for 6-digit hex (treated as fully opaque by callers)
    or anything that is not a valid hex color. This is the alpha-aware
    companion to :func:`_normalize_hex`, which deliberately drops the
    alpha byte so dedup keys and drift checks stay 6-digit.
    """
    text = str(value or "").strip()
    if not _HEX_COLOR_RE.match(text):
        return None
    if len(text) != 9:  # only #RRGGBBAA carries alpha
        return None
    try:
        return int(text[7:9], 16) / 255.0
    except ValueError:
        return None


def _composite_over_opaque(fg: object, bg: object) -> str | None:
    """Alpha-composite a (possibly translucent) ``fg`` hex onto an opaque
    ``bg`` hex, returning the effective 6-digit ``#RRGGBB`` color.

    A translucent ``accent_tint`` such as ``#3B82F620`` painted over a
    white canvas reads to the eye as a pale blue, not the full accent.
    Contrast must therefore be judged against this composited color,
    not the raw paint — otherwise text on a tint reads as 1.00:1
    (accent-on-accent) even though it is perfectly legible.

    For fully opaque ``fg`` (6-digit, or alpha == 1.0) this returns the
    normalized 6-digit ``fg`` unchanged, so all existing 6-digit callers
    behave identically.
    """
    fg_text = str(fg or "").strip()
    bg6 = _normalize_hex(bg)
    if not bg6:
        return None
    fg6 = _normalize_hex(fg_text)
    if not fg6:
        return None
    alpha = _hex_alpha(fg_text)
    if alpha is None or alpha >= 1.0:
        return fg6
    if alpha <= 0.0:
        return bg6
    # Standard "over" compositing, per channel: out = fg*α + bg*(1−α).
    out = []
    for i in (1, 3, 5):
        fc = int(fg6[i:i + 2], 16) / 255.0
        bc = int(bg6[i:i + 2], 16) / 255.0
        mixed = fc * alpha + bc * (1.0 - alpha)
        out.append(f"{round(mixed * 255):02X}")
    return f"#{out[0]}{out[1]}{out[2]}"


def _effective_background(raw_fill: object, fallback: object) -> str | None:
    """Resolve a candidate background fill to its effective opaque color.

    If ``raw_fill`` carries an alpha channel (8-digit hex, e.g. an
    ``accent_tint`` rect), composite it onto ``fallback`` (the canvas
    behind it) so contrast is measured against the color the viewer
    actually sees. Otherwise normalize to 6-digit as before.
    """
    alpha = _hex_alpha(raw_fill)
    if alpha is not None and alpha < 1.0:
        composited = _composite_over_opaque(raw_fill, fallback)
        if composited:
            return composited
    return _normalize_hex(raw_fill)


def _contrast_ratio(foreground: str, background: str) -> float:
    fg = _relative_luminance(foreground)
    bg = _relative_luminance(background)
    lighter = max(fg, bg)
    darker = min(fg, bg)
    return (lighter + 0.05) / (darker + 0.05)


def _relative_luminance(hex_color: str) -> float:
    text = str(hex_color).lstrip("#")
    channels = [int(text[i:i + 2], 16) / 255 for i in (0, 2, 4)]

    def linear(channel: float) -> float:
        if channel <= 0.03928:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    r, g, b = [linear(channel) for channel in channels]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _find_group_by_id(root: ET.Element, group_id: str) -> ET.Element | None:
    for elem in root.iter():
        if _local_name(elem.tag) == "g" and elem.attrib.get("id") == group_id:
            return elem
    return None


def _ancestor_id_hint(root: ET.Element, target: ET.Element) -> str:
    path: list[str] = []

    def visit(elem: ET.Element, ancestors: list[str]) -> bool:
        current = ancestors
        elem_id = str(elem.attrib.get("id") or "")
        if elem_id:
            current = [*ancestors, elem_id.lower()]
        if elem is target:
            path.extend(current)
            return True
        for child in list(elem):
            if visit(child, current):
                return True
        return False

    visit(root, [])
    return " ".join(path)


def _is_chrome_group(gid: str) -> bool:
    return gid.startswith("chrome-") or gid == "background"


def _parse_fit_box(value: str) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    try:
        parts = [int(float(p.strip())) for p in value.split(",")]
    except ValueError:
        return None
    if len(parts) != 4:
        return None
    x, y, w, h = parts
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h
