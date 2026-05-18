---
last_mapped_commit: fa4b24c317ed091b8d6132314e40e1bbf3e46eba
mapped_at: 2026-05-03
mapper: arch
---

# STRUCTURE

## Repo layout (top-level)
```
slide-skill/
├── SKILL.md                      # Anthropic-format root skill descriptor (EN+ZH triggers)
├── README.md / README.zh-CN.md   # Bilingual docs
├── AGENTS.md                     # Agent integration guide
├── pyproject.toml                # Python package metadata + pytest config
├── requirements.txt              # `-e .` (delegates to pyproject)
│                                 # NB: no replit.nix at repo root — system deps are documented in SKILL.md only
├── .planning/                    # GSD planning state (this folder)
│   ├── codebase/                 # ← codebase map (you are here)
│   ├── milestones/  STATE.md  PROJECT.md  ROADMAP.md  ...
├── .claude/                      # GSD-installed commands, agents, hooks
├── tools/
│   ├── slide/                    # Main package
│   │   ├── src/slide_skill/      # Python source
│   │   └── (tests at repo /tests/)
│   └── slide-demo/               # Flask online demo (separate artifact)
├── tests/                        # Pytest suite
├── examples/                     # Sample projects (e.g. sample-dark-tech)
├── docs/                         # Long-form docs
├── jules/                        # Reference materials
└── skills/                       # (placeholder; see CONCERNS.md drift note)
```

## `tools/slide/src/slide_skill/` (sorted by LOC, descending)

| File | LOC | Purpose |
|---|---:|---|
| `svg_pipeline.py` | 894 | Spec creation, fallback SVG renderer, finalize, `check-svg` gate. |
| `converters.py` | 519 | SVG → DrawingML registry; gradients, CJK font injection, freeform paths. |
| `design_guide.py` | 363 | Builds the human/AI-readable Markdown contract for the Executor role. |
| `geometry.py` | 323 | SVG path → `custGeom` EMU math (Bézier, arc, polyline). |
| `cli.py` | 322 | `argparse` subcommands; `main` → `_dispatch`. |
| `template_ops.py` | 299 | Low-level OOXML edits: delete/reorder slides, transition XML. |
| `exporter.py` | 291 | PPTX assembly, EMU scaling, `validate_pptx`. |
| `intake.py` | 210 | `convert_file` for md/docx/pdf/html/xlsx/pptx/URL → markdown. |
| `animations.py` | 205 | Slide-transition + entrance-effect XML injection. |
| `narrate.py` | 200 | TTS orchestration; `edge-tts` async + audio embedding. |
| `competition.py` | 194 | Pitch-competition presets + constraints. |
| `rehearse.py` | 190 | Per-slide timing estimation, rehearsal playback aid. |
| `draft_notes.py` | 154 | Speaker-note drafting / sync helpers. |
| `qa.py` | 143 | Composite QA: SVG gate + PPTX validate + placeholder scan. |
| `mimo_tts.py` | 132 | MiMo voice-design / cloning client (OpenAI-compatible). |
| `themes.py` | 128 | 5 preset `ThemeSpec` instances; CJK font stacks. |
| `render.py` | 127 | PPTX → PDF (soffice) → PNG/JPG (pdftoppm). |
| `snapshot_diff.py` | 119 | Pixel-diff visual regression. |
| `project.py` | 116 | `init_project`, `project.json` schema, required dirs. |
| `util.py` | 48 | `slugify`, JSON IO, fs helpers. |
| `formats.py` | 39 | Aspect-ratio + canvas dim presets (16:9, 4:3, A4, …). |
| `__main__.py` | 7 | `python -m slide_skill` entry. |
| `__init__.py` | 4 | Re-exports. |

**Total: ~5,176 LOC across 23 files** in the core package.

## Project workspace convention (created by `init_project`)
```
projects/<name>/
├── project.json                  # name, title, format, canvas, created_at
├── sources/                      # original input files
├── images/                       # embedded assets
├── svg_output/                   # initial SVGs from generation stage
├── svg_final/                    # validated/finalized SVGs (export source)
├── notes/                        # speaker notes (total.md or slide_NN.md)
├── exports/                      # <name>_YYYYMMDD_HHMMSS.pptx
├── backup/                       # previous exports
└── qa/                           # svg_report.md, pptx_report.md
```
Required-dir constant: `tools/slide/src/slide_skill/project.py:11`.

## Tests
- Live in repo-root `tests/` (NOT under `tools/slide/`).
- `pyproject.toml` sets `pythonpath = ["tools/slide/src"]` so imports resolve.
- Discovery: `pytest` default `test_*.py`.
- Run: `pytest tests/` from repo root.
- Files (18): `test_animations`, `test_cli_new`, `test_competition`, `test_competition_workflow`, `test_design_guide`, `test_draft_notes`, `test_geometry`, `test_intake`, `test_mimo_tts`, `test_narrate`, `test_pipeline`, `test_rehearse`, `test_render`, `test_rich_notes`, `test_snapshot`, `test_svg_rendering`, `test_template_ops`, `test_themes`.
