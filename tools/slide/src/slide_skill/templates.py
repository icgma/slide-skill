
"""Named slide templates — 10 categories × 8 templates = 80 presets.

A *template* is a ready-to-use combination of:
    - a visual `theme` (from `themes.BUILTIN_THEMES`)
    - recommended layout primitives (cover / executive-summary / process-flow
      / comparison / quote-block / metric-highlight / bullet-list / closing)
    - a sample 6-slide markdown outline that demonstrates the layouts

Templates make the CLI approachable for non-designers: instead of picking a
theme and writing perfect markdown, the user runs

    slide-skill templates --category business
    slide-skill quickstart biz-mck-strategy --title "我的战略复盘"

and gets a deck that already looks production-grade.

Categories cover the 10 most common Chinese-language deck use cases:

    business / pitch / product / report / education / academic /
    marketing / government / tech / training

Inspired by:
    - hugohe3/ppt-master example library
    - the `pptx` agent skill (color palettes, font pairings, anti-patterns)
    - the `ui-ux-pro-max` skill (color/typography CSV libraries)
    - the `frontend-design` skill ("commit to a bold direction")

Phase v3.1.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Iterable


CATEGORIES: dict[str, str] = {
    "business":   "商业咨询 / Consulting & Strategy",
    "pitch":      "创业融资 / Startup & Pitch",
    "product":    "产品发布 / Product Launch",
    "report":     "内部复盘 / Internal Report",
    "education":  "教学课件 / Education & Lecture",
    "academic":   "学术汇报 / Academic & Research",
    "marketing":  "营销品牌 / Marketing & Brand",
    "government": "政务汇报 / Government & Public",
    "tech":       "技术分享 / Tech Talk",
    "training":   "培训讲座 / Training & Workshop",
}


@dataclass(frozen=True)
class TemplateSpec:
    """A named template binding a theme + layout pattern + sample outline."""

    slug: str
    category: str
    name_zh: str
    name_en: str
    theme: str
    layouts: list[str]
    persona: str
    outline: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def category_label(self) -> str:
        return CATEGORIES.get(self.category, self.category)


def _t(
    slug: str, category: str, name_zh: str, name_en: str,
    theme: str, layouts: list[str], persona: str, outline: list[str],
) -> TemplateSpec:
    return TemplateSpec(
        slug=slug, category=category,
        name_zh=name_zh, name_en=name_en,
        theme=theme, layouts=layouts,
        persona=persona, outline=outline,
    )


# ---------------------------------------------------------------------------
# 1. BUSINESS — 商业咨询 / Consulting & Strategy
# ---------------------------------------------------------------------------
_BUSINESS = [
    _t("biz-mck-strategy", "business", "麦肯锡战略复盘", "McKinsey Strategy Review",
       "mckinsey-consulting",
       ["cover", "executive-summary", "comparison", "process-flow", "metric-highlight", "closing"],
       "三段式战略复盘：现状 → 路径 → 关键指标。",
       ["核心结论", "三大主线 vs 现状", "战略落地路径", "关键指标 OKR", "风险与对冲", "结语"]),
    _t("biz-bcg-matrix", "business", "BCG 矩阵分析", "BCG Matrix Analysis",
       "midnight-executive",
       ["cover", "comparison", "metric-highlight", "process-flow", "executive-summary", "closing"],
       "适合产品组合 / 业务象限分析，2×2 思维框架贯穿全文。",
       ["明星 vs 现金牛", "问题 vs 瘦狗象限", "象限关键指标", "迁移路径", "三条建议", "总结"]),
    _t("biz-quarterly", "business", "季度业绩复盘", "Quarterly Business Review",
       "data-forward",
       ["cover", "metric-highlight", "executive-summary", "comparison", "process-flow", "closing"],
       "数据驱动的 QBR：营收、毛利、留存全景透视。",
       ["核心指标", "三大增长引擎", "目标 vs 实际", "下季度路径", "风险预警", "结束"]),
    _t("biz-ma-due", "business", "并购尽调摘要", "M&A Due Diligence",
       "midnight-executive",
       ["cover", "executive-summary", "comparison", "metric-highlight", "quote-block", "closing"],
       "投行风格尽调摘要，财务 + 战略协同 + 风险三段。",
       ["交易摘要", "标的 vs 同业对比", "财务关键指标", "战略协同", "管理层访谈", "建议结论"]),
    _t("biz-board-update", "business", "董事会更新", "Board Update Deck",
       "charcoal-minimal",
       ["cover", "executive-summary", "metric-highlight", "process-flow", "bullet-list", "closing"],
       "董事会例会用，极简留白、信息密度优先。",
       ["三句话总结", "财务总览", "本季关键事件", "下季计划", "议程外讨论", "Q&A"]),
    _t("biz-market-entry", "business", "市场进入策略", "Market Entry Strategy",
       "ocean-deep",
       ["cover", "executive-summary", "comparison", "process-flow", "metric-highlight", "closing"],
       "新市场进入分析：市场容量 → 竞争格局 → 切入路径。",
       ["市场机会", "本地玩家 vs 海外玩家", "进入路径选择", "里程碑", "投入产出", "结语"]),
    _t("biz-transformation", "business", "数字化转型方案", "Digital Transformation",
       "indigo-saas",
       ["cover", "executive-summary", "process-flow", "comparison", "metric-highlight", "closing"],
       "传统企业数字化转型路线图，分阶段落地。",
       ["现状诊断", "三阶段路线图", "传统 vs 数字化对比", "投入产出", "组织保障", "下一步"]),
    _t("biz-cost-opt", "business", "降本增效方案", "Cost Optimization",
       "light-corporate",
       ["cover", "metric-highlight", "comparison", "process-flow", "bullet-list", "closing"],
       "成本结构分析 + 优化机会清单 + 实施路径。",
       ["成本现状", "可优化项 vs 不可动项", "优化优先级", "三阶段实施", "预期收益", "总结"]),
]

# ---------------------------------------------------------------------------
# 2. PITCH — 创业融资 / Startup & Pitch
# ---------------------------------------------------------------------------
_PITCH = [
    _t("pitch-seed", "pitch", "种子轮路演", "Seed Round Pitch",
       "indigo-saas",
       ["cover", "quote-block", "executive-summary", "metric-highlight", "process-flow", "closing"],
       "10 页种子轮经典框架：问题 - 解决 - 市场 - 团队 - Ask。",
       ["问题", "我们的洞察", "解决方案", "市场规模", "Traction 数据", "融资 Ask"]),
    _t("pitch-seriesa", "pitch", "A 轮融资", "Series A Deck",
       "ocean-deep",
       ["cover", "metric-highlight", "executive-summary", "process-flow", "comparison", "closing"],
       "重 Traction 与 Unit Economics，证明 PMF + 可规模化。",
       ["核心指标", "增长曲线", "PMF 信号", "扩张路径", "团队 vs 同业", "融资计划"]),
    _t("pitch-demoday", "pitch", "Demo Day 路演", "Demo Day Pitch",
       "vibrant-startup",
       ["cover", "quote-block", "metric-highlight", "process-flow", "executive-summary", "closing"],
       "5 分钟 Demo Day：故事 + 演示 + Ask，节奏强烈。",
       ["一句话定位", "用户故事", "现场演示", "三大数据", "下一步", "联系方式"]),
    _t("pitch-vc-followup", "pitch", "VC 跟进材料", "VC Follow-up Memo",
       "light-corporate",
       ["cover", "executive-summary", "metric-highlight", "comparison", "bullet-list", "closing"],
       "投后跟进 / DD 阶段补充材料，更详细的数据陈述。",
       ["问题与机会", "本月关键进展", "竞争格局", "下季度计划", "风险与缓解", "附录指引"]),
    _t("pitch-product-vision", "pitch", "产品愿景 V1", "Product Vision Pitch",
       "midnight-executive",
       ["cover", "quote-block", "executive-summary", "process-flow", "metric-highlight", "closing"],
       "面向 Founders / 早期员工的愿景陈述，重叙事。",
       ["十年后的世界", "今天的痛点", "我们的方案", "三阶段路径", "TAM 估算", "加入我们"]),
    _t("pitch-strategic", "pitch", "战略投资人路演", "Strategic Investor Pitch",
       "midnight-executive",
       ["cover", "executive-summary", "comparison", "metric-highlight", "process-flow", "closing"],
       "面向产业 / 战投，强调协同价值与生态卡位。",
       ["公司定位", "我们 vs 现有玩家", "协同点", "数据指标", "合作蓝图", "Ask"]),
    _t("pitch-grant", "pitch", "政府项目申报", "Grant / Subsidy Application",
       "academic-royal",
       ["cover", "executive-summary", "process-flow", "metric-highlight", "bullet-list", "closing"],
       "政府专项 / 科研立项，结构严谨、数据扎实。",
       ["项目背景", "技术路线", "实施方案", "预期成果", "团队配置", "经费预算"]),
    _t("pitch-acceleration", "pitch", "加速器申请", "Accelerator Application",
       "coral-energy",
       ["cover", "quote-block", "executive-summary", "metric-highlight", "process-flow", "closing"],
       "YC / 加速器申请：洞察 + 团队 + 牵引力。",
       ["创始人故事", "我们的洞察", "团队构成", "本月数据", "三个月计划", "为什么是我们"]),
]

# ---------------------------------------------------------------------------
# 3. PRODUCT — 产品发布 / Product Launch
# ---------------------------------------------------------------------------
_PRODUCT = [
    _t("prod-keynote", "product", "苹果发布会风", "Apple Keynote Style",
       "ocean-deep",
       ["cover", "quote-block", "metric-highlight", "comparison", "process-flow", "closing"],
       "极简留白 + 大字号 + 一图一字，发布会舞台风格。",
       ["全新一代", "重新定义", "核心数据", "新 vs 旧", "三大体验", "今天上市"]),
    _t("prod-launch-b2b", "product", "B2B 产品上线", "B2B Product Launch",
       "indigo-saas",
       ["cover", "executive-summary", "comparison", "process-flow", "metric-highlight", "closing"],
       "面向企业客户的产品发布，价值主张 + 集成方案。",
       ["产品定位", "三大核心价值", "新版 vs 旧版", "集成路径", "首批客户成绩", "下一步"]),
    _t("prod-feature-update", "product", "功能更新摘要", "Feature Release Notes",
       "light-corporate",
       ["cover", "executive-summary", "bullet-list", "metric-highlight", "process-flow", "closing"],
       "Sprint / 月度功能发布，给客户成功 / 销售用。",
       ["本月亮点", "三大新功能", "性能提升数据", "迁移指引", "已知问题", "反馈渠道"]),
    _t("prod-roadmap", "product", "产品路线图", "Product Roadmap",
       "data-forward",
       ["cover", "process-flow", "executive-summary", "comparison", "metric-highlight", "closing"],
       "季度 / 半年路线图，时间轴 + 优先级 + 北极星指标。",
       ["北极星指标", "Q1 - Q4 路径", "已交付 vs 待交付", "里程碑", "依赖与风险", "团队对齐"]),
    _t("prod-launch-c", "product", "消费品发布", "Consumer Product Launch",
       "coral-energy",
       ["cover", "quote-block", "metric-highlight", "comparison", "process-flow", "closing"],
       "面向 C 端用户的发布会，情绪 + 颜值 + 价格惊喜。",
       ["品牌主张", "用户痛点", "核心卖点", "新品 vs 老款", "上市节奏", "首发福利"]),
    _t("prod-app-launch", "product", "App 上线", "Mobile App Launch",
       "vibrant-startup",
       ["cover", "executive-summary", "process-flow", "metric-highlight", "comparison", "closing"],
       "App 上线日：增长策略 + 渠道 + 留存目标。",
       ["产品摘要", "目标用户", "增长漏斗", "渠道矩阵", "竞品对比", "30 天目标"]),
    _t("prod-ai-launch", "product", "AI 产品发布", "AI Product Launch",
       "dark-tech",
       ["cover", "quote-block", "metric-highlight", "process-flow", "comparison", "closing"],
       "AI / LLM 产品发布：能力 + Benchmark + 安全。",
       ["产品概览", "我们的赌注", "Benchmark 数据", "工作流", "vs 现有方案", "上线计划"]),
    _t("prod-sunset", "product", "旧版下线公告", "Product Sunset Notice",
       "charcoal-minimal",
       ["cover", "executive-summary", "process-flow", "comparison", "bullet-list", "closing"],
       "宣告旧版本停止支持的迁移指南，结构清晰、口吻克制。",
       ["停服公告", "时间表", "新版 vs 旧版", "迁移步骤", "FAQ", "联系支持"]),
]

# ---------------------------------------------------------------------------
# 4. REPORT — 内部复盘 / Internal Report
# ---------------------------------------------------------------------------
_REPORT = [
    _t("rep-weekly", "report", "周报模板", "Weekly Status",
       "light-corporate",
       ["cover", "executive-summary", "bullet-list", "metric-highlight", "process-flow", "closing"],
       "团队周报：本周完成 / 下周计划 / 风险阻塞。",
       ["本周三件事", "关键指标", "已完成事项", "下周计划", "风险阻塞", "求助清单"]),
    _t("rep-monthly", "report", "月度业务复盘", "Monthly Business Review",
       "data-forward",
       ["cover", "metric-highlight", "executive-summary", "comparison", "process-flow", "closing"],
       "月度业务复盘，数据 + 洞察 + 行动项。",
       ["北极星指标", "本月 vs 上月", "三大洞察", "行动项", "风险预警", "下月重点"]),
    _t("rep-postmortem", "report", "事故复盘 Postmortem", "Incident Postmortem",
       "charcoal-minimal",
       ["cover", "executive-summary", "process-flow", "metric-highlight", "bullet-list", "closing"],
       "Blameless 事故复盘：时间线 + 根因 + 改进项。",
       ["事件摘要", "影响范围", "时间线", "根因分析", "已采取行动", "长期改进"]),
    _t("rep-okr-review", "report", "OKR 季度回顾", "OKR Quarterly Review",
       "indigo-saas",
       ["cover", "metric-highlight", "executive-summary", "comparison", "bullet-list", "closing"],
       "OKR 打分 + 学到什么 + 下季度对齐。",
       ["上季度评分", "三个 O 完成度", "关键 KR 数据", "学到什么", "下季 OKR", "对齐声明"]),
    _t("rep-budget", "report", "预算执行报告", "Budget Execution Report",
       "midnight-executive",
       ["cover", "metric-highlight", "comparison", "executive-summary", "process-flow", "closing"],
       "财务月报 / 季报：预算 vs 实际 + 差异分析。",
       ["总览", "预算 vs 实际", "三大差异", "原因分析", "调整建议", "下期预测"]),
    _t("rep-team-update", "report", "团队季度更新", "Team Quarterly Update",
       "sage-calm",
       ["cover", "executive-summary", "bullet-list", "process-flow", "metric-highlight", "closing"],
       "团队向上汇报 / 部门同步：人员、项目、文化。",
       ["团队概况", "本季度交付", "关键项目", "团队文化", "下季度计划", "支持需求"]),
    _t("rep-customer-success", "report", "客户成功复盘", "Customer Success Review",
       "coral-energy",
       ["cover", "metric-highlight", "executive-summary", "quote-block", "process-flow", "closing"],
       "CS 季度复盘：NPS + 续约 + 客户故事。",
       ["客户健康度", "续约 / 流失", "NPS 与反馈", "客户故事", "改进行动", "下季重点"]),
    _t("rep-eng-update", "report", "工程团队更新", "Engineering Update",
       "dark-tech",
       ["cover", "metric-highlight", "executive-summary", "process-flow", "bullet-list", "closing"],
       "工程团队向上汇报：交付 + 稳定性 + 技术债务。",
       ["核心指标", "交付情况", "可用性 / SLO", "技术决策", "技术债务", "下季计划"]),
]

# ---------------------------------------------------------------------------
# 5. EDUCATION — 教学课件 / Education & Lecture
# ---------------------------------------------------------------------------
_EDUCATION = [
    _t("edu-lecture", "education", "大学课程讲义", "University Lecture",
       "academic-royal",
       ["cover", "executive-summary", "process-flow", "comparison", "bullet-list", "closing"],
       "高校课程单次讲义：纲要 + 知识点 + 例题 + 总结。",
       ["本节目标", "知识点纲要", "推导过程", "经典例题", "课后练习", "本节小结"]),
    _t("edu-k12", "education", "中小学课件", "K-12 Class Slide",
       "vibrant-startup",
       ["cover", "executive-summary", "bullet-list", "metric-highlight", "process-flow", "closing"],
       "中小学课堂：图文并茂、节奏轻快、互动提问。",
       ["导入提问", "今日主题", "三个知识点", "趣味实例", "课堂互动", "回家任务"]),
    _t("edu-flipped", "education", "翻转课堂", "Flipped Classroom",
       "sage-calm",
       ["cover", "executive-summary", "process-flow", "comparison", "bullet-list", "closing"],
       "翻转教学：课前预习 + 课中讨论 + 课后任务。",
       ["课前任务回顾", "本节主题", "讨论问题", "概念对比", "小组活动", "课后延伸"]),
    _t("edu-mooc", "education", "MOOC 课程模板", "MOOC Lecture",
       "indigo-saas",
       ["cover", "executive-summary", "metric-highlight", "process-flow", "comparison", "closing"],
       "在线课程：节奏快、要点突出、配 demo / 视频引导。",
       ["欢迎语", "本课目标", "三个核心概念", "动手 demo", "对比辨析", "本节作业"]),
    _t("edu-stem", "education", "理工科推导", "STEM Derivation",
       "data-forward",
       ["cover", "executive-summary", "process-flow", "comparison", "metric-highlight", "closing"],
       "数学 / 物理 / CS 推导课件，结构严谨、公式清晰。",
       ["问题陈述", "已知与求解", "推导过程", "等价变形", "数值验证", "结论与延伸"]),
    _t("edu-language", "education", "语言学习", "Language Learning",
       "warm-editorial",
       ["cover", "executive-summary", "comparison", "quote-block", "bullet-list", "closing"],
       "外语 / 古文教学：场景 + 对照 + 语料 + 练习。",
       ["本课主题", "新词与短语", "原文 vs 翻译", "经典例句", "口语练习", "本节作业"]),
    _t("edu-history", "education", "历史人文课件", "Humanities Lecture",
       "terracotta-warm",
       ["cover", "executive-summary", "quote-block", "process-flow", "comparison", "closing"],
       "历史 / 人文：时间轴 + 史料引用 + 多元视角。",
       ["时代背景", "关键人物", "重要史料", "事件时间轴", "历史评价", "延伸阅读"]),
    _t("edu-art", "education", "艺术鉴赏", "Art Appreciation",
       "berry-cream",
       ["cover", "quote-block", "executive-summary", "comparison", "bullet-list", "closing"],
       "艺术 / 美学课件：作品赏析 + 技法对比 + 名家点评。",
       ["作品介绍", "时代背景", "美学评价", "古典 vs 现代", "技法要点", "推荐欣赏"]),
]

# ---------------------------------------------------------------------------
# 6. ACADEMIC — 学术汇报 / Academic & Research
# ---------------------------------------------------------------------------
_ACADEMIC = [
    _t("aca-thesis", "academic", "毕业论文答辩", "Thesis Defense",
       "academic-royal",
       ["cover", "executive-summary", "process-flow", "comparison", "metric-highlight", "closing"],
       "本硕博答辩：选题 + 方法 + 创新 + 不足，时长 15-20 分钟。",
       ["选题背景", "研究问题", "方法与数据", "核心创新点", "实验结果", "不足与展望"]),
    _t("aca-conference", "academic", "学术会议报告", "Conference Presentation",
       "academic-royal",
       ["cover", "executive-summary", "process-flow", "metric-highlight", "comparison", "closing"],
       "顶会 / 期刊宣讲：贡献 + 方法 + 实验 + 与基线对比。",
       ["研究动机", "核心贡献", "方法概述", "实验设置", "vs SOTA", "未来工作"]),
    _t("aca-proposal", "academic", "开题报告", "Research Proposal",
       "midnight-executive",
       ["cover", "executive-summary", "comparison", "process-flow", "bullet-list", "closing"],
       "硕博开题：研究意义 + 现状 + 创新 + 计划。",
       ["选题意义", "国内外现状", "拟解决问题", "技术路线", "时间安排", "预期成果"]),
    _t("aca-paper-deepdive", "academic", "论文精读分享", "Paper Deep-Dive",
       "data-forward",
       ["cover", "executive-summary", "process-flow", "comparison", "metric-highlight", "closing"],
       "组会 / Reading Group：论文要点 + 实验 + 评价。",
       ["论文摘要", "核心思路", "方法细节", "实验结果", "vs 同类工作", "我们的看法"]),
    _t("aca-grant-final", "academic", "课题结题汇报", "Grant Closeout",
       "midnight-executive",
       ["cover", "executive-summary", "process-flow", "metric-highlight", "bullet-list", "closing"],
       "国自然 / 省部级课题结题：成果清单 + 经费 + 论文。",
       ["课题概述", "工作量完成", "标志性成果", "论文与专利", "经费使用", "后续展望"]),
    _t("aca-poster-presentation", "academic", "Poster 现场宣讲", "Poster Talk",
       "academic-royal",
       ["cover", "executive-summary", "metric-highlight", "process-flow", "comparison", "closing"],
       "Poster 答辩 / 短报告，3-5 分钟极致压缩信息。",
       ["一句话贡献", "问题与动机", "核心方法", "关键结果", "vs 基线", "联系我"]),
    _t("aca-lit-review", "academic", "文献综述", "Literature Review",
       "warm-editorial",
       ["cover", "executive-summary", "process-flow", "comparison", "bullet-list", "closing"],
       "综述报告：发展脉络 + 流派对比 + 空白点。",
       ["综述范围", "发展时间线", "主要流派", "代表性方法对比", "研究空白", "未来方向"]),
    _t("aca-defense-prep", "academic", "答辩预演", "Defense Rehearsal",
       "charcoal-minimal",
       ["cover", "executive-summary", "comparison", "process-flow", "bullet-list", "closing"],
       "答辩前自查 / 预演：可能被问的问题 + 应对。",
       ["论文摘要", "评委可能问题", "薄弱点应对", "演讲节奏", "时间分配", "心态调整"]),
]

# ---------------------------------------------------------------------------
# 7. MARKETING — 营销品牌 / Marketing & Brand
# ---------------------------------------------------------------------------
_MARKETING = [
    _t("mkt-campaign", "marketing", "整合营销方案", "Integrated Campaign",
       "coral-energy",
       ["cover", "executive-summary", "process-flow", "comparison", "metric-highlight", "closing"],
       "整合营销提案：洞察 + 创意 + 渠道 + 数据 KPI。",
       ["市场洞察", "策略主张", "创意核心", "渠道矩阵", "投入预算", "效果预测"]),
    _t("mkt-brand-deck", "marketing", "品牌手册", "Brand Guidelines",
       "berry-cream",
       ["cover", "quote-block", "executive-summary", "comparison", "bullet-list", "closing"],
       "品牌识别 + 应用规范，给设计 / 公关参考。",
       ["品牌主张", "Logo 用法", "色彩与字体", "应用对比", "禁用案例", "联系品牌组"]),
    _t("mkt-launch", "marketing", "新品上市方案", "Product Launch Plan",
       "coral-energy",
       ["cover", "executive-summary", "process-flow", "metric-highlight", "comparison", "closing"],
       "新品 GTM 计划：产品 + 价格 + 渠道 + 推广四 P。",
       ["产品摘要", "目标人群", "上市节奏", "渠道与售点", "预期 ROI", "团队分工"]),
    _t("mkt-social", "marketing", "社媒投放方案", "Social Media Plan",
       "vibrant-startup",
       ["cover", "executive-summary", "metric-highlight", "comparison", "process-flow", "closing"],
       "小红书 / 抖音 / 微博三平台投放打法。",
       ["平台策略", "KOL vs KOC", "三大爆款思路", "投放数据", "节奏排期", "效果指标"]),
    _t("mkt-event", "marketing", "线下活动策划", "Event Plan",
       "warm-editorial",
       ["cover", "executive-summary", "process-flow", "comparison", "metric-highlight", "closing"],
       "线下发布 / 路演 / 展会方案，重流程与体验。",
       ["活动目标", "嘉宾与议程", "现场流程", "与去年活动对比", "预算 ROI", "应急预案"]),
    _t("mkt-pr", "marketing", "公关传播方案", "PR Strategy",
       "midnight-executive",
       ["cover", "executive-summary", "quote-block", "process-flow", "bullet-list", "closing"],
       "PR 危机 / 主动传播：信息纲领 + 媒体矩阵 + 口径。",
       ["传播目标", "核心信息", "意见领袖", "传播节奏", "口径模板", "效果评估"]),
    _t("mkt-content", "marketing", "内容营销年度", "Content Marketing Plan",
       "sage-calm",
       ["cover", "executive-summary", "process-flow", "metric-highlight", "comparison", "closing"],
       "年度内容日历 + 选题策略 + 数据指标。",
       ["内容主张", "四季选题", "渠道分布", "数据目标", "今年 vs 去年", "团队配置"]),
    _t("mkt-sponsorship", "marketing", "赞助 / 招商提案", "Sponsorship Proposal",
       "coral-energy",
       ["cover", "executive-summary", "metric-highlight", "comparison", "process-flow", "closing"],
       "向品牌方推介赞助权益，价值主张 + 数据 + 套餐。",
       ["项目概览", "受众画像", "三大价值", "权益对比", "成功案例", "联系方式"]),
]

# ---------------------------------------------------------------------------
# 8. GOVERNMENT — 政务汇报 / Government & Public
# ---------------------------------------------------------------------------
_GOV = [
    _t("gov-work-report", "government", "工作总结汇报", "Government Work Report",
       "gov-red",
       ["cover", "executive-summary", "process-flow", "metric-highlight", "bullet-list", "closing"],
       "机关年度 / 半年度工作总结，结构对仗、口吻庄重。",
       ["指导思想", "主要成绩", "关键数据", "经验做法", "存在问题", "下阶段安排"]),
    _t("gov-policy", "government", "政策解读宣讲", "Policy Briefing",
       "gov-red",
       ["cover", "executive-summary", "process-flow", "comparison", "bullet-list", "closing"],
       "政策文件解读：背景 + 要点 + 影响 + 落实。",
       ["政策背景", "出台依据", "三大要点", "新旧政策对比", "落实路径", "答疑"]),
    _t("gov-project", "government", "项目立项申报", "Project Proposal (Gov)",
       "academic-royal",
       ["cover", "executive-summary", "process-flow", "metric-highlight", "bullet-list", "closing"],
       "财政 / 发改委项目立项：必要性 + 方案 + 预算。",
       ["立项背景", "项目目标", "建设方案", "投资预算", "效益分析", "实施保障"]),
    _t("gov-poverty", "government", "乡村振兴汇报", "Rural Revitalization",
       "forest-moss",
       ["cover", "executive-summary", "metric-highlight", "process-flow", "quote-block", "closing"],
       "乡村振兴 / 帮扶工作汇报：成果 + 案例 + 群众声音。",
       ["工作概览", "脱贫数据", "产业带动", "走访故事", "下阶段规划", "结语"]),
    _t("gov-emergency", "government", "应急处置汇报", "Emergency Response",
       "charcoal-minimal",
       ["cover", "executive-summary", "process-flow", "metric-highlight", "bullet-list", "closing"],
       "突发事件应急处置汇报：时序 + 数据 + 改进。",
       ["事件经过", "处置时序", "影响数据", "已采取措施", "经验教训", "下一步"]),
    _t("gov-twomeetings", "government", "两会发言材料", "Two-Sessions Speech",
       "gov-red",
       ["cover", "quote-block", "executive-summary", "process-flow", "bullet-list", "closing"],
       "代表 / 委员发言稿配套幻灯片，重金句、重数据。",
       ["开场致敬", "调研发现", "三点建议", "数据支撑", "落地路径", "结束语"]),
    _t("gov-inspection", "government", "巡视整改报告", "Inspection Rectification",
       "midnight-executive",
       ["cover", "executive-summary", "process-flow", "comparison", "bullet-list", "closing"],
       "巡视反馈整改：问题清单 + 整改进度 + 销号台账。",
       ["反馈要点", "整改总览", "前后对比", "已销号问题", "未完成事项", "长效机制"]),
    _t("gov-public-hearing", "government", "公示听证材料", "Public Hearing",
       "warm-editorial",
       ["cover", "executive-summary", "comparison", "process-flow", "quote-block", "closing"],
       "公示 / 听证会材料，向公众透明展示方案与影响。",
       ["事项说明", "方案要点", "现状 vs 改造后", "实施步骤", "民意反馈", "意见征集"]),
]

# ---------------------------------------------------------------------------
# 9. TECH — 技术分享 / Tech Talk
# ---------------------------------------------------------------------------
_TECH = [
    _t("tech-engall", "tech", "技术全员分享", "Eng All-Hands",
       "dark-tech",
       ["cover", "metric-highlight", "executive-summary", "process-flow", "comparison", "closing"],
       "工程团队全员会：架构变迁 + 数据 + 路线图。",
       ["架构现状", "关键指标", "本季交付", "技术决策", "新旧架构对比", "下季路径"]),
    _t("tech-architecture", "tech", "架构评审", "Architecture Review",
       "ocean-deep",
       ["cover", "executive-summary", "comparison", "process-flow", "metric-highlight", "closing"],
       "ARC / 架构评审会：方案 + 备选 + 决策。",
       ["问题域", "方案 A vs B", "选型理由", "实施路径", "风险与缓解", "决策结论"]),
    _t("tech-rfc", "tech", "RFC 提案", "Engineering RFC",
       "charcoal-minimal",
       ["cover", "executive-summary", "comparison", "process-flow", "bullet-list", "closing"],
       "工程 RFC 走查会：动机 + 设计 + 备选 + 反馈。",
       ["背景动机", "目标 / 非目标", "设计概要", "备选方案", "未决问题", "反馈征集"]),
    _t("tech-conf-talk", "tech", "技术大会演讲", "Conference Tech Talk",
       "ocean-deep",
       ["cover", "quote-block", "metric-highlight", "process-flow", "comparison", "closing"],
       "QCon / KubeCon 风格技术演讲，故事 + 干货 + Demo。",
       ["演讲主题", "我们的痛点", "核心数据", "解决思路", "vs 其他方案", "经验沉淀"]),
    _t("tech-deepdive", "tech", "技术深度分享", "Tech Deep-Dive",
       "dark-tech",
       ["cover", "executive-summary", "process-flow", "comparison", "metric-highlight", "closing"],
       "团队内 brown-bag：源码级 / 系统级深度讲解。",
       ["主题概览", "核心概念", "实现细节", "性能数据", "对比同类", "Q&A"]),
    _t("tech-postmortem", "tech", "故障复盘技术版", "SRE Postmortem",
       "charcoal-minimal",
       ["cover", "executive-summary", "process-flow", "metric-highlight", "bullet-list", "closing"],
       "SRE / DevOps 故障复盘，时间线 + RCA + Action Items。",
       ["事故概述", "影响数据", "时间线", "根因分析", "改进项", "长期方向"]),
    _t("tech-launch", "tech", "中间件 / 平台发布", "Platform Launch",
       "indigo-saas",
       ["cover", "executive-summary", "metric-highlight", "process-flow", "comparison", "closing"],
       "面向内部用户的平台 / SDK / API 发布。",
       ["平台简介", "核心能力", "性能数据", "接入指引", "新版 vs 旧版", "迁移支持"]),
    _t("tech-ai-research", "tech", "AI 研究分享", "AI Research Update",
       "dark-tech",
       ["cover", "executive-summary", "process-flow", "comparison", "metric-highlight", "closing"],
       "LLM / 模型研究进展：思路 + Benchmark + 后续。",
       ["研究问题", "方法概述", "训练流程", "vs Baseline", "Benchmark 数据", "未来工作"]),
]

# ---------------------------------------------------------------------------
# 10. TRAINING — 培训讲座 / Training & Workshop
# ---------------------------------------------------------------------------
_TRAINING = [
    _t("trn-onboarding", "training", "新员工入职培训", "New-Hire Onboarding",
       "sage-calm",
       ["cover", "executive-summary", "process-flow", "comparison", "bullet-list", "closing"],
       "新人入职第一课：公司 / 团队 / 工具 / 文化。",
       ["欢迎你", "公司概览", "团队结构", "常用工具", "工作 vs 文化", "联系人"]),
    _t("trn-workshop", "training", "工作坊", "Hands-on Workshop",
       "vibrant-startup",
       ["cover", "executive-summary", "process-flow", "comparison", "bullet-list", "closing"],
       "工作坊节奏：理论 + 演示 + 动手 + 复盘。",
       ["工作坊目标", "理论速览", "演示步骤", "动手任务", "对照检查清单", "复盘讨论"]),
    _t("trn-leadership", "training", "管理力培训", "Leadership Training",
       "midnight-executive",
       ["cover", "quote-block", "executive-summary", "process-flow", "comparison", "closing"],
       "中高层管理力 / 教练式领导力培训。",
       ["开场金句", "核心理念", "三大行为", "高效 vs 低效模式", "练习活动", "课后任务"]),
    _t("trn-sales", "training", "销售技能培训", "Sales Training",
       "coral-energy",
       ["cover", "executive-summary", "process-flow", "comparison", "metric-highlight", "closing"],
       "销售方法论 + 话术 + 场景演练。",
       ["核心方法论", "拜访流程", "话术模板", "成功 vs 失败案例", "数据指标", "演练任务"]),
    _t("trn-compliance", "training", "合规 / 安全培训", "Compliance Training",
       "light-corporate",
       ["cover", "executive-summary", "comparison", "process-flow", "bullet-list", "closing"],
       "信息安全 / 合规年度培训：必学条款 + 案例。",
       ["培训目标", "关键条款", "对错案例", "处置流程", "红线清单", "考试入口"]),
    _t("trn-product", "training", "产品培训", "Product Training",
       "indigo-saas",
       ["cover", "executive-summary", "process-flow", "comparison", "metric-highlight", "closing"],
       "面向销售 / CS 的产品培训：定位 + 卖点 + 演示。",
       ["产品定位", "三大卖点", "客户场景", "vs 竞品", "Demo 演示", "常见 FAQ"]),
    _t("trn-tech-bootcamp", "training", "技术训练营", "Tech Bootcamp",
       "dark-tech",
       ["cover", "executive-summary", "process-flow", "comparison", "metric-highlight", "closing"],
       "新工程师 / 实习生集中训练营，Day1-DayN 设计。",
       ["训练营目标", "课程地图", "动手任务", "评估标准", "经典 vs 反模式", "毕业要求"]),
    _t("trn-public-speaking", "training", "演讲与表达培训", "Public Speaking",
       "berry-cream",
       ["cover", "quote-block", "executive-summary", "process-flow", "bullet-list", "closing"],
       "演讲技巧 / 商务表达培训，重示范与练习。",
       ["开场金句", "三个核心原则", "结构化表达", "好 vs 差案例", "练习场景", "课后任务"]),
]


_ALL_TEMPLATES: list[TemplateSpec] = (
    _BUSINESS + _PITCH + _PRODUCT + _REPORT + _EDUCATION
    + _ACADEMIC + _MARKETING + _GOV + _TECH + _TRAINING
)

TEMPLATES: dict[str, TemplateSpec] = {t.slug: t for t in _ALL_TEMPLATES}


def list_templates(category: str | None = None) -> list[TemplateSpec]:
    """Return all templates, optionally filtered to one category."""
    if category is None:
        return list(_ALL_TEMPLATES)
    if category not in CATEGORIES:
        raise ValueError(
            f"Unknown category '{category}'. Valid: {', '.join(CATEGORIES)}"
        )
    return [t for t in _ALL_TEMPLATES if t.category == category]


def get_template(slug: str) -> TemplateSpec:
    """Look up a template by slug. Raises KeyError if not found."""
    try:
        return TEMPLATES[slug]
    except KeyError as exc:
        raise KeyError(
            f"Unknown template slug '{slug}'. Run `slide-skill templates` "
            f"to see all {len(TEMPLATES)} available templates."
        ) from exc


def list_categories() -> list[tuple[str, str, int]]:
    """Return (slug, label, count) for each category."""
    return [
        (slug, label, sum(1 for t in _ALL_TEMPLATES if t.category == slug))
        for slug, label in CATEGORIES.items()
    ]


def template_outline_markdown(spec: TemplateSpec, title: str | None = None) -> str:
    """Render a template's sample outline as a markdown source file.

    Used by `slide-skill quickstart <slug>` to scaffold a starter deck the
    user can immediately render.
    """
    deck_title = title or spec.name_zh
    lines = [f"# {deck_title}", ""]
    for heading in spec.outline:
        lines.append(f"# {heading}")
        lines.append("")
        lines.append(f"<!-- TODO: 在此填写 {heading} 的内容 -->")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
