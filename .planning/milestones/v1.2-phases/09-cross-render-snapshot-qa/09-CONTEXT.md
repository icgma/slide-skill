# Phase 9 Context: Cross-Render Snapshot QA

**Phase:** 9
**Milestone:** v1.2
**Created:** 2026-05-01
**Status:** Ready for planning

## Goal

Add per-slide snapshot rendering and automated pixel-similarity comparison for visual QA evidence.

## Requirements

- RND-01: Render PPTX to per-slide PNGs with deterministic naming (slide-01.png, etc.)
- RND-02: Compare two snapshot sets → per-page pixel similarity scores (0-100%)
- RND-03: QA report with per-slide scores, overall deck score, PASS/FAIL verdict
- RND-04: Configurable threshold and DPI without code changes
- RND-05: Diff engine handles anti-aliasing noise (no false positives)

## Decisions

### Snapshot rendering
- Add `snapshot_pptx()` to render.py using pdftoppm with `-png` flag
- Deterministic naming: rename pdftoppm output to `slide-{NN}.png`
- Default DPI: 150 (configurable)

### Diff engine
- Use Pillow + numpy for pixel comparison (both already available)
- Per-pixel tolerance: difference < 10/255 per channel counts as matching (anti-aliasing noise handling)
- Per-slide score: percentage of matching pixels
- Overall deck score: average of per-slide scores

### QA integration
- Add `compare_snapshots()` to new module `snapshot_diff.py`
- Add `run_snapshot_qa()` to qa.py
- Report: markdown file with per-slide scores, overall score, PASS/FAIL

### Configuration
- Threshold: default 95.0%, configurable via function parameter
- DPI: default 150, configurable via function parameter

## Technical Context

- `render.py` already has `render_pptx()` for PPTX→PDF→JPG pipeline
- LibreOffice + pdftoppm are the render dependencies (may not be installed)
- Tests must handle the case where render deps are missing (skip gracefully)

## Scope

- In scope: snapshot rendering, pixel diff, QA report, configurable threshold/DPI
- Out of scope: SSIM/perceptual metrics, cross-app validation

---
*Context created: 2026-05-01*
