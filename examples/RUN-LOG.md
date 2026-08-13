# End-to-End Validation Run Log

Generated: 2026-05-02

## Purpose

Validate the slide-skill v2.0 pipeline produces clean SVG and valid PPTX for at
least two themes using a representative sample Markdown deck.

## Source File

`examples/sample.md` — 14-slide "AI-Powered Analytics Platform" deck with a
variety of layout types: default, bullet-list, metric-highlight, and two-column.

## Commands Executed

### Theme: dark-tech

```
slide-skill quickstart sample.md --theme dark-tech --name sample-dark-tech
slide-skill check-svg projects/sample-dark-tech
slide-skill validate-pptx projects/sample-dark-tech/exports/sample-dark-tech_*.pptx
```

Results:
- quickstart: **passed** (14 SVGs generated, exported to PPTX)
- check-svg: **passed** — `status: passed`, no issues found
- validate-pptx: **valid**
- QA.md: `status: automated-passed` — PPTX Package ✓, SVG Gate ✓, Placeholder Scan ✓

### Theme: light-corporate

```
slide-skill quickstart sample.md --theme light-corporate --name sample-light-corporate
slide-skill check-svg projects/sample-light-corporate
slide-skill validate-pptx projects/sample-light-corporate/exports/sample-light-corporate_*.pptx
```

Results:
- quickstart: **passed** (14 SVGs generated, exported to PPTX)
- check-svg: **passed** — `status: passed`, no issues found
- validate-pptx: **valid**
- QA.md: `status: automated-passed` — PPTX Package ✓, SVG Gate ✓, Placeholder Scan ✓

## Known Observations

- Slide 8 body text ("Why Now") is long and gets truncated at the PPTX text-extraction
  boundary — the visual SVG contains the full sentence but python-pptx text extraction
  cuts off at the last shape boundary. Content fits the slide visually; worth tracking
  as a text-overflow/wrapping improvement area.

## Artifacts Committed

```
examples/
  sample.md                          # source Markdown
  RUN-LOG.md                         # this file
  sample-dark-tech/
    deck.pptx                        # exported presentation
    svg_output/                      # 14 generated SVG slides
    design_spec.md                   # design spec written by create_spec()
    SVG-QA.md                        # SVG quality gate report (passed)
    QA.md                            # full QA report (automated-passed)
  sample-light-corporate/
    deck.pptx
    svg_output/
    design_spec.md
    SVG-QA.md
    QA.md
```
