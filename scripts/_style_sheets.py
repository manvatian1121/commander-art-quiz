# -*- coding: utf-8 -*-
"""拼画法标注用的联系表：3x3，每格 >=340px 图，编号用 art_form.json 的 n。

输出 data/sheets_style/style_XX.jpg 与 data/_style_sheets_index.json
严格按 n 升序排列（不按 art_id / 文件名排序）。
"""
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "sheets_style")
os.makedirs(OUT, exist_ok=True)

CELL_W = 340                      # 每格图宽
CROP_W, CROP_H = 626, 457         # 原图尺寸
CELL_H = round(CELL_W * CROP_H / CROP_W)   # 248
LABEL_H = 44
PAD = 8
COLS = ROWS = 3
PER = COLS * ROWS

form = json.load(open(os.path.join(DATA, "art_form.json"), encoding="utf-8"))
items = [r for r in form if not r.get("excluded")]
items.sort(key=lambda r: r["n"])          # <-- 按 n 排序，关键
assert len(items) == 370, len(items)

font_path = r"C:\Windows\Fonts\arialbd.ttf"
def font(sz):
    try:
        return ImageFont.truetype(font_path, sz)
    except Exception:
        return ImageFont.load_default()

F_SMALL = font(26)   # 角标
F_BIG = font(40)     # 底部编号

cell_w_tot = CELL_W + PAD
cell_h_tot = CELL_H + PAD + LABEL_H
sheet_w = PAD + COLS * cell_w_tot
sheet_h = PAD + ROWS * cell_h_tot

index = []
pages = (len(items) + PER - 1) // PER
for p in range(pages):
    chunk = items[p * PER:(p + 1) * PER]
    sheet = Image.new("RGB", (sheet_w, sheet_h), (16, 16, 18))
    d = ImageDraw.Draw(sheet)
    for i, rec in enumerate(chunk):
        r, c = divmod(i, COLS)
        x0 = PAD + c * cell_w_tot
        y0 = PAD + r * cell_h_tot
        src = os.path.join(DATA, "cards", "art_crop", rec["art_id"] + ".jpg")
        try:
            im = Image.open(src).convert("RGB").resize((CELL_W, CELL_H), Image.LANCZOS)
        except Exception as e:
            im = Image.new("RGB", (CELL_W, CELL_H), (120, 0, 0))
            print("MISS", rec["n"], e)
        sheet.paste(im, (x0, y0))
        d.rectangle([x0, y0, x0 + CELL_W - 1, y0 + CELL_H - 1], outline=(90, 90, 95), width=1)
        # 底部编号条
        ly0 = y0 + CELL_H
        d.rectangle([x0, ly0, x0 + CELL_W - 1, ly0 + LABEL_H - 1], fill=(8, 8, 10))
        txt = str(rec["n"])
        bb = d.textbbox((0, 0), txt, font=F_BIG)
        d.text((x0 + 10, ly0 + (LABEL_H - (bb[3] - bb[1])) / 2 - bb[1]), txt,
               font=F_BIG, fill=(255, 255, 255))
        # 右上角小号角标（双保险）
        bb2 = d.textbbox((0, 0), txt, font=F_SMALL)
        sx = x0 + CELL_W - 8 - (bb2[2] - bb2[0])
        sy = y0 + 6
        d.rectangle([sx - 6, sy - 2, sx + (bb2[2] - bb2[0]) + 6, sy + (bb2[3] - bb2[1]) + 4],
                    fill=(0, 0, 0))
        d.text((sx, sy), txt, font=F_SMALL, fill=(255, 230, 80))
    name = "style_%02d.jpg" % (p + 1)
    sheet.save(os.path.join(OUT, name), quality=88)
    index.append({"sheet": name, "ns": [r["n"] for r in chunk]})

json.dump(index, open(os.path.join(DATA, "_style_sheets_index.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# 自检：n 无缺无重
allns = [n for e in index for n in e["ns"]]
assert allns == sorted(allns), "顺序不对"
assert len(allns) == len(set(allns)) == 370, (len(allns), len(set(allns)))
print("pages", pages, "cells", len(allns), "sheet", sheet_w, "x", sheet_h, "cell", CELL_W, "x", CELL_H)
