<!-- GSD:docs-update -->
# 快速开始

Slide Skill 是一个 SVG 优先的 PowerPoint 技能包与 Python 工具集，帮助 AI 智能体可靠地生成、审查和导出可编辑的 PPTX 演示文稿。

## 前置条件

- **Python 3.10+**
- **pip**（随 Python 自带）
- （可选）LibreOffice — 用于渲染 PDF / 图片进行视觉 QA
- （可选）Poppler — 用于 PDF 转图片（`pdftoppm`）

## 安装

```powershell
# 核心包
pip install slide-skill

# 附加可选依赖
pip install slide-skill[intake]      # 源文件转换（PDF/DOCX/XLSX/Markdown 等）
pip install slide-skill[audio]       # edge-tts 语音合成
pip install slide-skill[mimo]        # MiMo TTS 语音合成
pip install slide-skill[intake,audio,mimo]  # 全部安装
```

## 验证安装

```powershell
slide-skill --help
```

看到命令列表即表示安装成功。

## 快速上手：CLI

从示例 Markdown 一键生成演示文稿：

```powershell
slide-skill quickstart examples/demo.md --name my-demo
```

生成的文件位于 `projects/my-demo/exports/`，可直接用 PowerPoint 打开编辑。

> `quickstart` 在结构检查通过时会自动写入 `status: automated-passed` 的 QA 记录。如需完整视觉 QA 门控，请使用 `slide-skill qa <project> --strict`。

## 快速上手：IDE 智能体

Slide Skill 的规则文件会被以下 IDE 智能体自动加载，无需手动配置：

| IDE / 智能体 | 加载方式 |
|---|---|
| Claude Code | 读取 `AGENTS.md` 及 `.claude/` 下的技能文件 |
| Cursor | 读取 `.cursor/` 下的规则与技能文件 |
| VS Code Copilot | 读取 `.github/copilot-instructions.md` |
| Windsurf | 读取项目根目录的规则文件 |

在任意上述环境中打开项目即可使用 Slide Skill。

## 分步工作流

以下是完整的幻灯片制作流程：

```powershell
# 1. 初始化项目与规格
slide-skill spec projects/my-deck --source projects/my-deck/sources/source.md

# 2. 生成 SVG 草稿
slide-skill svg projects/my-deck --source projects/my-deck/sources/source.md

# 3. SVG 质量检查（检测不支持的标签与属性）
slide-skill check-svg projects/my-deck

# 4. 通过检查后，定稿 SVG（复制到 svg_final/）
slide-skill finalize-svg projects/my-deck

# 5. 导出为原生可编辑 PPTX
slide-skill export projects/my-deck

# 6. 质量保证（文本 + 视觉）
slide-skill qa projects/my-deck
```

### 工作流说明

| 步骤 | 命令 | 作用 |
|------|------|------|
| spec | `spec` | 解析源内容，生成 `spec_lock.json` 锁定画布尺寸与布局 |
| svg | `svg` | 基于规格生成 SVG 草稿到 `svg_draft/` |
| check-svg | `check-svg` | 校验 SVG 合规性，拒绝不支持的标签/属性 |
| finalize-svg | `finalize-svg` | 将通过检查的 SVG 复制到 `svg_final/` |
| export | `export` | 将 SVG 转换为原生可编辑 PPTX |
| qa | `qa` | 文本 QA + 渲染视觉 QA（需 LibreOffice + Poppler） |

## 可选系统依赖

视觉渲染与 QA 需要以下系统级工具：

- **LibreOffice**（headless 模式）：将 PPTX 转 PDF
  - 安装后确保 `soffice` 在 PATH 中
- **Poppler**：将 PDF 转图片用于视觉检查
  - 安装后确保 `pdftoppm` 在 PATH 中

渲染诊断：

```powershell
slide-skill render-doctor
```

## 下一步

- [使用指南](USAGE.md) — 完整命令参考与已知限制
- [SVG 管线详解](../skills/slide/guides/svg-pipeline.md) — SVG 规则与定稿流程
- [导出指南](../skills/slide/guides/export.md) — PPTX 导出选项
- [QA 指南](../skills/slide/guides/qa.md) — 文本与视觉 QA 标准
- [编辑指南](../skills/slide/guides/editing.md) — 修改已有 PPTX
- [源文件摄入](../skills/slide/guides/intake.md) — 从 PDF/DOCX/XLSX 等提取内容
