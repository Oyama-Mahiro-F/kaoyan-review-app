# -*- coding: utf-8 -*-
"""生成启动图标（简单几何图形：深蓝圆角底 + 白色书本/对勾意象）。"""
from PIL import Image, ImageDraw

SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
OUT = __file__.rsplit("\\", 1)[0] + "/res"

BG = (37, 60, 122, 255)      # 深蓝
ACCENT = (255, 199, 44, 255) # 琥珀黄
WHITE = (255, 255, 255, 255)

for dpi, size in SIZES.items():
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size // 5
    # 圆角底
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=BG)
    # 打开的书（两页）
    cx, cy = size // 2, int(size * 0.46)
    w, h = int(size * 0.58), int(size * 0.30)
    d.polygon([(cx - w, cy - h // 3), (cx, cy - h // 6), (cx, cy + h), (cx - w, cy + h * 2 // 3)], fill=WHITE)
    d.polygon([(cx + w, cy - h // 3), (cx, cy - h // 6), (cx, cy + h), (cx + w, cy + h * 2 // 3)], fill=(230, 236, 250, 255))
    # 书脊线
    d.line([(cx, cy - h // 6), (cx, cy + h)], fill=BG, width=max(2, size // 48))
    # 底部对勾（复习完成意象）
    lw = max(3, size // 16)
    x1, y1 = int(size * 0.34), int(size * 0.70)
    x2, y2 = int(size * 0.46), int(size * 0.82)
    x3, y3 = int(size * 0.68), int(size * 0.58)
    d.line([(x1, y1), (x2, y2)], fill=ACCENT, width=lw)
    d.line([(x2, y2), (x3, y3)], fill=ACCENT, width=lw)
    d.ellipse([x1 - lw * 2, y1 - lw * 2, x1 + lw * 2, y1 + lw * 2], fill=ACCENT)
    d.ellipse([x3 - lw * 2, y3 - lw * 2, x3 + lw * 2, y3 + lw * 2], fill=ACCENT)
    import os
    folder = f"{OUT}/mipmap-{dpi}"
    os.makedirs(folder, exist_ok=True)
    img.save(f"{folder}/ic_launcher.png")
    print(f"mipmap-{dpi}/ic_launcher.png {size}x{size}")
