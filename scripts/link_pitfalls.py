#!/usr/bin/env python3
"""把 PITFALLS.md 加进 README 的导航，然后提交推送。

教训文档单独放一个文件，README 里只留一行链接 ——
README 是给「想玩/想重建」的人看的，教训是给「想改代码」的人看的，受众不同。
"""
from __future__ import annotations

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:/万智/commander-art-quiz")
README = ROOT / "README.md"

LINE = (
    "\n## 改动前请先读\n\n"
    "`PITFALLS.md` 记录了本项目踩过的坑——尤其是几处**症状会误导排查方向**的问题"
    "（最典型的一个：手机上卡片整块空白，看着像图片加载失败，实际是移动端 flex 高度塌陷）。\n"
    "改前端、改数据格式、加维度或加类别之前，建议先扫一遍。\n"
)


def main() -> int:
    t = README.read_text(encoding="utf-8")
    if "PITFALLS.md" in t:
        print("  · README 里已经有链接")
        return 0
    anchor = "## 目录"
    if anchor in t:
        t = t.replace(anchor, LINE.strip() + "\n\n" + anchor, 1)
    else:
        t = t.rstrip() + "\n" + LINE
    README.write_text(t, encoding="utf-8")
    print("  ✓ README 已加 PITFALLS.md 导航")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
