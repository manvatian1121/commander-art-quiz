#!/usr/bin/env python3
"""下载主将卡图。

每张独立美术 × 2 个尺寸 = 546 个文件。
  normal (488×680) —— 网页展示用
  large  (672×936) —— 大图 / 视频素材用

落盘结构：
  data/cards/normal/<art_id>.jpg
  data/cards/large/<art_id>.jpg

文件名只用 art_id：不含空格与中文，跨平台安全；对应关系查 art_manifest.json。

带断点续传：已存在且体积大于 1KB 的文件直接跳过，中断后重跑即可。
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"
MANIFEST = DATA / "art_manifest.json"

UA = {"User-Agent": "commander-art-quiz/0.1 (personal fan project)"}
SIZES = ("normal", "large")


def fetch(url: str, dest: pathlib.Path, retries: int = 3) -> bool:
    if dest.exists() and dest.stat().st_size > 1024:
        return True                                   # 已有，跳过
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                blob = r.read()
            if len(blob) < 1024:
                time.sleep(1.0)
                continue
            dest.write_bytes(blob)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            time.sleep(1.5 * (a + 1))
        except Exception:  # noqa: BLE001
            time.sleep(1.5 * (a + 1))
    return False


def main() -> int:
    items = json.loads(MANIFEST.read_text(encoding="utf-8"))
    print(f"待下载 {len(items)} 张 × {len(SIZES)} 个尺寸 = {len(items)*len(SIZES)} 个文件\n")

    ok = fail = 0
    bytes_total = 0
    for name in SIZES:
        (DATA / "cards" / name).mkdir(parents=True, exist_ok=True)

    for i, it in enumerate(items, 1):
        aid = it["art_id"]
        for name in SIZES:
            url = it.get(f"image_{name}")
            dest = DATA / "cards" / name / f"{aid}.jpg"
            if not url:
                fail += 1
                continue
            before = dest.stat().st_size if dest.exists() else 0
            if fetch(url, dest):
                now = dest.stat().st_size
                bytes_total += max(0, now - before)
                it[f"local_{name}"] = f"cards/{name}/{aid}.jpg"
                ok += 1
            else:
                fail += 1
                print(f"  ✗ 失败 {aid} ({name})  {it['cmdr_zh']}", flush=True)
            time.sleep(0.08)
        if i % 25 == 0 or i == len(items):
            print(f"  …{i}/{len(items)}　成功 {ok}　失败 {fail}　"
                  f"已下 {bytes_total/1024/1024:.1f} MB", flush=True)

    MANIFEST.write_text(json.dumps(items, ensure_ascii=False, indent=1),
                        encoding="utf-8")

    for name in SIZES:
        d = DATA / "cards" / name
        files = list(d.glob("*.jpg"))
        total = sum(f.stat().st_size for f in files)
        print(f"\n  cards/{name}/　{len(files)} 个文件　{total/1024/1024:.1f} MB")

    print(f"\n=== 汇总 ===")
    print(f"  成功 {ok}　失败 {fail}")
    print(f"  本次新增 {bytes_total/1024/1024:.1f} MB")
    if fail:
        print("  ⚠ 有失败项，重跑本脚本会只补缺的")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
