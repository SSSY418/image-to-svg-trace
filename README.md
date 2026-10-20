# image-to-svg-trace

**Turn any bitmap into a real SVG — no numpy, no vtracer, one file, ~5 seconds.**

**把任意位图变成真正的 SVG——不依赖 numpy、不用 vtracer，一个文件，五秒出图。**

---

## What it is / 这是什么

A dependency-free raster→vector tracer written with nothing but Pillow.

流程：预处理 → 调色板减色 → 像素边界追踪（crack following）→ 折线简化（Douglas–Peucker）→ 输出 SVG `<path>`

Uses `fill-rule="evenodd"` and stacks colour layers by area, so the result is a single self-contained SVG that scales cleanly and can be edited in any vector editor.

输出按面积降序叠层，用 `fill-rule="evenodd"` 处理镂空，最终是一个自包含、可无限缩放的 SVG，能直接拖进 Illustrator / Figma / Inkscape。

![demo](examples/demo-compare.png)

*Left: input PNG. Right: re-rendered from the SVG. This pair scores MAE **1.83** (mean absolute per-pixel error, 0–255).*
*左：输入的位图。右：从生成的 SVG 重新渲染。这一对的 MAE 是 **1.83**（逐像素平均绝对误差，0–255）。*

## Why not vtracer / potrace / autotrace? / 为什么不用现成库

Measured on WSL2 + Python 3.14, October 2026:

| Tool | Result |
|---|---|
| `vtracer` 0.6.15 / 0.6.11 | imports fine, then **segfaults on the first call** — even on a 60×107 image. Wheel/environment mismatch. |
| `potracer` | `ModuleNotFoundError: No module named 'potrace'` after install; also drags in numpy (16.7 MB) |
| `potrace` / `autotrace` binaries | not present, and not packaged for this distro |

So the tracer here is ~200 lines of plain Python + Pillow. It needs nothing you don't already have, and it runs anywhere Pillow runs.

所以就自己写了一个两百来行、只用 Pillow 的实现。你在哪都能跑，不用装编译器、不用配原生库。

## Install / 安装

```bash
pip install pillow
git clone https://github.com/SSSY418/image-to-svg-trace.git
cd image-to-svg-trace
```

No other dependencies. Python 3.9+.

## Usage / 用法

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

Rules of thumb / 经验值

- **Anime / flat illustrations**: `--colors 40~48 --eps 0.4~0.5 --min-area 15~25 --saturate 1.25`
- **Photos**: `--colors 64 --eps 0.35 --median 3`
- **Icons / line art**: skip this tool, use centreline tracing instead
- **Big flat fills, small file**: `--colors 16~24 --eps 0.8 --min-area 60 --smooth 1`

## Verify it looks right / 验证闭环

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

Reference numbers / 参考量级

| Approach | MAE |
|---|---|
| This tracer, default settings on an illustration | **7.0** |
| This tracer on a flat vector-ish demo | **1.8** |
| Hand-authoring SVG coordinates to "reproduce" an illustration | **76.8** |

That last row is the reason this tool exists: four hand-drawn attempts at reproducing an anime illustration landed at 76.8, then the tracer landed at 7.0 on the first try. Don't hand-place coordinates to copy an image.

最后一行就是这工具存在的理由：手写坐标复刻插画，四版加起来 MAE 76.8，换上描摹第一版就是 7.0。

## Output characteristics / 输出特性与局限

Honest limits — tell users before they ask:

- **Polylines, not curves.** Paths are `M…L…Z` (implicit lineto). At 4× zoom you can see polygon edges. Catmull-Rom → cubic Bézier smoothing is the next step if you need it.
- **Detail gets flattened.** Hair highlights, iris gradients, soft shading become flat blocks. Banding is unavoidable at 20–48 colours.
- **Large files.** 675 px wide, 48 colours ≈ 2.5–3.5 MB. Detailed images are worse. This is the price of fidelity.
- **It's a trace, not a redraw.** Shapes are machine-cut colour regions, not artist-authored structure. Editing the result by hand is awkward.
- **Text becomes blobs.** Never trace a screenshot when you can re-type the text.

- **输出是折线不是曲线**，放大四倍能看出多边形边。要更顺就做 Catmull-Rom → 贝塞尔拟合。
- **细节会被压平**：高光、渐变、柔光都变成色块，色阶不可避免。
- **文件偏大**：675 宽 48 色大约 2.5–3.5MB。
- **这是描摹不是重绘**：形状是机器切的色区，结构不是画师的那套。
- **文字会变成糊块**：能重新打字就别描截图。

## Use as an OpenClaw skill / 作为 OpenClaw skill 使用

`SKILL.md` in this repo is the same procedure written for an agent, so it can be dropped into a skills directory and invoked when someone says *"turn this image into SVG"*.

仓库里的 `SKILL.md` 是同一套流程的 agent 版说明书，放进 skills 目录即可让 agent 在「把这张图转成 svg」时自动走这套流程。

## Repo layout / 目录

```
img2svg.py   → scripts/img2svg.py      the tracer
render_check.py → scripts/render_check.py  render + MAE + comparison sheet
SKILL.md                               agent-facing procedure
examples/                              demo input, output, render, comparison
```

## License

MIT © 2026 SSSY418. See [LICENSE](LICENSE).

Tracing produces a derivative of the input image. Whatever rights you have in the source, that's what you get in the trace — and whatever obligations the source carries, so does the output.
描摹产物是输入图的衍生品：源图你能怎么用，描摹结果才能怎么用；源图的授权限制，同样落在结果上。
