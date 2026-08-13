# Route: free-design — Host-Agent SVG Authoring

**You, the host agent, hand-write every SVG page.** The toolkit supplies the
design contract (spec_lock + design guide), the QA gates, and the lossless
SVG→PPTX conversion. This is the highest-ceiling route: deck quality equals
the quality of the model driving it. Budget 10–30 minutes for a 10-page deck.

## Pipeline

```
init → spec → generate-guide → [write svg_output/slide_NN.svg one page at a time]
     → check-svg (per page) → finalize-svg → export → render/review → qa --strict
```

### 1. Set up the project

```bash
slide-skill init <name> --theme <theme>          # creates projects/<name>/
slide-skill spec projects/<name> --source <source.md> --theme <theme>
```

`spec` writes `design_spec.md` and `spec_lock.json` — the locked palette,
typography, and canvas contract for this deck. Everything you draw must obey it.

### 2. Generate the design guide

```bash
slide-skill generate-guide projects/<name> --source <source.md>
```

This writes `design_guide.md` (12-role palette table, typography ramp, chrome
coordinates, layout templates with full SVG examples) and copies executor
reference docs into `projects/<name>/references/`. Read `design_guide.md` in
full, plus `references/executor-base.md`, before writing any page.

### 3. Plan the deck

Read the source and decide the page list: title, layout family, and content of
each page. Write it down (a simple numbered list is fine) so page N+1 is written
with page N's decisions in view. Vary composition — a deck where every page is
the same card grid reads as machine output.

### 4. Write the pages — PER-PAGE DISCIPLINE

This discipline is what makes agent-authored decks consistent. Each rule exists
because its violation has produced broken decks.

1. **One page at a time, in deck order.** Write `svg_output/slide_01.svg`
   completely, then slide_02, then slide_03. One file per edit. Never draft
   several pages in one pass, never fill pages out of order.
2. **Re-read `spec_lock.json` before EVERY page.** Open it and re-check the
   palette hexes and font stack before each new file. Long sessions compress
   context; without this re-read, later pages drift off-palette and layouts
   collapse into one repeated pattern.
3. **Hand-write the SVG yourself.** Never generate pages with a script or loop,
   and never delegate pages to a sub-agent. Cross-page visual consistency
   requires one author holding the full upstream context; a script or fresh
   sub-agent has neither.
4. **Closed world for visible text.** Every visible string comes from the
   source document or the agreed plan. No invented numbers, claims, or filler.
   The QA gate checks fidelity in both directions — missing planned content
   AND unsourced visible text both block publish.
5. **Gate as you go.** Run `slide-skill check-svg projects/<name>` after each
   page — after every 3 pages at absolute minimum — and fix every reported
   error before writing the next page. Errors compound; late discovery means
   rewriting many pages.
6. **Chrome on every page.** Left accent stripe, footer bar, and `NN / TT`
   page number exactly as `design_guide.md` specifies. Canvas is always
   `width="1280" height="720" viewBox="0 0 1280 720"`.
7. **Stay inside the supported element set.**
   - Allowed: `rect circle ellipse line text tspan image path polygon polyline
     g defs linearGradient radialGradient stop filter feGaussianBlur
     feDropShadow feOffset feFlood feComposite feMerge feMergeNode clipPath
     mask pattern use title desc`
   - Banned (hard error): `script foreignObject iframe animate
     animateTransform set animateMotion` and any `on*` event attribute.
   - Structure: semantic top-level groups (`<g id="background">`,
     `<g id="content-title-NN">`, `<g id="chrome-footer">`, …); gradients and
     filters inside `<defs>`; only local `url(#id)` references.
8. **Finish through the gates — then read the report.**

   ```bash
   slide-skill check-svg projects/<name>          # final structural pass
   slide-skill finalize-svg projects/<name>       # svg_output → svg_final
   slide-skill export projects/<name>             # svg_final → exports/*.pptx
   slide-skill render <exported.pptx> -o projects/<name>/qa/rendered
   slide-skill qa projects/<name> --strict        # strict QA with evidence
   ```

   Inspect every rendered page and write `qa/VISUAL-REVIEW.md`. Record the fix
   cycle (or “no fixes required”) in `qa/FIX-VERIFY.md`. If LibreOffice/Poppler
   is unavailable, capture every `svg_final/slide_NN.svg` at 1280×720 with
   headless Chrome into `qa/rendered/` and note the fallback in both files.
   Open `qa/QA.md`; only report completion when its status is `passed`.

## Composition guidance

- Use the layout families from `design_guide.md` §6-7: cover, section-divider,
  bullet-list, two-column, metric-highlight, quote, closing. Pick per page
  based on content shape — metrics get metric cards, comparisons get columns.
- Respect page rhythm (§3.5): never 3+ consecutive pages with the same density;
  cover/closing are anchors; dividers breathe.
- Title length rules: ≤15 chars → 56-64px, 16-25 → 44-48px, 26+ → split lines.
- Text safe area: x 80–1200, y 80–680. Overflow is a QA error, not a style choice.

## Fallback

If you cannot hand-author SVG in this session (context limits, capability),
say so and fall back to the built-in AI executor
(`slide-skill quickstart <md> --mode ai`, needs `OPENAI_API_KEY`) or
[fast mode](fast.md). Do not silently script-generate pages — that defeats
this route's purpose and produces the exact monotony this discipline prevents.
