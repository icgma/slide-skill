"""Chart rendering — SVG (matplotlib) and native PPTX DrawingML (python-pptx).

Phase 21 (v1.4): introduced. v1.4-CHART-01..05.

Spec format (in deck source / layout slot):

    chart:
      kind: bar | line | pie | area | scatter
      title: "Q3 Revenue by Region"
      categories: [North, South, East, West]
      series:
        - name: "2024"
          values: [120, 90, 150, 80]
        - name: "2025"
          values: [140, 110, 170, 100]

SVG path: matplotlib -> SVG buffer, themed via theme palette.
PPTX path: python-pptx native chart so PowerPoint users can double-click + edit.
matplotlib is OPTIONAL — chart_to_svg degrades to a placeholder rect on missing
dep, while PPTX export uses python-pptx (already in dependencies).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
from typing import Optional

from .themes import ThemeSpec, get_theme


SUPPORTED_KINDS = {"bar", "line", "pie", "area", "scatter"}


@dataclass
class ChartSpec:
    kind: str
    categories: list[str] = field(default_factory=list)
    series: list[dict] = field(default_factory=list)  # [{"name": str, "values": [..]}]
    title: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "ChartSpec":
        kind = (data.get("kind") or "bar").lower()
        if kind not in SUPPORTED_KINDS:
            raise ValueError(f"Unsupported chart kind: {kind!r}. Choose from {sorted(SUPPORTED_KINDS)}")
        return cls(
            kind=kind,
            categories=list(data.get("categories", [])),
            series=[{"name": str(s.get("name", f"S{i+1}")), "values": list(s.get("values", []))}
                    for i, s in enumerate(data.get("series", []))],
            title=str(data.get("title", "")),
        )


def _theme_palette(theme: ThemeSpec) -> list[str]:
    """Return a 5-color cycle derived from the theme."""
    p = theme.palette
    base = [p.get("accent", "#3B82F6")]
    # Cheap derived palette: accent + body/text + muted variants for contrast.
    base += [p.get("text", "#0F172A"), p.get("body", "#475569"), p.get("muted", "#CBD5E1")]
    # Pad with a complementary tint of accent.
    base.append(_lighten(p.get("accent", "#3B82F6"), 0.4))
    return base


def _lighten(hex_color: str, amount: float) -> str:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02X}{g:02X}{b:02X}"


def chart_to_svg(
    spec: ChartSpec,
    *,
    theme: Optional[ThemeSpec] = None,
    width: int = 800,
    height: int = 480,
    x: int | float = 0,
    y: int | float = 0,
) -> str:
    """Render a ChartSpec to an SVG <g> fragment positioned at (x, y).

    Uses matplotlib if available; otherwise emits a labelled placeholder
    panel so the slide layout still composes.
    """
    if theme is None:
        theme = get_theme("dark-tech")

    inner = _matplotlib_chart_inner(spec, theme, width, height)
    if inner is None:
        # Fallback placeholder.
        from .util import xml_escape
        bg = theme.palette.get("surface", "#1E293B")
        fg = theme.palette.get("text", "#F1F5F9")
        return (
            f'<g transform="translate({x},{y})">'
            f'<rect width="{width}" height="{height}" rx="8" ry="8" fill="{bg}"/>'
            f'<text x="{width // 2}" y="{height // 2}" text-anchor="middle" '
            f'font-size="22" fill="{fg}">[chart: {xml_escape(spec.kind)} — install matplotlib]</text>'
            f'</g>'
        )
    return f'<g transform="translate({x},{y})">{inner}</g>'


def _matplotlib_chart_inner(
    spec: ChartSpec, theme: ThemeSpec, width: int, height: int,
) -> Optional[str]:
    try:
        import matplotlib  # type: ignore[import-not-found]
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except ImportError:
        return None

    palette = _theme_palette(theme)
    bg = theme.palette.get("surface", "#1E293B")
    fg = theme.palette.get("text", "#F1F5F9")
    body = theme.palette.get("body", "#94A3B8")

    dpi = 100
    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi, facecolor=bg)
    ax = fig.add_subplot(111)
    ax.set_facecolor(bg)
    for spine in ax.spines.values():
        spine.set_color(body)
    ax.tick_params(colors=body)
    ax.title.set_color(fg)
    ax.xaxis.label.set_color(body)
    ax.yaxis.label.set_color(body)

    cats = spec.categories or [str(i + 1) for i in range(max((len(s["values"]) for s in spec.series), default=0))]

    if spec.kind == "bar":
        n = len(spec.series)
        import numpy as np  # type: ignore[import-not-found]
        idx = np.arange(len(cats))
        bar_w = 0.8 / max(n, 1)
        for i, s in enumerate(spec.series):
            ax.bar(idx + i * bar_w, s["values"], bar_w, label=s["name"], color=palette[i % len(palette)])
        ax.set_xticks(idx + bar_w * (n - 1) / 2)
        ax.set_xticklabels(cats)
    elif spec.kind == "line":
        for i, s in enumerate(spec.series):
            ax.plot(cats, s["values"], marker="o", label=s["name"], color=palette[i % len(palette)], linewidth=2)
    elif spec.kind == "area":
        for i, s in enumerate(spec.series):
            ax.fill_between(cats, s["values"], color=palette[i % len(palette)], alpha=0.5, label=s["name"])
    elif spec.kind == "scatter":
        for i, s in enumerate(spec.series):
            ax.scatter(range(len(s["values"])), s["values"], label=s["name"], color=palette[i % len(palette)], s=60)
        ax.set_xticks(range(len(cats)))
        ax.set_xticklabels(cats)
    elif spec.kind == "pie":
        first = spec.series[0] if spec.series else {"values": []}
        ax.pie(first["values"], labels=cats, colors=palette[: len(cats)],
               textprops={"color": fg}, autopct="%1.0f%%")
        ax.axis("equal")

    if spec.title:
        ax.set_title(spec.title, color=fg, fontsize=14, pad=12)
    if spec.kind != "pie" and len(spec.series) > 1:
        leg = ax.legend(facecolor=bg, edgecolor=body)
        for text in leg.get_texts():
            text.set_color(fg)

    fig.tight_layout()
    buf = StringIO()
    fig.savefig(buf, format="svg", facecolor=bg, transparent=False)
    plt.close(fig)
    raw = buf.getvalue()

    # Extract the inner content of the <svg>...</svg> envelope so it slots
    # into a parent SVG document without nesting <?xml?> declarations.
    import re
    m = re.search(r"<svg[^>]*>(.*)</svg>", raw, re.DOTALL)
    return m.group(1) if m else None


def add_native_chart_to_slide(slide, spec: ChartSpec, *, left, top, width, height):
    """Add a native PPTX (DrawingML) chart to a python-pptx slide.

    PowerPoint users can double-click the result to edit the data. Returns the
    GraphicFrame containing the chart.
    """
    from pptx.chart.data import CategoryChartData, XyChartData  # type: ignore[import-not-found]
    from pptx.enum.chart import XL_CHART_TYPE  # type: ignore[import-not-found]

    kind_map = {
        "bar": XL_CHART_TYPE.COLUMN_CLUSTERED,
        "line": XL_CHART_TYPE.LINE,
        "pie": XL_CHART_TYPE.PIE,
        "area": XL_CHART_TYPE.AREA,
        "scatter": XL_CHART_TYPE.XY_SCATTER,
    }
    chart_type = kind_map.get(spec.kind, XL_CHART_TYPE.COLUMN_CLUSTERED)

    if spec.kind == "scatter":
        data = XyChartData()
        for s in spec.series:
            series = data.add_series(s["name"])
            for i, v in enumerate(s["values"]):
                series.add_data_point(i + 1, v)
    else:
        data = CategoryChartData()
        data.categories = spec.categories or [str(i + 1) for i in range(
            max((len(s["values"]) for s in spec.series), default=0)
        )]
        for s in spec.series:
            data.add_series(s["name"], s["values"])

    return slide.shapes.add_chart(chart_type, left, top, width, height, data)
