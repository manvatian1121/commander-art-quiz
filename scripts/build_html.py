# -*- coding: utf-8 -*-
"""把 questions.json + art_axes.json 内嵌进单文件 HTML。

可重复运行（幂等）：同样的输入永远产出逐字节相同的 art_quiz.html。

    python scripts/build_html.py

默认：
    输入  data/questions.json, data/art_axes.json, data/art_form.json
    模板  scripts/templates/art_quiz.template.html
    输出  art_quiz.html（项目根目录 —— 图片路径依赖这个位置）

之所以要内嵌而不是 fetch：用户会直接双击打开，file:// 协议下
fetch 本地 JSON 会被浏览器的同源策略拦掉，整个测试就白屏了。
图片走相对路径（data/cards/art_crop/xxx.jpg），因为 268 张图太大，
但 HTML 必须留在项目根目录，否则相对路径会断。

形态（form_*）轴由 scripts/add_form_axes.py 标定；本脚本只负责把
被标记 excluded 的图挡在 payload 之外 —— 结果页因此永远推荐不到它们。

2026-10-13：审美轴 10 → 9，`darkarea` 不再内嵌（它与 bright 实测 r = −0.830，
基本是同一根轴的负向，题库里已全部撤题）。`data/art_axes.json` 里那一列特征
原样保留，只是不进 payload；以后要重新启用，把它加回下面的审美轴列表即可。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PROJECT = Path(__file__).resolve().parent.parent
MARKER = "__PAYLOAD__"

# 9 个审美轴（darkarea 已下线）+ 7 个画面形态轴 + 9 个风格轴
LEGACY_AXES = ["warm", "bright", "vivid", "rich", "detailed",
               "contrasty", "modern", "borderless", "starart"]
FORM_AXES = ["form_纯人类", "form_人形异类", "form_凶猛巨兽",
             "form_扭曲异形", "form_可爱小兽", "form_机械构装", "form_写实动物"]
#   变异人形 → 人形异类；兽形三类＝可爱小兽 / 写实动物 / 凶猛巨兽（2026-10-13）
# 2026-10-13 新增：由 art_labels.json 的 mood 标签做的「画风轴」（多标签中心化）
STYLE_AXES = ["style_神秘", "style_史诗", "style_黑暗", "style_怪诞", "style_激烈",
              "style_温暖", "style_宁静", "style_可爱", "style_忧郁"]
AXES = LEGACY_AXES + FORM_AXES + STYLE_AXES
FORMS = [a.replace("form_", "") for a in FORM_AXES]
STYLES = [a.replace("style_", "") for a in STYLE_AXES]

# /result 会把这些键渲染出来，缺一个都算数据有问题
REQUIRED_ART_KEYS = ("art_id", "cmdr_en", "cmdr_zh", "artist", "set_name", "vec", "local_art_crop")


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def rel_prefix(out_path: Path, project: Path) -> str:
    """HTML 到项目根的相对前缀：HTML 在项目根就是 ''，在下级目录就是 '../'。"""
    rel = out_path.resolve().parent.relative_to(project.resolve())
    return "../" * len(rel.parts)


def build_payload(questions: dict, arts: list, form_of: dict, img_base: str) -> dict:
    qlist = questions["questions"]
    payload_q = []
    for q in qlist:
        multi = bool(q.get("multi"))
        opts = []
        for o in q["opts"]:
            s = {k: v for k, v in o["s"].items() if abs(v) > 1e-12}
            for k in s:
                if k not in AXES:
                    raise ValueError(f"题目 {q['id']} 出现未知轴：{k}")
            opts.append({"t": o["t"], "s": s})
        pq = {"id": q["id"], "q": q["q"], "opts": opts}
        if multi:
            pq["multi"] = True          # 前端据此渲染成可多选、可取消、带「下一题」
        payload_q.append(pq)

    payload_a = []
    for art in arts:
        if art.get("excluded"):
            continue                      # 被裁定剔除的图不进 payload
        vec = {}
        for a in AXES:
            if a not in art["vec"]:
                raise ValueError(f"{art['art_id']} 缺轴 {a}")
            vec[a] = round(float(art["vec"][a]), 6)
        payload_a.append({
            "art_id": art["art_id"],
            "cmdr_en": art["cmdr_en"],
            "cmdr_zh": art["cmdr_zh"],
            "artist": art["artist"],
            "set_name": art["set_name"],
            "released_at": art.get("released_at", ""),
            "face": art.get("face", 0),
            "form": form_of[art["art_id"]],   # 画面形态（6 类之一），冒烟测试用来核对 form_* 轴
            "vec": vec,
            # local_art_crop 是相对 data/ 的（"cards/art_crop/x.jpg"），这里补回
            # data/ 前缀，变成相对项目根的路径，前端再拼 HTML 自身的 img_base。
            "img": "data/" + art["local_art_crop"].replace("\\", "/").lstrip("/"),
        })
    return {"v": 1, "base": img_base, "axes": AXES, "forms": FORMS, "styles": STYLES,
            "q": payload_q, "a": payload_a}


def self_check(arts: list, payload: dict, project: Path, form_of: dict) -> list[str]:
    """返回问题清单（空列表 = 全通过）。"""
    problems: list[str] = []

    if len(payload["q"]) == 0:
        problems.append("题目为空")
    n_single = sum(1 for q in payload["q"] if not q.get("multi"))
    n_multi = sum(1 for q in payload["q"] if q.get("multi"))
    for q in payload["q"]:
        # 单选审美题一律 4 个选项（2×2 叉乘）；多选题选项数由题库自己定（b01 是 6 个）
        if not q.get("multi") and len(q["opts"]) != 4:
            problems.append(f"{q['id']} 的选项数不是 4（是 {len(q['opts'])}）")
        if q.get("multi") and len(q["opts"]) < 3:
            problems.append(f"{q['id']} 是多选题但只有 {len(q['opts'])} 个选项")
        for i, o in enumerate(q["opts"]):
            if not o["s"]:
                problems.append(f"{q['id']} 选项 {i} 没有任何轴权重")
            if not o["t"].strip():
                problems.append(f"{q['id']} 选项 {i} 文本为空")
        if q.get("multi"):
            # 多选题每个选项只挂自己那一类，重复挂同一轴会让「勾一次加两份」变味
            seen_axes: set[str] = set()
            for i, o in enumerate(q["opts"]):
                for k in o["s"]:
                    if k in seen_axes:
                        problems.append(f"{q['id']} 的 {k} 被重复挂在多个选项上")
                    seen_axes.add(k)

    missing_fields = [a["art_id"] for a in arts if not a.get("excluded")
                      and any(not str(a.get(k, "")).strip() for k in REQUIRED_ART_KEYS)]
    if missing_fields:
        problems.append(f"{len(missing_fields)} 张卡图缺字段：{missing_fields[:3]}")

    bad_form = [a["art_id"] for a in payload["a"] if a["form"] not in FORMS]
    if bad_form:
        problems.append(f"{len(bad_form)} 张卡图的形态不在 6 类里：{bad_form[:3]}")

    # 被剔除的图必须一张都不在 payload 里（结果页永远推荐不到）
    excluded = {a["art_id"] for a in arts if a.get("excluded")}
    leaked = excluded & {a["art_id"] for a in payload["a"]}
    if leaked:
        problems.append(f"被剔除的图漏进了 payload：{sorted(leaked)[:3]}")
    if excluded and len(excluded) != len(arts) - len(payload["a"]):
        problems.append("payload 少了图，但不是因为 excluded 标记，检查 art_axes.json")

    # 图片必须真实存在，否则几十张图永远加载不出来
    missing_img = []
    for a in payload["a"]:
        fp = project / a["img"]
        if not fp.is_file():
            missing_img.append(str(fp))
    if missing_img:
        problems.append(f"{len(missing_img)} 张插画文件不存在，例如 {missing_img[:2]}")

    cmdr = {a["cmdr_en"] for a in payload["a"]}
    if len(cmdr) < 3:
        problems.append(f"主将只有 {len(cmdr)} 位，凑不满 3 张不重复的推荐")

    # 每张图的 form_* 轴里，自己那一类必须最高（否则打分口径就反了）
    flipped = []
    for a in payload["a"]:
        vals = {f: a["vec"]["form_" + f] for f in FORMS}
        if max(vals, key=lambda f: vals[f]) != a["form"]:
            flipped.append(a["art_id"])
    if flipped:
        problems.append(f"{len(flipped)} 张图的 form_* 最高项不是自己的形态：{flipped[:3]}")

    # 多选题的每个选项必须恰好挂一个 form_* 轴，且与自己标的 form 一致
    for q in payload["q"]:
        if not q.get("multi"):
            continue
        for i, o in enumerate(q["opts"]):
            ks = [k for k in o["s"] if k.startswith("form_")]
            if len(ks) != 1:
                problems.append(f"{q['id']} 选项 {i} 挂了 {len(ks)} 个形态轴，应当 1 个")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成单文件美术审美测试 HTML")
    ap.add_argument("--questions", default=str(PROJECT / "data" / "questions.json"))
    ap.add_argument("--arts", default=str(PROJECT / "data" / "art_axes.json"))
    ap.add_argument("--forms", default=str(PROJECT / "data" / "art_form.json"))
    ap.add_argument("--template", default=str(PROJECT / "scripts" / "templates" / "art_quiz.template.html"))
    ap.add_argument("--out", default=str(PROJECT / "art_quiz.html"))
    args = ap.parse_args(argv)

    questions = load_json(Path(args.questions))
    arts = load_json(Path(args.arts))
    form_rows = load_json(Path(args.forms))
    template = Path(args.template).read_text(encoding="utf-8")

    form_of = {r["art_id"]: r["form"] for r in form_rows if not r.get("excluded")}
    missing_form = [a["art_id"] for a in arts
                    if not a.get("excluded") and a["art_id"] not in form_of]
    if missing_form:
        print(f"✗ {len(missing_form)} 张图没有形态分类：{missing_form[:3]}", file=sys.stderr)
        return 1

    if template.count(MARKER) != 1:
        print(f"✗ 模板里 {MARKER} 出现 {template.count(MARKER)} 次，应当恰好 1 次", file=sys.stderr)
        return 1

    out_path = Path(args.out)
    img_base = rel_prefix(out_path, PROJECT)
    payload = build_payload(questions, arts, form_of, img_base)

    problems = self_check(arts, payload, PROJECT, form_of)
    if problems:
        print("✗ 数据自检未通过：", file=sys.stderr)
        for p in problems:
            print("   - " + p, file=sys.stderr)
        return 1

    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # 防止样本里出现 "</script" 之类把内嵌 JSON 提前截断
    blob = blob.replace("</", "<\\/")

    html = template.replace(MARKER, blob)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8", newline="\n")

    size = out_path.stat().st_size
    n_single = sum(1 for q in payload["q"] if not q.get("multi"))
    n_multi = sum(1 for q in payload["q"] if q.get("multi"))
    print("✓ 已生成", out_path)
    print(f"  体积      {size:,} 字节（{size / 1024:.1f} KB）")
    print(f"  题目      {len(payload['q'])} 题（{n_single} 单选 + {n_multi} 多选）；"
          f"{n_single} 题 × 4 选项"
          + ("；多选题选项数：" + "、".join(
              f"{q['id']} {len(q['opts'])} 个" for q in payload['q'] if q.get('multi')) if n_multi else ""))
    print(f"  插画      {len(payload['a'])} 张 / {len({a['cmdr_en'] for a in payload['a']})} 位主将"
          f"（另有 {len(arts) - len(payload['a'])} 张被裁定剔除）")
    print(f"  轴        {len(AXES)} 个（9 图像/元数据 + 7 画面形态 + 9 风格；darkarea 已下线）")
    print(f"  图片前缀  {img_base or '(同目录)'}")
    print(f"  内嵌数据  {len(blob.encode('utf-8')):,} 字节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
