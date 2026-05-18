# Slide Skill Usage

## End-to-End

```powershell
python -m pip install -e .
slide-skill quickstart examples/demo.md --name demo-deck
```

Open the generated deck in `projects/demo-deck/exports/`.

Quickstart writes automated QA with `status: automated-passed` when structural checks pass but visual review or fix-cycle evidence has not been provided. Use `slide-skill qa <project> --strict` for completion gating.

## Development Checks

```powershell
python -m unittest discover -s tests -v
slide-skill quickstart examples/demo.md --name smoke-demo
slide-skill render-doctor
```

## Speaker Notes

Add notes before export:

```markdown
## Slide 1
Opening speaker cue.

## Slide 2
Detail speaker cue.
```

Store that as `projects/<deck>/notes/total.md`, or create per-slide files like `notes/slide_01.md`. Export embeds notes into the PPTX and also writes a Markdown sidecar. Use `slide-skill pptx-notes <deck.pptx>` to inspect embedded notes.

## Known v1 Limits

- Complex SVG paths are not converted to editable custom geometries yet.
- The SVG gate rejects unsupported SVG constructs, opacity attributes, and transforms instead of allowing silent export loss or fidelity drift.
- PDF intake requires optional `PyMuPDF`.
- Visual rendering through LibreOffice/Poppler is documented but not bundled.
- Use `slide-skill render <deck.pptx> -o <out-dir>` after installing LibreOffice and Poppler.
- Strict QA requires rendered images, `qa/VISUAL-REVIEW.md`, and `qa/FIX-VERIFY.md`.
- Speaker notes are embedded for common PowerPoint notes workflows and also preserved as sidecar Markdown.
