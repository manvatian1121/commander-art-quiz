# -*- coding: utf-8 -*-
"""复核用联系表：原图尺寸(626x457) 3x3，按给定 n 列表拼页。
用法：python scripts/_style_review_sheets.py 9 17 30 32 ...
输出 data/sheets_style/rev_XX.jpg + 打印每页 n 布局。
"""
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "sheets_style")
form = {r["n"]: r for r in json.load(open(os.path.join(DATA, "art_form.json"), encoding="utf-8"))}

ns = [int(a) for a in sys.argv[1:]]
if not ns:
    print("need n list"); sys.exit(1)

CW, CH, LAB, PAD, COLS = 626, 457, 60, 10, 3
PER = 9
F_BIG = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 52)
sheet_w = PAD + COLS * (CW + PAD)
sheet_h = PAD + 3 * (CH + LAB + PAD)

for p in range((len(ns) + PER - 1) // PER):
    chunk = ns[p * PER:(p + 1) * PER]
    sh = Image.new("RGB", (sheet_w, sheet_h), (16, 16, 18))
    d = ImageDraw.Draw(sh)
    for i, n in enumerate(chunk):
        r, c = divmod(i, COLS)
        x0 = PAD + c * (CW + PAD)
        y0 = PAD + r * (CH + LAB + PAD)
        src = os.path.join(DATA, "cards", "art_crop", form[n]["art_id"] + ".jpg")
        sh.paste(Image.open(src).convert("RGB"), (x0, y0))
        d.rectangle([x0, y0 + CH, x0 + CW - 1, y0 + CH + LAB - 1], fill=(8, 8, 10))
        d.text((x0 + 12, y0 + CH + 4), str(n), font=F_BIG, fill=(255, 235, 90))
    name = "rev_%02d.jpg" % (p + 1)
    sh.save(os.path.join(OUT, name), quality=90)
    print(name, chunk)
