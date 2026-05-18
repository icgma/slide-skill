# Milestones

## v1.1 Follow-Up (Shipped: 2026-05-01)

**Phases completed:** 7 phases, 7 plans

**Key accomplishments:**

- Established a license-safe clean-room slide skill repository with local skill docs, toolkit code, examples, and tests.
- Added source intake and reproducible per-deck workspace conventions.
- Implemented SVG-first deck authoring with spec locks, semantic groups, SVG QA, and finalization.
- Exported finalized SVG pages to native editable PPTX with validation, backups, and notes sidecars.
- Added relationship-safe template inspection/editing workflows.
- Formalized automated and strict visual QA guidance, docs, and release packaging.
- Removed the v1 notes sidecar-only limitation with embedded PPTX notes, `pptx-notes`, and `render-doctor`.

**Verification:** `python -m unittest discover -s tests -v` passed with 9 tests.

**Known deferred items:** richer SVG path geometry conversion, richer notes formatting, and local render conversion evidence after LibreOffice/Poppler installation.

---

## v1.4 Visual Authoring Power Pack (Shipped: 2026-05-03)

**Phases completed:** 8 phases, 8 plans

**Key accomplishments:**

- Theme plugin system with entry-point discovery and user TOML install.
- Icon library with 350+ Lucide/Tabler icons, theme-styled SVG + EMF export.
- Code block highlighting via Pygments → SVG with line numbers and highlights.
- Native charts (bar/line/pie/area/scatter) with editable PPTX chart objects.
- Element-level animations v2 with build order and PPTX timing serialization.
- First-class PDF export (LibreOffice + cairo backends).
- HTML/Reveal.js live preview with presenter view.
- Multi-language template coverage (zh/en/ja × 5 themes) + font preflight.

**Verification:** 238 tests passing (50 subtests). All optional deps gracefully degraded.

---
