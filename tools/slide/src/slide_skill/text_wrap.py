from __future__ import annotations
import re
from .util import xml_escape

def _char_width(ch: str, font_size: int) -> float:
    """Approximate advance width of a single character."""
    return font_size * (1.0 if ord(ch) >= 0x2E80 else 0.55)

def _token_width(token: str, font_size: int) -> float:
    """Sum of character widths for a token."""
    return sum(_char_width(c, font_size) for c in token)

def _is_cjk(ch: str) -> bool:
    """Return True if ch is a CJK/wide character."""
    return ord(ch) >= 0x2E80

def _tokenize_for_wrap(text: str) -> list[str]:
    """Split text into wrap-friendly tokens.

    CJK characters become individual tokens (can break between any two).
    Latin/digit runs stay together as one token (never break mid-word).
    Whitespace is attached to the preceding token where possible.
    Number+unit pairs ("6.5 小时", "89％", "2400 位") merge into one
    unbreakable cluster so a line never ends with a bare number.
    """
    tokens: list[str] = []
    buf = ""
    for ch in text:
        if _is_cjk(ch):
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
        elif ch in (" ", "\t"):
            buf += ch
        else:
            if buf.endswith((" ", "\t")) and any(not c.isspace() for c in buf):
                # Whitespace after a completed Latin word → flush word+space
                tokens.append(buf)
                buf = str(ch)
            elif buf and buf.rstrip() == "" and tokens:
                # Pure whitespace buffer after CJK → attach to prev token
                tokens[-1] += buf
                buf = str(ch)
            else:
                buf += ch
    if buf:
        tokens.append(buf)
    return _merge_number_unit(tokens)


# A Latin/digit token that is purely a number run (optionally followed by
# whitespace), e.g. "6.5 ", "2400 ", "89", "0.91".
_NUMBER_RUN = re.compile(r"^\d[\d.,]*[ \t]*$")

# Common two-character CJK measure words that must stay attached to their
# number as a whole ("6.5 小时" must not become "6.5 小 / 时").
_TWO_CHAR_UNITS = frozenset({
    "小时", "分钟", "公里", "千米", "毫米", "厘米",
    "千克", "公斤", "万元", "亿元", "个月", "年级",
})


def _merge_number_unit(tokens: list[str]) -> list[str]:
    """Merge digit-run tokens with their immediate CJK unit suffix.

    A digit sequence plus its unit ("6.5 小时", "89％", "2400 位") is an
    unbreakable cluster — a wrap must never separate the number from the
    unit that gives it meaning.
    """
    merged: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        is_unit_char = len(nxt) == 1 and (
            nxt == "％"
            or (
                _is_cjk(nxt)
                and nxt not in _KINSOKU_NO_START
                and nxt not in _KINSOKU_NO_END
            )
        )
        if _NUMBER_RUN.match(tok) and is_unit_char:
            cluster = tok + nxt
            i += 2
            # Extend to the full two-char unit word where known (小时, 分钟…)
            if (
                i < len(tokens)
                and len(tokens[i]) == 1
                and nxt + tokens[i] in _TWO_CHAR_UNITS
            ):
                cluster += tokens[i]
                i += 1
            merged.append(cluster)
        else:
            merged.append(tok)
            i += 1
    return merged

# CJK line-breaking (kinsoku) character classes.
# Leading-forbidden: characters that must not begin a line (closing marks).
_KINSOKU_NO_START = set(
    "，。、；：！？”’）》」』】〉〕｝］%％‰°·…—–～！？，。；：、）】》」』"
    ",.;:!?)]}%"
)
# Trailing-forbidden: characters that must not end a line (opening marks).
_KINSOKU_NO_END = set("（《「『【〈〔｛［“‘([{")


def _apply_kinsoku(lines: list[str], max_width_px: int, font_size: int) -> list[str]:
    """Apply CJK 避头尾 rules without ever widening a line past max_width_px.

    Adjustments are width-safe: a transformation is applied only when the
    receiving line still fits, so SVG QA (which wraps with the same model)
    stays consistent. Latin words are never split — only CJK characters are
    relocated.
    """
    if len(lines) < 2 or max_width_px <= 0:
        return lines
    lines = list(lines)

    def _fits(s: str) -> bool:
        return _token_width(s, font_size) <= max_width_px

    def _fix_leading() -> None:
        # No line after the first may start with a forbidden mark. Prefer
        # pulling the mark UP to the previous line (punctuation is narrow, so
        # the previous line usually has room). Fall back to pulling the
        # previous line's trailing CJK char DOWN when the lift does not fit.
        for i in range(1, len(lines)):
            guard = 0
            while lines[i] and lines[i][0] in _KINSOKU_NO_START and len(lines[i]) > 1:
                lifted = lines[i - 1] + lines[i][0]
                if _fits(lifted):
                    lines[i - 1] = lifted
                    lines[i] = lines[i][1:]
                elif len(lines[i - 1]) > 1 and _is_cjk(lines[i - 1][-1]):
                    candidate = lines[i - 1][-1] + lines[i]
                    if not _fits(candidate):
                        break
                    lines[i] = candidate
                    lines[i - 1] = lines[i - 1][:-1]
                else:
                    break
                guard += 1
                if guard > 8:
                    break

    def _fix_trailing() -> None:
        # No line may end with an opening mark. Push it down to the next line.
        for i in range(len(lines) - 1):
            guard = 0
            while lines[i] and lines[i][-1] in _KINSOKU_NO_END and lines[i + 1]:
                candidate = lines[i][-1] + lines[i + 1]
                if not _fits(candidate):
                    break
                lines[i + 1] = candidate
                lines[i] = lines[i][:-1]
                guard += 1
                if guard > 8:
                    break

    def _is_orphan_tail(line: str) -> bool:
        # An orphan tail is a stranded final line: 1-2 bare CJK chars, or a
        # single CJK char carrying only trailing punctuation ("例。").
        if not line:
            return False
        core = line
        trailing = ""
        while core and core[-1] in _KINSOKU_NO_START:
            trailing = core[-1] + trailing
            core = core[:-1]
        if not core or not all(_is_cjk(c) for c in core):
            return False
        return len(core) == 1 or (len(core) == 2 and not trailing)

    def _rebalance_orphan_tail() -> None:
        # Fix stranded final lines ("…文稿样 / 例。") by merging the tail up
        # when the previous line has slack, or by moving the break earlier
        # (pulling CJK chars down) so the final line reads as a word.
        if len(lines) < 2:
            return
        guard = 0
        while _is_orphan_tail(lines[-1]) and guard < 8:
            guard += 1
            prev, last = lines[-2], lines[-1]
            merged = prev + last
            if _fits(merged):
                lines[-2] = merged
                del lines[-1]
                if len(lines) < 2:
                    return
                continue
            pull = prev[-1]
            if (
                not _is_cjk(pull)
                or pull in _KINSOKU_NO_START
                or len(prev) < 3
                or not _fits(pull + last)
            ):
                break
            lines[-2] = prev[:-1]
            lines[-1] = pull + last
        # Pulling chars down may leave the previous line ending on an
        # opening mark — re-run the directional fixes to restore kinsoku.
        _fix_leading()
        _fix_trailing()

    _fix_leading()
    _fix_trailing()
    _rebalance_orphan_tail()

    return [ln for ln in lines if ln != ""] or lines


def _visual_wrap(text: str, max_width_px: int, font_size: int) -> list[str]:
    """Wrap a string into visual lines that fit within max_width_px.

    Wraps at word boundaries for Latin text and at character boundaries
    for CJK text.  Never breaks an English word in the middle unless
    the word alone is wider than the available width.
    """
    if not text:
        return []

    # Handle explicit newlines first
    raw_lines = text.split("\n")
    result: list[str] = []

    for raw_line in raw_lines:
        tokens = _tokenize_for_wrap(raw_line)
        if not tokens:
            result.append("")
            continue

        block: list[str] = []
        cur_line = ""
        cur_w = 0.0

        for token in tokens:
            tw = _token_width(token, font_size)

            if tw > max_width_px and max_width_px > 0:
                if cur_line:
                    block.append(cur_line.rstrip())
                    cur_line = ""
                    cur_w = 0.0
                chunk = ""
                chunk_w = 0.0
                for ch in token:
                    cw = _char_width(ch, font_size)
                    if chunk and chunk_w + cw > max_width_px:
                        block.append(chunk.rstrip())
                        chunk = ch
                        chunk_w = cw
                    else:
                        chunk += ch
                        chunk_w += cw
                if chunk:
                    cur_line = chunk
                    cur_w = chunk_w
                continue

            if cur_w + tw <= max_width_px or not cur_line:
                # Fits, or first token on line (must accept even if too wide)
                cur_line += token
                cur_w += tw
            else:
                # Doesn't fit → wrap: emit current line, start new line
                block.append(cur_line.rstrip())
                # Keep the full token (with trailing space) so the next
                # token concatenates with proper word separation.
                cur_line = token
                cur_w = tw

        if cur_line:
            block.append(cur_line.rstrip())

        result.extend(_apply_kinsoku(block, max_width_px, font_size))

    return result

def _wrap_to_tspans(
    text: str, x: int, font_size: int, max_width_px: int,
    line_height: float = 1.4,
) -> tuple[str, int]:
    """Return (joined `<tspan>` xml, total visual line count) for a text run.

    If text is empty or whitespace-only, returns empty string with 0 lines.
    """
    text = _strip_inline_md(text)
    # Don't generate empty tspan for empty/whitespace text
    if not text.strip():
        return "", 0

    lines = _visual_wrap(text, max_width_px, font_size)
    if not lines:
        return "", 0

    dy = int(font_size * line_height)
    parts = []
    for i, line in enumerate(lines):
        d = "0" if i == 0 else str(dy)
        parts.append(
            f'<tspan x="{x}" dy="{d}">{xml_escape(line)}</tspan>'
        )
    return "".join(parts), len(lines)


def fit_text_to_box(
    text: str,
    max_width_px: int,
    max_height_px: int,
    *,
    max_font_size: int,
    min_font_size: int = 12,
    line_height: float = 1.25,
) -> tuple[int, list[str], int]:
    """Choose the largest font size whose wrapped lines fit a box.

    Returns ``(font_size, lines, line_dy)``. The wrapping model is intentionally
    the same approximation used by SVG QA so generated text and QA agree.
    """
    clean = _strip_inline_md(text).strip()
    if not clean:
        return min_font_size, [], int(min_font_size * line_height)

    width = max(1, max_width_px)
    height = max(1, max_height_px)
    for font_size in range(max_font_size, min_font_size - 1, -1):
        lines = _visual_wrap(clean, width, font_size)
        line_dy = max(1, int(font_size * line_height))
        text_h = font_size + max(0, len(lines) - 1) * line_dy
        if lines and text_h <= height:
            return font_size, lines, line_dy

    font_size = min_font_size
    lines = _visual_wrap(clean, width, font_size)
    line_dy = max(1, int(font_size * line_height))
    max_lines = max(1, (height + line_dy - font_size) // line_dy)
    return font_size, lines[:max_lines], line_dy


def fitted_tspans(
    text: str,
    x: int,
    max_width_px: int,
    max_height_px: int,
    *,
    max_font_size: int,
    min_font_size: int = 12,
    line_height: float = 1.25,
) -> tuple[str, int, int, int]:
    """Return ``(tspans, line_count, font_size, line_dy)`` for fitted text."""
    font_size, lines, line_dy = fit_text_to_box(
        text,
        max_width_px,
        max_height_px,
        max_font_size=max_font_size,
        min_font_size=min_font_size,
        line_height=line_height,
    )
    parts = [
        f'<tspan x="{x}" dy="{"0" if i == 0 else line_dy}">{xml_escape(line)}</tspan>'
        for i, line in enumerate(lines)
    ]
    return "".join(parts), len(lines), font_size, line_dy

def _strip_inline_md(text: str) -> str:
    """Strip inline markdown (**bold**, *italic*) only — leave block markers."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    return text

def _estimate_text_bounds(
    text: str,
    font_size: int,
    x: int,
    y: int,
    max_width: int | None = None,
    line_height: float = 1.45,
) -> tuple[int, int, int, int]:
    """Estimate pixel bounding box (x, y_top, x_right, y_bottom) for a text run.

    Uses the same character-width model as _visual_wrap.
    If max_width is given, accounts for wrapping.
    """
    if not text:
        return (x, y, x, y)

    if max_width:
        wrapped = _visual_wrap(text, max_width, font_size)
    else:
        wrapped = [text]

    line_dy = int(font_size * line_height)
    max_line_w = max(
        (_token_width(line, font_size) for line in wrapped),
        default=0,
    )
    y_top = y - font_size  # approximate ascent
    y_bottom = y + (len(wrapped) - 1) * line_dy
    return (x, int(y_top), int(x + max_line_w), int(y_bottom))

