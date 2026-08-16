---
name: slide-skill
description: Convert any source material into a polished, fully-editable PowerPoint (.pptx). Use whenever the user asks for slides, a deck, a presentation, or "做一份 PPT". IMPORTANT — this is a ROUTED skill. Assess the user's scenario first, then follow exactly ONE workflow doc — defense-fill (校方模板), competition (比赛路演), course (课程汇报), fast (deadline 快速出片), or free-design (host agent hand-writes SVG).
---

# slide-skill — AI Agent Skill (v5.1.0)

An SVG-first pipeline that turns prose into `.pptx` whose every shape, text run,
and gradient is natively editable. 32 built-in themes, full CJK support, school
template fill, competition packs, and automated QA gates. This entry file owns
**scenario routing only** — each route's procedure lives in its own workflow doc.

---

## Global Execution Discipline (applies to every route)

1. **Assess before generating.** Understand the scenario, audience, time budget,
   and source quality BEFORE touching any command. Never run a generator blindly
   on raw input — garbage in, garbage out has been proven repeatedly.
2. **Serial steps.** Execute pipeline stages in order. Never skip a QA gate,
   never run stages speculatively out of order.
3. **Closed world.** Slide text comes ONLY from the user's source material or an
   agreed plan. Never invent facts, numbers, or claims absent from the source.
4. **QA gates are mandatory.** A deck is done when the QA report passes — not
   when an export command exits 0.
5. **Match the user's language.** Chinese request → Chinese deck and replies.

---

## Routing Table

Resolve the user's request to EXACTLY ONE route. Open that route's workflow doc
and follow it end to end. When two routes seem to match, ask one clarifying
question instead of guessing.

| Route | Triggers (中 / EN) | Workflow doc | Output contract |
|-------|--------------------|--------------|-----------------|
| **defense-fill** | "学校模板 / 答辩模板 / 开题 / 中期 / 按模板填" + user HAS a `.pptx` template | [workflows/defense-fill.md](workflows/defense-fill.md) | Template pages untouched, content filled in, FILL-REPORT clean |
| **competition** | "互联网+ / 挑战杯 / 数模 / 数学建模 / 大创 / 比赛路演 / roadshow pitch" | [workflows/competition.md](workflows/competition.md) | Deck follows the competition's section budget + judge tips, with speaker notes and timing |
| **course** | "课程汇报 / 作业展示 / 教学课件 / 上课用 / course presentation / teaching slides" | [workflows/course.md](workflows/course.md) | Academic-clean deck matching classroom density rules |
| **fast** | "今晚就要 / deadline / 快点 / 越快越好 / no API key available" | [workflows/fast.md](workflows/fast.md) | Presentable deck in seconds via the deterministic renderer |
| **free-design** | "自由设计 / 高质量定制 / 精心设计 / design it yourself / make it beautiful" | [workflows/agent-authoring.md](workflows/agent-authoring.md) | Host agent hand-writes every SVG page under per-page discipline; highest visual ceiling |

**RECOMMENDED route:** when the driving model is capable and time permits,
prefer **free-design** ([workflows/agent-authoring.md](workflows/agent-authoring.md)).
You — the host agent — author every page yourself. That is what this toolkit
is built for: the harness handles conversion and QA; the model designs.

---

## Fallback: no capable host agent

If the driving model cannot hand-author SVG (or the user wants zero involvement):

- **Built-in AI executor** — `slide-skill quickstart <md> --mode ai` with
  `OPENAI_API_KEY` + `OPENAI_BASE_URL` configured. The toolkit's own
  planner/executor/visual-critic chain generates the deck.
- **Fast mode** — `slide-skill quickstart <md> --mode fast`. Deterministic,
  no key, seconds. See [workflows/fast.md](workflows/fast.md).

---

## Scenario Identification Cheat Sheet

Ask when unclear: "这份 PPT 用于什么场景？有学校模板吗？什么时候要？"

- User has a mandated school `.pptx` → **defense-fill** (redesigning it is a failure mode)
- Named competition (互联网+/挑战杯/数模/大创) → **competition**
- Classroom / homework / teaching → **course**
- Urgent, or no API key and no capable agent → **fast**
- "Make it beautiful", flexible timeline, capable model → **free-design**

---

## Setup

```bash
git clone https://github.com/icgma/slide-skill.git
cd slide-skill
pip install -e .

slide-skill --help    # verify
slide-skill themes    # list all 32 themes
```

---

**Bottom line**: You are NOT a command proxy. You are a presentation consultant
with a rendering harness. Route first, follow the workflow doc exactly, let the
QA gates arbitrate. The tool converts and verifies; YOU design.
