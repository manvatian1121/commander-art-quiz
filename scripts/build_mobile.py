#!/usr/bin/env python3
"""做一个「手机版」：把图压得更小，让整个 HTML 瘦下来。

为什么需要：
  art_quiz_standalone.html 是 17.3 MB（370 张图 @420px q82，base64 约 12 MB）。
  用户在两台设备上都打不开内嵌图，其中一个可能是**文件太大、手机内存扛不住**。

做法：
  从 art_quiz.html（图是相对路径的那版）出发，把每张 art_crop 缩小到指定宽度、
  降低 JPEG 质量，再 base64 内嵌。

尺寸取舍：
  手机 CSS 宽度约 400px，但结果页是三张并排 + 单张详情，实际显示宽度不大。
  240~300px 在手机上够看，体积能压到 5~7 MB。
"""
from __future__ import annotations

import base64
import io
import pathlib
import re
import sys
import time

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(r"D:/万智/commander-art-quiz")
SRC = ROOT / "art_quiz.html"
ART = ROOT / "data" / "cards" / "art_crop"


def build(width: int, quality: int, out_name: str) -> float:
    html = SRC.read_text(encoding="utf-8")
    ids = list(dict.fromkeys(
        re.findall(r'"img":"data/cards/art_crop/([0-9a-f\-]+)\.jpg"', html)))
    t0 = time.time()
    raw_total = 0
    for aid in ids:
        p = ART / f"{aid}.jpg"
        if not p.is_file():
            continue
        im = Image.open(p).convert("RGB")
        w, h = im.size
        if w > width:
            im = im.resize((width, round(h * width / w)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
        blob = buf.getvalue()
        raw_total += len(blob)
        html = html.replace(
            f'"img":"data/cards/art_crop/{aid}.jpg"',
            '"img":"data:image/jpeg;base64,' + base64.b64encode(blob).decode() + '"')
    out = ROOT / out_name
    out.write_text(html, encoding="utf-8")
    mb = out.stat().st_size / 1024 / 1024
    print(f"  ✓ {out_name}  {mb:.1f} MB   {len(ids)} 张  "
          f"{width}px/q{quality}   图共 {raw_total/1024/1024:.1f} MB   {time.time()-t0:.0f}s")
    left = len(re.findall(r'"img":"data/cards/', html))
    print(f"      残留相对路径 {left} 处 {'✓' if not left else '✗'}")
    return mb


def main() -> int:
    print("=== 逐档试，看体积曲线 ===")
    for w, q, name in ((240, 70, "art_quiz_mobile.html"),
                       (300, 76, "_try_300.html"),
                       (360, 80, "_try_360.html")):
        build(w, q, name)
    # 只留手机版，删掉试档
    for f in ("_try_300.html", "_try_360.html"):
        (ROOT / f).unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
