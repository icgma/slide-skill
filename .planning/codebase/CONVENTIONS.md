---
last_mapped_commit: fa4b24c317ed091b8d6132314e40e1bbf3e46eba
mapped_at: 2026-05-03
mapper: quality
---

# CONVENTIONS

## Module style
- **Function-first**, not class-first. Each pipeline stage is a top-level function (`init_project`, `convert_file`, `create_spec`, `generate_svg`, `finalize_svg`, `export_project`).
- Classes are reserved for **registries** (`ConverterRegistry` in `converters.py`) and **value objects** (`@dataclass ThemeSpec`, `@dataclass SvgIssue`).
- Configuration objects passed as **dicts loaded from JSON** (`project.json`, `spec_lock.json`); structured at the boundary, dict-shaped inside.

## CLI pattern (`cli.py`)
- `argparse` with `subparsers.add_parser(...)`. Sole entry point: `main(argv=None)` → `_dispatch(args)` containing one `if/elif` per subcommand.
- Subcommands (alphabetic): `init`, `import-sources`, `spec`, `generate-guide`, `svg`, `finalize-svg`, `check-svg`, `export`, `render`, `narrate`, `rehearse`, `snapshot`, `qa`, `quickstart`, `competition`, …
- `quickstart` flags: `--theme`, `--base`, `--name`, `--format`, `--competition`. **No** `--output-dir` (project always goes under `<base>/<name>/`).

## Theme pattern (`themes.py`)
```python
@dataclass                                            # NOT frozen
class ThemeSpec:
    name: str
    palette: dict[str, str]
    font_family: str                                  # CSS stack incl. CJK fallbacks
    design_hints: str
    layout_rhythm: list[str] = field(default_factory=lambda: ["anchor", "breathing", "dense"])

THEMES: dict[str, ThemeSpec] = {                      # 5 presets (themes.py:19)
    "dark-tech": ThemeSpec(...), "light-corporate": ..., "warm-editorial": ...,
    "data-forward": ..., "vibrant-startup": ...,
}

def get_theme(name: str) -> ThemeSpec: ...            # falls back to "dark-tech"
def list_themes() -> list[ThemeSpec]: ...             # returns objects, not names
```
CJK font stacks are baked into every preset, e.g. dark-tech ships with
`"Aptos, Arial, 'Microsoft YaHei', 'PingFang SC', 'Noto Sans SC', 'Source Han Sans SC', sans-serif"`.

## Project I/O contract
- `init_project(name, format, base_dir, overwrite=False)` → creates `<base>/<name>/` with `REQUIRED_DIRS` (see `STRUCTURE.md`) and writes `project.json`:
  ```json
  { "name": "...", "title": "...", "format": "16:9",
    "canvas": {"width_emu": ..., "height_emu": ..., "ratio": "16:9"},
    "created_at": "ISO-8601" }
  ```
- All subsequent commands accept the **project root path**, not the name.

## Naming
- Source files & functions: `snake_case`.
- Generated SVGs: `slide_NN.svg` (zero-padded to 2 digits).
- Exports: `<name>_<YYYYMMDD_HHMMSS>.pptx` under `exports/`.

## Error handling
- Library code raises `RuntimeError`, `FileNotFoundError`, `ValueError`.
- Top-level CLI catches in `cli.py` (`# noqa: BLE001`), prints to `stderr`, exits with `sys.exit(1)`.
- Demo (`tools/slide-demo/app.py`) catches at request boundary, scrubs message, calls `log.exception`, returns JSON.

## Type hints
- Pervasive Python 3.11+ syntax (`list[str] | None`, `dict[str, ThemeSpec]`).
- No `mypy` config currently; hints are documentation-grade, not strictly enforced.

## Markdown source format (what the Strategist consumes)
| Markdown | Effect |
|---|---|
| `# Title` | Deck title (cover slide) |
| `> subtitle` | Cover subtitle |
| `## Slide title` | New slide |
| `**42%**` etc. | Triggers metric-highlight layout |
| `### A` + `### B` (sibling H3) | Two-column comparison layout |
| `- item` | Bullet list |
| `![alt](path)` | Image (resolved relative to `sources/`) |

## Commit / version conventions
- Git tags: `v<MAJOR.MINOR>` (latest: `v2.1`).
- README badges + INTEGRATION-TEST-RESULTS.md updated alongside releases.
