<!-- GSD:docs-update -->

# Slide Skill 架构

> 版本 v3.0 | 47 个源模块 + 38 个测试文件 = 460 测试通过

## 设计哲学

AI 能写 SVG，但写不了 DrawingML（PowerPoint 的 XML）。Slide Skill 在中间搭桥——每个 SVG 元素映射成可编辑的 PowerPoint 原生对象。这就是 **SVG-first pipeline**：AI 负责创作，Slide Skill 负责无损转换。

核心原则：

- **SVG 是作者层**——AI 生成/调试 SVG 远比直接写 DrawingML 可靠
- **原生可编辑是输出契约**——每个形状、文字框、曲线都是 PowerPoint 原生对象
- **注册表驱动扩展**——新增 SVG 元素类型只需注册转换器，不改核心代码
- **QA 必须有视觉证据**——不做"文件存在就算通过"的空壳检查

---

## 六层架构

```
┌─────────────────────────────────────────────────────────────┐
│  1. Intake Layer — 源文件归一化                              │
│     PDF/DOCX/XLSX/PPTX/HTML/URL → Markdown                  │
├─────────────────────────────────────────────────────────────┤
│  2. SVG Pipeline — 设计到图形的全流程                         │
│     Design Spec → SVG Gen → SVG QA → SVG Finalize           │
├─────────────────────────────────────────────────────────────┤
│  3. Export Layer — SVG 到原生 PPTX                           │
│     ConverterRegistry (9 种元素) + geometry + animations     │
│     + gradients + clip-path + pattern + filter effects       │
│     + narrate (edge-tts / MiMo TTS)                         │
├─────────────────────────────────────────────────────────────┤
│  4. Student Toolkit — 竞赛/演讲辅助                          │
│     竞赛模板 + 计时排练 + 智能备注草稿                         │
├─────────────────────────────────────────────────────────────┤
│  5. QA Layer — 质量保证                                      │
│     快照对比 (SSIM) + 结构检查 + 视觉验证 + 自动修复           │
├─────────────────────────────────────────────────────────────┤
│  6. CLI — 统一入口                                          │
│     20+ 子命令调度所有模块                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 模块详解

所有源码位于 `tools/slide/src/slide_skill/`。

### 1. Intake Layer — 源文件归一化

| 模块 | 行数 | 职责 |
|------|------|------|
| `intake.py` | 210 | PDF/DOCX/XLSX/PPTX/HTML/URL → Markdown 转换 |
| `project.py` | 116 | 项目工作区：init / load / validate / import-sources |

**设计要点：** 输入无论什么格式，统一归一为 Markdown。后续所有流程只消费 Markdown，不关心来源。

### 2. SVG Pipeline — 设计到图形

| 模块 | 行数 | 职责 |
|------|------|------|
| `svg_pipeline.py` | 1,039 | 设计规格生成、SVG 页面生成、SVG QA 质量门控、SVG 定稿、spec_lock |

**流程阶段：**

1. **Design Spec** — 从 Markdown 内容 + 画布格式 + 模板生成设计规格（配色、布局、字号）
2. **Spec Lock** — 冻结设计参数到 `spec_lock.json`，后续阶段只读
3. **SVG Gen** — 按锁定的规格逐页生成 SVG 文件
4. **SVG QA** — 质量门控：检查 viewBox、文字溢出、元素合法性，不通过则阻断
5. **SVG Finalize** — 定稿：将 `svg_output/` 移极内容复制到 `svg_final/`，标记不可变

**关键约束：** `spec_lock` 一旦写入，整个下游管线只读不写。防止 AI 反复"改进"设计导致规格漂移。

### 3. Export Layer — SVG 到原生 PPTX

| 模块 | 行数 | 职责 |
|------|------|------|
| `converters.py` | 330 | SVG 元素 → PPTX 形状转换器注册表（9 种元素类型） |
| `geometry.py` | 323 | SVG path `d` 属性解析（20 种命令）+ DrawingML 自由形状构建 |
| `exporter.py` | 289 | SVG→PPTX 导出主流程：遍历 SVG 文件、构建 Presentation、嵌入动画/备注/音频 |
| `animations.py` | 205 | OOXML 动画/转场 XML 构建（5 种转场 + 5 种入场动画） |
| `narrate.py` | 200 | TTS 旁白：edge-tts（异步）+ MiMo TTS 双引擎 |
| `mimo_tts.py` | 132 | MiMo TTS 后端：8 预置音色、声音克隆、音色设计 |
| `templates.py` | 597 | 80 套视觉模板注册表（10 类别 × 8 模板） + 自定义 JSON 模板加载 |
| `template_ops.py` | 299 | 模板操作：inspect / replace / delete / reorder / duplicate |
| `gradient_fills.py` | ~120 | SVG linearGradient/radialGradient → 独立渐变收集/解析 |
| `clip_path.py` | ~150 | SVG clipPath/mask → DrawingML 自定义几何裁剪 |
| `pattern_fill.py` | ~100 | SVG pattern → DrawingML blipFill 平铺填充 |
| `filter_effects.py` | 178 | SVG feGaussianBlur/feDropShadow → DrawingML effectLst (blur + outerShdw) |
| `animations_v2.py` | ~200 | v2 动画系统：效果目录 + ElementAnimation 数据类 + timing 注入 |
| `formats.py` | 39 | 11 种画布预设（ppt169 / xhs / a4 / banner 等） |
| `util.py` | 48 | 通用工具函数 |

#### ConverterRegistry — 核心扩展机制

```
SVG 元素                    PPTX 原生对象
─────────                   ────────────
<rect>         ──→          Rectangle
<circle>       ──→          Oval
<ellipse>      ──→          Oval
<line>         ──→          Connector
<text>         ──→          TextFrame
<image>        ──→          Picture
<path>         ──→          Freeform (贝塞尔)
<polygon>      ──→          Freeform (闭合)
<polyline>     ──→          Freeform (开放)
```

每个转换器实现 `PathConverter` 接口：

```python
class PathConverter:
    def accepts(self, tag: str, elem: ET.Element) -> bool: ...
    def convert(self, slide, elem, scale_x, scale_y) -> None: ...
```

新增元素类型只需 `registry.register(MyConverter())`，不改 `exporter.py` 核心逻辑。

#### geometry.py — SVG path 到 DrawingML

20 种 SVG path 命令的完整解析链：

```
SVG <path d="M 10 20 C 30 40 50 60 70 80 A 90 100 ...">
    ↓ svgpathtools.parse_path()
Segment 列表 [MoveTo, CubicBezier, Arc, ...]
    ↓ 弧线 → 三次贝塞尔近似
Segment 列表 [MoveTo, CubicBezier, CubicBezier, ...]
    ↓ 坐标缩放（SVG → PPTX 像素）
DrawingML <a:path> XML
    ↓ 注入 <p:sp> 自由形状
PowerPoint 原生可编辑自由形状
```

### 4. Student Toolkit — 竞赛/演讲辅助

| 模块 | 行数 | 职责 |
|------|------|------|
| `competition.py` | 194 | 6 套竞赛模板定义 + Markdown 大纲生成 |
| `rehearse.py` | 190 | 计时排练：从备注估算时长、超时预警 |
| `draft_notes.py` | 154 | 自动从幻灯片内容生成演讲备注草稿 |

**竞赛模板覆盖：** 互联网+、挑战杯、数学建模、大创、毕设答辩、课程展示。每套模板定义时限、页数范围、章节结构和评审提示。

### 5. QA Layer — 质量保证

| 模块 | 行数 | 职责 |
|------|------|------|
| `qa.py` | 143 | PPTX 有效性、原生形状、占位符、结构/视觉/修复验证 |
| `snapshot_diff.py` | 119 | 像素快照对比：SSIM 相似度 + 报告 |
| `render.py` | 127 | LibreOffice+Poppler 渲染 + 环境诊断 |

**验证维度：**

- **结构检查** — 文件结构完整性、SVG 质量、原生形状存在性
- **视觉验证** — 渲染后像素级对比（SSIM 相似度打分，可配置阈值）
- **修复验证** — 自动修复后确认问题已消除

### 6. CLI — 统一入口

| 模块 | 行数 | 职责 |
|------|------|------|
| `cli.py` | 327 | 20+ 子命令入口，调度所有模块 |

子命令分组：基本流程（init/svg/export/qa）、快捷操作（quickstart）、旁白（narrate/voices）、竞赛工具包（competitions/rehearse/draft-notes）、模板操作、检查验证。

---

## 数据流

```
源文件 (PDF/DOCX/XLSX/PPTX/HTML/URL)
    ↓ intake.py
Markdown
    ↓ project.py
项目工作区 (sources/)
    ↓ svg_pipeline.py (design_spec + spec_lock)
设计规格 (spec_lock.json)
    ↓ svg_pipeline.py (svg gen)
SVG 输出 (svg_output/)
    ↓ svg_pipeline.py (svg qa)
质量门控 ──── 不通过 → 阻断，返回修复建议
    ↓ svg_pipeline.py (svg finalize)
SVG 定稿 (svg_final/)
    ↓ exporter.py → converters.py + geometry.py
    ↓ animations.py + narrate.py
PPTX 文件 (exports/)
    ↓ qa.py + render.py + snapshot_diff.py
QA 报告 ──── 通过 → 完成
              不通过 → 修复建议
```

---

## 关键设计模式

### Spec Lock — 设计参数冻结

`spec_lock.json` 一旦生成，全管线只读。防止 AI 在后续步骤"顺手改进"导致配色/字号/布局漂移。需要修改设计时，从 design spec 阶段重新开始。

### ConverterRegistry — 开闭原则

转换器注册表实现开闭原则：对扩展开放（注册新 `PathConverter`），对修改关闭（不改 `exporter.py` 的核心遍历逻辑）。

### 双引擎 TTS — 策略模式

`narrate.py` 通过策略模式支持 edge-tts（默认，90+ 语音）和 MiMo TTS（声音克隆/音色设计）。运行时通过 `--engine` 参数切换，不改动调用方代码。

### QA 门控 — 阻断而非警告

SVG QA 和 PPTX QA 都是门控：不通过时阻断下游流程并返回结构化修复建议，而非仅打印警告继续执行。确保输出质量有证据支撑。

---

## 依赖

### 核心（必须）

| 依赖 | 用途 |
|------|------|
| `python-pptx` | PPTX 组装和导出 |
| `Pillow` | 图片处理、缩略图、SSIM 对比 |
| `svgpathtools` | SVG path `d` 属性解析 |

### 可选（按功能）

| 依赖 | 用途 | 安装 |
|------|------|------|
| `PyMuPDF` | PDF 转文本提取 | `pip install slide-skill[intake]` |
| `mammoth` | DOCX → Markdown | `pip install slide-skill[intake]` |
| `openpyxl` | XLSX → Markdown | `pip install slide-skill[intake]` |
| `beautifulsoup4` | HTML → Markdown | `pip install slide-skill[intake]` |
| `requests` | URL 抓取 | `pip install slide-skill[intake]` |
| `edge-tts` | 语音旁白（默认引擎） | `pip install slide-skill[audio]` |
| `openai` | MiMo TTS 语音旁白 | `pip install slide-skill[mimo]` |

### 系统（渲染 QA）

| 依赖 | 用途 |
|------|------|
| LibreOffice | PPTX → PDF 转换 |
| Poppler (`pdftoppm`) | PDF → PNG 渲染 |

---

## 反模式

1. **不做通用 SVG 渲染器** — 只转换 DrawingML 能表达的子集。SVG 支持但 PowerPoint 不支持的特性直接拒绝。
2. **不改 python-pptx 内部** — 通过 `_element` 访问构造自定义 XML，但不 monkey-patch。
3. **不做空壳 QA** — "文件存在"不等于"质量通过"。必须有视觉证据（渲染截图）或结构证据（原生形状数 > 0）。
4. **不做单体生成脚本** — 拆分为可测试的小模块，而非一个 2000 行的 `generate.py`。
5. **不内嵌上游专有代码** — 独立实现，参考设计思路但不复制源码。
