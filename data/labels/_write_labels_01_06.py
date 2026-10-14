import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")

labels = [
    {"n": 1,  "subject": "人物", "race": "人类",   "mood": ["史诗"],             "conf": "中"},
    {"n": 2,  "subject": "生物", "race": "巨龙",   "mood": ["激烈", "黑暗"],     "conf": "高"},
    {"n": 3,  "subject": "人物", "race": "人类",   "mood": ["温暖"],             "conf": "高"},
    {"n": 4,  "subject": "抽象", "race": "无",     "mood": ["神秘"],             "conf": "高"},
    {"n": 5,  "subject": "生物", "race": "野兽",   "mood": ["怪诞"],             "conf": "高"},
    {"n": 6,  "subject": "生物", "race": "其他",   "mood": ["怪诞", "黑暗"],     "conf": "中"},
    {"n": 7,  "subject": "人物", "race": "哥布林", "mood": ["怪诞"],             "conf": "中"},
    {"n": 8,  "subject": "人物", "race": "人类",   "mood": ["激烈"],             "conf": "高"},
    {"n": 9,  "subject": "人物", "race": "人类",   "mood": ["神秘"],             "conf": "低"},
    {"n": 10, "subject": "人物", "race": "人类",   "mood": ["激烈", "史诗"],     "conf": "高"},
    {"n": 11, "subject": "生物", "race": "野兽",   "mood": ["激烈", "怪诞"],     "conf": "中"},
    {"n": 12, "subject": "人物", "race": "人类",   "mood": ["神秘", "史诗"],     "conf": "中"},
    {"n": 13, "subject": "人物", "race": "人类",   "mood": ["神秘"],             "conf": "中"},
    {"n": 14, "subject": "人物", "race": "人类",   "mood": ["史诗"],             "conf": "中"},
    {"n": 15, "subject": "人物", "race": "其他",   "mood": ["神秘", "黑暗"],     "conf": "低"},
    {"n": 16, "subject": "人物", "race": "其他",   "mood": ["怪诞"],             "conf": "低"},
    {"n": 17, "subject": "人物", "race": "其他",   "mood": ["激烈"],             "conf": "低"},
    {"n": 18, "subject": "人物", "race": "人类",   "mood": ["可爱"],             "conf": "高"},
    {"n": 19, "subject": "生物", "race": "巨龙",   "mood": ["黑暗"],             "conf": "高"},
    {"n": 20, "subject": "生物", "race": "其他",   "mood": ["怪诞", "黑暗"],     "conf": "高"},
    {"n": 21, "subject": "人物", "race": "人类",   "mood": ["激烈"],             "conf": "高"},
    {"n": 22, "subject": "人物", "race": "亡灵",   "mood": ["黑暗", "怪诞"],     "conf": "中"},
    {"n": 23, "subject": "抽象", "race": "无",     "mood": ["激烈", "黑暗"],     "conf": "中"},
    {"n": 24, "subject": "人物", "race": "人类",   "mood": ["激烈"],             "conf": "高"},
    {"n": 25, "subject": "生物", "race": "巨龙",   "mood": ["史诗", "宁静"],     "conf": "高"},
    {"n": 26, "subject": "抽象", "race": "无",     "mood": ["怪诞"],             "conf": "中"},
    {"n": 27, "subject": "场景", "race": "无",     "mood": ["宁静", "神秘"],     "conf": "高"},
    {"n": 28, "subject": "人物", "race": "精灵",   "mood": ["史诗"],             "conf": "高"},
    {"n": 29, "subject": "生物", "race": "野兽",   "mood": ["激烈", "怪诞"],     "conf": "中"},
    {"n": 30, "subject": "人物", "race": "人类",   "mood": ["黑暗"],             "conf": "中"},
    {"n": 31, "subject": "生物", "race": "其他",   "mood": ["神秘"],             "conf": "低"},
    {"n": 32, "subject": "人物", "race": "人类",   "mood": ["神秘"],             "conf": "中"},
    {"n": 33, "subject": "人物", "race": "哥布林", "mood": ["怪诞"],             "conf": "中"},
    {"n": 34, "subject": "生物", "race": "其他",   "mood": ["怪诞", "激烈"],     "conf": "中"},
    {"n": 35, "subject": "人物", "race": "人类",   "mood": ["史诗", "温暖"],     "conf": "高"},
    {"n": 36, "subject": "人物", "race": "人类",   "mood": ["史诗", "神秘"],     "conf": "中"},
    {"n": 37, "subject": "人物", "race": "其他",   "mood": ["史诗", "温暖"],     "conf": "低"},
    {"n": 38, "subject": "人物", "race": "人类",   "mood": ["黑暗", "神秘"],     "conf": "中"},
    {"n": 39, "subject": "人物", "race": "其他",   "mood": ["怪诞", "黑暗"],     "conf": "低"},
    {"n": 40, "subject": "人物", "race": "其他",   "mood": ["激烈", "怪诞"],     "conf": "中"},
    {"n": 41, "subject": "人物", "race": "人类",   "mood": ["激烈"],             "conf": "高"},
    {"n": 42, "subject": "人物", "race": "人类",   "mood": ["史诗"],             "conf": "高"},
    {"n": 43, "subject": "人物", "race": "其他",   "mood": ["宁静", "温暖"],     "conf": "低"},
    {"n": 44, "subject": "生物", "race": "野兽",   "mood": ["可爱"],             "conf": "高"},
    {"n": 45, "subject": "人物", "race": "人类",   "mood": ["可爱", "温暖"],     "conf": "高"},
    {"n": 46, "subject": "人物", "race": "人类",   "mood": ["神秘", "宁静"],     "conf": "中"},
    {"n": 47, "subject": "人物", "race": "人类",   "mood": ["黑暗", "神秘"],     "conf": "低"},
    {"n": 48, "subject": "抽象", "race": "无",     "mood": ["怪诞"],             "conf": "高"},
    {"n": 49, "subject": "人物", "race": "人类",   "mood": ["温暖"],             "conf": "高"},
    {"n": 50, "subject": "生物", "race": "巨龙",   "mood": ["史诗"],             "conf": "高"},
    {"n": 51, "subject": "人物", "race": "人类",   "mood": ["宁静"],             "conf": "中"},
    {"n": 52, "subject": "生物", "race": "野兽",   "mood": ["怪诞"],             "conf": "中"},
    {"n": 53, "subject": "生物", "race": "野兽",   "mood": ["可爱"],             "conf": "中"},
    {"n": 54, "subject": "人物", "race": "人类",   "mood": ["宁静"],             "conf": "低"},
]

assert [x["n"] for x in labels] == list(range(1, 55)), "编号不连续"

out_dir = r"D:\万智\commander-art-quiz\data\labels"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "sheet_01_06.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({"labels": labels}, f, ensure_ascii=False, indent=1)

# --- 统计 ---
from collections import Counter
def dist(key, multi=False):
    c = Counter()
    for x in labels:
        v = x[key]
        if multi:
            for m in v:
                c[m] += 1
        else:
            c[v] += 1
    return c

print("输出:", out_path, os.path.getsize(out_path), "bytes")
print("总格数:", len(labels))
print("subject:", dict(dist("subject")))
print("race:", dict(dist("race")))
print("mood:", dict(dist("mood", multi=True)))
print("conf:", dict(dist("conf")))
print("低把握编号:", [x["n"] for x in labels if x["conf"] == "低"])
print("无subject=场景/抽象的race非无:", [(x["n"], x["race"]) for x in labels if x["subject"] in ("场景", "抽象") and x["race"] != "无"])
print("mood>2:", [x["n"] for x in labels if len(x["mood"]) > 2])
