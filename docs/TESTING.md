<!-- GSD:docs-update -->
# 测试指南

## 运行测试

**推荐方式**（pytest）：

```bash
python -m pytest tests/ -x -q
```

- `-x`：首个失败即停止，便于快速定位问题
- `-q`：精简输出

**备选方式**（stdlib unittest）：

```bash
python -m unittest discover -s tests -v
```

运行单个测试文件：

```bash
python -m pytest tests/test_geometry.py -v
```

运行匹配关键字的测试：

```bash
python -m pytest tests/ -k "snapshot" -v
```

## 测试结构

全部 16 个测试文件位于 `tests/` 目录，共 144 个测试用例。项目混用两种风格：

| 风格 | 文件 | 说明 |
|------|------|------|
| `unittest.TestCase` 类 | `test_geometry.py`、`test_pipeline.py`、`test_animations.py` 等 | 早期模块，类式组织 |
| pytest 函数 + `capsys` | `test_cli_new.py`、`test_draft_notes.py`、`test_competition.py` 等 | 后期模块，函数式，使用 pytest fixture |

两种风格均可被 pytest 发现并执行，无需额外配置。

## 测试分类

### 单元测试

验证独立模块的输入/输出逻辑，无外部依赖。

| 文件 | 行数 | 覆盖内容 |
|------|------|----------|
| `test_geometry.py` | 329 | SVG 路径几何——全部 20 种 path 命令、polygon、polyline、`compute_bbox`、`parse_svg_path`、`points_to_commands` |
| `test_animations.py` | 160 | 幻灯片切换与元素动画 XML 生成、预设注入、时序构建 |
| `test_rich_notes.py` | 106 | 富文本演讲备注导出到 PPTX notes |
| `test_draft_notes.py` | 175 | 备注草稿生成——幻灯片分类、SVG 文本提取、备注模板 |
| `test_rehearse.py` | 139 | 演练计时——语速估算、分页时间分配、报告格式化 |
| `test_competition.py` | 80 | 竞赛模板规格——6 种竞赛名称、字段校验、Markdown 输出 |
| `test_template_ops.py` | 96 | 模板操作——复制、占位符替换、验证 |
| `test_narrate.py` | 56 | TTS 语音合成——音频生成、可用语音列表 |
| `test_mimo_tts.py` | 69 | MiMo TTS 引擎集成 |
| `test_intake.py` | 27 | 源文件摄入——Markdown/DOCX/PDF 转换 |
| `test_render.py` | 34 | 渲染诊断——LibreOffice 可用性、输出路径 |

### 集成测试

验证多模块协作的端到端流程。

| 文件 | 行数 | 覆盖内容 |
|------|------|----------|
| `test_pipeline.py` | 100 | 完整 SVG 流水线：Markdown → spec → SVG → finalize → PPTX 导出 → QA 校验 |
| `test_competition_workflow.py` | 85 | 竞赛项目初始化 → SVG 生成 → 导出完整流程 |
| `test_cli_new.py` | 57 | CLI 入口集成——`competitions`、`voices`、`init --competition` 子命令 |

### 视觉测试

基于像素比较的回归验证，依赖 Pillow + numpy。

| 文件 | 行数 | 覆盖内容 |
|------|------|----------|
| `test_snapshot.py` | 158 | 像素快照对比——同图通过、异图报告差异、报告生成 |
| `test_svg_rendering.py` | 160 | SVG 渲染输出——尺寸、视口、元素完整性 |

## 测试依赖

| 依赖 | 用途 | 安装 |
|------|------|------|
| `pytest` | 推荐测试运行器，支持 `-k` 过滤、`capsys` fixture | `pip install pytest` |
| `unittest` | stdlib 内置，零依赖备选 | Python 自带 |
| `Pillow` | 视觉测试图片生成 | `pip install Pillow` |
| `numpy` | 像素差异计算 | `pip install numpy` |

## 添加新测试

1. **遵循已有模式**：查看同模块现有测试文件的风格（类式 or 函数式），保持一致
2. **使用 `tempfile`**：所有涉及文件 I/O 的测试用 `tempfile.TemporaryDirectory()` 创建临时目录，测试结束自动清理
3. **通过 `init_project()` 构建 fixture**：需要项目目录时调用 `slide_skill.project.init_project()`，而非手动创建目录树
4. **命名规范**：文件名 `test_<模块>.py`，测试方法 `test_<行为描述>`
5. **断言风格**：unittest 类用 `self.assertXxx()`，pytest 函数用 `assert` 语句
6. **运行验证**：添加后执行 `python -m pytest tests/ -x -q` 确认全部通过

示例（函数式）：

```python
import tempfile
from pathlib import Path
from slide_skill.my_module import my_function

def test_my_function_output():
    with tempfile.TemporaryDirectory() as tmp:
        result = my_function(Path(tmp))
        assert result.exists()
```

示例（类式）：

```python
class MyModuleTest(unittest.TestCase):
    def test_my_function_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = my_function(Path(tmp))
            self.assertTrue(result.exists())
```

## CI 要求

- **全部 144 个测试必须通过**，零失败、零错误
- CI 命令：`python -m pytest tests/ -x -q`
- 任何新增测试需同步更新本文档的测试计数
