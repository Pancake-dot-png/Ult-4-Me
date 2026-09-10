# Template Guide

## Capturing new templates

1. Play Overwatch 2 in **borderless windowed** mode
2. Trigger the event you want to capture (get healed, get boosted, etc.)
3. Screenshot at the exact moment the HUD indicator appears
4. Crop tightly to just the icon/indicator — no extra background
5. Save as PNG in this folder

## Resolution rules

All templates must be at **1920x1080 base resolution**.

If your monitor is higher res (e.g. 2560x1440), you MUST downscale:

```python
import cv2
scale = YOUR_MONITOR_HEIGHT / 1080  # e.g. 1440/1080 = 1.333
img = cv2.imread('your_template.png')
h, w = img.shape[:2]
img = cv2.resize(img, (int(w / scale), int(h / scale)))
cv2.imwrite('your_template.png', img)
```

Common scale factors:
- 1440p: divide by 1.333
- 1600p: divide by 1.481
- 2160p (4K): divide by 2.0

## Typical template sizes

For reference, correctly-sized templates are roughly:
- Receive icons (heal/boost/status): ~30-50px wide, ~50-75px tall
- Popup text (elimination/assist): ~180-200px wide, ~25px tall
- Prompt text (CC effects): ~120-180px wide, ~40-50px tall
- Give icons (mercy beam, zen orb): ~40-50px wide and tall

If your template is significantly larger than these, it probably needs downscaling.

## Transparent templates (alpha mask)

Save your PNG with transparency to tell the matcher which pixels matter:
- **Opaque pixels** = matched against the screen
- **Transparent pixels** = ignored (background, variable areas)

Use any image editor (Photoshop, GIMP, Paint.NET) to erase the background
or variable parts of your template. The app automatically detects the alpha
channel and switches to masked matching.

Notes:
- Masked templates skip filters (the mask handles background exclusion)
- Thresholds for masked templates are different — `TM_CCORR_NORMED` is used
  instead of `TM_CCOEFF_NORMED`. Start around 0.9+ and adjust with the debug panel.
- Works with any existing template — just add transparency and re-save as PNG

## Filter types

Templates are matched against the screen using filters set in config:
- **No filter** — raw pixel matching. Good when colors are stable.
- **`edge`** — Canny edge detection. Strips color, matches shapes only. Best for receive icons that change color between OW2 patches.
- **`popup`** — brightness-based filter for kill feed text.
- **`prompt`** — HSV + edge filter for center-screen CC prompts.

Receive Heal and Receive Status Effect templates use the `edge` filter by default.

## Testing

1. Launch the app, start vision
2. Open the Debug panel (button in Controls section)
3. Watch the confidence value for your template
4. Use the threshold slider to find where it reliably triggers without false positives
5. Typical good thresholds: 0.45-0.6 for edge-filtered, 0.7-0.85 for raw matching
