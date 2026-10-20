# image-to-svg-trace

Convert a raster image into a faithful SVG, then verify the result by rendering and pixel-diffing. Use when someone hands you a picture and says "reproduce this in SVG" or "make me a vector version of this".

## When to use

- "Turn this image into SVG / 把这张图转成矢量图"
- "I need a version that can scale without blurring"
- Bitmap logo, illustration, poster background → editable paths

## When NOT to use

- They want a **re-creation in the same style**, not a trace → this only copies what exists
- Pure black-and-white line art / icons → centreline tracing gives better results
- Screenshots containing text → re-type the text instead of tracing blobs
- Illustrator-grade smooth curves are required → see "Upgrade path" below

## Why this implementation

`vtracer` segfaults on first call on some wheels (verified: 0.6.15 and 0.6.11, even on 60×107 input). `potracer` needs numpy and often fails to import. This script is Pillow-only: no numpy, no native binaries, ~5 s for a 675 px wide illustration.

## Quick start

```bash
python3 scripts/img2svg.py input.jpg output.svg
# fidelity-first starting point for illustrations
python3 scripts/img2svg.py input.jpg output.svg \
  --width 675 --colors 48 --eps 0.45 --min-area 20 --saturate 1.25 --median 3
```

Prints one line: `done output.svg  <bytes>  <layers>  WIDTHxHEIGHT`.

## Tuning

| Flag | Default | Effect | Raise | Lower |
|---|---|---|---|---|
| `--width` | 675 | canvas width | more detail, bigger file | faster, coarser |
| `--colors` | 48 | palette size | closer to source, more banding | flatter, may lose highlights |
| `--eps` | 0.45 | polyline simplification (px) | fewer nodes, harder edges | hugs pixels, bigger file |
| `--min-area` | 20 | drop regions below N px² | cleaner, loses small detail | keeps detail, may look noisy |
| `--median` | 3 | pre-blur, kills JPEG noise | cleaner, softer | keeps grain |
| `--saturate` | 1.25 | saturation compensation | punchier | duller |
| `--smooth` | 0 | 3×3 mode filter after quantising | clean, eats thin lines and eye highlights | keeps detail |

Starting points: anime `40~48 / 0.4~0.5 / 15~25`; photos `64 / 0.35`; flat fills `16~24 / 0.8 / 60 --smooth 1`.

## Verification loop — do not skip

1. Trace.
2. `python3 scripts/render_check.py out.svg --ref input.jpg --out render.png --compare compare.png`
   - renders through headless Chrome at matched size, returns `mae` (mean absolute per-pixel error, 0–255)
3. Sweep parameters, keep the lowest MAE that still looks clean at 100 %.
4. Show the user the side-by-side sheet, not adjectives.

Calibration: illustration with defaults ≈ 7.0 (excellent); hand-authored SVG coordinates on the same illustration ≈ 76.8 (unusable). If your MAE is above ~15, something is set wrong — usually JPEG noise (`--median 3`) or too few colours.

## Limits to state up front

- Output is **polylines, not curves** — polygon edges show above ~4× zoom
- Highlights, gradients, soft shading become flat blocks; banding is inevitable
- Files are large: 675 px / 48 colours ≈ 2.5–3.5 MB
- It is a trace of colour regions, not an artist-authored structure — hand editing is awkward
- The output inherits the source image's rights and restrictions

## Upgrade path

1. **Curve fitting**: Catmull-Rom through each path's points → cubic Bézier (`C`), smoother lines and a smaller file
2. **Layered tracing**: large regions at a loose `--eps`, fine detail at a tight one
3. **Subject isolation**: mask out the background first to avoid tracing noise

## Pitfalls

- JPEG noise without `--median 3` produces speckle everywhere
- `--smooth 1` destroys pupils, eyelashes, and hair highlights — avoid on portraits
- Fix window size and `--force-device-scale-factor=1` during comparison, or MAE is meaningless
- Pillow 14 deprecation warning about `getdata` is harmless
- Never hand-place coordinates to reproduce an illustration — run this first
