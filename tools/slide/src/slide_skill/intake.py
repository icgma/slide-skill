"""Source material to Markdown conversion."""

from __future__ import annotations

import html
import re
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "div", "section", "article", "h1", "h2", "h3", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text + " ")

    def markdown(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return html.unescape(text).strip() + "\n"


def convert_file(path: Path | str, output: Path | str | None = None) -> str:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix in {".md", ".markdown"}:
        markdown = source.read_text(encoding="utf-8")
    elif suffix in {".txt", ".csv", ".tsv"}:
        markdown = source.read_text(encoding="utf-8")
    elif suffix in {".html", ".htm"}:
        markdown = html_to_markdown(source.read_text(encoding="utf-8", errors="ignore"))
    elif suffix == ".docx":
        markdown = docx_to_markdown(source)
    elif suffix in {".xlsx", ".xlsm"}:
        markdown = xlsx_to_markdown(source)
    elif suffix == ".pptx":
        markdown = pptx_to_markdown(source)
    elif suffix == ".pdf":
        markdown = pdf_to_markdown(source)
    else:
        raise ValueError(f"Unsupported source format: {source.suffix}")
    if output:
        Path(output).write_text(markdown, encoding="utf-8")
    return markdown


def url_to_markdown(url: str, output: Path | str | None = None, timeout: int = 20) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read()
    except Exception as e:
        raise RuntimeError(f"Failed to fetch URL '{url}': {e}") from e
    text = data.decode("utf-8", errors="ignore")
    markdown = html_to_markdown(text)
    if output:
        Path(output).write_text(markdown, encoding="utf-8")
    return markdown


def html_to_markdown(text: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(text)
    return parser.markdown()


def docx_to_markdown(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml")
    except zipfile.BadZipFile as e:
        raise ValueError(f"The file {path} is corrupted or not a valid DOCX archive.") from e
    root = ET.fromstring(xml)
    paragraphs: list[str] = []
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    for para in root.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in para.findall(".//w:t", ns)).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs) + "\n"


def xlsx_to_markdown(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            shared = _xlsx_shared_strings(zf)
            sheet_names = [name for name in zf.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")]
            sections: list[str] = []
            for sheet_index, sheet_name in enumerate(sorted(sheet_names), start=1):
                root = ET.fromstring(zf.read(sheet_name))
                ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                rows: list[list[str]] = []
                for row in root.findall(".//x:sheetData/x:row", ns):
                    values: list[str] = []
                    for cell in row.findall("x:c", ns):
                        values.append(_xlsx_cell_value(cell, shared, ns))
                    if any(values):
                        rows.append(values)
                if rows:
                    sections.append(f"## Sheet {sheet_index}\n\n" + _rows_to_markdown_table(rows))
            return "\n\n".join(sections).strip() + "\n"
    except zipfile.BadZipFile as e:
        raise ValueError(f"The file {path} is corrupted or not a valid XLSX archive.") from e


def _xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    return ["".join(t.text or "" for t in item.findall(".//x:t", ns)) for item in root.findall(".//x:si", ns)]


def _xlsx_cell_value(cell: ET.Element, shared: list[str], ns: dict[str, str]) -> str:
    value = cell.find("x:v", ns)
    if value is None or value.text is None:
        inline = cell.find(".//x:t", ns)
        return inline.text if inline is not None and inline.text else ""
    if cell.attrib.get("t") == "s":
        idx = int(value.text)
        return shared[idx] if idx < len(shared) else ""
    return value.text


def _rows_to_markdown_table(rows: list[list[str]]) -> str:
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    header = padded[0]
    body = padded[1:] or [[""] * width]
    lines = [
        "| " + " | ".join(_escape_table_cell(cell) for cell in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(_escape_table_cell(cell) for cell in row) + " |")
    return "\n".join(lines)


def _escape_table_cell(cell: str) -> str:
    return str(cell).replace("|", "\\|").replace("\n", " ")


def pptx_to_markdown(path: Path) -> str:
    slides = extract_pptx_slide_text(path)
    sections = [f"## Slide {index}\n\n{text}" for index, text in slides]
    return "\n\n".join(sections).strip() + "\n"


def extract_pptx_slide_text(path: Path | str) -> list[tuple[int, str]]:
    deck = Path(path)
    try:
        with zipfile.ZipFile(deck) as zf:
            slide_names = _presentation_slide_names(zf)
            slides: list[tuple[int, str]] = []
            for idx, name in enumerate(slide_names, start=1):
                root = ET.fromstring(zf.read(name))
                texts = [node.text or "" for node in root.iter() if node.tag.endswith("}t")]
                slides.append((idx, "\n".join(text.strip() for text in texts if text.strip())))
        return slides
    except zipfile.BadZipFile as e:
        raise ValueError(f"The file {path} is corrupted or not a valid PPTX archive.") from e


def _presentation_slide_names(zf: zipfile.ZipFile) -> list[str]:
    fallback = sorted(
        [name for name in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)],
        key=lambda item: int(re.search(r"slide(\d+)\.xml", item).group(1)),  # type: ignore[union-attr]
    )
    try:
        pres = ET.fromstring(zf.read("ppt/presentation.xml"))
        rels = ET.fromstring(zf.read("ppt/_rels/presentation.xml.rels"))
    except KeyError:
        return fallback

    rel_targets = {
        rel.attrib.get("Id", ""): rel.attrib.get("Target", "")
        for rel in rels
        if rel.attrib.get("Type", "").endswith("/slide")
    }
    names: list[str] = []
    for elem in pres.iter():
        if not elem.tag.endswith("}sldId"):
            continue
        rel_id = elem.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rel_targets.get(rel_id or "")
        if not target:
            continue
        name = _ppt_part_name(target)
        if name in zf.namelist():
            names.append(name)
    return names or fallback


def _ppt_part_name(target: str) -> str:
    clean = target.replace("\\", "/").lstrip("/")
    if clean.startswith("ppt/"):
        return clean
    return f"ppt/{clean}"


def pdf_to_markdown(path: Path) -> str:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PDF conversion requires PyMuPDF. Install with: python -m pip install -e .[intake]") from exc
    doc = fitz.open(str(path))
    pages: list[str] = []
    for index, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        pages.append(f"## Page {index}\n\n{text}")
    return "\n\n".join(pages).strip() + "\n"
