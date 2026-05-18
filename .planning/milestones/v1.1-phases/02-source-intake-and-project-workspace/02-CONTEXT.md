# Phase 2: Source Intake And Project Workspace - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement project workspace creation, source import, validation, and source-to-Markdown conversion for common document inputs.
</domain>

<decisions>
## Implementation Decisions

### Runtime
- Use Python-first tooling.
- Keep optional heavy converters optional.

### Workspace
- Standard directories: `sources`, `images`, `svg_output`, `svg_final`, `notes`, `exports`, `backup`, `qa`.
</decisions>

<code_context>
## Existing Code Insights

Phase 1 created package scaffolding and skill docs.
</code_context>

<specifics>
## Specific Ideas

Prefer pure-Python OOXML extraction for DOCX/XLSX/PPTX where feasible.
</specifics>

<deferred>
## Deferred Ideas

Full-fidelity PDF table/image extraction is deferred behind optional dependencies.
</deferred>
