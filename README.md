<div align="center">

# Slide Skill

### Source material in. Polished, editable PowerPoint out.

An SVG-first slide generation toolkit for AI agents and the command line.
Convert PDFs, Markdown, DOCX, or URLs into editable PPTX decks through a
clean, inspectable SVG intermediate.

[English README](README.md) · [中文 README](README.zh-CN.md)

[![version](https://img.shields.io/badge/version-5.0.0a1-3B82F6)](pyproject.toml)
[![tests](https://img.shields.io/badge/tests-900%2B%20passing-22C55E)](tests/)
[![python](https://img.shields.io/badge/python-3.11%2B-FFD43B)](pyproject.toml)
[![output](https://img.shields.io/badge/output-editable%20PPTX-D04A02)](examples/sample-dark-tech/deck.pptx)
[![license](https://img.shields.io/badge/license-MIT-lightgrey)](#license)

</div>

  ---

  <div align="center">

  ### Live preview — actual PPTX rendered through LibreOffice

  <video src="https://github.com/icgma/slide-skill/raw/master/examples/auto-render/dark-tech/preview.mp4" controls autoplay loop muted playsinline width="720" poster="examples/auto-render/dark-tech/slide_01.png">
    Your browser does not support the video tag — <a href="examples/auto-render/dark-tech/preview.mp4">download the MP4</a> or view the <a href="examples/auto-render/dark-tech/preview.gif">animated GIF</a>.
  </video>

  <sub><b>Real screen recording</b> of the generated <code>.pptx</code>: rendered via LibreOffice → PDF → 1920×1080 PNG frames → H.264 MP4 (16 s, 8 slides @ 2 s each, 348 KB). This is the actual file PowerPoint opens — no SVG approximation. Reproduce locally with <code>slide-skill quickstart examples/sample.md --theme dark-tech</code>: ~2 seconds, no API key, no LLM. Then open the <a href="examples/sample-dark-tech/deck.pptx">.pptx</a> in PowerPoint to edit every shape, text, and gradient natively.</sub>

  </div>

  ---

## 🎓 Built for students / 面向大学生

Three high-pressure student scenarios, each backed by a **finished example committed in this repo** — open the artifact first, then reproduce it with one command.

### 1 · Thesis defense on your school's mandated template

Your school hands you a fixed `.pptx` template? Keep its design untouched — one command fills your thesis Markdown into the template's native pages (duplicating content pages as needed) and reports text-overflow and leftover-placeholder risks.

Committed end-to-end example: [school template](examples/school-template/template.pptx) → [filled 17-slide deck](examples/school-template/filled-example.pptx), with a clean [FILL-REPORT](examples/school-template/FILL-REPORT.md).

```bash
slide-skill template-fill examples/school-template/template.pptx --content examples/thesis-sample.zh.md -o filled.pptx
```

### 2 · Competition roadshow decks

Six finished, QA-passed competition packs live in [`examples/competitions/`](examples/competitions/README.md) — realistic Chinese content following each competition's judging structure, spoken-register speaker notes embedded in every `deck.pptx`, and a QA report per pack.

| Competition | Theme | Slides | Deck | Reproduce |
|---|---|---|---|---|
| [互联网+ 创新创业大赛](examples/competitions/internet-plus/) | vibrant-startup | 17 | [deck.pptx](examples/competitions/internet-plus/deck.pptx) | `slide-skill quickstart examples/competitions/internet-plus/source.md --theme vibrant-startup --name comp-internet-plus --mode fast` |
| [挑战杯](examples/competitions/challenge-cup/) | data-forward | 16 | [deck.pptx](examples/competitions/challenge-cup/deck.pptx) | `slide-skill quickstart examples/competitions/challenge-cup/source.md --theme data-forward --name comp-challenge-cup --mode fast` |
| [数学建模竞赛](examples/competitions/math-modeling/) | data-forward | 14 | [deck.pptx](examples/competitions/math-modeling/deck.pptx) | `slide-skill quickstart examples/competitions/math-modeling/source.md --theme data-forward --name comp-math-modeling --mode fast` |
| [大创（大学生创新创业训练计划）](examples/competitions/innovation-training/) | indigo-saas | 13 | [deck.pptx](examples/competitions/innovation-training/deck.pptx) | `slide-skill quickstart examples/competitions/innovation-training/source.md --theme indigo-saas --name comp-innovation-training --mode fast` |
| [毕业论文答辩](examples/competitions/thesis-defense/) | academic-defense | 16 | [deck.pptx](examples/competitions/thesis-defense/deck.pptx) | `slide-skill quickstart examples/competitions/thesis-defense/source.md --theme academic-defense --name comp-thesis-defense --mode fast` |
| [课程展示](examples/competitions/course-presentation/) | light-corporate | 10 | [deck.pptx](examples/competitions/course-presentation/deck.pptx) | `slide-skill quickstart examples/competitions/course-presentation/source.md --theme light-corporate --name comp-course-presentation --mode fast` |

Start your own deck from any pack — the scaffold copies its source and speaker notes into a fresh project:

```bash
slide-skill init my-deck --competition internet-plus --from-example
```

### 3 · Deadline tonight — a 16-page defense deck in ~2 seconds

[`examples/thesis-sample.zh.md`](examples/thesis-sample.zh.md) is a realistic LSTM thesis source. One command, no API key, ~2 seconds, QA passed — these PNGs are real rendered pages of the resulting deck:

```bash
slide-skill quickstart examples/thesis-sample.zh.md --theme academic-defense --mode fast
```

<table>
<tr>
<td width="25%"><img src="examples/thesis-sample/01-cover.png" alt="Thesis cover (academic-defense)" /></td>
<td width="25%"><img src="examples/thesis-sample/02-outline.png" alt="Thesis outline" /></td>
<td width="25%"><img src="examples/thesis-sample/10-metrics.png" alt="Thesis metrics" /></td>
<td width="25%"><img src="examples/thesis-sample/13-conclusion.png" alt="Thesis conclusion" /></td>
</tr>
<tr>
<td align="center"><sub>Cover</sub></td>
<td align="center"><sub>Outline</sub></td>
<td align="center"><sub>Key metrics</sub></td>
<td align="center"><sub>Conclusion</sub></td>
</tr>
</table>

  ---

  ## What it produces

Real example slides — six layouts across five of the 32 built-in themes.
GitHub renders SVG inline, so what you see below is the actual artifact,
not a screenshot.

<table>
<tr>
<td width="50%"><img src="examples/svg/01-cover-dark-tech.svg" alt="Cover slide (dark-tech theme)" /></td>
<td width="50%"><img src="examples/svg/02-bullet-list-light-corporate.svg" alt="Bullet list slide (light-corporate theme)" /></td>
</tr>
<tr>
<td align="center"><sub><b>Cover</b> — <code>dark-tech</code></sub></td>
<td align="center"><sub><b>Bullet list</b> — <code>light-corporate</code></sub></td>
</tr>
<tr>
<td><img src="examples/svg/03-metric-highlight-data-forward.svg" alt="Metric highlight slide (data-forward theme)" /></td>
<td><img src="examples/svg/04-two-column-warm-editorial.svg" alt="Two-column slide (warm-editorial theme)" /></td>
</tr>
<tr>
<td align="center"><sub><b>Metric highlight</b> — <code>data-forward</code></sub></td>
<td align="center"><sub><b>Two-column</b> — <code>warm-editorial</code></sub></td>
</tr>
<tr>
<td><img src="examples/svg/05-section-divider-vibrant-startup.svg" alt="Section divider slide (vibrant-startup theme)" /></td>
<td><img src="examples/svg/06-closing-dark-tech.svg" alt="Closing slide (dark-tech theme)" /></td>
</tr>
<tr>
<td align="center"><sub><b>Section divider</b> — <code>vibrant-startup</code></sub></td>
<td align="center"><sub><b>Closing</b> — <code>dark-tech</code></sub></td>
</tr>
</table>

> Source SVGs and per-file breakdown live in [`examples/`](examples/). Drop them into
> any project's `svg_output/` and run `slide-skill export <project>` to get a PPTX.

---

## Why this exists

PowerPoint is the lingua franca of business and academia, but generating it
from raw text has always been painful. Most tools either spit out a binary
blob you can't inspect, or render slides as bitmaps that no one can edit.

| Common pain | Typical tools | Slide Skill |
|---|---|---|
| Hard to inspect intermediate output | Binary `.pptx` only | Hand-readable SVG you can `cat` and diff |
| LLMs produce a wall of bullets | Fixed prompt → flat list | Layout-aware: cover, metric, two-column, quote… |
| Themes all look the same | One template | 32 themes with full palette + type + layout specs |
| Visual QA is "open and look" | Manual | `check-svg`, `validate-pptx`, machine-readable `QA.md` |
| Gradients become flat colours in PPTX | Bitmap fallback | True `<a:gradFill>` rendered natively (v2.1) |
| AI authoring is one giant prompt | All-in-one | Strategist + Executor multi-role workflow |

---

## Quick start

```bash
pip install -e .

# Source → PPTX in one command
slide-skill quickstart your-notes.md --theme dark-tech

# Open exports/*.pptx in PowerPoint, Keynote, or Google Slides — fully editable.
```

Default mode is auto — with `OPENAI_API_KEY` set it uses AI-authored slides; without a key it falls back to the deterministic `fast` renderer (~2 seconds, no API key needed).

Want more control? Use the multi-step pipeline:

```bash
slide-skill init my-deck --theme light-corporate
slide-skill source-to-md content.pdf -o projects/my-deck/sources/source.md
slide-skill spec projects/my-deck --source projects/my-deck/sources/source.md
slide-skill generate-guide projects/my-deck --source projects/my-deck/sources/source.md
# ...Executor (you or an LLM) writes svg_output/slide_NN.svg guided by design_guide.md
slide-skill check-svg projects/my-deck
slide-skill finalize-svg projects/my-deck
slide-skill export projects/my-deck
```

---

## What's new in v5.0 (in progress)

The v5.0 arc hardens the AI production chain and makes the no-key path first-class. Shipped so far, each behind tests:

- **No-key default that never crashes** — `--mode auto` uses AI generation when an API key is configured and falls back to the deterministic `fast` renderer otherwise. The AI gate is non-interactive: CI pipelines and agent shells never hang on a hidden prompt.
- **Provider response gate** — truncated or malformed LLM responses are caught at the adapter (completion-status check) instead of surfacing as corrupt SVG; per-role token budgets with escalation stop silent mid-slide cutoffs.
- **Closed-world content fidelity** — bidirectional checks reject slides whose visible text is not sourced from your material: no invented numbers, no dropped bullets.
- **Namespace-safe validated repairs** — auto-repair only applies XML-validated, namespace-preserving patches; rejected repairs are traced, never silently merged.
- **Trustworthy QA geometry** — dx-aware tspan flow measurement eliminates false overlap warnings; ghost (zero-render) elements are ERROR-level; when Chrome is available, browser `getBBox` measurements arbitrate verdicts and every repair triggers a mandatory re-render check.

What landed in **v3.0** and still ships: intelligent content planning (`content_planner` picks the best layout per slide from plain markdown) plus teaching, course, and competition domain layouts with domain-aware density defaults.

What landed in **v2.1** and still ships: native PowerPoint gradients (SVG `<linearGradient>`/`<radialGradient>` exported as editable DrawingML `<a:gradFill>`) and the polished pure-Python auto-renderer (hero typography, gradient orbs, numbered bullet markers).

---

## Two ways to use it

  Slide Skill ships two execution paths. Pick based on whether you have an LLM in the loop:

  | | **Fast mode** (`--mode fast`; auto fallback without a key) | **LLM Executor mode** |
  |---|---|---|
  | Setup | `pip install -e .` — that's it | + LLM API key (OpenAI / Claude / local) |
  | Time to first PPTX | ~2 seconds | ~30–90 seconds |
  | Visual ceiling | 6 polished templates with gradients, decorative orbs, numbered bullets, hero typography | Hand-crafted per-slide SVG following `design_guide.md` |
  | Layout selection | Heuristic (cover, bullet, metric, two-column, divider, closing) | LLM picks per slide |
  | Deterministic | ✅ same input → same output | ⚠️ depends on model |
  | Best for | Drafts, internal docs, recurring reports, CI pipelines | Pitch decks, conference talks, design-critical work |
  | Edit afterwards | Yes — fully editable PPTX | Yes — fully editable PPTX |

  **Fast mode samples** (zero API key, real `quickstart` output):

  <table>
  <tr>
  <td width="50%"><img src="examples/auto-render/dark-tech/slide_01.svg" alt="Auto-rendered cover (dark-tech)" /></td>
  <td width="50%"><img src="examples/auto-render/dark-tech/slide_03.svg" alt="Auto-rendered bullet list (dark-tech)" /></td>
  </tr>
  <tr>
  <td align="center"><sub><b>Auto-rendered cover</b> — <code>dark-tech</code></sub></td>
  <td align="center"><sub><b>Auto-rendered bullet list</b> — <code>dark-tech</code></sub></td>
  </tr>
  <tr>
  <td><img src="examples/auto-render/light-corporate/slide_05.svg" alt="Auto-rendered metrics (light-corporate)" /></td>
  <td><img src="examples/auto-render/dark-tech/slide_08.svg" alt="Auto-rendered closing (dark-tech)" /></td>
  </tr>
  <tr>
  <td align="center"><sub><b>Auto-rendered metrics</b> — <code>light-corporate</code></sub></td>
  <td align="center"><sub><b>Auto-rendered closing</b> — <code>dark-tech</code></sub></td>
  </tr>
  </table>

  **Per-slide stills** (rasterised PNGs of the same PPTX, for offline viewing):

  <table>
  <tr>
  <td width="25%"><img src="examples/auto-render/dark-tech/slide_01.png" alt="Slide 1 PNG" /></td>
  <td width="25%"><img src="examples/auto-render/dark-tech/slide_03.png" alt="Slide 3 PNG" /></td>
  <td width="25%"><img src="examples/auto-render/dark-tech/slide_05.png" alt="Slide 5 PNG" /></td>
  <td width="25%"><img src="examples/auto-render/dark-tech/slide_08.png" alt="Slide 8 PNG" /></td>
  </tr>
  </table>

  > Compare with the **Pipeline output** section below (auto-mode end-to-end with QA reports),
  > and the **What it produces** showcase above (LLM-Executor reference targets).

  ---

    ## 🌏 中文 / CJK support

    Every theme except the two monospace terminal ones (`industrial-blueprint`, `retro-terminal`) ships with a CJK font fallback chain (Microsoft YaHei → PingFang SC → Noto Sans SC → Source Han Sans SC). Chinese, Japanese, Korean input renders natively in PowerPoint, Keynote, Google Slides, and (with `noto-fonts-cjk` installed) LibreOffice.

    A ready-to-run Chinese sample lives at [`examples/sample.zh-CN.md`](examples/sample.zh-CN.md):

    ```bash
    slide-skill quickstart examples/sample.zh-CN.md --theme dark-tech
    ```

    Real recording of the resulting `.pptx` (rendered through LibreOffice → PDF → MP4):

    <div align="center">

    <video src="https://github.com/icgma/slide-skill/raw/master/examples/auto-render/zh-CN/preview-zh.mp4" controls autoplay loop muted playsinline width="720" poster="examples/auto-render/zh-CN/slide_03.png">
      Your browser doesn't support inline video — <a href="examples/auto-render/zh-CN/preview-zh.mp4">download MP4</a> or view <a href="examples/auto-render/zh-CN/preview-zh.gif">animated GIF</a>.
    </video>

    <sub>9-slide Chinese deck rendered with the same dark-tech theme. Same 2-second pipeline, same zero-API-key promise.</sub>

    </div>

    <table>
    <tr>
    <td width="50%"><img src="examples/auto-render/zh-CN/slide_01.png" alt="封面 (Cover slide)" /></td>
    <td width="50%"><img src="examples/auto-render/zh-CN/slide_03.png" alt="核心数据 (Metrics slide)" /></td>
    </tr>
    </table>

    ---

    ## 🤖 Use as an AI agent skill

    `slide-skill` ships with a [`SKILL.md`](SKILL.md) at the repo root, written in the Anthropic Claude Code / Replit Agent skill format. Drop it into any agent that supports the skills convention and the agent will automatically reach for it whenever a user asks for slides, a deck, a presentation, or "做一份 PPT".

    **Claude Code** (`~/.claude/skills/`):

    ```bash
    git clone https://github.com/icgma/slide-skill.git ~/.claude/skills/slide-skill
    ```

    **Replit Agent** (`.local/skills/` in your project):

    ```bash
    git clone https://github.com/icgma/slide-skill.git .local/skills/slide-skill
    ```

    **Cursor / other agents** (project-local `.cursor/skills/`): copy [`SKILL.md`](SKILL.md) into `.cursor/skills/slide-skill/`, install the package from the repository root (`pip install -e .`), and the agent will know to call `slide-skill quickstart <input.md> --theme <theme>` for any slide-related request.

    The two supported manual install targets are `~/.claude/skills/slide-skill/` and `.cursor/skills/`. `npx skills add` (skills-marketplace) install support lands together with the public repository release — until then, use the manual targets above.

    The skill file documents:
    - When to activate (English + Chinese trigger phrases)
    - The single command that does 90% of the work
    - How to choose between the 32 themes
    - Markdown authoring conventions (headings, bullets, **bold numbers** for metrics, `### A / ### B` for comparisons)
    - The decision flow the agent should follow

    ---

  ## Pipeline output (real end-to-end run)

The slides above are hand-crafted reference targets. Below is what the
pipeline **actually produced** running `slide-skill quickstart` against the
"AI-Powered Analytics Platform" sample deck, once for each of two themes.
(The committed runs are 8 slides; [`examples/sample.md`](examples/sample.md)
has since grown to 14 sections, so rerunning today yields a longer deck with
the same look.)

| Theme | SVGs | PPTX | QA report | Visual sample |
|---|---|---|---|---|
| `dark-tech` | [svg_output/](examples/sample-dark-tech/svg_output/) | [deck.pptx](examples/sample-dark-tech/deck.pptx) | [QA.md](examples/sample-dark-tech/QA.md) · [SVG-QA.md](examples/sample-dark-tech/SVG-QA.md) | <img src="examples/sample-dark-tech/svg_output/slide_02.svg" alt="dark-tech slide 2 (Problem Statement)" width="320"/> |
| `light-corporate` | [svg_output/](examples/sample-light-corporate/svg_output/) | [deck.pptx](examples/sample-light-corporate/deck.pptx) | [QA.md](examples/sample-light-corporate/QA.md) · [SVG-QA.md](examples/sample-light-corporate/SVG-QA.md) | <img src="examples/sample-light-corporate/svg_output/slide_02.svg" alt="light-corporate slide 2 (Problem Statement)" width="320"/> |

Both runs report `status: automated-passed` — PPTX Package ✓, SVG Gate ✓,
Placeholder Scan ✓. See [`examples/RUN-LOG.md`](examples/RUN-LOG.md) for
exact commands, outputs, and a known follow-up (text overflow on
long-paragraph slides).

> The reference decks above showcase the design **ceiling**. The pipeline
> output here shows the current **floor**. Every release should narrow that gap.

---

## How it works

```
┌──────────┐    ┌────────┐    ┌──────────┐    ┌──────────┐
│ Source   │ ─→ │ Spec   │ ─→ │ SVG      │ ─→ │ PPTX     │
│ md/pdf   │    │ JSON   │    │ output/  │    │ deck     │
│ docx/url │    │        │    │ slide_NN │    │ editable │
└──────────┘    └────────┘    └──────────┘    └──────────┘
                    ▲              ▲                ▲
              Strategist      Executor          Export +
              spec +          reads guide,      QA gates:
              generate-guide  writes SVGs       check-svg
                                                validate-pptx
```

The SVG intermediate is the hero. It is a hand-readable file you can:

- Diff in code review
- Tweak in any editor (Inkscape, browser, VSCode)
- Run through automated QA before binary export
- Few-shot into LLM prompts for layout consistency
- Hand to a designer for one-off polish without round-tripping through PPTX

---

## Design themes

| Theme | Background | Accent | Best for |
|---|---|---|---|
| `dark-tech` | `#0F172A` | `#3B82F6` | Engineering, SaaS, research |
| `light-corporate` | `#FFFFFF` | `#1D4ED8` | Business, corporate |
| `warm-editorial` | `#FDF6EE` | `#EA580C` | Humanities, editorial |
| `data-forward` | `#F1F5F9` | `#0284C7` | Analytics, dashboards |
| `vibrant-startup` | `#FFFFFF` | `#7C3AED` | Startups, pitch decks |

```bash
slide-skill themes    # list all themes
slide-skill formats   # list all canvas formats
```

---

## Multi-role workflow

### Strategist role

Prepares all planning artifacts before any SVG is written.

1. Normalize source: `slide-skill source-to-md <file>`
2. Create workspace: `slide-skill init <name> --theme <theme>`
3. Write design artifacts: `slide-skill spec <project> --source <md> --theme <theme>`
4. Write AI prompt: `slide-skill generate-guide <project> --source <md>`

### Executor role

Writes SVG files guided by the planning artifacts.

1. Read `design_guide.md` — palette, typography, layout examples
2. Read `svg_generation_prompt.md` — per-slide content breakdown
3. Write `svg_output/slide_NN.svg` for each slide
4. Validate: `slide-skill check-svg <project>`

---

## SVG authoring rules

**Allowed:** `rect` `circle` `ellipse` `line` `text` `tspan` `image` `path` `polygon`
`polyline` `g` `defs` `linearGradient` `radialGradient` `stop` `filter` `feGaussianBlur`
`feOffset` `feFlood` `feComposite` `feMerge` `feMergeNode` `clipPath` `pattern` `use`

**Banned (hard error):** `script` `foreignObject` `iframe` `animate` `animateTransform`
`set` `animateMotion`

**Banned attributes:** `onclick` `onload` `on*` (any DOM event handler)

**Fully permitted in v2.0+:** `opacity` `fill-opacity` `transform` `class` `style`,
and `fill="url(#local-id)"` gradient references — now rendered natively in PPTX.

---

## Layout templates

| Template | Use when |
|---|---|
| `cover` | Deck title / first slide |
| `section-divider` | Heading with no body text |
| `bullet-list` | 3–7 bullet points |
| `two-column` | Side-by-side comparison |
| `metric-highlight` | 2–4 large numbers / percentages |
| `quote` | A single strong quote |
| `closing` | Thank-you / CTA slide |

Full SVG examples for each template are in the generated `design_guide.md`.

---

## Chrome requirements (every slide)

```xml
<!-- Left accent stripe (required) -->
<g id="chrome-stripe">
  <rect x="0" y="0" width="6" height="720" fill="{accent}" />
</g>

<!-- Footer bar (required) -->
<g id="chrome-footer">
  <rect x="0" y="688" width="1280" height="32" fill="{surface}" />
  <text x="1184" y="708" ...>NN / TT</text>
</g>
```

---

## Speaker notes

Write notes to `<project>/notes/total.md`:

```markdown
## Slide 1
Opening remarks.

## Slide 2
Key insight: market opportunity is $50B.
```

Notes are embedded in the PPTX automatically during export.

---

## Student competition toolkit

```bash
slide-skill competitions                    # list templates
slide-skill init <name> --competition internet-plus --from-example
slide-skill rehearse <project>              # timing analysis
slide-skill draft-notes <project>           # generate notes draft
```

Templates: `internet-plus` · `challenge-cup` · `math-modeling` ·
`innovation-training` · `thesis-defense` · `course-presentation`

Every template ships a **finished example pack** under
[`examples/competitions/`](examples/competitions/README.md) — source, speaker
notes, SVGs, editable `deck.pptx`, and QA report. `--from-example` scaffolds
your project from the pack so you start by editing real content, not a blank
outline. The full pack table is in the **Built for students** section above.

### 校方模板保真填充 / Fill your school's template

School template mandated for your defense? Keep its design untouched — one command
fills your thesis Markdown into the template's native pages (duplicating/removing
content pages as needed) and reports text-overflow and leftover-placeholder risks.
End-to-end example: [`examples/school-template/`](examples/school-template/).

```bash
slide-skill template-fill school.pptx --content thesis.md -o filled.pptx
```

---

## TTS narration

```bash
# Edge TTS (default — free, offline-friendly)
slide-skill narrate <project> --engine edge-tts --voice zh-CN-XiaoxiaoNeural

# MiMo voice cloning
slide-skill narrate <project> --engine mimo --voice-clone sample.mp3

# MiMo voice design
slide-skill narrate <project> --engine mimo --voice-design "gentle female voice"
```

---

## Development

```bash
# Run the test suite (900+ tests)
pytest tests/ -q

# Lint / type-check helpers (if configured)
python -m slide_skill.cli --help
```

The agent skill documentation lives in two places:

- **`SKILL.md`** (repository root) — the canonical, self-contained skill
  entry point for AI agents. This is what the Claude Code / Replit /
  Cursor install steps load.
- `skills/slide/SKILL.md` — a redirect shim kept only so pre-existing
  deep links and package manifests resolve; it points back to the root.

Detailed runtime prompt templates (SVG standards, executor briefs, image
layouts, palettes, renderings) are bundled inside the Python package at
`tools/slide/src/slide_skill/references/` and are injected by the CLI as
needed — they are not meant to be read directly by agents.

---

## License

MIT — see [`LICENSE`](LICENSE).
