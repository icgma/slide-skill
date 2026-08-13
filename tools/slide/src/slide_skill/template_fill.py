"""School-template fidelity fill: thesis Markdown + mandated .pptx template in,
filled editable deck + risk reports out — without redesigning the template.

The school template is a delivery requirement; AI redesign is the failure
mode. This module composes the ZIP-level template primitives (analyze /
duplicate_slide / delete_slides / replace_text_scoped) into one deterministic
workflow plus the two checks competitor thesis-skills proved essential:
text-overflow estimation and stale-template-text scanning.

Everything here is deterministic — no LLM involved.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from .intake import _presentation_slide_names
from .template_ops import (
    A_NS,
    P_NS,
    delete_slides,
    duplicate_slide,
    replace_text_scoped,
    shape_paragraph_texts,
)
from .text_wrap import _strip_inline_md, _visual_wrap

EMU_PER_PT = 12700
_SHAPE_PADDING_EMU = 91440  # default ~0.1in text-box inset per side
_LINE_HEIGHT = 1.35
_OVERFLOW_THRESHOLD = 0.15  # estimation is approximate — only report >15% overshoot
_DEFAULT_FONT_PT = 18.0

_TOC_RE = re.compile(r"目录|提纲|CONTENTS|AGENDA|OUTLINE", re.IGNORECASE)
_ENDING_RE = re.compile(r"谢|Thank|Q&A|感谢", re.IGNORECASE)
_META_RE = re.compile(r"答辩人|汇报人|报告人|指导教师|导师|专业|学号|日期|20\d{2}")
_PLACEHOLDER_RE = re.compile(
    r"点击(输入|添加)|Click to add|Lorem|TODO|待填|占位|示例文本|XXX|输入.{0,4}(标题|文本|内容)",
    re.IGNORECASE,
)
_TABLE_SEP_RE = re.compile(r"^\|[\s:\-|]+\|$")


# ---------------------------------------------------------------------------
# Content parsing (Markdown -> fill-ready structure)
# ---------------------------------------------------------------------------

@dataclass
class ContentSection:
    heading: str
    body_lines: list[str] = field(default_factory=list)


@dataclass
class FilledContent:
    title: str = ""
    meta_lines: list[str] = field(default_factory=list)
    toc_lines: list[str] = field(default_factory=list)
    sections: list[ContentSection] = field(default_factory=list)


def parse_content_markdown(md_text: str) -> FilledContent:
    """Deterministically parse thesis Markdown into fill-ready content.

    - title: first ``#`` heading
    - meta lines: blockquote lines after the title, or pre-section lines
      matching 答辩人/指导教师/日期-style patterns
    - a section whose heading looks like a table of contents (目录/提纲/…)
      feeds ``toc_lines`` instead of becoming a content section
    - all other ``##`` sections become content sections with stripped body
      lines (bullets, numbered items, paragraphs, table rows)
    """
    content = FilledContent()
    current: ContentSection | None = None
    raw_sections: list[ContentSection] = []
    for raw in md_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("```"):
            continue
        if line.startswith("# ") and not content.title and current is None:
            content.title = _strip_inline_md(line[2:]).strip()
            continue
        if line.startswith("## "):
            current = ContentSection(_strip_inline_md(line[3:]).strip())
            raw_sections.append(current)
            continue
        if current is None:
            stripped = line.lstrip(">").strip()
            if line.startswith(">") and stripped:
                content.meta_lines.append(_strip_inline_md(stripped))
            elif _META_RE.search(line) and not line.startswith("#"):
                content.meta_lines.append(_strip_inline_md(line))
            continue
        body = _to_body_line(line)
        if body:
            current.body_lines.append(body)
    for section in raw_sections:
        if _TOC_RE.search(section.heading) and not content.toc_lines:
            content.toc_lines = section.body_lines
            continue
        content.sections.append(section)
    return content


def _to_body_line(line: str) -> str:
    if _TABLE_SEP_RE.match(line):
        return ""
    if line.startswith("|") and line.endswith("|"):
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        return " | ".join(cell for cell in cells if cell)
    line = re.sub(r"^#{3,6}\s+", "", line)
    line = re.sub(r"^[-*+]\s+", "", line)
    line = line.lstrip(">").strip()
    return _strip_inline_md(line).strip()


# ---------------------------------------------------------------------------
# Template analysis (per-slide roles and text slots)
# ---------------------------------------------------------------------------

@dataclass
class ShapeSlot:
    text: str
    max_font_pt: float | None
    paragraph_count: int


@dataclass
class SlideProfile:
    number: int
    role: str  # cover | toc | content | ending
    shapes: list[ShapeSlot]
    title: ShapeSlot | None
    body: ShapeSlot | None


@dataclass
class TemplateProfile:
    path: Path
    slides: list[SlideProfile]

    @property
    def content_numbers(self) -> list[int]:
        return [slide.number for slide in self.slides if slide.role == "content"]


def analyze_template(pptx: Path | str) -> TemplateProfile:
    """Classify template slides (cover/toc/content/ending) and locate text slots.

    The TITLE slot is the largest-font text shape; the BODY slot is the
    longest remaining text shape (pure page numbers excluded).
    """
    deck = Path(pptx)
    raw = _read_slide_shapes(deck)
    total = len(raw)
    slides: list[SlideProfile] = []
    for number, shapes in raw:
        joined = "\n".join(shape.text for shape in shapes)
        if number == 1:
            role = "cover"
        elif _TOC_RE.search(joined):
            role = "toc"
        elif number == total or _ENDING_RE.search(joined):
            role = "ending"
        else:
            role = "content"
        texted = [shape for shape in shapes if shape.text.strip()]
        title = max(texted, key=lambda shape: shape.max_font_pt or 0.0, default=None)
        candidates = [
            shape for shape in texted
            if shape is not title and not shape.text.strip().isdigit()
        ]
        body = max(candidates, key=lambda shape: len(shape.text), default=None)
        slides.append(SlideProfile(number, role, shapes, title, body))
    return TemplateProfile(deck, slides)


def _read_slide_shapes(deck: Path) -> list[tuple[int, list[ShapeSlot]]]:
    try:
        with zipfile.ZipFile(deck) as zf:
            names = _presentation_slide_names(zf)
            result: list[tuple[int, list[ShapeSlot]]] = []
            for number, name in enumerate(names, start=1):
                root = ET.fromstring(zf.read(name))
                shapes: list[ShapeSlot] = []
                for sp in root.iter(f"{{{P_NS}}}sp"):
                    paragraphs = shape_paragraph_texts(sp)
                    if paragraphs is None:
                        continue
                    sizes = _font_sizes(sp)
                    shapes.append(ShapeSlot(
                        text="\n".join(paragraphs),
                        max_font_pt=max(sizes) if sizes else None,
                        paragraph_count=len(paragraphs),
                    ))
                result.append((number, shapes))
        return result
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{deck} is corrupted or not a valid PPTX archive") from exc


def _font_sizes(elem: ET.Element) -> list[float]:
    tags = (f"{{{A_NS}}}rPr", f"{{{A_NS}}}defRPr", f"{{{A_NS}}}endParaRPr")
    sizes: list[float] = []
    for node in elem.iter():
        raw = node.attrib.get("sz", "")
        if node.tag in tags and raw.isdigit():
            sizes.append(int(raw) / 100.0)
    return sizes


# ---------------------------------------------------------------------------
# Fill planning (content -> per-slide replacement maps)
# ---------------------------------------------------------------------------

@dataclass
class FillOperation:
    kind: str  # duplicate | delete | replace
    slide: int
    detail: str


@dataclass
class FillPlan:
    operations: list[FillOperation] = field(default_factory=list)
    replacements: dict[int, dict[str, str]] = field(default_factory=dict)


def build_fill_plan(profile: TemplateProfile, content: FilledContent) -> FillPlan:
    """Map parsed content onto template slots.

    Unknown slots are always left untouched — the fill never blanks template
    text it cannot confidently pair with content (校名 wordmarks, page
    numbers, navigation footers all survive verbatim).
    """
    plan = FillPlan()

    def target(slide_number: int, slot: ShapeSlot | None, new_text: str) -> None:
        if slot is None or not slot.text.strip() or not new_text or slot.text == new_text:
            return
        mapping = plan.replacements.setdefault(slide_number, {})
        if slot.text in mapping:
            return
        mapping[slot.text] = new_text
        plan.operations.append(FillOperation(
            "replace", slide_number, f"{_preview(slot.text)} -> {_preview(new_text)}",
        ))

    content_slides = [slide for slide in profile.slides if slide.role == "content"]
    for slide in profile.slides:
        if slide.role == "cover":
            if content.title:
                target(slide.number, slide.title, content.title)
            if content.meta_lines:
                meta_slot = next(
                    (shape for shape in slide.shapes
                     if shape is not slide.title and shape.text.strip()
                     and _META_RE.search(shape.text)),
                    None,
                )
                target(slide.number, meta_slot, "\n".join(content.meta_lines))
        elif slide.role == "toc":
            toc_lines = content.toc_lines or [
                f"{index}. {section.heading}"
                for index, section in enumerate(content.sections, start=1)
            ]
            target(slide.number, slide.body, "\n".join(toc_lines))
    for section, slide in zip(content.sections, content_slides):
        target(slide.number, slide.title, section.heading)
        if section.body_lines:
            target(slide.number, slide.body, "\n".join(section.body_lines))
    return plan


# ---------------------------------------------------------------------------
# Risk checks: text overflow + stale template text
# ---------------------------------------------------------------------------

@dataclass
class OverflowIssue:
    slide: int
    preview: str
    overshoot_pct: int


def check_overflow(pptx: Path | str) -> list[OverflowIssue]:
    """Estimate wrapped text height per shape and report >15% overshoots.

    Uses the shared text_wrap width model at the shape's usable width
    (extent minus default insets). The estimate is approximate — autofit,
    exotic fonts, and inherited placeholder geometry are invisible here —
    so only clear overshoots (>15%) are reported.
    """
    issues: list[OverflowIssue] = []
    deck = Path(pptx)
    try:
        with zipfile.ZipFile(deck) as zf:
            names = _presentation_slide_names(zf)
            for number, name in enumerate(names, start=1):
                root = ET.fromstring(zf.read(name))
                for sp in root.iter(f"{{{P_NS}}}sp"):
                    issue = _shape_overflow(sp, number)
                    if issue is not None:
                        issues.append(issue)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{deck} is corrupted or not a valid PPTX archive") from exc
    return issues


def _shape_overflow(sp: ET.Element, slide_number: int) -> OverflowIssue | None:
    ext = sp.find(f"{{{P_NS}}}spPr/{{{A_NS}}}xfrm/{{{A_NS}}}ext")
    txbody = sp.find(f"{{{P_NS}}}txBody")
    if ext is None or txbody is None:
        return None
    try:
        cx = int(ext.attrib.get("cx", "0"))
        cy = int(ext.attrib.get("cy", "0"))
    except ValueError:
        return None
    if cx <= 0 or cy <= 0:
        return None
    shape_sizes = _font_sizes(sp)
    shape_default = max(shape_sizes) if shape_sizes else _DEFAULT_FONT_PT
    usable_width_pt = max(1.0, (cx - 2 * _SHAPE_PADDING_EMU) / EMU_PER_PT)
    height_pt = 0.0
    visible: list[str] = []
    for para in txbody.findall(f"{{{A_NS}}}p"):
        text = "".join(node.text or "" for node in para.iter(f"{{{A_NS}}}t"))
        para_sizes = _font_sizes(para)
        font_pt = max(para_sizes) if para_sizes else shape_default
        if text.strip():
            lines = _visual_wrap(text, int(usable_width_pt), int(round(font_pt))) or [text]
            visible.append(text)
        else:
            lines = [""]
        height_pt += len(lines) * font_pt * _LINE_HEIGHT
    if not visible:
        return None
    capacity_pt = cy / EMU_PER_PT
    overshoot = height_pt / capacity_pt - 1.0
    if overshoot <= _OVERFLOW_THRESHOLD:
        return None
    return OverflowIssue(slide_number, _preview("\n".join(visible)), round(overshoot * 100))


@dataclass
class StaleIssue:
    slide: int
    kind: str  # placeholder | survived | target-not-found
    text: str


def scan_stale(filled_pptx: Path | str, plan: FillPlan) -> list[StaleIssue]:
    """Flag leftover template text in the filled deck.

    Two classes are reported:
    - ``placeholder``: sample/placeholder patterns anywhere (点击输入…,
      Click to add, Lorem, TODO, …) — these must never ship in a defense deck
    - ``survived``: template text the fill plan intended to replace but which
      is still present (replacement failed)

    Template text the plan never targeted (page numbers, 校名 headers,
    navigation footers) is NOT flagged.
    """
    issues: list[StaleIssue] = []
    seen: set[tuple[int, str, str]] = set()
    for number, shapes in _read_slide_shapes(Path(filled_pptx)):
        joined = "\n".join(shape.text for shape in shapes)
        for line in joined.split("\n"):
            stripped = line.strip()
            if stripped and _PLACEHOLDER_RE.search(stripped):
                key = (number, "placeholder", stripped)
                if key not in seen:
                    seen.add(key)
                    issues.append(StaleIssue(number, "placeholder", _preview(stripped, 40)))
        for old in plan.replacements.get(number, {}):
            if old and old in joined:
                key = (number, "survived", old)
                if key not in seen:
                    seen.add(key)
                    issues.append(StaleIssue(number, "survived", _preview(old, 40)))
    return issues


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

@dataclass
class FillResult:
    output: Path
    report_path: Path
    plan: FillPlan
    overflow: list[OverflowIssue]
    stale: list[StaleIssue]
    verdict: str


def fill_template(
    template_pptx: Path | str,
    content_md: Path | str,
    output_pptx: Path | str,
    *,
    mapping_json: Path | str | None = None,
) -> FillResult:
    """Fill a mandated template from Markdown.

    Pipeline: analyze -> adapt page count (duplicate/delete content pages)
    -> re-analyze -> per-slide scoped replacement -> overflow + stale checks
    -> FILL-REPORT.md written next to the output deck.

    ``mapping_json`` optionally overrides/extends replacements per slide:
    ``{"3": {"旧文本": "新文本"}}``.
    """
    template = Path(template_pptx)
    content_path = Path(content_md)
    output = Path(output_pptx)
    content = parse_content_markdown(content_path.read_text(encoding="utf-8"))
    if not content.sections:
        raise ValueError(
            f"{content_path} has no content sections — need at least one '## ' heading"
        )
    profile = analyze_template(template)
    if not profile.content_numbers:
        raise ValueError(f"{template} has no content slides to fill (cover/toc/ending only)")
    overrides = _load_mapping(mapping_json) if mapping_json else {}
    operations: list[FillOperation] = []
    applied: dict[int, set[str]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work-0.pptx"
        shutil.copy2(template, work)
        need = len(content.sections)
        have = len(profile.content_numbers)
        if need > have:
            last = profile.content_numbers[-1]
            for index in range(need - have):
                step = Path(tmp) / f"work-dup-{index}.pptx"
                duplicate_slide(work, step, last)
                work = step
                operations.append(FillOperation(
                    "duplicate", last,
                    f"duplicate content page {last} (content pages {have}+{index + 1}, sections {need})",
                ))
        elif need < have:
            surplus = profile.content_numbers[need:]
            step = Path(tmp) / "work-trim.pptx"
            delete_slides(work, step, list(surplus))
            work = step
            operations.append(FillOperation(
                "delete", surplus[0],
                f"delete surplus content pages {surplus} (content pages {have} -> {need})",
            ))
        adapted = analyze_template(work)
        plan = build_fill_plan(adapted, content)
        plan.operations = operations + plan.operations
        for slide_number, mapping in overrides.items():
            slide_map = plan.replacements.setdefault(slide_number, {})
            for old, new in mapping.items():
                slide_map[old] = new
                plan.operations.append(FillOperation(
                    "replace", slide_number, f"[map] {_preview(old)} -> {_preview(new)}",
                ))
        output.parent.mkdir(parents=True, exist_ok=True)
        replace_text_scoped(work, output, plan.replacements, applied=applied)
    overflow = check_overflow(output)
    stale = scan_stale(output, plan)
    for slide_number in sorted(plan.replacements):
        done = applied.get(slide_number, set())
        for old in plan.replacements[slide_number]:
            if old not in done:
                stale.append(StaleIssue(slide_number, "target-not-found", _preview(old, 40)))
    issue_count = len(overflow) + len(stale)
    verdict = "clean" if issue_count == 0 else f"needs-review ({issue_count} issues)"
    report_path = output.parent / "FILL-REPORT.md"
    _write_report(report_path, template, content_path, output, plan, overflow, stale, verdict)
    return FillResult(output, report_path, plan, overflow, stale, verdict)


def _load_mapping(path: Path | str) -> dict[int, dict[str, str]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError('--map file must be a JSON object: {"slide": {"old": "new"}}')
    mapping: dict[int, dict[str, str]] = {}
    for slide_key, replacements in data.items():
        if not isinstance(replacements, dict):
            raise ValueError(f"--map entry for slide {slide_key} must be an object of old->new strings")
        try:
            number = int(slide_key)
        except ValueError as exc:
            raise ValueError(f"--map slide key must be an integer: {slide_key!r}") from exc
        mapping[number] = {str(old): str(new) for old, new in replacements.items()}
    return mapping


def _preview(text: str, limit: int = 20) -> str:
    flat = text.replace("\n", " ")
    return flat[:limit] + ("…" if len(flat) > limit else "")


def _write_report(
    report_path: Path,
    template: Path,
    content_path: Path,
    output: Path,
    plan: FillPlan,
    overflow: list[OverflowIssue],
    stale: list[StaleIssue],
    verdict: str,
) -> None:
    lines = [
        "# FILL-REPORT",
        "",
        f"- template: {template}",
        f"- content: {content_path}",
        f"- output: {output}",
        "",
        "## Operations",
        "",
    ]
    if plan.operations:
        lines.extend(f"- [{op.kind}] slide {op.slide}: {op.detail}" for op in plan.operations)
    else:
        lines.append("- none")
    lines += ["", "## Overflow Issues", ""]
    if overflow:
        lines.extend(
            f'- slide {issue.slide}: "{issue.preview}" estimated {issue.overshoot_pct}% over shape height'
            for issue in overflow
        )
    else:
        lines.append("- none")
    lines += ["", "## Stale Issues", ""]
    if stale:
        lines.extend(f'- slide {issue.slide} [{issue.kind}]: "{issue.text}"' for issue in stale)
    else:
        lines.append("- none")
    lines += ["", f"verdict: {verdict}", ""]
    report_path.write_text("\n".join(lines), encoding="utf-8")
