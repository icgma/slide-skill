# Examples

Real example slides produced with the v2.0 pipeline. Each file is a hand-crafted
SVG that follows `skills/slide/design_guide.md` exactly — the same structure the
LLM Executor agent generates when running through `slide-skill generate-guide`.

GitHub renders SVG inline, so the files in `svg/` double as both source and
preview. To produce a PPTX from them:

```bash
# Drop the svg/ files into a project under <project>/svg_output/
slide-skill export <project> --output deck.pptx
```

| # | File | Theme | Layout | What it shows |
|---|------|-------|--------|---------------|
| 01 | `svg/01-cover-dark-tech.svg` | dark-tech | cover | Title slide with linear-gradient background, radial accent glow, 4px accent rule |
| 02 | `svg/02-bullet-list-light-corporate.svg` | light-corporate | bullet-list | 5 alternating-row bullets with bullet glyphs and rounded surfaces |
| 03 | `svg/03-metric-highlight-data-forward.svg` | data-forward | metric-highlight | 3 metric cards with top-bar accent, big numerics, supporting context |
| 04 | `svg/04-two-column-warm-editorial.svg` | warm-editorial | two-column | Editorial side-by-side comparison, serif type, italic pull-quotes |
| 05 | `svg/05-section-divider-vibrant-startup.svg` | vibrant-startup | section-divider | Full-width gradient band with section label and headline |
| 06 | `svg/06-closing-dark-tech.svg` | dark-tech | closing | Centered closing slide with radial-gradient backdrop and contact line |

## Why these are useful

- **Reference for the LLM Executor.** Few-shot these into the prompt when the
  Executor needs help nailing a specific layout or theme.
- **Regression target.** The QA pipeline (`SVGQualityChecker`) accepts every
  one of these as-is — they exercise gradients, `letter-spacing`, `text-anchor`,
  rounded `rect` surfaces, and stroked outlines without tripping any banned-tag
  rule.
- **Theme showcase.** All five v2.0 themes are represented, so designers can
  see real palette + type pairings before picking one.
