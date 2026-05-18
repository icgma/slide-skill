# Phase 24: Spec Propagation & Anti-Drift — Context

## Phase Goal

实现增量设计传播和逐页防漂移，使迭代设计不再需要全量重生成

## Requirements

- SP-01: slide-skill update-spec 可读取 spec_lock 变更并增量传播到已有 SVG 文件
- SP-02: 支持传播的字段：palette 颜色（HEX 替换）、font-family（属性限定替换）
- SP-03: 不支持增量传播的字段（字号、图标、画布）明确报错并提示重生成
- SP-04: 传播后自动重跑 SVG QA 验证无破坏性变更
- AD-01: SVG 生成循环中每页前重读 spec_lock.json（已在 Phase 22 实现）
- AD-02: 重读的 spec_lock 值与首页严格一致，不一致时报错（已在 Phase 22 实现为警告）

## Decisions

### AD-01/AD-02: 已在 Phase 22 实现
- generate_svg() 中每页前重读 spec_lock.json，palette/font 不一致时发 warnings.warn
- SKILL.md 已指示长幅演示逐页重读
- 本阶段不再重复实现，聚焦 SP-01~04

### update-spec 传播策略
- 读取旧 spec_lock 和新 spec_lock 的差异
- 仅传播 palette（HEX 颜色替换）和 font_family（属性限定替换）
- 颜色替换：在所有 SVG 文件中查找旧 HEX 值并替换为新值（case-insensitive）
- font-family 替换：在所有 SVG 文件的 font-family 属性中替换
- 不支持传播的字段明确报错：font_size, icon, canvas, layout, page_rhythm
- 传播完成后自动调用 check_project_svg() 验证

### CLI 接口
- `slide-skill update-spec <project>` — 读取当前 spec_lock.json 并传播到 svg_output/
- 传播前自动备份 svg_output/ 到 svg_output.bak/
- 报告传播结果：替换了多少文件、多少处

### 颜色替换实现
- 提取旧 palette 中所有 HEX 值（#RRGGBB 格式）
- 对每个旧颜色，在 SVG 文件的 fill/stroke/stop-color 属性中查找并替换
- 同时替换内联样式中的颜色值
