import tempfile
from pathlib import Path
import pytest
import slide_skill.cli as cli
from slide_skill.cli import main

def test_competitions_command(capsys):
    assert main(["competitions"]) == 0
    captured = capsys.readouterr()
    output = captured.out
    assert "internet-plus" in output
    # Count the number of non-empty lines, subtracting headers.
    # We'll just verify that there are at least 6 competition names as requested.
    # The output format is:
    # ID                     名称                       时限       页数         章节数
    # -------------------------------------------------------------------------------------
    # internet-plus          ...
    lines = [line for line in output.split("\n") if line.strip()]
    assert len(lines) >= 8  # 2 header lines + 6 competitions


def test_voices_mimo(capsys):
    assert main(["voices", "--engine", "mimo"]) == 0
    captured = capsys.readouterr()
    output = captured.out
    assert len(output.strip()) > 0

def test_init_competition_flag():
    with tempfile.TemporaryDirectory() as temp_dir:
        assert main(["init", "testproj", "--base", temp_dir, "--competition", "internet-plus"]) == 0
        proj_dir = Path(temp_dir) / "testproj"
        assert proj_dir.exists()
        outline_file = proj_dir / "sources" / "competition_outline.md"
        assert outline_file.exists()

def test_narrate_engine_flag_help(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["narrate", "--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    output = captured.out
    assert "--engine" in output
    assert "mimo" in output

def test_draft_notes_no_slides():
    with tempfile.TemporaryDirectory() as temp_dir:
        # initialize an empty project
        assert main(["init", "testproj", "--base", temp_dir]) == 0
        proj_dir = Path(temp_dir) / "testproj"
        # draft notes should fail/return 1 because there are no slides/svgs
        assert main(["draft-notes", str(proj_dir)]) == 1

def test_rehearse_no_notes():
    with tempfile.TemporaryDirectory() as temp_dir:
        assert main(["init", "testproj", "--base", temp_dir]) == 0
        proj_dir = Path(temp_dir) / "testproj"
        # rehearsal should succeed and return 0 even if there are no notes
        assert main(["rehearse", str(proj_dir)]) == 0


def test_quickstart_ai_uses_strict_quality_by_default(tmp_path, monkeypatch):
    source = tmp_path / "source.md"
    source.write_text("# Demo\n\n## Point\n\n- Clear text\n", encoding="utf-8")
    calls = []

    def fake_generate_svg_with_ai(project, plans, **kwargs):
        calls.append(kwargs)
        svg_dir = Path(project) / "svg_output"
        svg_dir.mkdir(parents=True, exist_ok=True)
        (svg_dir / "slide_01.svg").write_text(
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">\n'
            '  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>\n'
            '  <g id="content-body-01"><text x="100" y="100" font-family="Arial" font-size="44" fill="#F1F5F9">Demo</text></g>\n'
            "</svg>\n",
            encoding="utf-8",
        )
        return [svg_dir / "slide_01.svg"]

    monkeypatch.setattr(cli, "_require_ai_access", lambda args: True)
    monkeypatch.setattr("slide_skill.ai_executor.generate_svg_with_ai", fake_generate_svg_with_ai)
    monkeypatch.setattr(cli, "export_project", lambda project, output=None, stage="final": Path(project) / "exports" / "deck.pptx")
    monkeypatch.setattr(cli, "run_qa", lambda *args, **kwargs: (True, Path(args[0]) / "qa" / "QA.md"))

    assert main([
        "quickstart",
        str(source),
        "--name",
        "strict-default",
        "--base",
        str(tmp_path / "projects"),
        "--mode",
        "ai",
        "--planner",
        "deterministic",
    ]) == 0

    assert calls
    assert calls[0]["strict_quality"] is True


def test_quickstart_ai_lenient_quality_opt_out(tmp_path, monkeypatch):
    source = tmp_path / "source.md"
    source.write_text("# Demo\n\n## Point\n\n- Clear text\n", encoding="utf-8")
    calls = []

    def fake_generate_svg_with_ai(project, plans, **kwargs):
        calls.append(kwargs)
        svg_dir = Path(project) / "svg_output"
        svg_dir.mkdir(parents=True, exist_ok=True)
        (svg_dir / "slide_01.svg").write_text(
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">\n'
            '  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>\n'
            '  <g id="content-body-01"><text x="100" y="100" font-family="Arial" font-size="44" fill="#F1F5F9">Demo</text></g>\n'
            "</svg>\n",
            encoding="utf-8",
        )
        return [svg_dir / "slide_01.svg"]

    monkeypatch.setattr(cli, "_require_ai_access", lambda args: True)
    monkeypatch.setattr("slide_skill.ai_executor.generate_svg_with_ai", fake_generate_svg_with_ai)
    monkeypatch.setattr(cli, "export_project", lambda project, output=None, stage="final": Path(project) / "exports" / "deck.pptx")
    monkeypatch.setattr(cli, "run_qa", lambda *args, **kwargs: (True, Path(args[0]) / "qa" / "QA.md"))

    assert main([
        "quickstart",
        str(source),
        "--name",
        "lenient-opt-out",
        "--base",
        str(tmp_path / "projects"),
        "--mode",
        "ai",
        "--planner",
        "deterministic",
        "--lenient-quality",
    ]) == 0

    assert calls
    assert calls[0]["strict_quality"] is False
