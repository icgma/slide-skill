# Phase 31: Advanced Filter Effects - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 31-Advanced Filter Effects
**Areas discussed:** Filter graph detection, Multi-effect composition, Glow radius and color, SVG pipeline glow generation

---

## Filter graph detection

| Option | Description | Selected |
|--------|-------------|----------|
| Pattern-based detection | Check blur in= attribute + scan siblings for feFlood/feComposite/feOffset presence | ✓ |
| Full graph traversal | Build result-name graph, trace chains | |
| Hybrid approach | Pattern-based first, fall back to graph traversal for unrecognized chains | |

**Notes:** 21 decision points total. Key decisions: glow precedence over soft edge, SourceAlpha required, feComposite operator="in" required, track result names for chain verification.

---

## Multi-effect composition

| Option | Description | Selected |
|--------|-------------|----------|
| Replace effectLst | Remove existing effectLst, create fresh with all detected effects | ✓ |
| Merge into existing | Preserve existing effects, add new ones | |

**Notes:** 13 decision points. Key decisions: explicit XSD order constant, two separate reorder functions, softEdge replaces blur (mutually exclusive), glow+shadow can coexist, single apply_filter_to_shape handles all types internally.

---

## Glow radius and color

| Option | Description | Selected |
|--------|-------------|----------|
| stdDeviation * 25400 | Same multiplier as blur | ✓ |
| stdDeviation * 50800 | Double multiplier for visually larger glow | |
| You decide | Match PowerPoint's native glow behavior | |

**Notes:** 5 decision points. All defaults follow existing patterns: 25400 multiplier, direct opacity mapping, full default alpha, srgbClr only, negative stdDeviation clamped to 0.

---

## SVG pipeline glow generation

| Option | Description | Selected |
|--------|-------------|----------|
| Add both filter defs | _soft_edge_filter_def() and _glow_filter_def() helpers | ✓ |
| Skip pipeline generators | Only parse/export, no SVG generation | |
| Glow only | Only glow filter def (soft edge is simple) | |

**Notes:** 7 decision points. Utility functions only (no layout integration). Glow uses palette accent color + 0.5 opacity defaults, soft edge uses stdDeviation=3. Same filter region as card-shadow. feMerge included for glow.

---

## Claude's Discretion

No areas deferred — user selected all recommended options.

## Deferred Ideas

None — discussion stayed within phase scope.
