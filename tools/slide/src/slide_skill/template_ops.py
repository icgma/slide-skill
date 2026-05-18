"""Basic PPTX template inspection and relationship-safe slide operations."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .intake import extract_pptx_slide_text

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

ET.register_namespace("p", P_NS)
ET.register_namespace("r", R_NS)
ET.register_namespace("a", A_NS)
ET.register_namespace("", REL_NS)


def inspect_template(path: Path | str) -> dict:
    deck = Path(path)
    slides = extract_pptx_slide_text(deck)
    with zipfile.ZipFile(deck) as zf:
        names = zf.namelist()
    return {
        "path": str(deck),
        "slide_count": len(slides),
        "slides": [{"number": idx, "text": text} for idx, text in slides],
        "media_count": len([name for name in names if name.startswith("ppt/media/")]),
        "layout_count": len([name for name in names if name.startswith("ppt/slideLayouts/slideLayout")]),
    }


def replace_text(input_pptx: Path | str, output_pptx: Path | str, replacements: dict[str, str]) -> Path:
    source = Path(input_pptx)
    output = Path(output_pptx)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _unzip(source, root)
        for slide in (root / "ppt" / "slides").glob("slide*.xml"):
            tree = ET.parse(slide)
            _replace_visible_text(tree.getroot(), replacements)
            tree.write(slide, encoding="utf-8", xml_declaration=True)
        _zip(root, output)
    return output


def delete_slides(input_pptx: Path | str, output_pptx: Path | str, slide_numbers: list[int]) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _unzip(Path(input_pptx), root)
        pres, rels = _load_presentation(root)
        sld_ids = _slide_id_elements(pres)
        keep = [elem for idx, elem in enumerate(sld_ids, start=1) if idx not in set(slide_numbers)]
        _remove_deleted_slide_parts(root, rels, sld_ids, keep)
        _replace_slide_id_list(pres, keep)
        _remove_deleted_relationships(rels, sld_ids, keep)
        _remove_unreferenced_payload_parts(root)
        _save_presentation(root, pres, rels)
        _zip(root, Path(output_pptx))
    return Path(output_pptx)


def reorder_slides(input_pptx: Path | str, output_pptx: Path | str, order: list[int]) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _unzip(Path(input_pptx), root)
        pres, rels = _load_presentation(root)
        sld_ids = _slide_id_elements(pres)
        if sorted(order) != list(range(1, len(sld_ids) + 1)):
            raise ValueError(f"Order must be a permutation of 1..{len(sld_ids)}")
        _replace_slide_id_list(pres, [sld_ids[index - 1] for index in order])
        _save_presentation(root, pres, rels)
        _zip(root, Path(output_pptx))
    return Path(output_pptx)


def duplicate_slide(input_pptx: Path | str, output_pptx: Path | str, slide_number: int) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _unzip(Path(input_pptx), root)
        pres, rels = _load_presentation(root)
        sld_ids = _slide_id_elements(pres)
        if slide_number < 1 or slide_number > len(sld_ids):
            raise ValueError(f"Slide number out of range: {slide_number}")
        new_slide_num = _next_slide_number(root)
        src_slide = root / "ppt" / "slides" / f"slide{slide_number}.xml"
        dst_slide = root / "ppt" / "slides" / f"slide{new_slide_num}.xml"
        shutil.copy2(src_slide, dst_slide)
        src_rels = root / "ppt" / "slides" / "_rels" / f"slide{slide_number}.xml.rels"
        dst_rels = root / "ppt" / "slides" / "_rels" / f"slide{new_slide_num}.xml.rels"
        if src_rels.exists():
            dst_rels.parent.mkdir(exist_ok=True)
            shutil.copy2(src_rels, dst_rels)
        rel_id = _next_rel_id(rels)
        ET.SubElement(rels.getroot(), f"{{{REL_NS}}}Relationship", {
            "Id": rel_id,
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
            "Target": f"slides/slide{new_slide_num}.xml",
        })
        max_id = max(int(elem.attrib.get("id", "256")) for elem in sld_ids)
        new_elem = ET.Element(f"{{{P_NS}}}sldId", {"id": str(max_id + 1), f"{{{R_NS}}}id": rel_id})
        sld_ids.insert(slide_number, new_elem)
        _replace_slide_id_list(pres, sld_ids)
        _add_content_type(root, new_slide_num)
        _save_presentation(root, pres, rels)
        _zip(root, Path(output_pptx))
    return Path(output_pptx)


def replacements_from_json(path: Path | str) -> dict[str, str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Replacement file must be a JSON object")
    return {str(key): str(value) for key, value in data.items()}


def _replace_visible_text(root: ET.Element, replacements: dict[str, str]) -> bool:
    changed = False
    for paragraph in root.iter(f"{{{A_NS}}}p"):
        text_nodes = [node for node in paragraph.iter(f"{{{A_NS}}}t")]
        if not text_nodes:
            continue
        original = "".join(node.text or "" for node in text_nodes)
        updated = original
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        if updated == original:
            continue
        text_nodes[0].text = updated
        for node in text_nodes[1:]:
            node.text = ""
        changed = True
    return changed


def _unzip(source: Path, dest: Path) -> None:
    with zipfile.ZipFile(source) as zf:
        zf.extractall(dest)


def _zip(source_dir: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(source_dir).as_posix())


def _load_presentation(root: Path) -> tuple[ET.ElementTree, ET.ElementTree]:
    return (
        ET.parse(root / "ppt" / "presentation.xml"),
        ET.parse(root / "ppt" / "_rels" / "presentation.xml.rels"),
    )


def _save_presentation(root: Path, pres: ET.ElementTree, rels: ET.ElementTree) -> None:
    pres.write(root / "ppt" / "presentation.xml", encoding="utf-8", xml_declaration=True)
    rels.write(root / "ppt" / "_rels" / "presentation.xml.rels", encoding="utf-8", xml_declaration=True)


def _slide_id_elements(pres: ET.ElementTree) -> list[ET.Element]:
    sld_id_list = pres.getroot().find(f".//{{{P_NS}}}sldIdLst")
    if sld_id_list is None:
        raise ValueError("presentation.xml has no sldIdLst")
    return list(sld_id_list)


def _replace_slide_id_list(pres: ET.ElementTree, elements: list[ET.Element]) -> None:
    sld_id_list = pres.getroot().find(f".//{{{P_NS}}}sldIdLst")
    if sld_id_list is None:
        raise ValueError("presentation.xml has no sldIdLst")
    for child in list(sld_id_list):
        sld_id_list.remove(child)
    for elem in elements:
        sld_id_list.append(elem)


def _remove_deleted_relationships(rels: ET.ElementTree, original: list[ET.Element], keep: list[ET.Element]) -> None:
    keep_ids = {elem.attrib[f"{{{R_NS}}}id"] for elem in keep}
    root = rels.getroot()
    for rel in list(root):
        if rel.attrib.get("Id") not in keep_ids and rel.attrib.get("Type", "").endswith("/slide"):
            root.remove(rel)


def _remove_deleted_slide_parts(root_dir: Path, rels: ET.ElementTree, original: list[ET.Element], keep: list[ET.Element]) -> None:
    keep_ids = {elem.attrib[f"{{{R_NS}}}id"] for elem in keep}
    removed_ids = [elem.attrib[f"{{{R_NS}}}id"] for elem in original if elem.attrib[f"{{{R_NS}}}id"] not in keep_ids]
    targets = {
        rel.attrib.get("Id", ""): rel.attrib.get("Target", "")
        for rel in rels.getroot()
        if rel.attrib.get("Type", "").endswith("/slide")
    }
    for rel_id in removed_ids:
        target = targets.get(rel_id)
        if not target:
            continue
        part = _target_path(root_dir, target)
        if part.exists():
            part.unlink()
        rel_part = part.parent / "_rels" / f"{part.name}.rels"
        if rel_part.exists():
            rel_part.unlink()
        _remove_content_type(root_dir, "/" + part.relative_to(root_dir).as_posix())


def _remove_unreferenced_payload_parts(root: Path) -> None:
    referenced = _referenced_package_parts(root)
    for folder in [root / "ppt" / "media", root / "ppt" / "embeddings"]:
        if not folder.exists():
            continue
        for part in folder.rglob("*"):
            if part.is_file() and part.relative_to(root).as_posix() not in referenced:
                _remove_content_type(root, "/" + part.relative_to(root).as_posix())
                part.unlink()


def _referenced_package_parts(root: Path) -> set[str]:
    parts: set[str] = set()
    for rels_file in root.rglob("*.rels"):
        base = _rels_base_dir(root, rels_file)
        try:
            rels = ET.parse(rels_file)
        except ET.ParseError:
            continue
        for rel in rels.getroot():
            target = rel.attrib.get("Target", "")
            if not target or rel.attrib.get("TargetMode") == "External":
                continue
            target_path = (base / target.replace("\\", "/")).resolve()
            try:
                rel_name = target_path.relative_to(root.resolve()).as_posix()
            except ValueError:
                continue
            parts.add(rel_name)
    return parts


def _rels_base_dir(root: Path, rels_file: Path) -> Path:
    if rels_file.name == ".rels":
        return root
    if rels_file.parent.name == "_rels":
        return rels_file.parent.parent
    return rels_file.parent


def _next_slide_number(root: Path) -> int:
    existing = [
        int(re.search(r"slide(\d+)\.xml", path.name).group(1))  # type: ignore[union-attr]
        for path in (root / "ppt" / "slides").glob("slide*.xml")
    ]
    return (max(existing) if existing else 0) + 1


def _next_rel_id(rels: ET.ElementTree) -> str:
    nums = []
    for rel in rels.getroot():
        rel_id = rel.attrib.get("Id", "")
        if rel_id.startswith("rId") and rel_id[3:].isdigit():
            nums.append(int(rel_id[3:]))
    return f"rId{(max(nums) if nums else 0) + 1}"


def _add_content_type(root: Path, slide_num: int) -> None:
    ct_path = root / "[Content_Types].xml"
    tree = ET.parse(ct_path)
    part_name = f"/ppt/slides/slide{slide_num}.xml"
    exists = any(elem.attrib.get("PartName") == part_name for elem in tree.getroot())
    if not exists:
        ET.SubElement(tree.getroot(), f"{{{CT_NS}}}Override", {
            "PartName": part_name,
            "ContentType": "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
        })
    tree.write(ct_path, encoding="utf-8", xml_declaration=True)


def _remove_content_type(root: Path, part_name: str) -> None:
    ct_path = root / "[Content_Types].xml"
    tree = ET.parse(ct_path)
    for elem in list(tree.getroot()):
        if elem.attrib.get("PartName") == part_name:
            tree.getroot().remove(elem)
    tree.write(ct_path, encoding="utf-8", xml_declaration=True)


def _target_path(root: Path, target: str) -> Path:
    clean = target.replace("\\", "/").lstrip("/")
    if clean.startswith("ppt/"):
        return root / clean
    return root / "ppt" / clean

