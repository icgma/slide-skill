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

> `quickstart` 默认使用 AI 逐页生成 SVG，需要 `OPENAI_API_KEY`，或通过 `--ai-base-url` 指向本地 OpenAI-compatible 服务。本地服务不需要真实 key；CLI 会自动提供 SDK 兼容用的 dummy key。只想跑确定性的转换器冒烟测试时，显式使用 `--mode template-smoke`。

AI 生成不是一次性模板渲染。每页生成时会读取 `spec_lock.json` / `spec_lock.md`、设计指南、上一轮 SVG QA 失败项，以及可选的视觉反馈；如果因为 QA 失败进入重试，executor 会重新读取当前 `spec_lock` 并重建 system prompt 和 page prompt，避免沿用陈旧的 palette/font。每次 SVG 生成 prompt 都会包含 Content Fidelity Contract，列出必须以实际可见的 `<text>` / `<tspan>` 输出的标题和正文 `primary` / `secondary` / `tertiary` 字段；`display="none"`、`visibility="hidden"`、`opacity="0"`、`fill-opacity="0"` 等隐藏文本不会被算作通过。如果模型输出了结构正确但漏内容的页面，会把缺失内容反馈给模型重写。每次 executor attempt 的 SVG 会先保存到 `qa/executor/attempt-svg/`，并对该候选页运行结构、输出协议、spec drift、font safety 和 content fidelity 检查；markdown fence、SVG 前后的解释文字、多个 SVG 文档都会反馈给模型重写，而不是静默截取后通过。只有通过这些 gate 的 attempt 才发布到正式 `svg_output/slide_XX.svg`，所以失败重试不会覆盖上一版可用页面。渲染后如果发现版式问题，优先运行 `slide-skill iterate-ai <project> --strict-qa` 进行导出、渲染、视觉批评、自动修复、再导出、最终复评和严格 QA；命令会写入 `qa/FIX-VERIFY.md` 和机器可读的 `qa/AI-ITERATION.json`。多次修复或比较模型/提示词时，用 `slide-skill ai-iteration-summary <project-or-parent>` 查看本次 run-scoped 的 trace 数、失败/阻塞数、视觉反馈注入次数和 prompt/raw/request 字符量，避免被历史累计 trace 污染。也可以单独运行 `slide-skill visual-critic <project>` 生成 `qa/VISUAL-REVIEW.md` 和 `qa/visual-feedback.json`。AI 视觉批评会读取 `qa/ai-planner/executor-brief.md` 中当前页的预期内容和设计契约，用来判断渲染图是否漏掉标题/正文，而不只是判断版式；它也会为问题页写入面向 SVG executor 的 `repair_prompt`。如果非 ok 输出缺少这段修复提示，提示太泛（例如只说 fix the slide），与问题/动作无关，或 `severity: ok` 却带有 issues/actions/repair_prompt，会反馈给视觉模型重试；相关性检查支持中文短语。新的 AI 视觉批评会先清除上一轮 AI 生成的旧反馈，但保留人工 review；如果所有重试仍不合格，命令会失败且不留下旧 AI 反馈文件，避免下一轮修复消费过期意见。下一轮 executor 会把通过质量门的视觉反馈提升为 Rendered Visual Repair Contract，优先执行 `repair_prompt`，并明确禁止通过删除、隐藏、改写或移出必需文字来规避版式问题。

生产模式还会把上游规划纳入 LLM 互动：`quickstart` / `build` 的 `--planner auto` 在 `--mode ai` 下使用 AI Strategist 生成结构化 `SlidePlan`。如果 planner 返回无效 JSON、在 JSON 外包 markdown fence 或解释文字、缺少具体 `visual_strategy` / `layout_pattern`，连续重复布局，漏掉从源文标题、要点、指标行抽取出的 source coverage anchors，把这些锚点只藏在 notes/设计字段里，在标题/items/notes 中编造源文没有的数字/指标，返回错误的控制字段（非顺序 index、非法 density、非法 rhythm），超过 `max_slides` / `max_items_per_slide`，或把 item 写成字符串而不是带 `primary` 的对象，系统会把校验错误反馈给模型重试，而不是静默清理、裁剪或丢弃。这里的“具体”不是泛泛说 hero 或 important message：`visual_strategy` 必须给出可执行的视觉装置/层级/几何，例如 accent rail、proof card、metric block、comparison grid；`layout_pattern` 必须给出实际摆位/结构，例如 title-left proof-card-right、two-column grid、top metric row with lower bullets。新的 AI planner run 会先清除旧的 `plan.json`、`executor-brief.md` 和 `raw-response.txt`；只有通过校验后才发布新的最终计划和 executor brief，最终失败时改写 `failure.json`，避免后续生成误读旧计划。SVG 生成时会自动把当前页的 `executor-brief.md` section 和 Planner Design Execution Contract 注入 executor prompt，把规划结果作为硬布局要求而不是灵感参考；常见布局词还会被转译成建议坐标区间，例如 left/right 两栏、top/lower 区带、grid、proof card、hero/image 区域，让模型拿到像素级摆位线索。每次 executor attempt 还会做轻量 layout-intent QA：如果 planner 要求左右、上下或 grid/comparison 结构，实际可见 SVG 元素必须落到对应区域，否则会把问题反馈给模型重写。attempt log 和 `ai-trace` 会记录 `has_executor_brief`。如果只想使用确定性规则规划，显式传入 `--planner deterministic`。

多阶段 LLM 可以分别配置模型：`--model` 是全局默认，`--planner-model` 覆盖规划模型，`--executor-model` 覆盖 SVG 生成模型，`--vision-model` 覆盖视觉批评模型。

多阶段反馈强度也可以分别配置：`--planner-retries` 控制规划校验重试，`--executor-qa-retries` 控制 SVG/content QA 失败后的重写次数，`--vision-retries` 控制视觉批评输出无效或缺少 `repair_prompt` 时的重试次数。

如果生成结果“不够好”，先运行 `slide-skill ai-trace <project>`。它会把 `qa/ai-trace.jsonl` 汇总成人可读的 planner / executor / visual-critic 互动记录，包括模型、尝试次数、失败状态、阻塞 QA 数量，以及是否注入了 planner brief 和视觉反馈。executor 失败行还会显示简短的 `blocking_issues`，用来区分模型是忽略布局合同、漏内容，还是违反 SVG 输出协议。planner/executor 的 provider 异常，例如鉴权、模型名、网络、限流错误，也会记录成 failed trace event 并保留 request sidecar，真实 provider 配置问题不会只停留在 stderr。需要快速判断问题归属时，运行 `slide-skill ai-trace <project> --diagnose`；它会汇总 stage/status 计数、最近失败事件、阻塞 issue、planner/executor 是否通过、sidecar 是否缺失，以及 executor 是否缺少 planner brief 注入。遇到视觉修复门或 `--require-visual-ok` 失败时，诊断还会输出 `repair-target` 和 `repair-command`；优先按这些逐页修复提示执行下一轮，而不是先改全局 prompt。`quickstart`、`build`、`visual-critic`、`repair-slide`、`repair-feedback`、`iterate-ai` 或 `ai-smoke` 因 AI 质量门或缺少修复素材失败时，CLI 会直接打印 trace 命令和 `--diagnose` 命令，并附上最近失败的 stage、attempt、model 和 slide。完整 prompt、原始响应和请求结构会保存到 `qa/ai-trace-artifacts/`；也可以用 `slide-skill ai-trace <project> --event 3 --part prompt`、`--part raw` 或 `--part request` 直接打印指定交互，方便复现和调试模型互动。视觉模型的 request sidecar 会省略内联图片 base64，只保留图片来源占位符。

要确认真实 LLM provider 是否能跑通，不要只看 mock 测试。先运行 `slide-skill ai-doctor` 预检 planner/executor 的最小文本请求；如果要使用 `visual-critic` 或 `iterate-ai`，再运行 `slide-skill ai-doctor --check-vision`，它会发送一个极小图片请求来确认 vision 模型和账号权限。发布前使用更严格的 `slide-skill ai-release-check --name release-llm-gate`；它会先做 planner/executor/vision provider 预检，再强制执行真实 planner → executor → render → visual-critic 冒烟，并要求最终视觉严重级别为 `ok`；如果视觉 smoke 可修复，会默认自动运行最多 2 轮视觉复评/修复（可用 `--repair-rounds` 调整），并在 `qa/AI-RELEASE-CHECK.json` 中分别标记是否进入复评和是否实际改写 SVG。上线验收环境应安装 LibreOffice 和 Poppler，并运行 `slide-skill ai-release-check --name release-llm-gate --require-pptx-render`；这个 gate 会拒绝 SVG 预览 fallback 和外部 `--rendered-dir` 图片，只有从导出的 PPTX 实际渲染出的证据才会让 `gates.rendered_source_pptx` 通过。之后运行 `slide-skill ai-smoke --name real-llm-smoke`，它会用一页样例走真实 AI planner 和 AI executor，输出持久项目、PPTX、QA 报告、`qa/AI-SMOKE.json` 机器可读结论和 trace 摘要；要把视觉模型也纳入同一次冒烟测试，运行 `slide-skill ai-smoke --name real-llm-smoke-vision --visual-critic`。如果本机没有 LibreOffice/Poppler，visual smoke 会在可用时用本机 Chrome/Edge 把本次生成的 SVG 页面渲染成预览截图；如果你已经用其他方式渲染图片，也可以传 `--rendered-dir <dir>`，命令会把图片复制到项目 `qa/rendered/` 并调用 vision critic。`qa/AI-SMOKE.json` 在失败时也会写入，记录错误、已发生的 trace event，以及未完成时为空的 deck/QA 字段；如果 deck 和 QA 已经生成但视觉反馈达到 `major` 或 `critical`，smoke 会失败并保留这些产物路径，避免把可修复但严重的视觉问题当成生成质量通过。视觉门失败时，`AI-SMOKE.json.diagnosis`、`AI-ITERATION.json` 和 `AI-RELEASE-CHECK.json.summary` 会在可用时写入 `repair_targets`、`repair_target_count` 和 `repair_command`，CI 或智能体可以直接拿这些字段启动下一轮 `repair-feedback`，不必重新解析 `visual-feedback.json`。多次调整 prompt 或模型后，用 `slide-skill ai-smoke-summary test-output/live-llm` 或 `slide-skill ai-smoke-summary <project-a> <project-b>` 汇总比较结果；表格会显示失败事件数、executor 阻塞数、最高视觉严重级别以及 prompt/raw/request 总字符数，用来发现 prompt 膨胀、模型输出异常变短、视觉退化或某阶段失败；`repair:targets=N`、`visual-ok:targets=N`、`failed:targets=N` 或 `blocked:repair-targets=N` 这类 hint 表示结果 JSON 里已有可执行修复目标，必要时加 `--json` 给 CI 或脚本读取。失败时同样可以用 `slide-skill ai-trace test-output/live-llm/real-llm-smoke --diagnose` 检查完整交互。使用兼容端点时设置 `OPENAI_BASE_URL`，需要分角色模型时设置 `OPENAI_PLANNER_MODEL` / `OPENAI_EXECUTOR_MODEL` / `OPENAI_VISION_MODEL` 或传入对应 CLI 参数。

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
