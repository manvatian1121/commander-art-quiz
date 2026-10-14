# -*- coding: utf-8 -*-
"""给 art_axes.json 的每张图补上 6 个「画面形态」轴（form_*）。

    python scripts/add_form_axes.py            # 就地改写（幂等）
    python scripts/add_form_axes.py --check    # 只体检，不写文件

做法：中心化 one-hot
    某张图的形态是 f  →  vec["form_f"] = (1 - p_f) * k_f
    其它 5 个形态      →  vec["form_g"] = (0 - p_g) * k_g
    p_f = 形态 f 在**参与池**里的占比    k_f = 0.2887 / sqrt(p_f * (1 - p_f))

为什么 k 是**逐形态**而不是一个全局常数：
    中心化 one-hot 的 SD = k * sqrt(p_f * (1 - p_f))。p_f 从 2.2% 到 41.8% 差 19 倍，
    全局常数不可能让 6 个轴的 SD 同时等于 0.2887（只能让最小/最大差 3.3 倍）。
    要让「形态轴 × 权重」和原有 10 个轴可比，k 必须按形态取。

代价（写在报告里）：稀有形态的系数被放大（机械构装 k=1.95、可爱小兽 k=1.40），
所以「稀有形态的正权重」对得分的影响远大于同权重的常见形态 —— 这正是
题目权重必须按 sqrt(p(1-p)) 之类的比例来给的原因（见 add_form_questions.py）。

轴上界不再是 ±1：0.2887 是「均匀分布」的 SD，稀有形态的单点值会超过 1
（form_机械构装 最高 +1.9257）。冒烟测试里对 10 个旧轴查 ±1，对新轴单独查。

无生物类取消后的 5 张图：
    art_form.json 里带 "excluded": true，本脚本给它们所有 form_* 轴都取
    「不属于任何一类」的值（-p_f * k_f），并在 art_axes.json 里同步 excluded 标记。
    build_html.py 见到 excluded 就不放进 payload —— 结果页永远推荐不到它们。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

PROJECT = Path(__file__).resolve().parent.parent
AXES_JSON = PROJECT / "data" / "art_axes.json"
FORM_JSON = PROJECT / "data" / "art_form.json"
BACKUP_DIR = PROJECT / "backups"

LEGACY_AXES = ["warm", "bright", "vivid", "rich", "detailed",
               "contrasty", "darkarea", "modern", "borderless", "starart"]
# 2026-10-13：`变异人形` 更名 `人形异类`（含义＝人形但不是普通人；兽首人形与卡通人形角色都归此）；
#             兽形拆成三类：可爱小兽（卡通 Q 版）/ 写实动物（写实画法）/ 凶猛巨兽（体型庞大、凶相）。
FORM_NAMES = ["纯人类", "人形异类", "凶猛巨兽", "扭曲异形", "可爱小兽", "机械构装", "写实动物"]
FORM_AXES = ["form_" + n for n in FORM_NAMES]
UNIFORM_SD = 1.0 / np.sqrt(12.0)          # ≈ 0.288675


def load(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="给每张图补 form_* 轴")
    ap.add_argument("--check", action="store_true", help="只体检不写文件")
    args = ap.parse_args(argv)

    arts = load(AXES_JSON)
    forms = load(FORM_JSON)

    by_id = {a["art_id"]: a for a in arts}
    form_of, excluded = {}, set()
    for row in forms:
        aid = row["art_id"]
        if aid not in by_id:
            print(f"✗ art_form.json 里的 {aid} 不在 art_axes.json 里", file=sys.stderr)
            return 1
        if aid in form_of or aid in excluded:
            print(f"✗ {aid} 在 art_form.json 里出现两次", file=sys.stderr)
            return 1
        if row.get("excluded"):
            excluded.add(aid)
            continue
        if row["form"] not in FORM_NAMES:
            print(f"✗ {aid} 的形态名不认识：{row['form']}", file=sys.stderr)
            return 1
        form_of[aid] = row["form"]

    missing = [a["art_id"] for a in arts
               if a["art_id"] not in form_of and a["art_id"] not in excluded]
    if missing:
        print(f"✗ {len(missing)} 张图既没形态分类也没被剔除，例如 {missing[:3]}", file=sys.stderr)
        return 1

    kept = [a for a in arts if a["art_id"] in form_of]
    labels = [form_of[a["art_id"]] for a in kept]
    n = len(kept)
    print(f"形态轴标定：参与池 {n} 张，剔除 {len(excluded)} 张"
          f"（占全池 {n / len(arts):.1%} 参与）")

    # ---- 占比 / 缩放系数 ----
    print(f"  {'形态':<10}{'张数':>5}{'占比 p':>10}{'k = .2887/sqrt(p(1-p))':>26}"
          f"{'本类取值':>12}{'其它取值':>11}{'本类位图摆动':>14}")
    k, p = {}, {}
    for f in FORM_NAMES:
        cnt = labels.count(f)
        p[f] = cnt / n
        k[f] = UNIFORM_SD / np.sqrt(p[f] * (1.0 - p[f]))
        own = (1.0 - p[f]) * k[f]
        other = -p[f] * k[f]
        print(f"  {f:<10}{cnt:>5}{p[f]:>10.4f}{k[f]:>26.4f}{own:>12.4f}{other:>11.4f}"
              f"{own - other:>14.4f}")
    print("  （最后一列 = 该类图与其它图在单轴上的得分差；权重 1.4 时就是 1.4 × 这一列）")

    # ---- 写回 vec（先清掉可能已经存在的 form_*，保证幂等）----
    for a in arts:
        vec = {kk: vv for kk, vv in a["vec"].items() if not kk.startswith("form_")}
        f = form_of.get(a["art_id"])           # 被剔除的图 f 为 None → 不属于任何一类
        for g in FORM_NAMES:
            hit = 1.0 if g == f else 0.0
            vec["form_" + g] = round(float((hit - p[g]) * k[g]), 4)
        a["vec"] = vec
        if a["art_id"] in excluded:
            a["excluded"] = True
        elif "excluded" in a:
            del a["excluded"]

    # ---- 验收：均值 / SD（只看参与池）----
    def stats(axis: str) -> tuple[float, float]:
        v = np.array([a["vec"][axis] for a in kept], dtype=float)
        return float(v.mean()), float(v.std(ddof=0))

    print("\n实测（写回文件里的那 4 位小数，与你要求的 0.2887 对照；统计范围＝参与池）")
    print(f"  {'轴':<14}{'均值':>12}{'SD':>12}{'SD-0.2887':>12}{'最小':>10}{'最大':>10}")
    ok = True
    for axis in LEGACY_AXES:                      # 旧轴必须原样不动
        m, s = stats(axis)
        print(f"  {axis:<14}{m:>12.6f}{s:>12.6f}{s - UNIFORM_SD:>12.6f}"
              f"{min(a['vec'][axis] for a in kept):>10.4f}"
              f"{max(a['vec'][axis] for a in kept):>10.4f}")
    print("  " + "-" * 66)
    worst_m = worst_s = 0.0
    for axis in FORM_AXES:
        m, s = stats(axis)
        worst_m = max(worst_m, abs(m))
        worst_s = max(worst_s, abs(s - UNIFORM_SD))
        print(f"  {axis:<14}{m:>12.6f}{s:>12.6f}{s - UNIFORM_SD:>12.6f}"
              f"{min(a['vec'][axis] for a in kept):>10.4f}"
              f"{max(a['vec'][axis] for a in kept):>10.4f}")
    # 4 位小数是刻意的（和原有 10 个轴同一精度）。每个轴只有 2 个不同取值，
    # 舍入误差不会互相抵消，所以均值只能收敛到 ~5e-5、SD 到 ~1.2e-5。
    TOL_M, TOL_S = 1e-4, 1e-4
    if worst_m > TOL_M or worst_s > TOL_S:
        ok = False
    print(f"\n  目标：均值 = 0，SD = {UNIFORM_SD:.6f}（与原有 10 轴同一个标度）")
    print(f"  6 个新轴实测：|均值| 最大 {worst_m:.6f}，|SD-0.2887| 最大 {worst_s:.6f}"
          f"（容差 {TOL_M:.0e}）")
    print("  ✓ 6 个新轴全部达标" if ok else "  ✗ 有轴不达标")

    # ---- 抽查：自己的那一类必须是 6 个 form 轴里的最高分 ----
    bad = []
    for a in kept:
        f = form_of[a["art_id"]]
        vals = {g: a["vec"]["form_" + g] for g in FORM_NAMES}
        top = max(vals, key=lambda g: vals[g])
        if top != f:
            bad.append((a["art_id"], f, top))
    print(f"  {'✓' if not bad else '✗'} 自我最高：{n - len(bad)}/{n} 张图的 form 轴最高项 = 自己的形态")
    if bad:
        print(f"     例如 {bad[:3]}")
        ok = False

    # ---- 被剔除的图：必须都带标记，且不在参与池里 ----
    flagged = [a["art_id"] for a in arts if a.get("excluded")]
    if set(flagged) != excluded:
        print(f"✗ excluded 标记不一致（art_axes {len(flagged)} vs art_form {len(excluded)}）",
              file=sys.stderr)
        ok = False
    else:
        print(f"  ✓ 剔除的 {len(excluded)} 张在 art_axes.json / art_form.json 里都标了 excluded")

    if args.check:
        print("\n--check：没有写文件")
        return 0 if ok else 1
    if not ok:
        print("\n✗ 验收未通过，不写文件", file=sys.stderr)
        return 1

    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(AXES_JSON, BACKUP_DIR / f"art_axes.json.{stamp}.pre-formaxes.bak")
    AXES_JSON.write_text(json.dumps(arts, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✓ 已写回 {AXES_JSON.relative_to(PROJECT)}（原文件备份到 backups/）")
    print(f"  每张图现在有 {len(arts[0]['vec'])} 个轴：10 旧 + 6 新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
