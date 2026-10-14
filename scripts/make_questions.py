# -*- coding: utf-8 -*-
"""生成 questions.json —— 20 道美术审美题，并做自检。

设计口径（写死在脚本里，方便复核）：
  10 个轴 × 每题 1~3 轴 × 权重 0.5~2.0
  每题内部：每个轴的权重**必须有正有负**（2 正 2 负），这样「暖 vs 冷」这类
            两端选择才表达得出来，也不会出现「四个选项都往同一个正方向推」。
  轴权重覆盖：每个轴恰好出现在 4 道题里，每题对该轴的平均 |w| 都是 1.4，
            所以每个轴的总权重 = 4 × 1.4 = 5.6，完全均衡。

  4 道纯轴题（单轴，±1.9 / ±0.9，均值 1.4）：
     a01 warm / a02 bright / a03 vivid / a04 detailed
  12 道双轴题（±1.4，2×2 四角）
  4 道三轴题（±1.4，Hadamard 四角）
"""
import sys, json, math, pathlib
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

W_STRONG, W_MILD, W2 = 1.9, 0.9, 1.4   # 纯轴题强/弱档、组合题档（三者均值都是 1.4）

AXES = ["warm", "bright", "vivid", "rich", "detailed",
        "contrasty", "darkarea", "modern", "borderless", "starart"]

Q: list[dict] = []


def add(qid: str, stem: str, opts: list[tuple[str, dict]]) -> None:
    Q.append({"id": qid, "q": stem,
              "opts": [{"t": t, "s": dict(s)} for t, s in opts]})


# ---------------------------------------------------------------- 纯轴题
add("a01", "同一片山谷的黄昏，四种调子摆在你面前。你眼睛最想停在哪一幅上？", [
    ("满眼金橘色，暖得像要烧起来", {"warm": +W_STRONG}),
    ("偏暖，暖色都堆在光落下来的那一片", {"warm": +W_MILD}),
    ("偏冷，只在角落里留了一点暖", {"warm": -W_MILD}),
    ("整幅青蓝紫，一丝暖意都没有", {"warm": -W_STRONG}),
])

add("a02", "一幅画整体是亮是暗，你更吃哪一头？", [
    ("近乎全亮，像正午直晒", {"bright": +W_STRONG}),
    ("整体亮，只压了几处深色", {"bright": +W_MILD}),
    ("整体偏暗，亮的地方就那么几处", {"bright": -W_MILD}),
    ("暗到接近夜色，只剩一点微光", {"bright": -W_STRONG}),
])

add("a03", "颜色的浓淡，你更偏哪边？", [
    ("浓到发亮，几乎要从画里溢出来", {"vivid": +W_STRONG}),
    ("偏浓，但还看得出颜色之间的层次", {"vivid": +W_MILD}),
    ("偏淡，颜色像被水洗过一遍", {"vivid": -W_MILD}),
    ("极淡，接近灰调，只透出一点点颜色", {"vivid": -W_STRONG}),
])

add("a04", "画面里塞多少东西，你觉得舒服？", [
    ("塞得满满当当，每个角落都有内容", {"detailed": +W_STRONG}),
    ("东西不少，但还留了几处空地", {"detailed": +W_MILD}),
    ("东西不多，大片地方空着", {"detailed": -W_MILD}),
    ("极简，就几个大色块，几乎不画细节", {"detailed": -W_STRONG}),
])

# ---------------------------------------------------------------- 双轴题
add("a05", "浓艳和多彩其实是两码事。这四个方向，你挑哪个？", [
    ("颜色浓到顶，而且十几种色相全用上", {"vivid": +W2, "rich": +W2}),
    ("颜色浓到顶，但翻来覆去就一个色系", {"vivid": +W2, "rich": -W2}),
    ("颜色很淡，色相却拉得很开，什么颜色都沾一点", {"vivid": -W2, "rich": +W2}),
    ("颜色很淡，而且整体就一个色调", {"vivid": -W2, "rich": -W2}),
])

add("a06", "细节和明暗反差，你更舍得在哪边下功夫？", [
    ("大片留白，明暗却拉得很硬", {"detailed": -W2, "contrasty": +W2}),
    ("细节堆到极致，明暗过渡却很柔", {"detailed": +W2, "contrasty": -W2}),
    ("细节堆到极致，明暗也拉得很开", {"detailed": +W2, "contrasty": +W2}),
    ("大片留白，明暗过渡也柔", {"detailed": -W2, "contrasty": -W2}),
])

add("a07", "暖冷和明暗，你会怎么配？", [
    ("暖调，而且整体亮堂堂的", {"warm": +W2, "bright": +W2}),
    ("暖调，但整体压得偏暗", {"warm": +W2, "bright": -W2}),
    ("冷调，整体亮堂堂的", {"warm": -W2, "bright": +W2}),
    ("冷调，而且整体压得偏暗", {"warm": -W2, "bright": -W2}),
])

add("a08", "用色多少和明暗跨度，你更想要哪种组合？", [
    ("颜色用得多，明暗跨度也拉得很开", {"rich": +W2, "contrasty": +W2}),
    ("颜色用得多，明暗却很柔", {"rich": +W2, "contrasty": -W2}),
    ("颜色用得少，明暗却拉得很开", {"rich": -W2, "contrasty": +W2}),
    ("颜色用得少，明暗也很柔", {"rich": -W2, "contrasty": -W2}),
])

add("a09", "光打下来的样子，你更想要哪一种？", [
    ("亮，光还很硬，影子边缘像刀切", {"bright": +W2, "contrasty": +W2}),
    ("亮得均匀，几乎没影子，像阴天的柔光", {"bright": +W2, "contrasty": -W2}),
    ("暗，一小束硬光打在焦点上", {"bright": -W2, "contrasty": +W2}),
    ("暗，而且灰蒙蒙一片，看不出光从哪来", {"bright": -W2, "contrasty": -W2}),
])

add("a11", "色相多和细节多，你更看重哪个？", [
    ("色相多，画面却很干净，不堆细节", {"rich": +W2, "detailed": -W2}),
    ("色相多，细节也堆得很满", {"rich": +W2, "detailed": +W2}),
    ("色相单一，细节却堆到极致", {"rich": -W2, "detailed": +W2}),
    ("色相单一，画面也干净利落", {"rich": -W2, "detailed": -W2}),
])

add("a12", "调子的冷暖，配上明暗的软硬，你选哪一套？", [
    ("暖调，明暗过渡很软，像褪色的旧照片", {"warm": +W2, "contrasty": -W2}),
    ("冷调，明暗拉得很硬，像金属反光", {"warm": -W2, "contrasty": +W2}),
    ("暖调，明暗拉得很硬", {"warm": +W2, "contrasty": +W2}),
    ("冷调，明暗过渡很软，像清晨的雾", {"warm": -W2, "contrasty": -W2}),
])

add("a13", "暖调和大块深色，你会怎么配？", [
    ("暖调，画面里大块大块的深色", {"warm": +W2, "darkarea": +W2}),
    ("冷调，通透明亮，几乎没有成片的深色", {"warm": -W2, "darkarea": -W2}),
    ("暖调，通透明亮，几乎没有成片的深色", {"warm": +W2, "darkarea": -W2}),
    ("冷调，画面里大块大块的深色", {"warm": -W2, "darkarea": +W2}),
])

add("a15", "用色多少配上整体明暗，你想要哪一种？", [
    ("颜色多，整体也明亮", {"rich": +W2, "bright": +W2}),
    ("颜色多，但整体压得很暗", {"rich": +W2, "bright": -W2}),
    ("颜色少，整体明亮", {"rich": -W2, "bright": +W2}),
    ("颜色少，整体也暗", {"rich": -W2, "bright": -W2}),
])

add("a16", "颜色浓淡和名字熟不熟，你会怎么配？", [
    ("颜色浓烈，作者是你早就眼熟的那几位", {"vivid": +W2, "starart": +W2}),
    ("颜色浓烈，作者是个你没听过的新名字", {"vivid": +W2, "starart": -W2}),
    ("颜色清淡，作者是个你没听过的新名字", {"vivid": -W2, "starart": -W2}),
    ("颜色清淡，作者是你早就眼熟的那几位", {"vivid": -W2, "starart": +W2}),
])

add("a18", "画法的新旧，配上画面铺得满不满，你更吃哪种？", [
    ("新派画法，画面一直铺到边", {"modern": +W2, "borderless": +W2}),
    ("老派画法，四周留一圈边", {"modern": -W2, "borderless": -W2}),
    ("新派画法，四周留一圈边", {"modern": +W2, "borderless": -W2}),
    ("老派画法，画面一直铺到边", {"modern": -W2, "borderless": +W2}),
])

add("a19", "画面里的深色块，和名字熟不熟，你怎么选？", [
    ("画面里大块大块的深色，作者的名字你早就见过很多次",
     {"darkarea": +W2, "starart": +W2}),
    ("画面里大块大块的深色，作者的名字你从没见过",
     {"darkarea": +W2, "starart": -W2}),
    ("画面通透明亮，作者的名字你从没见过",
     {"darkarea": -W2, "starart": -W2}),
    ("画面通透明亮，作者的名字你早就见过很多次",
     {"darkarea": -W2, "starart": +W2}),
])

# ---------------------------------------------------------------- 三轴题（Hadamard 四角）
add("a10", "挑一张海报贴墙上，你更吃哪一套？", [
    ("画法是这两年才有的，画面铺到纸边，作者的名字你早就见过很多次",
     {"modern": +W2, "borderless": +W2, "starart": +W2}),
    ("画法是这两年才有的，四周留一圈白边，作者是个你没听过的新名字",
     {"modern": +W2, "borderless": -W2, "starart": -W2}),
    ("画法是几十年前那一派，画面铺到纸边，作者是个你没听过的新名字",
     {"modern": -W2, "borderless": +W2, "starart": -W2}),
    ("画法是几十年前那一派，四周留一圈白边，作者的名字你早就见过很多次",
     {"modern": -W2, "borderless": -W2, "starart": +W2}),
])

add("a14", "画法新旧、名字熟不熟、颜色浓不浓——三件事一起看，你挑哪种？", [
    ("新派画法，作者眼熟，颜色很浓",
     {"modern": +W2, "starart": +W2, "vivid": +W2}),
    ("新派画法，生面孔，颜色很淡",
     {"modern": +W2, "starart": -W2, "vivid": -W2}),
    ("老派画法，作者眼熟，颜色很淡",
     {"modern": -W2, "starart": +W2, "vivid": -W2}),
    ("老派画法，生面孔，颜色很浓",
     {"modern": -W2, "starart": -W2, "vivid": +W2}),
])

add("a17", "同一幅画，你更愿意它长成哪种样子？", [
    ("画面铺到边，大片深色压着，细节堆得很满",
     {"borderless": +W2, "darkarea": +W2, "detailed": +W2}),
    ("画面铺到边，整体透亮，大片地方空着",
     {"borderless": +W2, "darkarea": -W2, "detailed": -W2}),
    ("四周留一圈边，大片深色压着，大片地方空着",
     {"borderless": -W2, "darkarea": +W2, "detailed": -W2}),
    ("四周留一圈边，整体透亮，细节堆得很满",
     {"borderless": -W2, "darkarea": -W2, "detailed": +W2}),
])

add("a20", "画法新旧、画面铺不铺满、深色多不多，你更吃哪种？", [
    ("新派画法，画面铺到边，大片深色压着",
     {"modern": +W2, "borderless": +W2, "darkarea": +W2}),
    ("新派画法，四周留边，画面基本是亮的",
     {"modern": +W2, "borderless": -W2, "darkarea": -W2}),
    ("老派画法，画面铺到边，画面基本是亮的",
     {"modern": -W2, "borderless": +W2, "darkarea": -W2}),
    ("老派画法，四周留边，大片深色压着",
     {"modern": -W2, "borderless": -W2, "darkarea": +W2}),
])

# 按 id 排序，保证 a01..a20 顺序稳定
Q.sort(key=lambda x: x["id"])

# ---------------------------------------------------------------- 位置偏置校正
# 固定选项顺序会让「一路选第 k 个」的人得到某种固定人设（初版实测 warm+6.1 /
# modern+5.6…），这是问卷设计的经典位置偏置。
# 这里在「允许的选项顺序」里做爬山搜索，把四个位置的向量都压到接近 0。
#   - 纯轴题（a01~a04）：只允许两种单调顺序（强→弱 / 弱→强），保持"梯度"读感
#   - 组合题：允许 24 种全排列
# 注意：任何重排都不改变「每轴正负各半」「选项集以 0 为中心」这两条性质。
import itertools, random

PURE = {"a01", "a02", "a03", "a04"}


def allowed_orders(q):
    opts = q["opts"]
    if q["id"] in PURE:
        # 纯轴题保持真正的「梯度」读感：强正 → 弱正 → 弱负 → 强负（或整体反过来）
        pos = sorted((o for o in opts if next(iter(o["s"].values())) > 0),
                     key=lambda o: -abs(next(iter(o["s"].values()))))
        neg = sorted((o for o in opts if next(iter(o["s"].values())) < 0),
                     key=lambda o: -abs(next(iter(o["s"].values()))))
        s = pos + neg
        return [s, list(reversed(s))]
    return [list(p) for p in itertools.permutations(opts)]


def total_cost(assign):
    tot = [[0.0] * len(AXES) for _ in range(4)]
    for q, order in assign:
        for k in range(4):
            for ax, v in order[k]["s"].items():
                tot[k][AXES.index(ax)] += v
    return sum(v * v for row in tot for v in row), tot


def _row(order):
    """把一份选项顺序压成 4×10 的贡献矩阵"""
    m = [[0.0] * len(AXES) for _ in range(4)]
    for k in range(4):
        for ax, v in order[k]["s"].items():
            m[k][AXES.index(ax)] += v
    return m


random.seed(11)
orders = {q["id"]: allowed_orders(q) for q in Q}
assign = [(q, random.choice(orders[q["id"]])) for q in Q]
mats = [_row(o) for _, o in assign]
tot = [[sum(mats[i][k][j] for i in range(len(Q))) for j in range(len(AXES))]
       for k in range(4)]
cost = sum(v * v for row in tot for v in row)

T0, STEPS = 6.0, 400000
for step in range(STEPS):
    T = T0 * (1.0 - step / STEPS) + 0.02
    i = random.randrange(len(Q))
    new_order = random.choice(orders[Q[i]["id"]])
    nm = _row(new_order)
    delta = 0.0
    for k in range(4):
        for j in range(len(AXES)):
            if nm[k][j] != mats[i][k][j]:
                old = tot[k][j]
                new = old - mats[i][k][j] + nm[k][j]
                delta += new * new - old * old
    if delta <= 0 or random.random() < math.exp(-delta / T):
        for k in range(4):
            for j in range(len(AXES)):
                tot[k][j] += nm[k][j] - mats[i][k][j]
        mats[i] = nm
        assign[i] = (Q[i], new_order)
        cost += delta

for q, order in assign:
    q["opts"] = order
pos_tot = tot

print("=== 位置偏置（一路选第 k 个选项，最终向量）===")
for k in range(4):
    txt = "  ".join(f"{AXES[j]}{pos_tot[k][j]:+.1f}"
                    for j in range(len(AXES)) if abs(pos_tot[k][j]) > 0.05)
    print(f"  第{k+1}个：" + (txt if txt else "全 0（无位置偏置）"))
worst = max(abs(v) for row in pos_tot for v in row)
print(f"  最大残留偏置：{worst:.2f}（每个轴总权重 5.60）")

# ================================================================ 自检
BANNED = ["牌", "卡牌", "万智", "指挥官", "扩画", "闪卡", "Magic", "地牌",
          "召唤", "法术", "生物", "传奇", "费用"]
errs: list[str] = []
collinear: list[str] = []
opposite: list[str] = []

print("=== 逐题 ===")
for q in Q:
    axes: dict[str, list[float]] = defaultdict(list)
    for o in q["opts"]:
        for k, v in o["s"].items():
            axes[k].append(v)
    if len(q["opts"]) != 4:
        errs.append(f"{q['id']} 选项数={len(q['opts'])}")
    if not 1 <= len(axes) <= 3:
        errs.append(f"{q['id']} 轴数={len(axes)}")
    for k, vs in axes.items():
        if k not in AXES:
            errs.append(f"{q['id']} 未知轴 {k}")
        if any(not (0.5 <= abs(v) <= 2.0) for v in vs):
            errs.append(f"{q['id']}.{k} 权重越界 {vs}")
        if not (any(v > 0 for v in vs) and any(v < 0 for v in vs)):
            errs.append(f"{q['id']}.{k} 没有正负两端（选项全指向同一方向）{vs}")
    # 同一题内选项的分数向量必须互不相同
    sigs = [tuple(sorted(o["s"].items())) for o in q["opts"]]
    if len(set(sigs)) != len(sigs):
        errs.append(f"{q['id']} 有重复的分数向量")
    # 选项集必须以 0 为中心：乱选不该系统性偏向任何一头
    for k, vs in axes.items():
        if abs(sum(vs) / len(vs)) > 1e-9:
            errs.append(f"{q['id']}.{k} 选项集不以 0 为中心（均值={sum(vs)/len(vs):.3f}）")
    # 提示（非错误）：纯强度梯度的共线选项对
    for i, a in enumerate(q["opts"]):
        for j, b in enumerate(q["opts"]):
            if i >= j:
                continue
            keys = sorted(set(a["s"]) | set(b["s"]))
            va = [a["s"].get(k, 0) for k in keys]
            vb = [b["s"].get(k, 0) for k in keys]
            nz = [(x, y) for x, y in zip(va, vb) if x != 0]
            if nz and all(y == 0 for x, y in zip(va, vb) if x == 0):
                ratios = [y / x for x, y in nz]
                if all(abs(r - ratios[0]) < 1e-9 for r in ratios):
                    if ratios[0] > 0:
                        collinear.append(f"{q['id']}选项{i+1}/{j+1}(同向·纯强度)")
                    else:
                        opposite.append(f"{q['id']}选项{i+1}/{j+1}")
    for txt in [q["q"]] + [o["t"] for o in q["opts"]]:
        for b in BANNED:
            if b in txt:
                errs.append(f"{q['id']} 出现禁用词「{b}」: {txt}")
    desc = "  ".join(f"{k}{'+' if max(v) > 0 else ''}" for k, v in
                     sorted(axes.items(), key=lambda kv: -max(map(abs, kv[1]))))
    print(f"{q['id']}  轴={list(axes)}  {q['q']}")

print("\n=== 轴权重覆盖 ===")
tot: dict[str, float] = defaultdict(float)
cnt: dict[str, int] = defaultdict(int)
for q in Q:
    axes: dict[str, list[float]] = defaultdict(list)
    for o in q["opts"]:
        for k, v in o["s"].items():
            axes[k].append(v)
    for k, vs in axes.items():
        tot[k] += sum(abs(v) for v in vs) / len(vs)   # 期望 |w|（选项等概率）
        cnt[k] += 1
print(f"{'轴':<12}{'题数':>5}{'总权重':>10}")
for k in AXES:
    print(f"{k:<12}{cnt[k]:>5}{tot[k]:>10.2f}")
vals = [tot[k] for k in AXES]
print(f"\n均衡性：min={min(vals):.2f}  max={max(vals):.2f}  "
      f"极差/均值={(max(vals)-min(vals))/ (sum(vals)/len(vals)) * 100:.1f}%")

# 平均每题轴数
slots = sum(len({k for o in q["opts"] for k in o["s"]}) for q in Q)
print(f"总轴槽位={slots}  平均每题 {slots/len(Q):.2f} 轴  题目数={len(Q)}")
print(f"同向共线（纯强度梯度）选项对：{len(collinear)} 处 → {collinear}")
print(f"完全反向（正好相反的两极）选项对：{len(opposite)} 处 → {opposite}")# 做题人若每题随机乱选，最终偏好向量的期望应当接近全 0
rand_mean = {k: 0.0 for k in AXES}
for q in Q:
    for o in q["opts"]:
        for k, v in o["s"].items():
            rand_mean[k] += v / len(q["opts"])
print("随机作答的期望向量：" + "  ".join(f"{k}={rand_mean[k]:+.2f}" for k in AXES))

if errs:
    print("\n!!! 自检失败 !!!")
    for e in errs:
        print("  -", e)
    raise SystemExit(1)
print("\n✓ 全部自检通过")

OUT = pathlib.Path(r"D:\万智\commander-art-quiz\data\questions.json")
# 本脚本只负责原有 20 题（a01~a20）。questions.json 里还可能有别的脚本追加的题
# （例如 scripts/add_form_questions.py 写的形态题 b01~b04）—— 一律原样保留，
# 否则重跑一次就把它们冲掉了。
old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"questions": []}
mine = {q["id"] for q in Q}
extra = [q for q in old.get("questions", []) if q["id"] not in mine]
if extra:
    print(f"· 保留 questions.json 里不由本脚本生成的 {len(extra)} 题："
          f"{[q['id'] for q in extra]}（形态题见 scripts/add_form_questions.py）")
    Q = Q + extra
OUT.write_text(json.dumps({"questions": Q}, ensure_ascii=False, indent=1),
               encoding="utf-8")
print(f"✓ 写出 {OUT}  ({OUT.stat().st_size} bytes, {len(Q)} 题)")
