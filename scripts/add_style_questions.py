# -*- coding: utf-8 -*-
"""把 9 道「画风题」（s01~s09）写进 data/questions.json，并把形态轴更名同步过来。

    python scripts/add_style_questions.py --check   # 只打印，不写
    python scripts/add_style_questions.py           # 写入（幂等）

设计约束（主 agent 给定，逐条守）：
  · 每题 4 选项、只挂 2 个 style_* 轴；
  · **每题每轴 2 正 2 负、四个选项等强、求和 = 0**（与 26 道审美题同口径）；
  · 单题权重只允许 0.6 / 1.2 两档（smoke_test.mjs 硬断言），瘦轴压到 0.6；
  · **每条轴恰好出现 2 次**（偶数次 = 位置残留「四列之和」归零的前提）；
  · 题干口语化、选项 ≤ 12 汉字、无万智牌/美术术语。
  · s01~s04 的**文案逐字照抄主 agent**，只按硬约束调轴值；s05~s09 为补齐 9 轴所加。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
QJSON = ROOT / "data" / "questions.json"

# 单题权重档：瘦轴（k = 0.2887/√(p(1−p)) > 1.25，即 p < 约 5.5%）压到 0.6，其余 1.2。
# 由 data/art_labels_v2.json 的实测 p 决定，见 scripts/add_style_axes.py 的输出。
TIER = {
    "style_神秘": 1.2, "style_史诗": 1.2, "style_黑暗": 1.2, "style_怪诞": 1.2,
    "style_激烈": 1.2, "style_温暖": 1.2, "style_宁静": 1.2,
    "style_可爱": 0.6,          # 池子里只有十几张 → 压低，别让选「可爱」的人被推到同一批图上
    "style_忧郁": 0.6,          # 同上，更瘦
}


def W(axis):
    return TIER[axis]


# 每道题：id / 题干 / 四个选项文本 / 每轴四个选项的符号（+1 = 正、−1 = 负）
STYLE_QUESTIONS = [
    dict(id="s01", q="你更爱看哪种片子？",
         opts=["从头笑到尾的轻松片", "大场面、气势足的", "看完心里沉一阵的", "热血又暖心的片子"],
         signs={"style_温暖": [+1, -1, -1, +1], "style_激烈": [-1, +1, -1, +1]}),
    dict(id="s02", q="晚上你更想听点什么？",
         opts=["热热闹闹的", "安安静静的", "带点神秘感的", "像睡前童话一样"],
         signs={"style_神秘": [-1, -1, +1, +1], "style_温暖": [-1, +1, -1, +1]}),
    dict(id="s03", q="同一段故事，你想听哪个版本？",
         opts=["讲得壮阔、有份量的", "讲得轻快、逗人笑的", "讲得阴森、后背发凉的", "讲得奇奇怪怪、不着调的"],
         signs={"style_史诗": [+1, -1, +1, -1], "style_怪诞": [-1, -1, +1, +1]}),
    dict(id="s04", q="你手机里存的表情包，多是哪种？",
         opts=["可爱小动物", "夸张搞笑的", "阴阳怪气的", "正经八百的"],
         signs={"style_可爱": [+1, +1, -1, -1], "style_怪诞": [-1, +1, +1, -1]}),
    dict(id="s05", q="周末你更想干什么？",
         opts=["打一场球，出一身汗", "窝在沙发看悬疑片", "半夜玩恐怖游戏", "躺着听歌发呆"],
         signs={"style_激烈": [+1, -1, +1, -1], "style_黑暗": [-1, +1, +1, -1]}),
    dict(id="s06", q="一个人待着时，你会？",
         opts=["翻旧箱子里的信", "一个人在窗边坐着", "看点没答案的怪谈", "刷点热闹的短视频"],
         signs={"style_神秘": [+1, -1, +1, -1], "style_忧郁": [+1, +1, -1, -1]}),
    dict(id="s07", q="电视剧你更想追哪种？",
         opts=["英雄一路打到最后", "小人物在泥里挣扎", "两个人日常过日子", "王国的最后一夜"],
         signs={"style_史诗": [+1, -1, -1, +1], "style_黑暗": [-1, +1, -1, +1]}),
    dict(id="s08", q="想刷哪种视频？",
         opts=["小奶猫打呼噜", "窗外慢慢下雨", "小动物追着玩", "一屋子人闹腾"],
         signs={"style_可爱": [+1, -1, +1, -1], "style_宁静": [+1, +1, -1, -1]}),
    dict(id="s09", q="睡前一小时，你会？",
         opts=["泡个澡，听点轻音乐", "找朋友吐槽两句", "一个人坐着，想点以前的事", "刷手机刷到困"],
         signs={"style_宁静": [+1, -1, +1, -1], "style_忧郁": [-1, +1, +1, -1]}),
]


def build_style_question(spec) -> dict:
    opts = []
    for i, t in enumerate(spec["opts"]):
        s = {ax: sign[i] * W(ax) for ax, sign in spec["signs"].items()}
        opts.append({"t": t, "s": s})
    return {"id": spec["id"], "q": spec["q"], "opts": opts}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="写入画风题 s01~s09")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    data = json.loads(QJSON.read_text(encoding="utf-8"))
    qs = data["questions"]

    # ---- ① 形态轴更名（幂等）----
    renamed = 0
    for q in qs:
        for o in q["opts"]:
            if "form_变异人形" in o.get("s", {}):
                o["s"]["form_人形异类"] = o["s"].pop("form_变异人形")
                renamed += 1
            if o.get("form") == "变异人形":
                o["form"] = "人形异类"
    print(f"形态轴更名：form_变异人形 → form_人形异类，共 {renamed} 个选项")

    # ---- ② 画风题插在形态多选题之前（模板里「前 N 道…最后 N 道多选」才仍然成立）----
    built = [build_style_question(s) for s in STYLE_QUESTIONS]
    by_id = {q["id"]: q for q in qs}
    for b in built:
        by_id[b["id"]] = b
    keep = [q for q in qs if q["id"] not in {b["id"] for b in built}]
    first_multi = next((i for i, q in enumerate(keep) if q.get("multi")), len(keep))
    out = keep[:first_multi] + built + keep[first_multi:]
    data["questions"] = out

    # ---- ③ 自检 ----
    print("\n每道画风题的轴 / 权重 / 正负：")
    bad = []
    for b in built:
        axes = sorted({k for o in b["opts"] for k in o["s"]})
        row = []
        for ax in axes:
            vals = [o["s"][ax] for o in b["opts"]]
            pos, neg = sum(1 for v in vals if v > 0), sum(1 for v in vals if v < 0)
            mags = {abs(v) for v in vals}
            if pos != 2 or neg != 2 or abs(sum(vals)) > 1e-9 or len(mags) != 1:
                bad.append((b["id"], ax, vals))
            if not (0.5 - 1e-9 <= max(mags) <= 2.0 + 1e-9):
                bad.append((b["id"], ax, "权重越界"))
            row.append(f"{ax}={'+' if vals[0] > 0 else '−'}{max(mags):.1f}"
                       f"({pos}正{neg}负,和{sum(vals):+.1f})")
        lens = [len([c for c in o["t"] if "\u4e00" <= c <= "\u9fff"]) for o in b["opts"]]
        print(f"  {b['id']}  {b['q']}  ｜ " + "  ".join(row) + f"  ｜ 选项汉字 {lens}")

    use = Counter()
    for q in out:
        if q.get("multi"):
            continue
        for k in {k for o in q["opts"] for k in o["s"] if k.startswith("style_")}:
            use[k] += 1
    print("\n9 个 style 轴的题数（必须全是偶数）：")
    for ax in TIER:
        n = use.get(ax, 0)
        flag = "✓" if n % 2 == 0 and n > 0 else ("✗ 奇数" if n % 2 else "✗ 没覆盖")
        print(f"  {ax:<10}{n} 题  权重 {TIER[ax]}  {flag}")
    # 位置残留：每轴四列之和
    print("\n每轴「四列之和」（应为 0）：")
    for ax in TIER:
        cols = [0.0] * 4
        for q in out:
            if q.get("multi"):
                continue
            for i, o in enumerate(q["opts"]):
                cols[i] += o["s"].get(ax, 0.0)
        print(f"  {ax:<10}" + "".join(f"{c:+7.1f}" for c in cols)
              + f"   和 {sum(cols):+.1f}")
        if abs(sum(cols)) > 1e-9:
            bad.append((ax, "四列之和不为 0", cols))

    if bad:
        print(f"\n✗ 自检失败 {len(bad)} 处：{bad[:4]}")
        return 1
    print(f"\n✓ 自检通过：{len(built)} 道画风题；题库共 {len(out)} 题"
          f"（{len([q for q in out if not q.get('multi')])} 单选 + "
          f"{len([q for q in out if q.get('multi')])} 多选）")

    if args.check:
        print("--check：没有写文件")
        return 0
    QJSON.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"✓ 已写回 {QJSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
