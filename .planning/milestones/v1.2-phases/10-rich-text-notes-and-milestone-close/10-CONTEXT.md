# Phase 10 Context: Rich-Text Notes and Milestone Close

**Phase:** 10
**Milestone:** v1.2
**Created:** 2026-05-01
**Status:** Ready for planning

## Goal

Add basic rich-text formatting (bold, italic, lists) to embedded speaker notes with backward compatibility, then close the milestone.

## Requirements

- NTS-01: `**bold**` in notes → bold runs in PPTX notes
- NTS-02: `*italic*` in notes → italic runs in PPTX notes
- NTS-03: `- bullet` items → indented paragraphs in PPTX notes
- NTS-04: Bold, italic, lists combined in a single notes block
- NTS-05: Plain-text notes produce identical output to v1.1 (backward compatible)

## Decisions

### Implementation approach
- Replace `_embed_slide_notes()` in exporter.py with `_embed_rich_notes()`
- Parse notes markdown into runs: `**bold**` → bold run, `*italic*` → italic run, plain text → normal run
- `- bullet` items → separate paragraphs with indent level
- If no markdown formatting detected, use plain text (identical to v1.1 behavior)

### Markdown parsing
- Simple regex-based parser: no external library needed
- Patterns: `\*\*(.+?)\*\*` for bold, `\*(.+?)\*` for italic, `^[-*]\s+(.+)` for bullets
- Bold takes precedence over italic (greedy match)

### Scope
- In scope: bold, italic, bullet lists, backward compatibility, milestone close
- Out of scope: links, colored text, numbered lists, tables in notes

---
*Context created: 2026-05-01*
