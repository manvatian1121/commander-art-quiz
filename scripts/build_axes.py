#!/usr/bin/env python3
"""修轴标度：让 10 个轴真正「零均值 + 等方差」。

问题（子代理报的第一条数据问题）：
  starart 用百分位秩时，因为画师频次只有 1~6、并列极多，
  平均秩导致中位数不回零——实测是 [−0.2518, +0.4908]，中位数 +0.1342。
  后果两层：
    ① 对全池有一个正偏置（所有卡在这个轴上都偏高）
    ② 它的实际摆幅比其他轴小 1.8 倍，权重 1.4 打上去不等于别的轴的 1.4

统一修法（对所有 10 个轴）：
  z = (百分位秩 − 均值) / 标准差
  再乘 √(1/12) ≈ 0.2887 —— 这是均匀分布的标准差，
  这样每个轴的 SD 都是 0.2887，权重才有统一的含义。
  同时均值天然归零。

二值轴（borderless）也走同一条路：先转成百分位秩再标准化，
否则 0/1 的方差和连续轴差太远。
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(r"D:/万智/commander-art-quiz")
DATA = ROOT / "data"
MANIFEST = DATA / "art_manifest.json"
OUT = DATA / "art_axes.json"

AXES = ["warm", "bright", "vivid", "rich", "detailed",
        "contrasty", "darkarea", "modern", "borderless", "starart"]
UNIFORM_SD = 1.0 / np.sqrt(12.0)          # ≈ 0.2887


def pct_rank(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    order = v.argsort()
    ranks = np.empty(len(v), dtype=float)
    ranks[order] = np.arange(len(v), dtype=float)
    uniq, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
    sums = np.zeros(len(uniq))
    np.add.at(sums, inv, ranks)
    ranks = (sums / cnt)[inv]
    return ranks / max(1, len(v) - 1)


def main() -> int:
    items = json.loads(MANIFEST.read_text(encoding="utf-8"))
    items = [x for x in items if "art" in x]
    n = len(items)
    print(f"标准化 {n} 张卡的 10 个轴\n")

    year = np.array([int((x.get("released_at") or "2000")[:4]) for x in items], float)
    afreq = np.array([Counter(x.get("artist") or "?" for x in items)[
        x.get("artist") or "?"] for x in items], float)
    borderless = np.array([1.0 if (x.get("full_art")
                                   or x.get("border_color") == "borderless"
                                   or "extendedart" in (x.get("frame_effects") or []))
                           else 0.0 for x in items])

    raw = {
        "warm": np.array([x["art"]["warmth"] for x in items]),
        "bright": np.array([x["art"]["brightness"] for x in items]),
        "vivid": np.array([x["art"]["saturation"] for x in items]),
        "rich": np.array([x["art"]["variety"] for x in items]),
        "detailed": np.array([x["art"]["detail"] for x in items]),
        "contrasty": np.array([x["art"]["contrast"] for x in items]),
        "darkarea": np.array([x["art"]["dark_ratio"] for x in items]),
        "modern": year,
        "borderless": borderless,
        "starart": afreq,
    }

    norm = {}
    print(f"  {'轴':<11} {'均值(改前)':>10} {'SD(改前)':>9} → "
          f"{'均值(改后)':>10} {'SD(改后)':>9}")
    for a in AXES:
        r = pct_rank(raw[a])          # 二值轴也先转秩
        before_m, before_s = r.mean() - 0.5, r.std(ddof=0)
        z = (r - r.mean()) / (r.std(ddof=0) or 1.0) * UNIFORM_SD
        norm[a] = z
        print(f"  {a:<11} {r.mean()-0.5:>10.4f} {before_s:>9.4f} → "
              f"{z.mean():>10.4f} {z.std(ddof=0):>9.4f}")

    out = []
    for i, x in enumerate(items):
        out.append({
            "art_id": x["art_id"], "cmdr_en": x["cmdr_en"], "cmdr_zh": x["cmdr_zh"],
            "cmdr_rank": x["cmdr_rank"], "cmdr_colors": x["cmdr_colors"],
            "face": x["face"], "face_name": x["face_name"],
            "artist": x.get("artist"), "set_name": x.get("set_name"),
            "released_at": x.get("released_at"), "promo": x.get("promo"),
            "vec": {a: round(float(norm[a][i]), 4) for a in AXES},
            "local_art_crop": x.get("local_art_crop"),
            "local_normal": x.get("local_normal"),
            "local_large": x.get("local_large"),
            "art_raw": x["art"],
        })
    # 本脚本只重算原有 10 个轴。art_axes.json 里还有 scripts/add_form_axes.py 标的
    # 6 个 form_* 轴 —— 这里直接拒写，否则一跑就把形态轴（和 excluded 标记）冲掉。
    if OUT.exists():
        old = json.loads(OUT.read_text(encoding="utf-8"))
        if any(any(k.startswith("form_") for k in a.get("vec", {})) or a.get("excluded")
               for a in old):
            print(f"✗ {OUT.name} 里已经有 form_* 形态轴 / excluded 标记，本脚本会把它们冲掉。\n"
                  f"  形态轴请用 scripts/add_form_axes.py 重新标定；"
                  f"要强制只用 10 轴重建，先把 art_axes.json 备份并删掉。", file=sys.stderr)
            return 1

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n写出 {OUT.name}")
    print("\n=== 抽查：各轴最高 / 最低 ===")
    for a in ("warm", "bright", "vivid", "detailed", "darkarea", "starart"):
        idx = np.argsort(norm[a])
        print(f"  {a:<10} 低：{items[idx[0]]['cmdr_zh'][:10]:<12}"
              f" 高：{items[idx[-1]]['cmdr_zh'][:10]:<12}"
              f" 摆幅 {norm[a].min():+.2f} ~ {norm[a].max():+.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
