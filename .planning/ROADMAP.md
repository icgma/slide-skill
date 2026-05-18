# Roadmap: Slide Skill

## Milestones

- [x] **v1.1 Follow-Up** — Phases 1-7 shipped 2026-05-01. Archive: `milestones/v1.1-ROADMAP.md`.
- [x] **v1.2 SVG Geometry, Render QA, Rich Notes** — Phases 8-10 shipped 2026-05-01. Archive: `milestones/v1.2-ROADMAP.md`.
- [x] **v1.3 Animations, TTS, Multi-Format Canvas, Competition Toolkit** — Phases 11-16 shipped 2026-05-02.
- [x] **v1.3.1 SVG Rendering Redesign** — Phase 17 shipped 2026-05-02.
- [x] **v1.4 Visual Authoring Power Pack** — Phases 18-25 shipped 2026-05-03. Archive: `milestones/v1.4-ROADMAP.md`.
- [x] **v1.5 Visual Quality & Template System** — Shipped 2026-05-06. Archive: `milestones/v1.5-ROADMAP.md`.
- [x] **v2.0 Pipeline Hardening & End-to-End Flow** — Shipped 2026-05-08. Archive: `milestones/v2.0-ROADMAP.md`.
- [x] **v2.1 Advanced SVG Conversion** — Phases 26-28 shipped 2026-05-08.
- [x] **v2.2 SVG Filter Effects** — Phases 29-30 shipped 2026-05-08.
- [x] **v2.3 Advanced Filters, Bilingual & PDF Export** — Phases 31-33 shipped 2026-05-10.
- [x] **v3.0 Intelligent Content Planning & Domain-Specific Layouts** — Shipped 2026-05-17. Archive: `milestones/v3.0-ROADMAP.md`.

---

## v3.0 Intelligent Content Planning & Domain-Specific Layouts

**Goal:** Transform the pipeline from mechanical markdown-to-slides conversion into an intelligent content planning system that understands domain context (teaching, course, competition) and applies specialized layouts with appropriate density rules and visual strategies.

**Phase order rationale:** Content planning layer first because it's the intelligence foundation that all domain renderers depend on. Teaching domain second because it has the most complex layout requirements (pinyin, bilingual, auto-sizing). Course and Competition domains last as they build on established patterns.

**Granularity:** coarse

| # | Phase | Status | Plans | Dependencies |
|---|-------|--------|-------|--------------|
| 34 | Content Planning Layer (intelligent slide planning) | Complete | 1/1 | — |
| 35 | Teaching Domain Renderer (vocab, dialogue, sentences) | Complete | 1/1 | 34 |
| 36 | Course Domain Renderer (objectives, concepts, cases) | Complete | 1/1 | 34 |
| 37 | Competition Domain Renderer (team, metrics, timeline) | Complete | 1/1 | 34 |

### Phase 34: Content Planning Layer
**Goal**: Replace naive `_markdown_to_slides()` with intelligent `ContentPlanner` that detects content types (vocabulary, dialogue, metrics, process flows) and produces structured `SlidePlan` objects with domain-aware density rules.
**Depends on**: Nothing (first v3.0 phase)
**Requirements**: CP-01, CP-02, CP-03, CP-04, CP-05
**Success Criteria** (what must be TRUE):
  1. User provides Markdown with vocabulary items in format "医院 (yīyuàn) — hospital" and planner detects type="vocabulary", assigns layout="vocab-card", caps at 4 items/slide for teaching domain
  2. User provides Markdown with A/B dialogue lines and planner detects type="dialogue", assigns layout="dialogue" with speaker metadata
  3. Planner enforces max_slides limit by inserting closing slide when exceeded
  4. Anti-monotony pass breaks runs of 3+ consecutive slides with same content layout by rotating middle slide to alternative layout
  5. `slide-skill plan <source.md> --domain teaching` outputs structured plan as markdown table or JSON showing layout assignments and item counts
**Plans**: [34-01-PLAN.md](phases/34-content-planning/34-01-PLAN.md)

### Phase 35: Teaching Domain Renderer
**Goal**: Specialized SVG renderers for language education content with pinyin support, auto-sizing Chinese characters, and bilingual annotations.
**Depends on**: Phase 34 (content planning)
**Requirements**: TD-01, TD-02, TD-03, TD-04
**Success Criteria** (what must be TRUE):
  1. `vocab-card` layout renders 1-4 large vocabulary items per slide with Chinese characters (auto-sized: 2-char=64pt, 3-4-char=52pt, 5+-char=40pt), pinyin above (accent color), English translation below (muted)
  2. `sentence-example` layout renders example sentences with Chinese text, pinyin annotation, and optional English translation in card-style containers
  3. `dialogue` layout renders A/B conversation bubbles with speaker labels in circles, alternating left/right alignment
  4. All teaching layouts include chrome elements (left accent stripe, footer with page numbers) and decorative orbs matching theme palette
**Plans**: TBD

### Phase 36: Course Domain Renderer
**Goal**: Academic presentation layouts optimized for classroom delivery with learning objectives, concept explanations, case studies, and discussion prompts.
**Depends on**: Phase 34 (content planning)
**Requirements**: CD-01, CD-02, CD-03
**Success Criteria** (what must be TRUE):
  1. `learning-objectives` layout presents 3-5 goals with numbered markers and clear hierarchy
  2. `key-concept` layout explains core ideas with definition boxes, examples, and visual emphasis
  3. `case-study` layout structures background → analysis → takeaways in readable sections
  4. `discussion` layout presents questions with space for notes or responses
**Plans**: TBD

### Phase 37: Competition Domain Renderer
**Goal**: Pitch deck layouts for student competitions (互联网+, 挑战杯) mapping to standard judging criteria with team showcase, metrics dashboards, timelines, and competitive analysis.
**Depends on**: Phase 34 (content planning)
**Requirements**: COMP-01, COMP-02, COMP-03, COMP-04
**Success Criteria** (what must be TRUE):
  1. `team-grid` layout displays team members with photos placeholders, names, roles in organized grid
  2. `metrics-dashboard` layout shows KPI cards with large numbers, labels, and trend indicators
  3. `timeline` layout visualizes project phases with connected nodes and quarter labels
  4. `comparison-matrix` layout presents feature comparison across competitors with checkmarks/crosses
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 34 -> 35 -> 36 -> 37

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 34. Content Planning Layer | 1/1 | Complete | 2026-05-17 |
| 35. Teaching Domain Renderer | 1/1 | Complete | 2026-05-17 |
| 36. Course Domain Renderer | 1/1 | Complete | 2026-05-17 |
| 37. Competition Domain Renderer | 1/1 | Complete | 2026-05-17 |

---

## v2.3 Advanced Filters, Bilingual & PDF Export

**Goal:** Complete remaining SVG filter effects (outer glow, soft edge, effectLst pipeline fixes) and add two new output modes -- bilingual parallel text and PDF handout with notes.

**Phase order rationale:** Filter effects first (Phase 31) because soft edge, outer glow, and effectLst pipeline fixes share `filter_effects.py` infrastructure and must be delivered together for correctness. Bilingual export second (Phase 32) because it touches text converters and i18n -- a different subsystem that benefits from a stable filter pipeline. PDF handout last (Phase 33) because it is completely independent (new module, new dependency) and lowest risk.

**Granularity:** coarse

| # | Phase | Status | Plans | Dependencies |
|---|-------|--------|-------|--------------|
| 31 | Advanced Filter Effects (soft edge + glow + effectLst fixes) | Complete | 1/1 | — |
| 32 | Bilingual Export (dual-language text layout) | Complete | 1/1 | — |
| 33 | PDF Handout Export (slides + notes as PDF) | Complete | 1/1 | — |

### Phase 31: Advanced Filter Effects
**Goal**: SVG soft edge, outer glow, and multi-effect composition all convert correctly to DrawingML, with effectLst child ordering enforced per OOXML schema
**Depends on**: Nothing (first v2.3 phase)
**Requirements**: FE-01, FE-02, FE-03, FE-04, FE-05
**Success Criteria** (what must be TRUE):
  1. User provides SVG with `feGaussianBlur` on `SourceAlpha` (no companion feOffset/feFlood) and the exported PPTX contains `<a:softEdge rad="N"/>` with radius derived from `stdDeviation`
  2. User provides SVG with a `feGaussianBlur` + `feFlood` + `feComposite` chain (no feOffset) and the exported PPTX contains `<a:glow>` with color from feFlood and radius from the Gaussian blur
  3. A shape with both glow and shadow effects has both `<a:glow>` and `<a:outerShdw>` in the same `<a:effectLst>`, ordered per XSD sequence (blur, fillOverlay, glow, innerShdw, outerShdw, prstShdw, reflection, softEdge) -- PowerPoint opens the file without discarding effects
  4. SVG QA no longer flags `feFlood`, `feComposite`, or `feMerge` as banned tags
**Plans**: [31-01-PLAN.md](phases/31-advanced-filter-effects/31-01-PLAN.md)

### Phase 32: Bilingual Export
**Goal**: Chinese + English text appears as parallel, independently styled text frames in exported PPTX, with correct CJK/Latin width estimation and RTL support
**Depends on**: Nothing (independent from Phase 31)
**Requirements**: BI-01, BI-02, BI-03, BI-04, BI-05, BI-06
**Success Criteria** (what must be TRUE):
  1. SVG element with `data-bilingual="true"` containing Chinese and English `<text>` children produces two PPTX text frames stacked vertically (Chinese above, English below) with correct content in each frame
  2. Slide with `data-layout="side-by-side"` places Chinese text on the left and English text on the right in the exported PPTX
  3. English text frame uses a smaller font size than the Chinese frame (e.g., 18pt vs 24pt), customizable via `data-lang-size` attribute on the SVG element
  4. `_approx_w_in()` and `i18n.py` LanguageProfile use consistent CJK width factor (unified from current 1.0 vs 1.8 mismatch), producing correct text frame widths for mixed CJK/Latin content
  5. Arabic/Hebrew text paired with English produces correct RTL layout in the exported PPTX bilingual text frames
**Plans**: TBD

### Phase 33: PDF Handout Export
**Goal**: Users can generate a multi-page PDF handout with slide thumbnails and formatted speaker notes, supporting CJK text and multiple layouts
**Depends on**: Nothing (completely independent new module)
**Requirements**: PD-01, PD-02, PD-03, PD-04, PD-05, PD-06
**Success Criteria** (what must be TRUE):
  1. Running the PDF handout command on a deck with speaker notes produces a multi-page PDF where each page has one slide thumbnail at the top and its speaker notes below
  2. User selects 2-up or 3-up layout and the PDF arranges 2 or 3 smaller slide thumbnails per page with their respective notes
  3. Speaker notes containing bold, italic, and bullet lists render with corresponding formatting in the PDF output
  4. Canvas presets (ppt169, xhs, wechat, etc.) automatically set the correct page aspect ratio in the PDF
  5. Chinese speaker notes render correctly in the PDF with embedded CJK font (Noto Sans SC or system font fallback)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 31 -> 32 -> 33

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 31. Advanced Filter Effects | 1/1 | Complete | 2026-05-10 |
| 32. Bilingual Export | 1/1 | Complete | 2026-05-10 |
| 33. PDF Handout Export | 1/1 | Complete | 2026-05-10 |

---

## Completed Milestones

<details>
<summary>v3.0 Intelligent Content Planning & Domain-Specific Layouts (Phases 34-37) -- Shipped 2026-05-17</summary>

**Goal:** Transform from mechanical markdown-to-slides to intelligent content planning with domain-specific renderers for teaching, course, and competition scenarios.

| # | Phase | Status | Plans | Dependencies |
|---|-------|--------|-------|--------------|
| 34 | Content Planning Layer | Complete | 1/1 | — |
| 35 | Teaching Domain Renderer | Complete | 1/1 | 34 |
| 36 | Course Domain Renderer | Complete | 1/1 | 34 |
| 37 | Competition Domain Renderer | Complete | 1/1 | 34 |

### Phase 34: Content Planning Layer
**Requirements:** CP-01..05
- `content_planner.py` module detects 8 content types: vocabulary, dialogue, metrics, process, bullets, paragraph, quote, empty
- Configurable per domain via `ContentConfig(domain="teaching"|"course"|"competition"|"general")`
- Anti-monotony pass breaks runs of 3+ identical layouts
- Max slides enforcement with automatic closing slide insertion
- New CLI command: `slide-skill plan <source.md> --domain teaching` outputs structured plan

### Phase 35: Teaching Domain Renderer
**Requirements:** TD-01..04
- `vocab-card`: 1-4 large vocabulary items with auto-sized Chinese characters (2-char=64pt, 3-4-char=52pt, 5+-char=40pt)
- Pinyin annotations above characters in accent color
- English translations below in muted color
- `sentence-example`: Example sentences with Chinese, pinyin, optional translation
- `dialogue`: A/B conversation bubbles with speaker labels in circles

### Phase 36: Course Domain Renderer
**Requirements:** CD-01..03
- `learning-objectives`: Numbered goal list with clear hierarchy
- `key-concept`: Definition boxes with examples and visual emphasis
- `case-study`: Background → Analysis → Takeaways structure
- `discussion`: Question prompts with space for notes

### Phase 37: Competition Domain Renderer
**Requirements:** COMP-01..04
- `team-grid`: Team member showcase with photos, names, roles
- `metrics-dashboard`: KPI cards with large numbers and trend indicators
- `timeline`: Connected phase nodes with quarter labels
- `comparison-matrix`: Feature comparison across competitors

**New Modules:**
- `content_planner.py` (562 lines)
- `domain_teaching.py` (478 lines)
- `domain_course.py` (443 lines)
- `domain_competition.py` (443 lines)

**Tests Added:** 61 new tests (460 total, 100% passing)
- `test_content_planner.py`: 25 tests
- `test_domain_teaching.py`: 22 tests
- `test_domain_course.py`: 7 tests
- `test_domain_competition.py`: 7 tests

**New CLI Commands:**
- `slide-skill plan`: Generate structured slide plan from Markdown
- `slide-skill build`: Full v3 pipeline with domain awareness
- `slide-skill preview`: Build + open HTML preview in browser
- `slide-skill adjust`: Regenerate specific slide in existing project

</details>

<details>
<summary>v2.2 SVG Filter Effects (Phases 29-30) -- Shipped 2026-05-08</summary>

**Goal:** 实现 SVG filter 效果到 DrawingML 的转换，使 SVG 管线支持高斯模糊和投影阴影

| # | Phase | Status | Plans | Dependencies |
|---|-------|--------|-------|--------------|
| 29 | Gaussian Blur (feGaussianBlur -> effectLst blur) | Complete | 1/1 | — |
| 30 | Drop Shadow (feDropShadow -> effectLst outerShdw) | Complete | 1/1 | 29 |

### Phase 29: Gaussian Blur
**Requirements:** BLUR-01..04, PIPE-01..02
- SVG `<filter>` with `<feGaussianBlur>` parsed for `stdDeviation`.
- `filter="url(#filterId)"` on SVG elements resolved at export time.
- DrawingML `<a:effectLst><a:blur rad="N"/></a:effectLst>` injected into `spPr`.
- `filter` elements registered as `_noop_converter`.
- SVG QA updated: `filter`, `feGaussianBlur` no longer banned.
- Exporter dispatch loop checks `filter` attribute and applies effects.

### Phase 30: Drop Shadow
**Requirements:** SHAD-01..04, PIPE-03
- SVG `<feDropShadow>` parsed for `dx`, `dy`, `stdDeviation`, `flood-color`, `flood-opacity`.
- `<feOffset>` + `<feGaussianBlur>` combination recognized as shadow.
- DrawingML `<a:effectLst><a:outerShdw>` with offset, blur radius, color, alpha.
- Multiple effects in same `<effectLst>` composed in schema order.
- SVG QA updated: `feDropShadow`, `feOffset` no longer banned.

</details>

<details>
<summary>v2.1 Advanced SVG Conversion (Phases 26-28) -- Shipped 2026-05-08</summary>

### Phase 26: Gradient Fill
**Requirements:** GF-01..05
- SVG `<linearGradient>` -> DrawingML `gradFill` (linear).
- SVG `<radialGradient>` -> DrawingML `gradFill` (radial).
- Gradient stops: offset, stop-color, stop-opacity correctly mapped.
- `url(#gradientId)` references resolved in fill/stroke attributes.
- SVG QA updated: gradient definitions no longer flagged as banned tags.

### Phase 27: Clip-Path & Mask
**Requirements:** CP-01..04
- SVG `<clipPath>` -> DrawingML customGeometry clip.
- SVG `<mask>` -> approximate DrawingML effect or grouped clip.
- `clip-path="url(#clipId)"` attribute resolved and applied.
- SVG QA updated: clip-path/mask references no longer trigger banned attribute errors.

### Phase 28: Pattern Fill
**Requirements:** PF-01..04
- SVG `<pattern>` -> DrawingML `blipFill` (pattern image tiling).
- Pattern width/height/repeat mapped to tiling parameters.
- `url(#patternId)` references resolved in fill attributes.
- SVG QA updated: pattern definitions no longer flagged as banned tags.

</details>

<details>
<summary>v1.1-v2.0 (Phases 1-25) -- Shipped 2026-05-01 through 2026-05-08</summary>

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1 | v1.1 | 1/1 | Complete | 2026-05-01 |
| 2 | v1.1 | 1/1 | Complete | 2026-05-01 |
| 3 | v1.1 | 1/1 | Complete | 2026-05-01 |
| 4 | v1.1 | 1/1 | Complete | 2026-05-01 |
| 5 | v1.1 | 1/1 | Complete | 2026-05-01 |
| 6 | v1.1 | 1/1 | Complete | 2026-05-01 |
| 7 | v1.1 | 1/1 | Complete | 2026-05-01 |
| 8 | v1.2 | 1/1 | Complete | 2026-05-01 |
| 9 | v1.2 | 1/1 | Complete | 2026-05-01 |
| 10 | v1.2 | 1/1 | Complete | 2026-05-01 |
| 11 | v1.3 | 1/1 | Complete | 2026-05-02 |
| 12 | v1.3 | 1/1 | Complete | 2026-05-02 |
| 13 | v1.3 | 1/1 | Complete | 2026-05-02 |
| 14 | v1.3 | 1/1 | Complete | 2026-05-02 |
| 15 | v1.3 | 1/1 | Complete | 2026-05-02 |
| 16 | v1.3 | 1/1 | Complete | 2026-05-02 |
| 17 | v1.3.1 | 1/1 | Complete | 2026-05-02 |
| 18 | v1.4 | 1/1 | Complete | 2026-05-03 |
| 19 | v1.4 | 1/1 | Complete | 2026-05-03 |
| 20 | v1.4 | 1/1 | Complete | 2026-05-03 |
| 21 | v1.4 | 1/1 | Complete | 2026-05-03 |
| 22 | v1.4 | 1/1 | Complete | 2026-05-03 |
| 23 | v1.4 | 1/1 | Complete | 2026-05-03 |
| 24 | v1.4 | 1/1 | Complete | 2026-05-03 |
| 25 | v1.4 | 1/1 | Complete | 2026-05-03 |

</details>

## Archives

- `milestones/v1.1-ROADMAP.md` -- v1.1 archive.
- `milestones/v1.2-ROADMAP.md` -- v1.2 archive.
- `milestones/v1.4-ROADMAP.md` -- v1.4 archive.
- `milestones/v1.5-ROADMAP.md` -- v1.5 archive.
- `milestones/v2.0-ROADMAP.md` -- v2.0 archive.
- `milestones/v2.1-ROADMAP.md` -- v2.1 archive.
- `milestones/v3.0-ROADMAP.md` -- v3.0 archive (to be created).
