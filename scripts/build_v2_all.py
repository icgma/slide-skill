#!/usr/bin/env python3
"""Generate v2 showcase decks with hand-crafted per-slide SVG."""
from __future__ import annotations
import sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "slide" / "src"))
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

# ═══════════════════════════════════════════
# Case 1: biz-mck-strategy (McKinsey Consulting)
# ═══════════════════════════════════════════
def biz_mck_strategy():
    t = F("mckinsey-consulting")
    P = {"bg":"#FFFFFF","sf":"#ECF0F1","ac":"#005587","tx":"#2C3E50","bd":"#5D6D7E","mt":"#BDC3C7"}
    return {
    1: svg(f'''<defs><linearGradient id="bmcg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#FFFFFF"/><stop offset="100%" stop-color="#F0F4F8"/></linearGradient></defs>
<g id="background"><rect x="0" y="0" width="1280" height="720" fill="url(#bmcg)"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-eyebrow"><text x="96" y="160" font-family="{t}" font-size="16" font-weight="600" fill="{P['ac']}" letter-spacing="4">STRATEGY REVIEW · 2026</text></g>
<g id="content-title"><text x="96" y="280" font-family="{t}" font-size="64" font-weight="700" fill="{P['tx']}">2026 战略复盘</text><text x="96" y="360" font-family="{t}" font-size="40" fill="{P['ac']}">增长引擎再校准</text></g>
<g id="content-divider"><rect x="96" y="400" width="200" height="4" fill="{P['ac']}"/></g>
<g id="content-subtitle"><text x="96" y="460" font-family="{t}" font-size="20" fill="{P['bd']}">三大主线并行 · 海外市场突破 · AI 第二曲线</text></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">01 / 07</text></g>'''),
    2: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">核心结论</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="1120" height="64" rx="8" fill="{P['sf']}"/><text x="120" y="182" font-family="{t}" font-size="20" font-weight="700" fill="{P['ac']}">28%</text><text x="168" y="182" font-family="{t}" font-size="20" fill="{P['bd']}">营收增速回到 28% 区间</text>
<rect x="80" y="234" width="1120" height="64" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><text x="120" y="256" font-family="{t}" font-size="20" font-weight="700" fill="{P['ac']}">41%</text><text x="168" y="256" font-family="{t}" font-size="20" fill="{P['bd']}">客单价提升带动毛利率突破 41%</text>
<rect x="80" y="308" width="1120" height="64" rx="8" fill="{P['sf']}"/><text x="120" y="330" font-family="{t}" font-size="20" font-weight="700" fill="{P['ac']}">30%</text><text x="168" y="330" font-family="{t}" font-size="20" fill="{P['bd']}">海外市场占比首次突破 30%</text>
<rect x="80" y="382" width="1120" height="64" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><text x="120" y="404" font-family="{t}" font-size="20" fill="{P['bd']}">新业务接入周期缩短 60%</text>
<rect x="80" y="456" width="1120" height="64" rx="8" fill="{P['sf']}"/><text x="120" y="478" font-family="{t}" font-size="20" fill="{P['bd']}">组织从职能型切换为业务线</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">02 / 07</text></g>'''),
    3: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="86" font-family="{t}" font-size="38" font-weight="700" fill="{P['tx']}">三大主线 vs 现状</text><rect x="96" y="100" width="60" height="3" fill="{P['ac']}"/></g>
<g id="content-left"><rect x="80" y="130" width="555" height="530" rx="12" fill="{P['sf']}"/><text x="120" y="172" font-family="{t}" font-size="14" font-weight="700" fill="{P['ac']}" letter-spacing="2">战略主线</text>
<text x="120" y="250" font-family="{t}" font-size="22" font-weight="700" fill="{P['tx']}">主业务深耕</text><text x="120" y="290" font-family="{t}" font-size="18" fill="{P['bd']}">头部客户 NDR 122%</text>
<text x="120" y="390" font-family="{t}" font-size="22" font-weight="700" fill="{P['tx']}">海外拓展</text><text x="120" y="430" font-family="{t}" font-size="18" fill="{P['bd']}">东南亚验证完成</text>
<text x="120" y="530" font-family="{t}" font-size="22" font-weight="700" fill="{P['tx']}">第二曲线</text><text x="120" y="570" font-family="{t}" font-size="18" fill="{P['bd']}">AI 业务月活破百万</text></g>
<g id="content-right"><rect x="648" y="130" width="555" height="530" rx="12" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="2"/><text x="688" y="172" font-family="{t}" font-size="14" font-weight="700" fill="{P['ac']}" letter-spacing="2">现状判断</text>
<text x="688" y="250" font-family="{t}" font-size="22" fill="{P['bd']}">中尾部留存不足 70%</text>
<text x="688" y="390" font-family="{t}" font-size="22" fill="{P['bd']}">欧洲仍处试点阶段</text>
<text x="688" y="530" font-family="{t}" font-size="22" fill="{P['bd']}">商业化路径尚未跑通</text></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">03 / 07</text></g>'''),
    4: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">战略落地路径</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-flow">
<rect x="80" y="200" width="200" height="420" rx="12" fill="{P['sf']}"/><text x="180" y="290" font-family="{t}" font-size="22" font-weight="700" fill="{P['ac']}" text-anchor="middle">Q1</text><text x="180" y="350" font-family="{t}" font-size="18" fill="{P['bd']}" text-anchor="middle">客户运营体系</text>
<rect x="310" y="200" width="200" height="420" rx="12" fill="{P['sf']}"/><text x="410" y="290" font-family="{t}" font-size="22" font-weight="700" fill="{P['ac']}" text-anchor="middle">Q2</text><text x="410" y="350" font-family="{t}" font-size="18" fill="{P['bd']}" text-anchor="middle">欧洲本地化</text>
<rect x="540" y="200" width="200" height="420" rx="12" fill="{P['sf']}"/><text x="640" y="290" font-family="{t}" font-size="22" font-weight="700" fill="{P['ac']}" text-anchor="middle">Q3</text><text x="640" y="350" font-family="{t}" font-size="18" fill="{P['bd']}" text-anchor="middle">AI 商业化</text>
<rect x="770" y="200" width="200" height="420" rx="12" fill="{P['sf']}"/><text x="870" y="290" font-family="{t}" font-size="22" font-weight="700" fill="{P['ac']}" text-anchor="middle">Q4</text><text x="870" y="350" font-family="{t}" font-size="18" fill="{P['bd']}" text-anchor="middle">独立核算</text>
<rect x="1000" y="200" width="200" height="420" rx="12" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/><text x="1100" y="290" font-family="{t}" font-size="22" font-weight="700" fill="{P['ac']}" text-anchor="middle">年底</text><text x="1100" y="350" font-family="{t}" font-size="18" fill="{P['bd']}" text-anchor="middle">方法论输出</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">04 / 07</text></g>'''),
    5: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">关键指标 OKR</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-metric">
<rect x="80" y="170" width="270" height="470" rx="16" fill="{P['sf']}"/><text x="215" y="360" font-family="{t}" font-size="64" font-weight="700" fill="{P['ac']}" text-anchor="middle">28%</text><text x="215" y="405" font-family="{t}" font-size="18" fill="{P['tx']}" text-anchor="middle">营收增长</text>
<rect x="370" y="170" width="270" height="470" rx="16" fill="{P['sf']}"/><text x="505" y="360" font-family="{t}" font-size="64" font-weight="700" fill="{P['ac']}" text-anchor="middle">41.5%</text><text x="505" y="405" font-family="{t}" font-size="18" fill="{P['tx']}" text-anchor="middle">毛利率</text>
<rect x="660" y="170" width="270" height="470" rx="16" fill="{P['sf']}"/><text x="795" y="360" font-family="{t}" font-size="64" font-weight="700" fill="{P['ac']}" text-anchor="middle">125%</text><text x="795" y="405" font-family="{t}" font-size="18" fill="{P['tx']}" text-anchor="middle">NDR 目标</text>
<rect x="950" y="170" width="270" height="470" rx="16" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/><text x="1085" y="360" font-family="{t}" font-size="64" font-weight="700" fill="{P['ac']}" text-anchor="middle">35%</text><text x="1085" y="405" font-family="{t}" font-size="18" fill="{P['tx']}" text-anchor="middle">海外占比</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">05 / 07</text></g>'''),
    6: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">风险与对冲</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="1120" height="88" rx="8" fill="{P['sf']}"/><text x="124" y="196" font-family="{t}" font-size="18" font-weight="700" fill="{P['tx']}">海外合规成本超预期</text><text x="124" y="222" font-family="{t}" font-size="16" fill="{P['bd']}">设立专项预算，法务团队前置</text>
<rect x="80" y="260" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><text x="124" y="296" font-family="{t}" font-size="18" font-weight="700" fill="{P['tx']}">AI 商业化不及预期</text><text x="124" y="322" font-family="{t}" font-size="16" fill="{P['bd']}">保留三条变现路径并行测试</text>
<rect x="80" y="360" width="1120" height="88" rx="8" fill="{P['sf']}"/><text x="124" y="396" font-family="{t}" font-size="18" font-weight="700" fill="{P['tx']}">核心人才流失</text><text x="124" y="422" font-family="{t}" font-size="16" fill="{P['bd']}">期权池补充，关键人保留</text>
<rect x="80" y="460" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><text x="124" y="496" font-family="{t}" font-size="18" font-weight="700" fill="{P['tx']}">汇率波动与价格战</text><text x="124" y="522" font-family="{t}" font-size="16" fill="{P['bd']}">自然对冲，价值锚定，产品差异化</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">06 / 07</text></g>'''),
    7: svg(f'''<defs><radialGradient id="bmclose" cx="50%" cy="50%" r="70%"><stop offset="0%" stop-color="#F0F4F8"/><stop offset="100%" stop-color="#FFFFFF"/></radialGradient></defs>
<g id="background"><rect x="0" y="0" width="1280" height="720" fill="url(#bmclose)"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-quote"><text x="640" y="260" font-family="Georgia, serif" font-size="180" font-weight="700" fill="{P['ac']}" fill-opacity="0.12" text-anchor="middle">"</text><text x="640" y="380" font-family="{t}" font-size="32" fill="{P['tx']}" text-anchor="middle">战略不是宏大叙事，</text><text x="640" y="428" font-family="{t}" font-size="32" fill="{P['tx']}" text-anchor="middle">而是每个季度兑现可验证的事。</text><rect x="590" y="470" width="100" height="3" fill="{P['ac']}"/></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">07 / 07</text></g>'''),
    }

# ═══════════════════════════════════════════
# Case 3: prod-keynote (Ocean Deep)
# ═══════════════════════════════════════════
def prod_keynote():
    t = F("ocean-deep")
    P = {"bg":"#0A1628","sf":"#0F2540","ac":"#0EA5E9","tx":"#F0F9FF","bd":"#7DD3FC","ft":"#38BDF8","mt":"#1E3A5F"}
    return {
    1: svg(f'''<defs><linearGradient id="bg1" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#0A1628"/><stop offset="100%" stop-color="#0F2540"/></linearGradient></defs>
<g id="background"><rect x="0" y="0" width="1280" height="720" fill="url(#bg1)"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-eyebrow"><text x="120" y="120" font-family="{t}" font-size="14" font-weight="600" fill="{P['ac']}" letter-spacing="4">PRODUCT LAUNCH · 2026</text></g>
<g id="content-title"><text x="120" y="300" font-family="{t}" font-size="84" font-weight="700" fill="{P['tx']}">Aurora Pro</text><text x="120" y="380" font-family="{t}" font-size="40" fill="{P['ac']}">重新定义专业创作</text></g>
<g id="content-divider"><rect x="120" y="420" width="200" height="4" fill="{P['ac']}"/></g>
<g id="content-subtitle"><text x="120" y="480" font-family="{t}" font-size="22" fill="{P['bd']}">当算力不再是瓶颈，创意便不再有等待</text></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="120" y="708" font-family="{t}" font-size="12" fill="{P['ft']}">01 / 06</text></g>'''),
    2: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">性能数据</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-metric">
<rect x="80" y="170" width="270" height="470" rx="16" fill="{P['sf']}"/><rect x="80" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="215" y="360" font-family="{t}" font-size="72" font-weight="700" fill="{P['ac']}" text-anchor="middle">4.2×</text>
<text x="215" y="400" font-family="{t}" font-size="18" font-weight="600" fill="{P['tx']}" text-anchor="middle">渲染速度提升</text>
<rect x="370" y="170" width="270" height="470" rx="16" fill="{P['sf']}"/><rect x="370" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="505" y="360" font-family="{t}" font-size="72" font-weight="700" fill="{P['ac']}" text-anchor="middle">38%</text>
<text x="505" y="400" font-family="{t}" font-size="18" font-weight="600" fill="{P['tx']}" text-anchor="middle">内存占用降低</text>
<rect x="660" y="170" width="270" height="470" rx="16" fill="{P['sf']}"/><rect x="660" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="795" y="360" font-family="{t}" font-size="72" font-weight="700" fill="{P['ac']}" text-anchor="middle">22h</text>
<text x="795" y="400" font-family="{t}" font-size="18" font-weight="600" fill="{P['tx']}" text-anchor="middle">续航突破</text>
<rect x="950" y="170" width="270" height="470" rx="16" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/><rect x="950" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="1085" y="360" font-family="{t}" font-size="72" font-weight="700" fill="{P['ac']}" text-anchor="middle">0.6s</text>
<text x="1085" y="400" font-family="{t}" font-size="18" font-weight="600" fill="{P['tx']}" text-anchor="middle">首屏冷启动</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">02 / 06</text></g>'''),
    3: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="86" font-family="{t}" font-size="38" font-weight="700" fill="{P['tx']}">旧版 vs 新版</text><rect x="96" y="100" width="60" height="3" fill="{P['ac']}"/></g>
<g id="content-left"><rect x="80" y="130" width="555" height="530" rx="12" fill="{P['sf']}"/>
<text x="120" y="172" font-family="{t}" font-size="14" font-weight="700" fill="{P['ac']}" letter-spacing="2">AURORA 经典版</text>
<line x1="120" y1="192" x2="595" y2="192" stroke="{P['mt']}" stroke-width="1"/>
<text x="120" y="240" font-family="{t}" font-size="20" fill="{P['bd']}">M2 芯片</text><text x="120" y="300" font-family="{t}" font-size="20" fill="{P['bd']}">渲染 4K 视频 12 分钟</text>
<text x="120" y="360" font-family="{t}" font-size="20" fill="{P['bd']}">续航 14 小时</text>
<text x="120" y="420" font-family="{t}" font-size="20" fill="{P['bd']}">1.6 公斤，机身较厚</text>
<text x="120" y="480" font-family="{t}" font-size="20" fill="{P['bd']}">$1,899 起</text></g>
<g id="content-right"><rect x="648" y="130" width="555" height="530" rx="12" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/>
<text x="688" y="172" font-family="{t}" font-size="14" font-weight="700" fill="{P['ac']}" letter-spacing="2">AURORA PRO</text>
<line x1="688" y1="192" x2="1163" y2="192" stroke="{P['ac']}" stroke-width="1" opacity="0.3"/>
<text x="688" y="240" font-family="{t}" font-size="20" font-weight="700" fill="{P['ac']}">M4 Ultra 芯片</text><text x="688" y="300" font-family="{t}" font-size="20" fill="{P['tx']}">渲染 4K 视频 2.8 分钟</text>
<text x="688" y="360" font-family="{t}" font-size="20" fill="{P['tx']}">续航 22 小时</text>
<text x="688" y="420" font-family="{t}" font-size="20" fill="{P['tx']}">1.2 公斤，超薄设计</text>
<text x="688" y="480" font-family="{t}" font-size="20" fill="{P['tx']}">$2,199 起</text></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">03 / 06</text></g>'''),
    4: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">三大全新体验</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="170" width="1120" height="130" rx="12" fill="{P['sf']}"/>
<text x="120" y="215" font-family="{t}" font-size="24" font-weight="700" fill="{P['ac']}">01 原生 AI 协作</text>
<text x="120" y="252" font-family="{t}" font-size="18" fill="{P['bd']}">本地推理大模型，创意零延迟</text>
<rect x="80" y="318" width="1120" height="130" rx="12" fill="{P['sf']}"/>
<text x="120" y="363" font-family="{t}" font-size="24" font-weight="700" fill="{P['ac']}">02 空间显示</text>
<text x="120" y="400" font-family="{t}" font-size="18" fill="{P['bd']}">裸眼三维预览，所见即所得</text>
<rect x="80" y="466" width="1120" height="130" rx="12" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/>
<text x="120" y="511" font-family="{t}" font-size="24" font-weight="700" fill="{P['ac']}">03 跨设备无缝</text>
<text x="120" y="548" font-family="{t}" font-size="18" fill="{P['bd']}">手机、平板、桌面共享创作上下文</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">04 / 06</text></g>'''),
    5: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">上市节奏</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="170" width="1120" height="80" rx="8" fill="{P['sf']}"/>
<text x="120" y="218" font-family="{t}" font-size="22" fill="{P['tx']}">今天起：全球预订开启</text>
<rect x="80" y="264" width="1120" height="80" rx="8" fill="{P['bg']}" stroke="{P['mt']}" stroke-width="1"/>
<text x="120" y="312" font-family="{t}" font-size="22" fill="{P['tx']}">11 月 8 日：北美、日本、欧洲首发</text>
<rect x="80" y="358" width="1120" height="80" rx="8" fill="{P['sf']}"/>
<text x="120" y="406" font-family="{t}" font-size="22" fill="{P['tx']}">11 月 22 日：中国大陆与港澳台同步发售</text>
<rect x="80" y="452" width="1120" height="80" rx="8" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/>
<text x="120" y="500" font-family="{t}" font-size="22" fill="{P['ac']}">教育优惠：学生立省 $200 · 旧机折抵最高 $600</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">05 / 06</text></g>'''),
    6: svg(f'''<defs><radialGradient id="cg" cx="50%" cy="50%" r="70%"><stop offset="0%" stop-color="#0F2540"/><stop offset="100%" stop-color="#0A1628"/></radialGradient></defs>
<g id="background"><rect x="0" y="0" width="1280" height="720" fill="url(#cg)"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title">
<text x="640" y="280" font-family="{t}" font-size="22" font-weight="600" fill="{P['ac']}" text-anchor="middle" letter-spacing="6">AVAILABLE TODAY</text>
<text x="640" y="400" font-family="{t}" font-size="96" font-weight="700" fill="{P['tx']}" text-anchor="middle">今天上市</text>
<rect x="490" y="426" width="300" height="4" fill="{P['ac']}"/>
<text x="640" y="500" font-family="{t}" font-size="22" fill="{P['bd']}" text-anchor="middle">技术存在的意义，是让每个人都能创造非凡。</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="120" y="708" font-family="{t}" font-size="12" fill="{P['ft']}">06 / 06</text></g>'''),
    }

# ═══════════════════════════════════════════
# Case 4: rep-monthly (Data Forward)
# ═══════════════════════════════════════════
def rep_monthly():
    t = F("data-forward")
    P = {"bg":"#F1F5F9","sf":"#FFFFFF","ac":"#0284C7","tx":"#0F172A","bd":"#475569","mt":"#94A3B8"}
    return {
    1: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-eyebrow"><text x="96" y="160" font-family="{t}" font-size="16" font-weight="600" fill="{P['ac']}" letter-spacing="4">MONTHLY REVIEW · APR 2026</text></g>
<g id="content-title"><text x="96" y="280" font-family="{t}" font-size="56" font-weight="700" fill="{P['tx']}">2026 年 4 月业务月报</text></g>
<g id="content-divider"><rect x="96" y="310" width="200" height="4" fill="{P['ac']}"/></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">01 / 07</text></g>'''),
    2: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">北极星指标</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-metric">
<rect x="80" y="170" width="356" height="440" rx="16" fill="{P['sf']}"/><rect x="80" y="170" width="356" height="6" rx="3" fill="{P['ac']}"/>
<text x="258" y="370" font-family="{t}" font-size="72" font-weight="700" fill="{P['ac']}" text-anchor="middle">480万</text>
<text x="258" y="410" font-family="{t}" font-size="18" font-weight="600" fill="{P['tx']}" text-anchor="middle">月活 MAU</text>
<text x="258" y="440" font-family="{t}" font-size="16" fill="{P['bd']}" text-anchor="middle">环比 +12%</text>
<rect x="462" y="170" width="356" height="440" rx="16" fill="{P['sf']}"/><rect x="462" y="170" width="356" height="6" rx="3" fill="{P['ac']}"/>
<text x="640" y="370" font-family="{t}" font-size="72" font-weight="700" fill="{P['ac']}" text-anchor="middle">8.4%</text>
<text x="640" y="410" font-family="{t}" font-size="18" font-weight="600" fill="{P['tx']}" text-anchor="middle">付费转化率</text>
<text x="640" y="440" font-family="{t}" font-size="16" fill="{P['bd']}" text-anchor="middle">环比 +0.6 pct</text>
<rect x="844" y="170" width="356" height="440" rx="16" fill="{P['sf']}"/><rect x="844" y="170" width="356" height="6" rx="3" fill="{P['ac']}"/>
<text x="1022" y="370" font-family="{t}" font-size="60" font-weight="700" fill="{P['ac']}" text-anchor="middle">¥1240万</text>
<text x="1022" y="410" font-family="{t}" font-size="18" font-weight="600" fill="{P['tx']}" text-anchor="middle">MRR</text>
<text x="1022" y="440" font-family="{t}" font-size="16" fill="{P['bd']}" text-anchor="middle">环比 +18%</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">02 / 07</text></g>'''),
    3: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">本月 vs 上月</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="1120" height="80" rx="8" fill="{P['sf']}"/>
<text x="120" y="208" font-family="{t}" font-size="20" fill="{P['tx']}">新增付费用户 3.2 万，净增 2.4 万（流失 0.8 万）</text>
<rect x="80" y="254" width="1120" height="80" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="120" y="302" font-family="{t}" font-size="20" fill="{P['tx']}">平均客单价 ¥312，较上月 +9%</text>
<rect x="80" y="348" width="1120" height="80" rx="8" fill="{P['sf']}"/>
<text x="120" y="396" font-family="{t}" font-size="20" fill="{P['tx']}">渠道获客成本 ¥168，较上月 -14%</text>
<rect x="80" y="442" width="1120" height="80" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="120" y="490" font-family="{t}" font-size="20" fill="{P['tx']}">客服首响时长 2 分 18 秒，目标 2 分内</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">03 / 07</text></g>'''),
    4: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">三大洞察</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="170" width="1120" height="130" rx="12" fill="{P['sf']}"/>
<rect x="100" y="188" width="4" height="94" rx="2" fill="{P['ac']}"/>
<text x="124" y="220" font-family="{t}" font-size="20" font-weight="700" fill="{P['tx']}">学生群体留存率领先职场用户 22 个百分点</text>
<text x="124" y="252" font-family="{t}" font-size="16" fill="{P['bd']}">学生市场是被低估的增长飞轮</text>
<rect x="80" y="318" width="1120" height="130" rx="12" fill="{P['sf']}"/>
<rect x="100" y="336" width="4" height="94" rx="2" fill="{P['ac']}"/>
<text x="124" y="368" font-family="{t}" font-size="20" font-weight="700" fill="{P['tx']}">签到打卡功能贡献 31% 的次日留存</text>
<text x="124" y="400" font-family="{t}" font-size="16" fill="{P['bd']}">轻互动机制显著提升粘性</text>
<rect x="80" y="466" width="1120" height="130" rx="12" fill="{P['sf']}"/>
<rect x="100" y="484" width="4" height="94" rx="2" fill="{P['ac']}"/>
<text x="124" y="516" font-family="{t}" font-size="20" font-weight="700" fill="{P['tx']}">东南亚双语用户 ARPU 比国内同类高 1.8 倍</text>
<text x="124" y="548" font-family="{t}" font-size="16" fill="{P['bd']}">海外市场价值远超预期</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">04 / 07</text></g>'''),
    5: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">行动项</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="1120" height="88" rx="8" fill="{P['sf']}"/><circle cx="124" cy="204" r="5" fill="{P['ac']}"/>
<text x="148" y="210" font-family="{t}" font-size="20" fill="{P['tx']}">上线学生认证体系，放大学生人群优势</text>
<rect x="80" y="260" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><circle cx="124" cy="304" r="5" fill="{P['ac']}"/>
<text x="148" y="310" font-family="{t}" font-size="20" fill="{P['tx']}">签到打卡能力扩展至全场景</text>
<rect x="80" y="360" width="1120" height="88" rx="8" fill="{P['sf']}"/><circle cx="124" cy="404" r="5" fill="{P['ac']}"/>
<text x="148" y="410" font-family="{t}" font-size="20" fill="{P['tx']}">东南亚双语版本投入产品资源</text>
<rect x="80" y="460" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><circle cx="124" cy="504" r="5" fill="{P['ac']}"/>
<text x="148" y="510" font-family="{t}" font-size="20" fill="{P['tx']}">小程序首页改版进入 A/B 测试</text>
<rect x="80" y="560" width="1120" height="88" rx="8" fill="{P['sf']}"/><circle cx="124" cy="604" r="5" fill="{P['ac']}"/>
<text x="148" y="610" font-family="{t}" font-size="20" fill="{P['tx']}">推出"老带新"激励 v2，目标转化率翻倍</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">05 / 07</text></g>'''),
    6: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">风险预警</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="170" width="1120" height="80" rx="8" fill="{P['sf']}"/><rect x="100" y="188" width="4" height="44" rx="2" fill="#E11D48"/>
<text x="124" y="218" font-family="{t}" font-size="20" fill="{P['tx']}">iOS 投放 ROI 下降 18%（苹果广告政策调整）</text>
<rect x="80" y="264" width="1120" height="80" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><rect x="100" y="282" width="4" height="44" rx="2" fill="#F59E0B"/>
<text x="124" y="312" font-family="{t}" font-size="20" fill="{P['tx']}">客服团队压力指数突破阈值，需扩招</text>
<rect x="80" y="358" width="1120" height="80" rx="8" fill="{P['sf']}"/><rect x="100" y="376" width="4" height="44" rx="2" fill="#F59E0B"/>
<text x="124" y="406" font-family="{t}" font-size="20" fill="{P['tx']}">数据基础设施容量预警，Q3 必须扩容</text>
<rect x="80" y="452" width="1120" height="80" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><rect x="100" y="470" width="4" height="44" rx="2" fill="#F59E0B"/>
<text x="124" y="500" font-family="{t}" font-size="20" fill="{P['tx']}">头部 KOL 合作到期，续签价格上涨 30%</text>
<rect x="80" y="546" width="1120" height="80" rx="8" fill="{P['sf']}"/><rect x="100" y="564" width="4" height="44" rx="2" fill="#F59E0B"/>
<text x="124" y="594" font-family="{t}" font-size="20" fill="{P['tx']}">监管层对数据出境细则尚未明确</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">06 / 07</text></g>'''),
    7: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-quote">
<text x="640" y="280" font-family="{t}" font-size="180" font-weight="700" fill="{P['ac']}" fill-opacity="0.12" text-anchor="middle">"</text>
<text x="640" y="380" font-family="{t}" font-size="30" fill="{P['tx']}" text-anchor="middle">守住北极星，放大学生市场，</text>
<text x="640" y="420" font-family="{t}" font-size="30" fill="{P['tx']}" text-anchor="middle">完成签到能力升级。</text>
<rect x="590" y="460" width="100" height="3" fill="{P['ac']}"/>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">07 / 07</text></g>'''),
    }

# ═══════════════════════════════════════════
# Case 5: edu-stem (Data Forward - 教学课件)
# ═══════════════════════════════════════════
def edu_stem():
    t = F("data-forward")
    P = {"bg":"#F1F5F9","sf":"#FFFFFF","ac":"#0284C7","tx":"#0F172A","bd":"#475569","mt":"#94A3B8"}
    return {
    1: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-eyebrow"><text x="96" y="180" font-family="{t}" font-size="16" font-weight="600" fill="{P['ac']}" letter-spacing="4">微积分基础 · 第七讲</text></g>
<g id="content-title"><text x="96" y="320" font-family="{t}" font-size="64" font-weight="700" fill="{P['tx']}">链式法则</text></g>
<g id="content-subtitle"><text x="96" y="390" font-family="{t}" font-size="24" fill="{P['bd']}">Chain Rule — 复合函数求导的核心工具</text></g>
<g id="content-divider"><rect x="96" y="420" width="200" height="4" fill="{P['ac']}"/></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">01 / 07</text></g>'''),
    2: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">本节目标</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="1120" height="88" rx="8" fill="{P['sf']}"/><rect x="100" y="178" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="200" font-family="{t}" font-size="20" font-weight="600" fill="{P['tx']}">理解复合函数求导的几何直观</text>
<text x="124" y="228" font-family="{t}" font-size="14" fill="{P['bd']}">内外层函数如何"嵌套"——用洋葱模型类比</text>
<rect x="80" y="260" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><rect x="100" y="278" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="300" font-family="{t}" font-size="20" font-weight="600" fill="{P['tx']}">掌握链式法则的标准写法与变形</text>
<text x="124" y="328" font-family="{t}" font-size="14" fill="{P['bd']}">dy/dx = f'(g(x)) · g'(x)，以及莱布尼茨记号形式</text>
<rect x="80" y="360" width="1120" height="88" rx="8" fill="{P['sf']}"/><rect x="100" y="378" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="400" font-family="{t}" font-size="20" font-weight="600" fill="{P['tx']}">能识别复合层级并按顺序拆解</text>
<text x="124" y="428" font-family="{t}" font-size="14" fill="{P['bd']}">从外到内逐层"剥壳"，避免遗漏中间层</text>
<rect x="80" y="460" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><rect x="100" y="478" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="500" font-family="{t}" font-size="20" font-weight="600" fill="{P['tx']}">会应用链式法则解决物理与经济场景题</text>
<text x="124" y="528" font-family="{t}" font-size="14" fill="{P['bd']}">如：瞬时变化率、边际成本、相关变化率</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">02 / 07</text></g>'''),
    3: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="86" font-family="{t}" font-size="38" font-weight="700" fill="{P['tx']}">知识回顾 vs 新概念</text><rect x="96" y="100" width="60" height="3" fill="{P['ac']}"/></g>
<g id="content-left"><rect x="80" y="130" width="555" height="530" rx="12" fill="{P['sf']}"/>
<text x="120" y="172" font-family="{t}" font-size="14" font-weight="700" fill="{P['ac']}" letter-spacing="2">已学：基本求导</text>
<line x1="120" y1="192" x2="595" y2="192" stroke="#E2E8F0" stroke-width="1"/>
<text x="120" y="240" font-family="{t}" font-size="18" fill="{P['tx']}">幂函数、指数、对数、三角函数的导数</text>
<text x="120" y="300" font-family="{t}" font-size="18" fill="{P['tx']}">加减法则、乘积法则、商法则</text>
<text x="120" y="360" font-family="{t}" font-size="18" fill="{P['tx']}">一阶导数的几何意义：切线斜率</text>
<text x="120" y="430" font-family="{t}" font-size="14" fill="{P['mt']}">但：当函数"套函数"时，以上法则都不够用</text></g>
<g id="content-right"><rect x="648" y="130" width="555" height="530" rx="12" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/>
<text x="688" y="172" font-family="{t}" font-size="14" font-weight="700" fill="{P['ac']}" letter-spacing="2">本节新概念</text>
<line x1="688" y1="192" x2="1163" y2="192" stroke="{P['ac']}" stroke-width="1" opacity="0.3"/>
<text x="688" y="240" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">链式法则 Chain Rule</text>
<text x="688" y="300" font-family="{t}" font-size="18" fill="{P['tx']}">核心公式：dy/dx = f'(g(x)) · g'(x)</text>
<text x="688" y="360" font-family="{t}" font-size="18" fill="{P['tx']}">直觉：外层变化率 × 内层变化率</text>
<text x="688" y="430" font-family="{t}" font-size="14" fill="{P['ac']}">关键：把复杂函数拆成简单函数的"嵌套"</text></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">03 / 07</text></g>'''),
    4: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">推导过程</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="1120" height="88" rx="8" fill="{P['sf']}"/>
<text x="120" y="200" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">Step 1</text>
<text x="200" y="200" font-family="{t}" font-size="18" fill="{P['tx']}">设 y = f(u), u = g(x)，则 y = f(g(x))</text>
<rect x="80" y="260" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="120" y="300" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">Step 2</text>
<text x="200" y="300" font-family="{t}" font-size="18" fill="{P['tx']}">自变量 x 微小变化 Δx，导致 u 变化 Δu = g'(x)·Δx</text>
<rect x="80" y="360" width="1120" height="88" rx="8" fill="{P['sf']}"/>
<text x="120" y="400" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">Step 3</text>
<text x="200" y="400" font-family="{t}" font-size="18" fill="{P['tx']}">u 的变化进一步导致 y 变化 Δy ≈ f'(u)·Δu</text>
<rect x="80" y="460" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="120" y="500" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">Step 4</text>
<text x="200" y="500" font-family="{t}" font-size="18" fill="{P['tx']}">取极限得 dy/dx = f'(g(x)) · g'(x) ← 这就是链式法则</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">04 / 07</text></g>'''),
    5: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">经典例题</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="548" height="88" rx="8" fill="{P['sf']}"/>
<text x="120" y="200" font-family="{t}" font-size="16" font-weight="600" fill="{P['ac']}">例 1</text>
<text x="172" y="200" font-family="{t}" font-size="16" fill="{P['tx']}">y = sin(2x+1)</text>
<text x="120" y="228" font-family="{t}" font-size="14" fill="{P['bd']}">dy/dx = 2cos(2x+1)</text>
<rect x="648" y="160" width="548" height="88" rx="8" fill="{P['sf']}"/>
<text x="688" y="200" font-family="{t}" font-size="16" font-weight="600" fill="{P['ac']}">例 2</text>
<text x="740" y="200" font-family="{t}" font-size="16" fill="{P['tx']}">y = (3x²+1)⁵</text>
<text x="688" y="228" font-family="{t}" font-size="14" fill="{P['bd']}">dy/dx = 30x(3x²+1)⁴</text>
<rect x="80" y="260" width="548" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="120" y="300" font-family="{t}" font-size="16" font-weight="600" fill="{P['ac']}">例 3</text>
<text x="172" y="300" font-family="{t}" font-size="16" fill="{P['tx']}">y = e^(-x²)</text>
<text x="120" y="328" font-family="{t}" font-size="14" fill="{P['bd']}">dy/dx = -2x · e^(-x²)</text>
<rect x="648" y="260" width="548" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="688" y="300" font-family="{t}" font-size="16" font-weight="600" fill="{P['ac']}">例 4</text>
<text x="740" y="300" font-family="{t}" font-size="16" fill="{P['tx']}">y = ln(1+x²)</text>
<text x="688" y="328" font-family="{t}" font-size="14" fill="{P['bd']}">dy/dx = 2x / (1+x²)</text>
<rect x="80" y="360" width="1116" height="88" rx="8" fill="{P['sf']}" stroke="{P['ac']}" stroke-width="1"/>
<text x="120" y="400" font-family="{t}" font-size="16" font-weight="600" fill="{P['ac']}">例 5  三层嵌套</text>
<text x="300" y="400" font-family="{t}" font-size="16" fill="{P['tx']}">y = sin(ln(x²+1))</text>
<text x="120" y="428" font-family="{t}" font-size="14" fill="{P['bd']}">从外到内：sin → ln → (x²+1)，自行展开</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">05 / 07</text></g>'''),
    6: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">数值验证</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="170" width="1120" height="100" rx="12" fill="{P['sf']}"/>
<text x="120" y="215" font-family="{t}" font-size="20" font-weight="600" fill="{P['tx']}">取 y = (2x+1)³，x = 1</text>
<text x="120" y="248" font-family="{t}" font-size="16" fill="{P['bd']}">先展开再求导：dy/dx = 3(2x+1)² · 2 = 6 · 9 = 54</text>
<rect x="80" y="290" width="548" height="120" rx="12" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/>
<text x="120" y="330" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">链式法则结果</text>
<text x="120" y="365" font-family="{t}" font-size="36" font-weight="700" fill="{P['ac']}">54</text>
<rect x="648" y="290" width="548" height="120" rx="12" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="688" y="330" font-family="{t}" font-size="16" font-weight="700" fill="{P['tx']}">数值差分 (Δx=0.001)</text>
<text x="688" y="365" font-family="{t}" font-size="36" font-weight="700" fill="{P['tx']}">54.012</text>
<rect x="80" y="430" width="1120" height="80" rx="8" fill="{P['sf']}"/>
<text x="120" y="478" font-family="{t}" font-size="18" fill="{P['tx']}">误差 0.02%，验证公式正确</text>
<text x="600" y="478" font-family="{t}" font-size="14" fill="{P['mt']}">提示：数值法适合检验解析解，不适合代替</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">06 / 07</text></g>'''),
    7: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-quote">
<text x="640" y="260" font-family="{t}" font-size="180" font-weight="700" fill="{P['ac']}" fill-opacity="0.12" text-anchor="middle">"</text>
<text x="640" y="360" font-family="{t}" font-size="28" fill="{P['tx']}" text-anchor="middle">完成讲义第 87 页 1-12 题，</text>
<text x="640" y="400" font-family="{t}" font-size="28" fill="{P['tx']}" text-anchor="middle">周三课前提交至学习通。</text>
<rect x="590" y="440" width="100" height="3" fill="{P['ac']}"/>
<text x="640" y="490" font-family="{t}" font-size="16" fill="{P['bd']}" text-anchor="middle">下节预告：隐函数求导与对数微分法</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">07 / 07</text></g>'''),
    }

# ═══════════════════════════════════════════
# Case 6: aca-thesis (Academic Royal)
# ═══════════════════════════════════════════
def aca_thesis():
    t = F("academic-royal")
    P = {"bg":"#FAFAF9","sf":"#F5F3FF","ac":"#5B21B6","tx":"#1C1917","bd":"#57534E","mt":"#A8A29E"}
    return {
    1: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-eyebrow"><text x="96" y="160" font-family="{t}" font-size="14" font-weight="600" fill="{P['ac']}" letter-spacing="4">硕士学位论文答辩</text></g>
<g id="content-title"><text x="96" y="290" font-family="{t}" font-size="42" font-weight="700" fill="{P['tx']}">基于多模态融合的</text><text x="96" y="345" font-family="{t}" font-size="42" font-weight="700" fill="{P['tx']}">医疗影像辅助诊断研究</text></g>
<g id="content-divider"><rect x="96" y="375" width="200" height="4" fill="{P['ac']}"/></g>
<g id="content-meta"><text x="96" y="430" font-family="{t}" font-size="16" fill="{P['bd']}">答辩人：张三　　导师：李教授　　专业：生物医学工程</text></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">01 / 08</text></g>'''),
    2: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">选题背景</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="1120" height="88" rx="8" fill="{P['sf']}"/><rect x="100" y="178" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="200" font-family="{t}" font-size="18" fill="{P['tx']}">全球放射科医师缺口超过 20 万，中国基层尤其突出</text>
<rect x="80" y="260" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><rect x="100" y="278" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="300" font-family="{t}" font-size="18" fill="{P['tx']}">单模态深度学习模型在跨中心场景下泛化不足</text>
<rect x="80" y="360" width="1120" height="88" rx="8" fill="{P['sf']}"/><rect x="100" y="378" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="400" font-family="{t}" font-size="18" fill="{P['tx']}">多模态（影像+文本+结构化数据）融合是下一个突破口</text>
<rect x="80" y="460" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><rect x="100" y="478" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="500" font-family="{t}" font-size="18" fill="{P['tx']}">国家"十四五"明确支持医工交叉研究</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">02 / 08</text></g>'''),
    3: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-quote">
<text x="640" y="260" font-family="{t}" font-size="180" font-weight="700" fill="{P['ac']}" fill-opacity="0.12" text-anchor="middle">"</text>
<text x="640" y="370" font-family="{t}" font-size="26" fill="{P['tx']}" text-anchor="middle">如何在标注稀缺场景下，</text>
<text x="640" y="410" font-family="{t}" font-size="26" fill="{P['ac']}" text-anchor="middle">构建可解释的多模态医疗影像诊断模型？</text>
<rect x="590" y="450" width="100" height="3" fill="{P['ac']}"/>
<text x="640" y="500" font-family="{t}" font-size="16" fill="{P['bd']}" text-anchor="middle">研究问题</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">03 / 08</text></g>'''),
    4: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">方法与数据</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="1120" height="88" rx="8" fill="{P['sf']}"/>
<text x="120" y="200" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">1. 数据收集</text>
<text x="300" y="200" font-family="{t}" font-size="18" fill="{P['tx']}">三家三甲医院 8.6 万例胸部 CT + 报告</text>
<rect x="80" y="260" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="120" y="300" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">2. 预处理</text>
<text x="300" y="300" font-family="{t}" font-size="18" fill="{P['tx']}">标准化窗宽窗位 + 文本结构化抽取</text>
<rect x="80" y="360" width="1120" height="88" rx="8" fill="{P['sf']}"/>
<text x="120" y="400" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">3. 模型设计</text>
<text x="300" y="400" font-family="{t}" font-size="18" fill="{P['tx']}">跨模态对比学习 + 弱监督引导</text>
<rect x="80" y="460" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="120" y="500" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">4. 可解释模块</text>
<text x="300" y="500" font-family="{t}" font-size="18" fill="{P['tx']}">基于注意力的病灶可视化</text>
<rect x="80" y="560" width="1120" height="88" rx="8" fill="{P['sf']}"/>
<text x="120" y="600" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">5. 评估方案</text>
<text x="300" y="600" font-family="{t}" font-size="18" fill="{P['tx']}">三家医院交叉验证 + 临床医师双盲评审</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">04 / 08</text></g>'''),
    5: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">核心创新点</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="548" height="130" rx="8" fill="{P['sf']}"/>
<text x="120" y="200" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">创新一</text>
<text x="120" y="228" font-family="{t}" font-size="15" fill="{P['tx']}">跨中心一致性约束损失函数 CCC-Loss</text>
<rect x="648" y="160" width="548" height="130" rx="8" fill="{P['sf']}"/>
<text x="688" y="200" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">创新二</text>
<text x="688" y="228" font-family="{t}" font-size="15" fill="{P['tx']}">文本-影像对齐的弱监督预训练范式</text>
<rect x="80" y="304" width="548" height="130" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="120" y="344" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">创新三</text>
<text x="120" y="372" font-family="{t}" font-size="15" fill="{P['tx']}">面向临床的多粒度可解释输出</text>
<rect x="648" y="304" width="548" height="130" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="688" y="344" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">创新四</text>
<text x="688" y="372" font-family="{t}" font-size="15" fill="{P['tx']}">小样本微调框架，新病种 50 例即达 90%</text>
<rect x="80" y="448" width="1116" height="130" rx="8" fill="{P['sf']}" stroke="{P['ac']}" stroke-width="1"/>
<text x="120" y="488" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">创新五</text>
<text x="120" y="516" font-family="{t}" font-size="15" fill="{P['tx']}">开源工具链 MedFuseKit，已被 7 家机构使用</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">05 / 08</text></g>'''),
    6: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="86" font-family="{t}" font-size="38" font-weight="700" fill="{P['tx']}">实验结果 vs 现有方法</text><rect x="96" y="100" width="60" height="3" fill="{P['ac']}"/></g>
<g id="content-left"><rect x="80" y="130" width="555" height="530" rx="12" fill="{P['sf']}"/>
<text x="120" y="172" font-family="{t}" font-size="14" font-weight="700" fill="{P['ac']}" letter-spacing="2">现有方法</text>
<line x1="120" y1="192" x2="595" y2="192" stroke="#E7E5E4" stroke-width="1"/>
<text x="120" y="240" font-family="{t}" font-size="16" fill="{P['tx']}">ResNet50 单模态：AUC 0.842</text>
<text x="120" y="268" font-family="{t}" font-size="14" fill="{P['bd']}">跨中心下降至 0.74</text>
<text x="120" y="340" font-family="{t}" font-size="16" fill="{P['tx']}">CLIP 通用预训练：AUC 0.871</text>
<text x="120" y="368" font-family="{t}" font-size="14" fill="{P['bd']}">可解释性弱</text></g>
<g id="content-right"><rect x="648" y="130" width="555" height="530" rx="12" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/>
<text x="688" y="172" font-family="{t}" font-size="14" font-weight="700" fill="{P['ac']}" letter-spacing="2">我们的 MedFuse</text>
<line x1="688" y1="192" x2="1163" y2="192" stroke="{P['ac']}" stroke-width="1" opacity="0.3"/>
<text x="688" y="240" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">AUC 0.927，跨中心保持 0.91</text>
<text x="688" y="268" font-family="{t}" font-size="14" fill="{P['tx']}">泛化能力大幅领先</text>
<text x="688" y="340" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">MedFuse + 临床后处理</text>
<text x="688" y="368" font-family="{t}" font-size="14" fill="{P['tx']}">假阳性率降低 37%</text></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">06 / 08</text></g>'''),
    7: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-quote">
<text x="640" y="260" font-family="{t}" font-size="180" font-weight="700" fill="{P['ac']}" fill-opacity="0.12" text-anchor="middle">"</text>
<text x="640" y="370" font-family="{t}" font-size="26" fill="{P['tx']}" text-anchor="middle">三家医院仍属东部地区，</text>
<text x="640" y="410" font-family="{t}" font-size="26" fill="{P['ac']}" text-anchor="middle">后续将引入西部样本验证泛化能力。</text>
<rect x="590" y="450" width="100" height="3" fill="{P['ac']}"/>
<text x="640" y="500" font-family="{t}" font-size="16" fill="{P['bd']}" text-anchor="middle">不足与展望</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">07 / 08</text></g>'''),
    8: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title">
<text x="640" y="320" font-family="{t}" font-size="72" font-weight="700" fill="{P['tx']}" text-anchor="middle">感谢各位老师</text>
<rect x="490" y="348" width="300" height="4" fill="{P['ac']}"/>
<text x="640" y="410" font-family="{t}" font-size="22" fill="{P['bd']}" text-anchor="middle">恳请批评指正</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">08 / 08</text></g>'''),
    }

# ═══════════════════════════════════════════
# Case 7: mkt-campaign (Coral Energy)
# ═══════════════════════════════════════════
def mkt_campaign():
    t = F("coral-energy")
    P = {"bg":"#FFFBF5","sf":"#FFF0ED","ac":"#F96167","tx":"#1A1A2E","bd":"#5A5A72","mt":"#FFB4B4"}
    return {
    1: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-eyebrow"><text x="96" y="180" font-family="{t}" font-size="14" font-weight="600" fill="{P['ac']}" letter-spacing="4">整合营销方案 · 2026 春</text></g>
<g id="content-title"><text x="96" y="320" font-family="{t}" font-size="64" font-weight="700" fill="{P['tx']}">「春日新生」</text></g>
<g id="content-subtitle"><text x="96" y="390" font-family="{t}" font-size="24" fill="{P['bd']}">不卖产品，卖一段属于自己的春天。</text></g>
<g id="content-divider"><rect x="96" y="420" width="200" height="4" fill="{P['ac']}"/></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">01 / 07</text></g>'''),
    2: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">市场洞察</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="1120" height="88" rx="8" fill="{P['sf']}"/><rect x="100" y="178" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="200" font-family="{t}" font-size="18" fill="{P['tx']}">Z 世代将"春天"重新定义为情绪修复期</text>
<rect x="80" y="260" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><rect x="100" y="278" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="300" font-family="{t}" font-size="18" fill="{P['tx']}">小红书"春日穿搭"笔记同比 +186%</text>
<rect x="80" y="360" width="1120" height="88" rx="8" fill="{P['sf']}"/><rect x="100" y="378" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="400" font-family="{t}" font-size="18" fill="{P['tx']}">"治愈系"内容停留时长比促销内容高 3.2 倍</text>
<rect x="80" y="460" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><rect x="100" y="478" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="500" font-family="{t}" font-size="18" fill="{P['tx']}">78% 的购买决策来自朋友推荐，而非品牌广告</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">02 / 07</text></g>'''),
    3: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">创意核心</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="548" height="100" rx="8" fill="{P['sf']}"/>
<text x="120" y="200" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">主视觉</text><text x="120" y="228" font-family="{t}" font-size="15" fill="{P['tx']}">漫画风格"春日女孩"，可二创</text>
<rect x="648" y="160" width="548" height="100" rx="8" fill="{P['sf']}"/>
<text x="688" y="200" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">三支短片</text><text x="688" y="228" font-family="{t}" font-size="15" fill="{P['tx']}">通勤、毕业、约会三种春日时刻</text>
<rect x="80" y="276" width="548" height="100" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="120" y="316" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">五位品牌挚友</text><text x="120" y="344" font-family="{t}" font-size="15" fill="{P['tx']}">生活方式 KOL 真实分享</text>
<rect x="648" y="276" width="548" height="100" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="688" y="316" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">十城快闪</text><text x="688" y="344" font-family="{t}" font-size="15" fill="{P['tx']}">门店改造为"春日邮局"</text>
<rect x="80" y="392" width="1116" height="100" rx="8" fill="{P['sf']}" stroke="{P['ac']}" stroke-width="1"/>
<text x="120" y="432" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">UGC 互动</text><text x="120" y="460" font-family="{t}" font-size="15" fill="{P['tx']}">用户上传"我的春日瞬间"赢取奖品</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">03 / 07</text></g>'''),
    4: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">渠道矩阵</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="220" height="470" rx="16" fill="{P['sf']}"/><rect x="80" y="160" width="220" height="6" rx="3" fill="{P['ac']}"/>
<text x="190" y="320" font-family="{t}" font-size="20" font-weight="700" fill="{P['ac']}" text-anchor="middle">小红书</text><text x="190" y="360" font-family="{t}" font-size="14" fill="{P['bd']}" text-anchor="middle">种草+话题</text>
<rect x="316" y="160" width="220" height="470" rx="16" fill="{P['sf']}"/><rect x="316" y="160" width="220" height="6" rx="3" fill="{P['ac']}"/>
<text x="426" y="320" font-family="{t}" font-size="20" font-weight="700" fill="{P['ac']}" text-anchor="middle">抖音</text><text x="426" y="360" font-family="{t}" font-size="14" fill="{P['bd']}" text-anchor="middle">短片+挑战赛</text>
<rect x="552" y="160" width="220" height="470" rx="16" fill="{P['sf']}"/><rect x="552" y="160" width="220" height="6" rx="3" fill="{P['ac']}"/>
<text x="662" y="320" font-family="{t}" font-size="20" font-weight="700" fill="{P['ac']}" text-anchor="middle">微博</text><text x="662" y="360" font-family="{t}" font-size="14" fill="{P['bd']}" text-anchor="middle">话题引爆</text>
<rect x="788" y="160" width="220" height="470" rx="16" fill="{P['sf']}"/><rect x="788" y="160" width="220" height="6" rx="3" fill="{P['ac']}"/>
<text x="898" y="320" font-family="{t}" font-size="20" font-weight="700" fill="{P['ac']}" text-anchor="middle">线下快闪</text><text x="898" y="360" font-family="{t}" font-size="14" fill="{P['bd']}" text-anchor="middle">体验转化</text>
<rect x="1024" y="160" width="220" height="470" rx="16" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/><rect x="1024" y="160" width="220" height="6" rx="3" fill="{P['ac']}"/>
<text x="1134" y="320" font-family="{t}" font-size="20" font-weight="700" fill="{P['ac']}" text-anchor="middle">私域社群</text><text x="1134" y="360" font-family="{t}" font-size="14" fill="{P['bd']}" text-anchor="middle">复购+UGC</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">04 / 07</text></g>'''),
    5: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">投入与效果</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-metric">
<rect x="80" y="170" width="356" height="440" rx="16" fill="{P['sf']}"/><rect x="80" y="170" width="356" height="6" rx="3" fill="{P['ac']}"/>
<text x="258" y="350" font-family="{t}" font-size="48" font-weight="700" fill="{P['ac']}" text-anchor="middle">1800万</text><text x="258" y="390" font-family="{t}" font-size="18" font-weight="600" fill="{P['tx']}" text-anchor="middle">总预算 8 周</text>
<rect x="462" y="170" width="356" height="440" rx="16" fill="{P['sf']}"/><rect x="462" y="170" width="356" height="6" rx="3" fill="{P['ac']}"/>
<text x="640" y="350" font-family="{t}" font-size="48" font-weight="700" fill="{P['ac']}" text-anchor="middle">8亿+</text><text x="640" y="390" font-family="{t}" font-size="18" font-weight="600" fill="{P['tx']}" text-anchor="middle">全网曝光</text>
<rect x="844" y="170" width="356" height="440" rx="16" fill="{P['sf']}"/><rect x="844" y="170" width="356" height="6" rx="3" fill="{P['ac']}"/>
<text x="1022" y="350" font-family="{t}" font-size="48" font-weight="700" fill="{P['ac']}" text-anchor="middle">6.7</text><text x="1022" y="390" font-family="{t}" font-size="18" font-weight="600" fill="{P['tx']}" text-anchor="middle">预期 ROI</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">05 / 07</text></g>'''),
    6: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">效果预测</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="548" height="88" rx="8" fill="{P['sf']}"/>
<text x="120" y="200" font-family="{t}" font-size="20" font-weight="700" fill="{P['ac']}">+240%</text><text x="280" y="200" font-family="{t}" font-size="20" fill="{P['tx']}">品牌搜索量提升</text>
<rect x="648" y="160" width="548" height="88" rx="8" fill="{P['sf']}"/>
<text x="688" y="200" font-family="{t}" font-size="20" font-weight="700" fill="{P['ac']}">60%</text><text x="768" y="200" font-family="{t}" font-size="20" fill="{P['tx']}">新客占比目标</text>
<rect x="80" y="260" width="548" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="120" y="300" font-family="{t}" font-size="20" font-weight="700" fill="{P['ac']}">+18pct</text><text x="280" y="300" font-family="{t}" font-size="20" fill="{P['tx']}">复购率较去年同期</text>
<rect x="648" y="260" width="548" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="688" y="300" font-family="{t}" font-size="20" font-weight="700" fill="{P['ac']}">5万条+</text><text x="848" y="300" font-family="{t}" font-size="20" fill="{P['tx']}">沉淀 UGC 内容</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">06 / 07</text></g>'''),
    7: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-quote">
<text x="640" y="370" font-family="{t}" font-size="30" fill="{P['tx']}" text-anchor="middle">不卖产品，</text>
<text x="640" y="410" font-family="{t}" font-size="30" fill="{P['ac']}" text-anchor="middle">卖一段属于自己的春天。</text>
<rect x="590" y="450" width="100" height="3" fill="{P['ac']}"/>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">07 / 07</text></g>'''),
    }

# ═══════════════════════════════════════════
# Case 8: gov-work-report (Gov Red)
# ═══════════════════════════════════════════
def gov_work_report():
    t = F("gov-red")
    P = {"bg":"#FFFFFF","sf":"#FFF8F6","ac":"#B22222","tx":"#1A1A1A","bd":"#4A4A4A","mt":"#E8D7D3"}
    return {
    1: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-eyebrow"><text x="96" y="180" font-family="{t}" font-size="14" font-weight="600" fill="{P['ac']}" letter-spacing="4">年度工作总结暨工作部署</text></g>
<g id="content-title"><text x="96" y="290" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">2025 年度工作总结</text><text x="96" y="345" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">暨 2026 年工作部署</text></g>
<g id="content-divider"><rect x="96" y="375" width="200" height="4" fill="{P['ac']}"/></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">01 / 06</text></g>'''),
    2: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">主要成绩</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="1120" height="88" rx="8" fill="{P['sf']}"/><rect x="100" y="178" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="200" font-family="{t}" font-size="18" fill="{P['tx']}">GDP 同比增长 6.8%，超额完成年度目标</text>
<rect x="80" y="260" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><rect x="100" y="278" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="300" font-family="{t}" font-size="18" fill="{P['tx']}">规上工业企业新增 142 家，累计 2380 家</text>
<rect x="80" y="360" width="1120" height="88" rx="8" fill="{P['sf']}"/><rect x="100" y="378" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="400" font-family="{t}" font-size="18" fill="{P['tx']}">财政一般公共预算收入 286 亿元，增长 9.4%</text>
<rect x="80" y="460" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><rect x="100" y="478" width="4" height="52" rx="2" fill="{P['ac']}"/>
<text x="124" y="500" font-family="{t}" font-size="18" fill="{P['tx']}">民生投入占财政支出 78%，十大民生实事全部办结</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">02 / 06</text></g>'''),
    3: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">关键数据</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-metric">
<rect x="80" y="170" width="270" height="470" rx="16" fill="{P['sf']}"/><rect x="80" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="215" y="350" font-family="{t}" font-size="40" font-weight="700" fill="{P['ac']}" text-anchor="middle">4.6万户</text><text x="215" y="390" font-family="{t}" font-size="16" font-weight="600" fill="{P['tx']}" text-anchor="middle">新增市场主体</text>
<rect x="370" y="170" width="270" height="470" rx="16" fill="{P['sf']}"/><rect x="370" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="505" y="350" font-family="{t}" font-size="40" font-weight="700" fill="{P['ac']}" text-anchor="middle">1860家</text><text x="505" y="390" font-family="{t}" font-size="16" font-weight="600" fill="{P['tx']}" text-anchor="middle">高新技术企业 +18%</text>
<rect x="660" y="170" width="270" height="470" rx="16" fill="{P['sf']}"/><rect x="660" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="795" y="350" font-family="{t}" font-size="40" font-weight="700" fill="{P['ac']}" text-anchor="middle">3.5%</text><text x="795" y="390" font-family="{t}" font-size="16" font-weight="600" fill="{P['tx']}" text-anchor="middle">研发投入强度</text>
<rect x="950" y="170" width="270" height="470" rx="16" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/><rect x="950" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="1085" y="350" font-family="{t}" font-size="40" font-weight="700" fill="{P['ac']}" text-anchor="middle">4.2%</text><text x="1085" y="390" font-family="{t}" font-size="16" font-weight="600" fill="{P['tx']}" text-anchor="middle">城镇调查失业率</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">03 / 06</text></g>'''),
    4: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="86" font-family="{t}" font-size="38" font-weight="700" fill="{P['tx']}">存在问题 vs 下阶段安排</text><rect x="96" y="100" width="60" height="3" fill="{P['ac']}"/></g>
<g id="content-left"><rect x="80" y="130" width="555" height="530" rx="12" fill="{P['sf']}"/>
<text x="120" y="172" font-family="{t}" font-size="14" font-weight="700" fill="{P['ac']}" letter-spacing="2">存在问题</text>
<line x1="120" y1="192" x2="595" y2="192" stroke="{P['mt']}" stroke-width="1"/>
<text x="120" y="240" font-family="{t}" font-size="16" fill="{P['tx']}">县域之间发展不平衡</text>
<text x="120" y="300" font-family="{t}" font-size="16" fill="{P['tx']}">战略性新兴产业集群尚未形成</text>
<text x="120" y="360" font-family="{t}" font-size="16" fill="{P['tx']}">高层次人才引育仍有差距</text></g>
<g id="content-right"><rect x="648" y="130" width="555" height="530" rx="12" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/>
<text x="688" y="172" font-family="{t}" font-size="14" font-weight="700" fill="{P['ac']}" letter-spacing="2">下阶段安排</text>
<line x1="688" y1="192" x2="1163" y2="192" stroke="{P['ac']}" stroke-width="1" opacity="0.3"/>
<text x="688" y="240" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">抓项目</text><text x="688" y="268" font-family="{t}" font-size="14" fill="{P['tx']}">全年开工亿元以上项目 320 个</text>
<text x="688" y="320" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">育产业</text><text x="688" y="348" font-family="{t}" font-size="14" fill="{P['tx']}">培育新材料、生物医药、AI 三大集群</text>
<text x="688" y="400" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">惠民生</text><text x="688" y="428" font-family="{t}" font-size="14" fill="{P['tx']}">十大民生实事再升级，重点解决“一老一小”</text></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">04 / 06</text></g>'''),
    5: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">经验做法</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="1120" height="88" rx="8" fill="{P['sf']}"/><circle cx="124" cy="204" r="5" fill="{P['ac']}"/>
<text x="148" y="210" font-family="{t}" font-size="18" fill="{P['tx']}">坚持党建引领，锤炼一支能打硬仗的干部队伍</text>
<rect x="80" y="260" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><circle cx="124" cy="304" r="5" fill="{P['ac']}"/>
<text x="148" y="310" font-family="{t}" font-size="18" fill="{P['tx']}">深化"放管服"改革，审批事项压减 42%</text>
<rect x="80" y="360" width="1120" height="88" rx="8" fill="{P['sf']}"/><circle cx="124" cy="404" r="5" fill="{P['ac']}"/>
<text x="148" y="410" font-family="{t}" font-size="18" fill="{P['tx']}">数字技术赋能基层治理，网格事件办结率 98.6%</text>
<rect x="80" y="460" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/><circle cx="124" cy="504" r="5" fill="{P['ac']}"/>
<text x="148" y="510" font-family="{t}" font-size="18" fill="{P['tx']}">医保+教育+养老三张网越织越密</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">05 / 06</text></g>'''),
    6: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title">
<text x="640" y="320" font-family="{t}" font-size="72" font-weight="700" fill="{P['tx']}" text-anchor="middle">Thank You</text>
<rect x="490" y="348" width="300" height="4" fill="{P['ac']}"/>
<text x="640" y="410" font-family="{t}" font-size="22" fill="{P['bd']}" text-anchor="middle">稳中求进 · 服务为民</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">06 / 06</text></g>'''),
    }

# ═══════════════════════════════════════════
# Case 9: tech-conf-talk (Ocean Deep)
# ═══════════════════════════════════════════
def tech_conf_talk():
    t = F("ocean-deep")
    P = {"bg":"#0A1628","sf":"#0F2540","ac":"#0EA5E9","tx":"#F0F9FF","bd":"#7DD3FC","ft":"#38BDF8","mt":"#1E3A5F"}
    return {
    1: svg(f'''<defs><linearGradient id="tbg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#0A1628"/><stop offset="100%" stop-color="#0F2540"/></linearGradient></defs>
<g id="background"><rect x="0" y="0" width="1280" height="720" fill="url(#tbg)"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-eyebrow"><text x="96" y="160" font-family="{t}" font-size="16" font-weight="600" fill="{P['ac']}" letter-spacing="4">QCON 2026 · 技术大会</text></g>
<g id="content-title"><text x="96" y="310" font-family="{t}" font-size="52" font-weight="700" fill="{P['tx']}">大型推理服务的</text><text x="96" y="375" font-family="{t}" font-size="52" font-weight="700" fill="{P['ac']}">成本之战</text></g>
<g id="content-divider"><rect x="96" y="405" width="200" height="4" fill="{P['ac']}"/></g>
<g id="content-subtitle"><text x="96" y="460" font-family="{t}" font-size="20" fill="{P['bd']}">把每一次推理调用，从 $0.012 降到 $0.0006 的两年</text></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">01 / 06</text></g>'''),
    2: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">核心数据</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-metric">
<rect x="80" y="170" width="270" height="470" rx="16" fill="{P['sf']}"/><rect x="80" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="215" y="340" font-family="{t}" font-size="56" font-weight="700" fill="{P['ac']}" text-anchor="middle">95%</text><text x="215" y="380" font-family="{t}" font-size="16" font-weight="600" fill="{P['tx']}" text-anchor="middle">推理成本下降</text>
<rect x="370" y="170" width="270" height="470" rx="16" fill="{P['sf']}"/><rect x="370" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="505" y="340" font-family="{t}" font-size="56" font-weight="700" fill="{P['ac']}" text-anchor="middle">71%</text><text x="505" y="380" font-family="{t}" font-size="16" font-weight="600" fill="{P['tx']}" text-anchor="middle">GPU 利用率</text>
<rect x="660" y="170" width="270" height="470" rx="16" fill="{P['sf']}"/><rect x="660" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="795" y="340" font-family="{t}" font-size="56" font-weight="700" fill="{P['ac']}" text-anchor="middle">380ms</text><text x="795" y="380" font-family="{t}" font-size="16" font-weight="600" fill="{P['tx']}" text-anchor="middle">P99 延迟</text>
<rect x="950" y="170" width="270" height="470" rx="16" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/><rect x="950" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="1085" y="340" font-family="{t}" font-size="56" font-weight="700" fill="{P['ac']}" text-anchor="middle">3s</text><text x="1085" y="380" font-family="{t}" font-size="16" font-weight="600" fill="{P['tx']}" text-anchor="middle">模型加载</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">02 / 06</text></g>'''),
    3: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">我们的解法</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="1120" height="88" rx="8" fill="{P['sf']}"/>
<text x="120" y="200" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">1. 统一推理网关</text><text x="400" y="200" font-family="{t}" font-size="18" fill="{P['tx']}">KV-Cache 跨请求复用，命中率 64%</text>
<rect x="80" y="260" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['mt']}" stroke-width="1"/>
<text x="120" y="300" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">2. 混合精度调度</text><text x="400" y="300" font-family="{t}" font-size="18" fill="{P['tx']}">fp16/int8/int4 按 SLA 智能切换</text>
<rect x="80" y="360" width="1120" height="88" rx="8" fill="{P['sf']}"/>
<text x="120" y="400" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">3. 推理优化器</text><text x="400" y="400" font-family="{t}" font-size="18" fill="{P['tx']}">TVM + TensorRT 双后端自动选优</text>
<rect x="80" y="460" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['mt']}" stroke-width="1"/>
<text x="120" y="500" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">4. Spot+预留混合调度</text><text x="400" y="500" font-family="{t}" font-size="18" fill="{P['tx']}">成本最优容量曲线</text>
<rect x="80" y="560" width="1120" height="88" rx="8" fill="{P['sf']}"/>
<text x="120" y="600" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">5. 流量预测</text><text x="400" y="600" font-family="{t}" font-size="18" fill="{P['tx']}">7 日滚动预测，误差 8%</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">03 / 06</text></g>'''),
    4: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="86" font-family="{t}" font-size="38" font-weight="700" fill="{P['tx']}">我们 vs 其他方案</text><rect x="96" y="100" width="60" height="3" fill="{P['ac']}"/></g>
<g id="content-left"><rect x="80" y="130" width="555" height="530" rx="12" fill="{P['sf']}"/>
<text x="120" y="172" font-family="{t}" font-size="14" font-weight="700" fill="{P['ac']}" letter-spacing="2">其他方案</text>
<line x1="120" y1="192" x2="595" y2="192" stroke="{P['mt']}" stroke-width="1"/>
<text x="120" y="240" font-family="{t}" font-size="16" fill="{P['tx']}">自建 vLLM：$0.0042/token</text><text x="120" y="268" font-family="{t}" font-size="14" fill="{P['bd']}">无弹性</text>
<text x="120" y="340" font-family="{t}" font-size="16" fill="{P['tx']}">云厂商托管：$0.0028/token</text><text x="120" y="368" font-family="{t}" font-size="14" fill="{P['bd']}">锁定单一厂商</text></g>
<g id="content-right"><rect x="648" y="130" width="555" height="530" rx="12" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/>
<text x="688" y="172" font-family="{t}" font-size="14" font-weight="700" fill="{P['ac']}" letter-spacing="2">我们的混合架构</text>
<line x1="688" y1="192" x2="1163" y2="192" stroke="{P['ac']}" stroke-width="1" opacity="0.3"/>
<text x="688" y="240" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">$0.0006/token，跨 3 朵云</text>
<text x="688" y="268" font-family="{t}" font-size="14" fill="{P['tx']}">加上自研编译器，进一步降低 18%</text>
<text x="688" y="370" font-family="{t}" font-size="48" font-weight="700" fill="{P['ac']}">7x 成本优势</text></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">04 / 06</text></g>'''),
    5: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-quote">
<text x="640" y="260" font-family="{t}" font-size="180" font-weight="700" fill="{P['ac']}" fill-opacity="0.12" text-anchor="middle">"</text>
<text x="640" y="370" font-family="{t}" font-size="24" fill="{P['tx']}" text-anchor="middle">真正省钱的不是更便宜的硬件，</text>
<text x="640" y="410" font-family="{t}" font-size="24" fill="{P['ac']}" text-anchor="middle">而是把每一比特带宽与显存都用满的工程纪律。</text>
<rect x="590" y="450" width="100" height="3" fill="{P['ac']}"/>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">05 / 06</text></g>'''),
    6: svg(f'''<defs><radialGradient id="tcg" cx="50%" cy="50%" r="70%"><stop offset="0%" stop-color="#0F2540"/><stop offset="100%" stop-color="#0A1628"/></radialGradient></defs>
<g id="background"><rect x="0" y="0" width="1280" height="720" fill="url(#tcg)"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title">
<text x="640" y="320" font-family="{t}" font-size="72" font-weight="700" fill="{P['tx']}" text-anchor="middle">Thank You</text>
<rect x="490" y="348" width="300" height="4" fill="{P['ac']}"/>
<text x="640" y="410" font-family="{t}" font-size="22" fill="{P['bd']}" text-anchor="middle">QCon 2026 · 欢迎交流</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">06 / 06</text></g>'''),
    }

# ═══════════════════════════════════════════
# Case 10: trn-onboarding (Sage Calm)
# ═══════════════════════════════════════════
def trn_onboarding():
    t = F("sage-calm")
    P = {"bg":"#F5F9F7","sf":"#E8F0ED","ac":"#69A297","tx":"#1B4332","bd":"#52796F","mt":"#A7C4BC"}
    return {
    1: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-quote">
<text x="640" y="370" font-family="{t}" font-size="26" fill="{P['tx']}" text-anchor="middle">从今天起，你不只是来上班，</text>
<text x="640" y="410" font-family="{t}" font-size="26" fill="{P['ac']}" text-anchor="middle">而是和我们共同书写一段值得回忆的旅程。</text>
<rect x="590" y="450" width="100" height="3" fill="{P['ac']}"/>
<text x="640" y="500" font-family="{t}" font-size="16" fill="{P['bd']}" text-anchor="middle">欢迎加入</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">01 / 06</text></g>'''),
    2: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">公司概览</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-metric">
<rect x="80" y="170" width="270" height="470" rx="16" fill="{P['sf']}"/><rect x="80" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="215" y="340" font-family="{t}" font-size="44" font-weight="700" fill="{P['ac']}" text-anchor="middle">1860</text><text x="215" y="380" font-family="{t}" font-size="16" font-weight="600" fill="{P['tx']}" text-anchor="middle">全球员工</text>
<rect x="370" y="170" width="270" height="470" rx="16" fill="{P['sf']}"/><rect x="370" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="505" y="340" font-family="{t}" font-size="44" font-weight="700" fill="{P['ac']}" text-anchor="middle">12000+</text><text x="505" y="380" font-family="{t}" font-size="16" font-weight="600" fill="{P['tx']}" text-anchor="middle">服务客户</text>
<rect x="660" y="170" width="270" height="470" rx="16" fill="{P['sf']}"/><rect x="660" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="795" y="340" font-family="{t}" font-size="44" font-weight="700" fill="{P['ac']}" text-anchor="middle">36</text><text x="795" y="380" font-family="{t}" font-size="16" font-weight="600" fill="{P['tx']}" text-anchor="middle">覆盖行业</text>
<rect x="950" y="170" width="270" height="470" rx="16" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/><rect x="950" y="170" width="270" height="6" rx="3" fill="{P['ac']}"/>
<text x="1085" y="340" font-family="{t}" font-size="32" font-weight="700" fill="{P['ac']}" text-anchor="middle">最佳雇主</text><text x="1085" y="380" font-family="{t}" font-size="16" font-weight="600" fill="{P['tx']}" text-anchor="middle">连续四年 100 强</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">02 / 06</text></g>'''),
    3: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="100" font-family="{t}" font-size="44" font-weight="700" fill="{P['tx']}">团队结构</text><rect x="96" y="118" width="80" height="4" fill="{P['ac']}"/></g>
<g id="content-body">
<rect x="80" y="160" width="1120" height="88" rx="8" fill="{P['sf']}"/>
<text x="120" y="200" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">产品研发线</text><text x="400" y="200" font-family="{t}" font-size="18" fill="{P['tx']}">负责核心产品与技术中台</text>
<rect x="80" y="260" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="120" y="300" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">市场销售线</text><text x="400" y="300" font-family="{t}" font-size="18" fill="{P['tx']}">负责客户成功与市场推广</text>
<rect x="80" y="360" width="1120" height="88" rx="8" fill="{P['sf']}"/>
<text x="120" y="400" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">客户成功线</text><text x="400" y="400" font-family="{t}" font-size="18" fill="{P['tx']}">服务全球客户的实施与支持</text>
<rect x="80" y="460" width="1120" height="88" rx="8" fill="{P['bg']}" stroke="{P['sf']}" stroke-width="1"/>
<text x="120" y="500" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">职能支持线</text><text x="400" y="500" font-family="{t}" font-size="18" fill="{P['tx']}">HR、财务、法务、IT 等支撑团队</text>
<rect x="80" y="560" width="1120" height="88" rx="8" fill="{P['sf']}"/>
<text x="120" y="600" font-family="{t}" font-size="18" font-weight="700" fill="{P['ac']}">战略与新业务</text><text x="400" y="600" font-family="{t}" font-size="18" fill="{P['tx']}">孵化下一条增长曲线</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">03 / 06</text></g>'''),
    4: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title"><text x="96" y="86" font-family="{t}" font-size="38" font-weight="700" fill="{P['tx']}">工作方式 vs 常用工具</text><rect x="96" y="100" width="60" height="3" fill="{P['ac']}"/></g>
<g id="content-left"><rect x="80" y="130" width="555" height="530" rx="12" fill="{P['sf']}"/>
<text x="120" y="172" font-family="{t}" font-size="14" font-weight="700" fill="{P['ac']}" letter-spacing="2">工作方式</text>
<line x1="120" y1="192" x2="595" y2="192" stroke="{P['mt']}" stroke-width="1"/>
<text x="120" y="240" font-family="{t}" font-size="16" fill="{P['tx']}">决策：数据驱动，允许试错，快速复盘</text>
<text x="120" y="300" font-family="{t}" font-size="16" fill="{P['tx']}">协作：异步优先，周会精简，文档先行</text>
<text x="120" y="360" font-family="{t}" font-size="16" fill="{P['tx']}">反馈：双周一对一，开放且具体</text>
<text x="120" y="420" font-family="{t}" font-size="16" fill="{P['tx']}">成长：每年 1 万元学习预算</text></g>
<g id="content-right"><rect x="648" y="130" width="555" height="530" rx="12" fill="{P['bg']}" stroke="{P['ac']}" stroke-width="2"/>
<text x="688" y="172" font-family="{t}" font-size="14" font-weight="700" fill="{P['ac']}" letter-spacing="2">常用工具</text>
<line x1="688" y1="192" x2="1163" y2="192" stroke="{P['ac']}" stroke-width="1" opacity="0.3"/>
<text x="688" y="240" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">飞书</text><text x="768" y="240" font-family="{t}" font-size="16" fill="{P['tx']}">即时沟通+在线文档+视频会议</text>
<text x="688" y="300" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">Jira</text><text x="768" y="300" font-family="{t}" font-size="16" fill="{P['tx']}">项目跟踪与版本管理</text>
<text x="688" y="360" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">GitHub</text><text x="768" y="360" font-family="{t}" font-size="16" fill="{P['tx']}">代码协作与 CI/CD</text>
<text x="688" y="420" font-family="{t}" font-size="16" font-weight="700" fill="{P['ac']}">Notion</text><text x="768" y="420" font-family="{t}" font-size="16" fill="{P['tx']}">知识库与个人 Wiki</text></g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">04 / 06</text></g>'''),
    5: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-quote">
<text x="640" y="370" font-family="{t}" font-size="26" fill="{P['tx']}" text-anchor="middle">入职导师 · HR 伙伴 · 部门负责人</text>
<text x="640" y="410" font-family="{t}" font-size="26" fill="{P['ac']}" text-anchor="middle">任何困惑，直接说出来，我们都在。</text>
<rect x="590" y="450" width="100" height="3" fill="{P['ac']}"/>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">05 / 06</text></g>'''),
    6: svg(f'''<g id="background"><rect x="0" y="0" width="1280" height="720" fill="{P['bg']}"/></g>
<g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{P['ac']}"/></g>
<g id="content-title">
<text x="640" y="320" font-family="{t}" font-size="72" font-weight="700" fill="{P['tx']}" text-anchor="middle">欢迎加入</text>
<rect x="490" y="348" width="300" height="4" fill="{P['ac']}"/>
<text x="640" y="410" font-family="{t}" font-size="22" fill="{P['bd']}" text-anchor="middle">让创造更简单</text>
</g>
<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="{P['sf']}"/><text x="1184" y="708" font-family="{t}" font-size="12" fill="{P['mt']}" text-anchor="end">06 / 06</text></g>'''),
    }


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
