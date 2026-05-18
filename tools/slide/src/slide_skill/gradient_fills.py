"""SVG gradient fill conversion to DrawingML gradFill."""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET


def collect_gradients(svg_root: ET.Element) -> dict[str, dict]:
    gradients: dict[str, dict] = {}
    defs = svg_root.find(".//{http://www.w3.org/2000/svg}defs")
    if defs is None:
        for elem in svg_root.iter():
            if _local(elem.tag) == "defs":
                defs = elem
                break
    if defs is None:
        return gradients
    for elem in defs:
        tag = _local(elem.tag)
        if tag == "linearGradient":
            gid = elem.attrib.get("id", "")
            if gid:
                gradients[gid] = _parse_linear(elem)
        elif tag == "radialGradient":
            gid = elem.attrib.get("id", "")
            if gid:
                gradients[gid] = _parse_radial(elem)
    return gradients


def _parse_linear(elem: ET.Element) -> dict:
    stops = _parse_stops(elem)
    x1 = _percent(elem.attrib.get("x1", "0%"))
    y1 = _percent(elem.attrib.get("y1", "0%"))
    x2 = _percent(elem.attrib.get("x2", "100%"))
    y2 = _percent(elem.attrib.get("y2", "0%"))
    angle = _linear_angle(x1, y1, x2, y2)
    return {
        "type": "linear",
        "angle": angle,
        "stops": stops,
        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
    }


def _parse_radial(elem: ET.Element) -> dict:
    stops = _parse_stops(elem)
    cx = _percent(elem.attrib.get("cx", "50%"))
    cy = _percent(elem.attrib.get("cy", "50%"))
    r = _percent(elem.attrib.get("r", "50%"))
    fx = _percent(elem.attrib.get("fx", f"{int(cx*100)}%"))
    fy = _percent(elem.attrib.get("fy", f"{int(cy*100)}%"))
    return {
        "type": "radial",
        "cx": cx, "cy": cy, "r": r,
        "fx": fx, "fy": fy,
        "stops": stops,
    }


def _parse_stops(elem: ET.Element) -> list[dict]:
    stops: list[dict] = []
    for child in elem:
        if _local(child.tag) == "stop":
            offset = _percent(child.attrib.get("offset", "0%"))
            color = child.attrib.get("stop-color", "#000000")
            opacity = float(child.attrib.get("stop-opacity", "1"))
            stops.append({"offset": offset, "color": color, "opacity": opacity})
    if not stops:
        stops = [{"offset": 0.0, "color": "#000000", "opacity": 1.0}, {"offset": 1.0, "color": "#FFFFFF", "opacity": 1.0}]
    return stops


def resolve_gradient_fill(fill_attr: str, gradients: dict[str, dict]) -> dict | None:
    m = re.match(r'url\(#([^)]+)\)', fill_attr.strip())
    if not m:
        return None
    gid = m.group(1)
    return gradients.get(gid)


def apply_gradient_to_shape(shape, gradient: dict, rgb_cls) -> None:
    from pptx.oxml.ns import qn
    gfill_type = gradient.get("type", "linear")
    stops = gradient.get("stops", [])
    if not stops:
        return
    fill = shape.fill
    fill.gradient()
    gfill = fill._fill._gradFill
    if gfill_type == "linear":
        _apply_linear_xml(gfill, gradient, rgb_cls)
    elif gfill_type == "radial":
        _apply_radial_xml(gfill, gradient, rgb_cls)


def _apply_linear_xml(gfill, gradient: dict, rgb_cls) -> None:
    from pptx.oxml.ns import qn
    from lxml import etree
    gsLst = etree.SubElement(gfill, qn("a:gsLst"))
    for stop in gradient.get("stops", []):
        gs = etree.SubElement(gsLst, qn("a:gs"))
        pos = int(stop["offset"] * 100000)
        gs.set("pos", str(pos))
        srgb = etree.SubElement(gs, qn("a:srgbClr"))
        hex_color = stop["color"].lstrip("#")
        if len(hex_color) == 3:
            hex_color = hex_color[0]*2 + hex_color[1]*2 + hex_color[2]*2
        srgb.set("val", hex_color.upper())
        if stop.get("opacity", 1.0) < 1.0:
            alpha = etree.SubElement(srgb, qn("a:alpha"))
            alpha.set("val", str(int(stop["opacity"] * 100000)))
    lin = etree.SubElement(gfill, qn("a:lin"))
    angle = gradient.get("angle", 0)
    lin.set("ang", str(int(angle * 60000)))
    lin.set("scaled", "1")


def _apply_radial_xml(gfill, gradient: dict, rgb_cls) -> None:
    from pptx.oxml.ns import qn
    from lxml import etree
    gsLst = etree.SubElement(gfill, qn("a:gsLst"))
    for stop in gradient.get("stops", []):
        gs = etree.SubElement(gsLst, qn("a:gs"))
        pos = int(stop["offset"] * 100000)
        gs.set("pos", str(pos))
        srgb = etree.SubElement(gs, qn("a:srgbClr"))
        hex_color = stop["color"].lstrip("#")
        if len(hex_color) == 3:
            hex_color = hex_color[0]*2 + hex_color[1]*2 + hex_color[2]*2
        srgb.set("val", hex_color.upper())
        if stop.get("opacity", 1.0) < 1.0:
            alpha = etree.SubElement(srgb, qn("a:alpha"))
            alpha.set("val", str(int(stop["opacity"] * 100000)))
    path_elem = etree.SubElement(gfill, qn("a:path"))
    path_elem.set("path", "circle")
    fillToRect = etree.SubElement(path_elem, qn("a:fillToRect"))
    fillToRect.set("l", "50000")
    fillToRect.set("t", "50000")
    fillToRect.set("r", "50000")
    fillToRect.set("b", "50000")


def _linear_angle(x1: float, y1: float, x2: float, y2: float) -> float:
    import math
    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) < 0.001 and abs(dy) < 0.001:
        return 0.0
    angle_rad = math.atan2(dx, dy)
    angle_deg = math.degrees(angle_rad)
    return angle_deg % 360


def _percent(value: str) -> float:
    value = value.strip()
    if value.endswith("%"):
        return float(value[:-1]) / 100.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
