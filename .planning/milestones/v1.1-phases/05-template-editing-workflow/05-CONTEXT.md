# Phase 5: Template Editing Workflow - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Provide conservative PPTX template inspection, text replacement, and structural slide operations on copied outputs.
</domain>

<decisions>
## Implementation Decisions

### Safety
- Never mutate input PPTX in place.
- Operate through temporary unpack/pack cycles.

### Scope
- Support inspect, replace text, delete, reorder, and duplicate slide operations.
</decisions>

<code_context>
## Existing Code Insights

Phase 4 can generate fixture PPTX files for template operation tests.
</code_context>

<specifics>
## Specific Ideas

Use OOXML relationship updates for slide list operations and validate resulting PPTX.
</specifics>

<deferred>
## Deferred Ideas

Rich layout matching and master/theme editing are deferred.
</deferred>
