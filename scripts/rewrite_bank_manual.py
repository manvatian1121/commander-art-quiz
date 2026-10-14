#!/usr/bin/env python3
"""重写题库文案 —— 由主 agent 手工撰写，不用子代理。

客户反馈的三条：
  ① 水果/蔬菜题没区分度（正常人都会选新鲜的）→ 去掉，换成日用品
  ② 「看着像人，但不对劲」不像人话 → 改成「类人形的奇异生物」这类准确说法
  ③ 形态题改成 1 道多选题：「在奇幻世界中，你比较想与哪些存在成为伙伴」

顺带修一个更根本的问题（这才是「僵硬」的根源）：
  原来每个选项都是「半句／半句」的 2×2 叉乘，读起来像表格不像选择。
  例如 a01：「采光好、亮堂／木色、暖光」。
  新写法让每个选项是一个完整的意象：
  「大窗，木地板，阳光晒进来」——仍然是 2×2 的四个角，但读起来是四个真实的房间。

奇偶约束：每条轴的出现次数必须为偶数，位置残留才能归零。
  去掉 a06（bright+rich）与 a11（bright+contrasty）后：
    bright 4、rich 5、contrasty 5、其余 6
  补一道 rich+contrasty → 全部为偶数 ✓
  最终：26 道审美题 + 1 道形态多选题 = 27 题
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:/万智/commander-art-quiz")
DATA = ROOT / "data"

L, H = 0.6, 1.2          # 光影轴用 L，其余用 H

# (题号, 题干, 轴A, 轴B, [四选项文本], [四选项的 (a值, b值)])
BANK = [
    ("a01", "你更想住哪种房子？", "warm", "bright",
     ["大窗，木地板，阳光晒进来", "大窗，白墙灰地，通透明亮",
      "小窗，暖黄的灯，木头家具", "小窗，冷白的灯，水泥墙"],
     [(+H, +L), (-H, +L), (+H, -L), (-H, -L)]),

    ("a02", "手机主题你会选哪种？", "vivid", "starart",
     ["默认那套，图标颜色很浓", "默认那套，素净的浅色",
      "自己调的小众主题，颜色浓", "自己调的小众主题，淡雅"],
     [(+H, +H), (-H, +H), (+H, -H), (-H, -H)]),

    ("a03", "壁纸你想贴哪种？", "rich", "borderless",
     ["一整面都是图案，好几种花色", "一整面都是图案，一个色",
      "四周留一圈素边，好几种花色", "四周留一圈素边，一个色"],
     [(+H, +H), (-H, +H), (+H, -H), (-H, -H)]),

    ("a04", "房间你会怎么布置？", "detailed", "modern",
     ["摆件很多，摆得满满当当", "摆件很多，但家具换成新款的",
      "东西很少，就几件老家具", "东西很少，家具全是新款的"],
     [(+H, -H), (+H, +H), (-H, -H), (-H, +H)]),

    ("a05", "桌上那块垫子，你喜欢哪种？", "warm", "vivid",
     ["暖黄、米色，颜色淡淡的", "冷灰、蓝青，颜色淡淡的",
      "暖黄、米色，颜色很浓", "冷灰、蓝青，颜色很浓"],
     [(+H, -H), (-H, -H), (+H, +H), (-H, +H)]),

    # 新的 rich+contrasty 题，补 parity
    ("a28", "你会买哪种沙发？", "rich", "contrasty",
     ["深灰底配一把亮黄单椅", "深灰配浅灰，颜色很接近",
      "米白、浅咖、豆绿凑一屋", "米白配浅咖，颜色很接近"],
     [(+H, +H), (-H, -H), (+H, -H), (-H, +H)]),

    ("a07", "给朋友挑礼物，你会挑？", "detailed", "starart",
     ["简单包一下，常见牌子", "简单包一下，很少见的牌子",
      "包装讲究，常见牌子", "包装讲究，很少见的牌子"],
     [(+H, +H), (+H, -H), (-H, +H), (-H, -H)]),

    ("a08", "点外卖，你喜欢哪种？", "borderless", "contrasty",
     ["配菜堆得满满，味道清淡", "配菜堆得满满，够辣够味",
      "只点一个菜，味道清淡", "只点一个菜，够辣够味"],
     [(+H, -L), (+H, +L), (-H, -L), (-H, +L)]),

    ("a09", "换床单的话，你会挑哪种？", "rich", "warm",
     ["印花一套，偏冷的颜色", "印花一套，偏暖的颜色",
      "纯色一套，偏冷的颜色", "纯色一套，偏暖的颜色"],
     [(+H, -H), (+H, +H), (-H, -H), (-H, +H)]),

    ("a10", "出门前挑衣服，你手会伸向哪种？", "detailed", "vivid",
     ["纯色没图案，浅灰米白", "有印花有刺绣，浅灰米白",
      "纯色没图案，亮黄正红", "有印花有刺绣，亮黄正红"],
     [(-H, -H), (+H, -H), (-H, +H), (+H, +H)]),

    ("a12", "收纳箱你会买哪种？", "borderless", "modern",
     ["素色不印图案，最新款", "素色不印图案，老式样",
      "箱面全印满，最新款", "箱面全印满，老式样"],
     [(-H, +H), (-H, -H), (+H, +H), (+H, -H)]),

    ("a13", "窗帘你想挂哪种？", "detailed", "warm",
     ["带花边有装饰，灰蓝冷白", "带花边有装饰，米黄暖棕",
      "干干净净，灰蓝冷白", "干干净净，米黄暖棕"],
     [(+H, -H), (+H, +H), (-H, -H), (-H, +H)]),

    ("a14", "外套你会挑哪种？", "contrasty", "rich",
     ["黑白撞色，就一个颜色", "深浅接近，就一个颜色",
      "黑白撞色，好几个颜色拼", "深浅接近，好几个颜色拼"],
     [(+L, -H), (-L, -H), (+L, +H), (-L, +H)]),

    ("a15", "台灯你更想要哪种？", "bright", "modern",
     ["光柔柔的，新款的", "光很足很亮，新款的",
      "光柔柔的，老式样的", "光很足很亮，老式样的"],
     [(-L, +H), (+L, +H), (-L, -H), (+L, -H)]),

    ("a16", "挑双袜子，你会挑？", "borderless", "starart",
     ["满印花纹，很难碰到的花色", "满印花纹，满大街都有的",
      "素色没花纹，很难碰到的花色", "素色没花纹，满大街都有的"],
     [(+H, -H), (+H, +H), (-H, -H), (-H, +H)]),

    ("a17", "地毯你会挑哪种？", "contrasty", "warm",
     ["深浅差别很大，偏冷的色", "深浅差别很大，偏暖的色",
      "颜色很柔和，偏冷的色", "颜色很柔和，偏暖的色"],
     [(+L, -H), (+L, +H), (-L, -H), (-L, +H)]),

    ("a18", "你更常买哪种零食？", "modern", "rich",
     ["从小吃到大的，就一种口味", "新出的口味，就一种",
      "从小吃到大的，一堆口味", "新出的口味，一堆口味混着"],
     [(-H, -H), (+H, -H), (-H, +H), (+H, +H)]),

    ("a19", "杯子你想要哪种？", "borderless", "vivid",
     ["满印图案，颜色很浅", "满印图案，颜色很艳",
      "素面一个色，颜色很浅", "素面一个色，颜色很艳"],
     [(+H, -H), (+H, +H), (-H, -H), (-H, +H)]),

    ("a20", "手机壳你更在意哪种？", "bright", "starart",
     ["颜色亮亮的，随手就能买到", "颜色亮亮的，找半天才找到",
      "颜色暗暗的，随手就能买到", "颜色暗暗的，找半天才找到"],
     [(+L, +H), (+L, -H), (-L, +H), (-L, -H)]),

    ("a21", "买笔的话，你会挑哪种？", "contrasty", "modern",
     ["笔身一色，样子老派", "笔身一色，样子新潮",
      "笔杆深浅两截，样子老派", "笔杆深浅两截，样子新潮"],
     [(-L, -H), (-L, +H), (+L, -H), (+L, +H)]),

    ("a22", "拖鞋你会买哪种？", "borderless", "detailed",
     ["素面一双，什么装饰都没有", "素面一双，加了装饰",
      "鞋面全是图案，什么装饰都没加", "鞋面全是图案，还加了装饰"],
     [(-H, -H), (-H, +H), (+H, -H), (+H, +H)]),

    ("a23", "你会买哪种保温杯？", "rich", "starart",
     ["花色好几样，大家都买的爆款", "花色好几样，杂货店淘的",
      "就一种颜色，大家都买的爆款", "就一种颜色，杂货店淘的"],
     [(+H, +H), (+H, -H), (-H, +H), (-H, -H)]),

    ("a24", "牙膏你会挑哪种？", "bright", "vivid",
     ["包装亮亮的，颜色扎眼", "包装暗暗的，颜色扎眼",
      "包装亮亮的，颜色素净", "包装暗暗的，颜色素净"],
     [(+L, +H), (-L, +H), (+L, -H), (-L, -H)]),

    ("a25", "雨伞你更想要哪种？", "starart", "warm",
     ["焦糖暖棕，很少见到同款", "焦糖暖棕，到处都有人打",
      "水泥灰深蓝，很少见到同款", "水泥灰深蓝，到处都有人打"],
     [(-H, +H), (+H, +H), (-H, -H), (+H, -H)]),

    ("a26", "围巾你更在意哪种？", "contrasty", "detailed",
     ["颜色撞一起，光面的", "颜色搭得顺，光面的",
      "颜色撞一起，有流苏有花纹", "颜色搭得顺，有流苏有花纹"],
     [(+L, -H), (-L, -H), (+L, +H), (-L, +H)]),

    ("a27", "耳机你想要哪种？", "modern", "vivid",
     ["最新款式，颜色抢眼", "经典老款，颜色抢眼",
      "最新款式，颜色低调", "经典老款，颜色低调"],
     [(+H, +H), (-H, +H), (+H, -H), (-H, -H)]),
]

# 形态题：1 道多选题
FORM_Q = {
    "id": "b01",
    "q": "在奇幻世界里，你比较想和哪些存在成为伙伴？",
    "multi": True,
    "opts": [
        {"t": "一个普普通通的人", "form": "纯人类"},
        {"t": "类人形的奇异生物", "form": "变异人形"},
        {"t": "一头凶猛的巨兽", "form": "凶猛巨兽"},
        {"t": "说不清形状的扭曲造物", "form": "扭曲异形"},
        {"t": "一只毛茸茸的小家伙", "form": "可爱小兽"},
        {"t": "一台钢铁造物", "form": "机械构装"},
    ],
}


def main() -> int:
    q = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    old = {x["id"]: x for x in q["questions"]}
    out = []
    for qid, stem, ax1, ax2, texts, vals in BANK:
        o = []
        for t, (v1, v2) in zip(texts, vals):
            s = {}
            if v1:
                s[ax1] = v1
            if v2:
                s[ax2] = v2
            o.append({"t": t, "s": s})
        out.append({"id": qid, "q": stem, "opts": o})
    out.append(FORM_Q)
    # 形态题的选项先不带权重，由 solve_form_weights2 填
    q["questions"] = out
    q["_form_multi"] = True
    (DATA / "questions.json").write_text(
        json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"写入 {len(out)} 题（{len(out)-1} 审美 + 1 形态多选）\n")
    cnt = Counter()
    for x in out:
        for o in x["opts"]:
            for k in (o.get("s") or {}):
                cnt[k] += 1
    print("=== 每条轴的出现次数（必须全为偶数）===")
    for k, v in sorted(cnt.items()):
        print(f"  {k:<11} {v}　{'✓' if v % 2 == 0 else '✗ 奇数！'}")

    bad = []
    for x in out:
        if "multi" in x:
            continue
        per = Counter()
        for o in x["opts"]:
            for k, v in o["s"].items():
                per[k] += v
        for k, v in per.items():
            if abs(v) > 1e-9:
                bad.append((x["id"], k, round(v, 4)))
    print(f"\n每题每轴求和为 0：{'✓' if not bad else f'✗ {bad}'}")
    # 选项字数：口径**唯一来源** scripts/check_limits.json（汉字数，标点不计）。
    # 以前这里是 `len(o["t"]) > 16`（含标点），与 audit_questions.py / verify_questions.mjs
    # 的「12 汉字」不一致 —— 2026-10-13 统一成同一份口径。
    limits = json.loads((ROOT / "scripts" / "check_limits.json").read_text(encoding="utf-8"))
    max_han = int(limits["option_max_han"])
    han = lambda s: len(re.findall(r"[\u4e00-\u9fff]", s))          # noqa: E731
    over = [(x["id"], o["t"]) for x in out for o in x["opts"] if han(o["t"]) > max_han]
    print(f"选项超过 {max_han} 汉字的：{len(over)} 个")
    for qid, t in over[:8]:
        print(f"    {qid} {t}（{han(t)} 字）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
