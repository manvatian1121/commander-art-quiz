# -*- coding: utf-8 -*-
"""生成按 n 升序的标注骨架：每行 = 联系表内位置 -> n 与 art_id。
用法：python scripts/_style_skeleton.py 1..42  -> 打印指定页的 9 格元数据
"""
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
idx = json.load(open(os.path.join(DATA, "_style_sheets_index.json"), encoding="utf-8"))
form = {r["n"]: r for r in json.load(open(os.path.join(DATA, "art_form.json"), encoding="utf-8"))}
axes = {r["art_id"]: r for r in json.load(open(os.path.join(DATA, "art_axes.json"), encoding="utf-8"))}

want = [int(a) for a in sys.argv[1:]] or list(range(1, len(idx) + 1))
for p in want:
    e = idx[p - 1]
    print("== sheet %s ==" % e["sheet"])
    for i, n in enumerate(e["ns"]):
        a = axes.get(form[n]["art_id"], {})
        print("  pos%-2d n=%-4d %-22s | %s" % (
            i + 1, n, a.get("artist", "?")[:22], a.get("cmdr_zh", "?")))
