# Phase 23: Image Acquisition Workflow — Context

## Phase Goal

实现图片搜索、AI 生成、许可过滤和自动引用，使演示不再缺图

## Requirements

- IMG-01: Agent 可通过 `slide-skill image-search <query>` 搜索网络图片并下载到 `images/`
- IMG-02: 图片搜索支持 Creative Commons 许可过滤（默认 CC BY / CC BY-SA），拒绝 NC/ND 许可
- IMG-03: Agent 可通过 `slide-skill image-generate <prompt>` 调用 AI 图像生成 API 填充 `images/`
- IMG-04: 图片元数据（来源、许可、尺寸、主色）记录在 `images/metadata.json`
- IMG-05: SVG 生成时自动引用 `images/` 中的匹配资源（按 spec_lock 中的资源列表）

## Decisions

### 图片搜索实现：DuckDuckGo/Google Custom Search API
- 优先使用无需 API key 的方案（DuckDuckGo HTML 解析或 `requests` + CC Search API）
- CC Search API (search.creativecommons.org) 是首选 — 直接返回 CC 许可元数据
- 备选：Google Custom Search（需 API key），作为可选后端

### AI 图像生成：OpenAI-compatible API
- 使用 `openai` 库（已有 mimo 可选依赖），调用 images.generate
- 支持 `IMAGE_API_KEY` 和 `IMAGE_BACKEND` 环境变量
- 默认后端：openai（DALL-E）
- 生成的图片存入 `images/` 并记录元数据

### 许可过滤策略
- 默认允许：CC BY, CC BY-SA, CC0 (Public Domain)
- 默认拒绝：CC BY-NC, CC BY-ND, CC BY-NC-ND, CC BY-NC-SA
- `--allow-nc` 标志可放宽过滤
- 搜索结果自动标注许可类型

### SVG 自动引用
- spec_lock.json 新增 `resources` 列表（图片资源引用）
- `generate_svg()` 时，image 布局类型自动匹配 `images/` 中的资源
- 匹配逻辑：按 spec_lock.resources 中的顺序分配给 image 布局的幻灯片

### metadata.json 结构
```json
{
  "images": [
    {
      "filename": "img_001.jpg",
      "source": "search|generate",
      "query": "原始查询",
      "license": "CC BY 4.0",
      "license_url": "https://...",
      "dimensions": {"width": 1024, "height": 768},
      "dominant_color": "#336699",
      "created_at": "ISO timestamp"
    }
  ]
}
```

## Prior Decisions Applied

- From Phase 22: confirmations.json 门控、spec_lock.json 新字段
- From v1.5: 8 templates + 8 layout types (including `image` layout)
- `images/` 目录在 project.py init_project 中已创建
