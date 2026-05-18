# Retrospective

## Milestone: v1.1 - Follow-Up

**Shipped:** 2026-05-01
**Phases:** 7
**Plans:** 7

### What Was Built

- Clean-room slide skill package and Python toolkit for agent-authored PowerPoint workflows.
- Source intake and deck workspace conventions for repeatable generation.
- SVG-first authoring, checking, finalization, and native editable PPTX export.
- Template inspection/editing operations with relationship safety tests.
- QA documentation, automated regression coverage, and strict visual QA artifact expectations.
- Embedded speaker notes extraction plus render dependency readiness diagnostics.

### What Worked

- SVG as the authoring intermediate kept slide generation inspectable and easier to validate than raw DrawingML.
- Small toolkit modules made regression tests practical across intake, export, rendering diagnostics, and template operations.
- The notes follow-up was narrow enough to close a high-value limitation without destabilizing export behavior.

### What Was Inefficient

- Milestone completion tooling produced an empty accomplishments list because phase summaries did not expose the expected one-line frontmatter.
- `gsd-tools audit-open` currently fails through the top-level command because it calls an undefined `output()` helper, so the audit library had to be invoked directly.
- Render conversion itself remains environment-dependent and was not executed locally.

### Patterns Established

- Preserve clean-room provenance in planning docs before implementing behavior inspired by external tools.
- Keep generated decks backed by both structural tests and human-readable QA artifacts.
- Add readiness diagnostics for optional external dependencies before running commands that mutate output directories.

### Key Lessons

- Phase summaries should include machine-readable one-liners if milestone automation is expected to populate accomplishment lists.
- External renderer availability should be treated as a diagnosable environment state, not as an implicit runtime assumption.
- Notes embedding is safest when sidecar Markdown remains available for manual audit and recovery.

## Cross-Milestone Trends

| Theme | Observation | Action |
|-------|-------------|--------|
| Verification | Regression tests are effective for package structure, notes, template operations, and dependency diagnostics. | Continue adding tests before widening SVG/PPTX conversion scope. |
| Tooling | GSD lifecycle automation is useful but still has command-wrapper edge cases. | Record wrapper failures and use underlying libraries only when necessary. |
| Compatibility | Visual rendering depends on local LibreOffice and Poppler installation. | Add render conversion smoke evidence when dependencies are available. |
