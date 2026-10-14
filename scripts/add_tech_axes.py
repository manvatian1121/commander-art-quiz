# -*- coding: utf-8 -*-
"""把 370 条「画法标注」做成 6 条画法轴（tech_*），写进 data/art_axes.json。

    python scripts/add_tech_axes.py                 # 默认读 data/art_style.json
    python scripts/add_tech_axes.py --check         # 只算不写

════════════════════════════════════════════════════════════════════════
与 style_*（mood 轴）的关系：**同一条推导，只是标签换了来源**
════════════════════════════════════════════════════════════════════════
形态轴是**单标签 one-hot**：每张图恰好一类 ⟹ 逐轴是 Bernoulli(p)，
    vec_g(x) = k_g·(1{x∈g} − p_g),   k_g = 0.2887/√(p_g(1−p_g))
（k 来自二项分布的方差：单个指示变量 1{x∈g} 的 SD 就是 √(p_g(1−p_g))。）

画法标注是**多标签**（一张图 1~2 个：370 条里 341 条 1 个 + 29 条 2 个）：
  · **次标必须计入**。逐轴看，第 a 条轴的原始量仍是 `1{该图有标签 a} − p_a`，
    依旧是一个 Bernoulli(p_a) 变量 —— 多标签只影响**轴与轴之间的协方差**
    （所以本脚本把实测相关矩阵也打出来），不影响**单轴的边际方差**。
  · ⚠️ 上一轮踩过的具体坑：`n=32` 的主标是卡通绘本、次标是二次元日系。
    只按「主标」统计会让**二次元日系少 1 条**（68 → 67），
    而 cosplay 到轴值上就是那一张图的二次元轴被写成负数 —— **界面完全看不出来**。
  · `水彩淡彩` 只有 6 张（p=1.6%）：轴照做、值照给，
    但**题目里不给它单独选项**（6 张凑不出三张不重复的主将，见 add_tech_questions.py）。

两处和形态轴不同、必须另外处理（与 add_style_axes.py 逐条一致）：
  ① **没有标注的图**：不写 −p_a（那等于断言「它一定不是这个画法」），取 **0**（中立）。
  ② 因为未知格取 0，若标注只覆盖池子的一部分，整池 SD 会掉到 0.2887·√(n_标注/N_池)，
     所以缩放系数里再乘 √(N_池/n_标注)。**本轮 370 张全覆盖 ⟹ 该因子 = 1.0。**
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import shutil
import sys
from collections import Counter
from datetime import datetime

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
AXES_JSON = DATA / "art_axes.json"
FORM_JSON = DATA / "art_form.json"
STYLE_JSON = DATA / "art_style.json"
BACKUP = ROOT / "backups"

# 轴名与顺序 = 交付口径（payload.axes / 模板 AXES / smoke_test 都按这个顺序追加）
TECH_NAMES = ["二次元日系", "欧美厚涂", "卡通绘本", "线稿版画", "写实数字绘", "水彩淡彩"]
TECH_AXES = ["tech_" + n for n in TECH_NAMES]
SD = 0.2887
K_TIER_CUT = 1.15          # k > 1.15（覆盖率 ≲ 6%）的轴压到 0.6 档，其余 1.2
#   只有水彩淡彩会越过这条线（k = 2.29）。它不出题，这一档只作登记。
NDIGITS = 4


def load_labels(path: pathlib.Path) -> dict[str, set[str]]:
    """→ {art_id: {画法, ...}}；兼容 list / {"items": list} / {"labels": list}。

    ⚠️ 多标签：`style` 是**列表**，`[0]` 是主标、`[1]`（若有）是次标，
    两个都要进集合 —— 少了次标就会少计（见模块 docstring）。
    """
    d = json.loads(path.read_text(encoding="utf-8"))
    items = d
    if isinstance(d, dict):
        for k in ("items", "labels", "data"):
            if isinstance(d.get(k), list):
                items = d[k]
                break
    out: dict[str, set[str]] = {}
    for x in items:
        aid = x.get("art_id") or x.get("id")
        if not aid:
            continue
        v = x.get("style") or x.get("styles") or []
        if isinstance(v, str):
            v = [v]
        out[aid] = {s for s in v if s}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成 6 条 tech_* 画法轴")
    ap.add_argument("--labels", default=str(STYLE_JSON))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    labels_path = pathlib.Path(args.labels)
    labels = load_labels(labels_path)
    arts = json.loads(AXES_JSON.read_text(encoding="utf-8"))
    form = json.loads(FORM_JSON.read_text(encoding="utf-8"))
    ok_ids = {r["art_id"] for r in form if not r.get("excluded")}
    live = [a for a in arts if not a.get("excluded") and a["art_id"] in ok_ids]
    N = len(live)
    labeled = [a for a in live if labels.get(a["art_id"])]
    n_L = len(labeled)

    unknown_names = sorted({s for v in labels.values() for s in v} - set(TECH_NAMES))
    if unknown_names:
        print(f"✗ 标注里出现了不认识的画法：{unknown_names}", file=sys.stderr)
        return 1
    orphan = sorted(set(labels) - {a["art_id"] for a in arts})
    if orphan:
        print(f"⚠ 标注里有 {len(orphan)} 个 art_id 不在 art_axes.json 里：{orphan[:3]}")

    multi = sum(1 for a in labeled if len(labels[a["art_id"]]) > 1)
    print(f"标注文件 {labels_path.name}：{len(labels)} 条（多标签 {multi} 条）；"
          f"参与池 {N} 张，其中 {n_L} 张有画法（未知 {N - n_L} 张）")

    # ---- 逐轴：p / k / 缩放 ----
    scale_fix = math.sqrt(N / n_L) if n_L else 0.0
    stats = {}
    print(f"\n{'轴':<12}{'张数':>6}{'p':>10}{'k=SD⁻¹':>11}{'覆盖修正':>10}{'k_eff':>10}"
          f"{'本轴取值':>10}{'其它取值':>10}{'轴间分差':>10}{'权重档':>8}")
    for name in TECH_NAMES:
        cnt = sum(1 for a in labeled if name in labels[a["art_id"]])
        p = cnt / n_L if n_L else 0.0
        k = SD / math.sqrt(p * (1 - p)) if 0 < p < 1 else 0.0
        k_eff = k * scale_fix
        tier = 0.6 if k > K_TIER_CUT else 1.2
        stats[name] = {"cnt": cnt, "p": p, "k": k, "k_eff": k_eff, "tier": tier}
        own, other = k_eff * (1 - p), -k_eff * p
        print(f"tech_{name:<7}{cnt:>6}{p:>10.4f}{k:>11.4f}{scale_fix:>10.4f}{k_eff:>10.4f}"
              f"{own:>10.4f}{other:>10.4f}{own - other:>10.4f}{tier:>8.1f}")
    print("  （k_eff = k × √(N_池/n_标注)；张数按**主标+次标**计；最后一列 = 单题权重 1.2 时"
          "该类图与其它图的得分差 ×1.2 前的原值）")

    # ---- 写回 vec ----
    for a in arts:
        vec = {kk: vv for kk, vv in a["vec"].items() if not kk.startswith("tech_")}
        tags = labels.get(a["art_id"]) if a["art_id"] in ok_ids else None
        for name in TECH_NAMES:
            st = stats[name]
            if not tags:                       # 未知 → 中立 0
                vec["tech_" + name] = 0.0
            else:
                hit = 1.0 if name in tags else 0.0
                vec["tech_" + name] = round((hit - st["p"]) * st["k_eff"], NDIGITS)
        a["vec"] = vec
    print(f"\n已把 {len(TECH_AXES)} 条 tech_* 轴写进内存（每张图现在 "
          f"{len(arts[0]['vec'])} 条轴）")

    # ---- 验收 ①：均值 / SD（统计范围＝参与池）----
    print(f"\n实测（统计范围＝参与池 {N} 张；文件里存的是 4 位小数）")
    print(f"  {'轴':<11}{'均值':>12}{'SD':>12}{'SD-0.2887':>12}{'最小':>10}{'最大':>10}")
    worst_m = worst_s = 0.0
    for name in TECH_NAMES:
        v = np.array([a["vec"]["tech_" + name] for a in live], dtype=float)
        m, s = float(v.mean()), float(v.std(ddof=0))
        worst_m, worst_s = max(worst_m, abs(m)), max(worst_s, abs(s - SD))
        print(f"  tech_{name:<6}{m:>12.6f}{s:>12.6f}{s - SD:>12.6f}{v.min():>10.4f}{v.max():>10.4f}")
    tol = 1e-4 if n_L == N else 5e-3
    print(f"  6 条轴实测：|均值| 最大 {worst_m:.6f}，|SD-0.2887| 最大 {worst_s:.6f}"
          f"（容差 {tol:g}）  {'✓' if worst_m < tol and worst_s < tol else '✗'}")
    if worst_m >= tol or worst_s >= tol:
        return 1

    # ---- 验收 ②：每张图的「正值集合」必须正好等于它的标注集合（次标也在内）----
    bad = []
    for a in live:
        tags = labels.get(a["art_id"]) or set()
        pos = {n for n in TECH_NAMES if a["vec"]["tech_" + n] > 0}
        if pos != set(tags):
            bad.append((a["art_id"], sorted(tags), sorted(pos)))
    print(f"  每张图的正值轴 == 标注集合（含次标）："
          f"{'✓' if not bad else f'✗ {len(bad)} 张对不上，例如 {bad[:2]}'}")
    if bad:
        return 1

    # ---- 实测相关（多标签特有：同一张图的两个标签会把两条轴拉成正相关）----
    M = np.array([[a["vec"]["tech_" + n] for n in TECH_NAMES] for a in live])
    C = np.corrcoef(M.T)
    off = [(TECH_NAMES[i], TECH_NAMES[j], C[i, j])
           for i in range(len(TECH_NAMES)) for j in range(i + 1, len(TECH_NAMES))]
    top = sorted(off, key=lambda t: -abs(t[2]))[:5]
    print("\n轴间相关（多标签的正相关是正常的；单标签 one-hot 之间只会是负相关）")
    print("  |r| 最大的 5 对：" + "，".join(f"{a}×{b} {r:+.3f}" for a, b, r in top))
    print(f"  6×6 非对角元 |r| 中位数 {np.median([abs(r) for _, _, r in off]):.3f}；"
          f"最大 {max(abs(r) for _, _, r in off):.3f}")

    # ---- 与 style_* 的交叉相关（复核「画法」不是「画风」的复读机）----
    q = json.loads(AXES_JSON.read_text(encoding="utf-8"))
    style_names = [k[6:] for k in q[0]["vec"] if k.startswith("style_")]
    if style_names:
        Ms = np.array([[a["vec"]["style_" + n] for n in style_names] for a in live])
        X = np.corrcoef(M.T, Ms.T)[:len(TECH_NAMES), len(TECH_NAMES):]
        pairs = sorted(((TECH_NAMES[i], style_names[j], X[i, j])
                        for i in range(len(TECH_NAMES)) for j in range(len(style_names))),
                       key=lambda t: -abs(t[2]))[:5]
        print("\n与 9 条 style_* 画风轴的交叉相关（|r| 最大的 5 对）")
        print("  " + "，".join(f"{a}×{b} {r:+.3f}" for a, b, r in pairs))
        print("  （高相关说明这两组标签在语义上有重叠，交付时一并报出；不改变轴值算法）")

    # ---- 题档建议 ----
    print("\n题库权重档建议（写进 scripts/add_tech_questions.py 的 TIER）")
    for name in TECH_NAMES:
        st = stats[name]
        note = "" if st["tier"] == 1.2 else "   ← 只有 6 张，**不出题**（只登记档位）"
        print(f"  tech_{name:<4} p={st['p']:.4f}  k={st['k']:.3f}  →  {st['tier']}{note}")

    print("\n各画法的标签组合（主标+次标逐条计数）")
    for combo, n in Counter(tuple(sorted(labels[a["art_id"]])) for a in labeled).most_common():
        print(f"  {'+'.join(combo):<24}{n:>4} 张")

    if args.check:
        print("\n--check：没有写文件")
        return 0
    BACKUP.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(AXES_JSON, BACKUP / f"art_axes.json.{stamp}.pre-techaxes.bak")
    AXES_JSON.write_text(json.dumps(arts, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✓ 已写回 {AXES_JSON}（备份在 backups/）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
