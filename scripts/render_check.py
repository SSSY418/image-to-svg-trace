#!/usr/bin/env python3
"""render_check.py —— 把 SVG 渲染成 PNG，并和参考图算逐像素平均差（MAE）

用法：
  python3 render_check.py out.svg --ref input.jpg --out render.png
  python3 render_check.py out.svg --ref input.jpg --width 675 --chrome "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"

没有浏览器时只做尺寸/结构检查，不渲染。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

CHROME_CANDIDATES = [
    os.environ.get("CHROME", ""),
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def find_chrome(explicit=None):
    for c in ([explicit] if explicit else []) + CHROME_CANDIDATES:
        if c and os.path.exists(c):
            return c
    return None


def svg_size(svg_path):
    """从 svg 头里读 width/height/viewBox"""
    head = open(svg_path, encoding="utf-8").read(600)
    import re
    def num(pat):
        m = re.search(pat, head)
        return float(m.group(1)) if m else None
    w = num(r'width="([\d.]+)')
    h = num(r'height="([\d.]+)')
    if not w or not h:
        m = re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ([\d.]+)"', head)
        if m:
            w, h = float(m.group(1)), float(m.group(2))
    return w, h


def render(svg_path, out_png, chrome, width=None, height=None, scale=1):
    w, h = svg_size(svg_path)
    if width:
        h = round(h * width / w)
        w = width
    if height:
        h = height
    w, h = int(round(w)), int(round(h))
    tmp = tempfile.mkdtemp(prefix="svgshot-")
    svg_local = os.path.join(tmp, "in.svg")
    shutil.copy(svg_path, svg_local)
    html_local = os.path.join(tmp, "shot.html")
    with open(html_local, "w", encoding="utf-8") as f:
        f.write('<!doctype html><meta charset="utf-8">'
                '<style>html,body{margin:0;padding:0;background:#fff}'
                'img{display:block;width:%dpx;height:%dpx}</style>'
                '<img src="in.svg">' % (w, h))
    win_png = out_png
    if os.name != "nt" and chrome.lower().endswith(".exe"):
        # WSL 下调 Windows Chrome：路径要转成 C:\ 形式，输出也是
        win_png = subprocess.run(["wslpath", "-w", os.path.abspath(out_png)],
                                 capture_output=True, text=True).stdout.strip()
        url = "file:///" + subprocess.run(["wslpath", "-w", html_local],
                                          capture_output=True, text=True).stdout.strip()
    else:
        url = "file://" + os.path.abspath(html_local)
    cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--force-device-scale-factor=%d" % scale,
           "--window-size=%d,%d" % (w, h),
           "--screenshot=" + win_png, url]
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(tmp, ignore_errors=True)
    return out_png, (w, h)


def mae(a_path, b_path, size):
    from PIL import Image, ImageChops, ImageStat
    a = Image.open(a_path).convert("RGB").resize(size)
    b = Image.open(b_path).convert("RGB").resize(size)
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3


def side_by_side(ref, render_png, dst, label_a="original", label_b="svg render"):
    from PIL import Image, ImageDraw, ImageFont
    a = Image.open(ref).convert("RGB")
    b = Image.open(render_png).convert("RGB")
    h = 900
    a = a.resize((round(a.width * h / a.height), h))
    b = b.resize((round(b.width * h / b.height), h))
    pad, top = 16, 46
    c = Image.new("RGB", (a.width + b.width + pad * 3, h + top + pad), "#111")
    c.paste(a, (pad, top))
    c.paste(b, (pad * 2 + a.width, top))
    d = ImageDraw.Draw(c)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
    except Exception:
        f = ImageFont.load_default()
    d.text((pad, 12), label_a, fill="#fff", font=f)
    d.text((pad * 2 + a.width, 12), label_b, fill="#fff", font=f)
    c.save(dst)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("--ref", help="参考图，用于算 MAE 和出对比图")
    ap.add_argument("--out", default="render.png")
    ap.add_argument("--width", type=int)
    ap.add_argument("--height", type=int)
    ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--chrome")
    ap.add_argument("--compare", help="并排对比图输出路径")
    a = ap.parse_args()

    chrome = find_chrome(a.chrome)
    info = {"svg": a.svg, "size": svg_size(a.svg), "chrome": chrome}
    if not chrome:
        print(json.dumps({**info, "error": "no chrome found"}, ensure_ascii=False))
        return 1
    png, size = render(a.svg, a.out, chrome, a.width, a.height, a.scale)
    info.update({"png": png, "px": size})
    if a.ref:
        info["mae"] = round(mae(a.ref, png, size), 2)
        if a.compare:
            info["compare"] = side_by_side(a.ref, png, a.compare)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
