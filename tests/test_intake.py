from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from slide_skill.intake import convert_file, html_to_markdown


class IntakeTest(unittest.TestCase):
    def test_html_to_markdown_extracts_text(self) -> None:
        markdown = html_to_markdown("<h1>Title</h1><p>Hello <b>world</b>.</p>")
        self.assertIn("Title", markdown)
        self.assertIn("Hello", markdown)
        self.assertIn("world", markdown)

    def test_text_file_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "notes.txt"
            output = Path(tmp) / "notes.md"
            source.write_text("plain notes", encoding="utf-8")
            convert_file(source, output)
            self.assertEqual(output.read_text(encoding="utf-8"), "plain notes")


if __name__ == "__main__":
    unittest.main()
