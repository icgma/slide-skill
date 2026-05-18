# Phase 3: SVG Design Pipeline - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement design spec generation, spec lock, SVG page generation, SVG compatibility checks, and finalization.
</domain>

<decisions>
## Implementation Decisions

### SVG Contract
- Require matching `width`, `height`, and `viewBox`.
- Require top-level semantic content groups.
- Reject unsupported tags and event/class/mask attributes.

### Design Defaults
- Start with a clean technical editorial deck style.
- Use stable palette and typography in `spec_lock.json`.
</decisions>

<code_context>
## Existing Code Insights

Phase 2 provides project metadata and normalized Markdown source.
</code_context>

<specifics>
## Specific Ideas

Keep the generator deterministic enough for tests; agents can hand-edit SVG for richer decks.
</specifics>

<deferred>
## Deferred Ideas

Advanced icon embedding and complex path transformations are deferred.
</deferred>
