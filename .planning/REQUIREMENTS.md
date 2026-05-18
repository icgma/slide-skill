# Requirements: Slide Skill v2.3

**Defined:** 2026-05-10
**Core Value:** Agents can produce and modify PowerPoint decks that are valid, visually reviewable, natively editable, and backed by repeatable QA evidence.

## v2.3 Requirements

Requirements for milestone v2.3 -- Advanced Filters, Bilingual & PDF Export.

### SVG Filter Effects

- [ ] **FE-01**: Soft edge -- SVG `feGaussianBlur` + `in="SourceAlpha"` -> DrawingML `<a:softEdge rad="N"/>`
- [ ] **FE-02**: Outer glow -- SVG `feGaussianBlur`+`feFlood`+`feComposite` chain -> DrawingML `<a:glow>` + color child elements
- [ ] **FE-03**: effectLst XSD ordering -- Effect child elements ordered per OOXML schema (blur -> softEdge -> outerShdw -> glow)
- [ ] **FE-04**: Multi-effect composition -- Same shape supports glow+shadow/blur+glow mixed effects without overwriting
- [ ] **FE-05**: SVG QA update -- `feFlood`, `feComposite`, `feMerge` no longer flagged as banned tags

### Bilingual Export

- [ ] **BI-01**: Stacked bilingual text boxes -- Chinese+English two-line text boxes, stacked in each page content area
- [ ] **BI-02**: Side-by-side layout -- Slide-level `data-layout="side-by-side"` attribute supports parallel display
- [ ] **BI-03**: Per-language font size -- English smaller than Chinese (e.g., Chinese 24pt, English 18pt), customizable via `data-lang-size` attribute
- [ ] **BI-04**: `data-bilingual` SVG convention -- Annotate `<text>` elements for bilingual content, AI follows this convention when generating
- [ ] **BI-05**: Unified width estimation -- Fix `_approx_w_in()` vs `i18n.py` CJK width factor inconsistency (1.0 vs 1.8)
- [ ] **BI-06**: RTL support -- Arabic/Hebrew + English bilingual layout support

### PDF Handout Export

- [ ] **PD-01**: Single slide + notes PDF -- One slide thumbnail per page with speaker notes below
- [ ] **PD-02**: Multi-slide per page layout -- 2-up and 3-up modes, reduced slide thumbnails arranged in grid
- [ ] **PD-03**: Notes formatting -- Bold, italic, lists in speaker notes render formatted in PDF
- [ ] **PD-04**: Custom page size -- Auto-adapt page ratio by canvas preset (ppt169, xhs, etc.)
- [ ] **PD-05**: CairoSVG + fpdf2 pipeline -- SVG->PNG thumbnails + fpdf2 composite output, `fpdf2>=2.8.7` as optional dependency
- [ ] **PD-06**: CJK font embedding -- Embed Noto Sans SC or Microsoft YaHei in PDF for correct Chinese rendering

## Deferred Requirements

(None -- all original deferred items promoted to v2.3)

## Out of Scope

| Feature | Reason |
|---------|--------|
| SVG filter beyond glow/softEdge (feColorMatrix, feTurbulence, etc.) | High complexity, v2.3 only covers most common effects |
| Full presentation SaaS / GUI editor | Local agent skill priority |
| Pixel-perfect cross-renderer parity | Deterministic local QA priority |
| Real-time bilingual editing preview | Out of v2.3 scope, future milestone candidate |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FE-01 | 31 | Pending |
| FE-02 | 31 | Pending |
| FE-03 | 31 | Pending |
| FE-04 | 31 | Pending |
| FE-05 | 31 | Pending |
| BI-01 | 32 | Pending |
| BI-02 | 32 | Pending |
| BI-03 | 32 | Pending |
| BI-04 | 32 | Pending |
| BI-05 | 32 | Pending |
| BI-06 | 32 | Pending |
| PD-01 | 33 | Pending |
| PD-02 | 33 | Pending |
| PD-03 | 33 | Pending |
| PD-04 | 33 | Pending |
| PD-05 | 33 | Pending |
| PD-06 | 33 | Pending |

**Coverage:**
- v2.3 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0

---
*Requirements defined: 2026-05-10*
*Last updated: 2026-05-10 -- roadmap created, all requirements mapped to phases 31-33*
