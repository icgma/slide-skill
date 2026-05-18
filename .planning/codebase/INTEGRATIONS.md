---
last_mapped_commit: fa4b24c317ed091b8d6132314e40e1bbf3e46eba
mapped_at: 2026-05-03
mapper: tech
---

# INTEGRATIONS

## File-format integrations (intake → markdown)
| Format | Library / mechanism | Entry point |
|---|---|---|
| Markdown (`.md`) | passthrough | `tools/slide/src/slide_skill/intake.py:35` |
| HTML / URL | `html.parser`, `urllib.request` | `tools/slide/src/slide_skill/intake.py:14,60` |
| DOCX | `zipfile` + `xml.etree` (no python-docx) | `tools/slide/src/slide_skill/intake.py:75` |
| XLSX | `zipfile` + `xml.etree` → markdown tables | `tools/slide/src/slide_skill/intake.py:88` |
| PDF | **PyMuPDF** (`import fitz`, optional extra) → text per page | `tools/slide/src/slide_skill/intake.py:50-51,200-210` |
| PPTX (re-import) | `zipfile` + `xml.etree` | `tools/slide/src/slide_skill/intake.py` |

## File-format integrations (export)
| Format | Library | Entry point |
|---|---|---|
| PPTX (write) | `python-pptx` + raw `lxml` for OOXML namespaces | `tools/slide/src/slide_skill/exporter.py`, `tools/slide/src/slide_skill/converters.py` |
| PPTX template ops (delete/reorder/transition XML) | raw `lxml` on slide parts | `tools/slide/src/slide_skill/template_ops.py` |
| Animations / transitions | `lxml` injection | `tools/slide/src/slide_skill/animations.py` |
| PDF (from PPTX) | LibreOffice subprocess | `tools/slide/src/slide_skill/render.py:54` |
| PNG / JPEG snapshots | `pdftoppm` subprocess | `tools/slide/src/slide_skill/render.py:64` |

## System-process integrations
- `soffice --headless --convert-to pdf …` — `tools/slide/src/slide_skill/render.py:53`
- `pdftoppm` (PNG and JPG modes) — `tools/slide/src/slide_skill/render.py:84,95`
- All invocations use list-form `subprocess.run` (no `shell=True`).
- ⚠ No `timeout=` argument anywhere — see `CONCERNS.md`.

## External services
- **Azure Edge TTS** via `edge-tts` — anonymous, no key. `tools/slide/src/slide_skill/narrate.py:14`.
- **MiMo TTS (XiaoMi MiMo-V2.5-TTS)** via OpenAI-compatible client — requires `MIMO_API_KEY`. `tools/slide/src/slide_skill/mimo_tts.py:24,48` (supports voice design + cloning).

## AI / LLM integration model
- The pipeline is **deterministic by default** (no LLM is invoked at runtime).
- The "AI Executor" role is realised via a **generated prompt** (`design_guide.md` + `spec_lock.json`) that an external agent (Claude / GPT / etc.) reads to author per-slide SVGs — the entry point that produces this contract is `svg_pipeline.create_spec` (`tools/slide/src/slide_skill/svg_pipeline.py:91`) and `design_guide.build_design_guide` (`tools/slide/src/slide_skill/design_guide.py:17`).
- Fallback executor when no agent is present: `_render_slide_svg` in `svg_pipeline.py` produces the SVG procedurally from heuristics.

## Online demo HTTP boundary
- Flask app at `tools/slide-demo/app.py` exposes `POST /generate` and `GET /download/<job>/<file>`; consumes the same public functions as the CLI (`init_project`, `convert_file`, `create_spec`, `generate_svg`, `finalize_svg`, `write_svg_report`, `export_project`).
