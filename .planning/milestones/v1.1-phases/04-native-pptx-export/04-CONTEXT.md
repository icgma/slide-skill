# Phase 4: Native PPTX Export - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Convert finalized SVG pages into `.pptx` decks with native editable objects where supported, preserve notes, backup artifacts, and validate output.
</domain>

<decisions>
## Implementation Decisions

### Export Library
- Use `python-pptx`, already available in the environment.

### Native Scope
- Map supported SVG primitives natively: rect, circle/ellipse, line, text, image.
- Do not claim native support for complex paths in v1.
</decisions>

<code_context>
## Existing Code Insights

Phase 3 produces simple checked SVGs that avoid unsupported constructs.
</code_context>

<specifics>
## Specific Ideas

Validate exported PPTX by checking ZIP package structure and native shape/text presence.
</specifics>

<deferred>
## Deferred Ideas

Direct notes embedding and full custom geometry path conversion are deferred.
</deferred>
