# slide-skill 模板目录 v3.1

> **80 个开箱即用模板,横跨 10 个使用场景。** 非设计师也能一行命令生成像样的 PPT:
> ```bash
> slide-skill templates                          # 看全部分类
> slide-skill templates --category business      # 看商业类下的 8 个模板
> slide-skill templates --show biz-mck-strategy  # 看某个模板的详细配方
> slide-skill template-quickstart biz-mck-strategy --title "我的战略复盘"
> ```

---

## 设计来源(吸收的技能)

本套模板的色彩 / 字体 / 反模式吸收自 `.agents/skills/` 下三套技能,**不重复造轮子**:

| 技能 | 吸收点 |
|---|---|
| **`pptx`** | 10 套命名色板(Midnight Executive、Coral Energy、Terracotta Warm 等)、8 套字体配对、反模式("不要在标题下加装饰横线"、"不要纯文字幻灯片"、"承诺一种视觉母题")|
| **`ui-ux-pro-max`** | 161 行 `colors.csv` + 74 行 `typography.csv` 中精选的产品配色(Indigo SaaS、Academic Royal、Sage Calm 等)|
| **`frontend-design`** | 设计哲学:"承诺一个明确的视觉方向,避免 AI slop";作为 Agent 写作时的总纲 |

未吸收(对一次性 CLI 不合适):`brainstorming`(9 步反复追问) / `web-design-guidelines`(只查 web 代码) / `pdf` / `browser-use`。

---

## 10 个分类 × 8 个模板 = 80

### 1. 商业咨询 / Consulting & Strategy (`business`)
| Slug | 中文名 | 主题 | 一句话用途 |
|---|---|---|---|
| `biz-mck-strategy`   | 麦肯锡战略复盘 | mckinsey-consulting | 三段式战略复盘:现状→路径→关键指标 |
| `biz-bcg-matrix`     | BCG 矩阵分析   | midnight-executive  | 产品组合 / 业务象限 2×2 框架        |
| `biz-quarterly`      | 季度业绩复盘   | data-forward        | 数据驱动的 QBR                       |
| `biz-ma-due`         | 并购尽调摘要   | midnight-executive  | 投行风格,财务+协同+风险             |
| `biz-board-update`   | 董事会更新     | charcoal-minimal    | 极简留白、信息密度优先               |
| `biz-market-entry`   | 市场进入策略   | ocean-deep          | 市场容量→竞争格局→切入路径          |
| `biz-transformation` | 数字化转型方案 | indigo-saas         | 传统企业转型路线图                   |
| `biz-cost-opt`       | 降本增效方案   | light-corporate     | 成本结构+优化机会+实施路径           |

### 2. 创业融资 / Startup & Pitch (`pitch`)
| Slug | 中文名 | 主题 | 一句话用途 |
|---|---|---|---|
| `pitch-seed`            | 种子轮路演    | indigo-saas         | 10 页种子轮经典 10 题框架            |
| `pitch-seriesa`         | A 轮融资      | ocean-deep          | 重 Traction + Unit Economics         |
| `pitch-demoday`         | Demo Day 路演 | vibrant-startup     | 5 分钟 Demo Day,故事+演示+Ask       |
| `pitch-vc-followup`     | VC 跟进材料   | light-corporate     | DD 阶段补充材料                      |
| `pitch-product-vision`  | 产品愿景 V1   | midnight-executive  | 面向 Founders / 早期员工的叙事       |
| `pitch-strategic`       | 战略投资人路演| midnight-executive  | 面向产业 / 战投,强调协同            |
| `pitch-grant`           | 政府项目申报  | academic-royal      | 政府专项 / 科研立项,结构严谨        |
| `pitch-acceleration`    | 加速器申请    | coral-energy        | YC / 加速器申请                      |

### 3. 产品发布 / Product Launch (`product`)
| Slug | 中文名 | 主题 | 一句话用途 |
|---|---|---|---|
| `prod-keynote`        | 苹果发布会风   | ocean-deep        | 极简留白 + 大字号舞台风                 |
| `prod-launch-b2b`     | B2B 产品上线   | indigo-saas       | 价值主张 + 集成方案                     |
| `prod-feature-update` | 功能更新摘要   | light-corporate   | Sprint / 月度功能发布                   |
| `prod-roadmap`        | 产品路线图     | data-forward      | 时间轴 + 优先级 + 北极星指标            |
| `prod-launch-c`       | 消费品发布     | coral-energy      | C 端发布会,情绪 + 颜值 + 价格          |
| `prod-app-launch`     | App 上线       | vibrant-startup   | 增长策略 + 渠道 + 留存目标              |
| `prod-ai-launch`      | AI 产品发布    | dark-tech         | 能力 + Benchmark + 安全                 |
| `prod-sunset`         | 旧版下线公告   | charcoal-minimal  | 迁移指南,口吻克制                      |

### 4. 内部复盘 / Internal Report (`report`)
| Slug | 中文名 | 主题 | 一句话用途 |
|---|---|---|---|
| `rep-weekly`           | 周报模板        | light-corporate   | 团队周报                       |
| `rep-monthly`          | 月度业务复盘    | data-forward      | 数据 + 洞察 + 行动项           |
| `rep-postmortem`       | 事故复盘 PM     | charcoal-minimal  | Blameless 事故复盘             |
| `rep-okr-review`       | OKR 季度回顾    | indigo-saas       | OKR 打分 + 学到什么            |
| `rep-budget`           | 预算执行报告    | midnight-executive| 财务月报 / 季报                |
| `rep-team-update`      | 团队季度更新    | sage-calm         | 团队向上汇报                   |
| `rep-customer-success` | 客户成功复盘    | coral-energy      | NPS + 续约 + 客户故事          |
| `rep-eng-update`       | 工程团队更新    | dark-tech         | 交付 + 稳定性 + 技术债务       |

### 5. 教学课件 / Education & Lecture (`education`)
| Slug | 中文名 | 主题 | 一句话用途 |
|---|---|---|---|
| `edu-lecture`  | 大学课程讲义 | academic-royal   | 高校课程单次讲义                |
| `edu-k12`      | 中小学课件   | vibrant-startup  | 图文并茂、节奏轻快              |
| `edu-flipped`  | 翻转课堂     | sage-calm        | 课前 + 课中 + 课后              |
| `edu-mooc`     | MOOC 课程    | indigo-saas      | 在线课程,重 Demo               |
| `edu-stem`     | 理工科推导   | data-forward     | 数学 / 物理 / CS 严谨推导       |
| `edu-language` | 语言学习     | warm-editorial   | 外语 / 古文 + 对照 + 语料       |
| `edu-history`  | 历史人文课件 | terracotta-warm  | 时间轴 + 史料 + 多元视角        |
| `edu-art`      | 艺术鉴赏     | berry-cream      | 作品赏析 + 技法对比             |

### 6. 学术汇报 / Academic & Research (`academic`)
| Slug | 中文名 | 主题 | 一句话用途 |
|---|---|---|---|
| `aca-thesis`               | 毕业论文答辩 | academic-royal     | 本硕博答辩 15-20 分钟        |
| `aca-conference`           | 学术会议报告 | academic-royal     | 顶会 / 期刊宣讲              |
| `aca-proposal`             | 开题报告     | midnight-executive | 硕博开题                     |
| `aca-paper-deepdive`       | 论文精读分享 | data-forward       | 组会 / Reading Group         |
| `aca-grant-final`          | 课题结题汇报 | midnight-executive | 国自然 / 省部级结题          |
| `aca-poster-presentation`  | Poster 宣讲  | academic-royal     | 3-5 分钟极致压缩信息         |
| `aca-lit-review`           | 文献综述     | warm-editorial     | 发展脉络 + 流派对比          |
| `aca-defense-prep`         | 答辩预演     | charcoal-minimal   | 答辩前自查                   |

### 7. 营销品牌 / Marketing & Brand (`marketing`)
| Slug | 中文名 | 主题 | 一句话用途 |
|---|---|---|---|
| `mkt-campaign`     | 整合营销方案     | coral-energy        | 洞察+创意+渠道+KPI         |
| `mkt-brand-deck`   | 品牌手册         | berry-cream         | 品牌识别 + 应用规范        |
| `mkt-launch`       | 新品上市方案     | coral-energy        | 新品 GTM 计划 4P           |
| `mkt-social`       | 社媒投放方案     | vibrant-startup     | 小红书 / 抖音 / 微博       |
| `mkt-event`        | 线下活动策划     | warm-editorial      | 发布 / 路演 / 展会方案     |
| `mkt-pr`           | 公关传播方案     | midnight-executive  | PR 危机 / 主动传播         |
| `mkt-content`      | 内容营销年度     | sage-calm           | 年度内容日历               |
| `mkt-sponsorship`  | 赞助 / 招商提案  | coral-energy        | 推介赞助权益               |

### 8. 政务汇报 / Government & Public (`government`)
| Slug | 中文名 | 主题 | 一句话用途 |
|---|---|---|---|
| `gov-work-report`     | 工作总结汇报 | gov-red             | 机关年度 / 半年度总结      |
| `gov-policy`          | 政策解读宣讲 | gov-red             | 背景 + 要点 + 影响 + 落实  |
| `gov-project`         | 项目立项申报 | academic-royal      | 财政 / 发改委立项          |
| `gov-poverty`         | 乡村振兴汇报 | forest-moss         | 帮扶工作汇报               |
| `gov-emergency`       | 应急处置汇报 | charcoal-minimal    | 突发事件应急               |
| `gov-twomeetings`     | 两会发言材料 | gov-red             | 代表 / 委员发言稿          |
| `gov-inspection`      | 巡视整改报告 | midnight-executive  | 整改进度 + 销号台账        |
| `gov-public-hearing`  | 公示听证材料 | warm-editorial      | 公示 / 听证                |

### 9. 技术分享 / Tech Talk (`tech`)
| Slug | 中文名 | 主题 | 一句话用途 |
|---|---|---|---|
| `tech-engall`        | 技术全员分享     | dark-tech         | 工程团队全员会             |
| `tech-architecture`  | 架构评审         | ocean-deep        | ARC 评审会                 |
| `tech-rfc`           | RFC 提案         | charcoal-minimal  | 工程 RFC 走查              |
| `tech-conf-talk`     | 技术大会演讲     | ocean-deep        | QCon / KubeCon 风格        |
| `tech-deepdive`      | 技术深度分享     | dark-tech         | 团队 brown-bag             |
| `tech-postmortem`    | 故障复盘技术版   | charcoal-minimal  | SRE / DevOps 故障复盘      |
| `tech-launch`        | 中间件 / 平台发布| indigo-saas       | 内部 SDK / API 发布        |
| `tech-ai-research`   | AI 研究分享      | dark-tech         | LLM / 模型研究进展         |

### 10. 培训讲座 / Training & Workshop (`training`)
| Slug | 中文名 | 主题 | 一句话用途 |
|---|---|---|---|
| `trn-onboarding`      | 新员工入职培训 | sage-calm           | 新人入职第一课             |
| `trn-workshop`        | 工作坊         | vibrant-startup     | 理论+演示+动手+复盘        |
| `trn-leadership`      | 管理力培训     | midnight-executive  | 中高层管理力               |
| `trn-sales`           | 销售技能培训   | coral-energy        | 销售方法论 + 话术          |
| `trn-compliance`      | 合规 / 安全培训| light-corporate     | 信息安全 / 合规年度        |
| `trn-product`         | 产品培训       | indigo-saas         | 销售 / CS 产品培训         |
| `trn-tech-bootcamp`   | 技术训练营     | dark-tech           | 新工程师集中训练营         |
| `trn-public-speaking` | 演讲与表达培训 | berry-cream         | 演讲技巧 / 商务表达        |

---

## 主题(色板)清单

v3.1 共 22 个内置主题。新增 10 个(吸收自 `pptx` + `ui-ux-pro-max`):

| 主题名 | 主色 | 来源 | 适合 |
|---|---|---|---|
| `midnight-executive` | `#1E2761` 深海军蓝 | pptx skill | 董事会 / 投行 / 战略 |
| `forest-moss`        | `#2C5F2D` 森林绿   | pptx skill | 可持续 / 乡村振兴 |
| `coral-energy`       | `#F96167` 珊瑚红   | pptx skill | 营销 / 招商 / 活动 |
| `terracotta-warm`    | `#B85042` 赤陶    | pptx skill | 编辑 / 文化 / 历史 |
| `ocean-deep`         | `#1C7293` 深海青  | pptx skill | 高端发布会 / 架构 |
| `charcoal-minimal`   | `#36454F` 炭灰    | pptx skill | 设计感强 / 极简 |
| `berry-cream`        | `#6D2E46` 莓紫    | pptx skill | 创意 / 个人 / 演讲 |
| `sage-calm`          | `#69A297` 鼠尾草绿| pptx skill | 健康 / 培训 |
| `academic-royal`     | `#4B0082` 学术紫  | ui-ux-pro-max | 答辩 / 论文 / 立项 |
| `indigo-saas`        | `#6366F1` 靛蓝    | ui-ux-pro-max | SaaS / 产品 / Pitch |

加上原 12 个(`dark-tech`, `light-corporate`, `warm-editorial`, `data-forward`,
`vibrant-startup`, `mckinsey-consulting`, `gov-red`, ...),共 **22 个主题**,
80 个模板可任意搭配。

---

## 一致遵守的反模式(吸收自 pptx skill)

每个模板内置以下硬规则,SVG 渲染器(`svg_pipeline.py`)在生成时会自动遵守:

1. **绝不**在标题下方画装饰横线 — 那是 AI 味的标志
2. **绝不**生成纯文字幻灯片 — 必有图标 / 图表 / 形状 / 色块
3. 一种主色占据 60-70% 视觉权重,1-2 个支撑色,1 个尖锐强调色
4. 标题 36-44pt,正文 14-16pt,字号差距明显才有层级
5. 每页留至少 0.5" 边距,内容块之间 0.3-0.5" 一致间隔
6. 正文左对齐,只有标题居中
