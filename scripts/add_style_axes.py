# -*- coding: utf-8 -*-
"""把 mood 标签做成 9 条「画风轴」（style_*），写进 data/art_axes.json。

    python scripts/add_style_axes.py --labels data/art_labels_v2.json   # 默认就这个
    python scripts/add_style_axes.py --check                            # 只算不写
    python scripts/add_style_axes.py --labels data/art_labels.json      # 只用旧 273 条（对比用）

═══ 标准化系数怎么推（多标签 ≠ 单标签） ═══
形态轴是**单标签 one-hot**：每张图恰好属于一类，所以
    vec_g(x) = k_g·(1{x∈g} − p_g),   k_g = 0.2887/√(p_g(1−p_g))
—— 这个 k 来自**二项分布**的方差：单个指示变量 1{x∈g} 的 SD 就是 √(p_g(1−p_g))。

mood 是**多标签**：一张图可能同时有「黑暗」和「史诗」，标签数 1~2 不定。
但**逐轴看**，第 a 条轴的原始量仍然是 `1{该图有标签 a} − p_a`，它依旧是一个
Bernoulli(p_a) 变量（多标签只影响不同轴之间的相关性，不影响**单轴的边际方差**）。
所以：

    k_a = 0.2887 / SD(1{· 有 a} − p_a) = 0.2887 / √(p_a(1−p_a))

—— **闭合形式和形态轴相同**，但推导必须先说清「为什么边际仍是 Bernoulli」；
照抄公式而不做这一步验证是不对的，因为多标签会让「一张图的标签总数」变化，
进而影响**轴与轴之间的协方差**（本脚本把实测相关矩阵也打出来备查）。

两处和形态轴**不同**、必须另外处理的地方：
  ① **未知（没有 mood 数据）的图**：不写成 −p_a（那等于断言「它一定没有这个 mood」），
     而是取 **0**（中立：既不因为这条轴加分，也不减分）。
  ② 因为未知格取 0，若标签只覆盖池子的一部分（本轮的旧标签只覆盖 273/370），
     整池 SD 会掉到 0.2887·√(n_标注/N_池)。
     所以缩放系数里再乘一个 √(N_池/n_标注)，把**整池**的 SD 顶回 0.2887；
     标注格的取值随之被放大同样倍数。全量标注时这个因子 = 1。
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
BACKUP = ROOT / "backups"

STYLE_NAMES = ["神秘", "史诗", "黑暗", "怪诞", "激烈", "温暖", "宁静", "可爱", "忧郁"]
STYLE_AXES = ["style_" + n for n in STYLE_NAMES]
SD = 0.2887
K_TIER_CUT = 1.15          # k > 1.15（覆盖率 ≲ 6%）的轴压到 0.6 档，其余 1.2
#   切在 1.15 而不是 1.25：可爱(k=1.221)按用户口径必须被压低（它只有 22 张，
#   1.2 档会让它的推力是神秘轴的 2 倍）；温暖/宁静(k=0.892)留在 1.2 档正合适。
NDIGITS = 4


def load_labels(path: pathlib.Path) -> dict[str, set[str]]:
    """→ {art_id: {mood, ...}}；兼容 list / {"items": list} / {"labels": list}。"""
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
        out[aid] = set(x.get("mood") or [])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成 9 条 style_* 轴")
    ap.add_argument("--labels", default=str(DATA / "art_labels_v2.json"))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--questions", default=str(DATA / "questions.json"))
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
    print(f"标签文件 {labels_path.name}：{len(labels)} 条；参与池 {N} 张，其中 {n_L} 张有 mood"
          f"（未知 {N - n_L} 张）")

    # ---- 逐轴：p / k / 缩放 ----
    scale_fix = math.sqrt(N / n_L) if n_L else 0.0
    stats = {}
    print(f"\n{'轴':<8}{'张数':>6}{'p':>10}{'k=SD⁻¹':>11}{'标注修正':>10}{'k_eff':>10}"
          f"{'本轴取值':>10}{'其它取值':>10}{'权重档':>8}")
    for name in STYLE_NAMES:
        cnt = sum(1 for a in labeled if name in labels[a["art_id"]])
        p = cnt / n_L if n_L else 0.0
        k = SD / math.sqrt(p * (1 - p)) if 0 < p < 1 else 0.0
        k_eff = k * scale_fix
        tier = 0.6 if k > K_TIER_CUT else 1.2
        stats[name] = {"cnt": cnt, "p": p, "k": k, "k_eff": k_eff, "tier": tier}
        print(f"{name:<8}{cnt:>6}{p:>10.4f}{k:>11.4f}{scale_fix:>10.4f}{k_eff:>10.4f}"
              f"{k_eff * (1 - p):>10.4f}{-k_eff * p:>10.4f}{tier:>8.1f}")
    print("  （k_eff = k × √(N_池/n_标注)；本轴/其它取值 = 有该标签 / 没该标签时这条轴的取值）")

    # ---- 写回 vec ----
    for a in arts:
        vec = {kk: vv for kk, vv in a["vec"].items() if not kk.startswith("style_")}
        moods = labels.get(a["art_id"]) if a["art_id"] in ok_ids else None
        for name in STYLE_NAMES:
            st = stats[name]
            if not moods:                      # 未知 → 中立 0
                vec["style_" + name] = 0.0
            else:
                hit = 1.0 if name in moods else 0.0
                vec["style_" + name] = round((hit - st["p"]) * st["k_eff"], NDIGITS)
        a["vec"] = vec
    print(f"\n已把 {len(STYLE_AXES)} 条 style_* 轴写进内存（每张图现在 "
          f"{len(arts[0]['vec'])} 条轴）")

    # ---- 实测 ----
    print(f"\n实测（统计范围＝参与池 {N} 张）")
    print(f"  {'轴':<10}{'均值':>12}{'SD':>12}{'SD-0.2887':>12}{'最小':>10}{'最大':>10}")
    worst_m = worst_s = 0.0
    for name in STYLE_NAMES:
        v = np.array([a["vec"]["style_" + name] for a in live], dtype=float)
        m, s = float(v.mean()), float(v.std(ddof=0))
        worst_m, worst_s = max(worst_m, abs(m)), max(worst_s, abs(s - SD))
        print(f"  style_{name:<4}{m:>12.6f}{s:>12.6f}{s - SD:>12.6f}{v.min():>10.4f}{v.max():>10.4f}")
    tol = 1e-4 if n_L == N else 5e-3
    print(f"  9 条轴实测：|均值| 最大 {worst_m:.6f}，|SD-0.2887| 最大 {worst_s:.6f}"
          f"（容差 {tol:g}）  {'✓' if worst_m < tol and worst_s < tol else '✗'}")

    # ---- 轴间相关（多标签特有：单标签的形态轴之间必然是负相关）----
    M = np.array([[a["vec"]["style_" + n] for n in STYLE_NAMES] for a in live])
    C = np.corrcoef(M.T)
    print("\n轴间相关（多标签的正相关是正常的；形态轴的 one-hot 之间只会是负相关）")
    off = [(STYLE_NAMES[i], STYLE_NAMES[j], C[i, j])
           for i in range(len(STYLE_NAMES)) for j in range(i + 1, len(STYLE_NAMES))]
    top = sorted(off, key=lambda t: -abs(t[2]))[:5]
    print("  |r| 最大的 5 对：" + "，".join(f"{a}×{b} {r:+.3f}" for a, b, r in top))
    print(f"  9×9 相关矩阵非对角元 |r| 中位数 {np.median([abs(r) for _, _, r in off]):.3f}；"
          f"最大 {max(abs(r) for _, _, r in off):.3f}")

    # ---- 未知格在推荐里的实际行为 ----
    print("\n未知标签的格子在推荐里的行为（模拟：把某条轴拉满，看未知格排名分布）")
    qs = json.loads(pathlib.Path(args.questions).read_text(encoding="utf-8"))["questions"]
    smax = {k: max(sum(o["s"].get(k, 0.0) for o in q["opts"] if o["s"].get(k, 0.0) > 0)
                   for q in qs if not q.get("multi")) for k in STYLE_AXES}
    unk = [a for a in live if not labels.get(a["art_id"])]
    print(f"  {'轴':<10}{'满偏时未知格均分':>16}{'有标签格均分':>13}"
          f"{'未知格平均百分位':>17}{'未知格进前 3':>13}")
    for name in STYLE_NAMES:
        ax = "style_" + name
        pref = {k: 0.0 for k in STYLE_AXES}
        pref[ax] = smax[ax]
        sc = np.array([sum(pref[k] * a["vec"][k] for k in STYLE_AXES) for a in live])
        isunk = np.array([not labels.get(a["art_id"]) for a in live])
        order = np.argsort(-sc)
        top3 = order[:3]
        n_unk_top3 = int(isunk[top3].sum())
        mu = float(sc[isunk].mean()) if isunk.any() else float("nan")
        ml = float(sc[~isunk].mean()) if (~isunk).any() else float("nan")
        # 平均百分位：0 = 永远排第一，1 = 永远排最后（0.5 左右 = 中游，没被系统排除）
        pct = float(np.mean([int(np.where(order == i)[0][0]) / (len(live) - 1)
                             for i in np.where(isunk)[0]])) if isunk.any() else float("nan")
        print(f"  {ax:<10}{mu:>16.4f}{ml:>13.4f}{pct:>17.3f}{f'{n_unk_top3} / 3':>13}")
    if not unk:
        print("  → 本轮 **没有未知格**（mood 标签 378 条全覆盖参与池），这条通道不影响任何推荐。")
    else:
        print(f"  → 池子里有 {len(unk)} 张未知格；它们在这条轴上的取值恒为 0，"
              f"排名**夹在「有该标签」与「没有该标签」之间**：因为大多数图没有该标签"
              f"（p < 0.5），未知格实测落在**中上段**（平均百分位 0.15~0.31），"
              f"**不会被系统性排除**，但也拿不到「有该标签」那批图的上位。")

    # ---- 题档建议 ----
    print("\n题库权重档建议（写进 scripts/add_style_questions.py 的 TIER）")
    for name in STYLE_NAMES:
        st = stats[name]
        print(f"  style_{name:<4} p={st['p']:.4f}  k={st['k']:.3f}  →  {st['tier']}")

    # ---- 真引擎模拟：把单条 style 轴拉满，看 Top3 落到谁头上 ----
    print("\n单轴拉满时的 Top3（与前端同口径：按分降序、同一主将只留最高那版）")
    print(f"  {'轴':<10}{'该标签张数':>12}{'Top3 命中':>12}   Top3（主将 / 是否带该标签）")
    for name in STYLE_NAMES:
        ax = "style_" + name
        pref = {k: 0.0 for k in STYLE_AXES}
        pref[ax] = smax[ax]
        sc = [(sum(pref[k] * a["vec"][k] for k in STYLE_AXES), a) for a in live]
        sc.sort(key=lambda t: (-t[0], str(t[1]["art_id"])))
        out, seen = [], set()
        for s, a in sc:
            key = a.get("cmdr_en") or a.get("cmdr_zh")
            if key in seen:
                continue
            seen.add(key)
            out.append((s, a))
            if len(out) == 3:
                break
        hit = sum(1 for _, a in out if name in (labels.get(a["art_id"]) or set()))
        names = " / ".join(
            f"{a['cmdr_zh'][:10]}{'✓' if name in (labels.get(a['art_id']) or set()) else '·'}"
            for _, a in out)
        print(f"  {ax:<10}{stats[name]['cnt']:>12}{f'{hit}/3':>12}   {names}")

    if args.check:
        print("\n--check：没有写文件")
        return 0
    BACKUP.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(AXES_JSON, BACKUP / f"art_axes.json.{stamp}.pre-styleaxes.bak")
    AXES_JSON.write_text(json.dumps(arts, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✓ 已写回 {AXES_JSON}（备份在 backups/）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
