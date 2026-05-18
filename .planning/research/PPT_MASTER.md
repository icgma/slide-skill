# External Reference Research: PPT Master

## Reference

- Repository: https://github.com/hugohe3/ppt-master
- License: MIT
- Default branch observed: `main`
- Repository description observed through GitHub: AI generates natively editable PPTX from documents using real PowerPoint shapes and native animations.
- Version observed in README: v2.3.0
- Last checked: 2026-05-01

## Why This Matters

PPT Master is closer to the direction this project should take than the original Anthropic `pptx` skill baseline. The key shift is architectural: PPT Master uses SVG as an AI-friendly intermediate representation, then post-processes and exports to native PowerPoint objects. This gives agents a format they can author and debug visually while still producing editable PPTX output.

## Core Technical Pattern

The observed pipeline is:

1. Convert source material to Markdown.
2. Initialize a project workspace.
3. Confirm a design specification.
4. Lock execution details in a machine-readable spec.
5. Generate SVG pages sequentially.
6. Run SVG quality checks before export.
7. Finalize SVGs.
8. Convert finalized SVGs to PPTX.
9. Preserve both native PPTX output and SVG backup artifacts.

The important transfer is not a specific script implementation. The important transfer is the staged contract: content understanding, design planning, locked execution parameters, SVG generation, quality gate, native conversion, and archival artifacts.

## Stack Lessons

| Area | PPT Master Approach | Implication For Slide Skill |
|------|---------------------|-----------------------------|
| Runtime | Python 3.10+ as the main runtime | Prefer Python-first tooling for v1. |
| Native PPTX export | `python-pptx` plus custom SVG/OOXML handling | Evaluate native export through Python before committing to PptxGenJS as primary. |
| Intermediate representation | SVG pages with absolute coordinates | Add SVG as the main design IR for generated decks. |
| Source ingestion | PDF, DOCX, Excel, PPTX, web, Markdown to Markdown | Add source-to-Markdown ingestion as first-class scope. |
| Quality gate | SVG checker before post-processing | Add a pre-export SVG quality gate, not only post-export visual QA. |
| Project state | Per-deck project directories with sources, spec, SVGs, notes, exports, backup | Add a local project workspace convention. |
| Animation | Top-level SVG groups become PPT animation anchors | Require semantic grouping and stable IDs in generated SVG. |
| Narration | Notes can be split and converted to audio | Keep narration as v2 unless core generation is stable. |

## Implementation Ideas To Adapt

- Project workspace: `sources/`, `images/`, `svg_output/`, `svg_final/`, `notes/`, `exports/`, `backup/`.
- Design spec plus spec lock: one human-readable planning document and one machine-readable execution contract.
- Canvas presets: 16:9, 4:3, vertical story/poster, square social, article header.
- SVG standards: banned features, inline styles, XML-safe text, stable viewBox, semantic grouping, image clipping rules.
- Quality checker: fail on unsupported SVG features, viewBox mismatch, spec drift, invalid XML, and missing group IDs.
- Export artifacts: main editable PPTX plus a visual SVG snapshot/backup path.
- Source ingestion: convert PDFs, DOCX, spreadsheets, existing PPTX, URLs, and Markdown into normalized Markdown before slide planning.
- Chart verification: treat charts as a separate calibration workflow because coordinate/data mapping errors are common.

## License Guidance

PPT Master is MIT licensed, so reuse is possible if license and attribution requirements are preserved. This project should still avoid blind vendoring. Prefer reimplementing the minimum compatible architecture, and only copy code deliberately when there is a clear reason, attribution, and license retention.

This differs from the Anthropic `pptx` reference, whose `LICENSE.txt` is proprietary and should not be copied into this project.

## Roadmap Impact

The roadmap should be revised from a direct PPTX/PptxGenJS-first approach to a Python/SVG-native pipeline:

- Phase 2 should add source ingestion and project workspace primitives.
- Phase 3 should add design spec, spec lock, SVG generation standards, and SVG QA.
- Phase 4 should add native PPTX export, backup artifacts, animations, and notes.
- Template editing remains valuable, but should come after the generation/export pipeline is stable.
- Advanced narration/video, chart calibration, and multi-format social outputs should be v2 or late-v1 hardening work.

## Sources

- README: https://github.com/hugohe3/ppt-master/blob/main/README.md
- Technical design: https://github.com/hugohe3/ppt-master/blob/main/docs/technical-design.md
- Skill entry: https://github.com/hugohe3/ppt-master/blob/main/skills/ppt-master/SKILL.md
- Requirements: https://github.com/hugohe3/ppt-master/blob/main/skills/ppt-master/requirements.txt
- Scripts index: https://github.com/hugohe3/ppt-master/blob/main/skills/ppt-master/scripts/README.md
- Shared standards: https://github.com/hugohe3/ppt-master/blob/main/skills/ppt-master/references/shared-standards.md
- Canvas formats: https://github.com/hugohe3/ppt-master/blob/main/skills/ppt-master/references/canvas-formats.md
