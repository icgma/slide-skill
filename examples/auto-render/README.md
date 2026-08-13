# Auto-rendered samples

  These SVGs were produced by the v2.1 `quickstart` command with no LLM in the loop:

  ```bash
  slide-skill quickstart examples/sample.md --theme dark-tech
  slide-skill quickstart examples/sample.md --theme light-corporate
  ```

  The same source ([`examples/sample.md`](../sample.md)) — the
  "AI-Powered Analytics Platform" deck, 8 slides at the time these renders were
  committed (the sample has since grown to 14 sections) — rendered through two
  different themes using the pure-Python template engine in
  `tools/slide/src/slide_skill/svg_pipeline.py`.

  Compare against:

  - [`../svg/`](../svg/) — hand-crafted reference targets (the "design ceiling")
  - [`../sample-dark-tech/svg_output/`](../sample-dark-tech/svg_output/) — pre-v2.1
    auto-render output (kept for diff comparison; gradients render as midpoints there)

  The v2.1 auto-renderer adds: hero typography on cover slides, decorative
  gradient orbs, numbered bullet markers, accent edge bars, gradient cards on
  metrics, A/B labels on two-column layouts, and a centered thank-you closing slide.
