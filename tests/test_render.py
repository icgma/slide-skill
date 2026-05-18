from __future__ import annotations

import unittest
from unittest.mock import patch

from slide_skill.render import render_environment, render_environment_report


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


if __name__ == "__main__":
    unittest.main()
