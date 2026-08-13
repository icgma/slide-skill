"""Closed-world content fidelity regression tests — Phase 49-02.

REDESIGN_v5 1.2C verified that the model invents plausible-but-unsourced
claims: sample 1 added judgments like 无需额外数据准备 that were never in the
plan, and the old ``_check_content_fidelity`` only checked the "missing"
direction. These tests prove the bidirectional contract:

* planned content missing from the page still blocks (unchanged direction);
* visible text that is neither planned content nor an approved derived label
  blocks with ``unsupported-visible-text``;
* visible numbers absent from the plan/source corpus block with
  ``unsourced-number``;
* legitimate wrapped lines, page footers, and enumeration markers never
  false-positive.
"""
from pathlib import Path

from slide_skill.ai_executor import _check_content_fidelity
from slide_skill.content_planner import ContentItem, SlidePlan


def _svg(body: str) -> str:
    return (
        '<svg width="1280" height="720" viewBox="0 0 1280 720" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
        f"{body}"
        "</svg>"
    )


def _fidelity_issues(issues) -> list:
    return [issue for issue in issues if "Content fidelity" in issue.message]


def _unsupported(issues) -> list:
    return [issue for issue in issues if "unsupported-visible-text" in issue.message]


def _unsourced(issues) -> list:
    return [issue for issue in issues if "unsourced-number" in issue.message]


class TestInventedClaimsBlock:
    """REDESIGN_v5 sample-1 scenario: invented judgments must block publish."""

    PLAN = SlidePlan(
        index=2,
        layout="comparison",
        title="三种推理策略对比",
        items=[
            ContentItem(type="text", primary="Zero-shot", secondary="直接生成答案"),
            ContentItem(type="text", primary="Few-shot", secondary="提供少量示例后推理"),
            ContentItem(type="text", primary="Chain-of-Thought", secondary="逐步展开推理链"),
        ],
    )

    INVENTED = ["无需额外数据准备", "成本最低、响应最快", "复杂任务易出错"]

    def test_sample_1_invented_claims_all_flagged_blocking(self, tmp_path):
        cards = "".join(
            f'<g id="content-card-{i:02d}"><text x="{100 + i * 300}" y="300" '
            f'font-size="20" fill="#94A3B8">{claim}</text></g>'
            for i, claim in enumerate(self.INVENTED, start=1)
        )
        svg = _svg(
            '<g id="content-title-02"><text x="96" y="120" font-size="40" '
            'fill="#F8FAFC">三种推理策略对比</text></g>'
            '<g id="content-body-02">'
            '<text x="96" y="200" font-size="24" fill="#F8FAFC">Zero-shot</text>'
            '<text x="96" y="240" font-size="20" fill="#94A3B8">直接生成答案</text>'
            "</g>"
            f"{cards}"
        )
        path = tmp_path / "slide_02.svg"
        path.write_text(svg, encoding="utf-8")

        issues = _check_content_fidelity(path, svg, self.PLAN)

        flagged = _unsupported(issues)
        for claim in self.INVENTED:
            assert any(claim in issue.message for issue in flagged), claim
        # Blocking: errors block regardless of strict_quality.
        assert all(issue.level == "error" for issue in flagged)

    def test_planned_content_only_passes(self, tmp_path):
        svg = _svg(
            '<g id="content-title-02"><text x="96" y="120">三种推理策略对比</text></g>'
            '<g id="content-body-02">'
            '<text x="96" y="200">Zero-shot</text>'
            '<text x="96" y="230">直接生成答案</text>'
            '<text x="96" y="280">Few-shot</text>'
            '<text x="96" y="310">提供少量示例后推理</text>'
            '<text x="96" y="360">Chain-of-Thought</text>'
            '<text x="96" y="390">逐步展开推理链</text>'
            "</g>"
        )
        path = tmp_path / "slide_02.svg"
        path.write_text(svg, encoding="utf-8")

        issues = _check_content_fidelity(path, svg, self.PLAN)

        assert not _fidelity_issues(issues)


class TestLegitimateDeckZeroFalsePositives:
    """Every visible string traces to plan fields: zero fidelity issues."""

    def test_wrapped_tspans_and_page_footer_pass(self, tmp_path):
        plan = SlidePlan(
            index=3,
            layout="bullet-list",
            title="Python 入门速览",
            items=[
                ContentItem(
                    type="bullet",
                    primary="动态类型提升入门效率，但需要通过测试减少类型错误",
                ),
                ContentItem(type="bullet", primary="Reliable provider response gating"),
            ],
        )
        svg = _svg(
            '<g id="content-title-03"><text x="96" y="120" font-size="40" '
            'fill="#F8FAFC">Python 入门速览</text></g>'
            '<g id="content-body-03">'
            # Wrapped 2-tspan line: chunks reflow the planned item.
            '<text x="96" y="200" font-size="24" fill="#94A3B8">'
            '<tspan x="96" dy="0">动态类型提升入门效率，</tspan>'
            '<tspan x="96" dy="34">但需要通过测试减少类型错误</tspan>'
            "</text>"
            '<text x="96" y="290" font-size="24" fill="#94A3B8">'
            '<tspan x="96" dy="0">Reliable provider</tspan>'
            '<tspan x="96" dy="34">response gating</tspan>'
            "</text>"
            "</g>"
            '<g id="chrome-footer"><text x="1180" y="700" font-size="12" '
            'fill="#94A3B8" text-anchor="end">03 / 14</text></g>'
        )
        path = tmp_path / "slide_03.svg"
        path.write_text(svg, encoding="utf-8")

        issues = _check_content_fidelity(path, svg, plan)

        assert _fidelity_issues(issues) == []

    def test_hidden_and_defs_text_never_flagged(self, tmp_path):
        plan = SlidePlan(
            index=1,
            layout="cover",
            title="封面标题",
            items=[ContentItem(type="text", primary="正文要点")],
        )
        svg = _svg(
            "<defs><text>defs-only ghost text 9999</text></defs>"
            '<g id="content-title-01"><text x="96" y="120">封面标题</text></g>'
            '<g id="content-body-01"><text x="96" y="200">正文要点</text></g>'
            '<g opacity="0"><text x="96" y="400">invisible invented claim</text></g>'
        )
        path = tmp_path / "slide_01.svg"
        path.write_text(svg, encoding="utf-8")

        issues = _check_content_fidelity(path, svg, plan)

        assert _fidelity_issues(issues) == []


class TestNumberSourceCheck:
    PLAN = SlidePlan(
        index=4,
        layout="metric-highlight",
        title="核心指标",
        items=[ContentItem(type="metric", primary="转化率达到 73%", meta={"number": "73%"})],
    )

    def test_invented_percentage_blocks(self, tmp_path):
        plan = SlidePlan(
            index=4,
            layout="metric-highlight",
            title="核心指标",
            items=[ContentItem(type="metric", primary="转化率显著提升")],
        )
        svg = _svg(
            '<g id="content-title-04"><text x="96" y="120">核心指标</text></g>'
            '<g id="content-body-04">'
            '<text x="96" y="240">转化率显著提升 73%</text>'
            "</g>"
        )
        path = tmp_path / "slide_04.svg"
        path.write_text(svg, encoding="utf-8")

        issues = _check_content_fidelity(path, svg, plan)

        flagged = _unsourced(issues)
        assert any("73%" in issue.message for issue in flagged)
        assert all(issue.level == "error" for issue in flagged)

    def test_planned_number_passes(self, tmp_path):
        svg = _svg(
            '<g id="content-title-04"><text x="96" y="120">核心指标</text></g>'
            '<g id="content-body-04"><text x="96" y="240">转化率达到 73%</text></g>'
        )
        path = tmp_path / "slide_04.svg"
        path.write_text(svg, encoding="utf-8")

        issues = _check_content_fidelity(path, svg, self.PLAN)

        assert _fidelity_issues(issues) == []

    def test_big_numeral_split_percent_traced_via_meta(self, tmp_path):
        # Hero metric rendered as "73" + "%" tspans; meta {"number": "73%"}
        # sources the concatenated token.
        svg = _svg(
            '<g id="content-title-04"><text x="96" y="120">核心指标</text></g>'
            '<g id="content-body-04">'
            '<text x="96" y="240">转化率达到 73%</text>'
            '<text x="400" y="420" font-size="140">'
            '<tspan>73</tspan><tspan font-size="70">%</tspan>'
            "</text>"
            "</g>"
        )
        path = tmp_path / "slide_04.svg"
        path.write_text(svg, encoding="utf-8")

        issues = _check_content_fidelity(path, svg, self.PLAN)

        assert _fidelity_issues(issues) == []


class TestEnumerationMarkers:
    def test_enumeration_markers_pass_without_plan_entries(self, tmp_path):
        plan = SlidePlan(
            index=5,
            layout="timeline",
            title="实施路线",
            items=[
                ContentItem(type="step", primary="固化基线"),
                ContentItem(type="step", primary="修正 QA"),
                ContentItem(type="step", primary="并发提速"),
            ],
        )
        steps = "".join(
            f'<g id="content-step-{i:02d}">'
            f'<text x="{100 + i * 260}" y="300" font-size="48" fill="#3B82F6">{i:02d}</text>'
            f'<text x="{100 + i * 260}" y="360" font-size="22" fill="#F8FAFC">{label}</text>'
            "</g>"
            for i, label in enumerate(["固化基线", "修正 QA", "并发提速"], start=1)
        )
        svg = _svg(
            '<g id="content-title-05"><text x="96" y="120">实施路线</text></g>'
            f"{steps}"
            '<g id="chrome-footer"><text x="1180" y="700" text-anchor="end">05 / 14</text></g>'
        )
        path = tmp_path / "slide_05.svg"
        path.write_text(svg, encoding="utf-8")

        issues = _check_content_fidelity(path, svg, plan)

        assert _fidelity_issues(issues) == []

    def test_roman_and_letter_markers_pass(self, tmp_path):
        plan = SlidePlan(
            index=6,
            layout="bullet-list",
            title="议程",
            items=[ContentItem(type="bullet", primary="研究背景")],
        )
        svg = _svg(
            '<g id="content-title-06"><text x="96" y="120">议程</text></g>'
            '<g id="content-body-06">'
            '<text x="96" y="220">III</text>'
            '<text x="96" y="260">B</text>'
            '<text x="140" y="220">研究背景</text>'
            "</g>"
        )
        path = tmp_path / "slide_06.svg"
        path.write_text(svg, encoding="utf-8")

        issues = _check_content_fidelity(path, svg, plan)

        assert _fidelity_issues(issues) == []


class TestMissingDirectionUnchanged:
    """The original required→visible direction still blocks omissions."""

    def test_missing_planned_item_still_flagged(self, tmp_path):
        plan = SlidePlan(
            index=7,
            layout="bullet-list",
            title="必须出现的标题",
            items=[ContentItem(type="bullet", primary="必须出现的要点")],
        )
        svg = _svg(
            '<g id="content-title-07"><text x="96" y="120">必须出现的标题</text></g>'
        )
        path = tmp_path / "slide_07.svg"
        path.write_text(svg, encoding="utf-8")

        issues = _check_content_fidelity(path, svg, plan)

        assert any("missing planned content item" in issue.message for issue in issues)
