"""DrawingML slide transitions and entrance animations."""

from __future__ import annotations

from typing import Sequence
from lxml import etree as ET

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

TRANSITION_PRESETS = {
    "fade": ("fade", {}),
    "push": ("push", {"dir": "l"}),
    "wipe": ("wipe", {"dir": "d"}),
    "split": ("split", {"orient": "horz", "dir": "out"}),
    "zoom": ("zoom", {"dir": "in"}),
}

ANIMATION_PRESETS = {
    "fly-in": (1, "l"),      # preset ID 1, direction left
    "fade-in": (10, None),   # preset ID 10
    "wipe": (22, "d"),       # preset ID 22, direction down
    "zoom-in": (53, "ctr"),  # preset ID 53, center
    "float-in": (42, "b"),   # preset ID 42, bottom
}


def build_transition_xml(transition_type: str, speed: str = "med"):
    """Build a <p:transition> element."""
    if transition_type not in TRANSITION_PRESETS:
        return None

    preset_name, attrs = TRANSITION_PRESETS[transition_type]
    nsmap = {_P.split("/")[-1]: _P}

    trans = ET.Element(f"{{{_P}}}transition")
    trans.set("spd", speed)
    trans.set("advClick", "1")

    preset_elem = ET.SubElement(trans, f"{{{_P}}}{preset_name}")
    for k, v in attrs.items():
        preset_elem.set(k, v)

    return trans


def build_timing_xml(animated_shapes: list[dict], default_duration: int = 500):
    """Build a <p:timing> element with entrance animations.

    Args:
        animated_shapes: list of dicts with keys:
            - sp_id: shape ID string (e.g. "2")
            - preset: animation preset name
            - duration: ms (optional, defaults to default_duration)
            - delay: ms (optional, defaults to 0)
    """
    if not animated_shapes:
        return None

    timing = ET.Element(f"{{{_P}}}timing")
    tn_lst = ET.SubElement(timing, f"{{{_P}}}tnLst")

    par_root = ET.SubElement(tn_lst, f"{{{_P}}}par")
    ctn_root = ET.SubElement(par_root, f"{{{_P}}}cTn")
    ctn_root.set("id", "1")
    ctn_root.set("dur", "indefinite")
    ctn_root.set("restart", "never")
    ctn_root.set("nodeType", "tmRoot")

    child_lst_root = ET.SubElement(ctn_root, f"{{{_P}}}childTnLst")

    seq = ET.SubElement(child_lst_root, f"{{{_P}}}seq")
    seq.set("concurrent", "1")
    seq.set("nextAc", "seek")

    seq_ctn = ET.SubElement(seq, f"{{{_P}}}cTn")
    seq_ctn.set("id", "2")
    seq_ctn.set("dur", "indefinite")
    seq_ctn.set("nodeType", "mainSeq")

    seq_child = ET.SubElement(seq_ctn, f"{{{_P}}}childTnLst")

    for idx, shape_info in enumerate(animated_shapes):
        sp_id = shape_info["sp_id"]
        preset_name = shape_info["preset"]
        duration = shape_info.get("duration", default_duration)
        delay = shape_info.get("delay", 0)

        preset_id, direction = ANIMATION_PRESETS.get(preset_name, (1, None))

        par = ET.SubElement(seq_child, f"{{{_P}}}par")
        par_ctn = ET.SubElement(par, f"{{{_P}}}cTn")
        par_ctn.set("id", str(3 + idx * 4))
        par_ctn.set("fill", "hold")

        stCondLst = ET.SubElement(par_ctn, f"{{{_P}}}stCondLst")
        cond = ET.SubElement(stCondLst, f"{{{_P}}}cond")
        cond.set("delay", str(delay) if delay else "0")

        child_lst = ET.SubElement(par_ctn, f"{{{_P}}}childTnLst")
        inner_par = ET.SubElement(child_lst, f"{{{_P}}}par")
        inner_ctn = ET.SubElement(inner_par, f"{{{_P}}}cTn")
        inner_ctn.set("id", str(4 + idx * 4))
        inner_ctn.set("presetID", str(preset_id))
        inner_ctn.set("presetClass", "entr")
        inner_ctn.set("presetSubtype", "0")
        inner_ctn.set("fill", "hold")
        inner_ctn.set("grpId", "0")
        inner_ctn.set("nodeType", "clickEffect" if delay == 0 else "afterEffect")

        inner_child = ET.SubElement(inner_ctn, f"{{{_P}}}childTnLst")

        set_elem = ET.SubElement(inner_child, f"{{{_P}}}set")
        set_ctn = ET.SubElement(set_elem, f"{{{_P}}}cTn")
        set_ctn.set("id", str(5 + idx * 4))
        set_ctn.set("dur", "1")
        set_ctn.set("fill", "hold")

        set_stCondLst = ET.SubElement(set_ctn, f"{{{_P}}}stCondLst")
        set_cond = ET.SubElement(set_stCondLst, f"{{{_P}}}cond")
        set_cond.set("delay", "0")

        tgt_el = ET.SubElement(set_ctn, f"{{{_P}}}tgtEl")
        sp_tgt = ET.SubElement(tgt_el, f"{{{_P}}}spTgt")
        sp_tgt.set("spid", str(sp_id))

        to_elem = ET.SubElement(set_ctn, f"{{{_P}}}to")
        str_val = ET.SubElement(to_elem, f"{{{_P}}}strVal")
        str_val.set("val", "visible")

        anim_elem = ET.SubElement(inner_child, f"{{{_P}}}anim")
        anim_ctn = ET.SubElement(anim_elem, f"{{{_P}}}cTn")
        anim_ctn.set("id", str(6 + idx * 4))
        anim_ctn.set("dur", str(duration))
        anim_ctn.set("fill", "hold")

        anim_stCondLst = ET.SubElement(anim_ctn, f"{{{_P}}}stCondLst")
        anim_cond = ET.SubElement(anim_stCondLst, f"{{{_P}}}cond")
        anim_cond.set("delay", "0")

        anim_tgtEl = ET.SubElement(anim_ctn, f"{{{_P}}}tgtEl")
        anim_sp_tgt = ET.SubElement(anim_tgtEl, f"{{{_P}}}spTgt")
        anim_sp_tgt.set("spid", str(sp_id))

        anim_with = ET.SubElement(anim_ctn, f"{{{_P}}}with")

        if direction:
            anim_attr = ET.SubElement(anim_with, f"{{{_P}}}attrNameLst")
            anim_attr_item = ET.SubElement(anim_attr, f"{{{_P}}}attrNameLst")
            # Direction is encoded in the preset, not as a separate attribute
            pass

    # Previous condition list (empty)
    prevCondLst = ET.SubElement(seq, f"{{{_P}}}prevCondLst")
    prev_cond = ET.SubElement(prevCondLst, f"{{{_P}}}cond")
    prev_cond.set("evt", "onPrev")
    prev_tgtEl = ET.SubElement(prev_cond, f"{{{_P}}}tgtEl")
    ET.SubElement(prev_tgtEl, f"{{{_P}}}sldTgt")

    nextCondLst = ET.SubElement(seq, f"{{{_P}}}nextCondLst")
    next_cond = ET.SubElement(nextCondLst, f"{{{_P}}}cond")
    next_cond.set("evt", "onNext")
    next_tgtEl = ET.SubElement(next_cond, f"{{{_P}}}tgtEl")
    ET.SubElement(next_tgtEl, f"{{{_P}}}sldTgt")

    return timing


def inject_transition(slide_elem, transition_type: str) -> None:
    """Inject transition XML into a slide element."""
    transition_xml = build_transition_xml(transition_type)
    if transition_xml is None:
        return

    for child in list(slide_elem):
        tag_local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag_local == "transition":
            slide_elem.remove(child)

    cSld = None
    for child in slide_elem:
        tag_local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag_local == "cSld":
            cSld = child
            break

    if cSld is not None:
        slide_elem.insert(list(slide_elem).index(cSld) + 1, transition_xml)
    else:
        slide_elem.append(transition_xml)


def inject_timing(slide_elem, animated_shapes: list[dict], default_duration: int = 500) -> None:
    """Inject timing animation XML into a slide element."""
    timing_xml = build_timing_xml(animated_shapes, default_duration)
    if timing_xml is None:
        return

    for child in list(slide_elem):
        tag_local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag_local == "timing":
            slide_elem.remove(child)

    slide_elem.append(timing_xml)
