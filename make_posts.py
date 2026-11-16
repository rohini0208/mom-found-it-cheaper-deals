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
        lines.append(f"{n}{tip}\n{link_for(i)}")
    lines.append("As an Amazon Associate I earn from qualifying purchases.")
    return caption, "\n".join(lines)


def main():
    deals = json.loads(DEALS_FILE.read_text()) if DEALS_FILE.exists() else []
    made = set(json.loads(MADE_FILE.read_text())) if MADE_FILE.exists() else set()
    OUT.mkdir(exist_ok=True)
    groups = pick_groups(deals, made)
    for n, (cat, items) in enumerate(groups, 1):
        theme = THEMES.get(cat, f"{cat} finds")
        make_image(OUT / f"post_{n}.png", theme, items)
        caption, comment = texts(theme, items)
        (OUT / f"post_{n}.txt").write_text(f"CAPTION:\n{caption}\n\nFIRST COMMENT (paste after posting):\n{comment}\n")
        made.update(i["id"] for i in items)
        print(f"made post_{n}.png - {theme}: " + " | ".join(i["title"][:30] for i in items))
    MADE_FILE.write_text(json.dumps(sorted(made)[-900:], indent=1))
    print(f"{len(groups)} posts made")


if __name__ == "__main__":
    main()
