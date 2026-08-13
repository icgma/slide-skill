from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from slide_skill.render import render_environment, render_environment_report, render_svg_previews


class RenderEnvironmentTest(unittest.TestCase):
    def test_render_environment_reports_missing_dependencies(self) -> None:
        with patch("slide_skill.render._find_soffice", return_value=None), patch("slide_skill.render.shutil.which", return_value=None):
            env = render_environment()
            self.assertFalse(env["ok"])
            self.assertIn("soffice", env["issues"][0])
            self.assertIn("pdftoppm", env["issues"][1])

            report = render_environment_report()
            self.assertIn("status: missing-dependencies", report)

    def test_render_environment_reports_ready(self) -> None:
        def fake_which(name: str) -> str | None:
            return "C:/tools/pdftoppm.exe" if name == "pdftoppm" else None

        with patch("slide_skill.render._find_soffice", return_value="C:/LibreOffice/soffice.exe"), patch(
            "slide_skill.render.shutil.which",
            side_effect=fake_which,
        ):
            env = render_environment()
            self.assertTrue(env["ok"])
            self.assertEqual([], env["issues"])

    def test_render_svg_previews_uses_headless_browser(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            svg_dir = project / "svg_final"
            svg_dir.mkdir(parents=True)
            (svg_dir / "slide_01.svg").write_text(
                '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
                '<rect width="1280" height="720" fill="#000"/></svg>',
                encoding="utf-8",
            )
            output_dir = project / "qa" / "rendered"

            def fake_run(cmd, *, timeout, label):
                self.assertIn("--headless=new", cmd)
                screenshot_arg = next(item for item in cmd if item.startswith("--screenshot="))
                Path(screenshot_arg.split("=", 1)[1]).write_bytes(b"png")

            with patch("slide_skill.render._find_browser", return_value="C:/Chrome/chrome.exe"), patch(
                "slide_skill.render._run_with_timeout",
                side_effect=fake_run,
            ):
                paths = render_svg_previews(project, output_dir)

            self.assertEqual([output_dir / "slide-01.png"], paths)
            self.assertTrue((output_dir / "_svg-preview-html" / "slide-01.html").exists())


if __name__ == "__main__":
    unittest.main()
