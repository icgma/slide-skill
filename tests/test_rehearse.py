from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from slide_skill.rehearse import (
    RehearsalReport,
    SlideTiming,
    estimate_speaking_time,
    format_rehearsal_report,
    rehearse_project,
)
from slide_skill.project import init_project


class RehearseTest(unittest.TestCase):
    def test_empty_text_returns_zero(self) -> None:
        self.assertEqual(estimate_speaking_time(""), 0.0)

    def test_chinese_text_reasonable_time(self) -> None:
        # 260 chars of Chinese should be roughly 60 seconds
        text = "中" * 260
        time = estimate_speaking_time(text)
        self.assertAlmostEqual(time, 60.0, delta=15.0)

    def test_english_text_reasonable_time(self) -> None:
        # 140 English words should be roughly 60 seconds
        text = "word " * 140
        time = estimate_speaking_time(text)
        self.assertAlmostEqual(time, 60.0, delta=15.0)

    def test_mixed_text_uses_weighted_estimate(self) -> None:
        # A mixed text should fall between the purely Latin calculation and purely CJK calculation
        # Let's pick a string where cjk_time and latin_time differ significantly.
        # cjk_time for 260 chars is 60. latin_time for 260 latin words is ~111.4.
        text_zh = "中" * 260
        text_en = "word " * 260
        text_mixed = text_zh + " " + text_en

        time_zh = estimate_speaking_time(text_zh)
        time_en = estimate_speaking_time(text_en)
        time_mixed = estimate_speaking_time(text_mixed)

        # We assert that the mixed time falls strictly between the CJK-only and Latin-only times.
        self.assertTrue(time_zh < time_mixed < time_en or time_en < time_mixed < time_zh)

    def test_whitespace_only_returns_zero(self) -> None:
        self.assertEqual(estimate_speaking_time("   \n\t "), 0.0)

    def test_report_shows_total_slides(self) -> None:
        report = RehearsalReport(
            total_slides=10,
            slides_with_notes=8,
            slides_silent=[2, 5],
            timings=[],
            total_seconds=120.0,
            time_limit_seconds=None,
            over_limit=False,
            over_by_seconds=None,
            fastest_slide=None,
            slowest_slide=None,
        )
        formatted = format_rehearsal_report(report)
        self.assertIn("Total slides: 10", formatted)

    def test_report_shows_overtime_warning(self) -> None:
        report = RehearsalReport(
            total_slides=10,
            slides_with_notes=8,
            slides_silent=[],
            timings=[],
            total_seconds=650.0,
            time_limit_seconds=600.0,
            over_limit=True,
            over_by_seconds=50.0,
            fastest_slide=None,
            slowest_slide=None,
        )
        formatted = format_rehearsal_report(report)
        self.assertIn("!! 超时", formatted)

    def test_report_shows_time_limit(self) -> None:
        report = RehearsalReport(
            total_slides=10,
            slides_with_notes=8,
            slides_silent=[],
            timings=[],
            total_seconds=500.0,
            time_limit_seconds=600.0,
            over_limit=False,
            over_by_seconds=None,
            fastest_slide=None,
            slowest_slide=None,
        )
        formatted = format_rehearsal_report(report)
        self.assertIn("Time limit:", formatted)

    def test_report_lists_silent_slides(self) -> None:
        report = RehearsalReport(
            total_slides=10,
            slides_with_notes=8,
            slides_silent=[2, 5],
            timings=[],
            total_seconds=500.0,
            time_limit_seconds=None,
            over_limit=False,
            over_by_seconds=None,
            fastest_slide=None,
            slowest_slide=None,
        )
        formatted = format_rehearsal_report(report)
        self.assertIn("S2", formatted)
        self.assertIn("S5", formatted)

    def test_rehearse_with_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project("Notes Test", base_dir=root / "projects")
            notes_dir = project / "notes"
            notes_dir.mkdir(parents=True, exist_ok=True)
            (notes_dir / "slide_01.md").write_text("Hello world. This is a note.", encoding="utf-8")

            report = rehearse_project(project)
            self.assertGreater(report.slides_with_notes, 0)
            self.assertGreater(report.total_seconds, 0)

    def test_rehearse_competition_auto_detects_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project("Comp Test", base_dir=root / "projects", competition="internet-plus")

            report = rehearse_project(project)
            # internet-plus has an 8 minute limit (8 * 60 = 480 seconds)
            self.assertEqual(report.time_limit_seconds, 480.0)


if __name__ == "__main__":
    unittest.main()
