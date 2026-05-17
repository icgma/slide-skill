import pytest
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from slide_skill.draft_notes import (
    _classify_slide,
    _extract_svg_text,
    _generate_note,
    draft_notes,
)
from slide_skill.project import init_project

# Test cases for _classify_slide

def test_classify_toc():
    assert _classify_slide("这是一个目录") == "toc"
    assert _classify_slide("Outline of the presentation") == "toc"

def test_classify_closing():
    assert _classify_slide("非常感谢大家的聆听") == "closing"
    assert _classify_slide("Thank you for your attention") == "closing"

def test_classify_section_divider():
    assert _classify_slide("第一章节 介绍") == "section_divider"
    assert _classify_slide("第三部分 实验结果") == "section_divider"

def test_classify_team():
    assert _classify_slide("我们的团队成员") == "team"
    assert _classify_slide("Team members") == "team"

def test_classify_conclusion():
    assert _classify_slide("最后的总结") == "conclusion"
    assert _classify_slide("In conclusion") == "conclusion"

def test_classify_content():
    assert _classify_slide("这是一个普通的内容幻灯片") == "content"
    assert _classify_slide("Some random text") == "content"


# Test cases for _extract_svg_text

def test_extract_text_from_svg(tmp_path):
    svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg">
    <text>Hello World</text>
    <g>
        <tspan>Nested Text</tspan>
    </g>
</svg>
"""
    svg_file = tmp_path / "test.svg"
    svg_file.write_text(svg_content)

    text = _extract_svg_text(svg_file)
    assert "Hello World" in text
    assert "Nested Text" in text

def test_extract_empty_svg(tmp_path):
    svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg">
    <rect width="10" height="10"/>
</svg>
"""
    svg_file = tmp_path / "empty.svg"
    svg_file.write_text(svg_content)

    text = _extract_svg_text(svg_file)
    assert text == ""


# Test cases for _generate_note

def test_toc_note_has_opening():
    note = _generate_note("目录内容", "toc", 1)
    assert "各位评委" in note or "各位老师" in note

def test_closing_note_has_thanks():
    note = _generate_note("感谢内容", "closing", 10)
    assert "感谢各位的聆听" in note

def test_content_note_has_structure():
    note = _generate_note("内容主题 数据分析", "content", 3)
    assert "这一页主要讲" in note
    assert "要点：" in note
    assert "过渡：" in note


# Test cases for draft_notes

def test_draft_notes_creates_files(tmp_path):
    # Setup project
    project_path = init_project("test_proj", "ppt169", tmp_path)
    svg_dir = project_path / "svg_final"
    svg_dir.mkdir(parents=True, exist_ok=True)

    # Create fake SVGs
    for i in range(1, 4):
        svg_file = svg_dir / f"slide_{i:02d}.svg"
        svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg">
    <text>Slide {i} Content</text>
</svg>"""
        svg_file.write_text(svg_content)

    created_files = draft_notes(project_path)

    assert len(created_files) == 3
    notes_dir = project_path / "notes"
    assert notes_dir.exists()

    for i in range(1, 4):
        note_file = notes_dir / f"slide_{i:02d}.md"
        assert note_file.exists()
        assert note_file in created_files
        content = note_file.read_text(encoding="utf-8")
        assert "Slide" in content

    total_file = notes_dir / "total.md"
    assert total_file.exists()

def test_draft_notes_no_overwrite(tmp_path):
    # Setup project
    project_path = init_project("test_proj_no_overwrite", "ppt169", tmp_path)
    svg_dir = project_path / "svg_final"
    svg_dir.mkdir(parents=True, exist_ok=True)

    # Create fake SVG
    svg_file = svg_dir / "slide_01.svg"
    svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg">
    <text>Slide Content</text>
</svg>"""
    svg_file.write_text(svg_content)

    # Create existing note
    notes_dir = project_path / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    note_file = notes_dir / "slide_01.md"
    note_file.write_text("Existing custom note", encoding="utf-8")

    # Run draft_notes with overwrite=False
    created_files = draft_notes(project_path, overwrite=False)

    assert len(created_files) == 0
    assert note_file.read_text(encoding="utf-8") == "Existing custom note"

def test_draft_notes_overwrite(tmp_path):
    # Setup project
    project_path = init_project("test_proj_overwrite", "ppt169", tmp_path)
    svg_dir = project_path / "svg_final"
    svg_dir.mkdir(parents=True, exist_ok=True)

    # Create fake SVG
    svg_file = svg_dir / "slide_01.svg"
    svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg">
    <text>Slide Content</text>
</svg>"""
    svg_file.write_text(svg_content)

    # Create existing note
    notes_dir = project_path / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    note_file = notes_dir / "slide_01.md"
    note_file.write_text("Existing custom note", encoding="utf-8")

    # Run draft_notes with overwrite=True
    created_files = draft_notes(project_path, overwrite=True)

    assert len(created_files) == 1
    assert note_file in created_files
    content = note_file.read_text(encoding="utf-8")
    assert content != "Existing custom note"
    assert "Slide" in content or "Content" in content
