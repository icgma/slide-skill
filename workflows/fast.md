# Route: fast — 快速出片 (Deadline Mode)

**Presentable deck in ~2 seconds, no API key, no LLM.** Deterministic
rendering: the same input always produces the same deck. Quality is decided
by the input shape, so spend your one minute on the Markdown, not the tool.

## 1. Content prep rules (60 seconds, non-negotiable)

- `#` heading → one slide. `##` → section divider. `- ` → bullets.
- **≤6 bullet lines per section** — split dense sections into two slides
  rather than letting one overflow.
- Titles ≤25 characters; long titles get clipped or shrunk.
- **Bold numbers** (`**87%**`) render as metric emphasis — use for the 2-3
  numbers that must land.
- `### A / ### B` under one `##` → side-by-side comparison layout.
- Never pass raw PDF text or lecture-notes dumps straight through — 30
  seconds of restructuring beats any theme change.

## 2. Pick a theme

| Need | Theme |
|------|-------|
| 毕业答辩 / 学术汇报 | `academic-defense` (navy/white/red, 中文学术规范) |
| 学术会议 / 评审 | `academic-royal` |
| 商务 / 通用汇报 | `light-corporate` |
| 科技 / 深色投影 | `dark-tech` |
| 数据密集 | `data-forward` |
| 创业 / 路演 | `vibrant-startup`, `indigo-saas` |
| 人文 / 叙事 | `warm-editorial`, `sage-calm` |

`slide-skill themes` lists all 32 with palettes.

## 3. Generate

```bash
slide-skill quickstart <source.md> --name <name> --theme <theme> --mode fast
```

Output: `projects/<name>/exports/*.pptx` (natively editable) + `qa/QA.md`.
Read the QA report; deliver only on pass.

A thesis-defense example lives in the repo:

```bash
slide-skill quickstart examples/thesis-sample.zh.md --theme academic-defense --mode fast
```

## 4. Common adjustments

| User says | Do this |
|-----------|---------|
| "字太小了" | Fewer items per section in the source; regenerate |
| "太密了" | Split the section into two `#` slides; regenerate |
| "配色不喜欢" | Re-run with a different `--theme` (seconds) |
| "某一页要改" | Edit that file in `svg_output/`, then `finalize-svg` + `export` |
| "顺序不对" | Reorder headings in the source; regenerate |
| "需要加一页" | Add a `#` section to the source; regenerate |

Regeneration is ~2 seconds — iterate on the source freely.

## Upgrade paths

- Flexible deadline + capable agent → [free-design route](agent-authoring.md)
  (hand-designed pages, highest ceiling).
- `OPENAI_API_KEY` configured → `--mode ai` runs the built-in AI
  planner/executor instead of deterministic templates.
