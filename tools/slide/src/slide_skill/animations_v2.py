"""Element-level animations v2 — entrance/exit/emphasis + build order.

Phase 22 (v1.4): introduced. v1.4-ANIM-01..04.

Builds on the v1.3 transition infrastructure in `slide_skill.animations` by
adding:

  * A named effect catalog spanning entrance / exit / emphasis classes.
  * Per-element trigger types: onClick (default), withPrevious, afterPrevious.
  * Build-order control so authors can declare a click-through sequence.
  * A pure-XML serializer (`build_timing_xml_v2`) that wraps the existing
    PresentationML <p:timing> tree.

Spec syntax (deck source / layout slot):

    animations:
      - target: "bullet[0]"        # logical target id; resolved to sp_id by exporter
        effect: fadeIn             # see EFFECT_CATALOG
        trigger: onClick           # onClick | withPrevious | afterPrevious
        order: 1                   # explicit build order (smaller -> earlier)
        delay: 0                   # ms
        duration: 500              # ms
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from lxml import etree as ET

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"

# Effect catalog — (presetClass, presetID, presetSubtype).
# Preset IDs follow ECMA-376 PresentationML conventions used by PowerPoint.
EFFECT_CATALOG: dict[str, tuple[str, int, int]] = {
    # entrance
    "fadeIn":            ("entr", 10, 0),
    "appear":            ("entr",  1, 0),
    "flyIn-left":        ("entr",  2, 4),
    "flyIn-right":       ("entr",  2, 8),
    "flyIn-top":         ("entr",  2, 1),
    "flyIn-bottom":      ("entr",  2, 2),
    "zoomIn":            ("entr", 23, 16),
    "wipe-down":         ("entr", 22, 1),
    "wipe-right":        ("entr", 22, 8),
    "slideIn-left":      ("entr", 41, 4),
    "slideIn-right":     ("entr", 41, 8),
    # exit
    "fadeOut":           ("exit", 10, 0),
    "disappear":         ("exit",  1, 0),
    "zoomOut":           ("exit", 23, 32),
    "flyOut-left":       ("exit",  2, 4),
    "flyOut-right":      ("exit",  2, 8),
    # emphasis
    "pulse":             ("emph", 50, 0),
    "spin":              ("emph",  8, 0),
    "grow":              ("emph",  6, 0),
    "color-pulse":       ("emph", 26, 0),
}

ENTRANCE_DEFAULT = "fadeIn"

VALID_TRIGGERS = {"onClick", "withPrevious", "afterPrevious"}


@dataclass
class ElementAnimation:
    """Spec-level description; exporter resolves `target` -> `sp_id`."""

    target: str
    effect: str = ENTRANCE_DEFAULT
    trigger: str = "onClick"
    order: Optional[int] = None
    delay: int = 0
    duration: int = 500
    sp_id: Optional[str] = None  # filled in by exporter once shape ID is known

    def __post_init__(self) -> None:
        if self.effect not in EFFECT_CATALOG:
            raise ValueError(f"Unknown effect: {self.effect!r}. Available: {sorted(EFFECT_CATALOG)}")
        if self.trigger not in VALID_TRIGGERS:
            raise ValueError(f"Invalid trigger: {self.trigger!r}. Choose from {sorted(VALID_TRIGGERS)}")
        if self.delay < 0 or self.duration <= 0:
            raise ValueError("delay must be >= 0 and duration must be > 0")


def normalize_animations(items: Iterable[dict | ElementAnimation]) -> list[ElementAnimation]:
    """Coerce dict-style spec entries into ElementAnimation, sorted by build order."""
    out: list[ElementAnimation] = []
    for i, raw in enumerate(items):
        if isinstance(raw, ElementAnimation):
            out.append(raw)
        else:
            out.append(ElementAnimation(
                target=str(raw["target"]),
                effect=raw.get("effect", ENTRANCE_DEFAULT),
                trigger=raw.get("trigger", "onClick"),
                order=raw.get("order"),
                delay=int(raw.get("delay", 0)),
                duration=int(raw.get("duration", 500)),
                sp_id=raw.get("sp_id"),
            ))
        # Default order: spec position.
        if out[-1].order is None:
            out[-1].order = i
    out.sort(key=lambda a: (a.order or 0))
    return out


def build_timing_xml_v2(animations: list[ElementAnimation]) -> Optional[ET._Element]:
    """Serialize element animations to a `<p:timing>` element.

    Animations missing an `sp_id` are silently dropped (the exporter must
    resolve targets to shape IDs before calling this).
    """
    resolved = [a for a in animations if a.sp_id]
    if not resolved:
        return None

    timing = ET.Element(f"{{{_P}}}timing")
    tn_lst = ET.SubElement(timing, f"{{{_P}}}tnLst")

    par_root = ET.SubElement(tn_lst, f"{{{_P}}}par")
    ctn_root = ET.SubElement(par_root, f"{{{_P}}}cTn",
                             id="1", dur="indefinite", restart="never", nodeType="tmRoot")
    child_lst_root = ET.SubElement(ctn_root, f"{{{_P}}}childTnLst")

    seq = ET.SubElement(child_lst_root, f"{{{_P}}}seq", concurrent="1", nextAc="seek")
    seq_ctn = ET.SubElement(seq, f"{{{_P}}}cTn", id="2", dur="indefinite", nodeType="mainSeq")
    seq_child = ET.SubElement(seq_ctn, f"{{{_P}}}childTnLst")

    next_id = 3
    for anim in resolved:
        preset_class, preset_id, preset_subtype = EFFECT_CATALOG[anim.effect]
        node_type = {
            "onClick": "clickEffect",
            "withPrevious": "withEffect",
            "afterPrevious": "afterEffect",
        }[anim.trigger]

        par = ET.SubElement(seq_child, f"{{{_P}}}par")
        par_ctn = ET.SubElement(par, f"{{{_P}}}cTn", id=str(next_id), fill="hold")
        next_id += 1

        st_cond = ET.SubElement(par_ctn, f"{{{_P}}}stCondLst")
        ET.SubElement(st_cond, f"{{{_P}}}cond", delay=str(anim.delay))

        inner_par = ET.SubElement(ET.SubElement(par_ctn, f"{{{_P}}}childTnLst"), f"{{{_P}}}par")
        inner_ctn = ET.SubElement(inner_par, f"{{{_P}}}cTn",
                                  id=str(next_id),
                                  presetID=str(preset_id),
                                  presetClass=preset_class,
                                  presetSubtype=str(preset_subtype),
                                  fill="hold",
                                  grpId="0",
                                  nodeType=node_type)
        next_id += 1

        anim_set_par = ET.SubElement(ET.SubElement(inner_ctn, f"{{{_P}}}childTnLst"), f"{{{_P}}}set")
        set_ctn = ET.SubElement(anim_set_par, f"{{{_P}}}cTn",
                                id=str(next_id), dur=str(anim.duration), fill="hold")
        next_id += 1
        st = ET.SubElement(set_ctn, f"{{{_P}}}stCondLst")
        ET.SubElement(st, f"{{{_P}}}cond", delay="0")
        tgt = ET.SubElement(set_ctn, f"{{{_P}}}tgtEl")
        ET.SubElement(tgt, f"{{{_P}}}spTgt", spid=str(anim.sp_id))
        to = ET.SubElement(set_ctn, f"{{{_P}}}to")
        ET.SubElement(to, f"{{{_P}}}strVal", val="visible" if preset_class == "entr" else "hidden")

    # Click-advance / prev affordances kept consistent with existing v1 emitter.
    for evt, name in (("onPrev", "prevCondLst"), ("onNext", "nextCondLst")):
        cond_lst = ET.SubElement(seq, f"{{{_P}}}{name}")
        cond = ET.SubElement(cond_lst, f"{{{_P}}}cond", evt=evt)
        ET.SubElement(ET.SubElement(cond, f"{{{_P}}}tgtEl"), f"{{{_P}}}sldTgt")

    return timing


def inject_timing_v2(slide_elem, animations: list[ElementAnimation]) -> None:
    """Replace any existing <p:timing> on the slide with one built from `animations`."""
    timing = build_timing_xml_v2(animations)
    if timing is None:
        return
    for child in list(slide_elem):
        if child.tag.split("}")[-1] == "timing":
            slide_elem.remove(child)
    slide_elem.append(timing)
