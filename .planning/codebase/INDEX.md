---
last_mapped_commit: fa4b24c317ed091b8d6132314e40e1bbf3e46eba
mapped_at: 2026-05-03
generated_by: gsd map-codebase (v1.39.1) + 4 parallel mapper agents
---

# Codebase Map — slide-skill

This folder is produced by the GSD `map-codebase` workflow (https://github.com/gsd-build/get-shit-done). It is reference material consumed by other GSD commands (`/gsd-plan-phase`, `/gsd-execute-phase`) and by humans onboarding to the codebase.

## Documents

| Doc | Mapper | Read when… |
|---|---|---|
| [STACK.md](STACK.md) | tech | adding deps, debugging system reqs, planning a setup task |
| [INTEGRATIONS.md](INTEGRATIONS.md) | tech | touching intake, export, TTS, or any subprocess boundary |
| [ARCHITECTURE.md](ARCHITECTURE.md) | arch | changing the pipeline, themes, or the Strategist/Executor contract |
| [STRUCTURE.md](STRUCTURE.md) | arch | deciding where new files go; orienting in the repo |
| [CONVENTIONS.md](CONVENTIONS.md) | quality | writing new modules, CLI subcommands, or theme presets |
| [TESTING.md](TESTING.md) | quality | adding tests; understanding coverage gaps |
| [CONCERNS.md](CONCERNS.md) | concerns | refactor / hardening / security / API-stability work |

## How this was generated
GSD's `commands/gsd/map-codebase.md` spawns 4 `gsd-codebase-mapper` agents (tech / arch / quality / concerns) in parallel, each writing its own document(s). In this run, GSD's CLI installed the workflow files into `.claude/`, and the equivalent four-agent fan-out was executed by Replit Agent's `explore` subagents.

## Refresh
After significant code changes, regenerate by running (from a Claude Code session in this repo):
```
/gsd-map-codebase --paths tools/slide/src
```
or do a full re-map:
```
/gsd-map-codebase
```
