#!/usr/bin/env python3
"""Build the hand-crafted pitch-seed v2 showcase deck."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "slide" / "src"))

from slide_skill.exporter import export_project
from slide_skill.project import init_project
from slide_skill.svg_pipeline import finalize_svg

# Theme palettes for each showcase
PALETTES = {
    "indigo-saas":       {"bg": "#F5F3FF", "accent": "#6366F1", "text": "#1E1B4B", "body": "#4A4485", "surface": "#E0E7FF", "muted": "#A5B4FC"},
    "ocean-deep":        {"bg": "#0A1628", "accent": "#0EA5E9", "text": "#F0F9FF", "body": "#7DD3FC", "surface": "#0F2540", "muted": "#38BDF8"},
    "data-forward":      {"bg": "#F1F5F9", "accent": "#0284C7", "text": "#0F172A", "body": "#475569", "surface": "#FFFFFF", "muted": "#94A3B8"},
    "academic-royal":    {"bg": "#FAFAF9", "accent": "#5B21B6", "text": "#1C1917", "body": "#57534E", "surface": "#F5F3FF", "muted": "#A8A29E"},
    "coral-energy":      {"bg": "#FFFBF5", "accent": "#F96167", "text": "#1A1A2E", "body": "#5A5A72", "surface": "#FFF0ED", "muted": "#FFB4B4"},
    "gov-red":           {"bg": "#FFFFFF", "accent": "#B22222", "text": "#1A1A1A", "body": "#4A4A4A", "surface": "#FFF8F6", "muted": "#E8D7D3"},
    "sage-calm":         {"bg": "#F5F9F7", "accent": "#69A297", "text": "#1B4332", "body": "#52796F", "surface": "#E8F0ED", "muted": "#A7C4BC"},
}

FF = "font-family=\"{font}\""
FONT_MAP = {
    "indigo-saas": "Poppins, Inter, 'PingFang SC', 'Microsoft YaHei', sans-serif",
    "ocean-deep": "'Helvetica Neue', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif",
    "data-forward": "Roboto, Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif",
    "academic-royal": "Cambria, Georgia, 'PingFang SC', 'Microsoft YaHei', serif",
    "coral-energy": "Poppins, Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif",
    "gov-red": "'Source Han Serif SC', 'Noto Serif SC', SimSun, Georgia, serif",
    "sage-calm": "Open Sans, Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif",
}

def f(theme):
    return FONT_MAP.get(theme, "Arial, sans-serif")

def p(theme):
    return PALETTES.get(theme, PALETTES["data-forward"])

# ─── Case 2: pitch-seed (Indigo SaaS) ───
PITCH_SLIDES = {
1: f'''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="cover-bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#F5F3FF" />
      <stop offset="100%" stop-color="#E0E7FF" />
    </linearGradient>
  </defs>
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="url(#cover-bg)" /></g>
  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="#6366F1" /></g>
  <g id="content-eyebrow"><text x="96" y="160" {FF.format(font=f("indigo-saas"))} font-size="16" font-weight="600" fill="#6366F1" letter-spacing="4">SEED ROUND · 2026</text></g>
  <g id="content-title">
    <text x="96" y="280" {FF.format(font=f("indigo-saas"))} font-size="64" font-weight="700" fill="#1E1B4B">Lumen</text>
    <text x="96" y="360" {FF.format(font=f("indigo-saas"))} font-size="36" font-weight="400" fill="#6366F1">让小团队拥有大公司的数据感知力</text>
  </g>
  <g id="content-divider"><rect x="96" y="400" width="200" height="4" fill="#6366F1" /></g>
  <g id="content-subtitle"><text x="96" y="460" {FF.format(font=f("indigo-saas"))} font-size="20" fill="#4A4485">自然语言问数据 · 自动建模 · 协作沙盒</text></g>
  <g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="#E0E7FF" /><text x="1184" y="708" {FF.format(font=f("indigo-saas"))} font-size="12" fill="#A5B4FC" text-anchor="end">01 / 07</text></g>
</svg>''',

2: f'''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#F5F3FF" /></g>
  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="#6366F1" /></g>
  <g id="content-title"><text x="96" y="100" {FF.format(font=f("indigo-saas"))} font-size="44" font-weight="700" fill="#1E1B4B">问题</text><rect x="96" y="118" width="80" height="4" fill="#6366F1" /></g>
  <g id="content-quote">
    <text x="640" y="280" {FF.format(font=f("indigo-saas"))} font-size="180" font-weight="700" fill="#6366F1" fill-opacity="0.12" text-anchor="middle">"</text>
    <text x="640" y="380" {FF.format(font=f("indigo-saas"))} font-size="32" fill="#1E1B4B" text-anchor="middle">中小公司每年在数据工具上花掉 $8,000，</text>
    <text x="640" y="428" {FF.format(font=f("indigo-saas"))} font-size="32" fill="#1E1B4B" text-anchor="middle">却没人真的看懂报表。</text>
  </g>
  <g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="#E0E7FF" /><text x="1184" y="708" {FF.format(font=f("indigo-saas"))} font-size="12" fill="#A5B4FC" text-anchor="end">02 / 07</text></g>
</svg>''',

3: f'''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#F5F3FF" /></g>
  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="#6366F1" /></g>
  <g id="content-title"><text x="96" y="100" {FF.format(font=f("indigo-saas"))} font-size="44" font-weight="700" fill="#1E1B4B">我们的洞察</text><rect x="96" y="118" width="80" height="4" fill="#6366F1" /></g>
  <g id="content-body">
    <rect x="80" y="170" width="1120" height="88" rx="8" fill="#E0E7FF" /><rect x="100" y="188" width="4" height="52" rx="2" fill="#6366F1" />
    <text x="124" y="210" {FF.format(font=f("indigo-saas"))} font-size="20" fill="#1E1B4B">数据团队只占员工 2%，却在替 98% 的人翻译数字</text>
    <rect x="80" y="270" width="1120" height="88" rx="8" fill="#FFFFFF" stroke="#E0E7FF" stroke-width="1" /><rect x="100" y="288" width="4" height="52" rx="2" fill="#6366F1" />
    <text x="124" y="310" {FF.format(font=f("indigo-saas"))} font-size="20" fill="#1E1B4B">业务一线需要的不是更多图表，而是"为什么"</text>
    <rect x="80" y="370" width="1120" height="88" rx="8" fill="#E0E7FF" /><rect x="100" y="388" width="4" height="52" rx="2" fill="#6366F1" />
    <text x="124" y="410" {FF.format(font=f("indigo-saas"))} font-size="20" fill="#1E1B4B">现有 BI 产品都在为分析师设计，而不是为决策者</text>
    <rect x="80" y="470" width="1120" height="88" rx="8" fill="#FFFFFF" stroke="#E0E7FF" stroke-width="1" /><rect x="100" y="488" width="4" height="52" rx="2" fill="#6366F1" />
    <text x="124" y="510" {FF.format(font=f("indigo-saas"))} font-size="20" fill="#1E1B4B">大模型让"自然语言问数据"第一次真的可用</text>
  </g>
  <g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="#E0E7FF" /><text x="1184" y="708" {FF.format(font=f("indigo-saas"))} font-size="12" fill="#A5B4FC" text-anchor="end">03 / 07</text></g>
</svg>''',

4: f'''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#F5F3FF" /></g>
  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="#6366F1" /></g>
  <g id="content-title"><text x="96" y="100" {FF.format(font=f("indigo-saas"))} font-size="44" font-weight="700" fill="#1E1B4B">市场规模 TAM</text><rect x="96" y="118" width="80" height="4" fill="#6366F1" /></g>
  <g id="content-metric">
    <rect x="80" y="170" width="356" height="440" rx="16" fill="#E0E7FF" /><rect x="80" y="170" width="356" height="6" rx="3" fill="#6366F1" />
    <text x="258" y="370" {FF.format(font=f("indigo-saas"))} font-size="56" font-weight="700" fill="#6366F1" text-anchor="middle">$420B</text>
    <text x="258" y="410" {FF.format(font=f("indigo-saas"))} font-size="18" font-weight="600" fill="#1E1B4B" text-anchor="middle">全球 SME SaaS</text>
    <rect x="462" y="170" width="356" height="440" rx="16" fill="#E0E7FF" /><rect x="462" y="170" width="356" height="6" rx="3" fill="#6366F1" />
    <text x="640" y="370" {FF.format(font=f("indigo-saas"))} font-size="56" font-weight="700" fill="#6366F1" text-anchor="middle">$87B</text>
    <text x="640" y="410" {FF.format(font=f("indigo-saas"))} font-size="18" font-weight="600" fill="#1E1B4B" text-anchor="middle">数据分析品类 5 年</text>
    <rect x="844" y="170" width="356" height="440" rx="16" fill="#FFFFFF" stroke="#6366F1" stroke-width="2" /><rect x="844" y="170" width="356" height="6" rx="3" fill="#6366F1" />
    <text x="1022" y="370" {FF.format(font=f("indigo-saas"))} font-size="56" font-weight="700" fill="#6366F1" text-anchor="middle">$60B</text>
    <text x="1022" y="410" {FF.format(font=f("indigo-saas"))} font-size="18" font-weight="600" fill="#1E1B4B" text-anchor="middle">SAM 中国 + 东南亚</text>
  </g>
  <g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="#E0E7FF" /><text x="1184" y="708" {FF.format(font=f("indigo-saas"))} font-size="12" fill="#A5B4FC" text-anchor="end">04 / 07</text></g>
</svg>''',

5: f'''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#F5F3FF" /></g>
  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="#6366F1" /></g>
  <g id="content-title"><text x="96" y="100" {FF.format(font=f("indigo-saas"))} font-size="44" font-weight="700" fill="#1E1B4B">Traction 数据</text><rect x="96" y="118" width="80" height="4" fill="#6366F1" /></g>
  <g id="content-metric">
    <rect x="80" y="170" width="270" height="470" rx="16" fill="#E0E7FF" /><rect x="80" y="170" width="270" height="6" rx="3" fill="#6366F1" />
    <text x="215" y="360" {FF.format(font=f("indigo-saas"))} font-size="72" font-weight="700" fill="#6366F1" text-anchor="middle">142</text>
    <text x="215" y="400" {FF.format(font=f("indigo-saas"))} font-size="18" font-weight="600" fill="#1E1B4B" text-anchor="middle">付费客户</text>
    <text x="215" y="430" {FF.format(font=f("indigo-saas"))} font-size="16" fill="#4A4485" text-anchor="middle">上线 4 个月</text>
    <rect x="370" y="170" width="270" height="470" rx="16" fill="#E0E7FF" /><rect x="370" y="170" width="270" height="6" rx="3" fill="#6366F1" />
    <text x="505" y="360" {FF.format(font=f("indigo-saas"))} font-size="72" font-weight="700" fill="#6366F1" text-anchor="middle">$3.5M</text>
    <text x="505" y="400" {FF.format(font=f("indigo-saas"))} font-size="18" font-weight="600" fill="#1E1B4B" text-anchor="middle">年化 ARR</text>
    <text x="505" y="430" {FF.format(font=f("indigo-saas"))} font-size="16" fill="#4A4485" text-anchor="middle">MRR 环比 +37%</text>
    <rect x="660" y="170" width="270" height="470" rx="16" fill="#E0E7FF" /><rect x="660" y="170" width="270" height="6" rx="3" fill="#6366F1" />
    <text x="795" y="360" {FF.format(font=f("indigo-saas"))} font-size="72" font-weight="700" fill="#6366F1" text-anchor="middle">134%</text>
    <text x="795" y="400" {FF.format(font=f("indigo-saas"))} font-size="18" font-weight="600" fill="#1E1B4B" text-anchor="middle">NDR 净留存</text>
    <text x="795" y="430" {FF.format(font=f("indigo-saas"))} font-size="16" fill="#4A4485" text-anchor="middle">NPS 62</text>
    <rect x="950" y="170" width="270" height="470" rx="16" fill="#FFFFFF" stroke="#6366F1" stroke-width="2" /><rect x="950" y="170" width="270" height="6" rx="3" fill="#6366F1" />
    <text x="1085" y="360" {FF.format(font=f("indigo-saas"))} font-size="48" font-weight="700" fill="#6366F1" text-anchor="middle">3× F500</text>
    <text x="1085" y="400" {FF.format(font=f("indigo-saas"))} font-size="18" font-weight="600" fill="#1E1B4B" text-anchor="middle">已签约</text>
    <text x="1085" y="430" {FF.format(font=f("indigo-saas"))} font-size="16" fill="#4A4485" text-anchor="middle">中国分公司</text>
  </g>
  <g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="#E0E7FF" /><text x="1184" y="708" {FF.format(font=f("indigo-saas"))} font-size="12" fill="#A5B4FC" text-anchor="end">05 / 07</text></g>
</svg>''',

6: f'''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#F5F3FF" /></g>
  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="#6366F1" /></g>
  <g id="content-title"><text x="96" y="100" {FF.format(font=f("indigo-saas"))} font-size="44" font-weight="700" fill="#1E1B4B">融资 Ask</text><rect x="96" y="118" width="80" height="4" fill="#6366F1" /></g>
  <g id="content-body">
    <rect x="80" y="170" width="540" height="200" rx="12" fill="#E0E7FF" />
    <text x="120" y="220" {FF.format(font=f("indigo-saas"))} font-size="56" font-weight="700" fill="#6366F1">$8M</text>
    <text x="120" y="260" {FF.format(font=f("indigo-saas"))} font-size="20" fill="#1E1B4B">本轮融资规模</text>
    <rect x="660" y="170" width="540" height="200" rx="12" fill="#E0E7FF" />
    <text x="700" y="220" {FF.format(font=f("indigo-saas"))} font-size="20" fill="#1E1B4B">用途分配</text>
    <text x="700" y="260" {FF.format(font=f("indigo-saas"))} font-size="18" fill="#4A4485">产品 50% · 海外 30% · 销售 20%</text>
    <rect x="80" y="400" width="1120" height="200" rx="12" fill="#FFFFFF" stroke="#6366F1" stroke-width="2" />
    <text x="120" y="450" {FF.format(font=f("indigo-saas"))} font-size="24" font-weight="700" fill="#1E1B4B">18 个月里程碑</text>
    <text x="120" y="490" {FF.format(font=f("indigo-saas"))} font-size="20" fill="#4A4485">ARR 跑通 $20M · 期待战略投资人出海与生态赋能</text>
    <text x="120" y="530" {FF.format(font=f("indigo-saas"))} font-size="20" fill="#6366F1">founders@lumen.ai</text>
  </g>
  <g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="#E0E7FF" /><text x="1184" y="708" {FF.format(font=f("indigo-saas"))} font-size="12" fill="#A5B4FC" text-anchor="end">06 / 07</text></g>
</svg>''',

7: f'''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <defs><radialGradient id="close-grad" cx="50%" cy="50%" r="70%"><stop offset="0%" stop-color="#E0E7FF" /><stop offset="100%" stop-color="#F5F3FF" /></radialGradient></defs>
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="url(#close-grad)" /></g>
  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="#6366F1" /></g>
  <g id="content-title">
    <text x="640" y="280" {FF.format(font=f("indigo-saas"))} font-size="22" font-weight="600" fill="#6366F1" text-anchor="middle" letter-spacing="6">LET'S BUILD</text>
    <text x="640" y="400" {FF.format(font=f("indigo-saas"))} font-size="96" font-weight="700" fill="#1E1B4B" text-anchor="middle">Thank You</text>
    <rect x="490" y="426" width="300" height="4" fill="#6366F1" />
    <text x="640" y="500" {FF.format(font=f("indigo-saas"))} font-size="22" fill="#4A4485" text-anchor="middle">founders@lumen.ai</text>
  </g>
  <g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="#E0E7FF" /><text x="1184" y="708" {FF.format(font=f("indigo-saas"))} font-size="12" fill="#A5B4FC" text-anchor="end">07 / 07</text></g>
</svg>''',
}

def reset_project(name: str) -> Path:
    project = init_project(name, "ppt169", ROOT / "projects", overwrite=True)
    for dirname in ("svg_output", "svg_final"):
        for old in (project / dirname).glob("*.svg"):
            old.unlink()
    return project

def write_slides(project_dir: Path, slides: dict[int, str]):
    svg_out = project_dir / "svg_output"
    svg_out.mkdir(parents=True, exist_ok=True)
    for num, content in slides.items():
        (svg_out / f"slide_{num:02d}.svg").write_text(content, encoding="utf-8")

def build_project(name: str, slides: dict[int, str]) -> Path:
    project = reset_project(name)
    write_slides(project, slides)
    finalize_svg(project)
    pptx = export_project(project)
    print(f"  pptx: {pptx.relative_to(ROOT)}")
    return pptx

def main():
    t0 = __import__("time").time()
    builders = {
        "pitch-seed-v2": PITCH_SLIDES,
    }
    only = sys.argv[1:] or list(builders)
    for name in only:
        if name not in builders:
            print(f"Unknown v2 showcase: {name}. Valid: {', '.join(builders)}", file=sys.stderr)
            return 1
        print(f"\n=== {name} ===")
        build_project(name, builders[name])
    print(f"\nDone in {__import__('time').time()-t0:.1f}s")
    return 0

if __name__ == "__main__":
    sys.exit(main())
