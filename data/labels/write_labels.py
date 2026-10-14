import json, os, sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

OUT = r"D:\万智\commander-art-quiz\data\labels\sheet_25_28.json"
os.makedirs(os.path.dirname(OUT), exist_ok=True)

L = [
    (217, "生物", "机械", ["神秘", "激烈"], "中"),
    (218, "人物", "其他", ["神秘"], "中"),
    (219, "人物", "人类", ["史诗", "激烈"], "中"),
    (220, "场景", "无", ["激烈"], "低"),
    (221, "人物", "其他", ["激烈", "黑暗"], "中"),
    (222, "人物", "哥布林", ["怪诞", "黑暗"], "中"),
    (223, "生物", "巨龙", ["史诗", "神秘"], "中"),
    (224, "人物", "其他", ["宁静", "神秘"], "中"),
    (225, "人物", "人类", ["神秘", "激烈"], "中"),
    (226, "人物", "人类", ["激烈"], "中"),
    (227, "人物", "人类", ["温暖"], "高"),
    (228, "抽象", "无", ["黑暗", "怪诞"], "低"),
    (229, "人物", "人类", ["激烈"], "高"),
    (230, "人物", "人类", ["怪诞", "神秘"], "中"),
    (231, "生物", "巨龙", ["史诗", "神秘"], "中"),
    (232, "人物", "亡灵", ["黑暗", "怪诞"], "高"),
    (233, "人物", "人类", ["史诗"], "中"),
    (234, "人物", "人类", ["神秘", "黑暗"], "中"),
    (235, "人物", "矮人", ["温暖"], "低"),
    (236, "人物", "吸血鬼", ["黑暗", "怪诞"], "中"),
    (237, "生物", "巨龙", ["史诗", "神秘"], "高"),
    (238, "人物", "恶魔", ["怪诞", "神秘"], "中"),
    (239, "生物", "巨龙", ["怪诞"], "中"),
    (240, "人物", "人类", ["黑暗", "神秘"], "中"),
    (241, "人物", "人类", ["激烈", "神秘"], "低"),
    (242, "人物", "人类", ["激烈"], "中"),
    (243, "人物", "精灵", ["宁静", "神秘"], "中"),
    (244, "人物", "人类", ["可爱", "温暖"], "中"),
    (245, "生物", "其他", ["温暖"], "中"),
    (246, "人物", "其他", ["黑暗", "史诗"], "低"),
    (247, "生物", "其他", ["怪诞", "黑暗"], "中"),
    (248, "人物", "人类", ["宁静"], "高"),
    (249, "人物", "人类", ["黑暗", "神秘"], "高"),
    (250, "人物", "人类", ["神秘", "史诗"], "低"),
    (251, "人物", "人类", ["史诗"], "高"),
    (252, "人物", "人类", ["可爱", "神秘"], "低"),
]

labels = [{"n": n, "subject": s, "race": r, "mood": m, "conf": c} for n, s, r, m, c in L]

with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"labels": labels}, f, ensure_ascii=False, indent=1)

# verification
ns = [d["n"] for d in labels]
print("count:", len(labels), "range:", min(ns), "-", max(ns), "contiguous:", ns == list(range(217, 253)))
print("conf low:", [d["n"] for d in labels if d["conf"] == "低"])
for key in ("subject", "race", "conf"):
    print(key, dict(Counter(d[key] for d in labels)))
print("mood", dict(Counter(m for d in labels for m in d["mood"])))
subj_ok = all((d["race"] == "无") == (d["subject"] in ("场景", "抽象")) for d in labels)
print("race/subject consistency:", subj_ok)
print("mood<=2:", all(len(d["mood"]) <= 2 for d in labels))
print("written:", OUT, os.path.getsize(OUT), "bytes")
