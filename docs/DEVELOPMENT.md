<!-- GSD:docs-update -->

# 开发指南

本文档面向 Slide Skill 项目的贡献者，涵盖项目结构、关键模块、开发环境搭建、编码规范及扩展流程。

## 1. 项目结构

```
slide-skill/
├── tools/slide/src/slide_skill/   # 主包：SVG 管线、转换器、导出器、CLI
├── skills/slide/                  # Skill 文档：SKILL.md 及引导文件
├── tests/                         # 测试套件
├── examples/                      # 示例输入（SVG、Markdown、PPTX 等）
├── projects/                      # 生成的输出目录（gitignored）
└── docs/                          # 项目文档
```

- `tools/slide/src/slide_skill/` — 所有运行时代码，安装后即为 `slide_skill` 包。
- `skills/slide/` — Agent 加载的 Skill 入口及子指南，保持简短可检视。
- `tests/` — 脚本级测试 + fixture 演示文稿，防止打包/解包/关系校验的静默损坏。
- `examples/` — 供开发与测试使用的样本输入文件。
- `projects/` — 运行时输出，已加入 `.gitignore`，不提交到仓库。

## 2. 关键模块

| 模块 | 路径 | 职责 |
|------|------|------|
| `svg_pipeline.py` | `tools/slide/src/slide_skill/svg_pipeline.py` | 核心管线：接收 SVG 输入，协调解析、布局、导出全流程 |
| `converters.py` | `tools/slide/src/slide_skill/converters.py` | SVG 元素注册表：将 SVG 标签映射到对应的转换函数 |
| `geometry.py` | `tools/slide/src/slide_skill/geometry.py` | 路径解析 + DrawingML 生成：SVG path → EMU 坐标 + DrawingML XML |
| `exporter.py` | `tools/slide/src/slide_skill/exporter.py` | SVG → PPTX 导出器：将转换后的元素写入 python-pptx 对象 |
| `cli.py` | `tools/slide/src/slide_skill/cli.py` | CLI 入口：20+ 子命令（create、render、qa、unpack 等） |

模块间数据流：`SVG 输入 → svg_pipeline → converters（元素分发）→ geometry（坐标/路径）→ exporter（PPTX 组装）→ .pptx 文件`

## 3. 开发环境搭建

```bash
# 克隆仓库
git clone <repo-url> slide-skill
cd slide-skill

# 基础安装（可编辑模式）
pip install -e .

# 含额外依赖的完整安装
pip install -e .[intake,audio,mimo]
```

- `[intake]` — 源摄入相关依赖（PyMuPDF、mammoth、openpyxl 等）
- `[audio]` — 语音旁白依赖（edge-tts）
- `[mimo]` — MIMO 多输入多输出相关依赖

## 4. 代码风格

- **Python 3.10+**：使用 `match`、`TypeAlias`、`ParamSpec` 等现代语法
- **类型注解**：所有公开函数必须标注参数和返回类型
- **无注释**：除非意图不明显，否则不写注释；代码应自解释
- **单职责函数**：每个函数只做一件事，缩进不超过 3 层
- **命名**：可读性优先于巧妙性，避免缩写

## 5. 添加新的 SVG 元素转换器

1. 在 `converters.py` 的 `ConverterRegistry` 中注册新转换器：

```python
from slide_skill.converters import ConverterRegistry

@ConverterRegistry.register("my_element")
def convert_my_element(svg_elem, context) -> SlideElement:
    ...
```

2. 确保转换器返回符合 `SlideElement` 协议的对象。
3. 在 `tests/` 下添加对应的单元测试，覆盖正常路径和边界情况。
4. 运行 `python -m pytest tests/ -x -q` 确认全部通过。

## 6. 添加新的视觉模板

1. 在 `templates.py` 的模板注册表中添加新模板：

```python
from slide_skill.templates import TemplateRegistry

@TemplateRegistry.register("my_template")
class MyTemplate(BaseTemplate):
    def build_svg(self, content: SlideContent) -> str:
        ...
```

2. 模板负责将内容映射到 SVG 布局，返回完整 SVG 字符串。
3. 添加测试用例验证输出 SVG 的结构正确性。
4. 在 `skills/slide/` 的引导文档中补充模板使用说明。

## 7. 添加新的竞赛模板

1. 在 `competition.py` 中添加新竞赛模板条目。
2. 竞赛模板继承视觉模板，额外限定尺寸、字体、配色等竞赛规范。
3. 添加 fixture 演示文稿到 `tests/` 以验证合规性。

## 8. 添加新的画布格式

1. 在 `formats.py` 中注册新格式：

```python
from slide_skill.formats import FormatRegistry

@FormatRegistry.register("my_format")
class MyFormat(BaseFormat):
    width: int   # EMU
    height: int  # EMU
    dpi: int
    ...
```

2. 格式定义画布尺寸、DPI、安全边距等物理参数。
3. 更新 CLI 的 `--format` 选项以包含新格式名称。

## 9. 运行测试

```bash
# 快速测试（遇错即停）
python -m pytest tests/ -x -q

# 完整测试（含详细输出）
python -m pytest tests/ -v

# 仅运行特定模块测试
python -m pytest tests/test_converters.py -x -q
```

测试覆盖要求：
- **正常路径**：所有需求定义的正常用例
- **边界情况**：空输入、最大限制、边界值
- **错误处理**：无效输入、失败场景、权限错误
- **状态转换**：有状态组件的所有合法状态变更

## 10. 构建发布包

```bash
# 构建 sdist + wheel
python -m build

# 产物位于 dist/
ls dist/
```

构建前确认：
1. 所有测试通过
2. 版本号已在 `pyproject.toml` 中更新
3. CHANGELOG 已记录本次变更
