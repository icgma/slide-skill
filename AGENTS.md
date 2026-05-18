<!-- GSD:project-start source:PROJECT.md -->
## Project

**Slide Skill**

Slide Skill is a clean-room project to build and iteratively improve an agent-facing PowerPoint skill and its supporting toolkit. It targets reliable source ingestion, SVG-based slide design, native editable PPTX export, rendering, editing, and QA without copying proprietary upstream source text or code.

The initial reference point is Anthropic's public `skills/pptx` package shape: a skill guide, editing guide, creation guide, helper scripts, and a strict visual QA loop. A second reference point is the MIT-licensed `hugohe3/ppt-master`, whose SVG-to-native-PPTX pipeline suggests a stronger architecture for agent-authored, editable decks. This project will turn those lessons into an independently authored local skill/library that can be evolved, tested, and used by coding agents.

**Core Value:** Agents can produce and modify PowerPoint decks that are valid, visually reviewable, natively editable, and backed by repeatable QA evidence.

### Constraints

- **Licensing**: Do not copy, vendor, or paraphrase upstream proprietary source as project implementation. Rebuild behavior independently from requirements and observable workflows.
- **Agent usability**: The skill must be short enough to load quickly, with deeper guides split into referenced files.
- **Verification**: Every slide-generation or editing workflow needs text QA and visual QA; success is evidence-based, not just file creation.
- **Compatibility**: The toolkit should prefer cross-platform components, but Windows support matters for this workspace.
- **Dependencies**: New runtime dependencies must be justified during phase planning, pinned where practical, and covered by verification.
- **Maintainability**: Prefer small scripts and testable modules over one-off monolithic deck-generation scripts.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Scope
## Recommended Stack
| Layer | Recommendation | Rationale | Confidence |
|-------|----------------|-----------|------------|
| Skill package | Markdown skill docs with small scripts under `skills/slide/` | Matches agent skill loading patterns and keeps guidance inspectable. | High |
| Primary runtime | Python 3.10+ | PPT Master demonstrates that source conversion, SVG processing, PPTX export, audio, and QA can share one Python runtime. | High |
| Deck creation | SVG-first pipeline converted to native PPTX | AI can generate/debug SVG more reliably than raw DrawingML, while export can preserve editable shapes. | High |
| Direct PPTX fallback | PptxGenJS or python-pptx recipes | Useful for targeted generated decks or package operations, but no longer the primary v1 architecture. | Medium |
| Source ingestion | Python converters to normalize PDF/DOCX/XLSX/PPTX/web/Markdown into Markdown | Makes "from any document" workflows possible and keeps slide planning input structured. | High |
| Deck text extraction | Python wrapper around MarkItDown or dedicated PPTX-to-Markdown converter | Existing ecosystem support for `.pptx` text extraction; useful for content QA. | Medium |
| Deck structure inspection | Python scripts using ZIP/XML parsing with safe XML libraries | `.pptx` is OOXML ZIP content; direct inspection is required for slide, rels, notes, media, animations, and placeholder checks. | High |
| Rendering | LibreOffice headless to PDF, then Poppler `pdftoppm` to images | Practical local rendering path for visual QA and screenshots. | High |
| Image manipulation | Pillow/numpy for thumbnails, image analysis, aspect correction, and optional generated assets | Covers quick contact sheets and image safety checks without requiring Node. | High |
| Native export | `python-pptx` plus custom SVG-to-PPTX conversion layer | Allows native editable objects, notes, and later animations/narration. | Medium |
| Tests | Script-level tests plus fixture decks | Prevents silent corruption in pack/unpack, slide relationship, and output validation flows. | High |
| CI | GitHub Actions or local equivalent after repo has package/test shape | Useful after first implementation phase; not needed before foundation. | Medium |
## Dependency Policy
- `python-pptx` for PPTX assembly and export.
- SVG parsing/conversion libraries or local converters for DrawingML output.
- `markitdown[pptx]` or alternative text extraction.
- `PyMuPDF`, `mammoth`, `openpyxl`, `markdownify`, `beautifulsoup4`, and `curl_cffi` equivalents for source ingestion.
- LibreOffice for conversion to PDF.
- Poppler for image rendering.
- Pillow for thumbnails/contact sheets.
- XML parsing libraries that preserve namespaces and avoid unsafe entity expansion.
- `edge-tts` for optional v2 narration.
## Environment Notes
## What Not To Use Initially
| Option | Reason |
|--------|--------|
| Vendored upstream Anthropic skill files | Proprietary license restrictions. |
| One large all-purpose generator script | Hard to test, hard to reuse, and likely to accumulate layout-specific hacks. |
| GUI automation as the primary path | Less deterministic than document/package-level operations and headless rendering. |
| LLM-only visual QA without rendered slide images | Misses layout issues because there is no visual evidence to inspect. |
| Raw DrawingML authored directly by AI | Too verbose and hard to visually debug; use SVG as the authoring layer. |
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:docs/ARCHITECTURE.md -->
## Architecture

Slide Skill operates on a 6-layer **SVG-first pipeline**. AI is responsible for creating SVGs, while the toolkit handles lossless conversion to native editable PowerPoint objects.

### 1. Intake Layer (`intake.py`, `project.py`)
Normalizes inputs (PDF, DOCX, XLSX, HTML, URL) into a unified Markdown source.

### 2. SVG Pipeline (`svg_pipeline.py`)
**Design Spec → Spec Lock → SVG Gen → SVG QA → SVG Finalize**
Locks design specifications (palette, layouts) into `spec_lock.json` early, preventing AI style drift, and performs visual/structural QA on generated SVGs before any binary export.

### 3. Export Layer (`exporter.py`, `converters.py`, `geometry.py`)
Converts SVGs into native PPTX shapes via `ConverterRegistry` (supporting `<rect>`, `<circle>`, `<path>`, etc.). Maps SVG path commands to native DrawingML freeforms. Includes native rendering for linear/radial gradients, clip-paths, and filter effects.

### 4. Student Toolkit (`competition.py`, `rehearse.py`)
Provides competition templates, automated timing rehearsal, and intelligent presentation notes drafting.

### 5. QA Layer (`qa.py`, `snapshot_diff.py`, `render.py`)
Validates structural integrity and uses LibreOffice+Poppler to generate pixel-level SSIM snapshot diffs to verify visual correctness.

### 6. CLI (`cli.py`)
Centralized command-line entry point with over 20 subcommands orchestrating the workflow.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
