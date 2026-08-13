"""Headless-Chrome DOM geometry measurement for SVG text (QA-02/QA-03).

Static character-width estimates in svg_qa are cheap pre-screens, but they
can be wrong for large display numerals and unusual fonts. When a local
Chrome/Edge exists, the browser's ``getBBox()`` is the final arbiter: this
module renders the SVG in a headless page, measures every ``<text>``/
``<tspan>`` node in SVG user units, and returns the measured boxes.

All entry points degrade gracefully: when no browser is present or the
invocation fails for environmental reasons, ``measure_svg_text_geometry``
returns ``None`` and callers decide policy (keep the static verdict, record
a capability gap, ...).
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

DEFAULT_MEASURE_TIMEOUT = 20.0

# Mirror the sandbox/stability flags of the existing screenshot path
# (render.render_svg_previews, ai_executor's repair render gate), swapping
# --screenshot for --dump-dom so the serialized DOM lands on stdout after
# the virtual-time budget lets scripts and font loading settle.
_CHROME_MEASURE_FLAGS = (
    "--headless=new",
    "--dump-dom",
    "--virtual-time-budget=5000",
    "--no-first-run",
    "--disable-gpu",
    "--no-sandbox",
)

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def find_chrome() -> str | None:
    """Locate a local headless-capable browser (single source of truth).

    Checks PATH names first, then common Windows install locations. Shared
    by the geometry measurement below, the executor's post-repair render
    gate, and render.py's SVG preview path.
    """
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def build_measurement_harness(svg_text: str) -> str:
    """Return an HTML page that measures every SVG text node into the title.

    The SVG travels as a JSON-encoded JS string assigned via ``innerHTML``
    (never raw concatenation), so ``</script>`` sequences and quotes inside
    the markup cannot break the harness. ``</`` is escaped to ``<\\/`` to
    keep the HTML parser from ending the script block early.

    The script waits for ``document.fonts.ready``, collects
    ``{index, tag, text, bbox, textLength}`` for every ``text``/``tspan``
    via ``getBBox()``/``getComputedTextLength()`` (both in SVG user units,
    so results compare directly against SVG coordinates), and serializes
    the JSON array into ``document.title`` for ``--dump-dom`` extraction.
    """
    payload = json.dumps(str(svg_text)).replace("</", "<\\/")
    return (
        "<!doctype html>\n"
        '<meta charset="utf-8">\n'
        "<style>html,body{margin:0;padding:0;width:1280px;height:720px;"
        "overflow:hidden;background:#000}"
        "#stage svg{width:1280px;height:720px;display:block}</style>\n"
        '<div id="stage"></div>\n'
        "<script>\n"
        '"use strict";\n'
        f"var SVG_MARKUP = {payload};\n"
        'document.getElementById("stage").innerHTML = SVG_MARKUP;\n'
        "(async function () {\n"
        "  try { await document.fonts.ready; } catch (err) {}\n"
        '  var nodes = document.querySelectorAll("#stage text, #stage tspan");\n'
        "  var results = [];\n"
        "  nodes.forEach(function (node, index) {\n"
        "    var entry = {\n"
        "      index: index,\n"
        "      tag: (node.tagName || \"\").toLowerCase(),\n"
        "      text: node.textContent || \"\",\n"
        "      bbox: {x: 0, y: 0, width: 0, height: 0},\n"
        "      textLength: 0,\n"
        "    };\n"
        "    try {\n"
        "      var box = node.getBBox();\n"
        "      entry.bbox = {x: box.x, y: box.y, width: box.width, height: box.height};\n"
        "    } catch (err) {}\n"
        "    try { entry.textLength = node.getComputedTextLength(); } catch (err) {}\n"
        "    results.push(entry);\n"
        "  });\n"
        "  document.title = JSON.stringify(results);\n"
        "})();\n"
        "</script>\n"
    )


def parse_measurement_dom(dom_text: str) -> list[dict] | None:
    """Extract the measurement JSON array from a ``--dump-dom`` payload.

    The dumped DOM HTML-escapes title text, so the payload is unescaped
    before parsing. Every ``<title>`` occurrence is tried (an SVG may carry
    its own ``<title>`` child) and the first that parses as a JSON list
    wins. Returns ``None`` when no valid payload exists.
    """
    for raw in _TITLE_RE.findall(dom_text or ""):
        payload = html.unescape(raw).strip()
        if not payload.startswith("["):
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            return [_normalize_entry(entry) for entry in data if isinstance(entry, dict)]
    return None


def _normalize_entry(entry: dict) -> dict:
    bbox = entry.get("bbox") if isinstance(entry.get("bbox"), dict) else {}
    return {
        "index": int(_float_or_zero(entry.get("index"))),
        "tag": str(entry.get("tag") or "").lower(),
        "text": str(entry.get("text") or ""),
        "bbox": {
            "x": _float_or_zero(bbox.get("x")),
            "y": _float_or_zero(bbox.get("y")),
            "width": _float_or_zero(bbox.get("width")),
            "height": _float_or_zero(bbox.get("height")),
        },
        "textLength": _float_or_zero(entry.get("textLength")),
    }


def _float_or_zero(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def measure_svg_text_geometry(
    svg_text: str,
    *,
    chrome_path: str | None = None,
    timeout: float = DEFAULT_MEASURE_TIMEOUT,
) -> list[dict] | None:
    """Measure real browser bounding boxes for every SVG text node.

    Returns a list of ``{index, tag, text, bbox: {x, y, width, height},
    textLength}`` dicts in SVG user units, or ``None`` when Chrome is
    missing or the invocation fails (callers decide policy).
    """
    browser = chrome_path or find_chrome()
    if not browser:
        return None
    harness = build_measurement_harness(svg_text)
    try:
        with tempfile.TemporaryDirectory(prefix="svg-geometry-") as tmp:
            html_path = Path(tmp) / "measure.html"
            html_path.write_text(harness, encoding="utf-8")
            completed = subprocess.run(
                [browser, *_CHROME_MEASURE_FLAGS, html_path.resolve().as_uri()],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_measurement_dom(completed.stdout or "")
