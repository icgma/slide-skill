# Slide Skill Usage

## End-to-End

```powershell
python -m pip install -e .
slide-skill quickstart examples/demo.md --name demo-deck
```

Open the generated deck in `projects/demo-deck/exports/`.

Quickstart writes automated QA with `status: automated-passed` when structural checks pass but visual review or fix-cycle evidence has not been provided. Use `slide-skill qa <project> --strict` for completion gating.

Production AI mode uses two LLM stages by default: AI Strategist planning (`--planner auto`) and AI Executor SVG generation. The AI Strategist rejects weak plans that lack concrete `visual_strategy` or `layout_pattern`, retries invalid plans with validation feedback, and writes `qa/ai-planner/attempt_*.json`. `visual_strategy` must name a specific visual device, hierarchy, or geometry such as an accent rail, proof card, metric block, comparison grid, or image panel; `layout_pattern` must describe actual placement or structure such as title-left/proof-card-right, two-column grid, or top metric row with lower bullets. It also rejects planner output-protocol violations instead of silently cleaning them up: markdown fences or prose around the JSON are fed back to the model. Malformed planner control fields are rejected instead of silently normalized: slide indexes must be sequential, density must be `sparse|normal|dense`, and rhythm must be `anchor|breathing|dense`. Over-limit output is rejected instead of silently truncated: the model must stay within `max_slides` and consolidate items to `max_items_per_slide`. Malformed item entries are rejected too; every item must be an object with `primary` text. It extracts source coverage anchors from important headings, bullets, and metric lines; missing anchors fail planning and are fed back to the model before SVG generation. Coverage anchors must appear in slide titles or items, not only in notes or hidden design fields. Numeric values in planned titles/items/notes are grounded against the source too, so invented metrics such as percentages or counts fail planning instead of reaching the SVG executor. A new AI planner run clears stale `plan.json`, `executor-brief.md`, and `raw-response.txt` before calling the model; successful validation publishes fresh versions, while final failure writes `qa/ai-planner/failure.json` instead. The validated design contract is written to `qa/ai-planner/executor-brief.md`, and AI Executor injects the matching slide section plus a Planner Design Execution Contract into the SVG prompt as hard layout requirements, not inspiration. Common layout words are translated into suggested coordinate regions, for example left/right panes, top/lower bands, grids, proof cards, and hero/image regions, so the model gets pixel-level placement guidance rather than only prose. Each executor attempt also runs lightweight layout-intent QA: if the planner asked for left/right, top/lower, or grid/comparison structure, visible SVG elements must occupy those regions or the issue is fed back for rewrite. Executor attempt logs and `ai-trace` metadata record `has_executor_brief` so prompt handoff failures are visible. Use `--planner deterministic` when you need rule-based planning for comparison or debugging.

Use `--model` as the global model default. Override individual LLM roles with `--planner-model`, `--executor-model`, and `--vision-model` when planning, SVG generation, and visual criticism need different models.

Tune role-specific feedback loops with `--planner-retries`, `--executor-qa-retries`, and `--vision-retries`. These are intentionally separate because the planner validates JSON/design contracts, the executor rewrites SVG after structural/content QA, and the visual critic retries weak feedback before it can be persisted. If the critic still fails its quality gate after all retries, the command fails instead of writing repair artifacts; stale AI-generated visual feedback from the previous critic run is cleared first so later repairs cannot consume old AI observations.

Development tests include a local OpenAI-compatible fake server that exercises the planner, executor, visual critic, and critic-to-repair-feedback HTTP payloads without calling an external provider.

Before running a full generation against a real provider, preflight the configured endpoint and role models:

```powershell
$env:OPENAI_API_KEY='<your key>'
$env:OPENAI_MODEL='gpt-4o'
slide-skill ai-doctor
slide-skill ai-doctor --check-vision
```

`ai-doctor` sends minimal requests for planner and executor access. `--check-vision` also sends a tiny image-input request to the vision model, so text-only models or accounts without image permissions fail before `visual-critic` or `iterate-ai` runs.

For release gating of the skill's LLM path, use the stricter one-command check. It runs planner, executor, and vision provider preflight, then executes a real planner → executor → render → visual-critic smoke with `--require-visual-ok`. If the visual smoke is repairable, it automatically runs up to two visual review/repair rounds (`--repair-rounds`) before writing `qa/AI-RELEASE-CHECK.json`; the release gates distinguish a review-only convergence from an applied SVG repair:

```powershell
slide-skill ai-release-check --name release-llm-gate
```

For production rollout, require visual evidence rendered from the exported PPTX itself:

```powershell
slide-skill ai-release-check --name release-llm-gate --require-pptx-render
```

This strict mode needs LibreOffice and Poppler. It preflights the render stack before provider doctor, planner, executor, or vision calls, fails instead of accepting Chrome/Edge SVG-preview fallback or `--rendered-dir` images, and `qa/AI-RELEASE-CHECK.json` records the result as `gates.rendered_source_pptx`.

Use `qa/AI-RELEASE-CHECK.json.summary` as the stable CI/human review entry point. It records the release decision, blocking reasons, non-blocking warnings, final rendered evidence source, final visual severity, whether visual iteration was needed, and concrete next actions. This is intentionally duplicated from lower-level doctor/smoke/iteration evidence so release automation does not need to infer why a run is or is not shippable from raw trace details.

The release-check top-level `status` is tied to `gates.release_ready`: if any required gate fails, the command writes `status: failed` and exits non-zero even when the underlying smoke or visual iteration produced usable intermediate artifacts.

Compare release gate runs with:

```powershell
slide-skill ai-release-summary test-output/live-llm
slide-skill ai-release-summary test-output/live-llm/run-a test-output/live-llm/run-b
slide-skill ai-release-summary test-output/live-llm/run-a --json
```

The release summary table reports release readiness, final visual severity, first-smoke visual severity, render source, whether evidence came from PPTX render, whether visual iteration/repair was needed, failed trace event count, executor blocking count, warning count, and compact blocking reasons. `--json` includes the same compact release signal as `summary_hint` with `ready`, `ready-warning:...`, `blocked:provider=planner,vision`, `blocked:repair-targets=N`, or `blocked:...`, so CI can route release failures without parsing nested `summary.blocking_reasons`. Its exit code is non-zero unless every summarized run has `gates.release_ready: true`.

To verify generation against a real LLM provider, run the persistent live smoke command. It calls the AI Strategist and AI Executor on a one-slide source, then writes a durable project with `qa/AI-SMOKE.json`, `qa/ai-trace.jsonl`, prompt/raw sidecars, `executor-brief.md`, generated SVG, PPTX export, QA report, and a readable trace summary:

```powershell
slide-skill ai-smoke --name real-llm-smoke
```

Reusing the same `--name` resets generated smoke evidence (`qa/`, `svg_output/`, `svg_final/`, and `exports/`) before the run, so `AI-SMOKE.json` and `ai-trace.jsonl` stay scoped to the current provider/model attempt.

To include the visual critic in the same persistent smoke run, add `--visual-critic`. By default this renders the exported PPTX through the normal render stack before calling the vision model:

```powershell
slide-skill ai-smoke --name real-llm-smoke-vision --visual-critic --vision-model gpt-4o
```

If LibreOffice/Poppler are unavailable, visual smoke falls back to headless Chrome SVG preview screenshots when a local Chrome/Edge browser is available. If you already rendered images another way, pass `--rendered-dir <dir>`; images are copied into the project `qa/rendered/` evidence directory before the vision request:

```powershell
slide-skill ai-smoke --name real-llm-smoke-vision --visual-critic --rendered-dir path/to/rendered-images
```

For high-quality provider comparisons where `minor` feedback should still fail, add `--require-visual-ok` with `--visual-critic`. For final PPTX-render acceptance, add `--require-pptx-render`; this fails before the vision call unless the evidence came from the exported PPTX render stack.

`qa/AI-SMOKE.json` is written for both passed and failed smoke runs. On failure it records the error, any trace events emitted before the failure, and empty `deck` / `qa_report` fields only when export or QA did not complete. The `diagnosis` object records copy-pasteable `ai-trace` / `ai-trace --diagnose` commands and, when relevant, the focused event number plus `inspect_raw` command for the latest failure, recovered retry failure, active visual repair gate, or visual-ok gate. Provider-access failures also include `provider_role`, `provider_model`, and role-specific `next` guidance for planner, executor, or vision configuration. For visual gates it also includes bounded `repair_targets`, `repair_target_count`, optional `repair_targets_more`, and `repair_command`, so the next repair pass can start from exact slide-level prompts instead of manually parsing `visual-feedback.json`; each target keeps `repair_source` as `repair_prompt`, `actions`, or `action` to show which visual-feedback field made it actionable. For visual smoke, `rendered_source` records whether images came from `pptx-render`, `svg-preview`, or `external-rendered-dir`. Visual smoke uses strict visual QA: AI visual feedback with `major` or `critical` severity fails the smoke even when planner/executor/provider interactions succeeded, so repair-worthy output is not reported as generation-quality passed. With `--require-visual-ok`, any final visual severity other than `ok` fails the smoke while keeping generated deck, QA, trace, and visual feedback evidence.

For release runs, start from `qa/AI-RELEASE-CHECK.json.summary`. Provider-preflight failures include `provider_failures` with the failed role, model, base URL, error, and role-specific `next_action`; the same role-specific advice is repeated in `next_actions` before the generic doctor fallback. Visual-gate failures include the same repair target fields as smoke or iteration results when repair evidence is available.

To compare multiple smoke runs after prompt/model changes:

```powershell
slide-skill ai-smoke-summary test-output/live-llm
slide-skill ai-smoke-summary test-output/live-llm/run-a test-output/live-llm/run-b
slide-skill ai-smoke-summary test-output/live-llm/run-a --json
```

The summary includes aggregate interaction and quality metrics from the trace: failed event count, executor blocking count, maximum visual severity, render source, total prompt/raw response/request character counts, and a compact `hint` from the smoke diagnosis. Use these columns to catch prompt bloat, unexpectedly short model output, visual regressions, a failing stage, or a recovered retry pattern before inspecting individual sidecars. `--json` includes the same value as `summary_hint`, including `failed:provider=planner`, `repair:targets=N`, and `visual-ok:targets=N` when the smoke result has actionable provider or repair targets, so automation can consume the table's compact diagnosis without reimplementing CLI formatting. For machine comparison, `qa/AI-SMOKE.json.metrics` also records `failure_hint_counts`, `recovered_failure_count`, and `feedback_recovered_failure_count`, so A/B runs can distinguish content-fidelity failures from style-token, protocol, grounding, layout, critic, provider-access, or unclassified failures. When a failed attempt is recovered by retry, `qa/AI-SMOKE.json.diagnosis` records `recovered_by_event`, whether the recovery used feedback, and issue-specific `next_detail` advice such as planner-protocol, output-protocol, content-fidelity, layout-handoff, style-token, critic-protocol, planner-coverage, numeric-grounding, or token-density. When `qa/ai-trace.jsonl` is still present, `ai-smoke-summary` refreshes stale smoke diagnosis and metrics from the trace before printing table or JSON output, so older real-provider runs benefit from newer failure classification without rerunning the model. A `passed` row with `sev=minor` still deserves review; `sev=major` or `sev=critical` should fail strict visual QA and should be repaired before treating the deck as complete.

Set `OPENAI_BASE_URL`, `OPENAI_PLANNER_MODEL`, `OPENAI_EXECUTOR_MODEL`, or `OPENAI_VISION_MODEL` when using an OpenAI-compatible provider or role-specific models.

For test-suite verification of the same planner/executor/trace path, opt in to the live pytest smoke:

```powershell
$env:SLIDE_SKILL_RUN_LIVE_LLM='1'
python -m pytest tests/test_live_llm_smoke.py -q
```

For debugging model behavior, run `slide-skill ai-trace <project>`. It summarizes `qa/ai-trace.jsonl`, which records each planner, executor, and visual-critic interaction with model, status, attempt number, prompt/output lengths, short excerpts, and stage-specific metadata. Executor rows show whether planner brief / rendered visual feedback was injected and include a short `blocking_issues` preview for failed attempts, so it is clear whether the model ignored a design contract, missed content, or violated SVG protocol. Planner/executor provider failures such as auth, model, network, or rate-limit errors are also recorded as failed trace events with request sidecars, so live-provider setup problems remain diagnosable. The summary and diagnosis include `failure-hints` counts, and `--json` adds a derived `failure_hint_alias` to failed events, using stable classes such as `content-fidelity`, `layout-handoff`, `style-token`, `output-protocol`, `critic-protocol`, `planner-coverage`, `numeric-grounding`, `token-density`, `planner-protocol`, `provider-access`, or `unclassified`. Use `slide-skill ai-trace <project> --diagnose` for a shorter triage view with stage/status counts, latest failed event, blocking issue previews, planner/executor pass gaps, missing sidecars, brief handoff warnings, issue-specific `next-detail` tuning advice, role/model-specific provider-access next steps, and visual gate `repair-target` / `repair-command` lines when current feedback is repairable. Those details distinguish content-fidelity failures, planner/executor layout handoff failures, JSON/SVG output-protocol failures, visual-critic repair-prompt failures, provider-access failures, source coverage gaps, numeric grounding issues, and token/density pressure, so the next action is not just "inspect the prompt". After repeated `iterate-ai` runs, add `--latest-iteration` to scope summary, JSON, diagnosis, or bundles to the current `qa/AI-ITERATION.json.trace_start` window; latest-iteration diagnosis also prints the iteration status, strict/ok gate settings, latest visual severity, issue count, non-ok slide count, repair prompt count, and repair targets from the current `qa/AI-ITERATION.json`. Event numbers remain global so `--event N --part prompt|raw|request` still opens the matching sidecar. When `quickstart`, `build`, `visual-critic`, `repair-slide`, `repair-feedback`, `iterate-ai`, or `ai-smoke` fails due to an AI quality gate or missing repair artifact, the CLI prints the trace command, the matching `--diagnose` command, and the latest failed stage/attempt/model so the failing model interaction is immediately inspectable. If `iterate-ai` fails after writing `qa/AI-ITERATION.json` and its `total_trace_events` matches the current trace length, it also prints `diagnose-latest: slide-skill ai-trace <project> --latest-iteration --diagnose` and scopes the `last-ai-*` summary to that current iteration rather than historical retries. Stale iteration results, and non-iteration failures that happen after an old iteration result, are ignored for scoped failure summaries. Full prompt/raw response/request sidecars are written under `qa/ai-trace-artifacts/` so failed or low-quality generations can be reproduced exactly. Use `slide-skill ai-trace <project> --event 3 --part prompt`, `--part raw`, or `--part request` to print a specific full sidecar. Use `slide-skill ai-trace <project> --bundle qa/trace-bundle.zip` to archive `ai-trace.jsonl`, selected events JSON, prompt/raw/request sidecars, and AI QA reports for release review or provider escalation. Visual request sidecars omit inline image base64 and keep a source placeholder instead.

Local OpenAI-compatible servers do not need a real API key through the CLI. Passing `--ai-base-url http://127.0.0.1:11434/v1` is enough; the CLI supplies a harmless dummy key for SDK compatibility.

For visual repair loops, prefer the one-command AI iteration. It exports the current deck, renders slides, asks the visual critic to inspect the images, repairs flagged pages, re-exports, runs a final visual review after the last repair, writes `qa/FIX-VERIFY.md` and `qa/AI-ITERATION.json`, and then writes QA against the latest feedback:

```powershell
slide-skill iterate-ai projects/demo-deck
```

Compare repair runs with:

```powershell
slide-skill ai-iteration-summary projects/demo-deck
slide-skill ai-iteration-summary test-output/live-llm --json
```

The iteration summary shows strict QA status, repair cycles, repaired slide count, latest visual severity, latest visual issue/non-ok/repair-prompt counts, render source, executor/vision models, current-run trace counts, total project trace counts, trace failures/blocking counts, visual-feedback injection count, and prompt/raw/request character totals. `--json` includes the same compact iteration signal as `summary_hint` with values such as `passed`, `repaired:2`, `passed-warning:minor,...`, `failed:targets=1`, or `failed:targets=2,major`, so automation can route remaining visual repair work without parsing nested feedback stats. `qa/AI-ITERATION.json` also stores compact latest-feedback summaries plus `actionable_repair_count`, which counts non-ok slides with `repair_prompt` or concrete `actions`; when latest severity is non-ok, it includes bounded `repair_targets`, `repair_target_count`, optional `repair_targets_more`, `repair_command`, and per-target `repair_source` so a run can explain why it passed or what exact slides remain without copying the full visual review. Metrics are scoped to the latest `iterate-ai` run; the total trace count is included only to show project history size.

Use `--require-visual-ok` when a final `minor` visual critique should still fail the run. This is stricter than `--strict-qa`: it requires final AI visual feedback severity to be exactly `ok`, writes a failed `qa/AI-ITERATION.json` if the latest feedback is `minor` / `major` / `critical`, and keeps the issue counts plus repair prompt and actionable repair counts visible in both the summary and `qa/FIX-VERIFY.md`.

The critic writes `qa/VISUAL-REVIEW.md` and `qa/visual-feedback.json`; each non-ok slide should include a `repair_prompt` written for the SVG executor, or a concrete `actions` entry that can serve as fallback repair text. Weak critic responses are retried with feedback before they are persisted, including contradictory `severity: ok` responses that still contain issues/actions/repair prompts and generic repair instructions such as "fix the slide". Before a new AI critic run, stale feedback generated by the previous AI critic run is cleared; manually authored review files are preserved. If every attempt remains weak, `visual-critic` raises an error and leaves AI feedback files absent so the executor cannot consume stale or non-actionable repair input. Valid repair text must be specific enough to paste into the SVG executor and should reference the visible issue or action it is meant to fix; this relevance check handles CJK/Chinese phrases as well as English words. When `qa/ai-planner/executor-brief.md` exists, visual criticism also injects the matching slide section so the vision model can compare the rendered image against expected title/body content, not just generic layout quality. The AI executor turns those per-slide comments into a Rendered Visual Repair Contract in the next SVG prompt: `repair_prompt` is prioritized when present, then issues/actions are used, while the Content Fidelity Contract remains mandatory so the model cannot "fix" layout by deleting, hiding, paraphrasing away, or moving required text off-canvas. Text that the visual feedback says to preserve, keep, retain, maintain, or 保留 is treated as required visible content too, including text mentioned only inside `repair_prompt`; matching feedback lines are also repeated as a compact preserve checklist in the repair contract and checked by content-fidelity QA before a repaired SVG can publish. If rendered feedback requests an accent stripe or rail, attempt QA also requires a visible narrow `<rect>` before publishing; if feedback requests a panel/card/surface/background, attempt QA requires a content-sized visible `<rect>` rather than accepting only the full-slide background; if feedback requests bullet marker color/dots/glyphs, attempt QA requires a visible marker or bullet glyph. On every retry, executor re-reads `spec_lock.json` / `spec_lock.md` and rebuilds both system and page prompts from the current palette/font lock. Executor prompts include a Content Fidelity Contract listing required visible strings, and attempts also run a content-fidelity gate: the planned title plus item `primary`, `secondary`, and `tertiary` text must appear in actually visible `<text>` / `<tspan>` SVG text. Hidden text such as `display="none"`, `visibility="hidden"`, `opacity="0"`, or `fill-opacity="0"` does not satisfy the gate; missing visible content is fed back to the model for rewrite. Executor attempts are saved under `qa/executor/attempt-svg/`; each attempt still runs structure, output-protocol, spec-drift, font-safety, and content-fidelity checks. Markdown fences, prose before/after SVG, or multiple SVG documents are fed back to the model instead of being silently accepted. Only a passing attempt is published to `svg_output/slide_XX.svg`, so a failed repair cannot overwrite the last good page.

If you need manual control, run the same loop step by step.

To revise only one page after visual review:

```powershell
slide-skill render projects/demo-deck/exports/demo-deck.pptx -o projects/demo-deck/qa/rendered
slide-skill visual-critic projects/demo-deck
slide-skill repair-slide projects/demo-deck 3
```

The command preserves the rest of `svg_output/`, rewrites `slide_03.svg` with AI, and updates `svg_final/slide_03.svg` when that final file exists.

To repair every slide flagged by `qa/visual-feedback.json`:

```powershell
slide-skill repair-feedback projects/demo-deck
```

`repair-feedback` skips `ok` slides by default and keeps footer page counts based on the full deck, not just the repaired subset.

## Development Checks

```powershell
python -m unittest discover -s tests -v
slide-skill quickstart examples/demo.md --name smoke-demo --mode template-smoke
slide-skill render-doctor
```

## Speaker Notes

Add notes before export:

```markdown
## Slide 1
Opening speaker cue.

## Slide 2
Detail speaker cue.
```

Store that as `projects/<deck>/notes/total.md`, or create per-slide files like `notes/slide_01.md`. Export embeds notes into the PPTX and also writes a Markdown sidecar. Use `slide-skill pptx-notes <deck.pptx>` to inspect embedded notes.

## Known v1 Limits

- Complex SVG paths are not converted to editable custom geometries yet.
- The SVG gate rejects unsupported SVG constructs, opacity attributes, and transforms instead of allowing silent export loss or fidelity drift.
- PDF intake requires optional `PyMuPDF`.
- Visual rendering through LibreOffice/Poppler is documented but not bundled. AI visual smoke can fall back to Chrome/Edge SVG screenshots for generated-slide visual review when PPTX rendering is unavailable.
- Use `slide-skill render <deck.pptx> -o <out-dir>` after installing LibreOffice and Poppler for final PPTX-render evidence.
- Use `slide-skill ai-release-check --require-pptx-render` for production acceptance so the release gate proves PPTX-rendered evidence, not SVG-preview fallback.
- Strict QA requires rendered images, `qa/VISUAL-REVIEW.md`, and `qa/FIX-VERIFY.md`.
- Speaker notes are embedded for common PowerPoint notes workflows and also preserved as sidecar Markdown.
