# 大语言模型驱动的产品设计

> 一份用 slide-skill 一行命令生成的中文演示文稿样例。

## 我们要解决的问题

- 传统幻灯片工具需要手动排版每一页
- 设计师与工程师之间的协作成本高
- 改一处文字，整页排版都要重做
- AI 生成的内容难以直接落到精美的母版

## 核心数据

- 用户调研覆盖 **2400** 位设计师
- 平均每份提案节省 **6.5** 小时
- 模板复用率提升至 **89%**
- 客户满意度评分 **4.8 / 5**

## 方案对比

### 传统流程

- PPT 手动调整,每页平均 12 分钟
- 改字号要重新对齐所有元素
- 设计依赖单一设计师

### slide-skill 流程

- Markdown 输入,2 秒生成完整 .pptx
- 主题切换瞬间完成,排版自动重算
- 设计、工程、AI 智能体共用同一份源

## 第一章 · 架构概览

## 渲染管道

- Markdown → 智能切片(LLM 可选)
- 切片 → SVG(主题驱动,完全确定性)
- SVG → 原生 DrawingML(渐变、形状、文字均可在 PowerPoint 内编辑)
- 全程 ~2 秒,零 API key 也能跑通

## 立即开始

- 安装:`pip install -e tools/slide`
- 快速体验:`slide-skill quickstart examples/sample.zh-CN.md --theme dark-tech`
- 切换主题:`--theme light-corporate / warm-editorial / data-forward / vibrant-startup`
- 反馈与共建:github.com/Yuuqq/slide-skill
