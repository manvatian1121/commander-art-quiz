# -*- coding: utf-8 -*-
"""把 data/art_form.json 的 excluded 标记同步到 data/art_axes.json。

    python scripts/sync_excluded_from_form.py [--check]

add_form_axes.py 会自己写这两个标记，但它在动手前会先比对两者是否一致，
不一致就直接报错退出（保护性设计）。本脚本只做「先把标记对齐」这一步，
好让 add_form_axes.py 能正常往下跑。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
FORM = ROOT / "data" / "art_form.json"
AXES = ROOT / "data" / "art_axes.json"
BACKUP = ROOT / "backups"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    forms = json.loads(FORM.read_text(encoding="utf-8"))
    axes = json.loads(AXES.read_text(encoding="utf-8"))
    want = {r["art_id"] for r in forms if r.get("excluded")}
    have = {a["art_id"] for a in axes if a.get("excluded")}
    print(f"art_form 要剔除 {len(want)} 张；art_axes 现在标了 {len(have)} 张")
    print(f"  需补标：{sorted(want - have)}")
    print(f"  需清掉：{sorted(have - want)}")
    changed = 0
    for a in axes:
        if a["art_id"] in want:
            if not a.get("excluded"):
                a["excluded"] = True
                changed += 1
        elif a.get("excluded"):
            del a["excluded"]
            changed += 1
    if args.check:
        print(f"--check：会改 {changed} 行，没有写文件")
        return 0
    BACKUP.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(AXES, BACKUP / f"art_axes.json.{stamp}.pre-exclsync.bak")
    AXES.write_text(json.dumps(axes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ 已写回 {AXES}（改 {changed} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
