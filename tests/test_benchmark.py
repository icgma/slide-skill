"""Six-family benchmark runner tests (BENCH-04).

All provider/browser interactions are mocked; these tests pin the runner's
gating, validation, classification, and manifest contract offline.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from slide_skill.benchmark import (
    BLIND_REVIEW_FILENAME,
    MANIFEST_FILENAME,
    Scene,
    SceneTextNode,
    check_non_degeneration,
    classify_scene,
    contract_self_test,
    load_briefs,
    parse_brief,
    run_benchmark,
)

REPO_BRIEFS = Path(__file__).resolve().parents[1] / "benchmarks" / "briefs"


# ── Brief loading ──────────────────────────────────────────────────────────


class TestBriefLoading:
    def test_repo_briefs_load_clean(self):
        briefs, problems = load_briefs(REPO_BRIEFS)
        assert problems == []
        assert len(briefs) == 6
        families = {b.family for b in briefs}
        assert families == {
            "comparison", "sequence", "metric",
            "hierarchy-definition", "quote", "enumeration",
        }
        english = [b for b in briefs if b.language == "en"]
        assert len(english) == 1 and english[0].family == "quote"

    def test_missing_family_is_reported(self, tmp_path):
        for family in ("comparison", "sequence", "metric", "quote", "enumeration"):
            (tmp_path / f"{family}.md").write_text(
                f"---\nfamily: {family}\nlanguage: zh\ntitle: 测试\n---\n\n- 内容\n",
                encoding="utf-8",
            )
        briefs, problems = load_briefs(tmp_path)
        assert any("missing brief for family" in p for p in problems)

    def test_two_english_briefs_rejected(self, tmp_path):
        families = ("comparison", "sequence", "metric", "quote", "enumeration", "hierarchy-definition")
        for i, family in enumerate(families):
            lang = "en" if family in {"quote", "enumeration"} else "zh"
            (tmp_path / f"{family}.md").write_text(
                f"---\nfamily: {family}\nlanguage: {lang}\ntitle: 测试\n---\n\n- 内容\n",
                encoding="utf-8",
            )
        _, problems = load_briefs(tmp_path)
        assert any("exactly one English brief" in p for p in problems)

    def test_parse_brief_extracts_facts(self, tmp_path):
        p = tmp_path / "x.md"
        p.write_text(
            "---\nfamily: metric\nlanguage: zh\ntitle: 质量门禁\n---\n\n## 说明\n文字\n\n- 核心数字：73\n- 结论：必须前置\n",
            encoding="utf-8",
        )
        brief = parse_brief(p)
        assert brief.family == "metric"
        assert brief.title == "质量门禁"
        assert "核心数字：73" in brief.facts
        assert all(not f.startswith("#") for f in brief.facts)


# ── Deterministic family classifier ────────────────────────────────────────


def _node(text, x, y, w, h, fs):
    return SceneTextNode(text, x, y, x + w, y + h, fs)


class TestClassifier:
    def test_metric_scene(self):
        scene = Scene(
            text_nodes=[
                _node("73", 300, 200, 220, 90, 96),
                _node("个低对比度问题", 300, 320, 240, 26, 24),
                _node("必须在导出前被拦截", 300, 380, 260, 26, 24),
            ],
        )
        assert classify_scene(scene)["family"] == "metric"

    def test_quote_scene(self):
        scene = Scene(
            text_nodes=[
                _node("Simplicity is the ultimate sophistication.", 200, 300, 700, 44, 36),
                _node("— Leonardo da Vinci", 200, 400, 220, 20, 20),
            ],
        )
        assert classify_scene(scene)["family"] == "quote"

    def test_sequence_scene(self):
        cards = [(120, 160, 380, 300), (520, 160, 780, 300), (920, 160, 1180, 300)]
        scene = Scene(
            text_nodes=[
                _node("步骤一", 160, 220, 120, 26, 24),
                _node("步骤二", 560, 220, 120, 26, 24),
                _node("步骤三", 960, 220, 120, 26, 24),
            ],
            card_rects=cards,
            connector_count=2,
        )
        assert classify_scene(scene)["family"] == "sequence"

    def test_comparison_scene(self):
        cards = [(80, 160, 420, 520), (470, 160, 810, 520), (860, 160, 1200, 520)]
        scene = Scene(
            text_nodes=[
                _node("零样本", 110, 210, 90, 30, 32), _node("直接提问", 110, 300, 200, 22, 18),
                _node("少样本", 500, 210, 90, 30, 32), _node("给出示例", 500, 300, 200, 22, 18),
                _node("思维链", 890, 210, 90, 30, 32), _node("逐步推理", 890, 300, 200, 22, 18),
            ],
            card_rects=cards,
        )
        assert classify_scene(scene)["family"] == "comparison"

    def test_enumeration_scene(self):
        rows = [(80, 150 + i * 100, 1200, 150 + i * 100 + 80) for i in range(5)]
        scene = Scene(
            text_nodes=[_node(f"维度{i}", 120, 170 + i * 100, 160, 24, 24) for i in range(5)],
            card_rects=rows,
        )
        assert classify_scene(scene)["family"] == "enumeration"

    def test_hierarchy_scene(self):
        scene = Scene(
            text_nodes=[
                _node("检索增强生成", 300, 140, 480, 60, 56),
                _node("生成前先检索外部知识库", 140, 320, 400, 24, 22),
                _node("用检索事实约束输出", 640, 320, 380, 24, 22),
            ],
        )
        assert classify_scene(scene)["family"] == "hierarchy-definition"

    def test_unmatched_scene_returns_none(self):
        scene = Scene(text_nodes=[_node("孤立的文本", 100, 100, 200, 24, 24)])
        assert classify_scene(scene)["family"] is None

    def test_non_degeneration_flags_collapsed_cards(self):
        cards = [(80, 160, 460, 600), (480, 160, 860, 600), (880, 160, 1260, 600)]
        scene = Scene(card_rects=cards)
        assert check_non_degeneration(scene, "quote") == "collapsed-to-cards"
        assert check_non_degeneration(scene, "comparison") == "ok"

    def test_non_degeneration_ignores_varied_cards(self):
        cards = [(80, 160, 460, 400), (480, 160, 860, 600), (880, 160, 1260, 320)]
        scene = Scene(card_rects=cards)
        assert check_non_degeneration(scene, "quote") == "ok"


class TestContractSelfTest:
    def test_green_on_current_library(self):
        assert contract_self_test() == []


# ── Runner ─────────────────────────────────────────────────────────────────


class TestRunner:
    def test_dry_run_validates_without_provider(self, tmp_path, monkeypatch, capsys):
        import slide_skill.ai_executor as ai_executor

        def _fail(*a, **k):
            raise AssertionError("provider called during dry-run")

        monkeypatch.setattr(ai_executor, "generate_svg_with_ai", _fail)
        manifest, code = run_benchmark(REPO_BRIEFS, tmp_path, yes=False)
        assert code == 0
        assert manifest is None
        out = capsys.readouterr().out
        assert "dry-run complete" in out
        assert "contract self-test green" in out

    def test_missing_briefs_exit_nonzero(self, tmp_path):
        empty = tmp_path / "briefs"
        empty.mkdir()
        manifest, code = run_benchmark(empty, tmp_path, yes=False)
        assert code == 2
        assert manifest is None

    def test_provider_run_requires_key(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        manifest, code = run_benchmark(REPO_BRIEFS, tmp_path, yes=True)
        assert code == 4

    def test_full_run_with_mocked_chain(self, tmp_path, monkeypatch):
        """Provider run against a mocked executor + mocked browser paths."""
        import slide_skill.benchmark as bm
        import slide_skill.ai_executor as ai_executor
        import slide_skill.chrome_geometry as chrome_geometry

        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
            '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
            '<g id="content-body-01">'
            '<text x="300" y="290" font-family="Arial" font-size="96" fill="#3B82F6">73</text>'
            '<text x="300" y="340" font-family="Arial" font-size="24" fill="#F1F5F9">个低对比度问题</text>'
            "</g></svg>"
        )
        # NOTE: generate_svg_with_ai is called via module attribute in the
        # runner, so patching the executor module attribute is effective.
        written: list[Path] = []

        def fake_generate(project, plans, **kwargs):
            out = Path(project) / "svg_output"
            out.mkdir(parents=True, exist_ok=True)
            p = out / "slide_01.svg"
            p.write_text(svg, encoding="utf-8")
            written.append(p)
            # Trace event with the fields the manifest extracts.
            from slide_skill.ai_trace import write_ai_trace
            write_ai_trace(
                project, stage="executor", model="test-model", status="passed",
                prompt="p" * 100, raw=svg,
                metadata={
                    "slide": plans[0].index,
                    "finish_reason": "stop",
                    "prompt_tokens": 111,
                    "completion_tokens": 222,
                    "reasoning_chars": 0,
                    "publish_path": str(p),
                },
            )
            return [p]

        monkeypatch.setattr(ai_executor, "generate_svg_with_ai", fake_generate)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        def fake_measure(svg_text, **kw):
            return [
                {"index": 0, "tag": "text", "text": "73",
                 "bbox": {"x": 300, "y": 214, "width": 220, "height": 90},
                 "textLength": 220},
                {"index": 1, "tag": "text", "text": "个低对比度问题",
                 "bbox": {"x": 300, "y": 316, "width": 240, "height": 26},
                 "textLength": 240},
            ]

        monkeypatch.setattr(chrome_geometry, "measure_svg_text_geometry", fake_measure)
        monkeypatch.setattr(bm, "_render_evidence", lambda s, o, *, brief_id: ("rendered", "clean"))

        out_dir = tmp_path / "bench-out"
        manifest, code = run_benchmark(
            REPO_BRIEFS, out_dir, yes=True, base_dir=tmp_path / "scratch",
        )
        assert code == 0
        assert manifest is not None
        assert manifest["brief_count"] == 6
        metric_entry = next(e for e in manifest["entries"] if e["family"] == "metric")
        assert metric_entry["model"] == "test-model"
        assert metric_entry["prompt_tokens"] == 111
        assert metric_entry["completion_tokens"] == 222
        assert metric_entry["finish_reason"] == "stop"
        assert metric_entry["latency_ms"] >= 0
        assert metric_entry["chrome_render"]["status"] == "rendered"
        assert metric_entry["machine_family_verdict"]["classified_as"] == "metric"
        assert metric_entry["machine_family_verdict"]["recognized"] is True
        # Manifest persisted, keyless, with the blind-review reference.
        persisted = json.loads((out_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
        assert persisted["brief_count"] == 6
        assert persisted["blind_review_reference"] == BLIND_REVIEW_FILENAME
        assert "test-key" not in json.dumps(persisted)
        assert (out_dir / BLIND_REVIEW_FILENAME).exists()
        assert (out_dir / "slide_01.svg").exists() or any(
            p.parent == out_dir for p in out_dir.glob("*.svg")
        )
