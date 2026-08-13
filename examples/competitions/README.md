# 竞赛示例包（Competition Packs）

六大学生竞赛场景各有一个**完整的成品示例包**：真实感中文内容 + 演讲备注 + 生成的 SVG 页面 + 可编辑 PPTX + QA 报告。每个包都严格按照 `slide-skill competitions` 中该竞赛的章节结构撰写，数字内部自洽，可直接下载 `deck.pptx` 查看效果，也可一条命令复现。

## 六个包一览

| 竞赛 | 目录 | 主题 | 页数 | 时限 | 复现命令 |
|---|---|---|---|---|---|
| 互联网+创新创业大赛 | [`internet-plus/`](./internet-plus/) | vibrant-startup | 17 | 8 min | `slide-skill quickstart examples/competitions/internet-plus/source.md --theme vibrant-startup --name comp-internet-plus --mode fast` |
| 挑战杯课外学术科技作品竞赛 | [`challenge-cup/`](./challenge-cup/) | data-forward | 16 | 8 min | `slide-skill quickstart examples/competitions/challenge-cup/source.md --theme data-forward --name comp-challenge-cup --mode fast` |
| 数学建模竞赛 | [`math-modeling/`](./math-modeling/) | data-forward | 14 | 10 min | `slide-skill quickstart examples/competitions/math-modeling/source.md --theme data-forward --name comp-math-modeling --mode fast` |
| 大学生创新创业训练计划（大创） | [`innovation-training/`](./innovation-training/) | indigo-saas | 13 | 5 min | `slide-skill quickstart examples/competitions/innovation-training/source.md --theme indigo-saas --name comp-innovation-training --mode fast` |
| 毕业论文答辩 | [`thesis-defense/`](./thesis-defense/) | academic-defense | 16 | 15 min | `slide-skill quickstart examples/competitions/thesis-defense/source.md --theme academic-defense --name comp-thesis-defense --mode fast` |
| 课程展示 | [`course-presentation/`](./course-presentation/) | light-corporate | 10 | 10 min | `slide-skill quickstart examples/competitions/course-presentation/source.md --theme light-corporate --name comp-course-presentation --mode fast` |

页数均落在对应竞赛的推荐页数范围内（`slide-skill competitions` 可查看每个竞赛的页数区间与章节蓝图）。全部使用 fast 模式生成——无需任何 API key，约 2 秒出片。

## 每个包里有什么

```
<slug>/
├── source.md        # 源内容（真实感中文，按竞赛章节结构撰写）
├── notes/total.md   # 全篇口语化演讲备注（## Slide N 分节，导出时自动嵌入 PPTX 备注页）
├── svg_output/      # 生成的每页 SVG（可直接在 GitHub 预览）
├── deck.pptx        # 最终可编辑 PPTX（含演讲备注）
└── qa/QA.md         # QA 报告（automated-passed，零 error）
```

想从某个包起步做自己的比赛 PPT：

```bash
slide-skill init 我的项目 --competition internet-plus --from-example
# 编辑 sources/source.md 换成你的内容，然后：
slide-skill quickstart sources/source.md --theme vibrant-startup --name 我的项目 --mode fast
```

## 评审提示（来自 slide-skill competitions）

**互联网+创新创业大赛** — 评委平均看每页 10-15 秒，文字不超过 30 字/页。数据用图表展示，避免大段文字。技术页放架构图，不要堆代码。准备 Q&A：竞品差异化、盈利模式可行性、团队能力是必问方向。

**挑战杯** — 学术严谨性是第一评分维度，数据必须有来源。创新点要用"与 XX 相比，本方案在 YY 上提升了 ZZ%"的量化表述。评委多为教授，技术细节要经得起追问。文献综述用对比表格，不要逐条罗列。

**数学建模竞赛** — 评委关注建模思路的合理性，不是结果精度。每个模型要讲清"为什么选这个模型"而非只写公式。灵敏度分析是加分项，体现对模型局限性的认知。图表要有标题、坐标轴标签和单位。

**大创** — 大创评审注重可行性和规范性，不要画大饼。进度安排要具体到月，体现可执行性。经费预算要合理，与实验内容对应。创新点要落在"可验证"上，而非口号式表述。

**毕业论文答辩** — 答辩时间有限，重点放在"你做了什么、发现了什么"。背景和文献不要超过总时长的 1/4。准备好"你的创新点是什么"和"为什么选这个方法"两个必答题。结果页用图表说话，避免读表。

**课程展示** — 课程展示重在逻辑清晰和表达生动。每页一个核心观点，配合图示或案例。结尾留一个思考题，引发课堂讨论。控制时间，留 2-3 分钟给 Q&A。

## 内容说明

- 所有项目、数据、人名均为虚构示例，数字经过内部一致性校对（如单位经济模型可复算、实验指标提升幅度与基线对得上），仅用于展示各竞赛的内容组织方式。
- `thesis-defense/source.md` 与 `examples/thesis-sample.zh.md` 保持同源（后者为唯一事实源，本包是它在竞赛包体系中的副本）。
- 本目录取代了早期的 `examples/competition-internet-plus.md` 草稿。
