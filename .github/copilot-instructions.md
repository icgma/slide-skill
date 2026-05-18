# Slide Skill Instructions

When the user asks to create, edit, or verify a PowerPoint deck (PPTX), follow the Slide Skill workflow.

## Design Gate

Before SVG generation, collect 8 confirmations: title, audience, key_points, layout_strategy, color_scheme, page_count, special_requirements, confirmation. Use `slide-skill confirm <project> --title "..." --audience "..." ...` and `slide-skill check-confirm <project>`.

## Pipeline

```
source → Markdown → init project → spec → SVG gen → SVG QA → finalize → export PPTX → QA
```

## Quick Start

```bash
slide-skill quickstart source.md --name my-deck
```

## Step-by-Step

```bash
slide-skill init my-deck --format ppt169
slide-skill source-to-md input.pdf -o projects/my-deck/sources/source.md
slide-skill spec projects/my-deck --source projects/my-deck/sources/source.md
slide-skill svg projects/my-deck --source projects/my-deck/sources/source.md
slide-skill check-svg projects/my-deck
slide-skill finalize-svg projects/my-deck
slide-skill export projects/my-deck
slide-skill qa projects/my-deck
```

## Key Commands

- `slide-skill narrate <project>` — TTS audio from notes
- `slide-skill formats` — list canvas presets
- `slide-skill qa <project> --strict` — full QA with visual evidence

## Animation

Add to SVG `<g>` elements:
- `data-transition="fade|push|wipe|split|zoom"`
- `data-anim="fly-in|fade-in|wipe|zoom-in|float-in"`
- `data-anim-duration="500"` / `data-anim-delay="0"`

## Notes

Speaker notes support Markdown: `**bold**`, `*italic*`, `- bullets`.
