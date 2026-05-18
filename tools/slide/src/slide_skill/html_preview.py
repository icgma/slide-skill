"""HTML / Reveal-style preview rendering — no LibreOffice required.

Phase 24 (v1.4): introduced. v1.4-PRES-01..04.

Generates a single self-contained HTML file from a project's finalized SVG
pages plus its speaker notes sidecar. The HTML uses a minimal dependency-free
slide engine (vanilla JS, ~3 KB) with:

  * Arrow-key / space / click navigation.
  * Presenter mode (key `P`) — current + next slide, notes pane, countdown timer.
  * Blackout (`B`) and whiteout (`W`).
  * Fullscreen (`F`).
  * Slide counter and progress bar.

The Flask demo (tools/slide-demo/app.py) gains a `/preview/<job>/html` route
that serves the rendered HTML inline; this is dramatically faster than the
LibreOffice path and works in containers without soffice installed.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Iterable

PRESENTER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; height: 100%; background: #000; color: #fff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; overflow: hidden; }}
#stage {{ position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; }}
#stage svg {{ max-width: 100vw; max-height: 100vh; width: auto; height: auto; }}
#hud {{ position: fixed; bottom: 16px; right: 24px; font-size: 14px; opacity: 0.55; color: #fff; mix-blend-mode: difference; }}
#progress {{ position: fixed; left: 0; top: 0; height: 3px; background: #38bdf8; transition: width 0.25s ease; }}
.blackout {{ background: #000 !important; }}
.whiteout {{ background: #fff !important; }}
#presenter {{ display: none; position: fixed; inset: 0; background: #0f172a; color: #f1f5f9; padding: 24px; grid-template-columns: 2fr 1fr; grid-template-rows: 1fr auto; gap: 16px; }}
#presenter.active {{ display: grid; }}
#p-current, #p-next {{ background: #1e293b; border-radius: 8px; overflow: hidden; display: flex; align-items: center; justify-content: center; padding: 12px; }}
#p-current svg, #p-next svg {{ max-width: 100%; max-height: 100%; }}
#p-notes {{ grid-column: 1 / -1; background: #1e293b; border-radius: 8px; padding: 18px; overflow-y: auto; font-size: 18px; line-height: 1.55; }}
#p-meta {{ position: fixed; top: 14px; right: 24px; font-variant-numeric: tabular-nums; font-size: 18px; opacity: 0.85; }}
.label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: #94a3b8; margin-bottom: 6px; }}
</style>
</head>
<body>
<div id="progress"></div>
<div id="stage"></div>
<div id="hud"><span id="counter">1 / {total}</span></div>

<div id="presenter">
  <div>
    <div class="label">Now</div>
    <div id="p-current"></div>
  </div>
  <div>
    <div class="label">Next</div>
    <div id="p-next"></div>
    <div id="p-meta">00:00</div>
  </div>
  <div id="p-notes"></div>
</div>

<script>
const SLIDES = {slides_json};
const NOTES = {notes_json};
let idx = 0;
let presenter = false;
let startTs = Date.now();

const stage = document.getElementById('stage');
const counter = document.getElementById('counter');
const progress = document.getElementById('progress');
const presenterPanel = document.getElementById('presenter');
const pCurrent = document.getElementById('p-current');
const pNext = document.getElementById('p-next');
const pNotes = document.getElementById('p-notes');
const pMeta = document.getElementById('p-meta');

function render() {{
  stage.innerHTML = SLIDES[idx];
  counter.textContent = (idx + 1) + ' / ' + SLIDES.length;
  progress.style.width = ((idx + 1) / SLIDES.length * 100) + '%';
  if (presenter) {{
    pCurrent.innerHTML = SLIDES[idx];
    pNext.innerHTML = SLIDES[idx + 1] || '<div style="opacity:0.4">— end —</div>';
    pNotes.textContent = NOTES[idx] || '(no notes)';
  }}
}}

function tick() {{
  if (!presenter) return;
  const dt = Math.floor((Date.now() - startTs) / 1000);
  const mm = String(Math.floor(dt / 60)).padStart(2, '0');
  const ss = String(dt % 60).padStart(2, '0');
  pMeta.textContent = mm + ':' + ss;
}}
setInterval(tick, 250);

function next() {{ if (idx < SLIDES.length - 1) {{ idx++; render(); }} }}
function prev() {{ if (idx > 0) {{ idx--; render(); }} }}
function togglePresenter() {{
  presenter = !presenter;
  presenterPanel.classList.toggle('active', presenter);
  if (presenter) startTs = Date.now();
  render();
}}
function toggleBlack() {{ document.body.classList.toggle('blackout'); document.body.classList.remove('whiteout'); }}
function toggleWhite() {{ document.body.classList.toggle('whiteout'); document.body.classList.remove('blackout'); }}
function fs() {{ if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen(); }}

document.addEventListener('keydown', (e) => {{
  switch (e.key) {{
    case 'ArrowRight': case ' ': case 'PageDown': next(); break;
    case 'ArrowLeft': case 'PageUp': prev(); break;
    case 'p': case 'P': togglePresenter(); break;
    case 'b': case 'B': toggleBlack(); break;
    case 'w': case 'W': toggleWhite(); break;
    case 'f': case 'F': fs(); break;
    case 'Escape': if (presenter) togglePresenter(); break;
    case 'Home': idx = 0; render(); break;
    case 'End': idx = SLIDES.length - 1; render(); break;
  }}
}});
document.addEventListener('click', (e) => {{ if (!presenter) next(); }});
render();
</script>
</body>
</html>
"""


def _read_slide_svgs(project: Path) -> list[str]:
    final = project / "svg_final"
    if not final.is_dir():
        raise FileNotFoundError(
            f"No finalized SVG pages at {final}. Run `slide-skill finalize-svg` first."
        )
    pages = sorted(final.glob("*.svg"))
    if not pages:
        raise FileNotFoundError(f"No *.svg files in {final}")
    out: list[str] = []
    for p in pages:
        raw = p.read_text(encoding="utf-8")
        # Strip XML declaration and DOCTYPE so the SVG slots cleanly into HTML.
        raw = re.sub(r"<\?xml[^?]*\?>", "", raw)
        raw = re.sub(r"<!DOCTYPE[^>]*>", "", raw)
        out.append(raw.strip())
    return out


def _read_notes(project: Path, slide_count: int) -> list[str]:
    notes_path = project / "notes.md"
    if not notes_path.is_file():
        return [""] * slide_count
    text = notes_path.read_text(encoding="utf-8")
    # Split by `## Slide N` headings; carry remainder into the matching slot.
    chunks: list[str] = [""] * slide_count
    current = -1
    buffer: list[str] = []

    def flush() -> None:
        if 0 <= current < slide_count:
            chunks[current] = "\n".join(buffer).strip()

    for line in text.splitlines():
        m = re.match(r"^##\s*[Ss]lide\s+(\d+)", line)
        if m:
            flush()
            current = int(m.group(1)) - 1
            buffer = []
        else:
            buffer.append(line)
    flush()
    return chunks


def render_preview_html(
    project: Path | str,
    *,
    title: str = "Slide Preview",
    lang: str = "en",
) -> str:
    """Return a self-contained HTML string for the project."""
    project = Path(project)
    slides = _read_slide_svgs(project)
    notes = _read_notes(project, len(slides))
    return PRESENTER_HTML_TEMPLATE.format(
        title=html.escape(title),
        lang=html.escape(lang),
        total=len(slides),
        slides_json=json.dumps(slides),
        notes_json=json.dumps(notes),
    )


def write_preview_html(
    project: Path | str,
    output: Path | str,
    *,
    title: str = "Slide Preview",
    lang: str = "en",
) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_preview_html(project, title=title, lang=lang), encoding="utf-8")
    return output
