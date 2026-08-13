# Image Layout Dimension Calculator

> **Precise pixel coordinates for image placement patterns on 1280×720 canvas.**
> Use this reference when calculating image positions for each layout pattern.

---

## Canvas Constants

```
CANVAS_W = 1280
CANVAS_H = 720
SAFE_X_MIN = 80
SAFE_X_MAX = 1200
SAFE_Y_MIN = 80
SAFE_Y_MAX = 680
FOOTER_Y = 688
STRIPE_W = 6
CONTENT_W = SAFE_X_MAX - SAFE_X_MIN  # 1120
CONTENT_H = SAFE_Y_MAX - SAFE_Y_MIN  # 600
```

---

## Container Layout Coordinates

### full-bleed / full-bleed-overlay
```
image: x=0 y=0 width=1280 height=720
overlay: x=0 y=0 width=1280 height=720 fill-opacity=0.5
```

### left-half / right-half
```
left-half:  image x=0   y=0 width=640 height=720
right-half: image x=640 y=0 width=640 height=720
content area: opposite half, padded 80px
```

### left-third / right-third
```
left-third:  image x=0   y=0 width=427 height=720
right-third: image x=853 y=0 width=427 height=720
content area: remaining 67%, padded 80px
```

### top-banner / bottom-banner
```
top-banner:    image x=0 y=0   width=1280 height=360
bottom-banner: image x=0 y=360 width=1280 height=360
content area: opposite half, padded 80px
```

### center-hero
```
image: x=390 y=120 width=500 height=400 (centered, adjust to aspect)
title: above image, y=100
caption: below image, y=560
```

### corner-accent (all variants)
```
tl: x=80  y=80  width=200 height=200
tr: x=1000 y=80  width=200 height=200
br: x=1000 y=440 width=200 height=200
```

### inset-card
```
card: x=80 y=120 width=520 height=520 rx=16
image padding: 16px inside card
image: x=96 y=136 width=488 height=360
caption: x=96 y=516 (below image inside card)
```

### floating-circle
```
clip: <circle cx="240" cy="360" r="160" />
image: x=80 y=200 width=320 height=320
(place circle clip-path in defs)
```

### diagonal-split
```
clip-path polygon: "0,0 1280,0 1280,720 640,720"
image fills full canvas, clipped to right triangle
content on left (unclipped) side
```

---

## Multi-Image Grid Coordinates

### grid-2x1
```
img1: x=80  y=120 width=536 height=520
img2: x=664 y=120 width=536 height=520
gap: 48px between images
```

### grid-1x2
```
img1: x=80  y=80  width=1120 height=272
img2: x=80  y=376 width=1120 height=272
gap: 24px between images
```

### grid-2x2
```
img1: x=80  y=120 width=536 height=248
img2: x=664 y=120 width=536 height=248
img3: x=80  y=392 width=536 height=248
img4: x=664 y=392 width=536 height=248
gap: 48px h, 24px v
```

### grid-3x1
```
img1: x=80  y=120 width=352 height=520
img2: x=464 y=120 width=352 height=520
img3: x=848 y=120 width=352 height=520
gap: 32px between images
```

### grid-1-2 (1 large + 2 small)
```
large: x=80  y=120 width=680 height=520
small1: x=792 y=120 width=408 height=248
small2: x=792 y=392 width=408 height=248
gap: 32px h, 24px v
```

---

## Overlay Dimension Templates

### gradient-fade-left
```
<linearGradient id="fade-l" x1="0%" y1="0%" x2="60%" y2="0%">
  <stop offset="0%" stop-color="{background}" />
  <stop offset="100%" stop-color="{background}" stop-opacity="0" />
</linearGradient>
rect: x=0 y=0 width=1280 height=720 fill="url(#fade-l)"
```

### gradient-fade-right
```
<linearGradient id="fade-r" x1="40%" y1="0%" x2="100%" y2="0%">
  <stop offset="0%" stop-color="{background}" stop-opacity="0" />
  <stop offset="100%" stop-color="{background}" />
</linearGradient>
```

### gradient-fade-bottom
```
<linearGradient id="fade-b" x1="0%" y1="40%" x2="0%" y2="100%">
  <stop offset="0%" stop-color="{background}" stop-opacity="0" />
  <stop offset="100%" stop-color="{background}" />
</linearGradient>
```

### frosted-card
```
card: rx=16 fill="{surface}" fill-opacity="0.85"
blur: feGaussianBlur stdDeviation="4" on background behind card
card position: centered or rule-of-thirds placement
```

---

## Aspect Ratio Reference

| Target | Width | Height | Ratio |
|--------|-------|--------|-------|
| 16:9 slide | 1280 | 720 | 1.78 |
| Square thumbnail | 1:1 | any | 1.00 |
| Portrait photo | 3:4 | e.g. 300×400 | 0.75 |
| Landscape photo | 4:3 | e.g. 400×300 | 1.33 |
| Widescreen photo | 16:9 | e.g. 480×270 | 1.78 |
| Ultra-wide | 21:9 | e.g. 560×240 | 2.33 |

Always use `preserveAspectRatio="xMidYMid slice"` for background/cover images.
Use `preserveAspectRatio="xMidYMid meet"` for contained/gallery images.
