#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解「形态多选」题的权重 —— 让随便勾哪几类都得到同一份推力（不偏袒）。

    python scripts/solve_form_weights.py            # 报数值并写回 data/questions.json
    python scripts/solve_form_weights.py --dry-run   # 只报不写

════════════════════════════════════════════════════════════════════════
结构（2026-10-13 第二版：形态题 1 道 → 3 道）
════════════════════════════════════════════════════════════════════════
题库里现在是 **3 道多选题 b01/b02/b03**，每道 6 个选项，选项 f 只给 form_f 加自己的
权重（其余 5 类不写 = 0）。用户可任意勾选：勾 1 个、勾 3 个、6 个全勾，都合法。

① 形态轴是中心化 one-hot（实测最大偏差 1.2e-4，见 §①）：
       vec_g(x) = k_g·(1{x∈g} − p_g),    k_g = 0.2887/√(p_g(1−p_g))
   于是任意一张图 x（类 c）的**形态部分**得分
       s_form(x) = Σ_g pref[g]·vec_g(x) = r_c − (1/n)·Σ_g r_g·n_g = r_c − μ
        r_c := pref[c]·k_c
   也就是说：**形态得分 = 类索引 r_c 减去全池加权均值 μ**。
   μ 对全部图同加，**不影响排序** —— 排序只看 r_c。

② 勾选集合 S、共 n_q 道形态题 → pref[c] = n_q · w_c · 1(c∈S)
   （三道题的权重表按设计完全相同，所以 pref 是三份同样推力的累加）
   → r_c = n_q · w_c · k_c · 1(c∈S)。

判据 J1（结构，恒等式）：让「被勾的类，不论勾了几个，拿到的推力都一样」，唯一的
    干净解是**单题**推力与类无关：
        w_c · k_c = α（对所有 c）   ⟹   w_c = α / k_c      ← 闭式解
    此时 r_c = n_q·α·1(c∈S)：勾中的每一类正好 +n_q·α，没勾的正好 0。

判据 J2（实测）：枚举全部 63 个非空真子集 S，测「被勾类的图平均分 − 未勾类的图平均分」
    D(S) 应为同一个 n_q·α，极差 ~0；且任意两类之间的平均分差 max|r_c−r_c'| ~0。

判据 J3（量级）：任务书要求「勾某一类 → Top3 里至少 2/3 是它」，同时**单题权重 ≤ 2.0**
    这条题库硬约束不变：
        max w = α / min k ≤ 2.0  ⟹  α ≤ 2.0·min k = 1.2116（本池）
    三题累加后**总推力** T = n_q·α = 3 × 1.2116 = 3.6348。
    旧版单题时 T 只有 1.21，六类纯度最差 0.00（可爱小兽）；三题累加把 T 顶到 3.63
    （旧分析里「六类纯度全到 1.00 需要 T ≥ 3.0」），所以在**不破约束**的前提下达标。

⚠️ J3 的实测边界（交付时必须一起报）：见 §④ 的纯度表。T 已被约束卡死，
    仍有极少数极端审美人设会把某一类的图挤出 Top3 —— 报告里给的是实测最小纯度。

★ 全勾（=「我都行」）：r_c 恒为 n_q·α，与 c 无关 ⟹ 形态部分对全部图变成同一个常数，
  形态维度**完全中立**（六类平均分极差 = 仅剩 2 位小数的舍入残差，比单题时的 0.0069
  大 n_q 倍，约 0.02）。
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import pathlib
import random
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

FORM_AXES = ["form_纯人类", "form_人形异类", "form_凶猛巨兽",
             "form_扭曲异形", "form_可爱小兽", "form_机械构装", "form_写实动物"]
#   变异人形 → 人形异类；写实动物是 2026-10-13 新增的第 7 类（兽形三分）
FORMS = [a[5:] for a in FORM_AXES]
AES_AXES = ["warm", "bright", "vivid", "rich", "detailed",
            "contrasty", "modern", "borderless", "starart"]
# 2026-10-13 新增的 9 条「画风轴」——真引擎模拟必须把它们算进去，
# 否则「只勾某一类形态」的纯度会被低估（用户答了画风题却不计入偏好向量）。
STYLE_AXES = ["style_神秘", "style_史诗", "style_黑暗", "style_怪诞", "style_激烈",
              "style_温暖", "style_宁静", "style_可爱", "style_忧郁"]
ALL_AXES = AES_AXES + FORM_AXES + STYLE_AXES          # 25 条（与 payload.axes 同序）

SD = 0.2887                 # 所有轴统一到同一个标准差
W_MIN, W_MAX = 0.5, 2.0     # 题库硬约束：**单题**权重区间（来自 make_questions.py）
ALPHA_TARGET = 99.0         # 单题 α 的目标；实际被 W_MAX·min k 卡住（取不到就取上限）
NDIGITS = 2                 # 写进题库的小数位


# ----------------------------------------------------------------------
def load_pool(axes_path=None, form_path=None) -> dict:
    """参与池（art_axes 里没被 excluded、且 art_form 里有形态分类的图）。"""
    axes = json.loads(pathlib.Path(axes_path or DATA / "art_axes.json").read_text(encoding="utf-8"))
    form_rows = json.loads(pathlib.Path(form_path or DATA / "art_form.json").read_text(encoding="utf-8"))
    formmap = {r["art_id"]: r["form"] for r in form_rows if not r.get("excluded")}
    live = [x for x in axes if not x.get("excluded") and x["art_id"] in formmap]
    cls = np.array([formmap[x["art_id"]] for x in live])
    V = np.array([[float(x["vec"][a]) for a in FORM_AXES] for x in live])
    n = len(live)
    p = {f: float((cls == f).mean()) for f in FORMS}
    k = {f: SD / math.sqrt(p[f] * (1.0 - p[f])) for f in FORMS}
    k_emp = {f: float(V[:, i].std() / math.sqrt(p[f] * (1 - p[f]))) for i, f in enumerate(FORMS)}
    return {"live": live, "cls": cls, "V": V, "p": p, "k": k, "k_emp": k_emp, "n": n}


def multi_questions(path) -> list[dict]:
    qs = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))["questions"]
    return [q for q in qs if q.get("multi")]


def alpha_for(pool: dict, target: float = ALPHA_TARGET, w_max: float = W_MAX) -> float:
    """**单题** α = min(目标, 单题权重上限允许的最大值)。等强性质对 α 尺度不变。"""
    return min(target, w_max * min(pool["k"].values()))


def alpha_ceiling(pool: dict, w_max: float = W_MAX) -> float:
    """题库硬约束「单题权重 ≤ w_max」能支撑的最大单题 α。"""
    return w_max * min(pool["k"].values())


def weights_for(pool: dict, alpha: float | None = None, ndigits: int = NDIGITS) -> dict:
    """闭式解 w_f = α / k_f（四舍五入到 ndigits 位，写进题库）。三道题共用这一组。"""
    a = alpha_for(pool) if alpha is None else alpha
    return {f: round(a / pool["k"][f], ndigits) for f in FORMS}


# ----------------------------------------------------------------------
def subset_scores(pool, weights, S, n_q=1):
    """返回 (被勾类图的平均分, 未勾类图的平均分, 全部图的分)；n_q 道题累加。"""
    w = np.array([weights[f] for f in FORMS]) * float(n_q)
    pref = np.where(np.isin(np.array(FORMS), list(S)), w, 0.0)
    sc = pool["V"] @ pref
    sel = np.isin(pool["cls"], list(S))
    m_sel = float(sc[sel].mean()) if sel.any() else float("nan")
    m_oth = float(sc[~sel].mean()) if (~sel).any() else float("nan")
    return m_sel, m_oth, sc


def verify(pool, weights, alpha, n_q) -> dict:
    """判据 J2：全部 63 个非空子集的推力一致性 + 各类之间的平均分差 + 全勾中立性。"""
    out = {"alpha": alpha, "n_q": n_q, "total": n_q * alpha,
           "rows": [], "r": {}, "r_spread": None, "all_spread": None}
    w = np.array([weights[f] for f in FORMS])
    k = np.array([pool["k"][f] for f in FORMS])
    r = w * k
    out["r"] = {f: float(r[i]) for i, f in enumerate(FORMS)}
    out["r_spread"] = float(r.max() - r.min())
    out["r_maxdev"] = float(np.abs(r - alpha).max())      # 单题：与目标 α 的最大偏差

    for size in range(1, len(FORMS) + 1):
        ds = []
        for combo in itertools.combinations(FORMS, size):
            a, b, _ = subset_scores(pool, weights, set(combo), n_q)
            if not math.isnan(b):          # 全勾时没有「未勾类」，D 无定义
                ds.append(a - b)
        out["rows"].append({
            "size": size, "n": math.factorial(len(FORMS)) //
                (math.factorial(size) * math.factorial(len(FORMS) - size)),
            "measured": len(ds),
            "min": min(ds) if ds else float("nan"),
            "max": max(ds) if ds else float("nan"),
            "mean": sum(ds) / len(ds) if ds else float("nan"),
            "spread": (max(ds) - min(ds)) if ds else float("nan"),
        })

    # 逐类平均分：勾任意子集时类间差 = r_c − r_c'
    means = {}
    for size in (1, 2, 3, 6):
        for combo in itertools.combinations(FORMS, size):
            _, _, sc = subset_scores(pool, weights, set(combo), n_q)
            for f in combo:
                means.setdefault((size, combo, f), float(sc[pool["cls"] == f].mean()))
    worst = 0.0
    for size in (1, 2, 3, 6):
        for combo in itertools.combinations(FORMS, size):
            vals = [means[(size, combo, f)] for f in combo]
            worst = max(worst, max(vals) - min(vals))
    out["class_gap_worst"] = worst

    _, _, sc = subset_scores(pool, weights, set(FORMS), n_q)
    all_means = [float(sc[pool["cls"] == f].mean()) for f in FORMS]
    out["all_spread"] = max(all_means) - min(all_means)
    out["all_means"] = all_means
    return out


# ----------------------------------------------------------------------
# 真引擎（与前端 art_quiz.html / smoke_test.mjs 的口径逐条对齐）
# ----------------------------------------------------------------------
def vec15(live) -> np.ndarray:
    """25 轴矩阵（9 像素 + 7 形态 + 9 画风），顺序与 payload.axes 一致。"""
    return np.array([[float(x["vec"][a]) for a in ALL_AXES] for x in live])


def aes_pref(questions, picker) -> np.ndarray:
    """全部**单选题**（26 道审美 + 9 道画风）产生的 25 轴 pref；多选题不参与。"""
    qs = [q for q in questions if not q.get("multi")]
    p = np.zeros(len(ALL_AXES))
    for i, q in enumerate(qs):
        s = q["opts"][picker(q, i)]["s"]
        for j, a in enumerate(ALL_AXES):
            p[j] += s.get(a, 0.0)
    return p


def recommend(pref15, live, n=3, M=None):
    """与 JS 引擎一致：按分降序（并列按 art_id 升序），同一主将只留分最高那版。"""
    if M is None:
        M = vec15(live)
    s = M @ np.asarray(pref15, dtype=float)
    order = sorted(range(len(live)), key=lambda i: (-float(s[i]), str(live[i]["art_id"])))
    out, seen = [], set()
    for i in order:
        x = live[i]
        key = x.get("cmdr_en") or x.get("cmdr_zh")
        if key in seen:
            continue
        seen.add(key)
        out.append((float(s[i]), x))
        if len(out) == n:
            break
    return out


def form_pref(weights, S, n_q, zero_forms=False):
    """25 轴 pref 里的形态部分（0 = 形态完全不参与）。"""
    p = np.zeros(len(ALL_AXES))
    if not zero_forms:
        for i, f in enumerate(FORMS):
            if f in S:
                p[len(AES_AXES) + i] = weights[f] * n_q
    return p


def personas(questions, n_random=300, seed=7):
    """一批审美人设：4 个「一路只选第 k 项」+ 若干随机作答。"""
    out = []
    for pos in range(4):
        out.append((f"固定第{pos + 1}项", aes_pref(questions, lambda q, i, p=pos: min(p, len(q["opts"]) - 1))))
    rng = random.Random(seed)
    for k in range(n_random):
        out.append((f"随机{k + 1}", aes_pref(questions, lambda q, i: rng.randrange(len(q["opts"])))))
    return out


def purity(pool, questions, weights, n_q, S, aes_list, zero_forms=False, M=None):
    """勾选集合 S（或全中立）下，Top3 里「形态 ∈ S」的比例，逐人设返回。"""
    if M is None:
        M = vec15(pool["live"])
    fp = form_pref(weights, S, n_q, zero_forms)
    out = []
    for nm, ap in aes_list:
        pref = fp + ap                       # 单选题的偏好（含画风轴）按轴位相加
        picks = recommend(pref, pool["live"], 3, M)
        hit = sum(1 for _, x in picks if (zero_forms or pool["formmap"][x["art_id"]] in S))
        out.append((nm, hit / 3.0, [pool["formmap"][x["art_id"]] for _, x in picks]))
    return out


# ----------------------------------------------------------------------
def apply_to_questions(path, weights, dry_run=False) -> tuple[int, int]:
    """把权重写进**每一道**多选题的 6 个选项（每个选项只挂自己那一类 form_*）。"""
    path = pathlib.Path(path)
    q = json.loads(path.read_text(encoding="utf-8"))
    mqs = [x for x in q["questions"] if x.get("multi")]
    if not mqs:
        print("✗ 题库里没有多选题", file=sys.stderr)
        return -1, -1
    changed = 0
    for mq in mqs:
        for o in mq["opts"]:
            f = o.get("form")
            if f not in weights:
                print(f"✗ {mq['id']} 选项「{o['t']}」的 form={f!r} 不在 6 类里", file=sys.stderr)
                return -1, -1
            nv = weights[f]
            old = (o.get("s") or {}).get("form_" + f)
            if old is None or abs(old - nv) > 1e-12:
                changed += 1
            o["s"] = {"form_" + f: nv}
    if not dry_run:
        path.write_text(json.dumps(q, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return sum(len(m["opts"]) for m in mqs), changed


# ----------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="解形态多选题（b01/b02/b03）的权重")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--alpha", type=float, default=None, help="覆盖【单题】α")
    ap.add_argument("--relax-weights", action="store_true",
                    help="允许单题权重突破题库记录的 0.5~2.0 上限（用于换取更高的 Top3 纯度）")
    ap.add_argument("--personas", type=int, default=300, help="随机审美人设数量")
    ap.add_argument("--questions", default=str(DATA / "questions.json"))
    args = ap.parse_args(argv)

    pool = load_pool()
    mqs = multi_questions(args.questions)
    n_q = len(mqs)
    # 把 form 缓存到 live 行上，供 x_form 用（load_pool 里的 formmap 不随行返回）
    form_rows = json.loads((DATA / "art_form.json").read_text(encoding="utf-8"))
    pool["formmap"] = {r["art_id"]: r["form"] for r in form_rows if not r.get("excluded")}
    for x in pool["live"]:
        x["_form"] = pool["formmap"][x["art_id"]]

    w_max = 99.0 if args.relax_weights else W_MAX
    alpha = alpha_for(pool, w_max=w_max) if args.alpha is None else args.alpha
    weights = weights_for(pool, alpha)
    total = n_q * alpha

    print("=" * 78)
    print("① 形态轴的实际标度（决定 w_f = α / k_f）")
    print("=" * 78)
    print(f"  参与池 {pool['n']} 张；形态多选题 {n_q} 道"
          f"（{'、'.join(m['id'] for m in mqs)}）")
    print(f"  {'形态':<10}{'张数':>6}{'占比 p':>10}{'k(解析)':>12}{'k(实测)':>12}"
          f"{'1/k':>10}{'w=α/k':>10}")
    for f in FORMS:
        n = int((pool["cls"] == f).sum())
        print(f"  {f:<10}{n:>6}{pool['p'][f]:>10.4f}{pool['k'][f]:>12.6f}"
              f"{pool['k_emp'][f]:>12.6f}{1 / pool['k'][f]:>10.4f}{weights[f]:>10.4f}")
    kmin, kmax = min(pool["k"].values()), max(pool["k"].values())
    print(f"\n  单题 α = {alpha:.4f}（上限 {W_MAX}·min k = {W_MAX * kmin:.4f}）"
          f"  →  {n_q} 题累加总推力 T = {total:.4f}")
    print(f"  权重范围 {min(weights.values()):.4f} ~ {max(weights.values()):.4f}"
          f"（题库硬约束 {W_MIN}~{W_MAX}）"
          f"  {'✓' if min(weights.values()) >= W_MIN - 1e-9 and max(weights.values()) <= W_MAX + 1e-9 else '⚠ 越界'}")
    print(f"  下限校验：α ≥ {W_MIN}·max k = {W_MIN * kmax:.4f} → "
          f"{'✓' if alpha >= W_MIN * kmax - 1e-9 else '⚠ 最小的权重会低于 0.5'}")
    print(f"  k 的解析式与实测最大偏差 "
          f"{max(abs(pool['k'][f] - pool['k_emp'][f]) for f in FORMS):.2e}")

    v = verify(pool, weights, alpha, n_q)
    print()
    print("=" * 78)
    print("② 判据 J1：r_c = w_c × k_c（单题）")
    print("=" * 78)
    for f in FORMS:
        print(f"  {f:<10} w={weights[f]:.4f} × k={pool['k'][f]:.6f} = r={v['r'][f]:.6f}")
    print(f"  max |r_c − α| = {v['r_maxdev']:.6f}（舍入到 {NDIGITS} 位小数的残差）；"
          f"极差 {v['r_spread']:.6f}")

    print()
    print("=" * 78)
    print("③ 判据 J2：全部 63 个非空真子集，「被勾类平均分 − 未勾类平均分」D(S)")
    print("  （池子上实测，不是解析式；三道题的推力累加，所以期望值 = n_q·α）")
    print("=" * 78)
    print(f"  {'子集大小':<10}{'子集数':>8}{'min':>10}{'mean':>10}{'max':>10}{'极差':>11}")
    for r in v["rows"]:
        if r["measured"]:
            print(f"  {r['size']:<10}{r['n']:>8}{r['min']:>10.4f}{r['mean']:>10.4f}"
                  f"{r['max']:>10.4f}{r['spread']:>11.6f}")
        else:
            print(f"  {r['size']:<10}{r['n']:>8}{'—':>10}{'—':>10}{'—':>10}{'—':>11}"
                  "   ← 全勾，无「未勾类」，D 无定义")
    worst = max(r["spread"] for r in v["rows"] if r["measured"])
    tot_n = sum(r["measured"] for r in v["rows"])
    print(f"  全部 {tot_n} 个真子集的 D(S) 极差 = {worst:.6f}；均值 = "
          f"{sum(r['mean'] * r['measured'] for r in v['rows'] if r['measured']) / tot_n:.6f}"
          f"（= n_q·α = {total:.4f}）")
    print(f"  任一次勾选里「被勾类之间」的最大平均分差 = {v['class_gap_worst']:.6f}"
          f"（判据：应为 0）")
    print(f"  全勾 6 类：六类平均分 " + "  ".join(f"{f} {m:+.6f}" for f, m in zip(FORMS, v["all_means"])))
    print(f"  全勾极差 {v['all_spread']:.6f} → 形态维度对全部图同加常数，完全中立")

    # ------------------------------------------------------------------
    print()
    print("=" * 78)
    print(f"④ 判据 J3：真引擎（含 9 个审美轴）下的 Top3 形态纯度 —— {n_q} 题一起勾")
    print(f"   人设：4 个「一路只选第 k 项」+ {args.personas} 个随机作答 = "
          f"{4 + args.personas} 组")
    print("=" * 78)
    questions = json.loads(pathlib.Path(args.questions).read_text(encoding="utf-8"))["questions"]
    aes_list = personas(questions, args.personas)
    M = vec15(pool["live"])

    print("  J3-a 勾 1 类 → Top3 里该类的比例")
    print(f"  {'勾':<10}{'最小':>8}{'平均':>8}{'最大':>8}   最差那个人设的 Top3")
    single_stats = {}
    for f in FORMS:
        rows = purity(pool, questions, weights, n_q, {f}, aes_list, M=M)
        ps = [r[1] for r in rows]
        worst_row = min(rows, key=lambda r: (r[1], r[0]))
        single_stats[f] = {"min": min(ps), "mean": sum(ps) / len(ps), "max": max(ps),
                           "worst": worst_row,
                           "miss": sum(1 for r in rows if r[1] < 2 / 3)}
        print(f"  {f:<10}{min(ps):>8.2f}{sum(ps) / len(ps):>8.2f}{max(ps):>8.2f}   "
              + " / ".join(worst_row[2]))
    print(f"  → 六类里「Top3 不足 2/3」的人设数："
          + "  ".join(f"{f} {single_stats[f]['miss']}" for f in FORMS)
          + f"（分母 {len(aes_list)}）")
    print(f"  → 六类**最小纯度**里的最小值 = "
          f"{min(s['min'] for s in single_stats.values()):.2f}；"
          f"平均 = {sum(s['mean'] for s in single_stats.values()) / len(FORMS):.2f}")

    # 只看「连贯人设」：一路只选第 k 项的那 4 组（真实用户的口味是连贯的，
    # 随机作答是「没有口味」的噪声人设，把两者分开报才看得清）
    print()
    print("  J3-a₂ 同上，但只取 4 个**连贯**人设（一路只选第 k 项）")
    print(f"  {'勾':<10}" + "".join(f"{nm:>10}" for nm, _ in aes_list[:4]) + f"{'最小':>8}{'平均':>8}")
    fixed_min = {}
    for f in FORMS:
        rows = purity(pool, questions, weights, n_q, {f}, aes_list[:4], M=M)
        ps = [r[1] for r in rows]
        fixed_min[f] = min(ps)
        print(f"  {f:<10}" + "".join(f"{p:>10.2f}" for p in ps)
              + f"{min(ps):>8.2f}{sum(ps) / len(ps):>8.2f}")
    print(f"  → 连贯人设下六类最小纯度 = {min(fixed_min.values()):.2f}"
          f"（任务书要求「3 张里至少 2 张」= 0.67）")

    # ---- 诊断：要让「全部人设的最小纯度 ≥ 2/3」需要多大的总推力 ----
    print()
    print("  J3-a₃ 诊断：把「全部人设最小纯度 ≥ 2/3」当目标，反推需要的单题 α")
    print(f"    {'勾':<10}{'实测最小':>10}{'≥2/3 需要的单题 α':>20}{'对应单题权重上限':>18}")

    def min_purity_for_total(f, T):
        """给定 3 题累加的总推力 T，该类纯度在人设里的最小值。"""
        w = {x: (T / n_q) / pool["k"][x] for x in FORMS}   # 用解析 α，避免舍入噪声
        return min(r[1] for r in purity(pool, questions, w, n_q, {f}, aes_list, M=M))

    need = {}
    for f in FORMS:
        lo, hi = 0.0, 60.0
        if min_purity_for_total(f, hi) < 2 / 3:
            need[f] = None
        else:
            for _ in range(28):
                mid = (lo + hi) / 2
                if min_purity_for_total(f, mid) >= 2 / 3:
                    hi = mid
                else:
                    lo = mid
            need[f] = hi
        nm = "不可达" if need[f] is None else f"{need[f] / n_q:.2f}"
        wmax = "—" if need[f] is None else f"{need[f] / n_q / min(pool['k'].values()):.2f}"
        print(f"    {f:<10}{single_stats[f]['min']:>10.2f}{nm:>20}{wmax:>18}")
    reachable = [f for f in FORMS if need[f] is not None]
    print(f"    → 六类里「全部人设 ≥ 2/3」可达的：{len(reachable)}/6"
          + ("（" + "、".join(f"{f} 需 α={need[f] / n_q:.2f}" for f in reachable) + "）"
             if reachable else ""))
    if reachable:
        print(f"    → 最贵的那一类要求单题 α ≥ {max(need[f] for f in reachable) / n_q:.2f}，"
              f"即单题权重上限 ≥ {max(need[f] for f in reachable) / n_q / min(pool['k'].values()):.2f}"
              f"（当前硬约束 2.0，本题库实测最大 α = {alpha:.4f}/题、总推力 {total:.4f}）")
    print("    → 结论：当前的**总推力已达约束允许的最大值**，"
          "把「全部人设最小纯度 ≥ 2/3」当硬指标只能破约束；"
          "任务书规定不许自作主张破约束，所以这里只报数、不改。")

    print()
    print("  J3-b 勾 3 类 → Top3 里「勾中三类」的比例（枚举全部 C(6,3)=20 组）")
    tri = []
    for combo in itertools.combinations(FORMS, 3):
        rows = purity(pool, questions, weights, n_q, set(combo), aes_list, M=M)
        ps = [r[1] for r in rows]
        tri.append((combo, min(ps), sum(ps) / len(ps), max(ps)))
    for combo, mn, me, mx in tri:
        print(f"    {'+'.join(combo):<24}{mn:>8.2f}{me:>8.2f}{mx:>8.2f}")
    print(f"  → 20 组里最小纯度 {min(t[1] for t in tri):.2f}，"
          f"平均 {sum(t[2] for t in tri) / len(tri):.2f}")

    print()
    print("  J3-c 全勾 6 类（「我都行」）→ 形态维度中立，Top3 完全由审美决定")
    rows = purity(pool, questions, weights, n_q, set(FORMS), aes_list, zero_forms=True, M=M)
    dist = {}
    for _, _, fs in rows:
        for f in fs:
            dist[f] = dist.get(f, 0) + 1
    tot3 = 3 * len(rows)
    print("    Top3 的形态分布：" + "  ".join(
        f"{f} {dist.get(f, 0)}/{tot3}({dist.get(f, 0) / tot3:.1%})" for f in FORMS))
    print(f"    （池子里六类的占比：" + "  ".join(f"{f} {pool['p'][f]:.1%}" for f in FORMS) + "）")

    n_opt, changed = apply_to_questions(args.questions, weights, args.dry_run)
    if n_opt < 0:
        return 1
    print(f"\n  ✓ {n_q} 道多选题共 {n_opt} 个选项已按 w_f = α/k_f 校准（{changed} 个值被改写）"
          + ("　[dry-run 不写]" if args.dry_run else ""))

    # 写回后复核
    q = json.loads(pathlib.Path(args.questions).read_text(encoding="utf-8"))
    bad = []
    for qq in q["questions"]:
        if qq.get("multi"):
            continue
        per = {}
        for o in qq["opts"]:
            for kk, vv in (o.get("s") or {}).items():
                per[kk] = per.get(kk, 0.0) + vv
        for kk, vv in per.items():
            if abs(vv) > 1e-9:
                bad.append((qq["id"], kk, round(vv, 4)))
    print(f"  每道单选审美题每轴求和为 0：{'✓' if not bad else f'✗ {bad[:4]}'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
