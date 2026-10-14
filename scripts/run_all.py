# -*- coding: utf-8 -*-
"""一键跑完整条流水线（Windows 上不能用 .sh，所以用 .py 串）。

    python scripts/run_all.py            # 全跑（含 build_standalone，约 10 秒）
    python scripts/run_all.py --fast     # 跳过 build_standalone（省 8 秒）

顺序（改上游的脚本时请照着这个顺序想依赖）：
    ① sync_excluded_from_form   形态表的 excluded → art_axes
    ② add_form_axes             7 条 form_*（依赖 art_form / art_axes）
    ③ add_style_axes            9 条 style_*（依赖 art_labels_v2 / art_axes）
    ④ extend_form_options_7     三道形态题的 7 个选项与顺序（会把权重重置为占位 1.0）
    ⑤ add_style_questions       s01~s09 写进题库（幂等）
    ⑥ solve_form_weights        闭式解权重写回题库（必须在 ④ 之后）
    ⑦ build_html                payload 自检 → art_quiz.html
    ⑧ build_standalone          → art_quiz_standalone.html
    ⑨ 三件套校验：smoke_test.mjs / audit_questions.py / audit_repeats.py / verify_questions.mjs
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
PY, NODE = sys.executable, "node"

STEPS = [
    ("sync_excluded_from_form", [PY, "scripts/sync_excluded_from_form.py"], False),
    ("add_form_axes",           [PY, "scripts/add_form_axes.py"],           False),
    ("add_style_axes",          [PY, "scripts/add_style_axes.py"],          False),
    ("extend_form_options_7",   [PY, "scripts/extend_form_options_7.py"],   False),
    ("add_style_questions",     [PY, "scripts/add_style_questions.py"],     False),
    ("solve_form_weights",      [PY, "scripts/solve_form_weights.py"],      False),
    ("build_html",              [PY, "scripts/build_html.py"],              False),
    ("build_standalone",        [PY, "scripts/build_standalone.py"],        True),
    ("smoke_test",              [NODE, "scripts/smoke_test.mjs"],           False),
    ("audit_questions",         [PY, "scripts/audit_questions.py"],         False),
    ("audit_repeats",           [PY, "scripts/audit_repeats.py"],           False),
    ("verify_questions",        [NODE, "scripts/verify_questions.mjs"],     False),
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="跳过 build_standalone")
    args = ap.parse_args(argv)
    failed = []
    for name, cmd, slow in STEPS:
        if slow and args.fast:
            print(f"\n=== 跳过 {name}（--fast）===")
            continue
        print(f"\n{'=' * 78}\n=== {name}：{' '.join(cmd[1:])}\n{'=' * 78}")
        r = subprocess.run(cmd, cwd=ROOT)
        if r.returncode != 0:
            failed.append(name)
            print(f"✗ {name} 退出码 {r.returncode}")
    print("\n" + "=" * 78)
    if failed:
        print("✗ 流水线有失败步骤：" + "、".join(failed))
        return 1
    print("✓ 流水线全部跑通（12 步里跑了 "
          + str(len(STEPS) - (1 if args.fast else 0)) + " 步，全绿）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
