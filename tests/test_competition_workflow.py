import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from slide_skill.competition import (
    EXAMPLE_PACK_THEMES,
    list_competitions,
    scaffold_from_example,
)
from slide_skill.project import init_project, load_project
from slide_skill.svg_pipeline import create_spec, generate_svg, finalize_svg
from slide_skill.draft_notes import draft_notes
from slide_skill.rehearse import rehearse_project
from slide_skill.exporter import export_project, validate_pptx


class TestCompetitionWorkflow(unittest.TestCase):
    def test_competition_init_creates_outline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project("Comp1", base_dir=root / "projects", competition="internet-plus")
            outline = project / "sources" / "competition_outline.md"
            self.assertTrue(outline.exists())
            self.assertIn("互联网+创新创业大赛", outline.read_text(encoding="utf-8"))

    def test_competition_init_saves_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project("Comp2", base_dir=root / "projects", competition="internet-plus")
            meta = load_project(project)
            self.assertIn("competition", meta)
            self.assertEqual(meta["competition"]["id"], "internet-plus")
            self.assertEqual(meta["competition"]["time_limit_minutes"], 8)

    def test_competition_full_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project("Comp3", base_dir=root / "projects", competition="internet-plus")
            source = project / "sources" / "competition_outline.md"

            # Use only a couple of sections to speed up test and avoid generating 20 slides
            source.write_text("# Demo Comp\n\n## Section 1\n\n### Slide 1\n\nHello\n\n### Slide 2\n\nWorld\n", encoding="utf-8")

            create_spec(project, source)
            svg_paths = generate_svg(project, source)
            self.assertGreaterEqual(len(svg_paths), 1)

            final_paths = finalize_svg(project)
            self.assertGreaterEqual(len(final_paths), 1)

            notes_paths = draft_notes(project)
            self.assertGreaterEqual(len(notes_paths), 1)

            report = rehearse_project(project)
            self.assertEqual(report.time_limit_seconds, 8 * 60)

            deck = export_project(project)
            valid, pptx_errors = validate_pptx(deck)
            self.assertTrue(valid, pptx_errors)

    def test_rehearse_auto_detects_competition_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project("Comp4", base_dir=root / "projects", competition="internet-plus")

            # create dummy svg to avoid rehearse error about no slides
            svg_dir = project / "svg_output"
            svg_dir.mkdir(parents=True, exist_ok=True)
            (svg_dir / "slide_01.svg").write_text("<svg></svg>", encoding="utf-8")

            report = rehearse_project(project)
            self.assertEqual(report.time_limit_seconds, 8 * 60)

    def test_competition_all_templates_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            comps = list_competitions()
            for comp in comps:
                project = init_project(f"Comp_{comp.name}", base_dir=root / "projects", competition=comp.name)
                outline = project / "sources" / "competition_outline.md"
                self.assertTrue(outline.exists())

    def test_competitions_cli_lists_six(self) -> None:
        comps = list_competitions()
        self.assertEqual(len(comps), 6)


class TestCompetitionExampleScaffold(unittest.TestCase):
    def test_scaffold_all_six_slugs_copies_source_and_notes(self) -> None:
        for comp in list_competitions():
            with self.subTest(slug=comp.name), tempfile.TemporaryDirectory() as tmp:
                project = init_project(
                    f"Scaffold_{comp.name}",
                    base_dir=Path(tmp) / "projects",
                    competition=comp.name,
                )
                info = scaffold_from_example(project, comp.name)

                source = Path(info["source"])
                self.assertEqual(source, project / "sources" / "source.md")
                self.assertTrue(source.is_file())
                self.assertGreater(len(source.read_text(encoding="utf-8").strip()), 200)

                notes = Path(info["notes"])
                self.assertEqual(notes, project / "notes" / "total.md")
                self.assertTrue(notes.is_file())
                self.assertIn("## Slide 1", notes.read_text(encoding="utf-8"))

                self.assertEqual(info["theme"], EXAMPLE_PACK_THEMES[comp.name])

    def test_scaffold_unknown_slug_lists_valid_slugs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = init_project("ScaffoldBad", base_dir=Path(tmp) / "projects")
            with self.assertRaises(ValueError) as ctx:
                scaffold_from_example(project, "not-a-competition")
            self.assertIn("internet-plus", str(ctx.exception))

    def test_scaffold_edit_and_quickstart_end_to_end(self) -> None:
        """COMP-06: scaffold -> edit content -> quickstart exports a deck."""
        from slide_skill.cli import main as cli_main

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "projects"
            rc = cli_main([
                "init", "ScaffoldE2E",
                "--base", str(base),
                "--competition", "course-presentation",
                "--from-example",
            ])
            self.assertEqual(rc, 0)

            project = base / "scaffolde2e"
            source = project / "sources" / "source.md"
            self.assertTrue(source.is_file())

            text = source.read_text(encoding="utf-8")
            self.assertIn("## 小组观点", text)
            source.write_text(text.replace("## 小组观点", "## 我们组的观点"), encoding="utf-8")

            rc = cli_main([
                "quickstart", str(source),
                "--theme", EXAMPLE_PACK_THEMES["course-presentation"],
                "--name", "ScaffoldE2E",
                "--base", str(base),
                "--mode", "fast",
            ])
            self.assertEqual(rc, 0)

            decks = list((project / "exports").glob("*.pptx"))
            self.assertTrue(decks, "quickstart should export a .pptx after the content edit")
            valid, errors = validate_pptx(decks[0])
            self.assertTrue(valid, errors)

    def test_init_from_example_requires_competition(self) -> None:
        from slide_skill.cli import main as cli_main

        with tempfile.TemporaryDirectory() as tmp:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                rc = cli_main(["init", "NoComp", "--base", str(Path(tmp) / "projects"), "--from-example"])
            self.assertEqual(rc, 1)
            self.assertIn("--competition", stderr.getvalue())

    def test_competitions_listing_mentions_packs_and_scaffold(self) -> None:
        from slide_skill.cli import main as cli_main

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            rc = cli_main(["competitions"])
        self.assertEqual(rc, 0)
        output = stdout.getvalue()
        self.assertIn("examples/competitions/", output)
        self.assertIn("--from-example", output)


if __name__ == "__main__":
    unittest.main()
