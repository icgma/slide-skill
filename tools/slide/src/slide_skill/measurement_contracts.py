"""Hardened offline measurement-semantics contracts (v5.1 BENCH).

Committed port of the probe_contracts scratch library: SVG render smoke,
structural/visible-content audit, closed-world text audit, browser text
geometry with clipping/card containment, and executor-trace freshness
checks. The benchmark runner requires this suite green before any provider
run (REDESIGN_v5 Phase 0 acceptance, 56-CONTEXT D-12).
"""
from __future__ import annotations

import html
import json
import re
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET
import zlib
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path

SVG_NS = "{http://www.w3.org/2000/svg}"
SAFE_AREA = (80.0, 80.0, 1200.0, 680.0)
MIN_VISIBLE_OPACITY = 0.1
MIN_TEXT_PIXEL_RETENTION = 0.5
Matrix = tuple[float, float, float, float, float, float]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def render_svg_smoke(
    svg_path: Path,
    png_path: Path,
    *,
    text_bounds: tuple[float, float, float, float] = (0.0, 0.0, 1280.0, 720.0),
    card_pairs: Sequence[tuple[str, str]] = (),
) -> list[str]:
    """Render one SVG and reject malformed, uniform, or browser-clipped output."""
    browser = _find_browser()
    if not browser:
        return ["no Chrome/Edge browser found for render smoke"]
    html_path = png_path.with_suffix(".html")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    svg = svg_path.read_text(encoding="utf-8")
    unsafe = _audit_unsafe_svg(svg)
    if unsafe:
        return unsafe
    html_path.write_text(
        '<!doctype html><meta charset="utf-8">'
        '<style>html,body{margin:0;width:1280px;height:720px;overflow:hidden;background:#000}'
        'svg{width:1280px;height:720px;display:block}</style>'
        + svg,
        encoding="utf-8",
    )
    try:
        subprocess.run(
            [
                browser,
                "--headless=new",
                "--disable-gpu",
                f"--screenshot={png_path.resolve()}",
                "--window-size=1280,720",
                html_path.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"Chrome render failed: {exc.__class__.__name__}: {exc}"]
    if not png_path.exists() or png_path.stat().st_size == 0:
        return ["Chrome render did not create a PNG"]
    try:
        width, height, rows = _decode_png(png_path)
    except (OSError, ValueError, zlib.error) as exc:
        return [f"invalid Chrome PNG: {exc}"]
    if (width, height) != (1280, 720):
        return [f"wrong rendered dimensions: {width}x{height}"]
    pixels = [pixel for row in rows for pixel in row]
    sampled = set(pixels)
    if len(sampled) < 2:
        return ["Chrome render is a uniform image (blank/black-screen candidate)"]
    background = _dominant_pixel(pixels)
    foreground_pixels = sum(
        1 for pixel in pixels if _color_distance(pixel, background) > 10
    )
    foreground_ratio = foreground_pixels / len(pixels)
    if foreground_ratio < 0.001:
        return [f"Chrome foreground coverage is too small: {foreground_ratio:.4%}"]
    geometry_defects, entries = _browser_text_geometry(browser, svg, html_path, text_bounds, card_pairs)
    if geometry_defects:
        return geometry_defects
    return _audit_text_pixel_effect(browser, svg, html_path, rows, entries)


def audit_svg_contract(
    svg_text: str,
    *,
    required_text: Sequence[str],
    allowed_text: Sequence[str],
    allowed_colors: set[str],
    card_pairs: Sequence[tuple[str, str]] = (),
    allowed_text_groups: Sequence[Sequence[str]] = (),
    derived_text_patterns: Sequence[str] = (),
) -> tuple[list[str], str | None]:
    """Audit the standalone SVG probe's structural and visible-content contract."""
    defects, svg, root = _parse_svg(svg_text)
    if root is None:
        return defects, svg
    defects.extend(_audit_unsafe_svg(svg))

    if (
        root.get("width") != "1280"
        or root.get("height") != "720"
        or root.get("viewBox") != "0 0 1280 720"
    ):
        defects.append(
            "wrong root geometry: expected width=1280 height=720 viewBox='0 0 1280 720'"
        )

    defects.extend(_audit_paints(root, allowed_colors))
    defects.extend(_audit_top_level_groups(root))
    visible_nodes, visibility_defects, positioned = _visible_text(root)
    visible_segments = [segment for _, segments in visible_nodes for segment in segments]
    defects.extend(visibility_defects)
    defects.extend(_audit_safe_area(positioned))
    defects.extend(
        _audit_text_values(
            visible_nodes,
            required_text=required_text,
            allowed_text=allowed_text,
            allowed_text_groups=allowed_text_groups,
            derived_text_patterns=derived_text_patterns,
        )
    )
    defects.extend(_audit_card_geometry(root, card_pairs))

    longest = max((_normalized(text) for text in visible_segments), key=len, default="")
    if len(longest) > 34:
        defects.append(f"longest unwrapped run = {len(longest)} chars (likely overflows)")
    return defects, svg


def audit_closed_world_text(
    svg_text: str,
    *,
    required_text: Sequence[str],
    allowed_text: Sequence[str],
    allowed_text_groups: Sequence[Sequence[str]] = (),
    derived_text_patterns: Sequence[str] = (),
) -> list[str]:
    """Require all planned text and reject unsupported visible copy."""
    defects, _, root = _parse_svg(svg_text)
    if root is None:
        return defects
    visible_nodes, visibility_defects, _ = _visible_text(root)
    return [
        *defects,
        *_audit_unsafe_svg(svg_text),
        *visibility_defects,
        *_audit_text_values(
            visible_nodes,
            required_text=required_text,
            allowed_text=allowed_text,
            allowed_text_groups=allowed_text_groups,
            derived_text_patterns=derived_text_patterns,
        ),
    ]


def audit_executor_trace(
    events: Sequence[dict],
    slide_index: int,
    *,
    publish_path: Path | None = None,
) -> list[str]:
    """Verify that the returned page came from a fresh complete response."""
    matching = [
        event
        for event in events
        if event.get("stage") == "executor"
        and (event.get("metadata") or {}).get("slide") == slide_index
    ]
    if publish_path is not None:
        expected = str(publish_path.resolve()).lower()
        matching = [
            event
            for event in matching
            if str((event.get("metadata") or {}).get("publish_path", "")).strip().lower() == expected
        ]
    passed = [event for event in matching if str(event.get("status", "")).startswith("passed")]
    if not passed:
        return ["fresh executor trace has no passed event for this slide and publish path"]
    finish = str((passed[-1].get("metadata") or {}).get("finish_reason", ""))
    if finish != "stop":
        return [f"fresh passed executor event has finish_reason={finish or '<missing>'}, expected stop"]
    return []


def _parse_svg(svg_text: str) -> tuple[list[str], str | None, ET.Element | None]:
    defects: list[str] = []
    body = (svg_text or "").strip()
    if body.startswith("```"):
        defects.append("wrapped in markdown fence")
        body = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", body)
    match = re.search(r"<svg\b.*?</svg>", body, re.DOTALL)
    if not match:
        return [*defects, "no <svg> element found"], None, None
    if body[: match.start()].strip() or body[match.end() :].strip():
        defects.append("prose outside the SVG")
    svg = match.group(0)
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        return [*defects, f"XML parse error: {exc}"], svg, None
    if root.tag != f"{SVG_NS}svg":
        defects.append("root must be an SVG element in the default SVG namespace")
    return defects, svg, root


def _audit_unsafe_svg(svg: str | None) -> list[str]:
    body = svg or ""
    defects: list[str] = []
    if re.search(r"<!DOCTYPE|<!ENTITY", body, re.IGNORECASE):
        defects.append("unsafe SVG declaration: DOCTYPE/ENTITY is prohibited")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        return [*defects, f"unsafe SVG cannot be parsed before rendering: {exc}"]

    active_tags = {"script", "foreignobject", "iframe", "object", "embed", "audio", "video",
                   "animate", "animatetransform", "animatemotion", "set"}
    for element in root.iter():
        name = _local_name(element).lower()
        if name in active_tags:
            defects.append(f"unsafe SVG active element: <{name}>")
        if name == "style":
            defects.append("unsafe SVG active element: <style>")
        for attribute, raw_value in element.attrib.items():
            attribute_name = attribute.rsplit("}", 1)[-1].lower()
            value = raw_value.strip()
            if attribute_name.startswith("on"):
                defects.append(f"unsafe SVG event attribute: {attribute_name}")
            if attribute_name in {"href", "src"} and value and not value.startswith("#"):
                defects.append(f"unsafe SVG external reference: {attribute_name}={value!r}")
            for reference in re.findall(r"url\(\s*[\"']?([^\)\"']+)", value, re.IGNORECASE):
                if not reference.strip().startswith("#"):
                    defects.append(f"unsafe SVG external URL reference: {reference!r}")
    return defects



def _audit_paints(root: ET.Element, allowed_colors: set[str]) -> list[str]:
    defects: list[str] = []
    allowed = {color.upper() for color in allowed_colors}
    local_paints = {
        element.get("id")
        for element in root.iter()
        if _local_name(element) in {"linearGradient", "radialGradient", "pattern"}
        and element.get("id")
    }

    def audit_element(element: ET.Element, inherited_fill: str | None, inherited_stroke: str | None, in_defs: bool) -> None:
        name = _local_name(element)
        if element.get("class") is not None or element.get("style") is not None:
            defects.append(f"uses class/style on <{name}>")
        current_fill = element.get("fill") or inherited_fill
        current_stroke = element.get("stroke") or inherited_stroke
        fillable = name in {"rect", "circle", "ellipse", "path", "polygon", "polyline", "text", "tspan"}
        if fillable and not in_defs and current_fill is None:
            defects.append(f"implicit paint on <{name}>: default fill is outside the palette")
        if name == "stop" and not element.get("stop-color"):
            defects.append("implicit paint on <stop>: missing stop-color")
        for attribute, value in (("fill", current_fill), ("stroke", current_stroke), ("stop-color", element.get("stop-color"))):
            value = (value or "").strip()
            if not value or value == "none":
                continue
            local_reference = re.fullmatch(r"url\(\s*[\"']?#([^)\"']+)[\"']?\s*\)", value)
            if local_reference and local_reference.group(1) in local_paints:
                continue
            if value.upper() not in allowed:
                defects.append(f"prohibited paint {attribute}={value!r} on <{name}>")
        for child in element:
            audit_element(child, current_fill, current_stroke, in_defs or name == "defs")

    audit_element(root, None, None, False)
    return defects


def _audit_top_level_groups(root: ET.Element) -> list[str]:
    tops = [child for child in root if _local_name(child) != "defs"]
    bare = [_local_name(child) for child in tops if _local_name(child) != "g"]
    defects = [f"top-level non-group elements: {bare[:5]}"] if bare else []
    group_ids = [child.get("id") for child in tops if _local_name(child) == "g"]
    if any(not group_id for group_id in group_ids):
        defects.append("top-level <g> missing id")
    if len(group_ids) != len(set(group_ids)):
        defects.append("duplicate top-level group ids")
    return defects


def _visible_text(
    root: ET.Element,
) -> tuple[list[tuple[str, list[str]]], list[str], list[tuple[str, float, float]]]:
    nodes: list[tuple[str, list[str]]] = []
    defects: list[str] = []
    positioned: list[tuple[str, float, float]] = []

    def visit(
        element: ET.Element,
        opacity: float,
        fill_opacity: float,
        transform: Matrix,
        text_position: tuple[float, float] | None,
        inherited_fill: str,
        displayed: bool,
        visible: bool,
        node_segments: list[str] | None,
    ) -> None:
        current_opacity = opacity * _number(element.get("opacity"), 1.0)
        current_fill_opacity = fill_opacity * _number(element.get("fill-opacity"), 1.0)
        current_transform = _multiply(transform, _parse_transform(element.get("transform", "")))
        current_fill = (element.get("fill") or inherited_fill).strip().lower()
        current_displayed = displayed and element.get("display", "").strip().lower() != "none"
        visibility = element.get("visibility", "").strip().lower()
        if visibility == "visible":
            current_visible = True
        elif visibility in {"hidden", "collapse"}:
            current_visible = False
        elif visibility in {"initial", "revert", "revert-layer"}:
            current_visible = True
        else:
            current_visible = visible
        name = _local_name(element)
        position = text_position
        segments = node_segments
        if name == "text":
            segments = []
            nodes.append(("", segments))

        if name in {"text", "tspan"}:
            base_x, base_y = position or (0.0, 0.0)
            x = _coordinate(element.get("x"), base_x) + _coordinate(element.get("dx"), 0.0)
            y = _coordinate(element.get("y"), base_y) + _coordinate(element.get("dy"), 0.0)
            position = (x, y)
            segment = (element.text or "").strip()
            if segment:
                is_visible = (
                    current_displayed
                    and current_visible
                    and current_opacity >= MIN_VISIBLE_OPACITY
                    and current_fill_opacity >= MIN_VISIBLE_OPACITY
                    and current_fill != "none"
                )
                if is_visible:
                    px, py = _apply(current_transform, x, y)
                    if segments is not None:
                        segments.append(segment)
                    positioned.append((segment, px, py))
                else:
                    defects.append(f"invisible text: {segment!r}")

        for child in element:
            visit(
                child,
                current_opacity,
                current_fill_opacity,
                current_transform,
                position,
                current_fill,
                current_displayed,
                current_visible,
                segments,
            )
            tail = (child.tail or "").strip()
            if tail and name in {"text", "tspan"}:
                tail_visible = (
                    current_displayed
                    and current_visible
                    and current_opacity >= MIN_VISIBLE_OPACITY
                    and current_fill_opacity >= MIN_VISIBLE_OPACITY
                    and current_fill != "none"
                )
                if tail_visible:
                    if segments is not None:
                        segments.append(tail)
                    tx, ty = _apply(current_transform, *(position or (0.0, 0.0)))
                    positioned.append((tail, tx, ty))
                else:
                    defects.append(f"invisible text: {tail!r}")

    visit(root, 1.0, 1.0, IDENTITY, None, "black", True, True, None)
    populated = [("".join(segments), segments) for _, segments in nodes if segments]
    return populated, defects, positioned


def _audit_safe_area(positioned: Iterable[tuple[str, float, float]]) -> list[str]:
    left, top, right, bottom = SAFE_AREA
    outside = [text for text, x, y in positioned if not (left <= x <= right and top <= y <= bottom)]
    return [f"{len(outside)} visible text segment(s) outside safe area: {outside[:4]}"] if outside else []


def _audit_text_values(
    visible_nodes: Sequence[tuple[str, list[str]]],
    *,
    required_text: Sequence[str],
    allowed_text: Sequence[str],
    allowed_text_groups: Sequence[Sequence[str]],
    derived_text_patterns: Sequence[str],
) -> list[str]:
    defects: list[str] = []
    node_texts = [_normalized(text) for text, _ in visible_nodes if _normalized(text)]
    for expected in required_text:
        normalized = _normalized(expected)
        if normalized and not any(normalized in node for node in node_texts):
            defects.append(f"missing required visible text: {expected}")

    groups = [
        [_normalized(text) for text in group if _normalized(text)]
        for group in allowed_text_groups
    ] if allowed_text_groups else [[_normalized(text)] for text in allowed_text if _normalized(text)]
    unexpected: list[str] = []
    for text, _ in visible_nodes:
        normalized = _normalized(text)
        is_source_composition = any(_matches_ordered_group(normalized, group) for group in groups)
        is_derived = any(re.fullmatch(pattern, normalized) for pattern in derived_text_patterns)
        if normalized and not (is_source_composition or is_derived):
            unexpected.append(text)
    if unexpected:
        defects.append(f"unexpected visible text: {unexpected[:6]}")
    return defects


def _matches_ordered_group(value: str, group: Sequence[str]) -> bool:
    if not value:
        return False
    reachable = {0}
    for source in group:
        next_reachable = set(reachable)
        for start in reachable:
            if value.startswith(source, start):
                next_reachable.add(start + len(source))
        reachable = next_reachable
    return len(value) in reachable


def _audit_card_geometry(
    root: ET.Element,
    card_pairs: Sequence[tuple[str, str]],
) -> list[str]:
    if not card_pairs:
        return []
    cards: list[tuple[float, float, float, float]] = []
    matched_groups: set[int] = set()
    top_groups = [child for child in root if _local_name(child) == "g"]

    for primary, secondary in card_pairs:
        match: tuple[int, tuple[float, float, float, float]] | None = None
        for index, group in enumerate(top_groups):
            text = "".join(_normalized(value) for value in group.itertext())
            if _normalized(primary) not in text or _normalized(secondary) not in text:
                continue
            boxes = [
                box for box in _rect_boxes_in_group(group, _parse_transform(root.get("transform", "")))
                if _meaningful_card(box)
            ]
            box = max(boxes, key=_box_area, default=None)
            if box is not None:
                match = (index, box)
                break
        if match is None:
            return [f"missing card geometry containing {primary!r} and its description"]
        matched_groups.add(match[0])
        cards.append(match[1])

    if len(matched_groups) != len(card_pairs):
        return ["comparison items do not occupy distinct card groups"]
    ordered = sorted(cards)
    for left, right in zip(ordered, ordered[1:]):
        if left[2] > right[0]:
            return ["comparison card geometry overlaps horizontally"]
    return []


def _rect_boxes_in_group(group: ET.Element, parent_transform: Matrix) -> list[tuple[float, float, float, float]]:
    boxes: list[tuple[float, float, float, float]] = []

    def visit(
        element: ET.Element,
        transform: Matrix,
        opacity: float,
        displayed: bool,
        visible: bool,
        inherited_fill: str | None,
        inherited_stroke: str | None,
    ) -> None:
        current = _multiply(transform, _parse_transform(element.get("transform", "")))
        current_opacity = opacity * _number(element.get("opacity"), 1.0)
        current_displayed = displayed and element.get("display", "").strip().lower() != "none"
        visibility = element.get("visibility", "").strip().lower()
        if visibility == "visible":
            current_visible = True
        elif visibility in {"hidden", "collapse"}:
            current_visible = False
        else:
            current_visible = visible
        current_fill = element.get("fill") or inherited_fill
        current_stroke = element.get("stroke") or inherited_stroke
        painted = current_fill not in {None, "none"} or current_stroke not in {None, "none"}
        fill_opacity = _number(element.get("fill-opacity"), 1.0)
        stroke_opacity = _number(element.get("stroke-opacity"), 1.0)
        paint_opacity = max(fill_opacity if current_fill != "none" else 0.0, stroke_opacity if current_stroke != "none" else 0.0)
        if (
            _local_name(element) == "rect"
            and current_displayed
            and current_visible
            and painted
            and current_opacity * paint_opacity >= MIN_VISIBLE_OPACITY
        ):
            box = _rect_box(element, current)
            if box is not None:
                boxes.append(box)
        for child in element:
            visit(
                child,
                current,
                current_opacity,
                current_displayed,
                current_visible,
                current_fill,
                current_stroke,
            )

    visit(group, parent_transform, 1.0, True, True, None, None)
    return boxes


def _box_area(box: tuple[float, float, float, float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _meaningful_card(box: tuple[float, float, float, float]) -> bool:
    left, top, right, bottom = box
    return right - left >= 120 and bottom - top >= 120


def _rect_box(rect: ET.Element, transform: Matrix) -> tuple[float, float, float, float] | None:
    x = _number(rect.get("x"), 0.0)
    y = _number(rect.get("y"), 0.0)
    width = _number(rect.get("width"), 0.0)
    height = _number(rect.get("height"), 0.0)
    if width <= 0 or height <= 0:
        return None
    corners = [
        _apply(transform, x, y),
        _apply(transform, x + width, y),
        _apply(transform, x, y + height),
        _apply(transform, x + width, y + height),
    ]
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    return min(xs), min(ys), max(xs), max(ys)


def _parse_transform(value: str) -> Matrix:
    result = IDENTITY
    for name, raw in re.findall(r"([A-Za-z]+)\s*\(([^)]*)\)", value or ""):
        values = [_number(item, 0.0) for item in re.split(r"[\s,]+", raw.strip()) if item]
        if name == "translate" and values:
            matrix = (1.0, 0.0, 0.0, 1.0, values[0], values[1] if len(values) > 1 else 0.0)
        elif name == "scale" and values:
            matrix = (values[0], 0.0, 0.0, values[1] if len(values) > 1 else values[0], 0.0, 0.0)
        elif name == "matrix" and len(values) == 6:
            matrix = tuple(values)  # type: ignore[assignment]
        else:
            continue
        result = _multiply(result, matrix)
    return result


def _multiply(left: Matrix, right: Matrix) -> Matrix:
    a, b, c, d, e, f = left
    g, h, i, j, k, l = right
    return (
        a * g + c * h,
        b * g + d * h,
        a * i + c * j,
        b * i + d * j,
        a * k + c * l + e,
        b * k + d * l + f,
    )


def _apply(matrix: Matrix, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    return a * x + c * y + e, b * x + d * y + f


def _coordinate(value: str | None, default: float) -> float:
    if not value:
        return default
    first = re.split(r"[\s,]+", value.strip())[0]
    return _number(first, default)


def _number(value: str | None, default: float) -> float:
    if value is None:
        return default
    match = re.match(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", str(value).strip())
    return float(match.group(0)) if match else default


def _normalized(value: str) -> str:
    return re.sub(r"[\s（）()]", "", value or "").strip()


def _dominant_pixel(pixels: Sequence[bytes]) -> bytes:
    """Return the dominant rendered color, tolerating antialias variants."""
    return Counter(pixels).most_common(1)[0][0]


def _color_distance(left: bytes, right: bytes) -> float:
    return sum((a - b) ** 2 for a, b in zip(left[:3], right[:3])) ** 0.5


def _browser_text_geometry(
    browser: str,
    svg: str,
    html_path: Path,
    bounds: tuple[float, float, float, float],
    card_pairs: Sequence[tuple[str, str]],
) -> tuple[list[str], list[dict]]:
    geometry_path = html_path.with_suffix(".geometry.html")
    script = """<script>
    const svg = document.querySelector('svg');
    const svgRect = svg.getBoundingClientRect();
    const bounds = [...document.querySelectorAll('svg text')].map((node) => {
      const rect = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      let ancestor = node;
      let hasClipOrMask = false;
      while (ancestor && ancestor !== svg) {
        const ancestorStyle = getComputedStyle(ancestor);
        if (ancestorStyle.clipPath !== 'none' || ancestorStyle.maskImage !== 'none'
            || ancestor.getAttribute('clip-path') || ancestor.getAttribute('mask')) {
          hasClipOrMask = true;
          break;
        }
        ancestor = ancestor.parentElement;
      }
      const opacity = Number(style.opacity);
      const fillOpacity = Number(style.fillOpacity);
      const visible = style.display !== 'none' && style.visibility !== 'hidden'
        && opacity >= 0.1 && fillOpacity >= 0.1 && style.fill !== 'none';
      const intersection = Math.max(0, Math.min(rect.right, svgRect.right) - Math.max(rect.left, svgRect.left))
        * Math.max(0, Math.min(rect.bottom, svgRect.bottom) - Math.max(rect.top, svgRect.top));
      let group = node.parentElement;
      while (group && group.parentElement !== svg) group = group.parentElement;
      const rects = group ? [...group.querySelectorAll('rect')]
        .filter((item) => {
          const rectStyle = getComputedStyle(item);
          const painted = rectStyle.fill !== 'none' || rectStyle.stroke !== 'none';
          return rectStyle.display !== 'none' && rectStyle.visibility !== 'hidden'
            && Number(rectStyle.opacity) >= 0.1 && painted
            && Math.max(Number(rectStyle.fillOpacity), Number(rectStyle.strokeOpacity)) >= 0.1;
        })
        .map((item) => item.getBoundingClientRect()) : [];
      const card = rects.sort((a, b) => b.width * b.height - a.width * a.height)[0];
      return {text: node.textContent.trim(), left: rect.left, top: rect.top,
              right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height,
              visible, hasClipOrMask, intersection, area: rect.width * rect.height,
              groupText: group ? group.textContent.trim() : '',
              groupId: group ? group.id : '',
              card: card ? {left: card.left, top: card.top, right: card.right, bottom: card.bottom} : null};
    });
    document.body.textContent = JSON.stringify(bounds);
    </script>"""
    geometry_path.write_text(
        '<!doctype html><meta charset="utf-8">'
        '<style>html,body{margin:0;width:1280px;height:720px;overflow:hidden}'
        'svg{width:1280px;height:720px;display:block}</style>'
        + svg
        + script,
        encoding="utf-8",
    )
    try:
        completed = subprocess.run(
            [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--dump-dom",
                geometry_path.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"Chrome geometry check failed: {exc.__class__.__name__}: {exc}"], []
    match = re.search(r"<body>(.*?)</body>", completed.stdout, re.DOTALL | re.IGNORECASE)
    if not match:
        return ["Chrome geometry check returned no body payload"], []
    try:
        entries = json.loads(html.unescape(match.group(1)))
    except (json.JSONDecodeError, TypeError) as exc:
        return [f"Chrome geometry payload is invalid: {exc}"], []
    if not isinstance(entries, list) or not entries:
        return ["Chrome geometry found no visible text nodes"], []
    left, top, right, bottom = bounds
    clipped = [
        entry.get("text", "")
        for entry in entries
        if not isinstance(entry, dict)
        or not entry.get("visible")
        or float(entry.get("width", 0)) <= 0
        or float(entry.get("height", 0)) <= 0
        or float(entry.get("intersection", 0)) < float(entry.get("area", 0)) * 0.98
        or float(entry.get("left", 0)) < left
        or float(entry.get("top", 0)) < top
        or float(entry.get("right", 0)) > right
        or float(entry.get("bottom", 0)) > bottom
    ]
    if clipped:
        return [f"Chrome text not visibly painted or clipped: {clipped[:4]}"], entries
    if card_pairs:
        containment = []
        rendered_cards: list[dict] = []
        for primary, secondary in card_pairs:
            matching = [
                entry for entry in entries
                if _normalized(primary) in _normalized(entry.get("groupText", ""))
                and _normalized(secondary) in _normalized(entry.get("groupText", ""))
            ]
            if not matching:
                containment.append(primary)
                continue
            card = matching[0].get("card")
            group_id = matching[0].get("groupId")
            if card and group_id and all(item.get("groupId") != group_id for item in rendered_cards):
                rendered_cards.append({"groupId": group_id, "box": card})
            for entry in matching:
                if not card or not _bbox_contains(card, entry):
                    containment.append(primary)
                    break
        if containment:
            return [f"Chrome card content escapes card geometry: {containment[:4]}"], entries
        for index, left_card in enumerate(rendered_cards):
            for right_card in rendered_cards[index + 1 :]:
                if _bbox_overlaps(left_card["box"], right_card["box"]):
                    groups = [left_card["groupId"], right_card["groupId"]]
                    return [f"Chrome card geometry overlaps: {groups}"], entries
    return [], entries


def _audit_text_pixel_effect(
    browser: str,
    svg: str,
    html_path: Path,
    rendered_rows: list[list[bytes]],
    entries: Sequence[dict],
) -> list[str]:
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        return [f"cannot build no-text render control: {exc}"]
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    for text in root.iter(f"{SVG_NS}text"):
        text.set("visibility", "hidden")
    try:
        control_rows = _render_svg_rows(
            browser,
            ET.tostring(root, encoding="unicode"),
            html_path.with_suffix(".no-text.html"),
            html_path.with_suffix(".no-text.png"),
        )
    except (OSError, ValueError, zlib.error, subprocess.SubprocessError) as exc:
        return [f"Chrome no-text control render failed: {exc.__class__.__name__}: {exc}"]

    clipped_counts = _text_pixel_counts(rendered_rows, control_rows, entries)
    invisible = [
        str(entry.get("text", ""))
        for entry, changed in zip(entries, clipped_counts)
        if changed < 3
    ]
    if invisible:
        return [f"Chrome text has no rendered pixel effect; not visibly painted: {invisible[:4]}"]

    affected = [index for index, entry in enumerate(entries) if entry.get("hasClipOrMask")]
    if not affected:
        return []
    try:
        unclipped_root = ET.fromstring(svg)
        for element in unclipped_root.iter():
            element.attrib.pop("clip-path", None)
            element.attrib.pop("mask", None)
        unclipped_rows = _render_svg_rows(
            browser,
            ET.tostring(unclipped_root, encoding="unicode"),
            html_path.with_suffix(".unclipped.html"),
            html_path.with_suffix(".unclipped.png"),
        )
        for text in unclipped_root.iter(f"{SVG_NS}text"):
            text.set("visibility", "hidden")
        unclipped_control_rows = _render_svg_rows(
            browser,
            ET.tostring(unclipped_root, encoding="unicode"),
            html_path.with_suffix(".unclipped-no-text.html"),
            html_path.with_suffix(".unclipped-no-text.png"),
        )
    except (OSError, ValueError, zlib.error, subprocess.SubprocessError) as exc:
        return [f"Chrome unclipped control render failed: {exc.__class__.__name__}: {exc}"]

    unclipped_counts = _text_pixel_counts(unclipped_rows, unclipped_control_rows, entries)
    mostly_clipped = [
        str(entries[index].get("text", ""))
        for index in affected
        if unclipped_counts[index] >= 3
        and clipped_counts[index] / unclipped_counts[index] < MIN_TEXT_PIXEL_RETENTION
    ]
    if mostly_clipped:
        return [f"Chrome text is mostly clipped: {mostly_clipped[:4]}"]
    return []



def _render_svg_rows(
    browser: str,
    svg: str,
    html_path: Path,
    png_path: Path,
) -> list[list[bytes]]:
    html_path.write_text(
        '<!doctype html><meta charset="utf-8">'
        '<style>html,body{margin:0;width:1280px;height:720px;overflow:hidden;background:#000}'
        'svg{width:1280px;height:720px;display:block}</style>'
        + svg,
        encoding="utf-8",
    )
    subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            f"--screenshot={png_path.resolve()}",
            "--window-size=1280,720",
            html_path.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )
    _, _, rows = _decode_png(png_path)
    return rows



def _text_pixel_counts(
    rendered_rows: Sequence[Sequence[bytes]],
    control_rows: Sequence[Sequence[bytes]],
    entries: Sequence[dict],
) -> list[int]:
    height = len(rendered_rows)
    width = len(rendered_rows[0]) if rendered_rows else 0
    counts: list[int] = []
    for entry in entries:
        left = max(0, int(float(entry.get("left", 0))) - 1)
        top = max(0, int(float(entry.get("top", 0))) - 1)
        right = min(width, int(float(entry.get("right", 0))) + 2)
        bottom = min(height, int(float(entry.get("bottom", 0))) + 2)
        counts.append(sum(
            1
            for y in range(top, bottom)
            for x in range(left, right)
            if rendered_rows[y][x] != control_rows[y][x]
        ))
    return counts


def _bbox_overlaps(left: dict, right: dict, tolerance: float = 1.0) -> bool:
    overlap_width = min(float(left.get("right", 0)), float(right.get("right", 0))) - max(
        float(left.get("left", 0)), float(right.get("left", 0))
    )
    overlap_height = min(float(left.get("bottom", 0)), float(right.get("bottom", 0))) - max(
        float(left.get("top", 0)), float(right.get("top", 0))
    )
    return overlap_width > tolerance and overlap_height > tolerance



def _bbox_contains(card: dict, text: dict, padding: float = 2.0) -> bool:
    return (
        float(text.get("left", 0)) >= float(card.get("left", 0)) - padding
        and float(text.get("top", 0)) >= float(card.get("top", 0)) - padding
        and float(text.get("right", 0)) <= float(card.get("right", 0)) + padding
        and float(text.get("bottom", 0)) <= float(card.get("bottom", 0)) + padding
    )


def _find_browser() -> str | None:
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def _decode_png(path: Path) -> tuple[int, int, list[list[bytes]]]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("missing PNG signature")
    offset = 8
    width = height = color_type = bit_depth = 0
    compressed = bytearray()
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", payload[:10])
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
    channels = {2: 3, 6: 4}.get(color_type)
    if bit_depth != 8 or channels is None or width <= 0 or height <= 0:
        raise ValueError(f"unsupported PNG format: depth={bit_depth}, color_type={color_type}")
    raw = zlib.decompress(bytes(compressed))
    stride = width * channels
    rows: list[list[bytes]] = []
    previous = bytearray(stride)
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        scanline = bytearray(raw[cursor : cursor + stride])
        cursor += stride
        _unfilter(scanline, previous, channels, filter_type)
        rows.append([bytes(scanline[x : x + channels]) for x in range(0, stride, channels)])
        previous = scanline
    return width, height, rows


def _unfilter(row: bytearray, previous: bytearray, channels: int, filter_type: int) -> None:
    for index in range(len(row)):
        left = row[index - channels] if index >= channels else 0
        above = previous[index]
        upper_left = previous[index - channels] if index >= channels else 0
        if filter_type == 1:
            row[index] = (row[index] + left) & 0xFF
        elif filter_type == 2:
            row[index] = (row[index] + above) & 0xFF
        elif filter_type == 3:
            row[index] = (row[index] + ((left + above) // 2)) & 0xFF
        elif filter_type == 4:
            row[index] = (row[index] + _paeth(left, above, upper_left)) & 0xFF
        elif filter_type != 0:
            raise ValueError(f"unsupported PNG filter: {filter_type}")


def _paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    distances = (abs(estimate - left), abs(estimate - above), abs(estimate - upper_left))
    return (left, above, upper_left)[distances.index(min(distances))]


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""
