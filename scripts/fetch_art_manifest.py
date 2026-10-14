#!/usr/bin/env python3
"""主将卡图小测试 —— 数据采集（第二版）。

口径：
  · 只要主将本人的印刷版
  · 按 illustration_id 去重：同一张画在普通/扩画/重印里只算一张
  · **双面牌的正面和背面各算一张独立美术**（背面是独立的画）
  · 保留 Judge 赠卡、售前赛卡、Secret Lair（画是独立的）
  · 排除电子版独占、衍生物、画集卡

第一版踩了三个坑，都修了：
  ① 名字带引号（Henzie "Toolbox" Torre）破坏 !"..." 语法 → 改用 name: 字段匹配
  ② 双面牌只取了正面（card_faces[0]）→ 现在两个面各出一条
  ③ 拍档组合名不是单张牌 → 先试整名，404 再分别查两半

坑的特点：三个都是**静默失败**——有输出、不报错、只是少了东西。
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "data"
OUT.mkdir(parents=True, exist_ok=True)
PREV = pathlib.Path(r"D:/万智/commander-quiz/data/commanders.json")

UA = {"User-Agent": "commander-art-quiz/0.1 (personal fan project)",
      "Accept": "application/json"}


def sf(url: str, retries: int = 3):
    for a in range(retries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=45) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(1.5 * (a + 1))
        except Exception:  # noqa: BLE001
            time.sleep(1.5 * (a + 1))
    return None


def query(name: str) -> list[dict]:
    """按名字查所有纸质印刷版。名字带引号时改用 name: 字段匹配。"""
    # 名字里的引号会破坏 !"..." 精确匹配语法（实测 name:"转义" 也不行）。
    # 最稳的办法是把引号整个去掉——实测 !"Henzie Toolbox Torre" 能正确命中。
    clean = name.replace('"', '').strip()
    q = f'!"{clean}"'
    q += " game:paper -is:token -is:artseries"
    url = ("https://api.scryfall.com/cards/search?unique=prints&order=released&q="
           + urllib.parse.quote(q))
    out: list[dict] = []
    while url:
        d = sf(url)
        if not d or "data" not in d:
            break
        out.extend(d["data"])
        url = d.get("next_page") if d.get("has_more") else None
        time.sleep(0.12)
    return out


def printings(name: str) -> list[dict]:
    """先试整个名字（双面牌会命中），404 说明是拍档组合，再分别查两半。"""
    got = query(name)
    if got:
        return got
    if " // " in name:
        merged, seen = [], set()
        for half in name.split(" // "):
            for p in query(half.strip()):
                if p.get("id") not in seen:
                    seen.add(p.get("id"))
                    merged.append(p)
        return merged
    return []


def main() -> int:
    pool = json.loads(PREV.read_text(encoding="utf-8"))["commanders"]
    top = sorted([c for c in pool if isinstance(c.get("all_time_rank"), int)],
                 key=lambda c: c["all_time_rank"])[:100]

    manifest, seen_art = [], set()
    printed = 0
    face_splits = 0
    for i, c in enumerate(top, 1):
        prints = printings(c["en"])
        printed += len(prints)
        best: dict[str, dict] = {}
        for p in prints:
            faces = p.get("card_faces") or []
            items = []
            if faces and any(f.get("image_uris") for f in faces):
                for fi, f in enumerate(faces):
                    if f.get("illustration_id") and f.get("image_uris"):
                        items.append((f["illustration_id"], f["image_uris"],
                                      fi, f.get("name") or p.get("name")))
                if len(items) > 1:
                    face_splits += 1
            if not items and p.get("illustration_id") and p.get("image_uris"):
                items.append((p["illustration_id"], p["image_uris"], 0,
                              p.get("name")))
            for iid, imgs, fi, fname in items:
                if iid in best or iid in seen_art:
                    continue
                best[iid] = {"imgs": imgs, "card": p, "face": fi, "fname": fname}

        for iid, rec in best.items():
            seen_art.add(iid)
            p, imgs = rec["card"], rec["imgs"]
            manifest.append({
                "cmdr_en": c["en"], "cmdr_zh": c["zh"],
                "cmdr_rank": c["all_time_rank"], "cmdr_colors": c["colors"],
                "art_id": iid, "face": rec["face"], "face_name": rec["fname"],
                "artist": p.get("artist"),
                "set": p.get("set"), "set_name": p.get("set_name"),
                "collector_number": p.get("collector_number"),
                "released_at": p.get("released_at"),
                "border_color": p.get("border_color"),
                "frame_effects": p.get("frame_effects") or [],
                "promo": bool(p.get("promo")),
                "promo_types": p.get("promo_types") or [],
                "full_art": bool(p.get("full_art")),
                "image_small": imgs.get("small"),
                "image_normal": imgs.get("normal"),
                "image_large": imgs.get("large"),
                "image_art_crop": imgs.get("art_crop"),
            })
        if i % 10 == 0 or i == len(top):
            print(f"  …已处理 {i}/{len(top)}，累计 {len(manifest)} 张", flush=True)
        time.sleep(0.12)

    (OUT / "art_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    per = defaultdict(int)
    for m in manifest:
        per[m["cmdr_en"]] += 1
    counts = sorted(per.values())
    print("\n=== 汇总 ===")
    print(f"  主将           100 位")
    print(f"  印刷版总计     {printed} 张")
    print(f"  独立美术       {len(manifest)} 张")
    print(f"  双面牌拆出     {face_splits} 张印刷版各出 2 面")
    print(f"  促销版         {sum(1 for m in manifest if m['promo'])} 张")
    print(f"  每位主将美术数：最少 {counts[0]}　中位 {counts[len(counts)//2]}　最多 {counts[-1]}")
    print(f"  缺图的主将     {sum(1 for c in top if per[c['en']] == 0)} 位")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
