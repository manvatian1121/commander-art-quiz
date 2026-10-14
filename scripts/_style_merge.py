# -*- coding: utf-8 -*-
"""合并 a-g 批次 + 复核修正，产出 data/art_style.json（370 条，按 n 升序）。
并打印自检结果。
"""
import sys, os, json, importlib.util
sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SC = os.path.join(ROOT, "scripts")

VOCAB = {"二次元日系", "欧美厚涂", "水彩淡彩", "线稿版画", "卡通绘本", "写实数字绘"}
CONF = {"高", "中", "低"}


def load(mod, attr="L"):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(SC, mod + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return getattr(m, attr)


L = {}
for mod in ["_style_labels_a", "_style_labels_b", "_style_labels_c", "_style_labels_d",
            "_style_labels_e", "_style_labels_f", "_style_labels_g"]:
    d = load(mod)
    dup = set(d) & set(L)
    assert not dup, ("批次重复", mod, dup)
    L.update(d)
print("批次合并后条数:", len(L))

FIX = load("_style_labels_fix", "FIX")
print("复核修正条数:", len(FIX))
L.update(FIX)

form = json.load(open(os.path.join(DATA, "art_form.json"), encoding="utf-8"))
items = sorted([r for r in form if not r.get("excluded")], key=lambda r: r["n"])
assert len(items) == 370

missing = [r["n"] for r in items if r["n"] not in L]
extra = sorted(set(L) - {r["n"] for r in items})
print("未标注:", missing)
print("多余/越界:", extra)
assert not missing and not extra

out = []
for r in items:
    st, cf, why = L[r["n"]]
    assert isinstance(st, list) and 1 <= len(st) <= 2, (r["n"], st)
    assert len(set(st)) == len(st), (r["n"], "重复词")
    for s in st:
        assert s in VOCAB, (r["n"], s)
    assert cf in CONF, (r["n"], cf)
    out.append({"n": r["n"], "art_id": r["art_id"], "style": st, "conf": cf, "why": why})

# 护栏：与 art_form / art_axes 的 n-art_id 逐条对齐
axes = {a["art_id"]: a for a in json.load(open(os.path.join(DATA, "art_axes.json"), encoding="utf-8"))}
for o, r in zip(out, items):
    assert o["n"] == r["n"] and o["art_id"] == r["art_id"], ("错位", o["n"])
    assert o["art_id"] in axes, ("art_id 不在 art_axes", o["n"])
assert len({o["art_id"] for o in out}) == 370, "art_id 重复"

dst = os.path.join(DATA, "art_style.json")
json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------------- 自检输出 ----------------
from collections import Counter
c = Counter()
for o in out:
    for s in o["style"]:
        c[s] += 1
print("\n== 1. 条数 / n 完整性 ==")
ns = [o["n"] for o in out]
print("总条数", len(out), "| n 唯一", len(set(ns)), "| n 连续且等于 1..378 去掉 excluded",
      ns == [r["n"] for r in items])
print("== 2. 词表 / 每格上限 ==")
print("全部 style 均在封闭词表:", all(s in VOCAB for o in out for s in o["style"]))
print("每格 ≤2:", all(len(o["style"]) <= 2 for o in out),
      "| 单标", sum(1 for o in out if len(o["style"]) == 1),
      "| 双标", sum(1 for o in out if len(o["style"]) == 2))
print("\n== 3. 6 类计数分布（含次标，故合计 > 370）==")
for k, v in c.most_common():
    print("  %-8s %3d  (%.1f%%)" % (k, v, v / 370 * 100))
print("  合计标签数", sum(c.values()))
print("\n  -- 仅主标（style[0]）分布 --")
c0 = Counter(o["style"][0] for o in out)
for k, v in c0.most_common():
    print("  %-8s %3d  (%.1f%%)" % (k, v, v / 370 * 100))

print("\n== 4. conf 分布 ==")
print(dict(Counter(o["conf"] for o in out)))
low = [o["n"] for o in out if o["conf"] == "低"]
print("conf=低 共 %d 条:" % len(low))
print(low)

print("\n== 5. 二次元日系 全部编号 ==")
ani = [o["n"] for o in out if "二次元日系" in o["style"]]
ani_main = [o["n"] for o in out if o["style"][0] == "二次元日系"]
print("含二次元日系（主或次）共 %d 条:" % len(ani))
print(ani)
print("其中主标为二次元日系共 %d 条:" % len(ani_main))
print(ani_main)
print("主标二次元日系的 conf 分布:",
      dict(Counter(o["conf"] for o in out if o["style"][0] == "二次元日系")))

print("\n== 6. 双标（主+次）清单 ==")
for o in out:
    if len(o["style"]) == 2:
        print("  n=%-4d %s | %s" % (o["n"], "+".join(o["style"]), o["why"]))
print("\n写出:", dst)
