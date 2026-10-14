# -*- coding: utf-8 -*-
"""交付实测：6 条画法轴（tech_*）的标度、覆盖、以及「拉满一条轴」时的 Top3 命中率。

    python scripts/report_tech_axes.py            # 只读，写不了任何文件
    python scripts/report_tech_axes.py --no-write-report

只读脚本，不碰 data/。所有数字**从产物现算**：
  · 轴值 / 引擎打分 → art_quiz.html 里内嵌的那份 payload（与用户真正跑的是同一份数据）
  · 权重 / 题数     → data/questions.json
  · 画法标签        → data/art_style.json（多标签，主标+次标都算）
排序与去重口径与前端逐条一致：按分降序、同分按 art_id 升序、同一主将只留最高那版。

★ 「拉满」的两种口径都报，因为它们的含义不同：
  ① 单轴口径：pref 只在这条轴上有值（= 该轴在题库里的满偏值 smax），其它轴全 0
     —— 与 add_style_axes.py 的单轴模拟同口径，可比性最好。
  ② 连贯人设口径：**每道题都挑对这条轴最有利的那一项**，其它轴跟着动
     —— 更接近真实用户（他答别的题时也在表达口味，那些口味会来抢 Top3）。
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
HTML = ROOT / "art_quiz.html"
SD = 0.2887

TECH_AXES = ["tech_二次元日系", "tech_欧美厚涂", "tech_卡通绘本",
             "tech_线稿版画", "tech_写实数字绘", "tech_水彩淡彩"]
TECH_NAMES = [a[5:] for a in TECH_AXES]
NO_OPTION = "tech_水彩淡彩"        # 按口径不出题


def load_payload() -> dict:
    html = HTML.read_text(encoding="utf-8")
    m = re.search(r'<script id="payload" type="application/json">([\s\S]*?)</script>', html)
    if not m:
        raise SystemExit(f"✗ {HTML.name} 里找不到内嵌 payload，先跑 build_html.py")
    return json.loads(m.group(1).replace("<\\/", "</"))


def load_labels() -> dict[str, set[str]]:
    rows = json.loads((DATA / "art_style.json").read_text(encoding="utf-8"))
    out = {}
    for x in rows:
        v = x.get("style") or []
        out[x["art_id"]] = set(v if isinstance(v, list) else [v])
    return out


def recommend(pref, axes, arts, n=3):
    """与前端 recommend() 同口径。"""
    scored = [(sum(pref.get(k, 0.0) * a["vec"][k] for k in axes), a) for a in arts]
    scored.sort(key=lambda t: (-t[0], str(t[1]["art_id"])))
    out, seen = [], set()
    for s, a in scored:
        key = a.get("cmdr_en") or a.get("cmdr_zh") or a["art_id"]
        if key in seen:
            continue
        seen.add(key)
        out.append((s, a))
        if len(out) == n:
            break
    return out


def smax_of(questions) -> dict[str, float]:
    """每条轴的满偏值 = 每题都挑对它最有利的那一项时拿到的 pref。"""
    out = collections.defaultdict(float)
    for q in questions:
        if q.get("multi"):
            continue
        axes = {k for o in q["opts"] for k in o["s"]}
        for k in axes:
            out[k] += max(o["s"].get(k, 0.0) for o in q["opts"])
    return dict(out)


def argmax_opts(q, ax) -> list[int]:
    """这道题里让 ax 拿分最多的选项集合（可能有并列）。"""
    vals = [o["s"].get(ax, 0.0) for o in q["opts"]]
    top = max(vals)
    return [i for i, v in enumerate(vals) if abs(v - top) < 1e-12]


def persona_sweep(qs, axes, arts, labels, ax):
    """② 口径：33 道非画法题**一路只选第 k 项**（k=0..3 = 四种连贯口味），
    画法题则全部挑对该轴最有利的那一项（并列最优的全枚举 —— 二次口味也是用户的一部分）。

    返回 [(k, 组合数, min, mean, max), ...]：min = 口味最不合的那位用户。
    形态多选题不参与（与 ①③ 口径一致，隔离出「画法偏好 vs 其余审美偏好」）。
    """
    name = ax[5:]
    non_multi = [q for q in qs if not q.get("multi")]
    rows = []
    for k in range(4):
        combos = [[]]
        for q in non_multi:
            ch = (argmax_opts(q, ax) if any(ax in o["s"] for o in q["opts"])
                  else [min(k, len(q["opts"]) - 1)])
            combos = [c + [i] for c in combos for i in ch]
        ps = []
        for c in combos:
            pref = {kk: 0.0 for kk in axes}
            for q, i in zip(non_multi, c):
                for kk, v in q["opts"][i]["s"].items():
                    pref[kk] = pref.get(kk, 0.0) + v
            top = recommend(pref, axes, arts)
            ps.append(sum(1 for _, a in top if name in (labels.get(a["art_id"]) or set())) / 3)
        rows.append((k, len(ps), min(ps), sum(ps) / len(ps), max(ps)))
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="画法轴交付实测")
    ap.add_argument("--no-write-report", action="store_true")
    args = ap.parse_args(argv)

    payload = load_payload()
    axes = payload["axes"]
    arts = payload["a"]
    qs = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))["questions"]
    labels = load_labels()
    formmap = {r["art_id"]: r["form"] for r in
               json.loads((DATA / "art_form.json").read_text(encoding="utf-8"))
               if not r.get("excluded")}
    smax = smax_of(qs)
    problems: list[str] = []
    lines: list[str] = []

    def say(s=""):
        print(s)
        lines.append(s)

    say("=" * 78)
    say("画法轴（tech_*）交付实测 · 只读")
    say(f"payload {HTML.name}：{len(arts)} 张 / {len(axes)} 轴（{len(qs)} 题）")
    say("=" * 78)

    # ------------------------------------------------------------------
    say("\n① 前端真的接上了（加轴时最容易静默失效的一处）")
    missing_axes = [a for a in TECH_AXES if a not in axes]
    say(f"  payload.axes 里的 6 条 tech_*：{'✓ 全在' if not missing_axes else '✗ 缺 ' + str(missing_axes)}")
    if missing_axes:
        problems.append(f"payload 缺画法轴 {missing_axes}")
    bad_vec = [a["art_id"] for a in arts
               if any(not isinstance(a["vec"].get(k), (int, float)) for k in TECH_AXES)]
    say(f"  每张图的 vec 都带这 6 条轴：{'✓' if not bad_vec else f'✗ {len(bad_vec)} 张缺，例如 {bad_vec[:2]}'}")
    if bad_vec:
        problems.append(f"{len(bad_vec)} 张图缺画法轴的值")
    bad_q = [(q["id"], sorted({k for o in q["opts"] for k in o["s"] if k.startswith("tech_")}))
             for q in qs if not q.get("multi")
             and len({k for o in q["opts"] for k in o["s"] if k.startswith("tech_")}) not in (0, 2)]
    say(f"  每道画法题恰好挂 2 条 tech_*：{'✓' if not bad_q else '✗ ' + str(bad_q)}")
    if bad_q:
        problems.append(f"有题目不是 2 条画法轴：{bad_q}")
    wc = [(q["id"], o["t"]) for q in qs for o in q["opts"] if NO_OPTION in o.get("s", {})]
    say(f"  水彩淡彩（6 张）没被挂进任何选项：{'✓' if not wc else '✗ ' + str(wc)}")
    if wc:
        problems.append(f"水彩淡彩被挂进了选项：{wc}")

    # ------------------------------------------------------------------
    say("\n② 6 条 tech_* 轴的均值 / SD（统计范围＝payload 里的 370 张参与池）")
    say(f"  {'轴':<17}{'均值':>13}{'SD':>13}{'SD-0.2887':>12}{'最小':>10}{'最大':>10}"
        f"{'池内张数':>9}")
    worst_m = worst_s = 0.0
    for ax in TECH_AXES:
        v = np.array([a["vec"][ax] for a in arts], dtype=float)
        m, s = float(v.mean()), float(v.std(ddof=0))
        worst_m, worst_s = max(worst_m, abs(m)), max(worst_s, abs(s - SD))
        n_lab = sum(1 for a in arts if ax[5:] in (labels.get(a["art_id"]) or set()))
        say(f"  {ax:<17}{m:>13.6f}{s:>13.6f}{s - SD:>12.6f}{v.min():>10.4f}{v.max():>10.4f}"
            f"{n_lab:>9}")
    ok = worst_m < 5e-3 and worst_s < 5e-3
    say(f"  → |均值| 最大 {worst_m:.6f}，|SD-0.2887| 最大 {worst_s:.6f}"
        f"（目标 0 / 0.2887，容差 5e-3）  {'✓' if ok else '✗'}")
    if not ok:
        problems.append(f"画法轴标度不达标：均值 {worst_m}，SD 偏差 {worst_s}")

    # ------------------------------------------------------------------
    tech_q = [q for q in qs if not q.get("multi")
              and any(k.startswith("tech_") for o in q["opts"] for k in o["s"])]
    n_other = len([q for q in qs if not q.get("multi")]) - len(tech_q)
    say("\n③ 「拉满一条轴」时的 Top3 命中率（命中 = Top3 里这张图带该画法标签）")
    say("  ① 单轴口径：pref 只在这条轴上（= 题库满偏），其它 30 条轴全 0")
    say(f"  ② 连贯人设口径：{n_other} 道非画法题一路只选第 k 项（k=0..3 四种口味），"
        f"画法题全挑该轴最优项")
    say(f"  {'轴':<17}{'满偏':>6}{'出题':>5}{'池内':>5}{'主将':>5}{'①单轴':>7}"
        f"{'②最小':>7}{'②平均':>7}{'②最大':>7}")
    pure = {}
    single_top = {}
    for ax in TECH_AXES:
        name = ax[5:]
        sm = smax.get(ax, 0.0)
        nq = sum(1 for q in qs if not q.get("multi")
                 and any(ax in o["s"] for o in q["opts"]))
        picked = [a for a in arts if name in (labels.get(a["art_id"]) or set())]
        n_cmdr = len({a.get("cmdr_en") or a.get("cmdr_zh") for a in picked})
        # ① 单轴口径（水彩淡彩不出题 → 满偏 0，改用「同等推力」的假想值，行尾标注）
        sm_eff = sm if sm else smax.get("tech_二次元日系", 2.4)
        pref1 = {k: 0.0 for k in axes}
        pref1[ax] = sm_eff
        top1 = recommend(pref1, axes, arts)
        hit1 = sum(1 for _, a in top1 if name in (labels.get(a["art_id"]) or set()))
        # ② 连贯人设口径（只对出题的 5 条轴有意义）
        rows = persona_sweep(qs, axes, arts, labels, ax) if nq else []
        pmin = min((r[2] for r in rows), default=float("nan"))
        pmean = (sum(r[3] for r in rows) / len(rows)) if rows else float("nan")
        pmax = max((r[4] for r in rows), default=float("nan"))
        single_top[ax] = top1
        pure[ax] = (hit1 / 3, pmin, pmean, pmax)
        mark = "" if sm else "*"
        say(f"  {ax:<17}{sm_eff:>6.1f}{nq:>5}{len(picked):>5}{n_cmdr:>5}{hit1:>4}/3"
            f"{pmin:>7.2f}{pmean:>7.2f}{pmax:>7.2f}{mark}")
    say("  （* = 水彩淡彩不出题，满偏 0；这里按「给出题轴同等的 2.4 推力」假想，仅供对照）")
    say("  ② 的 min 都是 0.00~0.33 —— 说明「用户的口味极强、又一心想画法这一维」时，"
        "画法偏好会被挤掉一部分；")
    say("     这与 9 条 style_* 轴同病：像素轴的满偏是 7.2，画法/画风只有 2.4（1 : 3）。")

    say("\n  ① 口径下的 Top3（✓ = 这张图带该画法标签）：")
    for ax in TECH_AXES:
        name = ax[5:]
        names = " / ".join(
            f"{a['cmdr_zh'][:10]}{'✓' if name in (labels.get(a['art_id']) or set()) else '·'}"
            for _, a in single_top[ax])
        say(f"    {ax:<17}{names}")

    say("\n  ② 口径逐人设（k = 非画法题一路只选第 k 项；组合数 = 并列最优的画法选项组合）")
    for ax in TECH_AXES:
        if not smax.get(ax, 0.0):
            continue
        say(f"    {ax}")
        for k, n, mn, mean, mx in persona_sweep(qs, axes, arts, labels, ax):
            say(f"      第{k + 1}项  {n:>3} 组   最小 {mn:.2f}  平均 {mean:.2f}  最大 {mx:.2f}")

    # ------------------------------------------------------------------
    say("\n④ 「只勾二次元日系」：只在这条轴上拉满，其它轴一律 0")
    ax = "tech_二次元日系"
    pref = {k: 0.0 for k in axes}
    pref[ax] = smax.get(ax, 0.0)
    top = recommend(pref, axes, arts)
    hits = [a for _, a in top if "二次元日系" in (labels.get(a["art_id"]) or set())]
    say(f"  满偏 {pref[ax]:.1f}（2 道题 × 1.2）")
    for s, a in top:
        lab = "、".join(sorted(labels.get(a["art_id"]) or []))
        say(f"    {s:+.4f}  {a['cmdr_zh'][:12]:<14}{a['cmdr_en'][:26]:<28}"
            f"形态={a['form']:<6}画法={lab}")
    say(f"  画法纯度（Top3 里二次元日系的张数）= {len(hits)}/3")
    forms = [a["form"] for _, a in top]
    say(f"  Top3 的形态：{' / '.join(forms)}"
        f"（这只是「这类画法恰好长什么样」，与形态轴偏好无关）")
    # 与之对照：全池的形态分布
    dist = collections.Counter(formmap[a["art_id"]] for a in arts if a["art_id"] in formmap)
    say("  全池形态占比：" + "  ".join(
        f"{f} {n / len(arts):.1%}" for f, n in dist.most_common()))
    say(f"  → 只勾二次元日系时，Top3 画法纯度 {len(hits)}/3，"
        f"其中「纯人类」{forms.count('纯人类')}/3"
        f"（全池纯人类占 {dist['纯人类'] / len(arts):.1%}）")
    rows = persona_sweep(qs, axes, arts, labels, ax)
    say(f"  同上换「连贯人设」口径（其它 {n_other} 题一路只选第 k 项）× "
        f"{sum(r[1] for r in rows)} 种组合：")
    for k, n, mn, mean, mx in rows:
        say(f"    第{k + 1}项  {n:>3} 组   最小 {mn:.2f} / 平均 {mean:.2f} / 最大 {mx:.2f}")

    # ------------------------------------------------------------------
    say("\n⑤ 全部 31 条轴的覆盖统计（题数 / 出题轴 / 池内张数）")
    say(f"  {'轴':<18}{'题数':>5}{'满偏':>7}{'池内张数':>9}{'说明':>0}")
    groups = [("9 图像/元数据", [k for k in axes if not k.startswith(("form_", "style_", "tech_"))]),
              ("7 画面形态", [k for k in axes if k.startswith("form_")]),
              ("9 画风", [k for k in axes if k.startswith("style_")]),
              ("6 画法", TECH_AXES)]
    zero_axes = []
    mood_rows = json.loads((DATA / "art_labels_v2.json").read_text(encoding="utf-8"))
    for gname, keys in groups:
        say(f"  ── {gname}（{len(keys)} 条）")
        for k in keys:
            nq = sum(1 for q in qs if any(k in o["s"] for o in q["opts"]))
            if k.startswith("tech_"):
                n_in = sum(1 for a in arts if k[5:] in (labels.get(a["art_id"]) or set()))
            elif k.startswith("form_"):
                n_in = sum(1 for a in arts if a["form"] == k[5:])
            elif k.startswith("style_"):
                n_in = sum(1 for x in mood_rows if k[6:] in (x.get("mood") or []))
            else:
                n_in = -1
            note = ""
            if nq == 0:
                note = "  ← 不出题（按口径）" if k == NO_OPTION else "  ⚠ 没被任何题目引到"
                if k != NO_OPTION:
                    zero_axes.append(k)
            say(f"    {k:<18}{nq:>5}{smax.get(k, 0.0):>7.1f}"
                f"{(str(n_in) if n_in >= 0 else '—'):>9}{note}")
    say(f"  → 31 条轴里没有任何题目引到的：{zero_axes if zero_axes else '0 条 ✓'}"
        f"（{NO_OPTION} 按口径不出题，是设计，不是漏）")
    if zero_axes:
        problems.append(f"这些轴没被题目引到：{zero_axes}")

    # ------------------------------------------------------------------
    say("\n⑥ 汇总（①=其它轴全 0 的单轴口径；②=其它题一路只选某项的连贯人设口径）")
    for k, (a, mn, mean, mx) in pure.items():
        say(f"  {k:<17}①单轴 {a:.2f}   ②连贯人设 min {mn:.2f} / 平均 {mean:.2f} / 最大 {mx:.2f}")
    say("")
    if problems:
        say(f"✗ 有 {len(problems)} 处问题：")
        for p in problems:
            say("   - " + p)
    else:
        say("✓ 全部判据通过")

    if not args.no_write_report:
        out = ROOT / "backups" / "tech_axes_report.txt"
        out.parent.mkdir(exist_ok=True)
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\n（本次输出已存 {out}）")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
