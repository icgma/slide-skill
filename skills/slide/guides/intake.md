# Guide: Intake & Project Workspace (v2.0)

---

## Source Conversion

Convert raw source files to clean Markdown before designing:

```bash
# PDF, DOCX, TXT, HTML → Markdown
slide-skill source-to-md <source.pdf> -o <project>/sources/source.md

# Web URL → Markdown
slide-skill source-to-md https://example.com/article --url -o sources/article.md
```

Supported input formats: PDF, DOCX, TXT, Markdown, HTML, URLs.

---

## Project Initialization

```bash
# Basic project
slide-skill init my-deck --format ppt169

# With a design theme
slide-skill init my-deck --format ppt169 --theme light-corporate

# Competition project
slide-skill init my-deck --competition internet-plus
```

### Format Presets

| Format | Size | Ratio | Use Case |
|--------|------|-------|----------|
| `ppt169` | 1280×720px | 16:9 | Standard presentation |
| `ppt43` | 960×720px | 4:3 | Legacy format |
| `a4` | 794×1123px | A4 | Report/document |
| `square` | 720×720px | 1:1 | Social media |

Run `slide-skill formats` for the full list.

### Available Themes

| Theme | Direction |
|-------|-----------|
| `dark-tech` | Dark engineering deck with blue accent |
| `light-corporate` | Clean white/navy corporate style |
| `warm-editorial` | Cream/orange editorial feel |
| `data-forward` | Light gray analytics deck |
| `vibrant-startup` | White/purple startup pitch |

Run `slide-skill themes` for full details.

---

## Project Structure

```
<project>/
├── project.json          # Workspace metadata
├── sources/              # Source materials (PDF, DOCX, MD, ...)
├── design_spec.md        # Visual direction (written by Strategist)
├── spec_lock.json        # Machine-readable palette, font, layout
├── design_guide.md       # AI Executor SVG authoring guide
├── svg_generation_prompt.md  # Per-slide content prompt (optional)
├── svg_output/           # SVG pages (Executor writes here)
├── svg_final/            # Finalized SVG (after QA)
├── notes/
│   ├── total.md          # Speaker notes (## Slide N sections)
│   └── slide_NN.md       # Per-slide override notes
├── exports/              # PPTX output files
├── backup/               # SVG and PPTX backups
└── qa/
    ├── SVG-QA.md
    ├── VISUAL-REVIEW.md
    └── FIX-VERIFY.md
```

---

## Importing Source Files

```bash
slide-skill import-sources <project> file1.pdf file2.docx
slide-skill import-sources <project> docs/*.md --move
```

---

## Validating a Project

```bash
slide-skill validate <project>
```

Checks that `project.json` is well-formed and required directories exist.

---

## Creating the Design Spec (Strategist step)

```bash
slide-skill spec <project> --source <project>/sources/source.md --theme dark-tech
```

This single command writes:
- `design_spec.md` — human-readable visual direction
- `spec_lock.json` — palette, font, layout rhythm (read by Executor)
- `design_guide.md` — full AI-facing SVG authoring guide

The Executor **must** read `design_guide.md` before writing any SVG file.
