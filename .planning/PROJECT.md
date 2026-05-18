# Slide Skill

## What This Is

Slide Skill is a local agent-facing PowerPoint skill and Python toolkit. It takes source content (PDF, DOCX, Markdown) and produces natively editable .pptx files — every shape, text box, and curve is a real PowerPoint object, not an image. The pipeline runs locally with 8 built-in visual templates, 8 layout types, animations, TTS narration, and automated QA.

## Core Value

Agents can produce and modify PowerPoint decks that are valid, visually reviewable, natively editable, and backed by repeatable QA evidence.

## Requirements

### Validated

- [x] License-safe, clean-room scope documented in `NOTICE.md`.
- [x] SVG-first deck creation with canvas presets, spec lock, semantic groups, and strict unsupported-feature checks.
- [x] Native editable PPTX export for supported SVG primitives with package validation and backup artifacts.
- [x] Speaker notes embedded into PPTX notes parts and preserved as sidecar Markdown.
- [x] Template workflows: inspection, cross-run text replacement, duplicate/delete/reorder, and orphan media cleanup.
- [x] QA with automated structural checks, render dependency diagnostics, and strict visual/fix evidence gating.
- [x] SVG path geometry: all 20 SVG path commands convert to native DrawingML shapes.
- [x] Cross-render snapshot QA with pixel-similarity comparison.
- [x] Rich-text notes (bold, italic, lists) embedded in PPTX.
- [x] OOXML animations and page transitions from SVG data attributes.
- [x] TTS narration via edge-tts and Xiaomi MiMo (voice clone, voice design).
- [x] Multi-format canvas (11 presets: ppt169, xhs, wechat, story, etc.).
- [x] Student competition toolkit (6 templates, rehearse timer, draft notes).
- [x] 8 built-in visual templates + custom JSON template loading.
- [x] 8 layout types with semantic auto-selection + icon system.
- [x] CJK + Latin text auto-wrapping, content-aware centering, responsive typography.
- [x] Browser preview command for SVG slides.
- [x] Eight Confirmations design gate with confirmations.json persistence.
- [x] Design spec enrichment: audience, objective, per-page intent, visual strategy.
- [x] Image acquisition: CC search + AI generation + license filtering + metadata.
- [x] Spec propagation: incremental palette/font updates via update-spec.
- [x] Per-page spec_lock re-read with anti-drift warnings.
- [x] Dual-artifact export: native PPTX + SVG-as-image preview PPTX.
- [x] Gradient fill conversion from SVG linearGradient/radialGradient to DrawingML gradFill — v2.1
- [x] Clip-path and mask conversion to DrawingML a:clipPath — v2.1
- [x] Pattern fill conversion to DrawingML blipFill with tiling — v2.1
- [x] SVG filter effects: Gaussian blur and drop shadow conversion to DrawingML — v2.2

### Active

- [ ] SVG filter: outer glow (feGaussianBlur+feFlood+feComposite → DrawingML `<a:glow>`)
- [ ] SVG filter: soft edge (alpha feathering → DrawingML `<a:softEdge>`)
- [ ] Bilingual export (Chinese + English parallel text in PPTX)
- [ ] PDF handout export (slides + speaker notes as multi-page PDF)

### Deferred (from v1.5 Future Requirements)

(None — all deferred items promoted to v2.3 Active)

### Out of Scope

- Copyting proprietary upstream source — clean-room only.
- Full presentation SaaS or GUI editor — local agent skill first.
- Pixel-perfect cross-renderer parity in v1 — deterministic local QA first.
- SVG filter beyond blur/shadow (feColorMatrix, feComposite, feTurbulence, etc.)

## Current Milestone: v2.3 Advanced Filters, Bilingual & PDF Export

**Goal:** Complete remaining SVG filter effects (outer glow, soft edge) and add two new output modes — bilingual parallel text and PDF handout with notes.

**Target features:**
- Outer glow — SVG glow pattern → DrawingML `<a:glow>`
- Soft edge — SVG alpha feathering → DrawingML `<a:softEdge>`
- Bilingual export — Chinese + English parallel text layout in PPTX
- PDF handout export — slides + speaker notes rendered as multi-page PDF

## Context

Shipped 8 milestones (v1.1 through v2.2) over 2026-05-01 to 2026-05-08. The repository contains ~7,500+ LOC Python across source intake, SVG generation, PPTX export, template system, layout engine, TTS, competition toolkit, design gate, image acquisition, spec propagation, preview export, gradient fills, clip-path, pattern fill, filter effects, and QA.

## Current State

**Shipped:** v2.2 on 2026-05-08 — SVG Filter Effects (Gaussian blur + drop shadow in PPTX export).

**v2.2 added:** feGaussianBlur → effectLst blur, feDropShadow → effectLst outerShdw, filter attribute propagation from parent `<g>` elements. 15 new filter effect tests.

**v2.3 in progress:** outer glow, soft edge, bilingual export, PDF handout.

## Constraints

- **Licensing:** Clean-room scope, no copying upstream proprietary content.
- **Agent usability:** Skill must load quickly, deeper guides split into referenced files.
- **Verification:** Every workflow needs text QA and visual QA; success is evidence-based.
- **Compatibility:** Cross-platform components preferred, Windows support matters.
- **Dependencies:** New runtime dependencies must be justified and pinned.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SVG-first generation | AI authors SVG more reliably than DrawingML; conversion produces editable PPTX | ✓ Good |
| Palette-driven templates | Zero hardcoded colors, all from template palettes | ✓ Good |
| Semantic layout selection | Content keywords auto-detect layout type | ✓ Good |
| Custom JSON templates | Users define visual styles without code changes | ✓ Good |
| Clean-room scope | Upstream LICENSE.txt restricts derivatives | ✓ Good |
| GSD for planning | Structured phase-driven development | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-10 starting v2.3 milestone*
