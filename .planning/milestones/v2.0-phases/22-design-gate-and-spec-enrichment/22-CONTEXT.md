# Phase 22: Design Gate & Spec Enrichment — Context

## Phase Goal

实现八确认门控和设计规格丰富化，使管线从"机械生成"升级为"意图驱动"

## Requirements

- DG-01: Agent 必须在 SVG 生成前通过八项确认门控
- DG-02: 确认结果持久化为 confirmations.json
- DG-03: 确认门控可跳过（--skip-confirm），仅限 quickstart 等快速路径
- DSE-01: design_spec.md 扩展包含目标受众、演示目标、逐页设计意图、视觉策略
- DSE-02: design_spec.md 每页包含 key_message 字段
- DSE-03: spec_lock.json 新增 audience、objective、per_page_rationale 字段
- DSE-04: 竞赛模板的 design_spec 自动填充赛制要求
- AD-03: 长幅演示 SKILL.md 指示 agent 逐页重读 spec_lock

## Decisions

### 确认交互形式：Agent 对话驱动
- SKILL.md 指示 agent 在对话中收集八确认，写入 confirmations.json
- Agent 理解自然语言，可追问澄清，体验最佳
- CLI 提供验证命令 `slide-skill check-confirm <project>` 确认 confirmations.json 完整
- 不走 CLI 交互式问答路线（agent 天然具备对话能力，无需模拟）

### 确认项粒度：8 项 + 模板可扩展
- 通用 8 项：标题、受众、关键要点、布局策略、配色方案、页数、特殊要求、确认
- 竞赛模板可覆盖/扩展确认项（如增加"赛制时限"、"评审要点"）
- 竞赛模板的 competition.py 已有 time_limit 和 section_guidance，可直接映射到扩展确认项

### 设计规格深度：完整深度
- design_spec.md 扩展到逐页完整设计意图 + 视觉策略 + 参考风格
- 每页字段：key_message、design_rationale、visual_strategy、reference_style
- 全局字段：audience、objective、overall_visual_strategy、tone
- 工作量较大但 ppt-master 验证了这一深度的价值（Strategist 角色产出完整设计文档）

### 文件关系：confirmations.json 与 spec_lock.json 保持独立
- confirmations.json：记录用户确认了什么（确认状态、时间戳）
- spec_lock.json：记录生成参数是什么（颜色、字体、布局）
- 生命周期不同：确认在 spec 之前，确认完成后才写 spec_lock
- generate_svg() 检查 confirmations.json 存在且完整才允许执行

## Specifics

### 八确认默认项（DG-01）
1. **title** — 演示标题
2. **audience** — 目标受众（如"互联网+评委"、"课程学生"）
3. **key_points** — 核心要点列表（3-5 个）
4. **layout_strategy** — 布局策略（如"内容驱动"、"视觉冲击"、"数据密集"）
5. **color_scheme** — 配色方案（模板名或自定义 palette）
6. **page_count** — 目标页数（范围或精确值）
7. **special_requirements** — 特殊要求（如"需要动画"、"需要旁白"、"中文为主"）
8. **confirmation** — 最终确认（agent 确认所有项已与用户对齐）

### confirmations.json 结构
```json
{
  "project": "项目名",
  "confirmations": {
    "title": { "value": "...", "confirmed_at": "ISO timestamp" },
    "audience": { "value": "...", "confirmed_at": "ISO timestamp" },
    ...
  },
  "all_confirmed": true,
  "created_at": "ISO timestamp"
}
```

### design_spec.md 扩展结构
```markdown
# Design Specification

## 全局
- **Audience**: ...
- **Objective**: ...
- **Overall Visual Strategy**: ...
- **Tone**: ...

## Per-Page Design Intent
### Slide 1: [Title]
- **Key Message**: ...
- **Design Rationale**: ...
- **Visual Strategy**: ...
- **Reference Style**: ...
```

### spec_lock.json 新增字段
```json
{
  "audience": "...",
  "objective": "...",
  "per_page_rationale": {
    "slide_01": { "key_message": "...", "design_rationale": "..." }
  }
}
```

## Prior Decisions Applied

- From v1.1-v1.5: SVG-first pipeline, palette-driven templates, semantic layout selection
- From v1.5: 8 templates + 8 layout types + competition toolkit
- Clean-room: 独立实现，参考 ppt-master 模式但不复制代码

## Deferred Ideas

(none — all within phase scope)
