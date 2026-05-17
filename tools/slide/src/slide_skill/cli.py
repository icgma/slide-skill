"""Command line interface for Slide Skill v2.0."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .exporter import export_project, pptx_notes, pptx_text, validate_pptx
from .intake import convert_file, url_to_markdown
from .project import import_sources, init_project, validate_project
from .qa import run_qa
from .render import render_environment_report, render_pptx
from .svg_pipeline import create_spec, finalize_svg, generate_guide, generate_svg, write_svg_report
from .template_ops import (
    delete_slides,
    duplicate_slide,
    inspect_template,
    reorder_slides,
    replace_text,
    replacements_from_json,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="slide-skill")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create a deck project workspace")
    p_init.add_argument("name")
    p_init.add_argument("--format", default="ppt169")
    p_init.add_argument("--base", default="projects")
    p_init.add_argument("--overwrite", action="store_true")
    p_init.add_argument("--theme", default="dark-tech", help="Visual theme (dark-tech, light-corporate, warm-editorial, data-forward, vibrant-startup)")
    p_init.add_argument("--competition", default=None, help="Competition template (internet-plus, challenge-cup, math-modeling, innovation-training, thesis-defense, course-presentation)")

    p_import = sub.add_parser("import-sources", help="Copy or move source files into a project")
    p_import.add_argument("project")
    p_import.add_argument("sources", nargs="+")
    p_import.add_argument("--move", action="store_true")

    p_validate = sub.add_parser("validate", help="Validate a project workspace")
    p_validate.add_argument("project")

    p_source = sub.add_parser("source-to-md", help="Convert source material to Markdown")
    p_source.add_argument("source")
    p_source.add_argument("-o", "--output")
    p_source.add_argument("--url", action="store_true")

    p_spec = sub.add_parser("spec", help="Create design_spec.md and spec_lock.json")
    p_spec.add_argument("project")
    p_spec.add_argument("--source")
    p_spec.add_argument("--title")
    p_spec.add_argument("--theme", default="dark-tech", help="Visual theme name")

    p_guide = sub.add_parser("generate-guide", help="Generate per-slide SVG authoring prompt for the AI Executor role")
    p_guide.add_argument("project")
    p_guide.add_argument("--source", required=True, help="Source Markdown file")
    p_guide.add_argument("--theme", default=None, help="Visual theme name (overrides spec_lock.json)")
    p_guide.add_argument("--max-slides", type=int, default=12)

    p_svg = sub.add_parser("svg", help="Generate SVG pages from Markdown (programmatic fallback)")
    p_svg.add_argument("project")
    p_svg.add_argument("--source", required=True)
    p_svg.add_argument("--max-slides", type=int, default=12)

    p_check = sub.add_parser("check-svg", help="Run SVG quality gate")
    p_check.add_argument("project")
    p_check.add_argument("--stage", default="output", choices=["output", "final"])

    p_finalize = sub.add_parser("finalize-svg", help="Finalize SVG pages for export")
    p_finalize.add_argument("project")

    p_export = sub.add_parser("export", help="Export finalized SVG pages to PPTX")
    p_export.add_argument("project")
    p_export.add_argument("-o", "--output")
    p_export.add_argument("--stage", default="final", choices=["output", "final"])

    p_qa = sub.add_parser("qa", help="Run QA checks")
    p_qa.add_argument("project")
    p_qa.add_argument("--pptx")
    p_qa.add_argument("--strict", action="store_true", help="Require visual QA and fix-and-verify evidence")
    p_qa.add_argument("--require-visual", action="store_true", help="Require rendered images and VISUAL-REVIEW.md")
    p_qa.add_argument("--require-fix-verify", action="store_true", help="Require FIX-VERIFY.md evidence")

    p_render = sub.add_parser("render", help="Render PPTX to per-slide JPEG images for visual QA")
    p_render.add_argument("pptx")
    p_render.add_argument("-o", "--output-dir", required=True)
    p_render.add_argument("--dpi", type=int, default=150)

    p_pdf = sub.add_parser("pdf", help="Export a project or PPTX to PDF")
    p_pdf.add_argument("input", help="Project directory or .pptx file")
    p_pdf.add_argument("-o", "--output", required=True, help="Output .pdf path")
    p_pdf.add_argument("--backend", default="soffice", choices=["soffice", "cairo"],
                       help="Conversion backend (cairo skips LibreOffice; needs cairosvg + pypdf)")
    p_pdf.add_argument("--quality", default="standard", choices=["draft", "standard", "print"],
                       help="Embedded raster DPI tier (cairo backend only)")

    sub.add_parser("render-doctor", help="Check LibreOffice/Poppler render dependencies")

    p_text = sub.add_parser("pptx-text", help="Extract text from a PPTX")
    p_text.add_argument("pptx")

    p_notes = sub.add_parser("pptx-notes", help="Extract embedded speaker notes from a PPTX")
    p_notes.add_argument("pptx")

    p_pptx_validate = sub.add_parser("validate-pptx", help="Validate PPTX package/native editability")
    p_pptx_validate.add_argument("pptx")

    p_inspect = sub.add_parser("template-inspect", help="Inspect a PPTX template")
    p_inspect.add_argument("pptx")

    p_replace = sub.add_parser("template-replace", help="Replace template text using a JSON mapping")
    p_replace.add_argument("input")
    p_replace.add_argument("output")
    p_replace.add_argument("--map", required=True)

    p_delete = sub.add_parser("template-delete", help="Delete slides from a PPTX")
    p_delete.add_argument("input")
    p_delete.add_argument("output")
    p_delete.add_argument("--slides", required=True, help="Comma-separated slide numbers")

    p_reorder = sub.add_parser("template-reorder", help="Reorder slides in a PPTX")
    p_reorder.add_argument("input")
    p_reorder.add_argument("output")
    p_reorder.add_argument("--order", required=True, help="Comma-separated full slide order")

    p_duplicate = sub.add_parser("template-duplicate", help="Duplicate one slide")
    p_duplicate.add_argument("input")
    p_duplicate.add_argument("output")
    p_duplicate.add_argument("--slide", type=int, required=True)

    p_plan = sub.add_parser("plan", help="Generate a structured slide plan from Markdown (review before generating)")
    p_plan.add_argument("source", help="Source Markdown file")
    p_plan.add_argument("--domain", default="general", choices=["teaching", "course", "competition", "general"],
                        help="Content domain for layout/density decisions")
    p_plan.add_argument("--max-items", type=int, default=6, help="Max content items per slide")
    p_plan.add_argument("--pinyin", action="store_true", help="Show pinyin annotations (teaching domain)")
    p_plan.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON instead of markdown table")
    p_plan.add_argument("--max-slides", type=int, default=20, help="Maximum number of slides")

    p_quick = sub.add_parser("quickstart", help="Run source-to-PPTX pipeline end-to-end")
    p_quick.add_argument("source")
    p_quick.add_argument("--name")
    p_quick.add_argument("--format", default="ppt169")
    p_quick.add_argument("--base", default="projects")
    p_quick.add_argument("--theme", default="dark-tech", help="Visual theme name")
    p_quick.add_argument("--competition", default=None, help="Competition template")

    p_build = sub.add_parser("build", help="Plan-driven source-to-PPTX (v3 pipeline with domain awareness)")
    p_build.add_argument("source")
    p_build.add_argument("--name", default=None)
    p_build.add_argument("--format", default="ppt169")
    p_build.add_argument("--base", default="projects")
    p_build.add_argument("--theme", default="dark-tech", help="Visual theme name")
    p_build.add_argument("--domain", default="general", choices=["teaching", "course", "competition", "general"],
                         help="Content domain for layout/density decisions")
    p_build.add_argument("--max-items", type=int, default=6, help="Max content items per slide")
    p_build.add_argument("--pinyin", action="store_true", help="Show pinyin annotations (teaching domain)")
    p_build.add_argument("--max-slides", type=int, default=20, help="Maximum number of slides")

    p_preview = sub.add_parser("preview", help="Build deck with plan + open instant HTML preview in browser")
    p_preview.add_argument("source")
    p_preview.add_argument("--name", default=None)
    p_preview.add_argument("--format", default="ppt169")
    p_preview.add_argument("--base", default="projects")
    p_preview.add_argument("--theme", default="dark-tech", help="Visual theme name")
    p_preview.add_argument("--domain", default="general", choices=["teaching", "course", "competition", "general"],
                           help="Content domain for layout/density decisions")
    p_preview.add_argument("--max-items", type=int, default=6, help="Max content items per slide")
    p_preview.add_argument("--pinyin", action="store_true", help="Show pinyin annotations (teaching domain)")
    p_preview.add_argument("--max-slides", type=int, default=20, help="Maximum number of slides")
    p_preview.add_argument("--no-open", action="store_true", help="Don't auto-open browser")

    p_adjust = sub.add_parser("adjust", help="Regenerate a specific slide in an existing project")
    p_adjust.add_argument("project", help="Path to existing project directory")
    p_adjust.add_argument("slide", type=int, help="Slide number to regenerate (1-based)")
    p_adjust.add_argument("--title", default=None, help="New title for the slide")
    p_adjust.add_argument("--body", default=None, help="New body content for the slide (Markdown)")
    p_adjust.add_argument("--layout", default=None, help="Force a specific layout (e.g. vocab-card, dialogue, bullet-list)")
    p_adjust.add_argument("--body-file", default=None, help="Read body content from a file instead of --body")

    p_narrate = sub.add_parser("narrate", help="Generate TTS audio from speaker notes")
    p_narrate.add_argument("project")
    p_narrate.add_argument("--voice", default=None, help="Voice name (engine-specific)")
    p_narrate.add_argument("--engine", default="edge-tts", choices=["edge-tts", "mimo"], help="TTS engine")
    p_narrate.add_argument("--style", default="", help="MiMo: natural language style instruction")
    p_narrate.add_argument("--voice-clone", default=None, help="MiMo: path to mp3/wav sample for voice cloning")
    p_narrate.add_argument("--voice-design", default=None, help="MiMo: text description for voice design")

    p_voices = sub.add_parser("voices", help="List available TTS voices")
    p_voices.add_argument("--locale", default="")
    p_voices.add_argument("--engine", default="edge-tts", choices=["edge-tts", "mimo"], help="TTS engine")

    sub.add_parser("formats", help="List available canvas format presets")
    sub.add_parser("themes", help="List available visual design themes")
    sub.add_parser("competitions", help="List available competition templates")

    p_templates = sub.add_parser(
        "templates",
        help="List 80 named slide templates across 10 categories (business / pitch / "
             "product / report / education / academic / marketing / government / tech / training)",
    )
    p_templates.add_argument(
        "--category", default=None,
        help="Filter to one category slug (e.g. business, pitch, product, ...). "
             "Omit to list every template grouped by category.",
    )
    p_templates.add_argument(
        "--show", default=None,
        help="Show full details (theme, layouts, sample outline) for one template slug.",
    )

    p_tquick = sub.add_parser(
        "template-quickstart",
        help="Scaffold a deck from a named template — creates project + sample outline.",
    )
    p_tquick.add_argument("slug", help="Template slug, e.g. biz-mck-strategy")
    p_tquick.add_argument("--name", default=None, help="Project name (defaults to template slug)")
    p_tquick.add_argument("--title", default=None, help="Deck title (defaults to template name)")
    p_tquick.add_argument("--format", default="ppt169")
    p_tquick.add_argument("--base", default="projects")
    p_tquick.add_argument("--overwrite", action="store_true")

    p_theme = sub.add_parser("theme", help="Manage user-installed theme plugins")
    theme_sub = p_theme.add_subparsers(dest="theme_command", required=True)
    p_theme_add = theme_sub.add_parser("add", help="Install a TOML theme file into ~/.config/slide-skill/themes/")
    p_theme_add.add_argument("path", help="Path to a TOML theme file")
    p_theme_add.add_argument("--overwrite", action="store_true")
    p_theme_remove = theme_sub.add_parser("remove", help="Delete a user-installed theme")
    p_theme_remove.add_argument("name")
    theme_sub.add_parser("list", help="List all available themes with their source")

    p_rehearse = sub.add_parser("rehearse", help="Estimate presentation timing from speaker notes")
    p_rehearse.add_argument("project")
    p_rehearse.add_argument("--time-limit", type=float, default=None, help="Time limit in minutes")

    p_draft = sub.add_parser("draft-notes", help="Generate speaker note drafts from slide content")
    p_draft.add_argument("project")
    p_draft.add_argument("--overwrite", action="store_true", help="Overwrite existing notes")

    p_html = sub.add_parser("html-preview", help="Render a self-contained HTML presenter from svg_final/")
    p_html.add_argument("project")
    p_html.add_argument("-o", "--output", default=None, help="Output .html path (default: <project>/exports/preview.html)")
    p_html.add_argument("--title", default="Slide Preview")
    p_html.add_argument("--lang", default=None, help="ISO language code; defaults to spec_lock.json lang or 'en'")

    p_pf = sub.add_parser("font-preflight", help="Scan deck text for missing-glyph / RTL handling issues")
    p_pf.add_argument("project")
    p_pf.add_argument("--theme", default=None, help="Theme name; defaults to spec_lock.json theme")
    p_pf.add_argument("--lang", default=None, help="Force language code (else autodetected)")

    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "init":
        print(init_project(args.name, args.format, args.base, args.overwrite, competition=args.competition))
    elif args.command == "import-sources":
        paths = import_sources(args.project, [Path(item) for item in args.sources], move=args.move)
        print("\n".join(str(path) for path in paths))
    elif args.command == "validate":
        ok, errors = validate_project(args.project)
        print("valid" if ok else "invalid")
        for error in errors:
            print(f"- {error}")
        return 0 if ok else 1
    elif args.command == "source-to-md":
        markdown = url_to_markdown(args.source, args.output) if args.url else convert_file(args.source, args.output)
        if not args.output:
            print(markdown)
    elif args.command == "spec":
        theme = getattr(args, "theme", "dark-tech") or "dark-tech"
        spec, lock = create_spec(args.project, args.source, args.title, theme_name=theme)
        print(spec)
        print(lock)
    elif args.command == "generate-guide":
        theme = getattr(args, "theme", None)
        prompt = generate_guide(args.project, args.source, theme_name=theme or "dark-tech", max_slides=args.max_slides)
        print(prompt)
    elif args.command == "svg":
        for path in generate_svg(args.project, args.source, args.max_slides):
            print(path)
    elif args.command == "check-svg":
        report = write_svg_report(args.project, args.stage)
        print(report)
        return 0 if "status: passed" in report.read_text(encoding="utf-8") else 1
    elif args.command == "finalize-svg":
        for path in finalize_svg(args.project):
            print(path)
    elif args.command == "export":
        print(export_project(args.project, args.output, args.stage))
    elif args.command == "qa":
        ok, report = run_qa(
            args.project,
            args.pptx,
            require_visual=args.strict or args.require_visual,
            require_fix_verify=args.strict or args.require_fix_verify,
        )
        print(report)
        return 0 if ok else 1
    elif args.command == "render":
        for path in render_pptx(args.pptx, args.output_dir, args.dpi):
            print(path)
    elif args.command == "pdf":
        from .pdf_export import export_pdf
        out = export_pdf(args.input, args.output, backend=args.backend, quality=args.quality)
        print(out)
    elif args.command == "render-doctor":
        print(render_environment_report(), end="")
    elif args.command == "pptx-text":
        print(pptx_text(args.pptx))
    elif args.command == "pptx-notes":
        print(pptx_notes(args.pptx))
    elif args.command == "validate-pptx":
        ok, errors = validate_pptx(args.pptx)
        print("valid" if ok else "invalid")
        for error in errors:
            print(f"- {error}")
        return 0 if ok else 1
    elif args.command == "template-inspect":
        import json
        print(json.dumps(inspect_template(args.pptx), ensure_ascii=False, indent=2))
    elif args.command == "template-replace":
        print(replace_text(args.input, args.output, replacements_from_json(args.map)))
    elif args.command == "template-delete":
        print(delete_slides(args.input, args.output, _numbers(args.slides)))
    elif args.command == "template-reorder":
        print(reorder_slides(args.input, args.output, _numbers(args.order)))
    elif args.command == "template-duplicate":
        print(duplicate_slide(args.input, args.output, args.slide))
    elif args.command == "plan":
        import json as _json
        from .content_planner import ContentConfig, plan_slides, plan_to_json, plan_to_markdown
        source_text = Path(args.source).read_text(encoding="utf-8")
        cfg = ContentConfig(
            domain=args.domain,
            max_items_per_slide=args.max_items,
            show_pinyin=args.pinyin,
            max_slides=args.max_slides,
        )
        plans = plan_slides(source_text, cfg)
        if args.as_json:
            print(_json.dumps(plan_to_json(plans), ensure_ascii=False, indent=2))
        else:
            print(plan_to_markdown(plans))
    elif args.command == "quickstart":
        name = args.name or Path(args.source).stem
        theme = getattr(args, "theme", "dark-tech") or "dark-tech"
        project = init_project(name, args.format, args.base, overwrite=True, competition=args.competition)
        source_md = project / "sources" / (Path(args.source).stem + ".md")
        convert_file(args.source, source_md)
        original = Path(args.source)
        if original.resolve() != source_md.resolve():
            dest_original = project / "sources" / original.name
            if not dest_original.exists():
                shutil.copy2(original, dest_original)
        create_spec(project, source_md, theme_name=theme)
        generate_svg(project, source_md)
        write_svg_report(project)
        finalize_svg(project)
        deck = export_project(project)
        ok, report = run_qa(project, deck)
        print(f"project: {project}")
        print(f"deck: {deck}")
        print(f"qa: {report}")
        return 0 if ok else 1
    elif args.command == "build":
        from .content_planner import ContentConfig, plan_slides, plan_to_markdown
        from .svg_pipeline import generate_svg_from_plan
        name = args.name or Path(args.source).stem
        theme = getattr(args, "theme", "dark-tech") or "dark-tech"
        project = init_project(name, args.format, args.base, overwrite=True)
        # Read and convert source
        source_md = project / "sources" / (Path(args.source).stem + ".md")
        convert_file(args.source, source_md)
        original = Path(args.source)
        if original.resolve() != source_md.resolve():
            dest_original = project / "sources" / original.name
            if not dest_original.exists():
                shutil.copy2(original, dest_original)
        create_spec(project, source_md, theme_name=theme)
        # Plan slides with domain awareness
        source_text = source_md.read_text(encoding="utf-8")
        cfg = ContentConfig(
            domain=args.domain,
            max_items_per_slide=args.max_items,
            show_pinyin=args.pinyin,
            max_slides=args.max_slides,
        )
        plans = plan_slides(source_text, cfg)
        # Show plan summary
        print(plan_to_markdown(plans))
        print()
        # Render from plan
        generate_svg_from_plan(project, plans)
        write_svg_report(project)
        finalize_svg(project)
        deck = export_project(project)
        ok, report = run_qa(project, deck)
        print(f"project: {project}")
        print(f"deck: {deck}")
        print(f"qa: {report}")
        return 0 if ok else 1
    elif args.command == "preview":
        import webbrowser
        from .content_planner import ContentConfig, plan_slides, plan_to_markdown
        from .svg_pipeline import generate_svg_from_plan
        from .html_preview import write_preview_html
        name = args.name or Path(args.source).stem
        theme = getattr(args, "theme", "dark-tech") or "dark-tech"
        project = init_project(name, args.format, args.base, overwrite=True)
        source_md = project / "sources" / (Path(args.source).stem + ".md")
        convert_file(args.source, source_md)
        original = Path(args.source)
        if original.resolve() != source_md.resolve():
            dest_original = project / "sources" / original.name
            if not dest_original.exists():
                shutil.copy2(original, dest_original)
        create_spec(project, source_md, theme_name=theme)
        source_text = source_md.read_text(encoding="utf-8")
        cfg = ContentConfig(
            domain=args.domain,
            max_items_per_slide=args.max_items,
            show_pinyin=args.pinyin,
            max_slides=args.max_slides,
        )
        plans = plan_slides(source_text, cfg)
        print(plan_to_markdown(plans))
        print()
        generate_svg_from_plan(project, plans)
        write_svg_report(project)
        finalize_svg(project)
        # Generate HTML preview
        lock_path = project / "spec_lock.json"
        lang = "en"
        preview_title = name
        if lock_path.exists():
            import json as _json
            lock = _json.loads(lock_path.read_text(encoding="utf-8"))
            lang = lock.get("lang", "en")
            preview_title = lock.get("title", name)
        html_out = project / "exports" / "preview.html"
        write_preview_html(project, html_out, title=preview_title, lang=lang)
        print(f"project: {project}")
        print(f"preview: {html_out}")
        if not args.no_open:
            webbrowser.open(html_out.as_uri())
        return 0
    elif args.command == "adjust":
        import json as _json
        from .svg_pipeline import _render_slide_svg
        project = Path(args.project)
        if not project.exists():
            print(f"error: project not found: {project}", file=sys.stderr)
            return 1
        lock_path = project / "spec_lock.json"
        if not lock_path.exists():
            print(f"error: no spec_lock.json in {project}", file=sys.stderr)
            return 1
        spec_lock = _json.loads(lock_path.read_text(encoding="utf-8"))
        slide_idx = args.slide
        svg_dir = project / "svg_output"
        svg_file = svg_dir / f"slide_{slide_idx:02d}.svg"
        if not svg_file.exists():
            print(f"error: slide {slide_idx} not found ({svg_file})", file=sys.stderr)
            return 1
        # Count total slides
        total = len(list(svg_dir.glob("*.svg")))
        # Get body content
        body = ""
        if args.body_file:
            body = Path(args.body_file).read_text(encoding="utf-8")
        elif args.body:
            body = args.body
        # Get title
        title = args.title or f"Slide {slide_idx}"
        layout = args.layout
        # Regenerate
        svg = _render_slide_svg(
            slide_idx, title, body, spec_lock, total,
            layout=layout,
        )
        svg_file.write_text(svg, encoding="utf-8")
        # Also update svg_final
        final_file = project / "svg_final" / f"slide_{slide_idx:02d}.svg"
        if final_file.parent.exists():
            final_file.write_text(svg, encoding="utf-8")
        print(f"adjusted: {svg_file}")
        print(f"Re-run `slide-skill html-preview {project}` to refresh the preview.")
        return 0
    elif args.command == "narrate":
        from .narrate import narrate_project
        voice = args.voice or ("冰糖" if args.engine == "mimo" else "zh-CN-XiaoxiaoNeural")
        paths = narrate_project(
            args.project,
            voice,
            engine=args.engine,
            style=args.style,
            voice_clone_sample=Path(args.voice_clone) if args.voice_clone else None,
            voice_design_prompt=args.voice_design,
        )
        for path in paths:
            print(path)
        if not paths:
            print("No speaker notes found — nothing to narrate.")
    elif args.command == "voices":
        from .narrate import list_available_voices
        voices = list_available_voices(args.locale, engine=args.engine)
        for v in voices:
            print(v)
    elif args.command == "formats":
        from .formats import CANVAS_FORMATS
        print(f"{'Name':<12} {'Ratio':<8} {'Size':<15} {'Use Case'}")
        print("-" * 65)
        for fmt in CANVAS_FORMATS.values():
            print(f"{fmt.name:<12} {fmt.ratio:<8} {fmt.width}x{fmt.height:<10} {fmt.use_case}")
    elif args.command == "themes":
        from .themes import list_themes
        themes = list_themes()
        print(f"{'Name':<22} {'Font':<30} {'Direction'}")
        print("-" * 90)
        for t in themes:
            direction = t.design_hints[:55].rstrip() + "…"
            font_short = t.font_family.split(",")[0].strip()
            print(f"{t.name:<22} {font_short:<30} {direction}")
    elif args.command == "theme":
        from .themes import install_user_theme, list_themes, remove_user_theme, user_themes_dir
        if args.theme_command == "add":
            dest = install_user_theme(args.path, overwrite=args.overwrite)
            print(f"installed: {dest}")
        elif args.theme_command == "remove":
            dest = remove_user_theme(args.name)
            print(f"removed: {dest}")
        elif args.theme_command == "list":
            print(f"User themes dir: {user_themes_dir()}")
            print(f"{'Name':<22} {'Source':<40} {'Font'}")
            print("-" * 100)
            for t in list_themes():
                font_short = t.font_family.split(",")[0].strip()
                print(f"{t.name:<22} {t.source:<40} {font_short}")
    elif args.command == "templates":
        from .templates import (
            CATEGORIES, get_template, list_categories, list_templates,
        )
        if args.show:
            spec = get_template(args.show)
            print(f"Slug:     {spec.slug}")
            print(f"分类:     {spec.category_label}")
            print(f"中文名:   {spec.name_zh}")
            print(f"英文名:   {spec.name_en}")
            print(f"主题:     {spec.theme}")
            print(f"布局:     {' → '.join(spec.layouts)}")
            print(f"用途:     {spec.persona}")
            print(f"示例提纲:")
            for i, h in enumerate(spec.outline, 1):
                print(f"  {i}. {h}")
            print()
            print(f"快速生成:  slide-skill template-quickstart {spec.slug} --title <你的标题>")
            return 0
        if args.category:
            templates = list_templates(args.category)
            print(f"## {CATEGORIES[args.category]} ({len(templates)} 个模板)")
            print(f"{'Slug':<26} {'中文名':<22} {'主题':<22} {'用途'}")
            print("-" * 110)
            for t in templates:
                print(f"{t.slug:<26} {t.name_zh:<22} {t.theme:<22} {t.persona}")
            return 0
        cats = list_categories()
        total = sum(c[2] for c in cats)
        print(f"# {total} templates across {len(cats)} categories")
        print(f"# Use `--category <slug>` to drill in, `--show <slug>` for details.\n")
        for slug, label, count in cats:
            print(f"  {slug:<12} {count:>2} 个   {label}")
        return 0
    elif args.command == "template-quickstart":
        from .templates import get_template, template_outline_markdown
        spec = get_template(args.slug)
        name = args.name or spec.slug
        project = init_project(name, args.format, args.base, overwrite=args.overwrite)
        source_md = project / "sources" / f"{spec.slug}.md"
        source_md.write_text(template_outline_markdown(spec, args.title), encoding="utf-8")
        create_spec(project, source_md, title=args.title or spec.name_zh, theme_name=spec.theme)
        print(f"project:    {project}")
        print(f"template:   {spec.slug}  ({spec.category_label})")
        print(f"theme:      {spec.theme}")
        print(f"source:     {source_md}  (填入正文后再运行下面命令)")
        print(f"next:       slide-skill svg {project} --source {source_md}")
        print(f"            slide-skill finalize-svg {project} && slide-skill export {project}")
        return 0
    elif args.command == "competitions":
        from .competition import list_competitions
        comps = list_competitions()
        print(f"{'ID':<22} {'名称':<24} {'时限':<8} {'页数':<10} {'章节数'}")
        print("-" * 85)
        for c in comps:
            pages = f"{c.page_range[0]}-{c.page_range[1]}"
            print(f"{c.name:<22} {c.name_zh:<24} {c.time_limit_minutes}min{' ':<4} {pages:<10} {len(c.sections)}")
    elif args.command == "rehearse":
        from .rehearse import format_rehearsal_report, rehearse_project
        report = rehearse_project(args.project, time_limit_minutes=args.time_limit)
        print(format_rehearsal_report(report))
        return 1 if report.over_limit else 0
    elif args.command == "html-preview":
        import json as _json
        from .html_preview import write_preview_html
        project = Path(args.project)
        lang = args.lang
        if lang is None:
            lock = project / "spec_lock.json"
            if lock.exists():
                try:
                    lang = _json.loads(lock.read_text(encoding="utf-8")).get("lang", "en")
                except Exception:  # noqa: BLE001
                    lang = "en"
            else:
                lang = "en"
        out = Path(args.output) if args.output else project / "exports" / "preview.html"
        path = write_preview_html(project, out, title=args.title, lang=lang or "en")
        print(path)
    elif args.command == "font-preflight":
        import json as _json
        from .i18n import font_preflight_project
        from .themes import get_theme
        project = Path(args.project)
        theme_name = args.theme
        if theme_name is None and (project / "spec_lock.json").exists():
            try:
                theme_name = _json.loads((project / "spec_lock.json").read_text(encoding="utf-8")).get("theme")
            except Exception:  # noqa: BLE001
                theme_name = None
        theme = get_theme(theme_name or "dark-tech")
        report = font_preflight_project(theme, project, lang=args.lang)
        print(f"language: {report.language}")
        if not report.findings:
            print("- ok: no issues found.")
        for f in report.findings:
            print(f"- {f.severity} {f.code}: {f.message}")
        return 0 if not any(f.severity in {"error", "warn"} for f in report.findings) else 1
    elif args.command == "draft-notes":
        from .draft_notes import draft_notes
        created = draft_notes(args.project, overwrite=args.overwrite)
        for path in created:
            print(path)
        if not created:
            print("All slides already have notes. Use --overwrite to regenerate.")
    return 0


def _numbers(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
