---
last_mapped_commit: fa4b24c317ed091b8d6132314e40e1bbf3e46eba
mapped_at: 2026-05-03
mapper: concerns
---

# CONCERNS

Severity: **HIGH** (act before next release) · **MED** (plan in next milestone) · **LOW** (nice-to-have).

## Operational / runtime

### ~~HIGH — `subprocess.run` calls have no `timeout`~~ — FIXED in commit 255ed99
Resolved by extracting `_run_with_timeout` / `_convert_pptx_to_pdf` / `_render_to_images` helpers in `tools/slide/src/slide_skill/render.py`. `soffice` calls now bounded by `SOFFICE_TIMEOUT_SECONDS=180`; `pdftoppm` by `PDFTOPPM_TIMEOUT_SECONDS=120`. `subprocess.TimeoutExpired` is converted into a typed `RuntimeError` caught by the CLI / demo boundaries.

### ~~HIGH — Path-traversal-ish glob in demo download route~~ — FIXED in commit 255ed99
Resolved in `tools/slide-demo/app.py`: filenames now validated against the whitelist `^[A-Za-z0-9._-]+$` (rejecting `*`, `?`, `[…]`, `{…}`, separators, NUL); `glob()` replaced with explicit `iterdir()` walk; each candidate `resolve()`-d and verified with `relative_to(job_root)` as defense-in-depth.

### MED — Unbounded `/tmp/slide-skill-demo` growth under low traffic
`tools/slide-demo/app.py` runs the TTL purge **on each request**, throttled to once/min. With zero traffic, expired job dirs are not cleaned until the next visitor arrives.
**Fix:** add a `threading.Timer`-based background sweeper, or run purge in a `before_request` hook with no traffic-dependency, or rely on systemd-tmpfiles / a cron equivalent.

### MED — CJK font availability is assumed, not verified
Theme stacks in `tools/slide/src/slide_skill/themes.py:30,51,71,90,109` reference `Microsoft YaHei`, `PingFang SC`, `Noto Sans CJK SC`. If the host has none, exports render with system fallback ("tofu" boxes) silently.
**Fix:** at `init_project` or `quickstart` start, run `fc-list :lang=zh` and warn if empty.

## Code-level

### MED — Two files exceed the 500-LOC threshold
- `tools/slide/src/slide_skill/svg_pipeline.py` — **894 LOC**. Mixes spec creation, layout heuristics, prompt assembly, fallback renderer, and the `check-svg` gate.
- `tools/slide/src/slide_skill/converters.py` — **519 LOC**.
**Fix:** extract `_render_slide_svg` + heuristics into `svg_renderer.py`; move `check_project_svg` into `qa.py` (where the other gates live).

### MED — `render.py` has duplicate render/snapshot pipelines
`render_pptx` (lines 45-79) and `snapshot_pptx` (lines 80-113) differ only in output extension and naming.
**Fix:** extract `_render_to_images(pptx, fmt)` helper.

### LOW — Broad `except Exception` at boundaries
`tools/slide/src/slide_skill/cli.py:161` and `tools/slide-demo/app.py:304` use `except Exception as exc:  # noqa: BLE001`. Acceptable as last-resort boundaries; document intent in a comment.

## Security

### MED — Image href is `Path(".").resolve()`-d in converters
`tools/slide/src/slide_skill/converters.py:427`. An untrusted SVG with `<image href="../../../etc/passwd">` will resolve outside the project. Currently mitigated because input SVGs come from the user's own `sources/`, but the demo widens that trust boundary.
**Fix:** require the resolved image path to be under `project_root` and reject otherwise.

### LOW — `subprocess.run` is always list-form
No `shell=True` anywhere — good. Keep that invariant in any future additions.

## Documentation drift

### LOW (but visible) — non-existent `skills/slide/` path implied
Some legacy docs reference `skills/slide/`. The actual package lives at `tools/slide/src/slide_skill/`. The repo-root `skills/` directory exists but is empty.
**Fix:** scrub references or populate `skills/slide/` with a redirect-style README.

### LOW — claims verified accurate
- "170 passing tests" — confirmed by `pytest --collect-only`.
- "Deterministic, no LLM at runtime" — `rg "openai|anthropic|langchain"` finds only `mimo_tts.py` (TTS, not text generation). Claim stands.

## Public API stability

### MED — Implicit public API has no versioned contract
`tools/slide-demo/app.py` (and any future external integrations) imports these unmarked functions:
```
slide_skill.project.init_project(name, format, base_dir, overwrite=False)
slide_skill.intake.convert_file(path, output=None)
slide_skill.svg_pipeline.create_spec(project_path, theme=...)
slide_skill.svg_pipeline.generate_svg(project_path)
slide_skill.svg_pipeline.finalize_svg(project_path)
slide_skill.svg_pipeline.write_svg_report(project_path)
slide_skill.exporter.export_project(project_path, output=None, stage="final")
```
None are re-exported from `slide_skill/__init__.py` (4 LOC).
**Fix:** add an `api.py` (or expand `__init__.py`) that re-exports the stable surface; mark non-re-exported helpers as internal in their docstrings; bump major version on signature changes.
