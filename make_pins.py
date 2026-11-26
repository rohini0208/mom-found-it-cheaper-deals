"""Pinterest pins (1000x1500, 2:3) from the verified site, one per price tier plus one per Top-5 product.
Brand tokens from brand.py; photo + big tier text + Mia sticker; link = the tier section on the site.
Output: pins/<date>/pin_<name>.png + pins/<date>/pins.csv (title, description, link, image) for bulk upload.
No Amazon prices or ratings on pins (AMAZON_PRICES=hide). Run after build_site.py:  python make_pins.py
"""
import csv
import html as html_
import json
import os
import re
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

import brand as B

ROOT = Path(__file__).parent
SITE_HTML = ROOT / "site" / "index.html"
SITE = "https://momfounditcheaper.com/"
W, H = 1000, 1500
OUT = ROOT / "pins" / date.today().isoformat()


def font(path, size, var=None):
    f = ImageFont.truetype(str(ROOT / path), size)
    if var:
        try:
            f.set_variation_by_name(var)
        except Exception:
            pass
    return f


def sticker(img, xy, text, size=30, rot=-6, pad=22):
    f = font(B.FONT_TEXT, size, "Black")
    d = ImageDraw.Draw(img)
    tw = d.textlength(text, font=f)
    w, h = int(tw + 2 * pad), int(size * 1.6)
    s = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    sd = ImageDraw.Draw(s)
    sd.rounded_rectangle([20, 20, 20 + w, 20 + h], radius=h // 2, fill=B.YELLOW + (255,), outline=(255, 255, 255, 255), width=4)
    sd.text((20 + pad, 20 + (h - size) // 2 - 3), text, font=f, fill=B.INK)
    s = s.rotate(rot, expand=True, resample=Image.BICUBIC)
    img.paste(s, xy, s)


def wrap(d, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=f) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def tiers_from_site():
    t = SITE_HTML.read_text()
    out = []
    for key, label in (("under-10", "Under $10"), ("under-20", "Under $20"), ("under-25", "Under $25"), ("under-50", "Under $50")):
        m = re.search(r'<section class="tier-sec" id="%s">(.*?)</section>' % key, t, re.S)
        if not m:
            continue
        cards = re.findall(r'<img src="([^"]+)" loading="lazy" alt="([^"]+)">.*?(?:<div class="price"><b>([^<]+)</b>(?:<s>([^<]+)</s>)?|<h3>)', m.group(1), re.S)
        if len(cards) >= 3:
            out.append((key, label, [(ROOT / "site" / html_.unescape(src), html_.unescape(alt), now or "", was or "") for src, alt, now, was in cards[:4]]))
    return out


def price_pill(img, xy, now, was, size=34):
    """Tangerine price pill with Amazon's list price struck through beside it (site show mode only)."""
    if not now:
        return 0
    d = ImageDraw.Draw(img)
    f = font(B.FONT_TEXT, size, "Black")
    x, y = xy
    w = d.textlength(now, font=f)
    d.rounded_rectangle([x, y, x + w + 36, y + size + 22], radius=14, fill=B.TANGERINE)
    d.text((x + 18, y + 9), now, font=f, fill=(255, 255, 255))
    if was:
        wf = font(B.FONT_TEXT, int(size * .7), "Medium")
        wx, wy = x + w + 50, y + size * .45
        d.text((wx, wy), was, font=wf, fill=B.MUTED)
        ww = d.textlength(was, font=wf)
        d.line([(wx - 2, wy + size * .4), (wx + ww + 2, wy + size * .4)], fill=B.WAS_RED, width=3)
    return size + 22


def base(title_lines, label):
    img = Image.new("RGB", (W, H), B.CREAM)
    d = ImageDraw.Draw(img)
    # soft blobs
    for (cx, cy, r, col) in ((880, 180, 260, B.MINT), (120, 1380, 300, B.LAVENDER)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    d.text((60, 70), "Mom Found It Cheaper", font=font(B.FONT_WORDMARK, 34), fill=B.INK)
    sticker(img, (54, 120), label.upper() + "  ·  CHECKED TODAY", 26)
    f = font(B.FONT_TEXT, 92, "Black")
    y = 230
    for i, line in enumerate(title_lines):
        d.text((60, y), line, font=f, fill=B.INK if i == 0 else B.TANGERINE)
        y += 96
    return img, y


def footer(img):
    """Green proof pill that always fits, plus the Associates disclosure on the image itself."""
    d = ImageDraw.Draw(img)
    text = "✓  Checked against Amazon  ·  momfounditcheaper.com"
    size = 30
    while size > 18 and d.textlength(text, font=font(B.FONT_TEXT, size, "Bold")) > 840:
        size -= 1
    f = font(B.FONT_TEXT, size, "Bold")
    d.rounded_rectangle([60, 1372, 940, 1427], radius=28, fill=B.GREEN)
    d.text((88, 1372 + (55 - size) // 2 - 2), text, font=f, fill=(255, 255, 255))
    d.text((60, 1445), "#ad · As an Amazon Associate I earn from qualifying purchases.", font=font(B.FONT_TEXT, 22, "Bold"), fill=B.MUTED)


def clean_name(alt):
    short = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", alt)
    short = re.sub(r"\b(?=[A-Z0-9-]{5,}\b)(?=[A-Z0-9-]*\d)[A-Z0-9-]+\b", "", short)
    return re.sub(r"\s{2,}", " ", short).strip(" ,-")


def tier_pin(key, label, items):
    img, y = base([label, "mom finds"], label)
    d = ImageDraw.Draw(img)
    # 2x2 photo grid
    gx, gy, cell, gap = 60, y + 24, 410, 28
    for i, (src, alt, now, was) in enumerate(items[:4]):
        x = gx + (i % 2) * (cell + gap)
        yy = gy + (i // 2) * (cell + gap)
        d.rounded_rectangle([x, yy, x + cell, yy + cell], radius=28, fill=(255, 255, 255))
        try:
            ph = cell - 50 - (70 if now else 0)
            p = ImageOps.contain(Image.open(src).convert("RGB"), (cell - 50, ph))
            img.paste(p, (x + (cell - p.width) // 2, yy + 25 + (ph - p.height) // 2))
        except Exception:
            pass
        price_pill(img, (x + 24, yy + cell - 78), now, was, 30)
    footer(img)
    return img


def product_pin(src, alt, label, key, now="", was=""):
    short = clean_name(alt)
    img = Image.new("RGB", (W, H), B.CREAM)
    d = ImageDraw.Draw(img)
    d.ellipse([620, -120, 1140, 400], fill=B.MINT)
    d.ellipse([-180, 1180, 340, 1700], fill=B.LAVENDER)
    d.rounded_rectangle([80, 150, 920, 990], radius=40, fill=(255, 255, 255))
    try:
        p = ImageOps.contain(Image.open(src).convert("RGB"), (760, 760))
        img.paste(p, (80 + (840 - p.width) // 2, 150 + (840 - p.height) // 2))
    except Exception:
        pass
    sticker(img, (60, 110), label.upper(), 30)
    d = ImageDraw.Draw(img)
    f = font(B.FONT_TEXT, 56, "Black")
    y = 1030
    for line in wrap(d, short, f, 880)[:3]:
        d.text((60, y), line, font=f, fill=B.INK)
        y += 64
    if now:
        y += price_pill(img, (60, y + 14), now, was, 44) + 24
        d.text((60, y + 10), "Amazon price this morning. Tap for today's.", font=font(B.FONT_TEXT, 30, "Bold"), fill=B.TANGERINE)
    else:
        d.text((60, y + 10), "Mia found it cheaper. Tap for today's price.", font=font(B.FONT_TEXT, 30, "Bold"), fill=B.TANGERINE)
    footer(img)
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for key, label, items in tiers_from_site():
        p = OUT / f"pin_{key}.png"
        tier_pin(key, label, items).save(p, optimize=True)
        rows.append({"title": f"{label} mom finds — checked against Amazon today", "media_url": p.name,
                     "pinterest_board": "Mom Found It Cheaper", "description": f"{label} finds for moms, every link checked against Amazon this morning. Toys, kitchen, beauty, baby and more. #ad As an Amazon Associate I earn from qualifying purchases.",
                     "link": f"{SITE}#{key}", "keywords": f"{label.lower()} amazon finds, mom deals, gifts {label.lower()}, stocking stuffers"})
        for i, (src, alt, now, was) in enumerate(items[:2], 1):
            pp = OUT / f"pin_{key}_{i}.png"
            product_pin(src, alt, label, key, now, was).save(pp, optimize=True)
            alt = clean_name(alt)
            pr = (f"{now} on Amazon this morning" + (f" (list {was})" if was else "")) if now else f"{label} on Amazon when I checked this morning"
            rows.append({"title": f"{alt[:80]} — {label}", "media_url": pp.name, "pinterest_board": "Mom Found It Cheaper",
                         "description": f"{alt[:120]}. {pr}. Prices change; tap for today's. #ad As an Amazon Associate I earn from qualifying purchases.",
                         "link": f"{SITE}#{key}", "keywords": f"{label.lower()}, amazon finds, mom deals"})
    with open(OUT / "pins.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["title", "media_url", "pinterest_board", "description", "link", "keywords"])
        w.writeheader()
        w.writerows(rows)
    print(f"pins: {len(rows)} -> {OUT}")


if __name__ == "__main__":
    main()
