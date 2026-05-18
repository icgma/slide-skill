"""SVG filter effects conversion to DrawingML effectLst (blur + shadow)."""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET


def collect_filters(svg_root: ET.Element) -> dict[str, dict]:
    filters: dict[str, dict] = {}
    defs = svg_root.find(".//{http://www.w3.org/2000/svg}defs")
    if defs is None:
        for elem in svg_root.iter():
            if _local(elem.tag) == "defs":
                defs = elem
                break
    if defs is None:
        return filters
    for elem in defs:
        if _local(elem.tag) == "filter":
            fid = elem.attrib.get("id", "")
            if fid:
                filters[fid] = _parse_filter(elem)
    return filters


EFFECT_ORDER = [
    "blur", "fillOverlay", "glow", "innerShdw",
    "outerShdw", "prstShdw", "reflection", "softEdge",
]


def _parse_filter(elem: ET.Element) -> dict:
    blur = None
    shadow = None
    offset = None
    flood_color = "000000"
    flood_opacity = 1.0
    has_composite_in = False
    composite_in2 = None
    blur_in = None
    blur_result = None
    offset_result = None

    for child in elem:
        tag = _local(child.tag)
        if tag == "feGaussianBlur":
            std = child.attrib.get("stdDeviation", "0")
            try:
                parts = std.replace(",", " ").split()
                val = max(float(parts[0]), float(parts[1]) if len(parts) > 1 else float(parts[0]))
            except (ValueError, IndexError):
                val = 0.0
            blur = {"stdDeviation": val}
            blur_in = child.attrib.get("in", "")
            blur_result = child.attrib.get("result", "")
        elif tag == "feDropShadow":
            dx = float(child.attrib.get("dx", "0"))
            dy = float(child.attrib.get("dy", "0"))
            std = child.attrib.get("stdDeviation", "0")
            try:
                parts = std.replace(",", " ").split()
                sv = max(float(parts[0]), float(parts[1]) if len(parts) > 1 else float(parts[0]))
            except (ValueError, IndexError):
                sv = 0.0
            fc = child.attrib.get("flood-color", "#000000")
            fo = child.attrib.get("flood-opacity", "1")
            shadow = {
                "dx": dx, "dy": dy, "stdDeviation": sv,
                "flood_color": _normalize_color(fc),
                "flood_opacity": float(fo),
            }
        elif tag == "feOffset":
            dx = float(child.attrib.get("dx", "0"))
            dy = float(child.attrib.get("dy", "0"))
            offset = {"dx": dx, "dy": dy}
            offset_result = child.attrib.get("result", "")
        elif tag == "feFlood":
            fc = child.attrib.get("flood-color", "#000000")
            fo = child.attrib.get("flood-opacity", "1")
            flood_color = _normalize_color(fc)
            flood_opacity = float(fo)
        elif tag == "feComposite":
            op = child.attrib.get("operator", "")
            if op == "in":
                has_composite_in = True
                composite_in2 = child.attrib.get("in2", "")

    has_offset = offset is not None and (offset["dx"] != 0 or offset["dy"] != 0)

    # Composite references offset result → card-shadow pattern (no glow)
    composite_targets_offset = (
        offset_result and composite_in2 == offset_result
    )

    # Detection priority: shadow > glow > soft_edge > blur
    glow = None
    soft_edge = None

    if shadow is None and blur is not None and has_offset:
        shadow = {
            "dx": offset["dx"], "dy": offset["dy"],
            "stdDeviation": blur["stdDeviation"],
            "flood_color": flood_color,
            "flood_opacity": flood_opacity,
        }

    if blur is not None and has_composite_in and not composite_targets_offset:
        glow = {
            "stdDeviation": blur["stdDeviation"],
            "flood_color": flood_color,
            "flood_opacity": flood_opacity,
        }

    if glow is None and shadow is None and blur is not None and blur_in == "SourceAlpha":
        soft_edge = {"stdDeviation": blur["stdDeviation"]}

    if soft_edge is not None:
        blur = None

    return {"blur": blur, "shadow": shadow, "glow": glow, "soft_edge": soft_edge}


def _normalize_color(value: str) -> str:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        try:
            int(value, 16)
            value = value[0] * 2 + value[1] * 2 + value[2] * 2
        except ValueError:
            return "000000"
    if len(value) != 6:
        return "000000"
    try:
        int(value, 16)
    except ValueError:
        return "000000"
    return value.upper()


def resolve_filter(attr_value: str, filters: dict[str, dict]) -> dict | None:
    m = re.match(r'url\(#([^)]+)\)', attr_value.strip())
    if not m:
        return None
    fid = m.group(1)
    return filters.get(fid)


def apply_filter_to_shape(shape, filter_info: dict, scale_x: float, scale_y: float) -> None:
    from pptx.oxml.ns import qn
    from lxml import etree

    blur = filter_info.get("blur")
    shadow = filter_info.get("shadow")
    glow = filter_info.get("glow")
    soft_edge = filter_info.get("soft_edge")

    if not blur and not shadow and not glow and not soft_edge:
        return

    sp = shape._element
    spPr = sp.spPr

    existing = spPr.find(qn("a:effectLst"))
    if existing is not None:
        spPr.remove(existing)

    effectLst = etree.SubElement(spPr, qn("a:effectLst"))

    if blur and soft_edge is None:
        std = blur["stdDeviation"]
        if std > 0:
            rad = int(std * 25400)
            blur_elem = etree.SubElement(effectLst, qn("a:blur"))
            blur_elem.set("rad", str(max(rad, 1)))

    if soft_edge:
        std = soft_edge["stdDeviation"]
        if std > 0:
            rad = int(std * 25400)
            se_elem = etree.SubElement(effectLst, qn("a:softEdge"))
            se_elem.set("rad", str(max(rad, 1)))

    if glow:
        std = glow["stdDeviation"]
        if std > 0:
            rad = int(std * 25400)
            glow_elem = etree.SubElement(effectLst, qn("a:glow"))
            glow_elem.set("rad", str(max(rad, 1)))
            color = glow.get("flood_color", "000000")
            opacity = glow.get("flood_opacity", 1.0)
            srgb = etree.SubElement(glow_elem, qn("a:srgbClr"))
            srgb.set("val", color)
            alpha = etree.SubElement(srgb, qn("a:alpha"))
            alpha.set("val", str(int(opacity * 100000)))

    if shadow:
        import math
        dx_emu = int(shadow["dx"] * scale_x * 914400)
        dy_emu = int(shadow["dy"] * scale_y * 914400)
        dist = int(math.hypot(dx_emu, dy_emu))
        dir_val = int((math.degrees(math.atan2(dx_emu, dy_emu)) % 360) * 60000)
        blur_rad = int(shadow["stdDeviation"] * 25400)
        alpha_pct = int(shadow["flood_opacity"] * 100000)
        color = shadow.get("flood_color", "000000")

        shdw = etree.SubElement(effectLst, qn("a:outerShdw"))
        if dist > 0:
            shdw.set("dist", str(dist))
            shdw.set("dir", str(dir_val))
        shdw.set("blurRad", str(max(blur_rad, 1)))
        shdw.set("algn", "bl")
        shdw.set("rotWithShape", "0")

        srgb = etree.SubElement(shdw, qn("a:srgbClr"))
        srgb.set("val", color)
        alpha = etree.SubElement(srgb, qn("a:alpha"))
        alpha.set("val", str(alpha_pct))

    _reorder_effect_lst(effectLst)
    _reorder_sppr(spPr)


def _reorder_effect_lst(effectLst) -> None:
    children = list(effectLst)
    if len(children) <= 1:
        return

    def _order_key(child):
        tag = _local(child.tag)
        try:
            return EFFECT_ORDER.index(tag)
        except ValueError:
            return len(EFFECT_ORDER)

    children.sort(key=_order_key)
    for child in list(effectLst):
        effectLst.remove(child)
    for child in children:
        effectLst.append(child)


def _reorder_sppr(spPr) -> None:
    from pptx.oxml.ns import qn

    effectLst = spPr.find(qn("a:effectLst"))
    if effectLst is None:
        return

    spPr.remove(effectLst)

    insert_after = None
    for child in spPr:
        tag = _local(child.tag)
        if tag in ("xfrm", "prstGeom", "custGeom"):
            insert_after = child

    if insert_after is not None:
        idx = list(spPr).index(insert_after) + 1
        spPr.insert(idx, effectLst)
    else:
        spPr.insert(0, effectLst)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
