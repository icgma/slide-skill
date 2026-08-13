---
name: slide
description: "Redirect shim. The canonical, up-to-date slide-skill guide lives at the repository root as SKILL.md. This file is kept only so pre-existing deep links and package manifests resolve. Do not maintain a second copy here — edit the root SKILL.md instead."
---

# Slide Skill — moved

This subdirectory previously held a **stale v2.0 copy** of the skill guide
(5 themes, the Strategist/Executor workflow, a different command set) that
diverged from and contradicted the canonical guide.

**The single source of truth is now the repository-root `SKILL.md`** —
32 themes, the interactive needs-assessment workflow, and the full
command surface (its title line carries the current version, which is
test-enforced against `pyproject.toml`). Load that file instead:

```
<repo-root>/SKILL.md
```

If you are an agent that auto-discovers skills by walking directories,
treat `../../SKILL.md` (relative to this file) as the skill entry point
and ignore the rest of `skills/slide/`.

> The old `guides/*.md` files under this directory were removed to
> eliminate the version contradiction. Their content (intake, SVG
> pipeline, export, editing, QA) is covered by the root `SKILL.md` and
> the bundled `tools/slide/src/slide_skill/references/*.md` runtime
> prompt templates.
