#!/usr/bin/env python3
"""对比「我做的手机版」与「朋友改过、手机上能显示的版本」，找出差异。

两份都含大量 base64 图片，直接 diff 会被噪声淹没。
做法：先把 base64 长串替换成占位符，再逐行比。
"""
from __future__ import annotations

import difflib
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

MINE = pathlib.Path(r"D:/万智/commander-art-quiz/art_quiz_mobile.html")
THEIRS = pathlib.Path(
    r"C:/Users/q0112/.dsh/attachments/v1/files/d7/"
    r"d733409187d421cd56e5dcb3b6b0196d993e302639ebb55b3fd4d6c0a3b6f0b6/"
    r"art_quiz_mobile.html")

B64 = re.compile(r"data:image/jpeg;base64,[A-Za-z0-9+/=]{200,}")


def clean(p: pathlib.Path) -> list[str]:
    t = p.read_text(encoding="utf-8", errors="replace")
    t = B64.sub("data:image/jpeg;base64,<BASE64>", t)
    return t.split("\n")


def main() -> int:
    if not THEIRS.exists():
        print(f"✗ 找不到朋友的版本：{THEIRS}")
        return 1
    a, b = clean(MINE), clean(THEIRS)
    print(f"  我的版本   {len(a)} 行")
    print(f"  朋友的版本 {len(b)} 行\n")

    diff = list(difflib.unified_diff(a, b, "我的", "朋友的", lineterm="", n=1))
    if not diff:
        print("  两份完全相同（去掉图片数据后）")
        return 0

    # 统计
    adds = [l for l in diff if l.startswith("+") and not l.startswith("+++")]
    dels = [l for l in diff if l.startswith("-") and not l.startswith("---")]
    print(f"  差异：新增 {len(adds)} 行，删除 {len(dels)} 行\n")

    shown = 0
    for l in diff:
        if l.startswith(("+++", "---", "@@")):
            print(l)
        elif l.startswith(("+", "-")):
            print("  " + l[:220])
            shown += 1
        if shown > 90:
            print(f"  …（还有 {len(adds)+len(dels)-shown} 行未显示）")
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
