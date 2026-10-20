# image-to-svg-trace

**English** ｜ [中文](README.md)

**Turn any bitmap into a real SVG — no numpy, no vtracer, one file, ~5 seconds.**

---

## What it is

A dependency-free raster→vector tracer written with nothing but Pillow.

Pipeline: preprocess → palette quantisation → pixel boundary following (crack following) → polyline simplification (Douglas–Peucker) → SVG `<path>` output.

Uses `fill-rule="evenodd"` and stacks colour layers by area, so the result is a single self-contained SVG that scales cleanly and can be edited in any vector editor.

![demo](examples/demo-compare.png)

*Left: input PNG. Right: re-rendered from the SVG. This pair scores MAE **1.83** (mean absolute per-pixel error, 0–255).*

## Why not vtracer / potrace / autotrace?

Measured on WSL2 + Python 3.14, October 2026:

| Tool | Result |
|---|---|
| `vtracer` 0.6.15 / 0.6.11 | imports fine, then **segfaults on the first call** — even on a 60×107 image. Wheel/environment mismatch. |
| `potracer` | `ModuleNotFoundError: No module named 'potrace'` after install; also drags in numpy (16.7 MB) |
| `potrace` / `autotrace` binaries | not present, and not packaged for this distro |

So the tracer here is ~200 lines of plain Python + Pillow. It needs nothing you don't already have, and it runs anywhere Pillow runs.

## Install

```bash
pip install pillow
git clone https://github.com/SSSY418/image-to-svg-trace.git
cd image-to-svg-trace
```

No other dependencies. Python 3.9+.

## Usage

```bash
# defaults: width 675, 48 colours, faithful
python3 scripts/img2svg.py input.jpg output.svg

# fidelity first (recommended starting point for illustrations)
python3 scripts/img2svg.py input.jpg output.svg \
  --width 675 --colors 48 --eps 0.45 --min-area 20 \
  --saturate 1.25 --median 3

# small file, clean flat colour
python3 scripts/img2svg.py input.jpg output.svg \
  --colors 20 --eps 0.8 --min-area 60 --smooth 1
```

Output line:

```
done output.svg  2882660 bytes  48 layers  675x1204
```

| Flag | Default | What it does | Raise it | Lower it |
|---|---|---|---|---|
| `--width` | 675 | output canvas width (height follows aspect) | more detail, bigger file | faster, coarser |
| `--colors` | 48 | palette size (median-cut, no dither) | closer to source, more banding | flatter, may lose highlights |
| `--eps` | 0.45 | Douglas–Peucker tolerance in px | fewer nodes, harder edges | hugs the pixels, bigger file |
| `--min-area` | 20 | drop regions smaller than this many px² | cleaner, loses small detail | keeps detail, may look noisy |
| `--median` | 3 | pre-blur to kill JPEG noise | cleaner, softer | keeps grain |
| `--saturate` | 1.25 | saturation compensation (quantising greys things out) | punchier | duller |
| `--smooth` | 0 | 3×3 mode filter after quantising | much cleaner, eats thin lines and eye highlights | keeps detail |
| `--contrast` | 1.0 | contrast compensation | punchier | flatter |
| `--bg` | `#ffffff` | background fill behind everything | | |

Rules of thumb:

- **Anime / flat illustrations**: `--colors 40~48 --eps 0.4~0.5 --min-area 15~25 --saturate 1.25`
- **Photos**: `--colors 64 --eps 0.35 --median 3`
- **Icons / line art**: skip this tool, use centreline tracing instead
- **Big flat fills, small file**: `--colors 16~24 --eps 0.8 --min-area 60 --smooth 1`

## Where it fits in an LLM image pipeline

Image models hand you a raster: a 1024² PNG that pixelates the moment you scale it, and that you cannot recolour or re-edit as shapes. This tracer is the stage **after** generation — feed the model's output in, get a self-contained SVG out in about five seconds on CPU, with no GPU, no network and no model weights.

Two concrete uses: **batch post-processing** (run a whole generation batch through it, keep the vector version for print, icons and UI assets) and **reproducible assets** (an SVG diffs cleanly in git and renders identically everywhere; a sampled PNG does neither).

Caveat: it vectorises whatever the model produced, it does not fix it — and 40–48 colours flattens gradients, see the limits below.

## Verify it looks right

Tracing without checking is guessing. `scripts/render_check.py` renders the SVG through headless Chrome and reports the pixel difference against the source, plus an optional side-by-side image.

```bash
python3 scripts/render_check.py examples/demo-output.svg \
  --ref examples/demo-input.png \
  --out examples/demo-render.png \
  --compare examples/demo-compare.png
```

```json
{
  "svg": "examples/demo-output.svg",
  "size": [560.0, 720.0],
  "chrome": "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
  "png": "examples/demo-render.png",
  "px": [560, 720],
  "mae": 1.83,
  "compare": "examples/demo-compare.png"
}
```

`mae` = mean absolute error, 0–255, averaged over RGB. Lower is closer.

Reference numbers:

| Approach | MAE |
|---|---|
| This tracer, default settings on an illustration | **7.0** |
| This tracer on a flat vector-ish demo | **1.8** |
| Hand-authoring SVG coordinates to "reproduce" an illustration | **76.8** |

That last row is the reason this tool exists: four hand-drawn attempts at reproducing an anime illustration landed at 76.8, then the tracer landed at 7.0 on the first try. Don't hand-place coordinates to copy an image.

## Output characteristics

Honest limits — tell users before they ask:

- **Polylines, not curves.** Paths are `M…L…Z` (implicit lineto). At 4× zoom you can see polygon edges. Catmull-Rom → cubic Bézier smoothing is the next step if you need it.
- **Detail gets flattened.** Hair highlights, iris gradients, soft shading become flat blocks. Banding is unavoidable at 20–48 colours.
- **Large files.** 675 px wide, 48 colours ≈ 2.5–3.5 MB. Detailed images are worse. This is the price of fidelity.
- **It's a trace, not a redraw.** Shapes are machine-cut colour regions, not artist-authored structure. Editing the result by hand is awkward.
- **Text becomes blobs.** Never trace a screenshot when you can re-type the text.

## Use as an OpenClaw skill

`SKILL.md` in this repo is the same procedure written for an agent, so it can be dropped into a skills directory and invoked when someone says *"turn this image into SVG"*.

## Repo layout

```
img2svg.py   → scripts/img2svg.py      the tracer
render_check.py → scripts/render_check.py  render + MAE + comparison sheet
SKILL.md                               agent-facing procedure
examples/                              demo input, output, render, comparison
```

## License

MIT © 2026 SSSY418. See [LICENSE](LICENSE).

Tracing produces a derivative of the input image. Whatever rights you have in the source, that's what you get in the trace — and whatever obligations the source carries, so does the output.
