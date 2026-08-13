from __future__ import annotations
import re

def _select_layout(heading: str, body: str, index: int, total: int) -> str:
    """Content-driven layout router. Returns a layout name string.

    Order matters — earlier checks win. Designed so common patterns map to
    the richest applicable layout (executive_summary, process_flow, etc.)
    instead of falling through to plain bullet-list every time.
    """
    if not body.strip():
        return "section-divider"
    raw_lines = [line for line in body.split("\n") if line.strip()]
    lines = [line.strip() for line in raw_lines]
    bullet_lines = [line[2:].strip() for line in lines if line.startswith("- ")]

    # Quote / takeaway: body starts with "> " or wrapped in fancy quotes.
    first = lines[0]
    if first.startswith("> ") or first.startswith("\u201c") or first.startswith('"'):
        return "quote-block"

    # Process flow: bullets separated by "→" arrows OR numbered step prefixes.
    has_arrows = any("→" in line or "->" in line for line in lines)
    numbered = sum(1 for line in lines if re.match(r"^\d+[\.、)]\s", line))
    if has_arrows or numbered >= 3:
        return "process-flow"

    # Markdown table: header | separator (|---|) | data rows
    table_sep = re.compile(r"^\|[\s\-:]+\|[\s\-:|]*\|$")
    pipe_lines = [l for l in lines if l.startswith("|") and l.endswith("|")]
    has_table_sep = any(table_sep.match(l) for l in lines)
    if has_table_sep and len(pipe_lines) >= 3:
        return "table"

    # Comparison: explicit "vs" OR at least one line shaped as
    # "label | description" with both sides non-empty. A bare pipe
    # anywhere in the body is too broad and matches markdown tables.
    pipe_pairs = [
        line for line in lines
        if "|" in line
        and line.split("|", 1)[0].strip()
        and line.split("|", 1)[1].strip()
    ]
    if re.search(r"\bvs\.?\b", body, re.IGNORECASE) or re.search(r"\bvs\.?\b", heading, re.IGNORECASE) or len(pipe_pairs) >= 2:
        return "comparison"

    # Metric-highlight: bullet items dominated by numeric/percentage data
    # (e.g. "- 32% YoY growth"). Must beat the generic bullet fallback.
    if bullet_lines:
        metric_bullets = sum(
            1 for b in bullet_lines if re.search(r"\d+\s*[%％]|\d+\s*[万亿KMB]", b)
        )
        if metric_bullets >= max(2, len(bullet_lines) // 2):
            return "metric-highlight"

    # Executive summary: 3-6 short bullet items (avg < 50 chars), title-like.
    if 3 <= len(bullet_lines) <= 6:
        avg_len = sum(len(b) for b in bullet_lines) / len(bullet_lines)
        if avg_len < 50:
            return "executive-summary"

    if bullet_lines:
        return "bullet-list"
    if re.search(r"\d+%|\d+[万亿]", body):
        return "metric-highlight"
    return "default"

def _distribute_layouts(
    layouts: list[str],
    slides: list[tuple[str, str]] | None = None,
) -> list[str]:
    """Anti-monotony pass: break up runs of 3+ identical content layouts.

    Keeps cover / section-divider / closing untouched. For a run of the
    same content layout, rotates the middle slide to a contrasting layout
    — but only to a layout that can fit all of that slide's content
    (so we never silently truncate bullets, etc.).
    """
    chrome = {"cover", "section-divider", "closing"}
    result = list(layouts)

    def _bullet_count(idx: int) -> int:
        if not slides or idx >= len(slides):
            return 99
        body = slides[idx][1]
        return sum(
            1 for line in body.split("\n")
            if line.strip().startswith(("- ", "* ", "• "))
        )

    def _safe_rotation(cur: str, idx: int) -> str | None:
        # Pick a contrasting layout that preserves this slide's content.
        if cur == "bullet-list":
            # Only collapse to 3-card summary if it really has ≤3 bullets.
            if _bullet_count(idx) <= 3:
                return "executive-summary"
            # Otherwise keep all content but use the default chrome.
            return "default"
        if cur == "executive-summary":
            # bullet-list always preserves all bullets.
            return "bullet-list"
        if cur == "default":
            return "bullet-list" if _bullet_count(idx) > 0 else None
        if cur == "metric-highlight":
            return "default"
        return None

    i = 1
    while i < len(result) - 1:
        prev, cur, nxt = result[i - 1], result[i], result[i + 1]
        if cur in chrome:
            i += 1
            continue
        if prev == cur == nxt:
            alt = _safe_rotation(cur, i)
            if alt and alt != cur:
                result[i] = alt
        i += 1
    return result

