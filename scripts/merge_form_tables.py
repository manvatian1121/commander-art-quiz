#!/usr/bin/env python3
"""把三份形态表合并成唯一的一份 —— art_form.json。

为什么会有三份：
  · f91a2998 代理的 art_form_v2.json  —— 最新、最细的一版（含量化判据实测）
  · 我手工写的 art_form_v3.json       —— 只做了改名与剔除，形态值比 v2 旧
  · 277ed1af 代理同步的 art_form.json —— 管线在用的

三份的差异只有 4 格，合并时按 v2 的口径（它有第五轮的读图与量化测量）：
  n27   主体是风景（瀑布＋苔林＋中央宝石，鹿只占约 10%）→ 剔除
  n160  无定形胶状团块，无头无足只有锯齿口盖＋触须肢 → 扭曲异形
  n247  纯线团里嵌一张脸 → 扭曲异形
  n316  团块＋环形多眼＋多肢，无正常动物体构 → 扭曲异形

合并后 art_form.json 应为 378 行（含 8 张 excluded），
v2 / v3 两份草稿改名归档，避免下游拿到不一致的表。
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
DATA = pathlib.Path(r"D:/万智/commander-art-quiz/data")

OLD = ["无生物", "变异人形"]          # 已被取消 / 已更名


def main() -> int:
    full = json.loads((DATA / "art_form.json").read_text(encoding="utf-8"))
    v2 = json.loads((DATA / "art_form_v2.json").read_text(encoding="utf-8"))
    v2m = {x["n"]: x for x in (v2 if isinstance(v2, list) else v2.get("items", []))}
    print(f"管线表 {len(full)} 行　v2 草稿 {len(v2m)} 行")

    applied = 0
    for rec in full:
        src = v2m.get(rec["n"])
        if not src:
            continue
        if rec.get("form") != src.get("form"):
            applied += 1
        rec["form"] = src["form"]
        rec["form_conf"] = src.get("form_conf", rec.get("form_conf"))
        rec["why"] = src.get("why", rec.get("why"))
        # excluded：v2 的判定优先，但已有的 true 不被 false 覆盖
        if src.get("excluded"):
            rec["excluded"] = True
        rec.setdefault("excluded", False)

    # 无效类名清零
    bad = [r["n"] for r in full if r.get("form") in OLD]
    for n in bad:
        rec = next(r for r in full if r["n"] == n)
        rec["form"] = "扭曲异形" if rec["form"] == "无生物" else "人形异类"
    print(f"  采用 v2 口径的形态值 {applied} 处；无效类名修正 {len(bad)} 处")

    (DATA / "art_form.json").write_text(
        json.dumps(full, ensure_ascii=False, indent=1), encoding="utf-8")

    # 归档两份草稿，避免下游拿到不一致的表
    for f in ("art_form_v2.json", "art_form_v3.json"):
        p = DATA / f
        if p.exists():
            shutil.move(str(p), str(DATA / "_archive" / f)
                        if (DATA / "_archive").exists() else str(DATA / f"{f}.merged"))

    live = [r for r in full if not r.get("excluded")]
    exc = [r["n"] for r in full if r.get("excluded")]
    c = Counter(r["form"] for r in live)
    print(f"\n=== 合并后（参与池 {len(live)} 张，剔除 {len(exc)} 张）===")
    for k, v in c.most_common():
        print(f"  {k:<8} {v:>3}  {v/len(live)*100:>5.1f}%")
    print(f"\n  剔除的编号：{sorted(exc)}")
    low = [r["n"] for r in live if r.get("form_conf") == "低"]
    print(f"  仍标低把握：{sorted(low)}")

    bad2 = [r["n"] for r in full if r.get("form") in OLD]
    print(f"\n  无效类名残留：{len(bad2)} 处 {'✓' if not bad2 else bad2}")
    for f in ("art_form_v2.json", "art_form_v3.json"):
        print(f"  {f} 已归档：{'是' if not (DATA / f).exists() else '否'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
