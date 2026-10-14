#!/usr/bin/env python3
"""修移动端卡片高度塌陷 —— 这才是「手机上卡片整个不显示」的真正原因。

根因：
  桌面宽度下 .picks 是横排（flex-direction:row），.pick{flex:1 1 0} 的
  flex-basis:0 作用在**宽度**上，靠 flex-grow 平分宽度，一切正常。

  手机宽度（<680px）触发了媒体查询，.picks 改成 flex-direction:column，
  flex-basis:0 于是作用在**高度**上：
      .picks 没有设定高度 → 没有多余空间可供 grow 分配
      → 每张卡片的高度 = 0
      → .pick{overflow:hidden} 把里面的内容整块裁掉
  结果就是「卡片里的文字和图片一起消失」，而且只在手机上出现。

  修法（与已验证可用的版本一致）：在移动端给卡片 flex:0 0 auto，
  让高度按内容计算。
"""
from __future__ import annotations

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
TPL = pathlib.Path(r"D:/万智/commander-art-quiz/scripts/templates/art_quiz.template.html")


def main() -> int:
    t = TPL.read_text(encoding="utf-8")
    orig = t

    # ① 移动端：卡片高度按内容算
    if ".pick{flex:0 0 auto}" in t:
        print("  · 已有 .pick{flex:0 0 auto}")
    else:
        anchor = ".picks{flex-direction:column;gap:14px}"
        if anchor in t:
            t = t.replace(anchor, anchor + "\n    .pick{flex:0 0 auto}")
            print("  ✓ 移动端加 .pick{flex:0 0 auto}（高度按内容算，不再塌成 0）")
        else:
            print("✗ 找不到移动端 .picks 竖排那条规则")
            return 1

    # ② 字号恢复 clamp()，与验证过的版本一致
    for a, b in (("h1{font-size:4.6vw;", "h1{font-size:clamp(23px,4.6vw,34px);"),
                 ("h2{font-size:3vw;", "h2{font-size:clamp(18px,3vw,23px);"),
                 (".rsub{font-size:3.4vw;", ".rsub{font-size:clamp(19px,3.4vw,26px);")):
        if a in t:
            t = t.replace(a, b)
            print(f"  ✓ 恢复 {b.split('{')[0]}{{font-size:clamp(...)}}")

    # ③ inset:0 恢复（等价写法，但和验证过的版本对齐）
    if "top:0;right:0;bottom:0;left:0" in t:
        t = t.replace("top:0;right:0;bottom:0;left:0", "inset:0")
        print("  ✓ 恢复 inset:0")

    if t != orig:
        TPL.write_text(t, encoding="utf-8")

    # 复核
    print("\n  复核：")
    print(f"    .pick{{flex:0 0 auto}}   {t.count('.pick{flex:0 0 auto}')} 处")
    print(f"    clamp(                  {t.count('clamp(')} 处")
    print(f"    inset:0                 {t.count('inset:0')} 处")
    print(f"    ::before 撑高           {t.count('.pick .shot::before')} 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
