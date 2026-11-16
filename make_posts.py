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

from PIL import Image, ImageDraw, ImageOps

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


COND_RE = re.compile(r"\s*\bw/\s*(?:S&S|Prime|Subscribe\s*&\s*Save|Coupon|Clip(?:pable)? Coupon)\b.*$", re.I)


def tidy(title):
    """Drop deal-site shorthand (w/ S&S, w/ Prime) that means nothing to shoppers."""
    return COND_RE.sub("", title).strip(" -,")


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
PALETTES = {                      # (background, accent) per category
    "Baby & Kids": ((255, 183, 77), (216, 67, 21)),
    "Toys & Games": ((126, 87, 194), (255, 202, 40)),
    "Beauty & Health": ((236, 100, 140), (255, 255, 255)),
    "Home & Kitchen": ((0, 137, 123), (255, 213, 79)),
    "Fashion": ((40, 53, 147), (255, 138, 128)),
    "Tech & Electronics": ((21, 101, 192), (255, 235, 59)),
    "Grocery & Household": ((67, 160, 71), (255, 241, 118)),
    "Pets": ((239, 108, 0), (255, 255, 255)),
    "Outdoor & Tools": ((55, 71, 79), (255, 193, 7)),
    "Everything else": ((216, 67, 21), (255, 235, 59)),
}
V2_TILE_H, V2_GAP, V2_TOP = 300, 18, 310


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
        d.text((PW - 70 - d.textlength(pr, font=sf), row + 8), pr.replace("stars", "\u2605"), font=sf, fill=(190, 120, 0))
    if is_amazon(deal) and AMAZON_PRICES != "hide":
        d.text((x, top + V2_TILE_H - 36), f"Amazon price as of {as_of(deal['seen'])}", font=sans(22, "Medium"), fill=MUTED)


def make_image_v2(path, theme, items, cat="Everything else"):
    bg, accent = PALETTES.get(cat, PALETTES["Everything else"])
    img = Image.new("RGB", (PW, PH), bg)
    d = ImageDraw.Draw(img)
    centered(d, 52, "MOM FOUND IT CHEAPER", sans(30, "SemiBold"), (255, 255, 255), spacing=8)
    head = theme.upper()
    hf = fit(d, head, lambda s: sans(s, "Bold"), 104, PW - 120, max_lines=1, min_size=56)
    centered(d, 118, head, hf, (255, 255, 255))
    centered(d, 118 + hf.size + 22, "TODAY'S PRICE DROPS", sans(34, "SemiBold"), accent, spacing=6)
    for i, deal in enumerate(items, 1):
        draw_tile_v2(img, i, deal, V2_TOP + (i - 1) * (V2_TILE_H + V2_GAP), accent)
    d = ImageDraw.Draw(img)
    centered(d, 1292, "PRICES CAN CHANGE  \u00b7  LINK IN COMMENTS  \u00b7  #AD", sans(24, "Medium"), (255, 255, 255), spacing=3, max_w=PW - 60)
    img.save(path)


def link_for(deal):
    return f"{SITE}#d-{hashlib.sha1(deal['id'].encode()).hexdigest()[:10]}"


def texts(theme, items):
    names = [tidy(short_title(no_price_title(i["title"]))) for i in items]
    names = [" ".join(re.sub(r"^\[[^\]]*\]\s*", "", n).split(",")[0].split()[:5]).rstrip(".,;:- ") for n in names]
    caption = (f"✨ {theme} - {names[0]}, {names[1]} and {names[2]} on price drops!\n"
               f"{pick(PERSONAL, items[0]['id'], 'pp')}\n(AD)(Commission earned)\n\n{HASHTAGS}")
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
        theme = THEMES.get(cat, f"{cat} finds")
        if os.environ.get("POST_LAYOUT", "v2") == "v2":
            make_image_v2(OUT / f"post_{n}.png", theme, items, cat)
        else:
            make_image(OUT / f"post_{n}.png", theme, items)
        caption, comment = texts(theme, items)
        (OUT / f"post_{n}.txt").write_text(f"CAPTION:\n{caption}\n\nFIRST COMMENT (paste after posting):\n{comment}\n")
        made.update(i["id"] for i in items)
        print(f"made post_{n}.png - {theme}: " + " | ".join(i["title"][:30] for i in items))
    MADE_FILE.write_text(json.dumps(sorted(made)[-900:], indent=1))
    print(f"{len(groups)} posts made")


if __name__ == "__main__":
    main()
