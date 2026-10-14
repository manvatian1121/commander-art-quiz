# -*- coding: utf-8 -*-
"""把 4 道「画法题」（t01~t04）写进 data/questions.json。

    python scripts/add_tech_questions.py --check   # 只打印，不写
    python scripts/add_tech_questions.py           # 写入（幂等）

设计约束（任务书给定，逐条守；模式照 add_style_questions.py）：
  · 每题 4 选项、只挂 2 个 tech_* 轴；
  · **每题每轴 2 正 2 负、四个选项等强、求和 = 0**（与 26 道审美题 / 9 道画风题同口径）；
  · 单题权重只允许 0.6 / 1.2 两档（smoke_test.mjs 硬断言），瘦轴压到 0.6；
  · 题干口语化、选项 ≤ 12 汉字（口径来自 scripts/check_limits.json）、无美术术语；
  · **画法可以直接问**（「你喜欢哪种」是常识问题），不必像「明暗反差」那样绕生活场景。

═══ 5 条轴怎么被 5 道题覆盖：链 → 环（2026-10-14 裁定后定稿）═══
「每类出现偶数次」+「5 类」⟹ 最少 10 个轴位；**5 题 × 每题 2 轴 = 10 个轴位，正好**
—— 在 5 个顶点上做 2-正则图，解就是一个 **5-环**（每类恰好 2 次）。

    t01 写实数字绘—线稿版画    t02 线稿版画—二次元日系    t03 二次元日系—卡通绘本
    t04 卡通绘本—欧美厚涂      t05 欧美厚涂—写实数字绘   ← 收口的那条边

* 第一版只做了 4 题（8 个轴位），是一条**链**：首尾两条边缺失，
  ⟹ `欧美厚涂` / `写实数字绘` 各只出现 1 次（满偏 1.2，其余 2.4），
  且逐列残留不是「每列 #正 = #负」的形状。**4 题覆盖 5 类时这不可避免**（鸽子洞）。
* 补上第 5 题成环之后：**五类各 2 题、满偏一律 2.4、奇偶性全过**，
  逐列残留五条全同形（实测 `+2.4 / 0 / 0 / −2.4`，与 9 条画风轴同形），
  整块 6 条 tech 轴的合力 = (12.0, 0, 0, −12.0)。
* 新题的两条轴挑了池子里**最大的两类**（欧美厚涂 109、写实数字绘 86）——这两类的
  k 最小（0.633 / 0.684），本来最该被补足推力，正好由这道收口题补上。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
QJSON = ROOT / "data" / "questions.json"
LIMITS = json.loads((ROOT / "scripts" / "check_limits.json").read_text(encoding="utf-8"))
MAX_HAN = int(LIMITS["option_max_han"])

# 单题权重档。5 条出题的轴 k 都在 0.63~0.82（< 1.15）→ 全用 1.2。
# 水彩淡彩 k=2.286 登记为 0.6 档，但**它不出题**（池里只有 6 张，凑不出 3 张不重复的主将）。
TIER = {
    "tech_二次元日系": 1.2, "tech_欧美厚涂": 1.2, "tech_卡通绘本": 1.2,
    "tech_线稿版画": 1.2, "tech_写实数字绘": 1.2,
    "tech_水彩淡彩": 0.6,          # ← 只登记，不出题（见模块 docstring）
}
NO_OPTION = ["tech_水彩淡彩"]      # 不给单独选项的轴

# 轴归属：RD=写实数字绘 LP=线稿版画 AN=二次元日系 CB=卡通绘本 WE=欧美厚涂
# 5 个顶点上的 2-正则图 = 5-环 ⟹ 每类恰好 2 次、10 个轴位不多不少。
# 每条相邻配对都是语义上真能分得清的两种画法（线 vs 色块 vs 笔触 vs 照片感）。
# 选项顺序统一是 2×2 叉乘：(+,+) (+,-) (-,+) (-,-) ⟹ axis1 符号 [+,+,-,-]、
#   axis2 符号 [+,-,+,-]，每条轴自然 2 正 2 负、和 = 0。
TECH_QUESTIONS = [
    dict(id="t01", q="下面几种感觉，你更想看到哪种？",
         opts=["干净写实、线条也清楚", "干净写实、看不到线条",
               "线条很重、像老版画", "颜色糊成一片、像水彩"],
         axes=["tech_写实数字绘", "tech_线稿版画"]),
    dict(id="t02", q="线条这方面，你更喜欢哪种？",
         opts=["线条重、像老漫画", "线条重、黑白分明",
               "线条细、颜色很亮", "没什么线条、大片颜色"],
         axes=["tech_线稿版画", "tech_二次元日系"]),
    dict(id="t03", q="你更想看到哪种角色？",
         opts=["动漫风、颜色大块", "动漫风、画得细致",
               "像儿童画册、圆圆的", "像照片或油画那种"],
         axes=["tech_二次元日系", "tech_卡通绘本"]),
    dict(id="t04", q="上色的感觉，你更喜欢哪种？",
         opts=["大色块、又有油画感", "大色块、像儿童绘本",
               "油画感、颜色堆得厚", "颜色淡淡的、像水彩"],
         axes=["tech_卡通绘本", "tech_欧美厚涂"]),
    # 收口题：把链接成环（欧美厚涂 × 写实数字绘）。题干换一个角度：不重复
    # 「你更想看到哪种」/「线条这方面」/「上色的感觉」，问放大之后的观感
    # —— 厚涂是看得见颜料层的，写实数字绘是干净无痕的，正好对上两条轴。
    dict(id="t05", q="把一张画放大看，你更想看到什么？",
         opts=["像真的一样，看得出手工", "颜料一层层堆上去",
               "干净得像照片一样", "颜色平平的、像贴纸"],
         axes=["tech_欧美厚涂", "tech_写实数字绘"]),
]
# 美术术语 / 万智牌术语的禁用词（口径与 audit_questions.py 一致；这里只做提交前自检，
# 真正的闸门是 scripts/audit_questions.py）
BANNED = ["赛璐璐", "平涂", "厚涂", "渲染", "画风", "画法", "笔触", "质感", "构图",
          "色彩", "色调", "明暗", "反差", "饱和度", "插画", "主将", "卡牌", "审美"]


def build_question(spec) -> dict:
    """2×2 叉乘：选项 i 的符号 = (axis1[i], axis2[i])，取自 SIGN 表。"""
    sign = [(+1, +1), (+1, -1), (-1, +1), (-1, -1)]
    opts = []
    for i, t in enumerate(spec["opts"]):
        opts.append({"t": t,
                     "s": {ax: sign[i][j] * TIER[ax] for j, ax in enumerate(spec["axes"])}})
    return {"id": spec["id"], "q": spec["q"], "opts": opts}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="写入画法题 t01~t04")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    data = json.loads(QJSON.read_text(encoding="utf-8"))
    qs = data["questions"]
    built = [build_question(s) for s in TECH_QUESTIONS]

    # ---- 插入到形态多选题之前（模板里「前 N 道单选 + 最后 N 道多选」才仍然成立）----
    by_id = {q["id"]: q for q in built}
    keep = [q for q in qs if q["id"] not in by_id]
    first_multi = next((i for i, q in enumerate(keep) if q.get("multi")), len(keep))
    out = keep[:first_multi] + built + keep[first_multi:]
    data["questions"] = out

    # ---- 自检：逐题 ----
    bad = []
    print(f"每题轴 / 权重 / 正负（选项汉字数上限 {MAX_HAN}，来自 check_limits.json）：")
    for b in built:
        axes = sorted({k for o in b["opts"] for k in o["s"]})
        if len(axes) != 2:
            bad.append((b["id"], f"挂了 {len(axes)} 个轴"))
        if len(b["opts"]) != 4:
            bad.append((b["id"], f"{len(b['opts'])} 个选项"))
        row = []
        for ax in axes:
            vals = [o["s"][ax] for o in b["opts"]]
            pos, neg = sum(1 for v in vals if v > 0), sum(1 for v in vals if v < 0)
            mags = {abs(v) for v in vals}
            if pos != 2 or neg != 2 or abs(sum(vals)) > 1e-9 or len(mags) != 1:
                bad.append((b["id"], ax, vals))
            if not (0.5 - 1e-9 <= max(mags) <= 2.0 + 1e-9):
                bad.append((b["id"], ax, "权重越界"))
            if max(mags) not in (0.6, 1.2):
                bad.append((b["id"], ax, f"权重档 {max(mags)} 不是 0.6/1.2"))
            if ax in NO_OPTION:
                bad.append((b["id"], f"{ax} 按口径不许出现在题目里"))
            row.append(f"{ax}={'+' if vals[0] > 0 else '−'}{max(mags):.1f}"
                       f"({pos}正{neg}负,和{sum(vals):+.1f})")
        for t in b["opts"]:
            hit = [w for w in BANNED if w in t["t"]]
            if hit:
                bad.append((b["id"], f"选项含禁用词 {hit}：{t['t']}"))
        lens = [len(re.findall(r"[\u4e00-\u9fff]", o["t"])) for o in b["opts"]]
        if max(lens) > MAX_HAN:
            bad.append((b["id"], f"选项最长 {max(lens)} 字 > {MAX_HAN}"))
        print(f"  {b['id']}  「{b['q']}」")
        for o, n in zip(b["opts"], lens):
            print(f"        {n:>2} 字  {o['t']:<12}"
                  + "  ".join(f"{k}={v:+.1f}" for k, v in sorted(o["s"].items())))
        print("      ｜ " + "  ".join(row))

    # ---- 自检：题数与偶数性 ----
    use = Counter()
    for q in out:
        if q.get("multi"):
            continue
        for k in {k for o in q["opts"] for k in o["s"] if k.startswith("tech_")}:
            use[k] += 1
    print("\n各 tech 轴的题数与位置残留（都从题库现算）：")
    print(f"  {'轴':<16}{'题数':>5}{'满偏':>8}{'第1项':>8}{'第2项':>8}{'第3项':>8}"
          f"{'第4项':>8}{'四列之和':>10}  偶数")
    for ax in TIER:
        cols = [0.0] * 4
        smax = 0.0                     # 满偏：每题都挑对该轴最有利的那一项
        for q in out:
            if q.get("multi"):
                continue
            top = 0.0
            for i, o in enumerate(q["opts"]):
                cols[i] += o["s"].get(ax, 0.0)
                top = max(top, o["s"].get(ax, 0.0))
            smax += top
        n = use.get(ax, 0)
        even = "✓" if n % 2 == 0 else "✗ 奇数"
        note = ""
        if n == 0:
            note = "   ← 按口径不出题（只有 6 张）" if ax in NO_OPTION else "   ← 没覆盖！"
            even = "✓" if ax in NO_OPTION else "✗ 没覆盖"
        print(f"  {ax:<16}{n:>5}{smax:>8.1f}"
              + "".join(f"{c:>+8.1f}" for c in cols)
              + f"{sum(cols):>10.1f}  {even}{note}")
        if abs(sum(cols)) > 1e-9:
            bad.append((ax, "四列之和不为 0", cols))
        # 5 题 × 2 轴 = 10 个轴位 = 5 类 × 2 次 ⟹ 出题的轴**必须**是偶数次（硬约束）。
        if n % 2 and ax not in NO_OPTION:
            bad.append((ax, f"出现 {n} 次（奇数）—— 5 题 × 2 轴 = 10 轴位覆盖 5 类，"
                            f"应当每类恰好 2 次"))
        if n and abs(smax - 1.2 * n) > 1e-9:
            bad.append((ax, f"满偏 {smax} != 1.2 × {n}"))
    covered = [ax for ax in TIER if use.get(ax, 0) > 0 and ax not in NO_OPTION]
    print(f"\n  出题的画法 {len(covered)}/5：{'、'.join(covered)}"
          f"（每条恰好 2 题、满偏 2.4）；不出题的：{'、'.join(NO_OPTION)}（池里 6 张）")
    print(f"  轴位总数 {sum(use.values())} = {len(TECH_QUESTIONS)} 题 × 2 轴"
          f" = 5 类 × 2 次 ✓（链 → 环：t01→t02→t03→t04→t05→t01）")

    if bad:
        print(f"\n✗ 自检失败 {len(bad)} 处：{bad[:4]}")
        return 1
    n_single = len([q for q in out if not q.get("multi")])
    n_multi = len([q for q in out if q.get("multi")])
    print(f"\n✓ 自检通过：{len(built)} 道画法题；题库共 {len(out)} 题"
          f"（{n_single} 单选 + {n_multi} 多选）")

    if args.check:
        print("--check：没有写文件")
        return 0
    QJSON.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"✓ 已写回 {QJSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
