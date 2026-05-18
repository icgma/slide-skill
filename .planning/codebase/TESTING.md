---
last_mapped_commit: fa4b24c317ed091b8d6132314e40e1bbf3e46eba
mapped_at: 2026-05-03
mapper: quality
---

# TESTING

## Framework
- `pytest` (declared in `pyproject.toml`); `pytest-cov` available for coverage.
- `pyproject.toml` sets `pythonpath = ["tools/slide/src"]` so `tests/` can `import slide_skill.*` without install.

## Layout
- All tests in `tests/` at repo root (NOT under `tools/slide/`).
- 18 test files, **170 collected tests** (verified via `pytest --collect-only`).

## File-by-file
| File | Covers |
|---|---|
| `test_animations.py` | Transition + timing XML injection. |
| `test_cli_new.py` | `argparse` wiring, help, exit codes. |
| `test_competition.py` | Competition presets / constraints. |
| `test_competition_workflow.py` | E2E pitch-competition pipeline. |
| `test_design_guide.py` | Guide is generated correctly for every theme. |
| `test_draft_notes.py` | Speaker-note drafting helpers. |
| `test_geometry.py` | SVG path → DrawingML EMU math (extensive). |
| `test_intake.py` | HTML / text / docx → markdown. |
| `test_mimo_tts.py` | MiMo client structure (no live audio). |
| `test_narrate.py` | edge-tts orchestration (mocked). |
| `test_pipeline.py` | Full markdown → PPTX integration. |
| `test_rehearse.py` | Timing estimation. |
| `test_render.py` | System-dep probes for `soffice`, `pdftoppm`. |
| `test_rich_notes.py` | Markdown formatting in speaker notes. |
| `test_snapshot.py` | Pixel-diff visual regression. |
| `test_svg_rendering.py` | Layout heuristics, SVG structure. |
| `test_template_ops.py` | Native PPTX delete/reorder. |
| `test_themes.py` | Palette + font validation per theme. |

## Patterns
- Heavy use of `tmp_path` fixture for isolated project IO.
- CLI tested two ways: direct `main(argv=[...])` *and* `subprocess.run` against the installed entry point.
- Snapshot tests (`test_snapshot.py`) do pixel-level diff — require `soffice` + `pdftoppm`; auto-skip if absent.
- E2E vs unit: ~20 % E2E (`test_pipeline`, `test_competition_workflow`), ~80 % unit.

## Known gaps
- **`tools/slide-demo/app.py`** — zero coverage. The Flask routes (`/generate`, `/download/...`), the TTL purge, the JSON error handlers, and the path-traversal guard are all untested.
- **CJK `<a:ea>` injection branch** in `converters.py:393-420` — covered indirectly by `test_svg_rendering.py` but no unit test that asserts the produced OOXML contains `<a:ea typeface="...">` for a CJK font stack.
- **Subprocess timeout behaviour** — none of the `subprocess.run` calls in `render.py` have a `timeout=`, so there is no test for hang recovery either.

## Run
```bash
pytest tests/                     # full suite (~170 tests)
pytest tests/test_pipeline.py -v  # one file
pytest --collect-only tests/      # count check
```
