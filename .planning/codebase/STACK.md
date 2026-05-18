---
last_mapped_commit: fa4b24c317ed091b8d6132314e40e1bbf3e46eba
mapped_at: 2026-05-03
mapper: tech
---

# STACK

## Language & runtime
- Python **3.11+** — declared in `pyproject.toml:9`.
- Single-process synchronous CLI; `asyncio` used only inside the TTS subsystem (`tools/slide/src/slide_skill/narrate.py:11`).

## Direct Python dependencies (from `pyproject.toml`)
| Role | Package | Used in |
|---|---|---|
| OOXML (PPTX) authoring | `python-pptx>=1.0.2` | `tools/slide/src/slide_skill/exporter.py`, `tools/slide/src/slide_skill/converters.py` |
| Low-level XML / DrawingML injection | `lxml>=6.1.0` | `tools/slide/src/slide_skill/converters.py` (CJK `<a:ea>` font fallback ~line 411) |
| SVG path math (Bézier → custGeom) | `svgpathtools>=1.7.2` | `tools/slide/src/slide_skill/geometry.py` |
| TTS — Azure Edge | `edge-tts>=7.2.8` | `tools/slide/src/slide_skill/narrate.py` |
| TTS — MiMo (OpenAI-compatible API) | `openai>=2.33.0` | `tools/slide/src/slide_skill/mimo_tts.py` |
| PDF intake | `PyMuPDF` (`import fitz`, optional extra) | `tools/slide/src/slide_skill/intake.py:200-210` |
| Other intake (DOCX/XLSX/PPTX/HTML) | stdlib `zipfile`, `xml.etree`, `html.parser`, `urllib.request` | `tools/slide/src/slide_skill/intake.py` |

## Dev / test dependencies
- `pytest`, `pytest-cov` — declared in `pyproject.toml`.

## Online demo (separate artifact, same repo)
- `Flask` 3.x — `tools/slide-demo/app.py` (single-file; not Gradio despite earlier mapper draft).

## System dependencies
Documented in `SKILL.md:107,169-170` (no `replit.nix` / `default.nix` at repo root — installation is left to the host or downstream artifact):
- **`libreoffice`** — headless `soffice` for PPTX → PDF (`tools/slide/src/slide_skill/render.py:53-54`).
- **`poppler-utils`** — `pdftoppm` for PDF → PNG/JPG snapshots (`tools/slide/src/slide_skill/render.py:63-64,84,95`).
- **`ffmpeg`** — referenced for the optional video pipeline (`SKILL.md:170`, `examples/auto-render/`).
- **`noto-fonts-cjk`** — required for CJK rendering on Linux (`SKILL.md:107,169`); theme font stacks in `tools/slide/src/slide_skill/themes.py` reference Noto + Microsoft YaHei + PingFang as fallbacks.

## Build & packaging
- `setuptools` backend — `pyproject.toml:1-3`.
- Source layout: `tools/slide/src/slide_skill/` (root `pyproject.toml` sets `pythonpath = ["tools/slide/src"]`).
- Console entry point: `slide-skill = slide_skill.cli:main` — `pyproject.toml:21`.

## Runtime topology
```
CLI (argparse) ──► intake ──► spec_lock + design_guide ──► svg_pipeline (heuristic or AI-authored) ──► finalize ──► converters → exporter (python-pptx) ──► [render: soffice/pdftoppm] ──► [narrate: edge-tts/mimo]
```
