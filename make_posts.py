"""Mom Found It Cheaper - themed collage posts for the Facebook group.

Each post is ONE image with 3 related deals from the same category (all categories,
no niche), plus a caption and a first-comment text, the same layout the big deal
groups use: themed headline, "(AD)(Commission earned)", link in the first comment.

Run:  python make_posts.py        (needs: pip install pillow)
Output: posts/post_N.png and posts/post_N.txt (caption + first comment to paste)
No Claude, no API keys. Uses photos/ when a photo matches a deal, else clean text tiles.
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

from copy_bank import PERSONAL, pick
from qa import check as qa_check
from deal_finder import is_amazon, no_price_title, product_key
from make_videos import (AMAZON_PRICES, BRAND, CHAR, GOLD, IVORY, MUTED, SITE, SKIP_WORDS,
                         as_of, centered, find_photo, fit, masthead, price_value, rule, sans,
                         serif, short_title, wrap)
from trends_finder import load_signals, viral_sources

SIGNALS = load_signals()
PW, PH = 1080, 1350                                    # 4:5 feed image
POSTS_PER_RUN = int(os.environ.get("POSTS_PER_RUN") or "8")
MAX_PRICE = float(os.environ.get("POST_MAX_PRICE") or "0")   # 0 = no price cap (all categories)
META_FILE = Path("data/product_meta.json")
META = json.loads(META_FILE.read_text()) if META_FILE.exists() else {}
DEALS_FILE = Path("data/deals.json")
MADE_FILE = Path("data/posts_made.json")
OUT = Path("posts")
TILE_H, TILE_GAP, TILE_TOP = 270, 30, 340

THEMES = {
    "Baby & Kids": "Baby & kids finds",
    "Toys & Games": "Toy & game finds",
    "Beauty & Health": "Beauty finds",
    "Home & Kitchen": "Home & kitchen finds",
    "Fashion": "Fashion finds",
    "Tech & Electronics": "Tech finds",
    "Grocery & Household": "Household finds",
    "Pets": "Pet finds",
    "Outdoor & Tools": "Outdoor & tools finds",
    "Everything else": "Today's top finds",
}
HASHTAGS = "#ad #amazonfinds #dealsforyou #founditcheaper #savemoney"
HASHTAG_SET = HASHTAGS


def clean_code(deal):
    """Show a code only when it looks usable; never one marked expired."""
    code = deal.get("code") or ""
    if not code or code == "w/ code" or deal.get("code_label") in ("expired", "may be expired"):
        return ""
    return code


def score(deal):
    s = {"likely works": 3, "check first": 1}.get(deal.get("code_label"), 0)
    s += 1 if deal.get("asin") else 0
    s += 2 if find_photo(deal) else 0
    s += 2 * len(viral_sources(deal, SIGNALS))
    s += min(deal.get("thumbs", 0), 100) / 50
    return s


def pick_groups(deals, made):
    """Best 3 fresh deals per category, strongest categories first."""
    by_cat, seen_keys = {}, set()
    for d in sorted(deals, key=lambda x: x["seen"], reverse=True):
        price = price_value(d.get("price", ""))
        low = d["title"].lower()
        key = product_key(d)
        if os.environ.get("REQUIRE_PHOTO", "1") == "1" and not find_photo(d):
            continue                                   # no photo = looks like a scam to shoppers
        if qa_check(d)[0] or not is_amazon(d):      # Amazon-only: our affiliate link is Amazon
            continue
        if (d["id"] in made or key in seen_keys or price is None or price < 1
                or (MAX_PRICE and price > MAX_PRICE) or d.get("expired")
                or any(w in low for w in SKIP_WORDS)):
            continue
        seen_keys.add(key)
        by_cat.setdefault(d.get("category", "Everything else"), []).append(d)
    groups = []
    for cat, items in by_cat.items():
        items.sort(key=score, reverse=True)
        if len(items) >= 3:
            groups.append((sum(score(i) for i in items[:3]), cat, items[:3]))
    groups.sort(key=lambda g: g[0], reverse=True)
    return [(cat, items) for _, cat, items in groups[:POSTS_PER_RUN]]


AT_RE = re.compile(r"\s+@\w+.*$")
COND_RE = re.compile(r"\s*\bw/\s*(?:S&S|Prime|Subscribe\s*&\s*Save|Coupon|Clip(?:pable)? Coupon)\b.*$", re.I)


def tidy(title):
    """Drop deal-site shorthand (w/ S&S, w/ Prime) that means nothing to shoppers."""
    t = AT_RE.sub("", COND_RE.sub("", title)).strip(" -,")
    if len(t) >= 85:                       # was cut at 90 characters: drop the broken last words
        words = t.split()[:-1]
        while words and len(words[-1].strip(",.")) <= 2:
            words.pop()
        t = " ".join(words)
    return t


def proof(deal):
    """'4.8 stars, 7.6K reviews' when we have it (only for products with enough reviews to mean something)."""
    m = META.get(deal.get("asin", ""))
    if not m or not m.get("rating") or (m.get("reviews") or 0) < 100:
        return ""
    n = m["reviews"]
    return f"{m['rating']:.1f} stars  |  " + (f"{n/1000:.1f}K" if n >= 1000 else str(n)) + " reviews"


def draw_tile(img, i, deal, top):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([60, top, PW - 60, top + TILE_H], 36, fill=(255, 255, 255), outline=GOLD, width=3)
    box = 210
    bx, by = 90, top + (TILE_H - box) // 2
    photo = find_photo(deal)
    shown = False
    if photo:
        try:
            pic = ImageOps.contain(Image.open(photo).convert("RGB"), (box, box))
            img.paste(pic, (bx + (box - pic.width) // 2, by + (box - pic.height) // 2))
            shown = True
        except Exception as e:
            print(f"[warn] photo {photo}: {e}")
    d = ImageDraw.Draw(img)
    if not shown:
        d.rounded_rectangle([bx, by, bx + box, by + box], 28, fill=IVORY)
        nf = serif(96, "Bold")
        num = f"{i}"
        d.text((bx + (box - d.textlength(num, font=nf)) / 2, by + 48), num, font=nf, fill=GOLD)
    x, w = 340, PW - 60 - 30 - 340
    amazon = is_amazon(deal)
    title = tidy(short_title(no_price_title(deal["title"]) if amazon else deal["title"]))
    tf = fit(d, title, lambda s: serif(s, "SemiBold"), 44, w, max_lines=2, min_size=30)
    y = top + 28
    for line in wrap(d, title, tf, w)[:2]:
        d.text((x, y), line, font=tf, fill=CHAR)
        y += tf.size + 6
    if amazon and AMAZON_PRICES == "hide":
        d.text((x, y + 10), "Price drop on Amazon", font=serif(46, "Bold"), fill=GOLD)
    else:
        pf = serif(64, "Bold")
        d.text((x, y + 4), deal["price"], font=pf, fill=GOLD)
        code = clean_code(deal)
        extra = (f"CODE {code}" if code else "CLIP THE COUPON" if deal.get("coupon") else "")
        was = deal.get("was", "")
        if was and price_value(was) and price_value(deal["price"]) and price_value(was) > price_value(deal["price"]):
            wf = sans(30, "Medium")        # struck-through earlier price, beside the new one
            wx, wy = x + d.textlength(deal["price"], font=pf) + 24, y + 22
            d.text((wx, wy), f"was {was}", font=wf, fill=MUTED)
            d.line([(wx - 2, wy + 20), (wx + d.textlength(f"was {was}", font=wf) + 2, wy + 20)], fill=MUTED, width=3)
            extra_x = wx + d.textlength(f"was {was}", font=wf) + 24
        else:
            extra_x = x + d.textlength(deal["price"], font=pf) + 30
        if extra:        # beside the price, never on top of it
            d.text((extra_x, y + 30) if extra_x < PW - 360 else (x, y + 72), extra,
                   font=sans(28, "SemiBold"), fill=CHAR)
    pr = proof(deal)
    if pr:
        pf2 = sans(24, "SemiBold")          # right end of the bottom row, next to the price stamp
        d.text((PW - 90 - d.textlength(pr, font=pf2), top + TILE_H - 96), pr, font=pf2, fill=GOLD)
    if amazon and AMAZON_PRICES != "hide":
        d.text((x, top + TILE_H - 50), f"Amazon price as of {as_of(deal['seen'])}",
               font=sans(24, "Medium"), fill=MUTED)


def make_image(path, theme, items):
    img = Image.new("RGB", (PW, PH), IVORY)
    d = ImageDraw.Draw(img)
    masthead(d, CHAR, y=70)
    tf = fit(d, theme, lambda s: serif(s, "Regular", italic=True), 96, PW - 160, max_lines=1, min_size=60)
    centered(d, 175, theme, tf, CHAR)
    rule(d, 312, 160)
    for i, deal in enumerate(items, 1):
        draw_tile(img, i, deal, TILE_TOP + (i - 1) * (TILE_H + TILE_GAP))
    d = ImageDraw.Draw(img)
    centered(d, 1262, "PRICES SUBJECT TO CHANGE ANYTIME  ·  LINK TO SHOP IN COMMENTS", sans(24, "Medium"),
             MUTED, spacing=3, max_w=PW - 80)
    centered(d, 1298, "#AD", sans(24, "SemiBold"), MUTED, spacing=4)
    img.save(path)



# ---------- layout v2: bold, photo-first (closer to the big deal groups) ----------
TRUST = (21, 101, 192)   # blue = trust, used for ratings
ORANGE = ((255, 143, 0), (255, 255, 255))
GREEN = ((46, 160, 90), (255, 235, 59))
TEAL = ((0, 137, 123), (255, 213, 79))
GOLD = ((255, 193, 7), (27, 94, 32))
ROT = [ORANGE, GREEN, TEAL, GOLD]
PALETTES = {                      # locked set: orange, green, teal, golden yellow
    "Baby & Kids": GOLD, "Toys & Games": ORANGE, "Beauty & Health": TEAL,
    "Home & Kitchen": GREEN, "Fashion": ORANGE, "Tech & Electronics": TEAL,
    "Grocery & Household": GREEN, "Pets": GOLD, "Outdoor & Tools": GREEN,
    "Everything else": ORANGE,
}
V2_TILE_H, V2_GAP, V2_TOP = 300, 18, 310


def fg(img):
    """Text color for the poster background: white on dark, deep green-brown on light."""
    r, g, b = img.getpixel((3, 3))
    return (33, 33, 33) if 0.299 * r + 0.587 * g + 0.114 * b > 170 else (255, 255, 255)


def was_of(deal):
    """Earlier price: from the deal itself, else Amazon's list price (read from the product page)."""
    w = deal.get("was", "")
    if not w:
        w = (META.get(deal.get("asin", "")) or {}).get("list") or ""
    return w


def pct_off(deal):
    a, b = price_value(deal.get("price", "")), price_value(was_of(deal))
    return round((1 - a / b) * 100) if a and b and b > a else 0


def draw_tile_v2(img, i, deal, top, accent):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, top, PW - 40, top + V2_TILE_H], 30, fill=(255, 255, 255))
    box = 250
    bx, by = 62, top + (V2_TILE_H - box) // 2
    photo = find_photo(deal)
    shown = False
    if photo:
        try:
            pic = ImageOps.contain(Image.open(photo).convert("RGB"), (box, box))
            img.paste(pic, (bx + (box - pic.width) // 2, by + (box - pic.height) // 2))
            shown = True
        except Exception as e:
            print(f"[warn] photo {photo}: {e}")
    d = ImageDraw.Draw(img)
    if not shown:                  # no photo yet: soft tile with the first letters of the product
        d.rounded_rectangle([bx, by, bx + box, by + box], 24, fill=(244, 241, 236))
        word = (short_title(no_price_title(deal["title"])).split() or ["?"])[0][:10]
        lf = fit(d, word, lambda s: sans(s, "Bold"), 56, box - 30, max_lines=1, min_size=26)
        d.text((bx + (box - d.textlength(word, font=lf)) / 2, by + box / 2 - lf.size / 2), word, font=lf, fill=(160, 150, 140))
    d.ellipse([bx - 14, top - 14, bx + 46, top + 46], fill=CHAR)        # number badge
    d.text((bx + 16 - d.textlength(str(i), font=sans(34, "Bold")) / 2 + 14, top - 6), str(i), font=sans(34, "Bold"), fill=(255, 255, 255))
    x, w = 340, PW - 40 - 30 - 340
    title = tidy(short_title(no_price_title(deal["title"])))
    tf = fit(d, title, lambda s: sans(s, "Bold"), 38, w, max_lines=2, min_size=28)
    y = top + 24
    for line in wrap(d, title, tf, w)[:2]:
        d.text((x, y), line, font=tf, fill=CHAR)
        y += tf.size + 6
    pf = sans(66, "Bold")
    price = deal["price"]
    pw_ = d.textlength(price, font=pf)
    d.rounded_rectangle([x - 6, y + 4, x + pw_ + 26, y + 86], 22, fill=accent[0] if False else CHAR)
    d.text((x + 10, y + 8), price, font=pf, fill=(255, 255, 255))
    cx = x + pw_ + 44
    off, was = pct_off(deal), was_of(deal)
    if off >= 10:
        d.rounded_rectangle([cx, y + 16, cx + 150, y + 70], 27, fill=(229, 57, 53))
        d.text((cx + 16, y + 24), f"{off}% OFF", font=sans(30, "Bold"), fill=(255, 255, 255))
        cx += 168
    if was and off:
        wf = sans(28, "Medium")
        d.text((cx, y + 30), f"was {was}", font=wf, fill=MUTED)
        d.line([(cx - 2, y + 46), (cx + d.textlength(f"was {was}", font=wf) + 2, y + 46)], fill=MUTED, width=3)
    code = clean_code(deal)
    extra = (f"CODE  {code}" if code else "CLIP THE COUPON" if deal.get("coupon") else "")
    row = y + 100
    if extra:
        ef = sans(28, "Bold")
        ew = d.textlength(extra, font=ef)
        d.rounded_rectangle([x - 6, row, x + ew + 26, row + 46], 23, outline=CHAR, width=3)
        d.text((x + 10, row + 6), extra, font=ef, fill=CHAR)
    pr = proof(deal)
    if pr:
        sf = sans(26, "SemiBold")
        d.text((PW - 70 - d.textlength(pr, font=sf), row + 8), pr.replace("stars", "\u2605"), font=sf, fill=TRUST)
    if is_amazon(deal) and AMAZON_PRICES != "hide":
        d.text((x, top + V2_TILE_H - 36), f"Amazon price as of {as_of(deal['seen'])}", font=sans(22, "Medium"), fill=MUTED)


def sticker(img, text, cx, cy, fill, ink=(255, 255, 255), angle=-8):
    """Round-cornered sticker, slightly tilted, like the hand-made look of the big deal groups."""
    f = sans(30, "Bold")
    tmp = Image.new("RGBA", (330, 110), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    w = td.textlength(text, font=f)
    td.rounded_rectangle([10, 15, 10 + w + 44, 85], 35, fill=fill)
    td.text((32, 32), text, font=f, fill=ink)
    tmp = tmp.rotate(angle, expand=True, resample=Image.BICUBIC)
    img.paste(tmp, (int(cx - tmp.width / 2), int(cy - tmp.height / 2)), tmp)


def cta_pill(img, y=1260, h=68):
    """Bold, readable footer: where the links are + why to join."""
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, y, PW - 40, y + h], h // 2, fill=(255, 255, 255))
    t = "LINKS IN THE 1ST COMMENT  \u00b7  JOIN FREE FOR DAILY DEALS"
    f = fit(d, t, lambda z: sans(z, "Bold"), 32, PW - 140, max_lines=1, min_size=22)
    centered(d, y + (h - f.size) // 2 - 4, t, f, (33, 33, 33), max_w=PW - 120)

HAND = Path(__file__).parent / "fonts" / "Caveat-Bold.ttf"


def hand(size):
    try:
        return ImageFont.truetype(str(HAND), size)
    except OSError:
        return sans(size, "Bold")


def mom_note(deal):
    """Short first-person line built only from real numbers."""
    m = META.get(deal.get("asin", "")) or {}
    off = pct_off(deal)
    if m.get("reviews", 0) >= 100 and m.get("rating", 0) >= 4.3:
        return f"{m['rating']:.1f} stars from {m['reviews']:,} shoppers. I'd grab this one!"
    if off >= 15:
        return f"{off}% below the list price. Worth a look!"
    return "Found this one for you. Check the price first!"


def make_image_single(path, deal, cat="Everything else"):
    """One product, big photo, handwritten mom note. Feels like a friend's find, not a flyer."""
    bg, accent = PALETTES.get(cat, PALETTES["Everything else"])
    img = Image.new("RGB", (PW, PH), bg)
    d = ImageDraw.Draw(img)
    centered(d, 46, "MOM FOUND IT CHEAPER", sans(30, "SemiBold"), fg(img), spacing=8)
    d.rounded_rectangle([40, 100, PW - 40, 1066], 40, fill=(255, 255, 255))
    _photo_into(img, deal, (70, 116), (PW - 140, 520))
    d = ImageDraw.Draw(img)
    y = _title(d, deal, 80, 668, PW - 160, 42, 2, 30)
    y = _price_row(img, deal, 80, y + 6, 76, PW - 160)
    _chips(img, deal, 80, y + 4, PW - 160, 30)
    # sticky note, tilted
    note = Image.new("RGBA", (560, 200), (0, 0, 0, 0))
    nd = ImageDraw.Draw(note)
    nd.rounded_rectangle([8, 8, 552, 192], 14, fill=(255, 247, 170))
    nf = hand(46)
    lines = wrap(nd, "Mom's pick: " + mom_note(deal), nf, 500)[:3]
    yy = 24
    for ln in lines:
        nd.text((28, yy), ln, font=nf, fill=(60, 50, 20))
        yy += 56
    note = note.rotate(5, expand=True, resample=Image.BICUBIC)
    img.paste(note, (PW - note.width - 30, 372), note)
    cta_pill(img, 1088, 74)
    d = ImageDraw.Draw(img)
    centered(d, 1182, "Prices checked today, they can change.", sans(28, "Medium"), fg(img), max_w=PW - 80)
    centered(d, 1230, "#AD  \u00b7  AMAZON ASSOCIATE, I EARN FROM QUALIFYING PURCHASES", sans(22, "SemiBold"), fg(img), spacing=2, max_w=PW - 60)
    img.save(path)



def make_image_v2(path, theme, items, cat="Everything else"):
    bg, accent = PALETTES.get(cat, PALETTES["Everything else"])
    img = Image.new("RGB", (PW, PH), bg)
    d = ImageDraw.Draw(img)
    centered(d, 52, "MOM FOUND IT CHEAPER", sans(30, "SemiBold"), fg(img), spacing=8)
    head = theme.upper()
    hf = fit(d, head, lambda s: sans(s, "Bold"), 104, PW - 120, max_lines=1, min_size=56)
    centered(d, 118, head, hf, fg(img), max_w=PW - 60)
    centered(d, 118 + hf.size + 22, "TODAY'S PRICE DROPS", sans(34, "SemiBold"), accent, spacing=6)
    for i, deal in enumerate(items, 1):
        draw_tile_v2(img, i, deal, V2_TOP + (i - 1) * (V2_TILE_H + V2_GAP), accent)
    star = best_item(items)
    k = items.index(star)
    sticker(img, "MOM'S PICK", 200, V2_TOP + k * (V2_TILE_H + V2_GAP) + V2_TILE_H - 22, (255, 193, 7), ink=(40, 40, 40))
    d = ImageDraw.Draw(img)
    cta_pill(img, 1262)
    img.save(path)


# ---------- layouts B and C ----------
def _photo_into(img, deal, box_xy, size):
    """Paste the product photo (contained, centered) or a soft brand tile."""
    x0, y0 = box_xy
    w, h = size
    d = ImageDraw.Draw(img)
    photo = find_photo(deal)
    if photo:
        try:
            pic = ImageOps.contain(Image.open(photo).convert("RGB"), (w, h))
            img.paste(pic, (x0 + (w - pic.width) // 2, y0 + (h - pic.height) // 2))
            return
        except Exception as e:
            print(f"[warn] photo {photo}: {e}")
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], 24, fill=(244, 241, 236))
    word = (short_title(no_price_title(deal["title"])).split() or ["?"])[0][:10]
    lf = fit(d, word, lambda s: sans(s, "Bold"), 64, w - 30, max_lines=1, min_size=26)
    d.text((x0 + (w - d.textlength(word, font=lf)) / 2, y0 + h / 2 - lf.size / 2), word, font=lf, fill=(160, 150, 140))


def _price_row(img, deal, x, y, big, max_w):
    """Price pill, % off badge, was price. Returns y below the row."""
    d = ImageDraw.Draw(img)
    pf = sans(big, "Bold")
    price = deal["price"]
    pw_ = d.textlength(price, font=pf)
    d.rounded_rectangle([x - 6, y, x + pw_ + 26, y + big + 22], 22, fill=CHAR)
    d.text((x + 10, y + 6), price, font=pf, fill=(255, 255, 255))
    off, was = pct_off(deal), was_of(deal)
    cx = x + pw_ + 42
    bf = sans(max(22, big // 2 - 6), "Bold")
    if off >= 10:
        label = f"{off}% OFF"
        bw = d.textlength(label, font=bf) + 32
        if cx + bw <= x + max_w:
            d.rounded_rectangle([cx, y + 8, cx + bw, y + 8 + bf.size + 18], 24, fill=(229, 57, 53))
            d.text((cx + 16, y + 15), label, font=bf, fill=(255, 255, 255))
            cx += bw + 14
    if was and off and cx + d.textlength(f"was {was}", font=sans(26)) <= x + max_w:
        wf = sans(26, "Medium")
        d.text((cx, y + 20), f"was {was}", font=wf, fill=MUTED)
        d.line([(cx - 2, y + 35), (cx + d.textlength(f"was {was}", font=wf) + 2, y + 35)], fill=MUTED, width=3)
    return y + big + 34


def _chips(img, deal, x, y, max_w, size=26):
    d = ImageDraw.Draw(img)
    code = clean_code(deal)
    extra = (f"CODE  {code}" if code else "CLIP THE COUPON" if deal.get("coupon") else "")
    if extra:
        ef = sans(size, "Bold")
        ew = d.textlength(extra, font=ef)
        d.rounded_rectangle([x - 6, y, x + ew + 24, y + size + 18], 22, outline=CHAR, width=3)
        d.text((x + 9, y + 7), extra, font=ef, fill=CHAR)
        y += size + 30
    pr = proof(deal)
    if pr:
        d.text((x, y), pr.replace("stars", "\u2605"), font=sans(size - 2, "SemiBold"), fill=TRUST)
        y += size + 8
    if is_amazon(deal) and AMAZON_PRICES != "hide":
        sf = sans(20, "Medium")
        for line in wrap(d, f"Amazon price as of {as_of(deal['seen'])}", sf, max_w):
            d.text((x, y), line, font=sf, fill=MUTED)
            y += 24
    return y


def _header(img, theme, accent):
    d = ImageDraw.Draw(img)
    centered(d, 52, "MOM FOUND IT CHEAPER", sans(30, "SemiBold"), fg(img), spacing=8)
    head = theme.upper()
    hf = fit(d, head, lambda s: sans(s, "Bold"), 104, PW - 120, max_lines=1, min_size=56)
    centered(d, 118, head, hf, fg(img), max_w=PW - 60)
    centered(d, 118 + hf.size + 22, "TODAY'S PRICE DROPS", sans(34, "SemiBold"), accent, spacing=6)


def _title(d, deal, x, y, w, start, lines=2, mn=26):
    t = tidy(short_title(no_price_title(deal["title"])))
    tf = fit(d, t, lambda s: sans(s, "Bold"), start, w, max_lines=lines, min_size=mn)
    for line in wrap(d, t, tf, w)[:lines]:
        d.text((x, y), line, font=tf, fill=CHAR)
        y += tf.size + 6
    return y


def make_image_hero(path, theme, items, cat="Everything else"):
    """B: one big hero deal, two smaller ones below."""
    bg, accent = PALETTES.get(cat, PALETTES["Everything else"])
    img = Image.new("RGB", (PW, PH), bg)
    _header(img, theme, accent)
    star = best_item(items)
    rest = [i for i in items if i is not star][:2]
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, 290, PW - 40, 740], 34, fill=(255, 255, 255))
    _photo_into(img, star, (66, 308), (420, 410))
    d = ImageDraw.Draw(img)
    y = _title(d, star, 520, 322, PW - 40 - 30 - 520, 42, 3, 30)
    y = _price_row(img, star, 520, y + 8, 84, PW - 40 - 30 - 520)
    _chips(img, star, 520, y + 6, 480, 28)
    sticker(img, "MOM'S PICK", 250, 722, (255, 193, 7), ink=(40, 40, 40))
    for k, deal in enumerate(rest):
        x0 = 40 + k * 510
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([x0, 762, x0 + 490, 1244], 30, fill=(255, 255, 255))
        _photo_into(img, deal, (x0 + 20, 778), (450, 190))
        d = ImageDraw.Draw(img)
        y = _title(d, deal, x0 + 24, 980, 442, 30, 2, 22)
        y = _price_row(img, deal, x0 + 24, y + 4, 52, 442)
        _chips(img, deal, x0 + 24, y + 2, 442, 22)
    d = ImageDraw.Draw(img)
    cta_pill(img, 1262)
    img.save(path)


def make_image_trio(path, theme, items, cat="Everything else"):
    """C: three tall poster cards side by side, photo on top."""
    bg, accent = PALETTES.get(cat, PALETTES["Everything else"])
    img = Image.new("RGB", (PW, PH), bg)
    _header(img, theme, accent)
    star = best_item(items)
    cw, gap = 320, 20
    for k, deal in enumerate(items[:3]):
        x0 = 40 + k * (cw + gap)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([x0, 300, x0 + cw, 1085], 30, fill=(255, 255, 255))
        _photo_into(img, deal, (x0 + 15, 316), (cw - 30, 290))
        d = ImageDraw.Draw(img)
        d.ellipse([x0 - 8, 292, x0 + 44, 344], fill=CHAR)
        d.text((x0 + 36 - d.textlength(str(k + 1), font=sans(32, "Bold")) / 2, 298), str(k + 1), font=sans(32, "Bold"), fill=(255, 255, 255))
        y = _title(d, deal, x0 + 18, 626, cw - 36, 30, 3, 22)
        y = _price_row(img, deal, x0 + 18, y + 8, 56, cw - 36)
        off = pct_off(deal)
        d = ImageDraw.Draw(img)
        if off >= 10:
            d.text((x0 + 18, y), f"was {was_of(deal)}  ({off}% off)", font=sans(24, "Medium"), fill=MUTED)
            y += 36
        _chips(img, deal, x0 + 18, y + 6, cw - 36, 24)
        if deal is star:
            sticker(img, "MOM'S PICK", x0 + cw - 90, 330, (255, 193, 7), ink=(40, 40, 40), angle=10)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, 1110, PW - 40, 1250], 34, fill=accent)
    ink = CHAR if sum(accent) > 480 else (255, 255, 255)
    centered(d, 1134, "LINKS IN THE 1ST COMMENT", sans(50, "Bold"), ink, max_w=PW - 100)
    centered(d, 1198, "join free for daily deals  \u00b7  prices checked today, can change", sans(26, "Medium"), ink, max_w=PW - 100)
    centered(d, 1290, "#AD  \u00b7  AMAZON ASSOCIATE, I EARN FROM QUALIFYING PURCHASES", sans(23, "SemiBold"), fg(img), spacing=3, max_w=PW - 60)
    img.save(path)


def link_for(deal):
    return f"{SITE}#d-{hashlib.sha1(deal['id'].encode()).hexdigest()[:10]}"


BANDS = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 150, 200, 300]


def fun_theme(cat, items):
    """'Games under $15' beats 'Toy finds': the price band tells people what they are getting."""
    top = max(price_value(i["price"]) or 0 for i in items)
    band = next((b for b in BANDS if top <= b), None)
    base = THEMES.get(cat, "Today's top finds").replace(" finds", "").replace("Today's top", "Top")
    return f"{base} under ${band}" if band else f"{base} worth a look"


def score_tile(deal):
    m = META.get(deal.get("asin", "")) or {}
    return (m.get("reviews") or 0) ** 0.5 * (m.get("rating") or 0) + 3 * pct_off(deal)


def best_item(items):
    return max(items, key=score_tile)


def story(items):
    """One honest, specific line built from real numbers (never invented)."""
    b = best_item(items)
    name = " ".join(tidy(short_title(no_price_title(b["title"]))).split(",")[0].split()[:4])
    m = META.get(b.get("asin", "")) or {}
    off = pct_off(b)
    bits = []
    if off >= 15:
        bits.append(f"{off}% under Amazon's list price")
    if m.get("reviews", 0) >= 100 and m.get("rating", 0) >= 4.3:
        n = m["reviews"]
        bits.append(f"{m['rating']:.1f} stars from {n:,} shoppers")
    return f"Our pick today: {name}, " + " and ".join(bits) + "." if bits else ""


QUESTIONS = ["Which one is going in your cart?", "Which would you grab first?", "Any of these already on your list?",
             "Tell us which one you want and we will keep an eye out for more like it.", "Which find surprised you most?"]


def texts(theme, items):
    names = [tidy(short_title(no_price_title(i["title"]))) for i in items]
    names = [" ".join(re.sub(r"^\[[^\]]*\]\s*", "", n).split(",")[0].split()[:5]).rstrip(".,;:- ") for n in names]
    st = story(items)
    caption = (f"✨ {theme}: {names[0]}, {names[1]} and {names[2]}\n"
               + (f"{st}\n" if st else "")
               + f"{pick(QUESTIONS, items[0]['id'], 'q')}\nLinks are in the first comment. Join Mom Found It Cheaper for a daily list.\n(AD)(Commission earned) As an Amazon Associate I earn from qualifying purchases.\n\n{HASHTAG_SET}")
    lines = ["Shop here (prices and codes can change):"]
    for n, i in zip(names, items):
        code = clean_code(i)
        tip = f" - code {code}" if code else (" - clip the coupon" if i.get("coupon") else "")
        hist = f"\nPrice history: https://camelcamelcamel.com/product/{i['asin']}" if i.get("asin") else ""
        lines.append(f"{n}{tip}\n{link_for(i)}{hist}")
    lines.append("As an Amazon Associate I earn from qualifying purchases.")
    return caption, "\n".join(lines)


def main():
    deals = json.loads(DEALS_FILE.read_text()) if DEALS_FILE.exists() else []
    made = set(json.loads(MADE_FILE.read_text())) if MADE_FILE.exists() else set()
    OUT.mkdir(exist_ok=True)
    groups = pick_groups(deals, made)
    for n, (cat, items) in enumerate(groups, 1):
        theme = fun_theme(cat, items)
        k = datetime.now(timezone.utc).toordinal() + n
        base = PALETTES.get(cat, PALETTES["Everything else"])
        schemes = [base, ROT[(k // 3) % len(ROT)], base, ROT[(k // 3 + 1) % len(ROT)]]
        PALETTES[cat] = schemes[k % 4]
        layout = os.environ.get("POST_LAYOUT") or ["list", "hero", "trio"][k % 3]
        p = OUT / f"post_{n}.png"
        if layout == "hero":
            make_image_hero(p, theme, items, cat)
        elif layout == "trio":
            make_image_trio(p, theme, items, cat)
        else:
            make_image_v2(p, theme, items, cat)
        PALETTES[cat] = base
        caption, comment = texts(theme, items)
        (OUT / f"post_{n}.txt").write_text(f"CAPTION:\n{caption}\n\nFIRST COMMENT (paste after posting):\n{comment}\n")
        made.update(i["id"] for i in items)
        print(f"made post_{n}.png - {theme}: " + " | ".join(i["title"][:30] for i in items))

    # one extra single-product "Mom's pick" post: best-reviewed item with a photo
    pool = [d for d in deals if is_amazon(d) and (META.get(d.get("asin", "")) or {}).get("reviews", 0) >= 100 and find_photo(d) and not qa_check(d)[0] and d["id"] not in made
            and price_value(d.get("price", "")) and not any(w in d["title"].lower() for w in SKIP_WORDS)]
    if pool:
        star = max(pool, key=lambda x: ((META.get(x.get("asin", "")) or {}).get("reviews", 0), pct_off(x)))
        cat = star.get("category", "Everything else")
        PALETTES["_s"] = ROT[datetime.now(timezone.utc).toordinal() % len(ROT)]
        make_image_single(OUT / "post_single.png", star, "_s")
        nm = tidy(short_title(no_price_title(star["title"])))
        cap = (f"Mom's pick today: {nm}.\n{mom_note(star)}\nLink is in the first comment. Join Mom Found It Cheaper for a daily list.\n"
               f"(AD)(Commission earned) As an Amazon Associate I earn from qualifying purchases.\n\n{HASHTAG_SET}")
        cm = f"Shop here (prices and codes can change):\n{link_for(star)}\nAs an Amazon Associate I earn from qualifying purchases."
        (OUT / "post_single.txt").write_text(f"CAPTION:\n{cap}\n\nFIRST COMMENT (paste after posting):\n{cm}\n")
        print("made post_single.png")
    MADE_FILE.write_text(json.dumps(sorted(made)[-900:], indent=1))
    print(f"{len(groups)} posts made")


if __name__ == "__main__":
    main()
