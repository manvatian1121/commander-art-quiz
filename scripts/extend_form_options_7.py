# -*- coding: utf-8 -*-
"""形态类从 6 类扩到 7 类（新增「写实动物」）后，把三道形态多选题补上第 7 个选项。

    python scripts/extend_form_options_7.py --check
    python scripts/extend_form_options_7.py

背景（本轮发现的不一致）：
  `art_form.json` 已经把兽形拆成三类 —— 可爱小兽（卡通 Q 版）/ 写实动物（写实画法）/
  凶猛巨兽（体型庞大、凶相）。但 b01/b02/b03 三道形态题仍然只有 6 个选项，**「写实动物」
  这一类既拿不到权重、也没法被用户勾中**；同时 build_html.py 的「自己那一类必须是
  form_* 最高项」自检和 solve_form_weights.py 的池子都会对不上。

做法：保持原来「一个选项 = 一类、每个选项只挂自己那一类 form_*」的结构，
在每道题里补一个「写实动物」选项，选项顺序仍按 0/1/3 左旋（7 元循环），
使六…七类都能进「前 4 位」、且没有任何一类垄断某个位置。
权重先占位，随后由 solve_form_weights.py 按闭式解 w = α/k 写回。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
QJSON = ROOT / "data" / "questions.json"

BASE = ["纯人类", "人形异类", "凶猛巨兽", "扭曲异形", "可爱小兽", "机械构装", "写实动物"]
TEXT = {
    "b01": {
        "纯人类": "一个普普通通的人", "人形异类": "类人形的奇异生物", "凶猛巨兽": "一头凶猛的巨兽",
        "扭曲异形": "说不清形状的扭曲造物", "可爱小兽": "一只毛茸茸的小家伙",
        "机械构装": "一台钢铁造物", "写实动物": "一只真实的猫或狗",
    },
    "b02": {
        "人形异类": "半人半怪的奇异存在", "凶猛巨兽": "一头横行的巨兽",
        "扭曲异形": "一坨说不清形状的东西", "可爱小兽": "一只软乎乎的小兽",
        "机械构装": "一副会走的钢铁躯壳", "写实动物": "一只寻常的动物", "纯人类": "就是个普通人",
    },
    "b03": {
        "扭曲异形": "一团认不出原形的东西", "可爱小兽": "一只看着无害的小家伙",
        "机械构装": "一台冰冷的机器", "写实动物": "一只真实的动物",
        "纯人类": "一个和你一样的人", "人形异类": "一个类人形的怪物", "凶猛巨兽": "一头巨兽",
    },
}
ROT = {"b01": 0, "b02": 1, "b03": 3}          # 左旋位数，与旧版一致


def order_of(qid: str) -> list[str]:
    k = ROT[qid] % len(BASE)
    return BASE[k:] + BASE[:k]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    data = json.loads(QJSON.read_text(encoding="utf-8"))
    qs = data["questions"]
    mqs = [q for q in qs if q.get("multi")]
    print(f"形态多选题 {len(mqs)} 道：" + "、".join(q["id"] for q in mqs))
    changed = 0
    for q in mqs:
        if q["id"] not in TEXT:
            print(f"✗ 不认识的形态题 {q['id']}", file=sys.stderr)
            return 1
        order = order_of(q["id"])
        old = [o.get("form") for o in q["opts"]]
        q["opts"] = [{"t": TEXT[q["id"]][f], "form": f, "s": {"form_" + f: 1.0}} for f in order]
        if old != order:
            changed += 1
        print(f"  {q['id']}  左旋{ROT[q['id']]}  " + " / ".join(order))
        print("        文案：" + " ｜ ".join(f"{f}={TEXT[q['id']][f]}" for f in order))
    # 结构自检：两两不同 / 前 4 位覆盖 7 类 / 逐位置不重类
    keys = ["/".join(o["form"] for o in q["opts"]) for q in mqs]
    cover: dict[str, int] = {}
    for q in mqs:
        for o in q["opts"][:4]:
            cover[o["form"]] = cover.get(o["form"], 0) + 1
    miss = [f for f in BASE if not cover.get(f)]
    print(f"\n三道题流程两两不同：{'✓' if len(set(keys)) == len(keys) else '✗'}")
    print("「前 4 位」覆盖：" + "  ".join(f"{f}×{cover.get(f, 0)}" for f in BASE))
    print(f"七类都能被「只勾前四项」的人扫到：{'✓' if not miss else '✗ ' + '、'.join(miss)}")
    for pos in range(4):
        col = [q["opts"][pos]["form"] for q in mqs]
        print(f"  第{pos + 1}位：{' / '.join(col)}"
              f"  {'✓' if len(set(col)) == len(col) else '✗ 同一类占多次'}")
    lens = [(len([c for c in o["t"] if "\u4e00" <= c <= "\u9fff"]), q["id"], o["t"])
            for q in mqs for o in q["opts"]]
    print(f"选项汉字数：最长 {max(lens)[0]} 字（{max(lens)[1]}「{max(lens)[2]}」），"
          f"平均 {sum(x[0] for x in lens) / len(lens):.1f}")
    if args.check:
        print("--check：没有写文件")
        return 0
    QJSON.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"✓ 已写回 {QJSON}（改动 {changed} 道；权重占位 1.0，随后由 solve_form_weights.py 覆写）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
