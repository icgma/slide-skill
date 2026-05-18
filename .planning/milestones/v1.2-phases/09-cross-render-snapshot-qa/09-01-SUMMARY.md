# Phase 9 Summary: Cross-Render Snapshot QA

**Phase:** 9
**Completed:** 2026-05-01
**Status:** Complete

## What Shipped

- **Snapshot rendering** — `snapshot_pptx()` in render.py renders PPTX to per-slide PNGs with deterministic naming (slide-01.png, slide-02.png). Uses LibreOffice→PDF→pdftoppm pipeline.
- **Pixel diff engine** — `snapshot_diff.py` compares two PNG sets using Pillow+numpy. Per-pixel tolerance (default 10/255) handles anti-aliasing noise. Per-slide scores and overall deck score.
- **QA report** — Markdown report with per-slide scores, overall score, PASS/FAIL verdict. Configurable threshold and DPI.
- **QA integration** — `run_snapshot_qa()` in qa.py ties rendering and comparison together.

## Files

- NEW: `snapshot_diff.py`
- MODIFIED: `render.py` (added snapshot_pptx)
- MODIFIED: `qa.py` (added run_snapshot_qa)
- NEW: `tests/test_snapshot.py` (9 tests)

## Test Results

53/53 pass.
