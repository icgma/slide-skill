"""Draft speaker notes from slide content — structured note templates."""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree as ET


def _extract_svg_text(svg_path: Path) -> str:
    """Extract all text content from an SVG file."""
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return ""
    texts = []
    for elem in tree.iter():
        if elem.text and elem.text.strip():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag in ("text", "tspan"):
                texts.append(elem.text.strip())
    return " ".join(texts)


def _classify_slide(text: str) -> str:
    """Heuristic: classify slide type from its text content."""
    lower = text.lower()
    if any(kw in lower for kw in ("目录", "目录", "outline", "contents", "agenda")):
        return "toc"
    if any(kw in lower for kw in ("谢谢", "感谢", "thank", "q&a", "提问", "致谢")):
        return "closing"
    if re.search(r"第[一二三四五六七八九十\d]+[章节部分]", text):
        return "section_divider"
    if any(kw in lower for kw in ("团队", "成员", "team", "关于我")):
        return "team"
    if any(kw in lower for kw in ("总结", "结论", "conclusion", "summary", "展望")):
        return "conclusion"
    return "content"


def _generate_note(text: str, slide_type: str, slide_num: int) -> str:
    """Generate a structured note template for one slide."""
    templates: dict[str, str] = {
        "toc": "各位评委/老师好，今天我将从以下几个方面进行汇报。",
        "closing": "以上就是我今天的全部内容，感谢各位的聆听，欢迎批评指正。",
        "section_divider": "接下来进入[章节名称]部分。",
        "conclusion": "总结一下，我们的核心发现/贡献是：[要点1]、[要点2]、[要点3]。",
        "team": "我们团队由[人数]名成员组成，分别负责[方向1]和[方向2]。",
    }

    base = templates.get(slide_type, "")

    keywords = re.findall(r"[\u4e00-\u9fff]{2,8}|[a-zA-Z]{3,}", text)
    key_points = keywords[:5] if keywords else []

    if slide_type == "content" and key_points:
        bullets = "\n".join(f"- {kw}：[展开说明]" for kw in key_points)
        base = f"这一页主要讲：{key_points[0]}。\n\n要点：\n{bullets}\n\n过渡：接下来我们来看[下一页主题]。"

    if not base:
        base = f"[Slide {slide_num} 备注草稿]\n\n要点：[根据幻灯片内容填写]\n过渡：接下来..."

    return base


def draft_notes(
    project_path: Path | str,
    *,
    overwrite: bool = False,
) -> list[Path]:
    """Generate speaker note drafts from SVG slide content.

    Returns list of created note file paths.
    """
    from .project import load_project

    project = Path(project_path)
    meta = load_project(project)

    svg_dir = project / "svg_final"
    if not svg_dir.exists():
        svg_dir = project / "svg_output"
    if not svg_dir.exists():
        raise FileNotFoundError("No SVG slides found. Run svg pipeline first.")

    svg_files = sorted(svg_dir.glob("slide_*.svg"))
    if not svg_files:
        raise FileNotFoundError("No SVG slides found in svg_final/ or svg_output/.")

    notes_dir = project / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    all_notes: list[str] = []

    for idx, svg_path in enumerate(svg_files, start=1):
        text = _extract_svg_text(svg_path)
        slide_type = _classify_slide(text)
        note = _generate_note(text, slide_type, idx)

        note_file = notes_dir / f"slide_{idx:02d}.md"
        if note_file.exists() and not overwrite:
            existing = note_file.read_text(encoding="utf-8").strip()
            if existing:
                all_notes.append(existing)
                continue

        note_file.write_text(note, encoding="utf-8")
        created.append(note_file)
        all_notes.append(note)

    total_file = notes_dir / "total.md"
    combined_parts: list[str] = []
    for idx, note_text in enumerate(all_notes, start=1):
        combined_parts.append(f"## Slide {idx}\n\n{note_text}")

    if overwrite or not total_file.exists():
        total_file.write_text("\n\n---\n\n".join(combined_parts), encoding="utf-8")

    return created


def draft_notes_report(project_path: Path | str) -> str:
    """Generate a readable report of drafted notes."""
    project = Path(project_path)

    svg_dir = project / "svg_final"
    if not svg_dir.exists():
        svg_dir = project / "svg_output"

    svg_files = sorted(svg_dir.glob("slide_*.svg")) if svg_dir.exists() else []

    notes_dir = project / "notes"
    lines = ["# 备注草稿报告", ""]

    for idx, svg_path in enumerate(svg_files, start=1):
        text = _extract_svg_text(svg_path)
        slide_type = _classify_slide(text)
        note_file = notes_dir / f"slide_{idx:02d}.md"

        existing = ""
        if note_file.exists():
            existing = note_file.read_text(encoding="utf-8").strip()

        status = "已有备注" if existing else "待生成"
        lines.append(f"## Slide {idx} [{slide_type}] — {status}")
        lines.append(f"提取文本: {text[:100]}{'...' if len(text) > 100 else ''}")
        if existing:
            lines.append(f"备注: {existing[:150]}{'...' if len(existing) > 150 else ''}")
        else:
            lines.append(f"建议: {_generate_note(text, slide_type, idx)[:150]}")
        lines.append("")

    return "\n".join(lines)
