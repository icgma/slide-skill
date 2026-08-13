#!/usr/bin/env python3
"""Generate v2 showcase decks with hand-crafted per-slide SVG."""
from __future__ import annotations
import sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "slide" / "src"))
sys.path.insert(0, str(ROOT))
from slide_skill.exporter import export_project
from slide_skill.project import init_project
from slide_skill.svg_pipeline import finalize_svg

def ff(theme):
    MAP = {
        "mckinsey-consulting": "Arial, 'Helvetica Neue', 'PingFang SC', sans-serif",
        "ocean-deep": "'Helvetica Neue', Roboto, 'PingFang SC', sans-serif",
        "data-forward": "Roboto, Arial, 'PingFang SC', sans-serif",
        "academic-royal": "Cambria, Georgia, 'PingFang SC', serif",
        "coral-energy": "Poppins, Arial, 'PingFang SC', sans-serif",
        "gov-red": "'Source Han Serif SC', SimSun, Georgia, serif",
        "dark-tech": "Aptos, Arial, 'PingFang SC', sans-serif",
        "sage-calm": "Open Sans, Arial, 'PingFang SC', sans-serif",
    }
    return MAP.get(theme, "Arial, sans-serif")

def reset_project(name):
    proj = init_project(name, "ppt169", ROOT / "projects", overwrite=True)
    for dirname in ("svg_output", "svg_final"):
        for old in (proj / dirname).glob("*.svg"):
            old.unlink()
    return proj

def build(name, theme, slides):
    proj = reset_project(name)
    out = proj / "svg_output"
    out.mkdir(parents=True, exist_ok=True)
    for n, svg in slides.items():
        (out / f"slide_{n:02d}.svg").write_text(svg, encoding="utf-8")
    finalize_svg(proj)
    pptx = export_project(proj)
    print(f"  {name}: {pptx.name}")
    return pptx

def svg(body, w=1280, h=720):
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n{body}\n</svg>'

F = ff

from tests.fixtures.v2_slides import biz_mck_strategy, prod_keynote, rep_monthly, edu_stem, aca_thesis, mkt_campaign, gov_work_report, tech_conf_talk, trn_onboarding
def main():
    from build_v2_examples import PITCH_SLIDES

    t0 = time.time()
    count = 0

    builders = [
        ("biz-mck-strategy-v2", "mckinsey-consulting", biz_mck_strategy),
        ("pitch-seed-v2", "indigo-saas", lambda: PITCH_SLIDES),
        ("prod-keynote-v2", "ocean-deep", prod_keynote),
        ("rep-monthly-v2", "data-forward", rep_monthly),
        ("edu-stem-v2", "data-forward", edu_stem),
        ("aca-thesis-v2", "academic-royal", aca_thesis),
        ("mkt-campaign-v2", "coral-energy", mkt_campaign),
        ("gov-work-report-v2", "gov-red", gov_work_report),
        ("tech-conf-talk-v2", "ocean-deep", tech_conf_talk),
        ("trn-onboarding-v2", "sage-calm", trn_onboarding),
    ]
    builders_by_name = {name: (theme, fn) for name, theme, fn in builders}
    only = sys.argv[1:] or [name for name, _, _ in builders]

    unknown = [name for name in only if name not in builders_by_name]
    if unknown:
        valid = ", ".join(builders_by_name)
        print(f"Unknown v2 showcase: {', '.join(unknown)}. Valid: {valid}", file=sys.stderr)
        return 1

    for name in only:
        theme, fn = builders_by_name[name]
        print(f"\n=== {name} ===")
        build(name, theme, fn())
        count += 1

    print(f"\nBuilt {count} examples in {time.time()-t0:.1f}s")
    return 0

if __name__ == "__main__":
    sys.exit(main())
