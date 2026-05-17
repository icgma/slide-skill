"""Tests for snapshot rendering and pixel-diff comparison."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image
import numpy as np

from slide_skill.snapshot_diff import DeckDiff, SlideDiff, compare_snapshots, write_snapshot_report


def _make_png(dir_path: Path, name: str, color: tuple[int, int, int], size: tuple[int, int] = (100, 100)) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, color)
    p = dir_path / name
    img.save(p)
    return p


class SnapshotDiffTest(unittest.TestCase):
    def test_identical_images_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp) / "ref"
            act_dir = Path(tmp) / "act"
            _make_png(ref_dir, "slide-01.png", (255, 0, 0))
            _make_png(act_dir, "slide-01.png", (255, 0, 0))

            result = compare_snapshots(ref_dir, act_dir)
            self.assertEqual(result.verdict, "PASS")
            self.assertEqual(len(result.slides), 1)
            self.assertAlmostEqual(result.slides[0].score, 100.0)

    def test_different_images_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp) / "ref"
            act_dir = Path(tmp) / "act"
            _make_png(ref_dir, "slide-01.png", (255, 0, 0))
            _make_png(act_dir, "slide-01.png", (0, 0, 255))

            result = compare_snapshots(ref_dir, act_dir, threshold=95.0)
            self.assertEqual(result.verdict, "FAIL")
            self.assertLess(result.slides[0].score, 95.0)

    def test_anti_aliasing_tolerance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp) / "ref"
            act_dir = Path(tmp) / "act"
            ref_img = Image.new("RGB", (50, 50), (100, 100, 100))
            ref_arr = np.array(ref_img)
            act_arr = ref_arr.copy()
            act_arr[10:20, 10:20] = [105, 95, 100]  # Within 10 tolerance
            act_img = Image.fromarray(act_arr.astype(np.uint8))

            ref_dir.mkdir(parents=True)
            act_dir.mkdir(parents=True)
            ref_img.save(ref_dir / "slide-01.png")
            act_img.save(act_dir / "slide-01.png")

            result = compare_snapshots(ref_dir, act_dir, threshold=95.0, pixel_tolerance=10)
            self.assertAlmostEqual(result.slides[0].score, 100.0)

    def test_missing_actual_slide_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp) / "ref"
            act_dir = Path(tmp) / "act"
            _make_png(ref_dir, "slide-01.png", (255, 0, 0))
            act_dir.mkdir(parents=True, exist_ok=True)

            result = compare_snapshots(ref_dir, act_dir)
            self.assertEqual(result.verdict, "FAIL")
            self.assertEqual(result.slides[0].score, 0.0)

    def test_empty_reference_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp) / "ref"
            act_dir = Path(tmp) / "act"
            ref_dir.mkdir(parents=True)
            act_dir.mkdir(parents=True)

            result = compare_snapshots(ref_dir, act_dir)
            self.assertEqual(result.verdict, "FAIL")
            self.assertEqual(result.overall_score, 0.0)

    def test_multi_slide_deck(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp) / "ref"
            act_dir = Path(tmp) / "act"
            _make_png(ref_dir, "slide-01.png", (255, 0, 0))
            _make_png(ref_dir, "slide-02.png", (0, 255, 0))
            _make_png(act_dir, "slide-01.png", (255, 0, 0))
            _make_png(act_dir, "slide-02.png", (0, 255, 0))

            result = compare_snapshots(ref_dir, act_dir)
            self.assertEqual(result.verdict, "PASS")
            self.assertEqual(len(result.slides), 2)
            self.assertAlmostEqual(result.overall_score, 100.0)

    def test_custom_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp) / "ref"
            act_dir = Path(tmp) / "act"
            ref_arr = np.full((100, 100, 3), [100, 100, 100], dtype=np.uint8)
            act_arr = ref_arr.copy()
            act_arr[:30, :, :] = [0, 0, 0]  # 30% of pixels are very different
            ref_img = Image.fromarray(ref_arr)
            act_img = Image.fromarray(act_arr)
            ref_dir.mkdir(parents=True)
            act_dir.mkdir(parents=True)
            ref_img.save(ref_dir / "slide-01.png")
            act_img.save(act_dir / "slide-01.png")

            result_low = compare_snapshots(ref_dir, act_dir, threshold=60.0)
            result_high = compare_snapshots(ref_dir, act_dir, threshold=99.0)
            self.assertEqual(result_low.verdict, "PASS")
            self.assertEqual(result_high.verdict, "FAIL")


class SnapshotReportTest(unittest.TestCase):
    def test_report_contains_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            diff = DeckDiff(
                slides=[
                    SlideDiff(slide_name="slide-01.png", score=98.5, verdict="PASS"),
                    SlideDiff(slide_name="slide-02.png", score=92.1, verdict="FAIL"),
                ],
                overall_score=95.3,
                verdict="FAIL",
                threshold=95.0,
            )
            out = Path(tmp) / "SNAPSHOT-QA.md"
            write_snapshot_report(diff, out)

            text = out.read_text(encoding="utf-8")
            self.assertIn("status: fail", text)
            self.assertIn("slide-01.png", text)
            self.assertIn("98.50%", text)
            self.assertIn("threshold: 95.0%", text)

    def test_report_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            diff = DeckDiff(
                slides=[SlideDiff(slide_name="slide-01.png", score=100.0, verdict="PASS")],
                overall_score=100.0,
                verdict="PASS",
                threshold=95.0,
            )
            out = Path(tmp) / "SNAPSHOT-QA.md"
            write_snapshot_report(diff, out)

            text = out.read_text(encoding="utf-8")
            self.assertIn("status: pass", text)


if __name__ == "__main__":
    unittest.main()
