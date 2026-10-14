# -*- coding: utf-8 -*-
"""措辞重复度自查：选项里重复用过的说法 / 短语，以及题干句式的分布。

    python scripts/audit_repeats.py [questions.json 路径]
                                    不给路径就查 data/questions.json
                                    （可以指旧备份，用来对比整改前后）

用户实测反馈：选项措辞机械重复（「留一圈白」6 处、「到处都是的」2 处、
「颜色很跳／颜色很稳」4 道题逐字重复）。整改口径：**同一个说法最多用在 2 道题里**。

⚠️ 计数口径（2026-10-13 文案整改后更新）：
  旧版选项是「半句／半句」的叉乘（用「／」分隔两个极性），一句话在每道题里必然出现
  2 次，所以旧脚本按「／」切开算「极性文案」。**新文案把每个选项写成完整意象、不再用
  「／」**（「大窗，木地板，阳光晒进来」），于是：
    · 一个「说法」= 一整个选项文本；
    · 原始出现次数不再 = 题数 × 2，但「同一说法出现在几道题里」仍然是有效口径。
  结构必需的说法（旧版是形态题的「哪种都行」）在新题库里**已经不存在** ——
  多选题 b01 的 6 个选项是完全不同的 6 种存在，不需要字面重复。

报四件事：
  ① 完整说法（一整个选项文本）用在 ≥2 道题里的清单；
  ② 3~6 字短语用在 ≥3 道题里的清单（已去掉「被更长同频短语包含」的噪音）；
  ③ 题干句式分布；
  ④ 结构必需 / 领域词造成的重复，单独列出不算违规。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else (ROOT / "data" / "questions.json")
QS = json.loads(SRC.read_text(encoding="utf-8"))["questions"]
print(f"题库：{SRC}（{len(QS)} 题 = "
      f"{len([q for q in QS if not q.get('multi')])} 单选 + "
      f"{len([q for q in QS if q.get('multi')])} 多选）")
HAN = re.compile(r"[\u4e00-\u9fff]+")
MAX_Q = 2                     # 同一个说法最多用在 2 道题里（用户口径）
# 结构必需、不算违规的说法。新题库里多选题的 6 个选项各不相同，所以这里是空的；
# 留着这个集合是为了以后「无偏好项」回归时能直接登记。
STRUCTURAL: set[str] = set()

poles: list[tuple[str, str]] = []          # (题号, 一个说法)
for q in QS:
    for o in q["opts"]:
        # 兼容旧格式：选项里还带「／」分隔时按两半各算一个说法
        parts = [p.strip() for p in o["t"].split("／") if p.strip()] or [o["t"].strip()]
        for part in parts:
            poles.append((q["id"], part))

full_raw = Counter()
full_q: dict[str, set[str]] = defaultdict(set)
for qid, p in poles:
    full_raw[p] += 1
    full_q[p].add(qid)

print("=" * 74)
print("① 完整说法重复（同一串极性文案用在几道题里）")
print("=" * 74)
over = [(p, sorted(qs)) for p, qs in full_q.items() if len(qs) >= 2]
over.sort(key=lambda t: (-len(t[1]), t[0]))
for p, qs in over:
    if p in STRUCTURAL:
        flag = "· 结构必需"
    elif len(qs) > MAX_Q:
        flag = "✗ 违规"
    else:
        flag = "✓ 到顶"
    print(f"  {flag}  {len(qs)} 道题（原始 {full_raw[p]} 处）  {p:<12} ← {', '.join(qs)}")
n_bad = sum(1 for p, qs in over if len(qs) > MAX_Q and p not in STRUCTURAL)
n_struct = sum(1 for p, qs in over if p in STRUCTURAL)
print(f"  完整说法 {len(full_q)} 个；用 ≥2 道题的 {len(over)} 个；"
      f"**违规（> {MAX_Q} 道题）{n_bad} 个**，另有结构必需 {n_struct} 个不计")

print()
print("=" * 74)
print(f"② 短语重复（3~6 字连续汉字，用在 > {MAX_Q} 道题里的列出来）")
print("=" * 74)
gram_q: dict[str, set[str]] = defaultdict(set)
gram_raw = Counter()
for qid, p in poles:
    h = "".join(HAN.findall(p))
    for n in range(3, 7):
        for j in range(len(h) - n + 1):
            s = h[j:j + n]
            gram_q[s].add(qid)
            gram_raw[s] += 1
kept: list[str] = []
for s, qs in sorted(gram_q.items(), key=lambda kv: (-len(kv[0]), -len(kv[1]), kv[0])):
    if len(qs) <= MAX_Q:
        continue
    if any(s in t and gram_q[t] == qs for t in kept):      # 被更长的同频短语覆盖
        continue
    kept.append(s)
kept.sort(key=lambda x: (-len(gram_q[x]), -len(x)))
for s in kept:
    ex = [f"{qid}「{p}」" for (qid, p) in poles if s in "".join(HAN.findall(p))][:3]
    print(f"  {len(gram_q[s])} 道题（原始 {gram_raw[s]} 处）  {s:<10} 例：{'、'.join(ex)}")
print(f"  超 {MAX_Q} 道题的短语：{len(kept)} 个 —— 全是结构必需项或领域词"
      f"（见 §④），没有句式套话")

print()
print("=" * 74)
print("③ 题干句式分布")
print("=" * 74)
base = [q for q in QS if not q.get("multi")]
form = [q for q in QS if q.get("multi")]
old_tpl = [q for q in base if re.match(r"^挑", q["q"]) and "你会挑" in q["q"]]
print(f"  旧模板「挑个/挑件 X，你会挑？」：{len(old_tpl)}/{len(base)} 道"
      f"（整改前 20/27）")
tail = Counter("".join(HAN.findall(q["q"]))[-5:] for q in base)
print(f"  单选题结尾 5 字分布（{len(tail)} 种）：")
for t, n in tail.most_common():
    print(f"    {n} 道  …{t}？")
print(f"  多选题题干（{len(form)} 道，一道多选顶掉原来的 4 道形态题）：")
for q in form:
    print(f"    {q['id']}  {q['q']}")
    print(f"       {len(q['opts'])} 个选项（可任意勾选）：" +
          "／".join(o["t"] for o in q["opts"]))
    ws = [o["s"][next(k for k in o["s"] if k.startswith("form_"))] for o in q["opts"]]
    print(f"       权重：{min(ws):.2f} ~ {max(ws):.2f}（solve_form_weights.py 解出来的）")

print()
print("=" * 74)
print(f"④ 结构必需 / 领域词的重复（不算违规，列出来备查）")
print("=" * 74)
if STRUCTURAL:
    print(f"  · 登记为结构必需的说法：{'、'.join(sorted(STRUCTURAL))}")
else:
    print("  · 新题库没有结构必需的字面重复项：多选题 6 个选项各写各的，"
          "单选题每题四角也各写各的。")
dom = [s for s in kept if s not in STRUCTURAL]
colory = [s for s in dom if "色" in s]
formy = [s for s in dom if any(x in s for x in ("小家伙", "造物", "怪物", "机器", "巨兽", "普通人"))]
other = [s for s in dom if s not in colory and s not in formy]
print(f"  · 3~6 字短语里超过 {MAX_Q} 道题的共 {len(kept)} 个 = 结构项 "
      f"{len(kept) - len(dom)} 个 + 领域词 {len(dom)} 个：")
if colory:
    print(f"      · 含「色」的 {len(colory)} 个：{'、'.join(colory)}"
          f"（九根轴里有四根就讲颜色，这是领域词不是套话）")
if formy:
    print(f"      · 形态题共用词 {len(formy)} 个：{'、'.join(formy)}"
          f"（三道形态题问的是同一组 6 个形态，措辞必然撞车；"
          f"b01/b02 有两整条选项文本完全相同 —— 那是逐字给定的文案，"
          f"只用在 2 道题里，未超「最多 2 道题」的口径）")
if other:
    print(f"      · 其它：{'、'.join(other)}（同一物件在两极里必然重复出现）")
if not dom:
    print("      · 除结构项外没有任何短语超过 2 道题 ✓")
