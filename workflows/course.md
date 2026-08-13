# Route: course — 课程汇报 / 教学课件 (Course & Teaching Decks)

**Content preparation is the whole game.** The renderer is deterministic:
well-shaped Markdown in, clean deck out. Your job is shaping the material
before any command runs.

## 1. Needs assessment

Ask (skip what's obvious from context):

- **场景**: 课程汇报（学生向老师同学讲）还是教学课件（老师向学生讲）？
- **受众**: 本科生/研究生/国际学生？语言课需要拼音或双语吗？
- **时长与页数**: 10 分钟汇报 ≈ 8-12 页；一节课的课件按教学单元数定。
- **材料**: 已有讲义/论文/笔记，还是从主题开始起草？

## 2. Prepare the Markdown (your responsibility, not the tool's)

The parser splits on headings: `#` → new slide, `##` → section, `- ` → bullet.

**课程汇报** — academic arc, one idea per slide:

```markdown
# 汇报主题

## 研究背景
- 为什么这个问题重要
- 现有方法的不足

## 核心内容
### 方法 / 要点一
- ...

## 结论与思考
- 主要结论
- 局限与下一步
```

**教学课件** — one teaching unit per `#` heading, low density:

- Vocabulary: 3-4 items per section, `词 (pīnyīn) — meaning` per line.
- Grammar: ONE pattern per slide with 2-3 example sentences.
- Dense source material (e.g. 20 vocab items) → YOU split it into multiple
  sections of 3-4 BEFORE generating. The tool will not split intelligently.
- Bilingual/pinyin needs → write both languages into the source lines.

Density ceiling for both: ≤6 bullet lines per section, ≤25-char titles.
`### A / ### B` sub-headings under one `##` render as a comparison layout.

## 3. Choose a theme (recommend, then confirm)

| 场景 | Themes | Why |
|------|--------|-----|
| 语言教学 | `vibrant-startup`, `sage-calm` | Bright, friendly, low fatigue |
| 理工科教学 | `data-forward`, `light-corporate` | Clean, data-friendly |
| 人文教学 | `warm-editorial`, `terracotta-warm` | Warm, readable |
| 课程汇报 | `light-corporate`, `dark-tech` | Professional, neutral |
| 学术风格偏好 | `academic-defense`, `academic-royal` | Formal, scholarly |

`slide-skill themes` lists all 32.

## 4. Generate

```bash
slide-skill quickstart <prepared.md> --name <name> --theme <theme> --mode fast
```

## 5. Iterate

1. Read `projects/<name>/qa/QA.md` — must be passed.
2. Open 2-3 files in `svg_output/` to sanity-check density and hierarchy.
3. Show the user; adjust by editing the SOURCE (split sections, shorten
   titles, reorder headings) and re-running — not by patching SVGs.
4. Optional: `slide-skill html-preview projects/<name>` for a browser
   walkthrough; `slide-skill draft-notes projects/<name>` for speaker notes.

Deliverable: `projects/<name>/exports/*.pptx` — fully editable in PowerPoint.
