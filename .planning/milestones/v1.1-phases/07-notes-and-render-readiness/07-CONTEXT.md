---
phase: 7
status: completed
---

# Context: Phase 7 - Notes And Render Readiness

## Goal

Remove the v1 notes sidecar limitation and make visual QA dependency readiness explicit before users attempt rendering or strict QA.

## Scope

- Embed speaker notes from `notes/total.md` or per-slide `notes/slide_XX.md` files into exported PPTX notes parts.
- Preserve Markdown notes sidecar behavior for auditability.
- Add `pptx-notes` inspection for embedded notes.
- Add `render-doctor` to diagnose LibreOffice/Poppler availability.
- Update docs, tests, GSD review, and audit records.

## Non-Goals

- Full custom SVG path-to-DrawingML conversion.
- Actual local rendering when LibreOffice/Poppler are unavailable.
- Rich PowerPoint notes formatting beyond text paragraphs.
