"""Tests for v1.4 Phase 23 — First-class PDF Export."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from slide_skill import pdf_export


class HelpersTests(unittest.TestCase):
    def test_quality_dpi_table(self) -> None:
        self.assertEqual(pdf_export.QUALITY_DPI["draft"], 96)
        self.assertEqual(pdf_export.QUALITY_DPI["standard"], 150)
        self.assertEqual(pdf_export.QUALITY_DPI["print"], 300)

    def test_list_finalized_svgs_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                pdf_export._list_finalized_svgs(Path(tmp))

    def test_list_finalized_svgs_returns_sorted(self) -> None:
        with TemporaryDirectory() as tmp:
            final = Path(tmp) / "svg_final"
            final.mkdir(parents=True)
            for n in (3, 1, 2):
                (final / f"slide_{n:02d}.svg").write_text("<svg/>", encoding="utf-8")
            pages = pdf_export._list_finalized_svgs(Path(tmp))
            self.assertEqual([p.name for p in pages], ["slide_01.svg", "slide_02.svg", "slide_03.svg"])

    def test_list_finalized_svgs_empty_dir_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "svg_final").mkdir(parents=True)
            with self.assertRaises(FileNotFoundError):
                pdf_export._list_finalized_svgs(Path(tmp))


class DispatchTests(unittest.TestCase):
    def test_cairo_rejects_pptx_file(self) -> None:
        with TemporaryDirectory() as tmp:
            pptx = Path(tmp) / "deck.pptx"
            pptx.write_bytes(b"PK\x03\x04stub")
            with self.assertRaises(ValueError):
                pdf_export.export_pdf(pptx, Path(tmp) / "out.pdf", backend="cairo")

    def test_soffice_backend_dispatches_to_export_pdf_soffice(self) -> None:
        with TemporaryDirectory() as tmp:
            pptx = Path(tmp) / "deck.pptx"
            pptx.write_bytes(b"PK\x03\x04stub")
            target = Path(tmp) / "out.pdf"
            with patch("slide_skill.pdf_export.export_pdf_soffice", return_value=target) as mock:
                result = pdf_export.export_pdf(pptx, target, backend="soffice")
            mock.assert_called_once()
            self.assertEqual(result, target)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
