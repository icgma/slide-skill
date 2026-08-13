# Examples 示例目录

本目录收录的都是**已提交、可直接打开**的真实产物：成品竞赛包、校方模板填充示例、
答辩样稿渲染图、手工精修的参考 SVG，以及流水线端到端跑出来的完整项目。
每一类都附一条复现命令。

## 目录索引

| 路径 | 内容 | 复现方式 |
|---|---|---|
| [`competitions/`](competitions/README.md) | 六大竞赛成品包（互联网+ / 挑战杯 / 数模 / 大创 / 答辩 / 课程展示）：源内容 + 演讲备注 + SVG + 可编辑 `deck.pptx` + QA 报告 | 各包 README 内附单命令复现；或 `slide-skill init <name> --competition <slug> --from-example` 从任意包起步 |
| [`school-template/`](school-template/) | 校方模板保真填充端到端示例：[模板](school-template/template.pptx) → [填充后 17 页成品](school-template/filled-example.pptx) + [FILL-REPORT](school-template/FILL-REPORT.md)（零溢出、零占位符残留） | `slide-skill template-fill examples/school-template/template.pptx --content examples/thesis-sample.zh.md -o filled.pptx` |
| [`thesis-sample.zh.md`](thesis-sample.zh.md) | 真实感 LSTM 毕业论文答辩源稿（16 页产出，数字内部自洽） | `slide-skill quickstart examples/thesis-sample.zh.md --theme academic-defense --mode fast` |
| [`thesis-sample/`](thesis-sample/) | 上述答辩稿生成成品的 4 张真实渲染页（封面 / 目录 / 指标 / 结论） | 同上命令后自行渲染，或直接查看 PNG |
| [`svg/`](svg/) | 6 张手工精修的参考 SVG（设计天花板，详见下表） | 拷入任意项目 `svg_output/` 后 `slide-skill export <project>` |
| [`auto-render/`](auto-render/) | fast 模式（零 API key）自动渲染样片：SVG、PNG 静帧与 LibreOffice 实录 MP4/GIF | `slide-skill quickstart examples/sample.md --theme dark-tech` |
| [`sample-dark-tech/`](sample-dark-tech/) · [`sample-light-corporate/`](sample-light-corporate/) | 流水线端到端真实运行产物（8 页 deck.pptx + svg_output + QA 报告），运行记录见 [`RUN-LOG.md`](RUN-LOG.md) | 见 RUN-LOG.md 内的完整命令 |
| [`sample.md`](sample.md) · [`sample.zh-CN.md`](sample.zh-CN.md) | 英文 / 中文快速上手源稿 | `slide-skill quickstart examples/sample.md --theme dark-tech` |
| [`_content/`](_content/) | 10 个领域的展示内容源（论文、商业战略、政务报告、营销、路演……），供文档站示例画廊构建脚本使用 | `python scripts/build_examples.py` |
| [`demo.md`](demo.md) · [`animation-demo.md`](animation-demo.md) · [`xhs-post.md`](xhs-post.md) | 小型演示源稿（基础功能 / 动画属性 / 小红书竖版画布） | `slide-skill quickstart examples/<file> --theme <theme>` |

## 参考 SVG 一览（`svg/`）

手工精修、逐条通过 QA 闸门的参考页，也是 LLM 执行者模式的 few-shot 目标。
GitHub 直接渲染 SVG，下表文件既是源码也是预览。

| # | 文件 | 主题 | 版式 | 展示点 |
|---|------|-------|--------|---------------|
| 01 | `svg/01-cover-dark-tech.svg` | dark-tech | cover | 线性渐变背景、径向强调光晕、4px 强调色规则线 |
| 02 | `svg/02-bullet-list-light-corporate.svg` | light-corporate | bullet-list | 5 条隔行变色要点、圆角面板、项目符号 |
| 03 | `svg/03-metric-highlight-data-forward.svg` | data-forward | metric-highlight | 3 张顶部强调条数据卡、大号数字、辅助说明 |
| 04 | `svg/04-two-column-warm-editorial.svg` | warm-editorial | two-column | 社论风并排对比、衬线字体、斜体引文 |
| 05 | `svg/05-section-divider-vibrant-startup.svg` | vibrant-startup | section-divider | 全宽渐变色带、章节标签与大标题 |
| 06 | `svg/06-closing-dark-tech.svg` | dark-tech | closing | 居中结束页、径向渐变背景、联系方式行 |

## 这些示例的用途

- **LLM 执行者的 few-shot 参考。** 执行者需要对齐某个版式或主题时，把对应
  SVG 直接放进 prompt。每个项目内生成的 `design_guide.md` 也包含同风格的完整示例。
- **回归基准。** QA 流水线（`SVGQualityChecker`）原样接受上述全部文件——它们覆盖
  渐变、`letter-spacing`、`text-anchor`、圆角面板与描边轮廓，且不触发任何禁用标签规则。
- **主题与场景橱窗。** 从参考 SVG（设计天花板）到 fast 模式自动渲染（当前地板），
  再到六大竞赛成品包，能看到同一套流水线在不同投入下的真实产出水平。
