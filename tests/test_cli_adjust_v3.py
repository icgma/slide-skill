import json
import tempfile
from pathlib import Path
from slide_skill.cli import main


def _setup_project(temp_dir):
    """Initialize a test project with stub SVGs and a mock spec_lock.json.

    Returns (proj_dir, svg_file) where svg_file is svg_output/slide_01.svg.
    """
    assert main(["init", "testproj", "--base", temp_dir]) == 0
    proj_dir = Path(temp_dir) / "testproj"
    assert proj_dir.exists()

    svg_dir = proj_dir / "svg_output"
    svg_dir.mkdir(parents=True, exist_ok=True)
    svg_file = svg_dir / "slide_01.svg"
    svg_file.write_text("<svg></svg>", encoding="utf-8")

    final_dir = proj_dir / "svg_final"
    final_dir.mkdir(parents=True, exist_ok=True)
    final_file = final_dir / "slide_01.svg"
    final_file.write_text("<svg></svg>", encoding="utf-8")

    mock_spec_lock = {
        "canvas": {"width": "960", "height": "540"},
        "font_family": "Arial",
        "palette": {
            "background": "#FFFFFF",
            "surface": "#F5F5F7",
            "text": "#1D1D1F",
            "accent": "#0066CC",
            "muted": "#86868B",
            "body": "#1D1D1F"
        }
    }
    (proj_dir / "spec_lock.json").write_text(json.dumps(mock_spec_lock), encoding="utf-8")
    return proj_dir, svg_file


def test_adjust_v3_layouts():
    with tempfile.TemporaryDirectory() as temp_dir:
        proj_dir, svg_file = _setup_project(temp_dir)

        # 3. Call adjust command to force a v3 domain layout (e.g., vocab-card)
        body_content = "医院 (yīyuàn) — hospital\n医生 (yīshēng) — doctor"
        args = ["adjust", str(proj_dir), "1", "--layout", "vocab-card", "--body", body_content]
        assert main(args) == 0

        # 4. Verify adjusted SVG content contains the vocab elements
        adjusted_content = svg_file.read_text(encoding="utf-8")
        assert "content-vocab-01" in adjusted_content
        assert "yīyuàn" in adjusted_content
        assert "hospital" in adjusted_content
        assert "医生" in adjusted_content

        # 5. Call adjust command for dialogue layout
        dialogue_content = "A: 你好！\nB: 你好！"
        args = ["adjust", str(proj_dir), "1", "--layout", "dialogue", "--body", dialogue_content]
        assert main(args) == 0

        # 6. Verify adjusted SVG content contains dialogue bubble elements
        adjusted_content = svg_file.read_text(encoding="utf-8")
        assert "content-dialogue-01" in adjusted_content
        assert "A" in adjusted_content
        assert "B" in adjusted_content


def test_comparison_matrix_with_vs_in_bullet():
    """Bullets containing the substring 'vs' (e.g. 'vs monolith') must
    survive — the old `"VS" in line.upper()` filter incorrectly stripped them."""
    with tempfile.TemporaryDirectory() as temp_dir:
        proj_dir, svg_file = _setup_project(temp_dir)
        body = "Microservices (vs monolith) win on scalability\n---\nMonoliths win on simplicity"
        args = ["adjust", str(proj_dir), "1",
                "--layout", "comparison-matrix", "--body", body]
        assert main(args) == 0
        content = svg_file.read_text(encoding="utf-8")
        assert "Microservices" in content, "vs-in-parens bullet was filtered out"
