#!/usr/bin/env python3
"""把三处文案改动写进「生成器」，而不是只改产物。

背景：
  我之前是直接编辑 data/questions.json 的。但 s01~s09 是由
  scripts/add_style_questions.py 生成的——流水线一跑就重新生成，
  我的手改全被覆盖。a14 之所以还在，是因为生成它的是 a 系列的脚本，
  那条链没在 run_all 里跑。

  这类坑我刚刚写进 PITFALLS.md（「会整份覆盖数据的脚本要加护栏」），
  然后自己踩了一次。教训：**改文案要改生成器，不是改产物。**

改的三处（都是选项文字，不动轴值，结构不变）：
  s01 D  「慢慢悠悠、没什么事的」 → 「热血又暖心的片子」
         原来那个被标成 激烈+1.2，语义正好相反
  s02 D  「听完让人心里暖的」     → 「像睡前童话一样」
         原来那个被标成 神秘+1.2，「心里暖」和「神秘」没有关系
  s09    整题四个选项换成真的会发生在睡前的行为
         原来四个是「看日落 / 想以前的事 / 在雨里站着 / 一群人吵吵闹闹」——
         问的是「你会做什么」，给的却是四个诗意画面，答的人不知道该选哪个
"""
from __future__ import annotations

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
GEN = pathlib.Path(r"D:/万智/commander-art-quiz/scripts/add_style_questions.py")

SUBST = [
    ("慢慢悠悠、没什么事的", "热血又暖心的片子"),
    ("听完让人心里暖的", "像睡前童话一样"),
    ("静静看场日落", "泡个澡，听点轻音乐"),
    ("坐着想以前的事", "找朋友吐槽两句"),
    ("一个人在雨里站着", "一个人坐着，想点以前的事"),
    ("一群人吵吵闹闹", "刷手机刷到困"),
]

# s09 的四个选项顺序必须与轴值对应：A(静+忧−) B(静−忧+) C(静+忧+) D(静−忧−)
# 旧文案的顺序是 日落/想事/雨里/吵闹，换成新文案后要按轴值重新配对
S09_OLD = ['"静静看场日落", "坐着想以前的事", "一个人在雨里站着", "一群人吵吵闹闹"']
S09_NEW = ['"泡个澡，听点轻音乐", "找朋友吐槽两句", "一个人坐着，想点以前的事", "刷手机刷到困"']


def main() -> int:
    t = GEN.read_text(encoding="utf-8")
    orig = t

    # 先整体替换 s09 那一行（保证顺序按轴值配对）
    for old, new in zip(S09_OLD, S09_NEW):
        if old in t:
            t = t.replace(old, new)
            print("  ✓ s09 四个选项按轴值重新配对")

    # 其余两处单词替换
    for a, b in SUBST[:2]:
        if a in t:
            n = t.count(a)
            t = t.replace(a, b)
            print(f'  ✓ 「{a}」→「{b}」（{n} 处）')

    if t == orig:
        print("  · 生成器里没有需要改的（可能已经改过）")
    else:
        GEN.write_text(t, encoding="utf-8")

    # 复核
    print("\n  复核：")
    for s in ("热血又暖心的片子", "像睡前童话一样", "泡个澡，听点轻音乐",
              "找朋友吐槽两句", "刷手机刷到困"):
        print(f"    「{s}」{'✓' if s in t else '✗'}")
    for s in ("慢慢悠悠、没什么事的", "听完让人心里暖的", "静静看场日落", "一群人吵吵闹闹"):
        print(f"    旧「{s}」残留 {t.count(s)} 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
