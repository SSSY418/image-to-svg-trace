#!/usr/bin/env python3
"""img2svg.py —— 位图自动矢量化（纯 PIL，无 numpy / 无 vtracer）

流程：预处理 -> 调色板减色 -> 像素边界追踪(crack following) -> 折线简化 -> SVG path

用法：
  python3 img2svg.py in.jpg out.svg
  python3 img2svg.py in.jpg out.svg --width 675 --colors 48 --eps 0.45 --min-area 20 --saturate 1.25 --median 3

参数经验值（二次元插画）：
  --colors 40~48 --eps 0.4~0.5 --min-area 15~25   保真优先
  --colors 16~24 --eps 0.7~0.9 --min-area 40~80   文件小、色块干净
  --smooth 1                                     出图干净但吃细节，慎用
"""
import argparse
from PIL import Image, ImageFilter, ImageEnhance


def preprocess(im, width, median, saturate, contrast):
    h = round(im.height * width / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    if median and median > 1:
        im = im.filter(ImageFilter.MedianFilter(median))
    if saturate and abs(saturate - 1.0) > 1e-3:
        im = ImageEnhance.Color(im).enhance(saturate)
    if contrast and abs(contrast - 1.0) > 1e-3:
        im = ImageEnhance.Contrast(im).enhance(contrast)
    return im


def quantize(im, k, smooth):
    q = im.quantize(colors=k, method=Image.MEDIANCUT, dither=Image.NONE)
    if smooth:
        q = q.filter(ImageFilter.ModeFilter(3))
    pal = q.getpalette()[:k * 3]
    colors = [tuple(pal[i * 3:i * 3 + 3]) for i in range(k)]
    return list(q.getdata()), colors, q.size[0], q.size[1]


def contour_loops(mask, W, H):
    """crack following：沿前景/背景像素之间的边追踪闭合轮廓（不依赖 numpy）"""
    edges = {}

    def add(a, b):
        edges.setdefault(a, []).append(b)

    for y in range(H):
        row = y * W
        for x in range(W):
            if not mask[row + x]:
                continue
            up = y > 0 and mask[row - W + x]
            dn = y < H - 1 and mask[row + W + x]
            lf = x > 0 and mask[row + x - 1]
            rt = x < W - 1 and mask[row + x + 1]
            if not up:
                add((x, y), (x + 1, y))
            if not rt:
                add((x + 1, y), (x + 1, y + 1))
            if not dn:
                add((x + 1, y + 1), (x, y + 1))
            if not lf:
                add((x, y + 1), (x, y))

    loops = []
    while edges:
        start = next(iter(edges))
        cur = start
        path = [start]
        while True:
            lst = edges.get(cur)
            if not lst:
                break
            nxt = lst.pop()
            if not lst:
                del edges[cur]
            path.append(nxt)
            cur = nxt
            if cur == start:
                break
        if len(path) > 4:
            loops.append(path)
    return loops


def drop_collinear(pts):
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        x0, y0 = out[-1]
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        if (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1) != 0:
            out.append((x1, y1))
    out.append(pts[-1])
    return out


def dp(pts, eps):
    """Douglas-Peucker，迭代实现，避免长轮廓递归爆栈"""
    n = len(pts)
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi <= lo + 1:
            continue
        x1, y1 = pts[lo]
        x2, y2 = pts[hi]
        dx, dy = x2 - x1, y2 - y1
        norm = (dx * dx + dy * dy) ** 0.5
        best, bi = -1.0, -1
        for i in range(lo + 1, hi):
            x0, y0 = pts[i]
            if norm == 0:
                d = ((x0 - x1) ** 2 + (y0 - y1) ** 2) ** 0.5
            else:
                d = abs(dy * (x0 - x1) - dx * (y0 - y1)) / norm
            if d > best:
                best, bi = d, i
        if best > eps and bi > 0:
            keep[bi] = True
            stack.append((lo, bi))
            stack.append((bi, hi))
    return [p for p, k in zip(pts, keep) if k]


def to_svg(src, dst, width=675, colors=48, eps=0.45, min_area=20,
           median=3, saturate=1.25, contrast=1.0, smooth=False, bg="#ffffff"):
    im = Image.open(src).convert("RGB")
    im = preprocess(im, width, median, saturate, contrast)
    idx, pal, W, H = quantize(im, colors, smooth)

    counts = [0] * colors
    for v in idx:
        counts[v] += 1
    order = sorted(range(colors), key=lambda i: -counts[i])

    parts = []
    for ci in order:
        if counts[ci] < min_area:
            continue
        mask = bytearray(W * H)
        for i, v in enumerate(idx):
            if v == ci:
                mask[i] = 1
        d = []
        for lp in contour_loops(mask, W, H):
            if len(lp) < 5:
                continue
            lp = drop_collinear(lp)
            if len(lp) > 3:
                lp = dp(lp, eps)
            if len(lp) < 4:
                continue
            d.append("M" + "".join("%g %g " % p for p in lp) + "Z")
        if d:
            r, g, b = pal[ci]
            parts.append('<path fill="#%02x%02x%02x" fill-rule="evenodd" d="%s"/>' % (r, g, b, "".join(d)))

    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
           '<rect width="%d" height="%d" fill="%s"/>%s</svg>') % (W, H, W, H, W, H, bg, "".join(parts))
    with open(dst, "w", encoding="utf-8") as f:
        f.write(svg)
    print("done %s  %d bytes  %d layers  %dx%d" % (dst, len(svg), len(parts), W, H))
    return dst


def main():
    ap = argparse.ArgumentParser(description="位图转 SVG（纯 PIL 实现）")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--width", type=int, default=675)
    ap.add_argument("--colors", type=int, default=48)
    ap.add_argument("--eps", type=float, default=0.45)
    ap.add_argument("--min-area", type=float, default=20)
    ap.add_argument("--median", type=int, default=3)
    ap.add_argument("--saturate", type=float, default=1.25)
    ap.add_argument("--contrast", type=float, default=1.0)
    ap.add_argument("--smooth", type=int, default=0)
    ap.add_argument("--bg", default="#ffffff")
    a = ap.parse_args()
    to_svg(a.src, a.dst, a.width, a.colors, a.eps, a.min_area,
           a.median, a.saturate, a.contrast, bool(a.smooth), a.bg)


if __name__ == "__main__":
    main()
