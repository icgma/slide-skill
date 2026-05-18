# Phase 17 Context: SVG Rendering Engine Redesign

**Milestone:** v1.3
**Created:** 2026-05-02

## Problem

Current SVG rendering output is prototype-quality, not production-ready. Five root causes:

1. **Text layout broken** — `re.sub(r"\s+", " ", body)` collapses all line breaks and bullet structure into one string
2. **Title overflow** — Long titles at 44px exceed canvas width with no auto-wrap or scaling
3. **Zero visual variety** — Every slide uses identical layout (dark bg + white card + title + body)
4. **Markdown rendered literally** — `- item` bullets output as raw text, not styled list markers
5. **Empty body cards** — Slide 1 shows an empty white card when body content is empty

## Solution

Redesign `_render_slide_svg` in `svg_pipeline.py` with:
- Proper markdown-to-SVG text rendering (bullets, bold, italic, line breaks)
- Multiple layout templates (section divider, bullet list, two-column, metric highlight, default)
- Title auto-wrapping for long titles
- Visual polish (accent stripe, footer bar, progress dots, title underline, card shadow)

## Execution

Tasks dispatched to Google Jules via jules-dispatch. Sequential dependency: Task 1 → 2 → 3 → 4 → 5.

## Files to Change

- `tools/slide/src/slide_skill/svg_pipeline.py` — Main rendering logic
