# Changelog

All notable changes to Slide Skill are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [3.0.0] — 2026-05-17

### Added
- Intelligent content planning layer (`ContentPlanner`) detecting 8 content types: vocabulary, dialogue, metrics, process, bullets, paragraph, quote, empty
- Domain-aware density rules with configurable `ContentConfig(domain="teaching"|"course"|"competition"|"general")`
- Anti-monotony pass breaking runs of 3+ identical layouts
- Teaching domain renderer: vocab-card (auto-sized CJK chars), sentence-example, dialogue layouts with pinyin annotations
- Course domain renderer: learning-objectives, key-concept, case-study, discussion layouts
- Competition domain renderer: team-grid, metrics-dashboard, timeline, comparison-matrix layouts
- CLI commands: `plan`, `build`, `preview`, `adjust`
- 61 new tests (460 total)

## [2.3.0] — 2026-05-10

### Added
- SVG soft edge effect (feGaussianBlur on SourceAlpha → DrawingML softEdge)
- SVG outer glow effect (feGaussianBlur + feFlood + feComposite → DrawingML glow)
- Multi-effect composition with correct effectLst child ordering per OOXML schema
- Bilingual parallel text export (Chinese + English stacked or side-by-side)
- Unified CJK width estimation (1.0x factor, replacing 1.0 vs 1.8 mismatch)
- RTL support for Arabic/Hebrew bilingual text
- PDF handout export with slide thumbnails + speaker notes (1-up, 2-up, 3-up layouts)
- CJK font embedding in PDF output

## [2.2.0] — 2026-05-08

### Added
- SVG Gaussian blur filter (feGaussianBlur → DrawingML blur)
- SVG drop shadow filter (feDropShadow/feOffset+feGaussianBlur → DrawingML outerShdw)
- Filter, feGaussianBlur, feDropShadow, feOffset removed from SVG QA banned list

## [2.1.0] — 2026-05-08

### Added
- SVG gradient fill conversion (linearGradient/radialGradient → DrawingML gradFill)
- SVG clip-path and mask support (→ DrawingML customGeometry)
- SVG pattern fill support (→ DrawingML blipFill tiling)
- Gradient, clip-path, mask, pattern definitions removed from SVG QA banned list

## [2.0.0] — 2026-05-08

### Added
- Multi-role workflow: Strategist (planning) + Executor (SVG authoring)
- 5 design themes: dark-tech, light-corporate, warm-editorial, data-forward, vibrant-startup
- SVG writing standards with allowed/banned tags and attributes
- 7 layout templates: cover, section-divider, bullet-list, two-column, metric-highlight, quote, closing
- Pipeline hardening with spec_lock.json machine-readable format
- End-to-end flow: source → spec → SVG → QA → finalize → export → QA

## [1.5.0] — 2026-05-06

### Added
- Visual quality and template system improvements
- Template inspection, replacement, deletion, reordering, duplication operations

## [1.4.0] — 2026-05-03

### Added
- Visual authoring power pack
- Rich SVG support: opacity, gradients, filters
- Enhanced animation and transition support

## [1.3.0] — 2026-05-02

### Added
- Animation support
- TTS narration (edge-tts engine)
- Multi-format canvas (ppt169, ppt43, a4, square, xhs, wechat)
- Student competition toolkit with templates
- SVG rendering redesign

## [1.2.0] — 2026-05-01

### Added
- SVG geometry module for path/curve conversion
- Render QA with visual evidence
- Rich speaker notes support

## [1.1.0] — 2026-05-01

### Added
- Core SVG-first pipeline: SVG authoring → PPTX export
- Source intake (PDF/DOCX/XLSX/HTML/URL → Markdown)
- Project workspace management
- Basic QA framework
