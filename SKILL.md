---
name: slide-skill
description: Convert any source material into a polished, fully-editable PowerPoint (.pptx). Use whenever the user asks for slides, a deck, a presentation, or "做一份 PPT". IMPORTANT — this skill requires a multi-step interactive workflow. You MUST assess the user's needs BEFORE generating anything.
---

# slide-skill — AI Agent Skill (v3.0)

An SVG-first pipeline that turns prose into `.pptx` whose every shape, text run,
and gradient is natively editable. 20 built-in themes, full CJK support, domain-
specific generators for teaching, courses, and competitions.

## ⚠️ CRITICAL: Never Generate Without Understanding

**The #1 failure mode is running `quickstart` blindly on raw input.** The tool is
deterministic — garbage in, garbage out. YOUR job as the agent is to:

1. Understand what the user actually needs
2. Prepare the right input
3. Choose the right settings
4. Show a preview and iterate

If you skip steps 1-2, the output WILL be unusable. This has been proven repeatedly.

---

## When to Activate

**English**: "make slides", "build a deck", "create a presentation", "turn this into PPT"
**Chinese**: "做一份 PPT", "生成幻灯片", "演示文稿", "汇报材料", "教学课件", "答辩 PPT", "比赛 PPT"

---

## Step 1: Needs Assessment (MANDATORY)

Before touching any tool command, ask the user these questions. Adapt your phrasing
naturally — don't read this list robotically. Skip questions whose answers are obvious
from context.

### 1a. Scenario Identification

| Scenario | Trigger phrases | Key constraints |
|----------|----------------|-----------------|
| **教学课件** (Teaching) | "课件", "教学", "给学生讲", "上课用" | Low density, clear hierarchy, may need pinyin/bilingual |
| **学生课程汇报** (Course presentation) | "课程汇报", "作业展示", "课堂展示" | Academic structure, 8-12 slides, 10 min |
| **学生比赛** (Competition) | "互联网+", "挑战杯", "数学建模", "大创", "答辩", "比赛" | Strict page/time limits, competition-specific structure |
| **通用** (General) | Everything else | Flexible |

**Ask**: "这份 PPT 是用于什么场景？教学课件、课程汇报、比赛答辩，还是其他用途？"

### 1b. Audience

**Ask**: "受众是谁？" Examples:
- Teaching: "国际学生？本科生？研究生？什么水平？" (For language teaching: "HSK 几级？")
- Competition: "评委是教授还是企业导师？"
- Course: "老师和同学？"

### 1c. Content Density

**Ask based on scenario**:
- Teaching: "每页最多放几个知识点/词汇？" (Default: 3-4 for vocab, 1 for grammar)
- Competition: "预计演讲几分钟？页数限制？"
- Course: "大概需要多少页？"

### 1d. Language & Visual

**Ask if relevant**:
- "需要中英双语吗？需要拼音标注吗？"
- "有偏好的视觉风格吗？"（然后推荐合适的 theme）

### 1e. Source Material

**Assess the input quality**:
- Is it a well-structured markdown? → Can use directly
- Is it a PDF of slides/screenshots? → Needs OCR/vision extraction first
- Is it raw notes? → Needs restructuring
- Is it a topic with no material? → Need to draft content together

---

## Step 2: Content Preparation (Agent's Responsibility)

**This is YOUR job, not the tool's.** The tool's markdown parser is basic — it splits
on `#` headings. YOU must prepare clean, well-structured markdown.

### For Teaching Slides (教学课件)

Structure the markdown so each `#` heading maps to ONE teaching unit:

```markdown
# 第一课：看病 (Seeing the Doctor)

## 生词 (Vocabulary)
- 医院 (yīyuàn) — hospital
- 感冒 (gǎnmào) — cold/flu
- 发烧 (fāshāo) — fever
- 头疼 (tóuténg) — headache

## 例句 (Example Sentences)
- 我感冒了，要去医院。
  Wǒ gǎnmào le, yào qù yīyuàn.
  I have a cold and need to go to the hospital.

## 对话 (Dialogue)
A: 你怎么了？(What's wrong?)
B: 我头疼，还发烧。(I have a headache and a fever.)
```

**CRITICAL for teaching**: If the user provides dense material (e.g., 20 vocab items),
YOU must split it into multiple sections of 3-4 items each BEFORE passing to the tool.
The tool will NOT do intelligent splitting for you.

### For Competition Slides (比赛)

Use the built-in competition templates:

```bash
slide-skill competitions                    # list available templates
slide-skill init my-deck --competition internet-plus  # scaffold with structure
```

Then fill in content following the competition's section structure.

### For Course Presentations (课程汇报)

Structure as: Introduction → 2-4 Body Sections → Conclusion

```markdown
# 主题名称

## 研究背景
- Key point 1
- Key point 2

## 核心内容
### 要点一
...

## 结论与思考
...
```

---

## Step 3: Theme Selection

Pick based on scenario. **Always confirm with the user.**

### Recommended by Scenario

| Scenario | Recommended themes | Why |
|----------|-------------------|-----|
| Teaching (language) | `vibrant-startup`, `sage-calm` | Bright, friendly, low fatigue |
| Teaching (STEM) | `data-forward`, `light-corporate` | Clean, data-friendly |
| Teaching (humanities) | `warm-editorial`, `terracotta-warm` | Warm, readable |
| Competition (互联网+/大创) | `vibrant-startup`, `indigo-saas` | Energy, modern |
| Competition (挑战杯/学术) | `academic-royal`, `data-forward` | Scholarly, rigorous |
| Competition (答辩) | `academic-royal`, `midnight-executive` | Formal, authoritative |
| Course presentation | `light-corporate`, `dark-tech` | Professional, clean |

```bash
slide-skill themes    # list all 20 themes with previews
```

---

## Step 4: Generate

```bash
# The one command — but ONLY after steps 1-3 are done
slide-skill quickstart <prepared-input.md> --theme <theme-name>
```

Output structure:
```
projects/<name>/
├── sources/          ← copy of input
├── svg_output/       ← one SVG per slide (inspectable!)
├── svg_final/        ← finalized SVGs
├── exports/
│   └── <name>_<timestamp>.pptx    ← the deliverable
└── qa/
    └── QA.md         ← quality report
```

### For Multi-Step Control

```bash
slide-skill init <name> --theme <theme>
slide-skill spec <project> --source <md> --theme <theme>
slide-skill svg <project> --source <md>
slide-skill check-svg <project>
slide-skill finalize-svg <project>
slide-skill export <project>
```

---

## Step 5: Preview & Iterate (MANDATORY)

After generation, you MUST:

1. **Check the QA report**: Read `qa/QA.md` — is status "passed"?
2. **Inspect the SVG output**: Read 2-3 SVG files to verify content and layout
3. **Generate HTML preview** (if available):
   ```bash
   slide-skill html-preview <project>
   ```
4. **Report to the user**: Show them what was generated, ask for feedback
5. **Iterate if needed**: Re-prepare markdown, adjust theme, regenerate

### Common Adjustments

| User says | What to do |
|-----------|-----------|
| "字太小了" | Reduce content per slide, restructure markdown |
| "太密了" | Split sections into more slides with fewer items |
| "配色不喜欢" | `slide-skill quickstart <md> --theme <different-theme>` |
| "某一页需要改" | Edit the SVG in `svg_output/`, re-run `finalize-svg` + `export` |
| "顺序不对" | Restructure the source markdown, regenerate |
| "需要加一页" | Add a `#` section to the markdown, regenerate |

---

## Decision Flow

```
User asks for slides
        │
        ▼
Step 1: NEEDS ASSESSMENT ← You MUST do this
        │
   ┌────┴───────────────────┐
   │ Identify scenario:     │
   │ Teaching / Course /    │
   │ Competition / General  │
   └────┬───────────────────┘
        │
        ▼
Step 2: PREPARE CONTENT ← You MUST do this
        │
   ┌────┴───────────────────┐
   │ - Clean up input       │
   │ - Split dense sections │
   │ - Structure properly   │
   └────┬───────────────────┘
        │
        ▼
Step 3: CHOOSE THEME ← Recommend + confirm
        │
        ▼
Step 4: GENERATE
        │
        ▼
Step 5: PREVIEW & ITERATE ← Show user, get feedback
        │
   ┌────┴────┐
   Approved   Needs changes
   │          │
   ▼          └──→ Go back to Step 2 or 4
   Done — deliver .pptx path
```

---

## Other Useful Commands

| Command | What it does |
|---------|-------------|
| `slide-skill themes` | List all 20 themes |
| `slide-skill formats` | Canvas sizes (16:9, 4:3, A4, etc.) |
| `slide-skill competitions` | List competition templates |
| `slide-skill rehearse <project>` | Estimate speaking time per slide |
| `slide-skill draft-notes <project>` | Auto-generate speaker notes |
| `slide-skill narrate <project>` | TTS audio from notes |
| `slide-skill html-preview <project>` | Self-contained HTML presenter |
| `slide-skill font-preflight <project>` | Check for missing CJK glyphs |
| `slide-skill validate-pptx <file>` | Validate PPTX structure |

---

## Common Pitfalls

1. **PDF is images, not text** → Extract with vision AI first, then prepare markdown
2. **Dense content = ugly slides** → YOU must split content before generating
3. **Long titles get clipped** → Keep titles under 25 characters
4. **Chinese boxes in LibreOffice** → `noto-fonts-cjk` system package needed
5. **"一键生成" mentality** → This tool needs intelligent input preparation. 
   The agent IS the intelligence layer.

---

## Setup

```bash
git clone https://github.com/Yuuqq/slide-skill.git
cd slide-skill
pip install -e .
pip install pymupdf  # optional: PDF input support

slide-skill --help   # verify
slide-skill themes   # see available themes
```

---

**Bottom line**: You are NOT a command proxy. You are a presentation consultant who
happens to have a powerful rendering engine. Understand first, prepare carefully,
generate, preview, iterate. The tool renders; YOU design.
