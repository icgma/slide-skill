# Route: competition — 比赛路演 (Competition Roadshow)

**The competition's structure is the contract.** 互联网+ / 挑战杯 / 数模 / 大创 /
答辩 / 课程展示 each have a known section budget, page range, time limit, and
judge expectations — all encoded in the built-in competition specs. Start from
the finished example pack, replace its content with the user's project, keep
the structure.

## 1. Pick the competition

```bash
slide-skill competitions       # slugs, time limits, page ranges, pack themes
```

| Slug | 比赛 | 时限 | 页数 | 示例包主题 |
|------|------|------|------|-----------|
| `internet-plus` | 互联网+创新创业大赛 | 8min | 15-20 | vibrant-startup |
| `challenge-cup` | 挑战杯课外学术科技作品竞赛 | 8min | 15-18 | data-forward |
| `math-modeling` | 数学建模竞赛 | 10min | 12-18 | data-forward |
| `innovation-training` | 大创（创新创业训练计划） | 5min | 10-15 | indigo-saas |
| `thesis-defense` | 毕业论文答辩 | 15min | 15-25 | academic-defense |
| `course-presentation` | 课程展示 | 10min | 8-12 | light-corporate |

If the user's competition is not listed, choose the closest structure (e.g.
省级创业赛 → `internet-plus`) and say so.

## 2. Scaffold from the example pack

```bash
slide-skill init <name> --competition <slug> --from-example
```

This copies the pack's `source.md` (a complete, well-shaped deck source) and
speaker notes into `projects/<name>/sources/` + `notes/`, and prints the pack's
section structure and theme. The committed reference pack lives at
`examples/competitions/<slug>/` (source, notes, SVGs, deck.pptx, QA report).

## 3. Replace content, keep structure

Edit `projects/<name>/sources/source.md`: swap the example's project for the
user's, section by section. Rules:

- Keep the section skeleton — judges score against the expected flow
  (痛点→方案→市场→壁垒→团队→财务→规划 for 互联网+, etc.). The scaffold output
  and `slide-skill competitions` show each competition's budget and judge tips.
- Respect the page budget per section; the time limit is hard.
- Numbers and claims come from the user's material only — never invent
  market sizes, user counts, or results.
- Metrics the judges must see get their own line with **bold numbers**
  (renders as metric emphasis).

## 4. Generate with the pack's theme

```bash
slide-skill quickstart projects/<name>/sources/source.md \
  --name <name> --theme <pack-theme> --mode fast
```

(`--mode fast` = deterministic, seconds, no key. For a hand-designed deck with
a flexible deadline, switch to the [free-design route](agent-authoring.md)
using the same prepared source.)

## 5. Rehearse against the clock

```bash
slide-skill draft-notes projects/<name>     # speaker-note drafts per slide
slide-skill rehearse projects/<name> --time-limit <minutes>
```

`rehearse` estimates speaking time per slide from the notes. Over the limit →
cut content in `source.md` (not talking speed) and regenerate.

## 6. Deliver

1. Read `projects/<name>/qa/QA.md` — must be passed.
2. Hand over `projects/<name>/exports/*.pptx` + the notes file.
3. Tell the user the rehearsal estimate vs the competition time limit.
