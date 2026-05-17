"""SVG path/polygon/polyline parsing and DrawingML freeform path construction."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

EMU_PER_INCH = 914400


@dataclass
class Pt:
    x: float
    y: float


@dataclass
class MoveTo:
    pt: Pt


@dataclass
class LineTo:
    pt: Pt


@dataclass
class CubicBezTo:
    pt1: Pt
    pt2: Pt
    pt3: Pt


@dataclass
class Close:
    pass


Command = MoveTo | LineTo | CubicBezTo | Close


def parse_svg_path(d: str) -> list[Command]:
    """Parse SVG path d attribute into drawing commands.

    Handles M/mLlCcSsQqTtAaZz. Relative commands are resolved to
    absolute by svgpathtools. Smooth/quadratic curves are converted
    to cubic beziers. Arcs are approximated as cubic bezier segments.
    """
    from svgpathtools import parse_path as svg_parse
    from svgpathtools.path import (
        Arc as SvgArc,
        CubicBezier as SvgCubic,
        Line as SvgLine,
        QuadraticBezier as SvgQuad,
    )

    if not d.strip():
        return []

    svg_path = svg_parse(d)
    commands: list[Command] = []

    for segment in svg_path:
        start = _complex_to_pt(segment.start)

        if isinstance(segment, SvgLine):
            end = _complex_to_pt(segment.end)
            if _is_close(commands, end):
                commands.append(Close())
            else:
                _ensure_move(commands, start)
                commands.append(LineTo(end))

        elif isinstance(segment, SvgCubic):
            cp1 = _complex_to_pt(segment.control1)
            cp2 = _complex_to_pt(segment.control2)
            end = _complex_to_pt(segment.end)
            _ensure_move(commands, start)
            commands.append(CubicBezTo(cp1, cp2, end))

        elif isinstance(segment, SvgQuad):
            end = _complex_to_pt(segment.end)
            cp = _complex_to_pt(segment.control)
            cp1 = Pt(
                start.x + 2 / 3 * (cp.x - start.x),
                start.y + 2 / 3 * (cp.y - start.y),
            )
            cp2 = Pt(
                end.x + 2 / 3 * (cp.x - end.x),
                end.y + 2 / 3 * (cp.y - end.y),
            )
            _ensure_move(commands, start)
            commands.append(CubicBezTo(cp1, cp2, end))

        elif isinstance(segment, SvgArc):
            _ensure_move(commands, start)
            commands.extend(_arc_to_cubics(segment))

        else:
            import warnings

            warnings.warn(
                f"Skipping unsupported SVG path segment: {type(segment).__name__}"
            )

    return commands


def parse_svg_points(points_str: str) -> list[Pt]:
    """Parse SVG polygon/polyline points attribute."""
    numbers = [
        float(n)
        for n in re.findall(
            r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", points_str
        )
    ]
    if len(numbers) < 2:
        return []
    return [Pt(numbers[i], numbers[i + 1]) for i in range(0, len(numbers) - 1, 2)]


def points_to_commands(pts: list[Pt], closed: bool = True) -> list[Command]:
    """Convert a list of points to drawing commands."""
    if not pts:
        return []
    commands: list[Command] = [MoveTo(pts[0])]
    for pt in pts[1:]:
        commands.append(LineTo(pt))
    if closed:
        commands.append(Close())
    return commands


def compute_bbox(commands: list[Command]) -> tuple[float, float, float, float]:
    """Compute bounding box (min_x, min_y, max_x, max_y) from commands."""
    xs: list[float] = []
    ys: list[float] = []
    for cmd in commands:
        if isinstance(cmd, MoveTo):
            xs.append(cmd.pt.x)
            ys.append(cmd.pt.y)
        elif isinstance(cmd, LineTo):
            xs.append(cmd.pt.x)
            ys.append(cmd.pt.y)
        elif isinstance(cmd, CubicBezTo):
            xs.extend([cmd.pt1.x, cmd.pt2.x, cmd.pt3.x])
            ys.extend([cmd.pt1.y, cmd.pt2.y, cmd.pt3.y])
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    return min(xs), min(ys), max(xs), max(ys)


def build_freeform_xml(
    commands: list[Command],
    w_emu: int,
    h_emu: int,
    min_x: float,
    min_y: float,
    scale_x: float,
    scale_y: float,
):
    """Build DrawingML custGeom XML for a freeform path.

    Returns an lxml Element containing <a:custGeom>.
    """
    from lxml import etree

    A = "http://schemas.openxmlformats.org/drawingml/2006/main"

    def emu(pt: Pt) -> tuple[int, int]:
        return (
            int((pt.x - min_x) * scale_x * EMU_PER_INCH),
            int((pt.y - min_y) * scale_y * EMU_PER_INCH),
        )

    def _pt_elem(parent, tag, pt: Pt) -> None:
        x, y = emu(pt)
        el = etree.SubElement(parent, f"{{{A}}}{tag}")
        el.set("x", str(x))
        el.set("y", str(y))

    path_el = etree.Element(f"{{{A}}}path")
    path_el.set("w", str(w_emu))
    path_el.set("h", str(h_emu))

    for cmd in commands:
        if isinstance(cmd, MoveTo):
            wrap = etree.SubElement(path_el, f"{{{A}}}moveTo")
            _pt_elem(wrap, "pt", cmd.pt)
        elif isinstance(cmd, LineTo):
            wrap = etree.SubElement(path_el, f"{{{A}}}lnTo")
            _pt_elem(wrap, "pt", cmd.pt)
        elif isinstance(cmd, CubicBezTo):
            bez = etree.SubElement(path_el, f"{{{A}}}cubicBezTo")
            for p in (cmd.pt1, cmd.pt2, cmd.pt3):
                _pt_elem(bez, "pt", p)
        elif isinstance(cmd, Close):
            etree.SubElement(path_el, f"{{{A}}}close")

    cust_geom = etree.Element(f"{{{A}}}custGeom")
    path_lst = etree.SubElement(cust_geom, f"{{{A}}}pathLst")
    path_lst.append(path_el)
    return cust_geom


# --- internal helpers ---


def _complex_to_pt(c: complex) -> Pt:
    return Pt(c.real, c.imag)


def _ensure_move(commands: list[Command], start: Pt) -> None:
    if not commands or isinstance(commands[-1], Close):
        commands.append(MoveTo(start))


def _is_close(commands: list[Command], end_pt: Pt) -> bool:
    """Check if end_pt matches the last moveTo (SVG Z command was a line back to start)."""
    for cmd in reversed(commands):
        if isinstance(cmd, MoveTo):
            return abs(cmd.pt.x - end_pt.x) < 0.5 and abs(cmd.pt.y - end_pt.y) < 0.5
    return False


def _arc_to_cubics(arc) -> list[CubicBezTo]:
    """Convert an SVG Arc to cubic bezier segments.

    Uses the SVG spec F.6.5 endpoint-to-center parametrization,
    subdivides into ≤90° segments, and approximates each with
    the standard kappa formula.
    """
    rx = abs(arc.radius.real)
    ry = abs(arc.radius.imag)

    if rx == 0 or ry == 0:
        return [LineTo(_complex_to_pt(arc.end))]

    start = _complex_to_pt(arc.start)
    end = _complex_to_pt(arc.end)

    phi = math.radians(arc.rotation)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)

    dx = (start.x - end.x) / 2
    dy = (start.y - end.y) / 2
    x1p = cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy

    rx_sq, ry_sq = rx * rx, ry * ry
    x1p_sq, y1p_sq = x1p * x1p, y1p * y1p

    lam = x1p_sq / rx_sq + y1p_sq / ry_sq
    if lam > 1:
        s = math.sqrt(lam)
        rx *= s
        ry *= s
        rx_sq, ry_sq = rx * rx, ry * ry

    num = max(0, rx_sq * ry_sq - rx_sq * y1p_sq - ry_sq * x1p_sq)
    den = rx_sq * y1p_sq + ry_sq * x1p_sq
    if den == 0:
        return [LineTo(end)]

    sq = math.sqrt(num / den)
    if arc.large_arc == arc.sweep:
        sq = -sq

    cxp = sq * rx * y1p / ry
    cyp = -sq * ry * x1p / rx
    cx = cos_phi * cxp - sin_phi * cyp + (start.x + end.x) / 2
    cy = sin_phi * cxp + cos_phi * cyp + (start.y + end.y) / 2

    def _vec_angle(ux, uy, vx, vy):
        n = math.sqrt(ux * ux + uy * uy) * math.sqrt(vx * vx + vy * vy)
        if n < 1e-12:
            return 0.0
        c = max(-1.0, min(1.0, (ux * vx + uy * vy) / n))
        a = math.acos(c)
        return a if ux * vy - uy * vx >= 0 else -a

    theta1 = _vec_angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dtheta = _vec_angle(
        (x1p - cxp) / rx,
        (y1p - cyp) / ry,
        (-x1p - cxp) / rx,
        (-y1p - cyp) / ry,
    )
    if not arc.sweep and dtheta > 0:
        dtheta -= 2 * math.pi
    elif arc.sweep and dtheta < 0:
        dtheta += 2 * math.pi

    n_segs = max(1, int(math.ceil(abs(dtheta) / (math.pi / 2))))
    seg_angle = dtheta / n_segs

    segments: list[CubicBezTo] = []
    for i in range(n_segs):
        t1 = theta1 + i * seg_angle
        t2 = theta1 + (i + 1) * seg_angle
        k = 4.0 / 3.0 * math.tan(seg_angle / 4.0)

        cos_t1, sin_t1 = math.cos(t1), math.sin(t1)
        cos_t2, sin_t2 = math.cos(t2), math.sin(t2)

        e1x, e1y = rx * cos_t1, ry * sin_t1
        e2x, e2y = rx * cos_t2, ry * sin_t2

        cp1x = e1x + k * (-rx * sin_t1)
        cp1y = e1y + k * (ry * cos_t1)
        cp2x = e2x - k * (-rx * sin_t2)
        cp2y = e2y - k * (ry * cos_t2)

        def _to_svg(ex, ey):
            return Pt(
                cos_phi * ex - sin_phi * ey + cx,
                sin_phi * ex + cos_phi * ey + cy,
            )

        segments.append(CubicBezTo(_to_svg(cp1x, cp1y), _to_svg(cp2x, cp2y), _to_svg(e2x, e2y)))

    return segments
