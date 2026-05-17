"""Tests for v1.4 Phase 22 — Element Animations v2."""

from __future__ import annotations

import unittest
from lxml import etree as ET

from slide_skill import animations_v2 as av2


class CatalogTests(unittest.TestCase):
    def test_required_effects_present(self) -> None:
        for name in ("fadeIn", "fadeOut", "pulse", "zoomIn", "flyIn-left", "wipe-down", "spin"):
            self.assertIn(name, av2.EFFECT_CATALOG)

    def test_classes_distributed(self) -> None:
        classes = {meta[0] for meta in av2.EFFECT_CATALOG.values()}
        self.assertEqual(classes, {"entr", "exit", "emph"})


class ElementAnimationTests(unittest.TestCase):
    def test_invalid_effect_raises(self) -> None:
        with self.assertRaises(ValueError):
            av2.ElementAnimation(target="bullet[0]", effect="not-real")

    def test_invalid_trigger_raises(self) -> None:
        with self.assertRaises(ValueError):
            av2.ElementAnimation(target="x", trigger="onHover")

    def test_negative_timing_raises(self) -> None:
        with self.assertRaises(ValueError):
            av2.ElementAnimation(target="x", duration=0)
        with self.assertRaises(ValueError):
            av2.ElementAnimation(target="x", delay=-1)


class NormalizeTests(unittest.TestCase):
    def test_dicts_coerced_and_default_order(self) -> None:
        items = [
            {"target": "a", "effect": "fadeIn"},
            {"target": "b", "effect": "fadeIn"},
            {"target": "c", "effect": "fadeIn", "order": 0},  # explicit -> first
        ]
        out = av2.normalize_animations(items)
        self.assertEqual([a.target for a in out], ["a", "c", "b"])  # sorted by (order=0 before 1=default for c, then a=0 default... let's verify)
        # a default order = 0, c explicit = 0, b default = 1 -> sort stable: a,c,b
        # Stable Python sort preserves input order on ties, so a(0) < c(0) (input position) < b(1).

    def test_normalize_keeps_existing_objects(self) -> None:
        a = av2.ElementAnimation(target="x")
        out = av2.normalize_animations([a])
        self.assertIs(out[0], a)


class TimingSerializerTests(unittest.TestCase):
    def test_returns_none_without_resolved_sp_ids(self) -> None:
        anims = [av2.ElementAnimation(target="bullet[0]")]
        self.assertIsNone(av2.build_timing_xml_v2(anims))

    def test_emits_one_par_per_animation(self) -> None:
        anims = [
            av2.ElementAnimation(target="t1", effect="fadeIn", trigger="onClick", sp_id="2"),
            av2.ElementAnimation(target="t2", effect="zoomIn", trigger="afterPrevious", sp_id="3", delay=300),
            av2.ElementAnimation(target="t3", effect="pulse", trigger="withPrevious", sp_id="4"),
        ]
        timing = av2.build_timing_xml_v2(anims)
        self.assertIsNotNone(timing)
        ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
        # Inside the mainSeq <p:childTnLst> there should be one <p:par> per anim.
        outer_pars = timing.findall(".//p:seq/p:cTn/p:childTnLst/p:par", ns)
        self.assertEqual(len(outer_pars), 3)

        # Verify nodeTypes encode triggers correctly.
        inner_ctns = timing.findall(".//p:seq/p:cTn/p:childTnLst/p:par/p:cTn/p:childTnLst/p:par/p:cTn", ns)
        self.assertEqual(len(inner_ctns), 3)
        node_types = [c.get("nodeType") for c in inner_ctns]
        self.assertEqual(node_types, ["clickEffect", "afterEffect", "withEffect"])

    def test_build_order_respected(self) -> None:
        anims = av2.normalize_animations([
            {"target": "late", "effect": "fadeIn", "order": 5, "sp_id": "5"},
            {"target": "first", "effect": "fadeIn", "order": 1, "sp_id": "1"},
            {"target": "mid", "effect": "fadeIn", "order": 3, "sp_id": "3"},
        ])
        timing = av2.build_timing_xml_v2(anims)
        ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
        sp_targets = timing.findall(".//p:spTgt", ns)
        spids = [s.get("spid") for s in sp_targets]
        self.assertEqual(spids, ["1", "3", "5"])

    def test_exit_effect_sets_hidden(self) -> None:
        anims = [av2.ElementAnimation(target="x", effect="fadeOut", sp_id="9")]
        timing = av2.build_timing_xml_v2(anims)
        ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
        str_vals = timing.findall(".//p:strVal", ns)
        self.assertEqual(str_vals[0].get("val"), "hidden")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
