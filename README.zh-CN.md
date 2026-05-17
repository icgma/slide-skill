<div align="center">

# Slide Skill

### 输入素材，输出可编辑的精美 PowerPoint。

一个面向 AI agent 与命令行的 SVG 优先（SVG-first）幻灯片生成工具。
把 PDF、Markdown、DOCX、URL 一键转成可编辑的 PPTX，中间产物是可读、可 diff 的 SVG。

[English README](README.md) · 中文 README

[![version](https://img.shields.io/badge/version-2.2.0-3B82F6)](pyproject.toml)
[![tests](https://img.shields.io/badge/tests-343%20passing-22C55E)](tests/)
[![python](https://img.shields.io/badge/python-3.11%2B-FFD43B)](pyproject.toml)
[![output](https://img.shields.io/badge/output-editable%20PPTX-D04A02)](examples/sample-dark-tech/deck.pptx)
[![license](https://img.shields.io/badge/license-MIT-lightgrey)](#许可)

</div>

  ---

  <div align="center">

  ### 实拍预览 —— 真实 PPTX 经 LibreOffice 渲染录制

  <video src="https://github.com/Yuuqq/slide-skill/raw/master/examples/auto-render/dark-tech/preview.mp4" controls autoplay loop muted playsinline width="720" poster="examples/auto-render/dark-tech/slide_01.png">
    你的浏览器不支持视频标签 —— <a href="examples/auto-render/dark-tech/preview.mp4">下载 MP4</a> 或查看 <a href="examples/auto-render/dark-tech/preview.gif">动图 GIF</a>。
  </video>

  <sub>这是生成的 <code>.pptx</code> 的 <b>真实屏幕录制</b>：经 LibreOffice → PDF → 1920×1080 PNG 帧 → H.264 MP4（16 秒，8 页幻灯片，每页 2 秒，348 KB）。这就是 PowerPoint 打开时看到的真实文件，没有任何 SVG 近似还原。本地一行命令复现：<code>slide-skill quickstart examples/sample.md --theme dark-tech</code> —— 约 2 秒，无需 API key，无需 LLM。然后在 PowerPoint 里打开 <a href="examples/sample-dark-tech/deck.pptx">.pptx</a>，每一个图形、文字、渐变都可以原生编辑。</sub>

  </div>

  ---

  ## 实际产出

下面是真实的示例幻灯片 —— 五种主题、六种版式。GitHub 直接渲染 SVG，
所以你看到的就是真正的产物，不是截图。

<table>
<tr>
<td width="50%"><img src="examples/svg/01-cover-dark-tech.svg" alt="封面（dark-tech 主题）" /></td>
<td width="50%"><img src="examples/svg/02-bullet-list-light-corporate.svg" alt="项目列表（light-corporate 主题）" /></td>
</tr>
<tr>
<td align="center"><sub><b>封面</b> — <code>dark-tech</code></sub></td>
<td align="center"><sub><b>项目列表</b> — <code>light-corporate</code></sub></td>
</tr>
<tr>
<td><img src="examples/svg/03-metric-highlight-data-forward.svg" alt="数据高亮（data-forward 主题）" /></td>
<td><img src="examples/svg/04-two-column-warm-editorial.svg" alt="双栏对比（warm-editorial 主题）" /></td>
</tr>
<tr>
<td align="center"><sub><b>数据高亮</b> — <code>data-forward</code></sub></td>
<td align="center"><sub><b>双栏对比</b> — <code>warm-editorial</code></sub></td>
</tr>
<tr>
<td><img src="examples/svg/05-section-divider-vibrant-startup.svg" alt="章节分隔（vibrant-startup 主题）" /></td>
<td><img src="examples/svg/06-closing-dark-tech.svg" alt="结束页（dark-tech 主题）" /></td>
</tr>
<tr>
<td align="center"><sub><b>章节分隔</b> — <code>vibrant-startup</code></sub></td>
<td align="center"><sub><b>结束页</b> — <code>dark-tech</code></sub></td>
</tr>
</table>

> 源 SVG 与逐文件说明都在 [`examples/`](examples/) 目录。把它们丢进任何项目的
> `svg_output/`，运行 `slide-skill export <project>` 就能得到 PPTX。

---

## 为什么做这个工具

PowerPoint 是商业与学术的通用语言，但从纯文本生成 PPT 一直是件麻烦事。
现有方案要么吐出无法检查的二进制文件，要么把每页渲染成图片让人没法编辑。

| 常见痛点 | 通常工具 | Slide Skill |
|---|---|---|
| 中间产物难以检查 | 只有二进制 `.pptx` | 人类可读的 SVG，能 `cat` 能 diff |
| LLM 直接产出一堵子弹墙 | 一个固定 prompt → 平铺列表 | 版式感知：封面、数据高亮、双栏、引言…… |
| 所有主题长得一样 | 一套模板 | 5 套主题，每套都有完整的色板 + 字体 + 版式规范 |
| 视觉 QA 全靠"打开看一眼" | 人工 | `check-svg`、`validate-pptx`、机器可读的 `QA.md` |
| 渐变在 PPTX 里变成纯色 | 位图回退 | 真正的 `<a:gradFill>` 原生渲染（v2.1） |
| AI 创作只有一个大 prompt | 全在一个 prompt 里 | 策略师 + 执行者多角色协作 |

---

## 快速上手

```bash
pip install -e .

# 一行命令：素材 → PPTX
slide-skill quickstart your-notes.md --theme dark-tech

# 在 PowerPoint、Keynote 或 Google Slides 里打开 exports/*.pptx —— 完全可编辑。
```

想要更细粒度的控制？用多步骤流水线：

```bash
slide-skill init my-deck --theme light-corporate
slide-skill source-to-md content.pdf -o projects/my-deck/sources/source.md
slide-skill spec projects/my-deck --source projects/my-deck/sources/source.md
slide-skill generate-guide projects/my-deck --source projects/my-deck/sources/source.md
# ……执行者（你或 LLM）按 design_guide.md 的指引写 svg_output/slide_NN.svg
slide-skill check-svg projects/my-deck
slide-skill finalize-svg projects/my-deck
slide-skill export projects/my-deck
```

---

## v2.1 新特性

- 🎨 **PowerPoint 原生渐变** —— SVG 里的 `<linearGradient>` 和 `<radialGradient>`
  现在会被翻译成真正的 DrawingML `<a:gradFill>`（多色标 + 正确的角度计算），
  而不是退化成中间色。在 PowerPoint 里打开 `.pptx`，渐变完全可以继续编辑。

- 🎯 **更精致的自动渲染** —— 纯 Python 模板现在能产出大字号标题、渐变光晕、
  带编号的列表标记和强调线条。默认的 `quickstart` 流程**不用任何 LLM** 就能直接拿出手。

**v2.0** 中已经稳定的能力（依然全部保留）：

- **5 套设计主题** —— `dark-tech` · `light-corporate` · `warm-editorial` · `data-forward` · `vibrant-startup`
- **多角色工作流** —— 策略师做规划，执行者写 SVG
- **每个项目独立的设计指南** —— `design_guide.md` 由 spec 锁定生成，附完整 SVG 示例
- **宽松的 SVG QA** —— 渐变、透明度、滤镜、变换、class、style 全部允许；只禁止脚本、动画、DOM 事件
- **AI SVG 创作 prompt** —— `slide-skill generate-guide` 为执行者角色生成完整简报
- **343 个测试全部通过** —— 包含两套主题的端到端流水线测试

---

## 两种使用方式

  Slide Skill 提供两条执行路径，按照你是否有 LLM 在回路里来选：

  | | **自动模式**（默认 `quickstart`） | **LLM 执行者模式** |
  |---|---|---|
  | 配置 | `pip install -e .` —— 这就够了 | + LLM API key（OpenAI / Claude / 本地） |
  | 出第一份 PPTX 的耗时 | 约 2 秒 | 约 30–90 秒 |
  | 视觉上限 | 6 套精修模板：渐变、装饰光晕、编号项目符号、大字号标题 | 按 `design_guide.md` 手工逐页精修的 SVG |
  | 版式选择 | 启发式（封面、列表、数据、双栏、分隔、结尾） | LLM 逐页决定 |
  | 是否确定性 | ✅ 同输入 → 同输出 | ⚠️ 取决于模型 |
  | 适合场景 | 草稿、内部文档、周期性报告、CI 流水线 | 路演、大会演讲、设计要求高的场合 |
  | 后续可编辑 | 是 —— 完全可编辑的 PPTX | 是 —— 完全可编辑的 PPTX |

  **自动模式样片**（零 API key，真实 `quickstart` 输出）：

  <table>
  <tr>
  <td width="50%"><img src="examples/auto-render/dark-tech/slide_01.svg" alt="自动渲染封面（dark-tech）" /></td>
  <td width="50%"><img src="examples/auto-render/dark-tech/slide_03.svg" alt="自动渲染列表（dark-tech）" /></td>
  </tr>
  <tr>
  <td align="center"><sub><b>自动渲染封面</b> — <code>dark-tech</code></sub></td>
  <td align="center"><sub><b>自动渲染列表</b> — <code>dark-tech</code></sub></td>
  </tr>
  <tr>
  <td><img src="examples/auto-render/light-corporate/slide_05.svg" alt="自动渲染数据（light-corporate）" /></td>
  <td><img src="examples/auto-render/dark-tech/slide_08.svg" alt="自动渲染结尾（dark-tech）" /></td>
  </tr>
  <tr>
  <td align="center"><sub><b>自动渲染数据</b> — <code>light-corporate</code></sub></td>
  <td align="center"><sub><b>自动渲染结尾</b> — <code>dark-tech</code></sub></td>
  </tr>
  </table>

  **逐页静态图**（同一份 PPTX 栅格化的 PNG，便于离线查看）：

  <table>
  <tr>
  <td width="25%"><img src="examples/auto-render/dark-tech/slide_01.png" alt="第 1 页 PNG" /></td>
  <td width="25%"><img src="examples/auto-render/dark-tech/slide_03.png" alt="第 3 页 PNG" /></td>
  <td width="25%"><img src="examples/auto-render/dark-tech/slide_05.png" alt="第 5 页 PNG" /></td>
  <td width="25%"><img src="examples/auto-render/dark-tech/slide_08.png" alt="第 8 页 PNG" /></td>
  </tr>
  </table>

  > 与下方"**流水线产出**"章节对比（自动模式端到端 + QA 报告），
  > 也可与上方"**实际产出**"展示对比（LLM 执行者模式的目标参考）。

  ---

  ## 🌏 中文 / CJK 支持

  五套主题现在都内置了中日韩字体回落链（Microsoft YaHei → PingFang SC → Noto Sans SC → Source Han Sans SC）。中文、日文、韩文输入在 PowerPoint、Keynote、Google Slides 中原生显示；LibreOffice 端只要装了 `noto-fonts-cjk` 也能完美渲染。

  开箱即用的中文样例在 [`examples/sample.zh-CN.md`](examples/sample.zh-CN.md)：

  ```bash
  slide-skill quickstart examples/sample.zh-CN.md --theme dark-tech
  ```

  生成的 `.pptx` 真实录屏（LibreOffice → PDF → MP4）：

  <div align="center">

  <video src="https://github.com/Yuuqq/slide-skill/raw/master/examples/auto-render/zh-CN/preview-zh.mp4" controls autoplay loop muted playsinline width="720" poster="examples/auto-render/zh-CN/slide_03.png">
    浏览器不支持内嵌视频 —— <a href="examples/auto-render/zh-CN/preview-zh.mp4">下载 MP4</a> 或查看 <a href="examples/auto-render/zh-CN/preview-zh.gif">动图 GIF</a>。
  </video>

  <sub>9 页中文 PPT，使用同一套 dark-tech 主题。还是 2 秒流水线，还是零 API key。</sub>

  </div>

  <table>
  <tr>
  <td width="50%"><img src="examples/auto-render/zh-CN/slide_01.png" alt="封面" /></td>
  <td width="50%"><img src="examples/auto-render/zh-CN/slide_03.png" alt="核心数据页" /></td>
  </tr>
  </table>

  ---

  ## 🤖 作为 AI agent skill 使用

  `slide-skill` 在仓库根目录提供了 [`SKILL.md`](SKILL.md)，按照 Anthropic Claude Code / Replit Agent 的 skill 规范编写。把它放到任何支持 skills 约定的 agent 里，每当用户提到"做幻灯片"、"做一份 PPT"、"slides"、"presentation"，agent 就会自动调用它。

  **Claude Code**（`~/.claude/skills/`）：

  ```bash
  git clone https://github.com/Yuuqq/slide-skill.git ~/.claude/skills/slide-skill
  ```

  **Replit Agent**（项目内 `.local/skills/`）：

  ```bash
  git clone https://github.com/Yuuqq/slide-skill.git .local/skills/slide-skill
  ```

  **Cursor / 其他 agent**：把 [`SKILL.md`](SKILL.md) 复制到 rules/skills 目录，安装本包（`pip install -e .`），agent 就会知道遇到任何幻灯片相关请求都该调用 `slide-skill quickstart <input.md> --theme <theme>`。

  Skill 文件里写明：
  - 何时激活（中英文触发词）
  - 那条搞定 90% 工作的命令
  - 5 套主题如何选择
  - Markdown 写作约定（标题层级、项目符号、用 **粗体数字** 表示数据指标、`### A / ### B` 表示对比）
  - Agent 应当遵循的决策流程

  ---

  ## 流水线产出（真实端到端运行）

上面那些幻灯片是手工精修的参考标杆。下面是流水线**实际跑出来**的成果 ——
对 [`examples/sample.md`](examples/sample.md)（一份 8 页"AI 驱动的分析平台"演示稿）
分别用两套主题运行 `slide-skill quickstart`：

| 主题 | SVG | PPTX | QA 报告 | 视觉样例 |
|---|---|---|---|---|
| `dark-tech` | [svg_output/](examples/sample-dark-tech/svg_output/) | [deck.pptx](examples/sample-dark-tech/deck.pptx) | [QA.md](examples/sample-dark-tech/QA.md) · [SVG-QA.md](examples/sample-dark-tech/SVG-QA.md) | <img src="examples/sample-dark-tech/svg_output/slide_02.svg" alt="dark-tech 第 2 页（Problem Statement）" width="320"/> |
| `light-corporate` | [svg_output/](examples/sample-light-corporate/svg_output/) | [deck.pptx](examples/sample-light-corporate/deck.pptx) | [QA.md](examples/sample-light-corporate/QA.md) · [SVG-QA.md](examples/sample-light-corporate/SVG-QA.md) | <img src="examples/sample-light-corporate/svg_output/slide_02.svg" alt="light-corporate 第 2 页（Problem Statement）" width="320"/> |

两次运行都报告 `status: automated-passed` —— PPTX 包结构 ✓、SVG 闸门 ✓、占位符扫描 ✓。
完整命令、输出与一个已知待办（长段落幻灯文字溢出）见 [`examples/RUN-LOG.md`](examples/RUN-LOG.md)。

> 上面的参考样片展示了设计**天花板**，下面的流水线产出展示当前的**地板**。每次发版都要把这两条线再缩小一点。

---

## 工作原理

```
┌──────────┐    ┌────────┐    ┌──────────┐    ┌──────────┐
│  素材    │ ─→ │ 规格    │ ─→ │ SVG     │ ─→ │ PPTX     │
│ md/pdf   │    │ JSON   │    │ output/ │    │ 幻灯片    │
│ docx/url │    │        │    │ slide_NN│    │ 可编辑   │
└──────────┘    └────────┘    └──────────┘    └──────────┘
                    ▲              ▲                ▲
                  策略师        执行者          导出 +
                  spec +       读指南、         QA 闸门:
              generate-guide   写 SVG          check-svg
                                              validate-pptx
```

中间产物 SVG 是整个工具的灵魂。它是一个人类可读的文件，你可以：

- 在 code review 里 diff
- 在任何编辑器里改（Inkscape、浏览器、VSCode）
- 在二进制导出之前跑自动 QA
- 作为 few-shot 样例喂给 LLM 以保持版式一致
- 直接交给设计师做一次性精修，不必绕回 PPTX

---

## 设计主题

| 主题 | 背景色 | 强调色 | 适用场景 |
|---|---|---|---|
| `dark-tech` | `#0F172A` | `#3B82F6` | 工程、SaaS、研究 |
| `light-corporate` | `#FFFFFF` | `#1D4ED8` | 商务、企业 |
| `warm-editorial` | `#FDF6EE` | `#EA580C` | 人文、社论 |
| `data-forward` | `#F1F5F9` | `#0284C7` | 分析、看板 |
| `vibrant-startup` | `#FFFFFF` | `#7C3AED` | 创业、路演 |

```bash
slide-skill themes    # 列出全部主题
slide-skill formats   # 列出全部画布尺寸
```

---

## 多角色工作流

### 策略师角色

在写任何 SVG 之前先准备好全部规划产物。

1. 归一化素材：`slide-skill source-to-md <file>`
2. 创建工作区：`slide-skill init <name> --theme <theme>`
3. 写设计产物：`slide-skill spec <project> --source <md> --theme <theme>`
4. 写 AI prompt：`slide-skill generate-guide <project> --source <md>`

### 执行者角色

在规划产物的引导下逐页写 SVG。

1. 读 `design_guide.md` —— 色板、字体、版式示例
2. 读 `svg_generation_prompt.md` —— 每页内容拆解
3. 为每一页写 `svg_output/slide_NN.svg`
4. 验证：`slide-skill check-svg <project>`

---

## SVG 创作规则

**允许使用：** `rect` `circle` `ellipse` `line` `text` `tspan` `image` `path` `polygon`
`polyline` `g` `defs` `linearGradient` `radialGradient` `stop` `filter` `feGaussianBlur`
`feOffset` `feFlood` `feComposite` `feMerge` `feMergeNode` `clipPath` `pattern` `use`

**禁止（硬错误）：** `script` `foreignObject` `iframe` `animate` `animateTransform`
`set` `animateMotion`

**禁止属性：** `onclick` `onload` `on*`（任何 DOM 事件回调）

**v2.0 起完全允许：** `opacity` `fill-opacity` `transform` `class` `style`，
以及 `fill="url(#local-id)"` 渐变引用 —— 现在会原生导出到 PPTX。

---

## 版式模板

| 模板 | 适用场景 |
|---|---|
| `cover` | 封面 / 第一页 |
| `section-divider` | 章节标题，无正文 |
| `bullet-list` | 3–7 条要点 |
| `two-column` | 并排对比 |
| `metric-highlight` | 2–4 个大号数字 / 百分比 |
| `quote` | 单条强观点引用 |
| `closing` | 致谢 / 行动号召 |

每个模板的完整 SVG 示例都在生成的 `design_guide.md` 里。

---

## 标准框架（每页必备）

```xml
<!-- 左侧强调色条（必需） -->
<g id="chrome-stripe">
  <rect x="0" y="0" width="6" height="720" fill="{accent}" />
</g>

<!-- 页脚条（必需） -->
<g id="chrome-footer">
  <rect x="0" y="688" width="1280" height="32" fill="{surface}" />
  <text x="1184" y="708" ...>NN / TT</text>
</g>
```

---

## 演讲备注

把备注写到 `<project>/notes/total.md`：

```markdown
## Slide 1
开场白。

## Slide 2
关键洞察：市场规模 500 亿美元。
```

导出 PPTX 时备注会自动嵌入到对应页。

---

## 学生竞赛工具包

```bash
slide-skill competitions                    # 列出所有竞赛模板
slide-skill init <name> --competition internet-plus
slide-skill rehearse <project>              # 时长分析
slide-skill draft-notes <project>           # 自动起草演讲备注
```

内置模板：`internet-plus`（互联网+） · `challenge-cup`（挑战杯） · `math-modeling`（数模） ·
`innovation-training`（大创） · `thesis-defense`（论文答辩） · `course-presentation`（课堂展示）

---

## 语音合成（TTS 旁白）

```bash
# Edge TTS（默认 —— 免费、可离线）
slide-skill narrate <project> --engine edge-tts --voice zh-CN-XiaoxiaoNeural

# MiMo 声音克隆
slide-skill narrate <project> --engine mimo --voice-clone sample.mp3

# MiMo 声音设计
slide-skill narrate <project> --engine mimo --voice-design "温柔的女声"
```

---

## 开发

```bash
# 跑测试套件（343 个测试）
pytest tests/ -v

# Lint / 类型检查辅助命令（如已配置）
python -m slide_skill.cli --help
```

`skills/slide/` 目录是 agent skill 的文档：

- `SKILL.md` —— AI agent 的主入口
- `guides/intake.md` —— 素材转换与项目初始化
- `guides/svg-pipeline.md` —— 设计指南、SVG 规则、最终化
- `guides/export.md` —— PPTX 导出与校验
- `guides/editing.md` —— 模板操作
- `guides/qa.md` —— QA 循环与产物期望

---

## 许可

MIT —— 见 [`LICENSE`](LICENSE)，或默认按 MIT 处理。
