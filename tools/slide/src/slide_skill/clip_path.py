"""SVG clip-path and mask conversion to DrawingML customGeometry clipping."""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from .geometry import parse_svg_path, parse_svg_points, points_to_commands


def collect_clip_paths(svg_root: ET.Element, parent_map: dict | None = None) -> dict[str, dict]:
    clips: dict[str, dict] = {}
    defs = svg_root.find(".//{http://www.w3.org/2000/svg}defs")
    if defs is None:
        for elem in svg_root.iter():
            if _local(elem.tag) == "defs":
                defs = elem
                break
    if defs is None:
        return clips
    for elem in defs:
        tag = _local(elem.tag)
        if tag == "clipPath":
            cid = elem.attrib.get("id", "")
            if cid:
                clips[cid] = _parse_clip_path(elem)
        elif tag == "mask":
            mid = elem.attrib.get("id", "")
            if mid:
                clips[mid] = _parse_mask(elem)
    return clips


def _parse_clip_path(elem: ET.Element) -> dict:
    children = list(elem)
    if not children:
        return {"type": "clipPath", "commands": []}
    first = children[0]
    tag = _local(first.tag)
    commands = _element_to_commands(first, tag)
    return {"type": "clipPath", "commands": commands}


def _parse_mask(elem: ET.Element) -> dict:
    children = list(elem)
    if not children:
        return {"type": "mask", "commands": []}
    first = children[0]
    tag = _local(first.tag)
    commands = _element_to_commands(first, tag)
    return {"type": "mask", "commands": commands}


def _element_to_commands(elem: ET.Element, tag: str) -> list:
    from .converters import safe_float

    if tag == "path":
        d = elem.attrib.get("d", "")
        if d.strip():
            return parse_svg_path(d)
    elif tag in ("polygon", "polyline"):
        pts = parse_svg_points(elem.attrib.get("points", ""))
        closed = tag == "polygon"
        return points_to_commands(pts, closed=closed)
    elif tag == "rect":
        x = safe_float(elem.attrib.get("x", "0"))
        y = safe_float(elem.attrib.get("y", "0"))
        w = safe_float(elem.attrib.get("width", "0"))
        h = safe_float(elem.attrib.get("height", "0"))
        return [
            ("M", x, y), ("L", x + w, y), ("L", x + w, y + h),
            ("L", x, y + h), ("Z",),
        ]
    elif tag == "circle":
        cx = safe_float(elem.attrib.get("cx", "0"))
        cy = safe_float(elem.attrib.get("cy", "0"))
        r = safe_float(elem.attrib.get("r", "0"))
        return _circle_to_commands(cx, cy, r)
    elif tag == "ellipse":
        cx = safe_float(elem.attrib.get("cx", "0"))
        cy = safe_float(elem.attrib.get("cy", "0"))
        rx = safe_float(elem.attrib.get("rx", "0"))
        ry = safe_float(elem.attrib.get("ry", "0"))
        return _ellipse_to_commands(cx, cy, rx, ry)
    return []


def _circle_to_commands(cx: float, cy: float, r: float) -> list:
    import math
    n = 24
    cmds = [("M", cx + r, cy)]
    for i in range(1, n):
        angle = 2 * math.pi * i / n
        cmds.append(("L", cx + r * math.cos(angle), cy + r * math.sin(angle)))
    cmds.append(("Z",))
    return cmds


def _ellipse_to_commands(cx: float, cy: float, rx: float, ry: float) -> list:
    import math
    n = 24
    cmds = [("M", cx + rx, cy)]
    for i in range(1, n):
        angle = 2 * math.pi * i / n
        cmds.append(("L", cx + rx * math.cos(angle), cy + ry * math.sin(angle)))
    cmds.append(("Z",))
    return cmds


def resolve_clip_path(attr_value: str, clips: dict[str, dict]) -> dict | None:
    m = re.match(r'url\(#([^)]+)\)', attr_value.strip())
    if not m:
        return None
    cid = m.group(1)
    return clips.get(cid)


def apply_clip_path_to_shape(shape, clip: dict, scale_x: float, scale_y: float) -> None:
    from .geometry import build_freeform_xml, compute_bbox, EMU_PER_INCH
    from pptx.oxml.ns import qn
    from lxml import etree

    commands = clip.get("commands", [])
    if not commands:
        return

    min_x, min_y, max_x, max_y = compute_bbox(commands)
    bbox_w = max(max_x - min_x, 0.01)
    bbox_h = max(max_y - min_y, 0.01)

    sp = shape._element
    spPr = sp.spPr

    existing = spPr.find(qn("a:clipPath"))
    if existing is not None:
        spPr.remove(existing)

    w_emu = int(bbox_w * scale_x * EMU_PER_INCH)
    h_emu = int(bbox_h * scale_y * EMU_PER_INCH)
    cust_geom = build_freeform_xml(
        commands, w_emu, h_emu, min_x, min_y, scale_x, scale_y
    )

    clipPath = etree.SubElement(spPr, qn("a:clipPath"))
    clipPath.set("pref", "1")
    path_elem = etree.SubElement(clipPath, qn("a:path"))
    path_elem.set("w", str(w_emu))
    path_elem.set("h", str(h_emu))

    for child in list(cust_geom):
        if _local(child.tag) == "avLst":
            continue
        path_elem.append(child)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
