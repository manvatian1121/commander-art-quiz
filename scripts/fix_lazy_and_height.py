#!/usr/bin/env python3
"""去掉两处与朋友版不一致、且可能导致图片不显示的写法。

对照朋友那份「手机上能显示」的版本，剩下的实质差别只有这几条：

  ① loading="lazy"                     他删了，我留着  ← 改
  ② .pick .shot img{height:auto}        他删了，我在移动端媒体查询里留着  ← 改
  ③ clamp()                             他用，我换成固定值   ← 不影响
  ④ inset:0                             他用，我写成四边     ← 不影响

前两条都可能致命：

  ① data: URI 配 loading="lazy"：浏览器按「是否进入视口」决定要不要解码。
     图片是绝对定位的，某些移动端内核在计算交叉区域时会判成「不在视口」，
     于是惰性加载永远不触发，图就一直空着。
  ② img{height:auto} 会覆盖绝对定位那套的 height:100%，图填不满容器。
"""
from __future__ import annotations

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
TPL = pathlib.Path(r"D:/万智/commander-art-quiz/scripts/templates/art_quiz.template.html")


def main() -> int:
    t = TPL.read_text(encoding="utf-8")
    orig = t

    # ① 去掉 loading="lazy"
    n1 = t.count('loading="lazy" ')
    t = t.replace("'loading=\"lazy\" data-img-key=", "'data-img-key=")
    t = t.replace('loading="lazy" ', "")
    print(f"  ✓ 去掉 loading=lazy（{n1} 处）")

    # ② 去掉会覆盖绝对定位的 height:auto
    n2 = t.count(".pick .shot img{height:auto}")
    t = t.replace(".pick .shot img{height:auto}", "")
    print(f"  ✓ 清掉 img{{height:auto}} 覆盖（{n2} 处）")

    if t == orig:
        print("  · 没有可改的地方")
    else:
        TPL.write_text(t, encoding="utf-8")

    # 复核
    print(f"\n  复核：")
    print(f"    loading= 残留        {t.count('loading=')} 处")
    print(f"    height:auto 残留     {t.count('.pick .shot img{height:auto}')} 处")
    print(f"    ::before 撑高        {t.count('.pick .shot::before')} 处")
    print(f"    img 绝对定位         {t.count('position:absolute;top:0;left:0')} 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
