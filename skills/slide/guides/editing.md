# Guide: Template Editing

---

## Inspect a PPTX Template

```bash
slide-skill template-inspect path/to/template.pptx
```

Returns JSON with: slide count, layouts, placeholders, slide dimensions.

---

## Replace Template Text

Provide a JSON mapping of old → new text strings:

```bash
slide-skill template-replace input.pptx output.pptx --map replacements.json
```

`replacements.json`:
```json
{
  "{{COMPANY_NAME}}": "Acme Corp",
  "{{YEAR}}": "2025",
  "{{PRESENTER}}": "Jane Smith"
}
```

---

## Delete Slides

```bash
# Delete slides 3 and 7 (1-indexed)
slide-skill template-delete input.pptx output.pptx --slides 3,7
```

---

## Reorder Slides

```bash
# New order: slide 2 first, then 1, then 3
slide-skill template-reorder input.pptx output.pptx --order 2,1,3
```

---

## Duplicate a Slide

```bash
# Duplicate slide 4
slide-skill template-duplicate input.pptx output.pptx --slide 4
```

---

## Speaker Notes

Write speaker notes to `<project>/notes/total.md` using `## Slide N` headings:

```markdown
## Slide 1
Opening remarks. Welcome the audience and introduce the topic.

## Slide 2
Key insight: the market opportunity is $50B by 2027.

## Slide 3
Transition to our solution approach.
```

Notes are embedded in the PPTX automatically during export.

Alternatively, write per-slide files: `<project>/notes/slide_01.md`, `slide_02.md`, …

---

## Generate Notes Draft

```bash
# Generate notes from slide content
slide-skill draft-notes <project>

# Regenerate (overwrite existing)
slide-skill draft-notes <project> --overwrite
```
