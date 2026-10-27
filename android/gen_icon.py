# -*- coding: utf-8 -*-
r"""启动图标生成：android/icon.svg（手绘矢量）→ Edge 无头渲染 1024px → Pillow 裁圆角、出全密度 mipmap。

用法：python gen_icon.py
依赖：Windows 自带 Edge；Pillow。产物：res/mipmap-*/ic_launcher.png + icon-1024.png（备份）+ ../docs/icon-512.png
"""
import os
import subprocess
import sys
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SVG = os.path.join(HERE, "icon.svg")
RAW = os.path.join(HERE, "icon-1024.png")
SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def find_edge():
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if os.path.exists(p):
            return p
    return None


def render():
    edge = find_edge()
    if not edge:
        sys.exit("未找到 Edge，无法渲染 icon.svg")
    url = "file:///" + SVG.replace("\\", "/")
    subprocess.run([edge, "--headless", "--disable-gpu",
                    "--screenshot=" + RAW, "--window-size=1024,1024",
                    "--hide-scrollbars", url],
                   check=True, capture_output=True, timeout=60)


def finish():
    img = Image.open(RAW).convert("RGBA")
    if img.size != (1024, 1024):
        img = img.resize((1024, 1024), Image.LANCZOS)
    # 圆角 alpha 蒙版（512 画布 rx=112 → 1024 下 r=224）
    mask = Image.new("L", (1024, 1024), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, 1023, 1023], radius=224, fill=255)
    img.putalpha(mask)
    img.save(RAW)
    for dpi, size in SIZES.items():
        folder = os.path.join(HERE, "res", "mipmap-" + dpi)
        os.makedirs(folder, exist_ok=True)
        img.resize((size, size), Image.LANCZOS).save(os.path.join(folder, "ic_launcher.png"))
        print(f"mipmap-{dpi}/ic_launcher.png {size}x{size}")
    preview = os.path.join(HERE, "..", "docs", "icon-512.png")
    img.resize((512, 512), Image.LANCZOS).save(preview)
    print("docs/icon-512.png（README 预览）")


if __name__ == "__main__":
    render()
    finish()
