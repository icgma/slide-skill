"""SVG pattern fill conversion to DrawingML blipFill with tiling."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET


def collect_patterns(svg_root: ET.Element) -> dict[str, dict]:
    patterns: dict[str, dict] = {}
    defs = svg_root.find(".//{http://www.w3.org/2000/svg}defs")
    if defs is None:
        for elem in svg_root.iter():
            if _local(elem.tag) == "defs":
                defs = elem
                break
    if defs is None:
        return patterns
    for elem in defs:
        if _local(elem.tag) == "pattern":
            pid = elem.attrib.get("id", "")
            if pid:
                patterns[pid] = _parse_pattern(elem)
    return patterns


def _parse_pattern(elem: ET.Element) -> dict:
    width = _length(elem.attrib.get("width", "10"))
    height = _length(elem.attrib.get("height", "10"))
    x = _length(elem.attrib.get("x", "0"))
    y = _length(elem.attrib.get("y", "0"))
    patternUnits = elem.attrib.get("patternUnits", "objectBoundingBox")
    patternContentUnits = elem.attrib.get("patternContentUnits", "userSpaceOnUse")
    children_xml = _serialize_children(elem)
    return {
        "type": "pattern",
        "width": width,
        "height": height,
        "x": x,
        "y": y,
        "patternUnits": patternUnits,
        "patternContentUnits": patternContentUnits,
        "children_xml": children_xml,
    }


def _serialize_children(elem: ET.Element) -> str:
    parts: list[str] = []
    for child in elem:
        parts.append(_serialize_element(child))
    return "".join(parts)


def _serialize_element(elem: ET.Element) -> str:
    tag = _local(elem.tag)
    attrs = " ".join(f'{k}="{v}"' for k, v in elem.attrib.items())
    inner = _serialize_children(elem)
    text = elem.text or ""
    tail = ""
    if attrs:
        return f"<{tag} {attrs}>{text}{inner}</{tag}>"
    return f"<{tag}>{text}{inner}</{tag}>"


def resolve_pattern_fill(fill_attr: str, patterns: dict[str, dict]) -> dict | None:
    m = re.match(r'url\(#([^)]+)\)', fill_attr.strip())
    if not m:
        return None
    pid = m.group(1)
    return patterns.get(pid)


def render_pattern_image(pattern: dict, dpi: int = 150) -> Path | None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    w = max(int(pattern["width"] * dpi / 96), 4)
    h = max(int(pattern["height"] * dpi / 96), 4)
    img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    children_xml = pattern.get("children_xml", "")
    _draw_pattern_children(draw, children_xml, w, h)

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False, prefix="pattern_")
    img.save(tmp.name, "PNG")
    return Path(tmp.name)


def _draw_pattern_children(draw, xml: str, w: int, h: int) -> None:
    try:
        root = ET.fromstring(f"<root>{xml}</root>")
    except ET.ParseError:
        return
    for elem in root:
        tag = _local(elem.tag)
        if tag == "rect":
            _draw_rect(draw, elem)
        elif tag == "circle":
            _draw_circle(draw, elem)
        elif tag == "line":
            _draw_line(draw, elem)


def _draw_rect(draw, elem: ET.Element) -> None:
    x = _length(elem.attrib.get("x", "0"))
    y = _length(elem.attrib.get("y", "0"))
    w = _length(elem.attrib.get("width", "0"))
    h = _length(elem.attrib.get("height", "0"))
    fill = elem.attrib.get("fill", "none")
    color = _svg_color_to_rgb(fill)
    stroke = elem.attrib.get("stroke")
    if color:
        draw.rectangle([x, y, x + w, y + h], fill=color)
    if stroke and stroke != "none":
        stroke_color = _svg_color_to_rgb(stroke)
        if stroke_color:
            draw.rectangle([x, y, x + w, y + h], outline=stroke_color)


def _draw_circle(draw, elem: ET.Element) -> None:
    cx = _length(elem.attrib.get("cx", "0"))
    cy = _length(elem.attrib.get("cy", "0"))
    r = _length(elem.attrib.get("r", "0"))
    fill = elem.attrib.get("fill", "none")
    color = _svg_color_to_rgb(fill)
    if color and r > 0:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)


def _draw_line(draw, elem: ET.Element) -> None:
    x1 = _length(elem.attrib.get("x1", "0"))
    y1 = _length(elem.attrib.get("y1", "0"))
    x2 = _length(elem.attrib.get("x2", "0"))
    y2 = _length(elem.attrib.get("y2", "0"))
    stroke = elem.attrib.get("stroke", "#000000")
    color = _svg_color_to_rgb(stroke)
    if color:
        draw.line([x1, y1, x2, y2], fill=color, width=1)


def _svg_color_to_rgb(value: str) -> tuple | None:
    if not value or value == "none":
        return None
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = value[0] * 2 + value[1] * 2 + value[2] * 2
    if len(value) != 6:
        return None
    try:
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    except ValueError:
        return None


def apply_pattern_to_shape(shape, pattern: dict, rgb_cls) -> None:
    image_path = render_pattern_image(pattern)
    if image_path is None or not image_path.exists():
        return

    try:
        from pptx.oxml.ns import qn
        from lxml import etree

        sp = shape._element
        spPr = sp.spPr

        for child in list(spPr):
            tag_local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag_local in ("solidFill", "gradFill", "blipFill", "noFill", "pattFill"):
                spPr.remove(child)

        rId = _add_image_relationship(sp, image_path)

        blipFill = etree.SubElement(spPr, qn("a:blipFill"))
        blip = etree.SubElement(blipFill, qn("a:blip"))
        blip.set(qn("r:embed"), rId)
        tile = etree.SubElement(blipFill, qn("a:tile"))
        tx = int(pattern.get("x", 0) * 914400)
        ty = int(pattern.get("y", 0) * 914400)
        if tx:
            tile.set("tx", str(tx))
        if ty:
            tile.set("ty", str(ty))
    except Exception:
        pass


def _add_image_relationship(sp, image_path: Path) -> str:
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    part = sp.getparent()
    while part is not None:
        if hasattr(part, "part"):
            part = part.part
            break
        part = part.getparent()
    if part is None:
        return "rId1"
    rel = part.relate_to(str(image_path), RT.IMAGE)
    return rel


def _length(value: str) -> float:
    value = value.strip()
    if value.endswith("px"):
        return float(value[:-2])
    if value.endswith("pt"):
        return float(value[:-2]) * 1.333
    try:
        return float(value)
    except ValueError:
        return 0.0


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
