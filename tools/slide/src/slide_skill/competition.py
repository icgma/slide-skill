"""Competition structure templates for student presentations."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Section:
    title: str
    min_pages: int
    max_pages: int
    guidance: str


@dataclass(frozen=True)
class CompetitionSpec:
    name: str
    name_zh: str
    time_limit_minutes: int
    page_range: tuple[int, int]
    sections: list[Section]
    tips: str


COMPETITIONS: dict[str, CompetitionSpec] = {
    "internet-plus": CompetitionSpec(
        name="internet-plus",
        name_zh="互联网+创新创业大赛",
        time_limit_minutes=8,
        page_range=(15, 20),
        sections=[
            Section("开场与痛点", 1, 2, "一句话点明项目核心价值，用数据或故事揭示目标用户的真实痛点"),
            Section("解决方案", 2, 3, "产品/方案的核心功能，用对比展示'使用前后'的变化"),
            Section("核心技术与创新", 2, 3, "技术架构图 + 关键算法/专利，突出与竞品的差异化壁垒"),
            Section("商业模式", 1, 2, "盈利模式、获客渠道、单位经济模型"),
            Section("市场分析", 1, 2, "TAM/SAM/SOM 市场规模，目标用户画像，竞品对比矩阵"),
            Section("团队介绍", 1, 1, "核心成员背景 + 互补性，导师/顾问"),
            Section("财务与里程碑", 1, 2, "已取得的里程碑 + 未来 12-24 月规划与财务预测"),
            Section("结尾与愿景", 1, 1, "总结核心价值主张，呼应开场，留下深刻印象"),
        ],
        tips=(
            "评委平均看每页 10-15 秒，文字不超过 30 字/页。\n"
            "数据用图表展示，避免大段文字。\n"
            "技术页放架构图，不要堆代码。\n"
            "准备 Q&A：竞品差异化、盈利模式可行性、团队能力是必问方向。"
        ),
    ),
    "challenge-cup": CompetitionSpec(
        name="challenge-cup",
        name_zh="挑战杯课外学术科技作品竞赛",
        time_limit_minutes=8,
        page_range=(15, 18),
        sections=[
            Section("研究背景", 1, 2, "问题来源、社会/学术意义，用数据说明紧迫性"),
            Section("文献综述", 2, 3, "国内外研究现状，用表格对比已有方案的局限性"),
            Section("研究方法", 2, 3, "实验设计、数据采集方案、技术路线图"),
            Section("创新点", 1, 2, "与已有工作对比，明确 2-3 个核心创新贡献"),
            Section("实验结果", 2, 3, "关键数据图表，与对照组/基线对比"),
            Section("结论与展望", 1, 2, "研究成果总结，应用前景，下一步计划"),
            Section("致谢", 1, 1, "导师、团队、资助方"),
        ],
        tips=(
            "学术严谨性是第一评分维度，数据必须有来源。\n"
            "创新点要用'与 XX 相比，本方案在 YY 上提升了 ZZ%'的量化表述。\n"
            "评委多为教授，技术细节要经得起追问。\n"
            "文献综述用对比表格，不要逐条罗列。"
        ),
    ),
    "math-modeling": CompetitionSpec(
        name="math-modeling",
        name_zh="数学建模竞赛",
        time_limit_minutes=10,
        page_range=(12, 18),
        sections=[
            Section("问题重述", 1, 1, "用自己的语言概括题目要求，明确需要回答的问题"),
            Section("模型假设", 1, 1, "列出关键假设及其合理性依据"),
            Section("符号说明", 1, 1, "符号 → 含义 → 单位的表格，保持全文一致"),
            Section("模型建立", 3, 4, "模型一、模型二分别阐述，配数学公式和流程图"),
            Section("模型求解", 2, 3, "算法步骤 + 核心代码片段（关键部分），计算流程图"),
            Section("结果分析", 2, 3, "图表展示结果，与实际数据或其他模型对比验证"),
            Section("灵敏度分析", 1, 2, "关键参数扰动下的结果变化，评估模型鲁棒性"),
            Section("模型评价与改进", 1, 1, "优缺点总结 + 改进方向"),
        ],
        tips=(
            "评委关注建模思路的合理性，不是结果精度。\n"
            "每个模型要讲清'为什么选这个模型'而非只写公式。\n"
            "灵敏度分析是加分项，体现对模型局限性的认知。\n"
            "图表要有标题、坐标轴标签和单位。"
        ),
    ),
    "innovation-training": CompetitionSpec(
        name="innovation-training",
        name_zh="大学生创新创业训练计划（大创）",
        time_limit_minutes=5,
        page_range=(10, 15),
        sections=[
            Section("项目背景", 1, 2, "选题来源、研究意义、与国家和行业发展需求的关联"),
            Section("研究现状", 1, 2, "国内外文献综述，指出研究空白"),
            Section("创新点", 1, 2, "项目的 2-3 个核心创新贡献"),
            Section("实施方案", 2, 3, "技术路线图、实验方案、时间节点"),
            Section("进度安排", 1, 1, "甘特图或里程碑时间表"),
            Section("预期成果", 1, 1, "论文、专利、原型等可量化的交付物"),
            Section("经费预算", 1, 1, "分项预算表，总额与资助额度匹配"),
        ],
        tips=(
            "大创评审注重可行性和规范性，不要画大饼。\n"
            "进度安排要具体到月，体现可执行性。\n"
            "经费预算要合理，与实验内容对应。\n"
            "创新点要落在'可验证'上，而非口号式表述。"
        ),
    ),
    "thesis-defense": CompetitionSpec(
        name="thesis-defense",
        name_zh="毕业论文答辩",
        time_limit_minutes=15,
        page_range=(15, 25),
        sections=[
            Section("研究背景与意义", 1, 2, "选题背景、研究问题、理论与实际意义"),
            Section("文献综述", 2, 3, "国内外研究现状，指出研究空白和本文切入点"),
            Section("研究内容与方法", 3, 5, "研究框架、实验/调研设计、数据来源、分析方法"),
            Section("实验/调研结果", 3, 5, "核心发现，用图表展示关键数据"),
            Section("讨论与分析", 2, 3, "结果的理论与实践含义，与前人研究对比"),
            Section("结论与展望", 1, 2, "研究贡献总结、局限性、未来研究方向"),
            Section("致谢", 1, 1, "导师、同学、家人"),
        ],
        tips=(
            "答辩时间有限，重点放在'你做了什么、发现了什么'。\n"
            "背景和文献不要超过总时长的 1/4。\n"
            "准备好'你的创新点是什么'和'为什么选这个方法'两个必答题。\n"
            "结果页用图表说话，避免读表。"
        ),
    ),
    "course-presentation": CompetitionSpec(
        name="course-presentation",
        name_zh="课程展示",
        time_limit_minutes=10,
        page_range=(8, 12),
        sections=[
            Section("主题介绍", 1, 1, "主题是什么、为什么选这个主题"),
            Section("核心内容", 3, 5, "分 3-5 个要点展开，每个要点配一个例子或数据"),
            Section("案例分析", 1, 2, "具体案例深入剖析，增强说服力"),
            Section("总结与思考", 1, 2, "核心结论、个人见解、开放性问题"),
        ],
        tips=(
            "课程展示重在逻辑清晰和表达生动。\n"
            "每页一个核心观点，配合图示或案例。\n"
            "结尾留一个思考题，引发课堂讨论。\n"
            "控制时间，留 2-3 分钟给 Q&A。"
        ),
    ),
}


# Theme used by each finished example pack under examples/competitions/<slug>/.
EXAMPLE_PACK_THEMES: dict[str, str] = {
    "internet-plus": "vibrant-startup",
    "challenge-cup": "data-forward",
    "math-modeling": "data-forward",
    "innovation-training": "indigo-saas",
    "thesis-defense": "academic-defense",
    "course-presentation": "light-corporate",
}


def find_examples_dir() -> Path | None:
    """Locate examples/competitions/ for editable-install and clone layouts.

    Walks up from the installed package location first (covers editable
    installs living inside the repo), then falls back to the current
    working directory (covers running a wheel-installed CLI from a clone).
    """
    candidates = [parent / "examples" / "competitions" for parent in Path(__file__).resolve().parents]
    candidates.append(Path.cwd() / "examples" / "competitions")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def scaffold_from_example(project_path: Path | str, slug: str) -> dict[str, str]:
    """Copy a competition example pack's source.md + notes into a project.

    Returns {"source": ..., "notes": ..., "theme": ...} with destination
    paths as strings ("" for notes when the pack ships none).
    """
    get_competition(slug)  # raises ValueError with valid slugs for unknown names
    examples = find_examples_dir()
    if examples is None:
        valid = ", ".join(sorted(COMPETITIONS))
        raise FileNotFoundError(
            "Competition example packs not found (expected examples/competitions/ "
            f"in the slide-skill repository). Valid slugs: {valid}"
        )
    pack_source = examples / slug / "source.md"
    if not pack_source.is_file():
        available = ", ".join(sorted(
            entry.name for entry in examples.iterdir() if (entry / "source.md").is_file()
        )) or "none"
        raise FileNotFoundError(
            f"No example pack for '{slug}' under {examples}. Available packs: {available}"
        )

    project = Path(project_path)
    dest_source = project / "sources" / "source.md"
    dest_source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pack_source, dest_source)

    dest_notes = ""
    pack_notes = examples / slug / "notes" / "total.md"
    if pack_notes.is_file():
        notes_path = project / "notes" / "total.md"
        notes_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pack_notes, notes_path)
        dest_notes = str(notes_path)

    return {
        "source": str(dest_source),
        "notes": dest_notes,
        "theme": EXAMPLE_PACK_THEMES.get(slug, "dark-tech"),
    }


def get_competition(name: str) -> CompetitionSpec:
    try:
        return COMPETITIONS[name]
    except KeyError as exc:
        valid = ", ".join(sorted(COMPETITIONS))
        raise ValueError(f"Unknown competition '{name}'. Valid: {valid}") from exc


def list_competitions() -> list[CompetitionSpec]:
    return list(COMPETITIONS.values())


def competition_to_markdown(spec: CompetitionSpec) -> str:
    """Generate a skeleton markdown file from a competition spec."""
    lines = [
        f"# {spec.name_zh} 演示文稿大纲",
        "",
        f"> 时限: {spec.time_limit_minutes} 分钟 | 页数: {spec.page_range[0]}-{spec.page_range[1]} 页",
        "",
    ]

    slide_num = 1
    for section in spec.sections:
        lines.append(f"## {section.title} ({section.min_pages}-{section.max_pages} 页)")
        lines.append(f"<!-- guidance: {section.guidance} -->")
        for _ in range(section.min_pages):
            lines.append(f"### Slide {slide_num}")
            lines.append(f"<!-- {section.guidance} -->")
            lines.append("")
            slide_num += 1
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("**评审提示：**")
    for tip_line in spec.tips.split("\n"):
        lines.append(f"- {tip_line.strip()}")
    lines.append("")

    return "\n".join(lines)
