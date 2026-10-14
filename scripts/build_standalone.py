#!/usr/bin/env python3
"""把 art_quiz.html 转成「真·单文件」版本：图片内嵌成 base64。

为什么需要：
  原版用相对路径引用 data/cards/art_crop/ 下的全部图。
  在电脑上没问题，但传到手机时通常只发了 HTML 一个文件，
  目录树没跟过去 → 图全看不见。

做法：
  把每张 art_crop 缩到指定宽度（默认 420px，足够手机全屏观看），
  JPEG 质量 82，base64 内嵌。
  这样 HTML 变成一个自包含文件，发给谁、拷到哪都能直接打开。

体积取舍：
  原图 18.7 MB（每张 626×457）
  → 420px 宽 + q82：约 6~7 MB，base64 后约 9 MB
  手机打开可接受；再小就该糊了。
"""
from __future__ import annotations

import base64
import io
import json
import pathlib
import re
import sys
import time

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SRC_HTML = ROOT / "art_quiz.html"
ART_DIR = ROOT / "data" / "cards" / "art_crop"
OUT = ROOT / "art_quiz_standalone.html"

MAX_W = 420
QUALITY = 82


def main() -> int:
    # newline="" 关掉换行转换：否则 Windows 上会把整份 HTML 的 \n 全写成 \r\n，
    # 应用脚本就跟 art_quiz.html 不再是逐字节相同的同一份（冒烟测试会拦下来）。
    html = SRC_HTML.read_text(encoding="utf-8")
    ids = re.findall(r'"img":"data/cards/art_crop/([0-9a-f\-]+)\.jpg"', html)
    ids = list(dict.fromkeys(ids))
    print(f"HTML 里引用了 {len(ids)} 张图")

    missing = [i for i in ids if not (ART_DIR / f"{i}.jpg").is_file()]
    if missing:
        print(f"✗ 缺 {len(missing)} 张：{missing[:4]}")
        return 1

    t0 = time.time()
    total_raw = total_b64 = 0
    for n, aid in enumerate(ids, 1):
        im = Image.open(ART_DIR / f"{aid}.jpg").convert("RGB")
        w, h = im.size
        if w > MAX_W:
            im = im.resize((MAX_W, round(h * MAX_W / w)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        blob = buf.getvalue()
        total_raw += len(blob)
        b64 = base64.b64encode(blob).decode("ascii")
        total_b64 += len(b64)
        html = html.replace(f'"img":"data/cards/art_crop/{aid}.jpg"',
                            f'"img":"data:image/jpeg;base64,{b64}"')
        if n % 50 == 0 or n == len(ids):
            print(f"  …{n}/{len(ids)}　内嵌 {total_b64/1024/1024:.1f} MB", flush=True)

    OUT.write_text(html, encoding="utf-8", newline="")
    size = OUT.stat().st_size / 1024 / 1024
    print(f"\n✓ {OUT.name}")
    print(f"  体积 {size:.1f} MB（原图 {total_raw/1024/1024:.1f} MB → base64 "
          f"{total_b64/1024/1024:.1f} MB，膨胀 33% 是 base64 的固有开销）")
    print(f"  耗时 {time.time()-t0:.0f} 秒")
    print(f"  图片最长边 {MAX_W}px，JPEG 质量 {QUALITY}")

    # 自检：还有没有残留的相对路径
    left = re.findall(r'"img":"(?!data:)[^"]+"', html)
    print(f"  残留的相对路径引用：{len(left)} 处 {'✓' if not left else left[:3]}")
    ext = re.findall(r'(?:src|href)="https?://', html)
    print(f"  外部依赖：{len(ext)} 处 {'✓' if not ext else ext[:3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
