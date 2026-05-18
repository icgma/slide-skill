# Guide: PPTX Export (v2.0)

---

## Export Command

```bash
slide-skill export <project>
# or specify output path
slide-skill export <project> -o path/to/deck.pptx
```

Always export from `svg_final/` (the default). Use `--stage output` only for quick iteration.

---

## SVG → PPTX Conversion

The exporter converts each SVG element to a native PPTX object where possible.

### Supported SVG → PPTX Mappings

| SVG element | PPTX object | Notes |
|------------|-------------|-------|
| `<rect>` | Rectangle shape | `rx` → Rounded Rectangle |
| `<rect rx="...">` | Rounded Rectangle shape | |
| `<circle>` | Oval shape | |
| `<ellipse>` | Oval shape | |
| `<line>` | Straight connector | |
| `<text>` | Textbox | font-size, font-weight, fill |
| `<image>` | Picture | local file path |
| `<path>` | Freeform shape | via DrawingML custGeom |
| `<polygon>` | Freeform shape | closed path |
| `<polyline>` | Freeform shape | open path |

### Gradient Handling (v2.0)

Gradient fills (`fill="url(#id)"`) are resolved to a solid approximation using the
midpoint stop colour. The visual result is a solid-filled shape rather than a true
gradient — gradients are preserved visually only in the SVG render, not in PPTX.

To preserve gradient fidelity in PPTX, render the slide to an image first and embed
it as a picture (`slide-skill render ...`).

### Opacity Handling (v2.0)

`opacity` and `fill-opacity` are supported — best effort. Simple transparency values
are applied where python-pptx exposes transparency APIs.

### Transform Handling (v2.0)

Simple `transform="translate(tx, ty)"` is applied as a position offset. Complex
transforms (scale, rotate, matrix) are ignored with a logged note in the QA report.

### Filter Handling (v2.0)

`<filter>` references (drop shadows, blur) are not natively renderable in PPTX.
Shapes with filter references are exported without the filter applied. A note is
written to `qa/SVG-QA.md`.

---

## PPTX Validation

```bash
slide-skill validate-pptx path/to/deck.pptx
```

Checks:
- Valid ZIP/PPTX package structure
- `[Content_Types].xml` present
- At least one slide XML file
- Native editable shapes detected

---

## Extract Text from PPTX

```bash
slide-skill pptx-text path/to/deck.pptx
```

---

## Extract Speaker Notes from PPTX

```bash
slide-skill pptx-notes path/to/deck.pptx
```

---

## Export from Specific Stage

```bash
# Export from svg_output (skip finalization)
slide-skill export <project> --stage output -o draft.pptx

# Export from svg_final (production)
slide-skill export <project> --stage final
```

---

## Known Limitations

- Gradients export as solid mid-stop colour (not true gradient in PPTX)
- Drop shadow filters are silently dropped
- Complex SVG transforms (scale, rotate, matrix) are ignored
- `<clipPath>` clipping is not applied in PPTX
- `<use>` elements referencing local defs are silently skipped
- Text in `<tspan>` elements is concatenated into the parent textbox
