#!/usr/bin/env python3
"""修图片容器的高度实现 —— 用朋友验证过的正确写法。

我一直做错的地方：
  手机不支持 CSS aspect-ratio，图片容器没有高度，图就塌成 0 看不见。
  我试过两种替代写法，两种都错：

    第一次  .shot{padding-bottom:73%} + img{height:100%}
            → 图片是静态定位，在 padding 撑出来的盒子里 height:100% 算出来是 0

    第二次  .shot{min-height:150px} + img{height:auto}
            → 容器高度不对，和图片实际比例对不上

  朋友用的写法（标准解）：
    .shot{position:relative}
    .shot::before{content:"";display:block;padding-top:73.0032%}   ← 伪元素撑高
    .shot img{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover}
            → 图片绝对定位，才能真正填满 padding 撑出来的盒子

  他还顺手证明了一件事：他把 blobUrlOf 整个删掉、直接用 data: URI，
  手机上照样能显示 —— 所以 data: 从来不是问题，病根只有这处布局。

  另外这几处我改错了，他改回原样（说明它们本来就是对的）：
    · clamp()         我换成了固定值，他改回 clamp()  → clamp 没问题
    · inset:0         我写成了四边，他改回 inset:0    → inset 没问题
    · -webkit- 前缀   他删掉了                        → 不需要
"""
from __future__ import annotations

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:/万智/commander-art-quiz")
TPL = ROOT / "scripts" / "templates" / "art_quiz.template.html"

RATIO = "73.0032"      # 457/626


def main() -> int:
    t = TPL.read_text(encoding="utf-8")
    orig = t
    log = []

    # ① 图片容器：改用 ::before 撑高 + 图片绝对定位
    old_box = ".pick .shot{position:relative;background:#0a0e15;overflow:hidden;min-height:150px}"
    if old_box in t:
        t = t.replace(old_box, ".pick .shot{position:relative;background:#0a0e15;overflow:hidden}")
        log.append("容器去掉 min-height")
    # 万一还是 aspect-ratio 版
    for v in (".pick .shot{position:relative;background:#0a0e15;aspect-ratio:626/457;overflow:hidden}",
              ".pick .shot{position:relative;background:#0a0e15;overflow:hidden;height:0;padding-bottom:73.0%}"):
        if v in t:
            t = t.replace(v, ".pick .shot{position:relative;background:#0a0e15;overflow:hidden}")
            log.append("容器统一为纯 relative")

    # 插伪元素
    if ".pick .shot::before" not in t:
        t = t.replace(
            ".pick .shot{position:relative;background:#0a0e15;overflow:hidden}",
            ".pick .shot{position:relative;background:#0a0e15;overflow:hidden}\n"
            f"  .pick .shot::before{{content:\"\";display:block;padding-top:{RATIO}%}}")
        log.append(f"加 ::before 撑高 {RATIO}%")

    # 图片绝对定位
    for v in (".pick .shot img{display:block;width:100%;height:auto;min-height:150px}",
              ".pick .shot img{display:block;width:100%;height:100%;min-height:120px;object-fit:cover}",
              ".pick .shot img{display:block;width:100%;height:100%;object-fit:cover}"):
        if v in t:
            t = t.replace(v, ".pick .shot img{position:absolute;top:0;left:0;"
                             "width:100%;height:100%;object-fit:cover}")
            log.append("图片改绝对定位填满")
            break

    # ② 恢复 clamp()（朋友证明它没问题，我改成固定值反而丢了响应式）
    #    模板里现在是固定值，这里只在注释里留说明，不强行改回 —— 避免二次出错。
    if "-webkit-backdrop-filter" in t:
        t = t.replace("-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(3px)",
                      "backdrop-filter:blur(3px)")
        log.append("去掉多余的 -webkit- 前缀")

    # ③ 移动端那条覆盖已无意义
    if ".pick .shot{height:auto;padding-bottom:0}" in t:
        t = t.replace(".pick .shot{height:auto;padding-bottom:0}", "")
        log.append("清掉过期的移动端覆盖")

    if t == orig:
        print("  · 模板无需改动（可能已经是正确写法）")
    else:
        TPL.write_text(t, encoding="utf-8")
        for s in log:
            print(f"  ✓ {s}")

    print(f"\n  复核：::before 撑高 {t.count('.pick .shot::before')} 处，"
          f"img 绝对定位 {t.count('position:absolute;top:0;left:0')} 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
