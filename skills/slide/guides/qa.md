# Guide: QA Loop (v2.0)

---

## SVG Quality Gate

```bash
slide-skill check-svg <project>
# or check the final stage
slide-skill check-svg <project> --stage final
```

Writes `qa/SVG-QA.md`. Returns exit code 0 if passed, 1 if failed.

### What is checked

| Check | Level |
|-------|-------|
| Root is `<svg>` with `width`, `height`, `viewBox` | error |
| `viewBox` matches `width` and `height` | error |
| No banned tags (`script`, `foreignObject`, `animate*`, `set`, `iframe`) | error |
| No `on*` event-handler attributes | error |
| `<path>` has non-empty `d` attribute | error |
| `<polygon>`/`<polyline>` have non-empty `points` | error |
| At least one semantic top-level `<g id="...">` | error |
| All top-level `<g>` have `id` attribute | error |
| `<use>` references external href | warning (non-blocking) |
| `design_guide.md` present in project | warning (non-blocking) |

### v2.0 Changes: Now Allowed

The following are **no longer errors** in v2.0:
- `opacity`, `fill-opacity`, `stroke-opacity` attributes
- `transform` attribute
- `class` and `style` attributes
- `fill="url(#local-id)"` gradient/pattern references
- `<defs>`, `<linearGradient>`, `<radialGradient>`, `<filter>`, `<clipPath>`
- `fill-opacity` on `<stop>` elements

---

## Full QA Run

```bash
# Basic QA
slide-skill qa <project>

# With PPTX validation
slide-skill qa <project> --pptx path/to/deck.pptx

# Strict (requires visual review and fix-verify evidence)
slide-skill qa <project> --strict
```

Writes `qa/QA-REPORT.md`. Returns exit code 0 if passed.

### QA Artifact Expectations

| Artifact | Required for basic | Required for strict |
|----------|--------------------|---------------------|
| `design_spec.md` | ✓ | ✓ |
| `spec_lock.json` | ✓ | ✓ |
| `design_guide.md` | ✓ (v2.0) | ✓ |
| `svg_output/*.svg` | ✓ | ✓ |
| `svg_final/*.svg` | ✓ | ✓ |
| `qa/SVG-QA.md` | ✓ | ✓ |
| `exports/*.pptx` | ✓ | ✓ |
| `qa/VISUAL-REVIEW.md` | — | ✓ |
| `qa/FIX-VERIFY.md` | — | ✓ |

---

## Visual QA (Strict Mode)

```bash
# Check render dependencies
slide-skill render-doctor

# Render PPTX to per-slide images
slide-skill render path/to/deck.pptx -o <project>/qa/rendered --dpi 150
```

After rendering, write `qa/VISUAL-REVIEW.md` with per-slide observations:
- Title placement correct
- Accent stripe present
- Footer bar visible
- No text overflow
- Colour palette matches spec_lock.json

---

## Fix-and-Verify Cycle

When visual issues are found, document the cycle in `qa/FIX-VERIFY.md`:

```markdown
## Fix-Verify Cycle 1

### Issues Found
- Slide 3: title overflow (font-size too large for 32-char title)
- Slide 5: bullet points not using accent colour

### Changes Made
- Reduced title font-size to 36px on slide 3
- Updated bullet text colour to #3B82F6 on slide 5

### Verified
- Re-rendered slides 3 and 5
- Both issues resolved
```

---

## QA Checklist (Manual)

Before declaring a deck production-ready:

- [ ] `slide-skill check-svg <project>` → `status: passed`
- [ ] `slide-skill validate-pptx <deck.pptx>` → `valid`
- [ ] `slide-skill qa <project> --pptx <deck.pptx>` → exit 0
- [ ] Visual review: accent stripe on every slide
- [ ] Visual review: footer bar on every slide
- [ ] Visual review: no text overflow
- [ ] Visual review: palette matches spec_lock.json
- [ ] Speaker notes embedded if requested
- [ ] Slide count matches `spec_lock.json` plan
