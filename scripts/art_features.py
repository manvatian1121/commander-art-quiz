#!/usr/bin/env python3
"""下载 art_crop（纯插画版）+ 算每张图的审美特征。

为什么先下载 art_crop：
  牌框是固定尺寸的装饰，会在特征里加一层恒定偏置。
  用「去掉牌框的纯插画」算出来的亮度/饱和度/细节才是画本身的。

审美特征全部**从像素算出来**，不靠人工打标签：
  brightness  明暗
  contrast    对比强弱
  saturation  鲜艳程度
  warmth      冷暖（色相映射）
  variety     色彩丰富度（色相熵）
  detail      细节密度（梯度幅值均值）
  dark/bright 暗部 / 亮部占比
这个口径可复现、可解释，也不会有「我觉得这张很燃」这种主观噪声。
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
import time
import urllib.request

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"
MANIFEST = DATA / "art_manifest.json"
CROP_DIR = DATA / "cards" / "art_crop"
UA = {"User-Agent": "commander-art-quiz/0.1 (personal fan project)"}


def fetch(url: str, dest: pathlib.Path, retries: int = 3) -> bool:
    if dest.exists() and dest.stat().st_size > 1024:
        return True
    for a in range(retries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=60) as r:
                blob = r.read()
            if len(blob) < 1024:
                time.sleep(1.0)
                continue
            dest.write_bytes(blob)
            return True
        except Exception:  # noqa: BLE001
            time.sleep(1.5 * (a + 1))
    return False


def features(path: pathlib.Path) -> dict | None:
    try:
        im = Image.open(path).convert("RGB")
    except Exception:  # noqa: BLE001
        return None
    im.thumbnail((320, 320), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    mx, mn = a.max(axis=2), a.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)

    # 色相 → 冷暖：暖色（红黄橙）为正，冷色（蓝青）为负，绿紫接近 0
    hsv = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).convert("HSV"))
    hue = hsv[..., 0].astype(np.float32) / 255.0 * 360.0
    warmth_map = np.cos(np.deg2rad(hue - 40.0))     # 40° 附近（橙）最暖
    warmth = float((warmth_map * sat).sum() / max(sat.sum(), 1e-6))

    # 色彩丰富度：色相加权直方图的熵（按饱和度加权，灰的不算数）
    hist, _ = np.histogram(hue, bins=24, range=(0, 360), weights=sat)
    p = hist / max(hist.sum(), 1e-6)
    p = p[p > 0]
    variety = float(-(p * np.log(p)).sum() / math.log(24))

    # 细节密度：Sobel 近似（中心差分）
    gy = np.abs(np.diff(lum, axis=0)).mean()
    gx = np.abs(np.diff(lum, axis=1)).mean()
    detail = float((gx + gy) / 2)

    return {
        "brightness": round(float(lum.mean()), 4),
        "contrast": round(float(lum.std()), 4),
        "saturation": round(float(sat.mean()), 4),
        "warmth": round(warmth, 4),
        "variety": round(variety, 4),
        "detail": round(detail, 4),
        "dark_ratio": round(float((lum < 0.20).mean()), 4),
        "bright_ratio": round(float((lum > 0.80).mean()), 4),
    }


def main() -> int:
    items = json.loads(MANIFEST.read_text(encoding="utf-8"))
    CROP_DIR.mkdir(parents=True, exist_ok=True)

    got = 0
    for i, it in enumerate(items, 1):
        url = it.get("image_art_crop")
        dest = CROP_DIR / f"{it['art_id']}.jpg"
        if url and fetch(url, dest):
            it["local_art_crop"] = f"cards/art_crop/{it['art_id']}.jpg"
            got += 1
        time.sleep(0.07)
        if i % 50 == 0 or i == len(items):
            print(f"  …下载 {i}/{len(items)}", flush=True)

    size = sum(f.stat().st_size for f in CROP_DIR.glob("*.jpg")) / 1024 / 1024
    print(f"\n  cards/art_crop/　{len(list(CROP_DIR.glob('*.jpg')))} 个　{size:.1f} MB")

    print("\n=== 算审美特征 ===")
    done = 0
    for i, it in enumerate(items, 1):
        p = CROP_DIR / f"{it['art_id']}.jpg"
        f = features(p) if p.is_file() else None
        if f:
            it["art"] = f
            done += 1
        if i % 50 == 0 or i == len(items):
            print(f"  …{i}/{len(items)}", flush=True)
    print(f"  算出 {done}/{len(items)} 张")

    MANIFEST.write_text(json.dumps(items, ensure_ascii=False, indent=1),
                        encoding="utf-8")

    # 分布报告，看这些特征有没有区分度
    print("\n=== 各特征的分布（区分度够不够）===")
    print(f"  {'特征':<12} {'最小':>7} {'25%':>7} {'中位':>7} {'75%':>7} {'最大':>7}")
    for k in ("brightness", "contrast", "saturation", "warmth",
              "variety", "detail", "dark_ratio"):
        v = np.array([it["art"][k] for it in items if "art" in it])
        q = np.percentile(v, [0, 25, 50, 75, 100])
        print(f"  {k:<12} " + " ".join(f"{x:>7.3f}" for x in q))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
