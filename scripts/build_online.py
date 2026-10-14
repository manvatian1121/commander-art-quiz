#!/usr/bin/env python3
"""做一个「在线版」：图不内嵌，改用 Scryfall 的图片 CDN 地址。

为什么走这条路：
  内嵌版在电脑 Chrome 上能开，但 GUI 预览窗、微信内置浏览器、手机夸克都失败。
  查过 base64 合法、esc 不破坏、路径无误 —— 剩下的可能（沙箱策略、内存、
  传输截断）我在远端都无法复现，继续猜没有意义。

  在线版把这个问题整个绕开：
    · 文件只有几百 KB，任何浏览器都吃得下
    · 不依赖 data:/blob:，不依赖本地文件
    · 每次结果页只加载 3 张图（约 200 KB），流量可忽略
  代价：需要联网。

图片来源：data/art_manifest.json 里存的 Scryfall CDN 地址（image_art_crop）。
Scryfall 允许配合 API 使用其图片地址。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(r"D:/万智/commander-art-quiz")
DATA = ROOT / "data"


def main() -> int:
    # art_id → CDN 地址
    # 两个清单都要读：art_manifest 是原池 273 张，
    # _expansion_manifest 是扩池那 105 张 —— 只读前者会漏 100 张。
    url = {}
    for fn in ("art_manifest.json", "_expansion_manifest.json"):
        fp = DATA / fn
        if not fp.exists():
            continue
        man = json.loads(fp.read_text(encoding="utf-8"))
        if isinstance(man, dict):
            man = man.get("items") or man.get("cards") or []
        for x in man:
            aid = x.get("art_id")
            u = x.get("image_art_crop") or x.get("image_normal")
            if aid and u:
                url[aid] = u
        print(f"  {fn}: 累计 {len(url)} 个地址")
    print(f"  art_manifest 里有 {len(url)} 个 CDN 地址")

    axes = json.loads((DATA / "art_axes.json").read_text(encoding="utf-8"))
    missing = [x["art_id"] for x in axes if x["art_id"] not in url]
    print(f"  art_axes 里 {len(axes)} 张，缺 CDN 地址的 {len(missing)} 张")

    html = (ROOT / "art_quiz.html").read_text(encoding="utf-8")
    ids = list(dict.fromkeys(
        re.findall(r'"img":"data/cards/art_crop/([0-9a-f\-]+)\.jpg"', html)))
    print(f"  HTML 引用 {len(ids)} 张")

    hit = 0
    for aid in ids:
        if aid in url:
            html = html.replace(f'"img":"data/cards/art_crop/{aid}.jpg"',
                                '"img":"' + url[aid] + '"')
            hit += 1
    out = ROOT / "art_quiz_online.html"
    out.write_text(html, encoding="utf-8")

    print(f"\n  ✓ art_quiz_online.html  {out.stat().st_size/1024:.0f} KB   替换 {hit} 张")
    left = len(re.findall(r'"img":"data/cards/', html))
    print(f"    残留本地路径 {left} 处 {'✓' if not left else '✗'}")
    print(f"    外部依赖 {len(re.findall(chr(34)+'img'+chr(34)+':'+chr(34)+'https?://', html))} 处（图片 CDN，仅结果页加载 3 张）")
    # 抽一个看看
    m = re.search(r'"img":"(https://[^"]+)"', html)
    print(f"    样例：{m.group(1)[:88] if m else '—'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
