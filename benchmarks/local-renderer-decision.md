# Local-Renderer Decision Gate — v5.1

**Decision:** DEFER (default NO-BUILD holds) — decided 2026-08-17, phase 59 (LOC-01);
**re-affirmed 2026-08-17 after the live benchmark manifest landed** (see Evidence Update).

---

## Evidence Update — 2026-08-17 (post live run)

The live manifest now exists (`six-family-manifest.json`, model
sensenova-6.7-flash-lite, serial, 5-key env pool). Re-evaluation:

- **Trigger 2 signal, honestly read:** 1/6 briefs passed the strict QA gate
  end-to-end; 5/6 exhausted repair attempts (contrast / overlap / closed-
  world fidelity). BUT the blind review recognized 5/6 composition families —
  the model COMPOSES the right structures; it is the strict-quality pass
  rate that fails, and that is chain-tuning territory (repair policy,
  contrast feedback), not proof that direct SVG cannot reach the targets.
  One model, one run: not the sustained multi-run miss trigger 2 requires.
- **Triggers 1 and 3:** unchanged — no confirmed keyless-production need;
  no outperforming slice exists.

**Decision stands: DEFER.** The most valuable v5.2 work this evidence points
at is executor repair policy (mixed-blocker auto-repair, contrast feedback
effectiveness) and classifier v2 (0/6 vs blind 5/6 divergence), not a local
renderer.

---

## What this decides

Whether v5.1 builds a keyless local layout renderer on top of the existing
`layout_renderer.py`, per REDESIGN_v5 Phase 5. The default is **do not
build**; building starts only when ALL THREE triggers are simultaneously
confirmed:

| # | Trigger (REDESIGN_v5 §Phase 5) | Status at decision time | Evidence |
|---|--------------------------------|------------------------|----------|
| 1 | Keyless production generation is a **confirmed core need**, not speculation | **Not confirmed.** The deterministic `fast` path already serves no-key generation end-to-end (v5.0 USE-01); no user requirement has asked for key-free *AI-composition-quality* generation | `.planning/REQUIREMENTS.md` v5.0 USE-01..04 shipped; v5.1 requirements contain no keyless-AI-quality requirement |
| 2 | Serial/parallel direct SVG still misses **quality or cost targets** on the Phase 2 six-family benchmark | **Unknown — live benchmark pending.** The benchmark machinery is complete and offline-green (BENCH-01..03 committed; classifier + runner tested), but the live provider manifest (`benchmarks/six-family-manifest.json`) requires a user-supplied provider key and has not yet run | `benchmarks/briefs/` (six briefs), `slide_skill.benchmark`, `tests/test_benchmark.py` (18 passed); manifest file absent = evidence not yet available |
| 3 | A 2–3 family `layout_renderer.py` **slice outperforms the AI path** on the same benchmark | **Not demonstrated.** No slice has been built (correctly — trigger 2 unproven) | No slice code exists; per REDESIGN_v5 this is a precondition, not an artifact of the decision |

**Evaluation:** zero of three triggers confirmed (trigger 2 has no live
evidence either way). An evidence-gated default cannot flip on missing
evidence — **DEFER**.

## Contract if the decision ever flips to BUILD (LOC-02)

Binding constraints carried from REDESIGN_v5 Phase 5 — these are conditions
on any future build, not work items now:

- Reuse `SlidePlan.layout` — **no new `semantic_shape.py`** (a fourth layout
  vocabulary is the failure mode this decision exists to prevent).
- Wire only the 2–3 highest-value families first: comparison,
  process-flow, metric-highlight — **never all 18 templates at once**.
- Reuse `text_wrap.py` for measured geometry.
- `local` is **not declared the production default** until the same
  six-family acceptance suite passes against it.

## How to re-open this decision

1. Obtain a provider key (env-only: `OPENAI_API_KEYS`).
2. Run `slide-skill benchmark-briefs --yes` → `benchmarks/six-family-manifest.json`
   + complete `benchmarks/blind-review-results.md` (human blind review).
3. Evaluate triggers 1–3 against the manifest: machine recognition rate,
   blind-review recognizability (≥5/6 target), non-degeneration verdicts,
   latency/cost fields.
4. If all three confirm, record the flip HERE with the manifest commit
   hash and build the slice under the contract above.

## References

- REDESIGN_v5 §Phase 5 (trigger source): `.planning/research/REDESIGN_v5.md`
- Benchmark requirements: `.planning/REQUIREMENTS.md` BENCH-01..04, LOC-01..02
- Evidence base when live: `benchmarks/six-family-manifest.json` (keyless),
  `benchmarks/blind-review-results.md` (human layer)
