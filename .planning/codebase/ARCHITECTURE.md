---
last_mapped_commit: fa4b24c317ed091b8d6132314e40e1bbf3e46eba
mapped_at: 2026-05-03
mapper: arch
---

# ARCHITECTURE

## SVG-first pipeline (5 stages)

| # | Stage | Module(s) | Input | Output |
|---|---|---|---|---|
| 1 | **Intake** | `intake.py` | `.md` `.docx` `.pdf` `.html` `.xlsx` `.pptx` `URL` | normalized markdown in `sources/` |
| 2 | **Spec** | `svg_pipeline.create_spec` (`:53`), `design_guide.build_design_guide` (`:17`) | markdown + theme + format | `spec_lock.json` (frozen palette/font/canvas) + `design_guide.md` |
| 3 | **SVG generation** | `svg_pipeline.generate_svg` (`:222`) → fallback `_render_slide_svg` (`:434`); or external AI agent | spec + guide | `svg_output/slide_NN.svg` |
| 4 | **Finalize** | `svg_pipeline.finalize_svg`, `svg_pipeline.check_project_svg` | `svg_output/*` | `svg_final/*` + `qa/svg_report.md` |
| 5 | **Export** | `exporter.export_project` → `converters.ConverterRegistry` | `svg_final/*` + project.json | `exports/<name>_TIMESTAMP.pptx` |

## Strategist / Executor split
- **Strategist** = the CLI / pipeline. Owns intake, spec-locking, theme selection, QA gates.
- **Executor** = whoever produces SVGs from `spec_lock.json` + `design_guide.md`. Two implementations interchangeable:
  1. Built-in heuristic renderer `_render_slide_svg` (`tools/slide/src/slide_skill/svg_pipeline.py:434`).
  2. External AI agent following the generated prompt contract.
- Spec-locking happens once at `create_spec` (`tools/slide/src/slide_skill/svg_pipeline.py:53`); palette / fonts / canvas are immutable after this point — guarantees export determinism.

## Theme system
- Defined in `tools/slide/src/slide_skill/themes.py`. Five preset themes in `THEMES: dict[str, ThemeSpec]` (`themes.py:19`): `dark-tech`, `light-corporate`, `warm-editorial`, `data-forward`, `vibrant-startup`.
- `@dataclass ThemeSpec(name: str, palette: dict[str, str], font_family: str, design_hints: str, layout_rhythm: list[str] = field(default_factory=…))` — **not** frozen (`themes.py:8-17`).
- Theme params are baked into `spec_lock.json` and rendered into the natural-language hints in `design_guide.md`. Converters consume them via spec, never directly.

## Converter pipeline (SVG → DrawingML)
- `tools/slide/src/slide_skill/converters.py` — `ConverterRegistry` dispatches by SVG tag.
- Supported tags: `rect` (→ RECTANGLE / ROUNDED_RECTANGLE), `circle`, `ellipse` (→ OVAL), `line`, `text`, `image`, `path`, `polygon`, `polyline` (→ FREEFORM via `geometry.py`).
- **Native DrawingML gradients**: `_apply_native_gradient` (`tools/slide/src/slide_skill/converters.py:198`) parses SVG `linearGradient` / `radialGradient`, computes angle, builds `<a:gradFill>` with `<a:gsLst>` stops, injects into `spPr`.
- **CJK fonts**: `convert_text` parses the CSS `font-family` stack, detects markers (`YaHei`, `PingFang`, `Noto Sans CJK`, …), and emits `<a:latin>` + `<a:ea>` typeface nodes side-by-side (`tools/slide/src/slide_skill/converters.py:393-420`).
- Path geometry → DrawingML EMU coords in `geometry.py`.

## QA gates
| Gate | Module | What it checks |
|---|---|---|
| `check-svg` | `svg_pipeline.check_project_svg` | viewBox present, banned tags (`script`, `iframe`), no animations, top-level semantic groups have `id`s |
| `validate-pptx` | `exporter.validate_pptx` (`:102`) | PPTX zip integrity, required parts present |
| `run_qa` | `qa.py:42` | composes both, plus `PLACEHOLDER_RE` scan for `lorem ipsum` / `todo` strings |

## TTS subsystem (`narrate` command)
- `narrate.py` — extracts speaker notes from `notes/`, generates per-slide audio via `edge-tts` or `mimo`, embeds into the PPTX as `audio` parts on each slide.
- `mimo_tts.py` — voice design + voice-cloning client.

## Online demo
- `tools/slide-demo/app.py` — single-file Flask app on `PORT` (default 5000).
- Per request: spawn a job dir under `/tmp/slide-skill-demo/<job_id>/` → run intake/spec/svg/finalize/export → return signed download URL.
- TTL purge of jobs after 30 min (`JOB_TTL_SECONDS = 1800`).
- JSON 404 / 413 handlers, error message scrubbing, `log.exception` for tracebacks (server-side only).
