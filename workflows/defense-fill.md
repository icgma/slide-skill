# Route: defense-fill — 校方模板填充 (School-Template Fidelity Fill)

**The template IS the deliverable requirement.** The school/organization `.pptx`
(logo, nav bar, colors, page furniture) must survive untouched — redesigning it
is a failure mode, not an improvement. This route copies native template pages
and replaces content only.

## Needs assessment (before any command)

1. **Template path** — "请把学校模板 .pptx 发给我" (get the actual file path).
2. **Thesis/content source** — Markdown preferred. PDF/DOCX first:
   `slide-skill source-to-md <file> -o thesis.md`.
3. **Deadline + required sections** — 开题/中期/答辩 have different section
   expectations; confirm which one this is.

## Fill

```bash
slide-skill template-fill <template.pptx> --content <thesis.md> -o filled.pptx
```

The command maps thesis sections onto template pages, replaces text inside the
native shapes, and writes `FILL-REPORT.md` next to the output.

## Read FILL-REPORT.md — then fix by editing CONTENT, not the template

The report has three verdict areas:

| Finding | Meaning | Fix |
|---------|---------|-----|
| **Overflow** (page N) | Filled text exceeds the frame bounds | Shorten that section in `thesis.md` — tighter phrasing, fewer bullets |
| **Stale placeholder** (page N) | Template sample text / "XXX大学" / TODO survived | Add the missing section to `thesis.md` so the placeholder gets replaced, or supply a `--map` override |
| **Unfilled page** | No thesis section matched | Rename the thesis heading to match the template page's topic |

Then re-fill (same command, overwrite output) and re-read the report. Iterate
until the report is clean. Never edit the template file itself.

Per-slide manual overrides when heading matching is not enough:

```bash
slide-skill template-fill <template.pptx> --content <thesis.md> -o filled.pptx --map overrides.json
# overrides.json: {"3": {"在此输入标题": "基于深度学习的目标检测研究"}}
```

## Worked example (committed in this repo)

`examples/school-template/` contains the full walk-through: `template.pptx`
(script-reproducible school-style template), the filled 17-slide
`filled-example.pptx`, and its clean `FILL-REPORT.md`. Reproduce it:

```bash
slide-skill template-fill examples/school-template/template.pptx \
  --content examples/thesis-sample.zh.md -o filled.pptx
```

## Deliver

1. `slide-skill validate-pptx filled.pptx` — package must validate.
2. Confirm FILL-REPORT.md shows no overflow / no stale placeholders.
3. Hand the user `filled.pptx` + point out anything the report still flags.

## Useful inspection commands

```bash
slide-skill template-inspect <template.pptx>   # page/placeholder inventory
slide-skill pptx-text filled.pptx              # extracted text for spot-checks
```
