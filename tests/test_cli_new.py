import tempfile
from pathlib import Path
import pytest
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
