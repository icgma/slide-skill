# Phase 11 Context: Slide Transitions and Element Animations

**Phase:** 11
**Milestone:** v1.3
**Created:** 2026-05-01
**Status:** Ready

## Goal

Add `<p:transition>` slide transitions and `<p:timing>` entrance animations to exported PPTX shapes via SVG semantic group hooks.

## Implementation

### Slide Transitions
- Parse `data-transition` attribute from SVG `<g>` elements
- After all shapes on a slide are created, inject `<p:transition>` into slide XML
- Supported: fade, push, wipe, split, zoom

### Element Animations
- Parse `data-anim`, `data-anim-duration`, `data-anim-delay` from SVG `<g>` elements
- Track shape IDs during export (each `<p:sp>` gets an `id` attribute)
- After all shapes are created, build `<p:timing>` XML with animation sequences
- Animation order follows group declaration order

### OOXML Format
```xml
<p:transition spd="med"><p:fade/></p:transition>
<p:timing><p:tnLst><p:par>
  <p:cTn><p:childTnLst><p:seq>
    <p:cTn><p:childTnLst><p:par>
      <p:cTn tgtEl><p:setTgtEl><p:spTgt spid="{shape_id}"/></p:setTgtEl></p:cTn>
    </p:par></p:childTnLst></p:cTn>
  </p:seq></p:childTnLst></p:cTn>
</p:par></p:tnLst></p:timing>
```

## Scope

- In scope: transitions, entrance animations, configurable duration/delay, order control
- Out of scope: exit animations, motion paths, triggers, animation previews

---
*Context created: 2026-05-01*
