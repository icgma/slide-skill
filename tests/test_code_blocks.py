"""Tests for v1.4 Phase 20 — Code Block Highlighting."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from slide_skill import code_blocks
from slide_skill.themes import get_theme


SAMPLE_MD = """\
intro paragraph

```python
def hello():
    return "world"
```

between

```js
const x = 1;
```

```
plain block
```
"""


class CodeBlockExtractTests(unittest.TestCase):
    def test_extract_three_blocks(self) -> None:
        blocks = code_blocks.extract_code_blocks(SAMPLE_MD)
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[0].language, "python")
        self.assertEqual(blocks[1].language, "js")
        self.assertEqual(blocks[2].language, "text")
        self.assertIn("def hello", blocks[0].text)

    def test_parse_highlight_spec_string(self) -> None:
        self.assertEqual(code_blocks.parse_highlight_spec("3, 7-9, 12"), [3, 7, 8, 9, 12])

    def test_parse_highlight_spec_list(self) -> None:
        self.assertEqual(code_blocks.parse_highlight_spec([1, "4-5", 9]), [1, 4, 5, 9])


class CodeBlockRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.theme = get_theme("dark-tech")

    def test_renders_well_formed_svg_fragment(self) -> None:
        block = code_blocks.CodeBlock(language="python", text='print("hi")\nprint("bye")')
        svg = code_blocks.render_code_svg(block, theme=self.theme, width=800)
        # Wrap in root for parsing — the function returns a <g> fragment.
        wrapped = f'<svg xmlns="http://www.w3.org/2000/svg">{svg}</svg>'
        root = ET.fromstring(wrapped)
        # Should contain at least one <rect> (panel) and >= 1 <text>.
        ns = "{http://www.w3.org/2000/svg}"
        self.assertGreaterEqual(len(root.findall(f".//{ns}rect")), 1)
        self.assertGreaterEqual(len(root.findall(f".//{ns}text")), 1)

    def test_panel_uses_theme_surface(self) -> None:
        block = code_blocks.CodeBlock(language="python", text="x = 1")
        svg = code_blocks.render_code_svg(block, theme=self.theme)
        self.assertIn(self.theme.palette["surface"], svg)

    def test_line_numbers_render(self) -> None:
        block = code_blocks.CodeBlock(language="python", text="a = 1\nb = 2\nc = 3", line_numbers=True)
        svg = code_blocks.render_code_svg(block, theme=self.theme)
        # Each line number must appear.
        self.assertIn(">1<", svg)
        self.assertIn(">2<", svg)
        self.assertIn(">3<", svg)

    def test_highlight_band_rendered(self) -> None:
        block = code_blocks.CodeBlock(language="python", text="a\nb\nc\nd", highlight=[2, 4])
        svg = code_blocks.render_code_svg(block, theme=self.theme)
        # Two extra highlight bands using accent color with fill-opacity.
        self.assertEqual(svg.count('fill-opacity="0.18"'), 2)
        self.assertIn(self.theme.palette["accent"], svg)

    def test_unknown_language_falls_back_gracefully(self) -> None:
        block = code_blocks.CodeBlock(language="not-a-real-lang-xyz", text="anything here")
        svg = code_blocks.render_code_svg(block, theme=self.theme)
        # Should still produce some SVG without crashing.
        self.assertIn("<text", svg)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
