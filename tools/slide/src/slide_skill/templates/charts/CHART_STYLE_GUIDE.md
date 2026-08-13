# Chart & Visualization Style Guide

> **Design standards for all chart and visualization template SVGs.**
> Apply these patterns when creating any data visualization slide.

---

## Card Container Pattern

All chart elements should be placed inside **card containers** for visual consistency:

```xml
<!-- Standard card container -->
<rect x="80" y="120" width="1120" height="540" rx="16"
      fill="{surface}" stroke="{border}" stroke-width="1" />
```

**Card variants:**
- **Default:** `fill="{surface}"` — standard data card
- **Elevated:** Add `filter="url(#shadow)"` — floating card with depth
- **Outlined:** `fill="none" stroke="{border}" stroke-width="2"` — minimal
- **Accent:** `fill="{accent_tint}"` — highlighted/active card

---

## Data Visualization Rules

### Color Usage
1. **Primary series:** `{accent}` — first/main data series
2. **Secondary series:** `{secondary_accent}` — comparison data
3. **Tertiary+:** Derive from accent at 60%, 40%, 20% opacity
4. **Baseline/grid:** `{border}` at 30% opacity
5. **Labels:** `{text_secondary}` for axis labels, `{text}` for data values
6. **Background grid:** `{muted}` at 15% opacity

### Typography
- **Chart title:** 28–32px, `{text}`, font-weight 700
- **Axis labels:** 14–16px, `{text_secondary}`, font-weight 400
- **Data labels:** 12–14px, `{text_tertiary}`, font-weight 400
- **Metric values:** 48–72px, `{accent}`, font-weight 700
- **Metric labels:** 16–18px, `{text_secondary}`, font-weight 400

### Grid & Axis
- Horizontal grid lines: `stroke="{border}" stroke-opacity="0.3" stroke-width="1"`
- Vertical grid lines: Only when needed (grouped bar, scatter)
- Axis lines: `stroke="{text_tertiary}" stroke-width="1.5"`
- Zero line: `stroke="{text_secondary}" stroke-width="2"` (when relevant)

---

## Plot Area Convention

Every chart template uses a **plot-area marker** for coordinate calibration:

```xml
<!-- Invisible marker for plot area boundaries -->
<rect id="plot-area" x="160" y="160" width="960" height="400"
      fill="none" stroke="none" data-role="plot-area" />
```

The AI reads these coordinates to place data points correctly:
- **x-origin:** left edge of plot area
- **y-origin:** bottom edge of plot area (SVG y inverted)
- **x-scale:** (data-max - data-min) mapped to plot width
- **y-scale:** (data-max - data-min) mapped to plot height

---

## Template Index

| Category | Templates | Count |
|----------|-----------|-------|
| Timeline | horizontal, vertical | 2 |
| KPI | cards, dashboard | 2 |
| Bar | vertical, horizontal, grouped | 3 |
| Line/Area | line_chart, area_chart | 2 |
| Circular | pie_chart, donut_chart | 2 |
| Table | basic_table, comparison_table | 2 |
| Process | process_flow, chevron_process | 2 |
| Matrix | matrix_2x2, quadrant_text_bullets | 2 |
| **Total** | | **17** |

---

## Animation Readiness

Templates should group elements in a way that supports later animation:
- Each data point/bar in its own `<g>` with sequential IDs
- Legend items in separate groups
- Title and labels in dedicated groups
- Use `data-anim-order` attribute to suggest build order
