"""Pinterest pins (1000x1500, 2:3) from the verified site, one per price tier plus one per Top-5 product.
Brand tokens from brand.py; photo + price pill + Mia avatar; link = the tier section on the site.
Output: pins/<date>/pin_<name>.png + pins/<date>/pins.csv in Pinterest's bulk-upload format
(Title, Media URL, Pinterest board, Thumbnail, Description, Link, Publish date, Keywords; Media URL = the public
copy on momfounditcheaper.com/pins/<date>/). Prices are Amazon's morning read, stamped with its date/time.
Run after build_site.py:  python make_pins.py
"""
import utf8_io  # noqa: F401  (first import: forces UTF-8 text IO so Windows cp1252 can't crash on emoji)
import csv
import html as html_
import json
import os


def _sft(_t, _fmt):
    """strftime that works on Windows too: %-d/%-I are glibc-only, Windows needs %#d/%#I."""
    return _t.strftime(_fmt.replace("%-", "%#") if os.name == "nt" else _fmt)
import re
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

import brand as B

ROOT = Path(__file__).parent
SITE_HTML = ROOT / "site" / "index.html"
SITE = "https://momfounditcheaper.com/"
W, H = 1000, 1500


def _et_now():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/New_York"))


OUT = ROOT / "pins" / _et_now().date().isoformat()
try:
    META = json.loads((ROOT / "data" / "product_meta.json").read_text())
except Exception:
    META = {}
try:
    HISTORY = json.loads((ROOT / "data" / "price_history.json").read_text())
except Exception:
    HISTORY = {}


def checked_stamp(asins):
    """'Nov 26, 7:40 PM ET' = the latest Amazon read among the products shown (what the price on the pin is)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    ts = [META.get(a, {}).get("checked", 0) for a in asins if a]
    ts = [t for t in ts if t]
    if not ts:
        return _sft(_et_now(), "%b %-d, %Y")
    t = datetime.fromtimestamp(max(ts), ZoneInfo("America/New_York"))
    return _sft(t, "%b %-d, %-I:%M %p ET")


def _mia():
    try:
        return Image.open(ROOT / B.MIA_AVATAR).convert("RGBA").resize((200, 200))
    except Exception:
        return None


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
        cards = re.findall(r'<article[^>]*data-asin="([A-Z0-9]*)"[^>]*>.*?<img src="([^"]+)" loading="lazy" alt="([^"]+)">.*?(?:<div class="price"><b>([^<]+)</b>(?:<s>([^<]+)</s>)?|<h3>)', m.group(1), re.S)
        items = []
        for asin, src, alt, now, was in cards:
            if now and _price_rose(asin, now):
                continue                                   # our own log shows it cheaper earlier: not a "found it cheaper"
            items.append((ROOT / "site" / html_.unescape(src), html_.unescape(alt), now or "", was or "", asin))
        if len(items) >= 3:
            out.append((key, label, items[:4]))
    return out


def _num(p):
    m = re.search(r"\d[\d,]*\.?\d*", p or "")
    return float(m.group().replace(",", "")) if m else None


def _price_rose(asin, now):
    n = _num(now)
    pts = []
    for k, v in HISTORY.items():
        if asin and asin in k:
            pts = v
            break
    lows = [p for _, p in pts if isinstance(p, (int, float))]
    return bool(n and lows and min(lows) < n * 0.97)


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
        a, b = _num(now), _num(was)
        strike = B.WAS_RED if (a and b and b >= a / 0.7) else B.MUTED     # red only on real >=30% drops (brand rule)
        d.line([(wx - 2, wy + size * .4), (wx + ww + 2, wy + size * .4)], fill=strike, width=3)
    return size + 22


STAMP_ASINS = []


def base(title_lines, label):
    img = Image.new("RGB", (W, H), B.CREAM)
    d = ImageDraw.Draw(img)
    # soft blobs
    for (cx, cy, r, col) in ((880, 180, 260, B.MINT), (120, 1380, 300, B.LAVENDER)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    ad_pill(img, (60, 28))
    d.text((60, 104), "Mom Found It Cheaper", font=font(B.FONT_WORDMARK, 34), fill=B.INK)
    sticker(img, (54, 152), "PRICE-CHECKED " + checked_stamp(STAMP_ASINS).split(",")[0].upper(), 40)
    f = font(B.FONT_TEXT, 92, "Black")
    y = 256
    for i, line in enumerate(title_lines):
        d.text((60, y), line, font=f, fill=B.INK if i == 0 else B.TANGERINE)
        y += 96
    return img, y


def ad_pill(img, xy):
    """Big, high-contrast #AD out of Pinterest's bottom overlay zone (the description carries the full statement)."""
    d = ImageDraw.Draw(img)
    f = font(B.FONT_TEXT, 34, "Black")
    t = "#AD · PAID LINK"
    w = d.textlength(t, font=f)
    x, y = xy
    d.rounded_rectangle([x, y, x + w + 44, y + 58], radius=29, fill=B.INK)
    d.text((x + 22, y + 10), t, font=f, fill=B.CREAM)


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
    STAMP_ASINS[:] = [it[4] for it in items[:4]]
    for i, (src, alt, now, was, _a) in enumerate(items[:4]):
        x = gx + (i % 2) * (cell + gap)
        yy = gy + (i // 2) * (cell + gap)
        d.rounded_rectangle([x, yy, x + cell, yy + cell], radius=28, fill=(255, 255, 255))
        try:
            ph = cell - 50 - (84 if now else 0)
            p = ImageOps.contain(Image.open(src).convert("RGB"), (cell - 50, ph))
            img.paste(p, (x + (cell - p.width) // 2, yy + 25 + (ph - p.height) // 2))
        except Exception:
            pass
        price_pill(img, (x + 24, yy + cell - 92), now, "", 44)        # list price only on single-product pins (unreadable here)
    mia = _mia()
    if mia:
        mia = mia.resize((170, 170))
        img.paste(mia, (W - 60 - 170, 36), mia)
    footer(img)
    return img


def product_pin(src, alt, label, key, now="", was="", asin=""):
    short = clean_name(alt)
    STAMP_ASINS[:] = [asin]
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
    ad_pill(img, (60, 44))
    sticker(img, (60, 128), label.upper(), 34)
    d = ImageDraw.Draw(img)
    f = font(B.FONT_TEXT, 56, "Black")
    y = 1030
    for line in wrap(d, short, f, 880)[:2]:
        d.text((60, y), line, font=f, fill=B.INK)
        y += 64
    mia = _mia()
    if mia:
        img.paste(mia, (W - 60 - 200, 40), mia)
    if now:
        y += price_pill(img, (60, y + 14), now, was, 48) + 24
        d.text((60, y + 10), f"Amazon price {checked_stamp([asin])}. Tap for today's.", font=font(B.FONT_TEXT, 30, "Bold"), fill=B.TANGERINE)
    else:
        d.text((60, y + 10), "Mia found it cheaper. Tap for today's price.", font=font(B.FONT_TEXT, 30, "Bold"), fill=B.TANGERINE)
    footer(img)
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    pub = f"{SITE}pins/{OUT.name}/"                       # build_site copies pins/<date>/ to site/pins/<date>/
    board = "Mom-Approved Finds"
    for key, label, items in tiers_from_site():
        p = OUT / f"pin_{key}.png"
        tier_pin(key, label, items).save(p, optimize=True)
        stamp = checked_stamp([it[4] for it in items])
        rows.append({"Title": f"{label} mom finds — verified on Amazon {stamp.split(',')[0]}", "Media URL": pub + p.name,
                     "Pinterest board": board, "Thumbnail": "",
                     "Description": f"#ad {label} mom finds that actually deliver \U0001F447 Toys, kitchen, beauty & baby, each price read on Amazon {stamp}. Tap for today's price. As an Amazon Associate I earn from qualifying purchases.",
                     "Link": f"{SITE}#{key}", "Publish date": "",
                     "Keywords": f"{label.lower()} amazon finds, mom deals, gifts {label.lower()}, stocking stuffers, budget finds for moms, black friday deals"})
        for i, (src, alt, now, was, asin) in enumerate(items[:2], 1):
            pp = OUT / f"pin_{key}_{i}.png"
            product_pin(src, alt, label, key, now, was, asin).save(pp, optimize=True)
            raw = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", alt)
            nm = clean_name(alt)
            st = checked_stamp([asin])
            pr = (f"{now} on Amazon as of {st}" + (f" (list price {was})" if was else "")) if now else f"{label} on Amazon as of {st}"
            _mn = re.search(r"[\d.]+", now or ""); _mw = re.search(r"[\d.]+", was or "")
            _nn = float(_mn.group()) if _mn else 0.0
            _nw = float(_mw.group()) if _mw else 0.0
            _offp = int(round((1 - _nn / _nw) * 100)) if _nw > 0 and _nn > 0 else 0
            # Hook-first description: lead with the discount when there's a real one, else the plain name+price.
            _desc = (f"\U0001F525 {_offp}% off — {nm[:90]} is {now} (was {was}). Price read Amazon {st}. Tap for today's price."
                     if _offp >= 15 else f"{nm[:120]}. {pr}. Prices change; tap for today's.")
            codes = " ".join(re.findall(r"\b\d{4,6}\b", raw))
            rows.append({"Title": f"{nm[:80]} — {label}", "Media URL": pub + pp.name, "Pinterest board": board, "Thumbnail": "",
                         "Description": f"#ad {_desc} As an Amazon Associate I earn from qualifying purchases.",
                         "Link": f"{SITE}#{key}", "Publish date": "",
                         "Keywords": ", ".join(x for x in [nm.lower()[:60], codes, label.lower(), "amazon finds", "mom deals", "gift ideas"] if x)})
    with open(OUT / "pins.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["Title", "Media URL", "Pinterest board", "Thumbnail", "Description", "Link", "Publish date", "Keywords"])
        w.writeheader()
        w.writerows(rows)
    print(f"pins: {len(rows)} -> {OUT}")


if __name__ == "__main__":
    main()
