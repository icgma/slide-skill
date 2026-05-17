<!-- GSD:docs-update -->

# Slide Skill 配置参考

> 所有配置均通过 CLI 参数、项目配置文件或环境变量传入，无全局配置文件。

---

## 1. pyproject.toml — 包配置

| 字段 | 值 |
|------|-----|
| name | `slide-skill` |
| version | `0.1.0` |
| requires-python | `>=3.10` |
| entry point | `slide-skill = slide_skill.cli:main` |
| package-dir | `{"" = "tools/slide/src"}` |

### 核心依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| python-pptx | >=0.6.21 | PPTX 组装与导出 |
| Pillow | >=9.0.0 | 图片处理、缩略图、SSIM 对比 |
| svgpathtools | >=1.6 | SVG path `d` 属性解析 |

### 可选依赖组

```bash
pip install slide-skill[intake]   # 源文件归一化
pip install slide-skill[audio]    # edge-tts 语音旁白
pip install slide-skill[mimo]     # MiMo TTS 语音旁白
```

| 组 | 包 | 用途 |
|----|-----|------|
| `[intake]` | PyMuPDF>=1.23.0 | PDF 转文本 |
| | mammoth>=1.6.0 | DOCX → Markdown |
| | openpyxl>=3.1.0 | XLSX → Markdown |
| | beautifulsoup4>=4.12.0 | HTML → Markdown |
| | requests>=2.31.0 | URL 抓取 |
| `[audio]` | edge-tts>=6.1.0 | 语音旁白（默认引擎） |
| `[mimo]` | openai>=1.0.0 | MiMo TTS 语音旁白 |

---

## 2. project.json — 项目工作区配置

由 `slide-skill init` 创建，位于项目根目录。

```json
{
  "name": "my-deck",
  "format": "ppt169",
  "template": "midnight",
  "slide_count": 12,
  "sources": ["report.pdf", "data.xlsx"],
  "created_at": "2025-01-15T10:30:00"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 项目名称 |
| `format` | str | 画布预设（见第 6 节） |
| `template` | str | 视觉主题（见第 7 节） |
| `slide_count` | int | 预期幻灯片页数 |
| `sources` | list[str] | 源文件路径列表 |
| `created_at` | str | ISO 8601 创建时间戳 |

---

## 3. spec_lock.json — 设计规格锁定文件

由 SVG Pipeline 的 design spec 阶段生成，**写入后全管线只读**。需要修改设计时，须从 design spec 阶段重新开始。

```json
{
  "palette": {
    "background": "#0F172A",
    "surface": "#FFFFFF",
    "text": "#FFFFFF",
    "body": "#334155",
    "accent": "#2563EB",
    "footer_bg": "#1E293B",
    "chrome_muted": "#64748B",
    "decor_light": "#15243F",
    "decor_medium": "#1A2D4D",
    "decor_line": "#1E3A5F",
    "hero_start": "#1A2744"
  },
  "fonts": {
    "family": "Aptos, Arial, sans-serif"
  },
  "layout": {
    "card_radius": 16,
    "title_decoration": "underline"
  },
  "slides": {
    "01": {"layout": "title", "accent_index": 0},
    "02": {"layout": "content", "accent_index": 1}
  }
}
```

| 顶层键 | 说明 |
|--------|------|
| `palette` | 配色方案，11 个色值键 |
| `fonts` | 字体族设置 |
| `layout` | 全局布局参数（圆角、标题装饰等） |
| `slides` | 每页幻灯片的布局分配和配色索引 |

---

## 4. 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `MIMO_API_KEY` | 仅 MiMo TTS | MiMo 语音服务的 API 密钥，用于声音克隆和音色设计 |

核心功能（SVG 生成、PPTX 导出、QA）无需任何环境变量。

---

## 5. CLI 选项

所有配置通过命令行标志传入，无配置文件优先级层叠。

### 画布与模板

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--format` | 画布预设（见第 6 节） | `ppt169` |
| `--template` | 视觉主题（见第 7 节） | `midnight` |

### 语音旁白

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--engine` | TTS 引擎：`edge-tts` 或 `mimo` | `edge-tts` |
| `--voice` | 语音 ID | 引擎默认 |
| `--voice-clone` | MiMo 声音克隆参考音频路径 | — |
| `--voice-design` | MiMo 音色设计提示文本 | — |
| `--style` | 语音风格标记 | — |

### 竞赛模板

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--competition` | 竞赛模板（见第 8 节） | — |
| `--time-limit` | 排练时限（分钟） | 竞赛默认值 |

### 通用

| 选项 | 说明 |
|------|------|
| `--overwrite` | 覆盖已有文件 |

---

## 6. 画布预设（formats.py）

11 种内置画布格式，通过 `--format` 选择。

| ID | 像素尺寸 | 比例 | PPTX 尺寸 (in) | 用途 |
|----|----------|------|-----------------|------|
| `ppt169` | 1280×720 | 16:9 | 13.33×7.50 | 商务宽屏演示 |
| `ppt43` | 1024×768 | 4:3 | 10.00×7.50 | 传统投影仪 |
| `square` | 1080×1080 | 1:1 | 10.00×10.00 | 方形社交帖子 |
| `story` | 1080×1920 | 9:16 | 7.50×13.33 | 手机竖屏故事 |
| `xhs` | 1242×1660 | 3:4 | 7.50×10.02 | 小红书帖子 |
| `wechat` | 1080×1080 | 1:1 | 10.00×10.00 | 微信朋友圈 |
| `a4` | 1123×794 | √2:1 | 10.00×7.07 | A4 文档页 |
| `letter` | 1056×816 | ~1.29:1 | 10.00×7.73 | US Letter 文档页 |
| `ipad` | 1536×2048 | 3:4 | 7.50×10.00 | iPad 竖屏 |
| `ultrawide` | 2560×1080 | 21:9 | 18.00×7.50 | 超宽屏演示 |
| `banner` | 1920×1080 | 16:9 | 13.33×7.50 | 横幅图 |

---

## 7. 视觉模板（templates.py）

8 套内置主题，通过 `--template` 选择。也可通过 JSON 文件加载自定义模板。

### 内置主题

| ID | 名称 | 风格 | 圆角 | 字体 |
|----|------|------|------|------|
| `midnight` | Midnight Blue | 深蓝商务科技 | 16 | Aptos |
| `aurora` | Aurora | 深紫高端典雅 | 20 | Aptos |
| `paper` | Paper | 白底学术正式 | 12 | Aptos |
| `neon` | Neon | 纯黑赛博朋克 | 8 | Consolas |
| `sakura` | Sakura | 柔粉日系温暖 | 24 | Aptos |
| `gradient` | Gradient | 深靛渐变科技 | 20 | Aptos |
| `minimal` | Minimal | 纯白极简留白 | 8 | Aptos |
| `corporate` | Corporate | 深蓝企业正式 | 12 | Aptos |

### 自定义模板

通过 JSON 文件加载，需包含完整 `palette` 键（11 个色值）：

```json
{
  "name": "My Theme",
  "description": "自定义模板描述",
  "palette": {
    "background": "#1a1a2e",
    "surface": "#16213e",
    "text": "#eaeaea",
    "body": "#a8a8a8",
    "accent": "#e94560",
    "footer_bg": "#0f3460",
    "chrome_muted": "#533483",
    "decor_light": "#1a1a2e",
    "decor_medium": "#16213e",
    "decor_line": "#0f3460",
    "hero_start": "#16213e"
  },
  "card_radius": 16,
  "title_decoration": "underline",
  "font_family": "Aptos, Arial, sans-serif"
}
```

缺少任何 palette 键会抛出 `ValueError`。

---

## 8. 竞赛模板（competition.py）

6 套内置竞赛结构，通过 `--competition` 选择。

| ID | 名称 | 时限 | 页数范围 |
|----|------|------|----------|
| `internet-plus` | 互联网+创新创业大赛 | 8 分钟 | 15–20 页 |
| `challenge-cup` | 挑战杯课外学术科技作品竞赛 | 8 分钟 | 15–18 页 |
| `math-modeling` | 数学建模竞赛 | 10 分钟 | 12–18 页 |
| `innovation-training` | 大学生创新创业训练计划（大创） | 5 分钟 | 10–15 页 |
| `thesis-defense` | 毕业论文答辩 | 15 分钟 | 15–25 页 |
| `course-presentation` | 课程展示 | 10 分钟 | 8–12 页 |

每套模板定义：章节结构（标题、页数范围、内容引导）、评审时限、评审提示。

---

## 系统依赖（渲染 QA）

| 依赖 | 用途 | 检测方式 |
|------|------|----------|
| LibreOffice | PPTX → PDF | `render.py` 环境诊断 |
| Poppler (`pdftoppm`) | PDF → PNG | `render.py` 环境诊断 |

渲染 QA 为可选功能。缺失系统依赖时，结构 QA 仍可正常运行。
