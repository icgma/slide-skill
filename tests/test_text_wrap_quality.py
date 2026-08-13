"""CJK line-break quality benchmark (Phase 52, ACAD-02).

Table-driven guards for the four wrap-defect classes fixed in v5.0:

1. ORPHAN TAIL      — final line must not strand 1-2 CJK chars ("样 / 例。").
2. LATIN TOKEN      — ASCII words/identifiers never split mid-token.
3. NUMBER+UNIT      — digit runs stay attached to their unit ("6.5 小时", "89％").
4. KINSOKU          — no line ends with an opener（「【 or starts with a closer 。，％.

Plus a control case proving greedy line fill did not regress (each
non-final line >= 70% of max width for plain CJK prose).
"""

from __future__ import annotations

import pytest

from slide_skill.text_wrap import (
    _KINSOKU_NO_END,
    _KINSOKU_NO_START,
    _token_width,
    _visual_wrap,
)


def _assert_lines_fit(lines: list[str], max_width_px: int, font_size: int) -> None:
    for line in lines:
        assert _token_width(line, font_size) <= max_width_px, (
            f"line exceeds width: {line!r}"
        )


def _assert_content_preserved(text: str, lines: list[str]) -> None:
    # Line breaks may drop inter-token whitespace; no other char may vanish.
    assert "".join(lines).replace(" ", "").replace("\t", "") == (
        text.replace(" ", "").replace("\t", "")
    )


def _assert_no_orphan_tail(lines: list[str]) -> None:
    last = lines[-1]
    core = last
    while core and core[-1] in _KINSOKU_NO_START:
        core = core[:-1]
    if core and all(ord(c) >= 0x2E80 for c in core):
        stripped_punct = len(core) != len(last)
        assert len(core) >= 3 or (len(core) == 2 and stripped_punct), (
            f"orphan tail line: {last!r}"
        )


def _assert_kinsoku(lines: list[str]) -> None:
    for i, line in enumerate(lines):
        if i > 0:
            assert line[0] not in _KINSOKU_NO_START, (
                f"line starts with closing mark: {line!r}"
            )
        if i < len(lines) - 1:
            assert line[-1] not in _KINSOKU_NO_END, (
                f"line ends with opening mark: {line!r}"
            )


# ---------------------------------------------------------------------------
# 1. Orphan tail — the verified historical defect and generic cases
# ---------------------------------------------------------------------------

class TestOrphanTail:
    def test_historical_defect_sample_sentence(self) -> None:
        """The exact QA-extracted defect: '…文稿样' + '例。' at width 490/fs 20."""
        text = "一份用 slide-skill 一行命令生成的中文演示文稿样例。"
        lines = _visual_wrap(text, 490, 20)
        assert len(lines) >= 2
        assert lines[-1] == "样例。", f"expected balanced tail, got {lines!r}"
        _assert_lines_fit(lines, 490, 20)
        _assert_content_preserved(text, lines)
        _assert_no_orphan_tail(lines)

    @pytest.mark.parametrize("width", [400, 420, 440, 460, 480, 490, 500])
    def test_sample_sentence_never_orphans_at_any_width(self, width: int) -> None:
        text = "一份用 slide-skill 一行命令生成的中文演示文稿样例。"
        lines = _visual_wrap(text, width, 20)
        _assert_lines_fit(lines, width, 20)
        _assert_content_preserved(text, lines)
        _assert_no_orphan_tail(lines)
        _assert_kinsoku(lines)

    def test_single_char_tail_pulled_back(self) -> None:
        # 21 CJK chars at 10 chars/line would greedily leave a 1-char tail.
        text = "这是一个关于中文换行质量控制的很长句子测试文本"
        lines = _visual_wrap(text, 200, 20)
        _assert_no_orphan_tail(lines)
        _assert_lines_fit(lines, 200, 20)
        _assert_content_preserved(text, lines)

    def test_merge_up_when_previous_line_has_slack(self) -> None:
        # Kinsoku pushes can leave a mergeable tail; the whole text fits two
        # lines comfortably — the tail must not remain stranded when the
        # previous line has slack for it.
        text = "中文排版质量特别重要哦"
        lines = _visual_wrap(text, 200, 20)
        _assert_no_orphan_tail(lines)
        _assert_content_preserved(text, lines)


# ---------------------------------------------------------------------------
# 2. Latin token integrity
# ---------------------------------------------------------------------------

class TestLatinTokenIntegrity:
    @pytest.mark.parametrize(
        "text,width",
        [
            ("本项目 slide-skill 支持中文排版", 160),
            ("本项目 slide-skill 支持中文排版", 200),
            ("使用 PPTX 格式导出全部页面内容", 140),
            ("训练框架 TensorFlow 与推理引擎", 180),
        ],
    )
    def test_ascii_identifier_never_splits(self, text: str, width: int) -> None:
        lines = _visual_wrap(text, width, 20)
        token = next(t for t in ("slide-skill", "PPTX", "TensorFlow") if t in text)
        assert any(token in line for line in lines), (
            f"token {token!r} split across lines: {lines!r}"
        )
        _assert_lines_fit(lines, width, 20)
        _assert_content_preserved(text, lines)


# ---------------------------------------------------------------------------
# 3. Number + unit integrity
# ---------------------------------------------------------------------------

class TestNumberUnitIntegrity:
    @pytest.mark.parametrize(
        "text,unit_cluster,width",
        [
            # Boundary width where the break previously landed between
            # the number and its unit.
            ("平均每份提案节省 6.5 小时", "6.5 小时", 220),
            ("平均每份提案节省 6.5 小时", "6.5 小时", 240),
            ("模板复用率提升至 89％", "89％", 200),
            ("覆盖师生共计 2400 位用户", "2400 位", 200),
            ("模型误差 MAE 下降 12.4%", "12.4%", 200),
        ],
    )
    def test_number_stays_with_unit(
        self, text: str, unit_cluster: str, width: int
    ) -> None:
        lines = _visual_wrap(text, width, 20)
        assert any(unit_cluster in line for line in lines), (
            f"number+unit {unit_cluster!r} split: {lines!r}"
        )
        _assert_lines_fit(lines, width, 20)
        _assert_content_preserved(text, lines)

    @pytest.mark.parametrize("width", [180, 200, 220, 240, 260, 280])
    def test_no_line_ends_with_bare_number(self, width: int) -> None:
        text = "实验结果显示预测精度提升 15 个百分点以上"
        lines = _visual_wrap(text, width, 20)
        for line in lines[:-1]:
            assert not line.rstrip().endswith("15"), (
                f"line ends with bare number: {lines!r}"
            )
        _assert_content_preserved(text, lines)


# ---------------------------------------------------------------------------
# 4. Kinsoku — both directions at line edges
# ---------------------------------------------------------------------------

class TestKinsoku:
    @pytest.mark.parametrize(
        "text",
        [
            "研究方法（问卷调查）与数据分析结果",
            "结果表明，模型有效。后续工作将继续推进",
            "核心指标【准确率】显著优于基线方案",
            "他说：「这个方案可行」并给出了理由",
        ],
    )
    @pytest.mark.parametrize("width", [120, 140, 160, 180, 200])
    def test_no_forbidden_line_edges(self, text: str, width: int) -> None:
        lines = _visual_wrap(text, width, 20)
        _assert_kinsoku(lines)
        _assert_lines_fit(lines, width, 20)
        _assert_content_preserved(text, lines)

    def test_fullwidth_percent_never_starts_line(self) -> None:
        text = "模板复用率提升至 89％，用户满意度同步上升"
        for width in (180, 200, 220, 240):
            lines = _visual_wrap(text, width, 20)
            for line in lines[1:]:
                assert not line.startswith("％"), f"％ starts line: {lines!r}"


# ---------------------------------------------------------------------------
# 5. Control — no under-fill regression
# ---------------------------------------------------------------------------

class TestFillControl:
    def test_plain_cjk_lines_fill_efficiently(self) -> None:
        text = (
            "中文自动换行需要兼顾行宽利用率与断行质量两个目标"
            "既不能把标点推到行首也不能让最后一行只剩下一两个字"
            "同时正常段落的每一行都应该尽量填满可用宽度避免碎行"
        )
        width, fs = 300, 20
        lines = _visual_wrap(text, width, fs)
        assert len(lines) >= 3
        for line in lines[:-1]:
            assert _token_width(line, fs) >= 0.7 * width, (
                f"under-filled non-final line: {line!r} in {lines!r}"
            )
        _assert_lines_fit(lines, width, fs)
        _assert_content_preserved(text, lines)

    def test_mixed_cjk_latin_control(self) -> None:
        text = "slide-skill 工具链覆盖了从 Markdown 源文档到可编辑 PPTX 的完整流程"
        width, fs = 260, 20
        lines = _visual_wrap(text, width, fs)
        _assert_lines_fit(lines, width, fs)
        _assert_content_preserved(text, lines)
        _assert_no_orphan_tail(lines)
        _assert_kinsoku(lines)
