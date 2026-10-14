# -*- coding: utf-8 -*-
"""交付自检：题干/选项里的美术术语、万智牌术语、字数、结构。

    python scripts/audit_questions.py

从 2026-10-13（第二版）起题库是 **26 道单选审美题 + 3 道形态多选题（b01/b02/b03）**：
  · 单选题走 2×2 四角：4 选项、每题 2 轴、每轴 2 正 2 负、和 = 0；
  · 多选题：N 个选项，每个选项只挂自己那一类 form_*（可以任意勾选，
    所以**没有**「2 正 2 负 / 和 = 0」这回事，不能拿单选的口径去套）；
  · 三道形态题的**选项文本各不相同、排列顺序也两两不同**（0/1/3 左旋）。

选项字数口径是**唯一来源** scripts/check_limits.json —— 以前这里写 12 汉字、
rewrite_bank_manual.py 写 len(文本) > 16（含标点），两处口径不一致；现已统一。
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
Q = json.loads((ROOT / "data" / "questions.json").read_text(encoding="utf-8"))["questions"]
# 选项汉字数上限：唯一来源 scripts/check_limits.json
LIMITS = json.loads((ROOT / "scripts" / "check_limits.json").read_text(encoding="utf-8"))
MAX_HAN = int(LIMITS["option_max_han"])

BAD = ["卡牌", "牌面", "主将", "生物", "法术", "扩画", "插画",
       "构图", "画风", "画法", "画师", "画作", "画面",
       "调子", "色调", "色相", "浓艳", "素雅", "明暗", "反差",
       "光影", "暗部", "留白", "笔触", "质感", "氛围", "风格",
       "想象", "脑补", "回忆", "艺术", "审美", "饱和", "鲜艳",
       "细腻", "繁复", "极简", "复古", "对比度", "饱和度"]
# 多选题里按设计必须出现的词（要描述「伙伴/存在」是什么，绕不开生物类名词）
# 口径同旧版的「形态题的『画面』按设计保留」：只豁免多选题的选项，题干照查。
MULTI_OK = {"生物"}
SINGLE_OPTS = 4

SINGLE = [q for q in Q if not q.get("multi")]
MULTI = [q for q in Q if q.get("multi")]

print(f"题库：{len(Q)} 题 = {len(SINGLE)} 单选 + {len(MULTI)} 多选"
      f"（{'、'.join(q['id'] for q in MULTI)}）")
print(f"选项字数口径：scripts/check_limits.json → 汉字数 ≤ {MAX_HAN}"
      f"（标点/字母/数字不计）")

print(f"\n① 题干里的禁用词（多选题选项里的 {sorted(MULTI_OK)} 按设计保留）")
hits = 0
for q in Q:
    for w in BAD:
        if w in q["q"]:
            hits += 1
            print(f"   ⚠ 要改  {q['id']} 「{w}」  {q['q']}")
print(f"   需要处理的：{hits} 处")

print("\n② 选项里的禁用词 / 超长")
bad_opt = 0
for q in Q:
    for o in q["opts"]:
        for w in BAD:
            if w in o["t"]:
                if w in MULTI_OK and q.get("multi"):
                    print(f"   · 保留  {q['id']} 选项「{o['t']}」含「{w}」（多选题按设计保留）")
                    continue
                bad_opt += 1
                print(f"   ⚠ 要改  {q['id']} 选项「{o['t']}」含「{w}」")
        n = len(re.findall(r"[\u4e00-\u9fff]", o["t"]))
        if n > MAX_HAN:
            bad_opt += 1
            print(f"   ⚠ 超长  {q['id']} 选项「{o['t']}」{n} 字（上限 {MAX_HAN}）")
print(f"   问题数：{bad_opt}")

print("\n③ 单选题结构（4 选项 / 2 轴 / 2 正 2 负 / 求和 0）")
ok = True
for q in SINGLE:
    axes: dict[str, list[float]] = {}
    for o in q["opts"]:
        for k, v in (o.get("s") or {}).items():
            axes.setdefault(k, []).append(v)
    if len(q["opts"]) != SINGLE_OPTS:
        ok = False
        print(f"   ⚠ {q['id']} 有 {len(q['opts'])} 个选项，应为 {SINGLE_OPTS}")
    if len(axes) != 2:
        ok = False
        print(f"   ⚠ {q['id']} 挂了 {len(axes)} 个轴，应为 2：{sorted(axes)}")
    for k, vals in axes.items():
        vals = vals + [0.0] * (SINGLE_OPTS - len(vals))
        pos = len([v for v in vals if v > 0])
        neg = len([v for v in vals if v < 0])
        if pos != 2 or neg != 2 or abs(sum(vals)) > 1e-9:
            ok = False
            print(f"   ⚠ {q['id']} {k}: 正 {pos} 负 {neg} 和 {sum(vals)}")
print(f"   {len(SINGLE)} 道单选题全部满足 4 选项 / 2 轴 / 2 正 2 负 / 求和 0"
      if ok else "   有问题")

print("\n④ 多选题结构（每个选项只挂自己那一类，权重在同一条数量级上）")
if not MULTI:
    print("   （题库里没有多选题）")
for q in MULTI:
    seen: dict[str, str] = {}
    ws: list[float] = []
    for i, o in enumerate(q["opts"]):
        s = o.get("s") or {}
        ks = [k for k in s if k.startswith("form_")]
        if len(s) != 1 or len(ks) != 1:
            print(f"   ⚠ {q['id']} 第 {i + 1} 项挂了 {sorted(s)}，应当恰好 1 个 form_* 轴")
            continue
        k = ks[0]
        if k in seen:
            print(f"   ⚠ {q['id']} 的 {k} 被挂在多个选项上（{seen[k]} 与第 {i + 1} 项）")
        seen[k] = f"第 {i + 1} 项"
        v = s[k]
        ws.append(v)
        if v <= 0:
            print(f"   ⚠ {q['id']} 的 {k} 权重 {v} 不是正的")
        if o.get("form") and "form_" + o["form"] != k:
            print(f"   ⚠ {q['id']} 第 {i + 1} 项标了 form={o['form']}，却挂着 {k}")
    if ws:
        print(f"   {q['id']}：{len(q['opts'])} 个选项 / {len(seen)} 个形态轴；"
              f"权重 {min(ws):.2f} ~ {max(ws):.2f}（极差 {max(ws) - min(ws):.2f}）")
        print(f"   形态轴清单：" + "、".join(sorted(k[5:] for k in seen)))

# 三道形态题的顺序必须是三种不同排列 —— 否则位置偏置会集中在同一批形态上
if len(MULTI) >= 2:
    print("\n④b 形态多选题的选项顺序（0/1/3 左旋；两两不同 + 七类都能进前四位）")
    for q in MULTI:
        order = [o.get("form") for o in q["opts"]]
        print(f"   {q['id']}：" + " / ".join(f"{i + 1}.{f}" for i, f in enumerate(order)))
    keys = ["/".join(str(o.get("form")) for o in q["opts"]) for q in MULTI]
    print(f"   两两不同：{'✓' if len(set(keys)) == len(keys) else '✗ 有重复的形态序列'}")
    cover: dict[str, int] = {}
    for q in MULTI:
        for o in q["opts"][:4]:
            cover[o.get("form")] = cover.get(o.get("form"), 0) + 1
    zero = sorted(f for f in cover if cover[f] == 0)
    all_forms = sorted({o.get("form") for q in MULTI for o in q["opts"]})
    miss = [f for f in all_forms if cover.get(f, 0) == 0]
    print("   「前 4 位」覆盖：" + "  ".join(f"{f}×{cover.get(f, 0)}" for f in all_forms))
    print(f"   七个形态都能被「只勾前四项」的人扫到：{'✓' if not miss else '✗ ' + '、'.join(miss)}")
    for pos in range(4):
        col = [q["opts"][pos].get("form") for q in MULTI]
        if len(set(col)) != len(col):
            print(f"   ⚠ 第 {pos + 1} 位被同一形态占了多次：{'/'.join(col)}")
    del zero

print("\n⑤ 题量与选项长度")
lens = [len(re.findall(r"[\u4e00-\u9fff]", o["t"])) for q in Q for o in q["opts"]]
print(f"   题数 {len(Q)}（审美 {len(SINGLE)} + 形态 {len(MULTI)}）；"
      f"选项 {len(lens)} 个，汉字数 最长 {max(lens)} / 平均 {sum(lens) / len(lens):.1f}"
      f"（口径上限 {MAX_HAN}）")
longest = max((len(re.findall(r"[\u4e00-\u9fff]", o["t"])), q["id"], o["t"])
              for q in Q for o in q["opts"])
print(f"   最长那条：{longest[1]}「{longest[2]}」{longest[0]} 字")
